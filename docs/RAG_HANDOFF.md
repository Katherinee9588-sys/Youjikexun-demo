# RAG 接入与知识条目交接

本文描述当前已实现的 RAG 最小闭环，以及产品侧交付知识条目的唯一格式。它不包含任何真实 chunks、模型密钥或模拟健康内容。

## 1. 当前闭环

```text
产品侧审核过的 knowledge_chunks.jsonl
  -> FastAPI 严格校验
  -> 只选择 review_status = approved 的条目
  -> 本地确定性排序取前 2 条
  -> OpenAI-compatible /chat/completions
  -> 三句 CompanionOutput 校验
  -> 前端按真实接入状态展示
```

这个版本刻意没有向量数据库、Embedding 服务、重排模型、异步队列或缓存。首包知识规模小、题材受控时，直接检索比提前引入复杂基础设施更快、更容易核查来源。每次检索只遍历当前审核通过的条目，不调用模型。

现阶段由于 `backend/data/knowledge_chunks.jsonl` 尚未交付，知识库状态为 `not_loaded`；这是正常的未接入状态，不是模拟数据。

## 2. 产品侧唯一交付文件

把真实条目逐行放入：

```text
backend/data/knowledge_chunks.jsonl
```

该文件已在 `.gitignore` 中排除，不能提交到仓库。文件是 JSONL：**一行一个 JSON 对象**，没有外层数组、没有空行。

以下仅是字段形状示例，方括号内容必须由产品侧替换为已经核对的真实信息，不能原样写入数据文件：

```json
{
  "chunk_id": "[stable-lowercase-id]",
  "scene_tags": ["[menstrual|joint_pain|emotion]"],
  "intent_tags": ["[record|observe|routine|sleep|movement|warmth|emotion]"],
  "title": "[4-80 characters]",
  "content": "[120-350 characters, one independently usable non-medical knowledge statement]",
  "source_publisher": "[publisher]",
  "source_title": "[source title]",
  "source_url": "https://[direct-source-url]",
  "accessed_at": "2026-08-28",
  "evidence_type": "guideline",
  "safety_boundary": "[what this chunk cannot conclude or advise]",
  "review_status": "approved",
  "version": "1.0"
}
```

### 字段约束

| 字段 | 约束 | 用途 |
|---|---|---|
| `chunk_id` | 小写字母、数字、`_`、`-`；3–64 字；文件内唯一 | 稳定引用与排序 |
| `scene_tags` | 1–3 个：`menstrual`、`joint_pain`、`emotion` | 场景匹配 |
| `intent_tags` | 1–3 个：`record`、`observe`、`routine`、`sleep`、`movement`、`warmth`、`emotion` | 意图匹配 |
| `title` | 4–80 字 | 检索与前端溯源标题 |
| `content` | 120–350 字 | 放进模型上下文的、可独立理解的内容 |
| `source_publisher` | 2–80 字 | 来源机构 |
| `source_title` | 4–160 字 | 原始资料标题 |
| `source_url` | 直接且有效的 `http(s)` 来源 | 溯源链接 |
| `accessed_at` | `YYYY-MM-DD` | 来源核查日期 |
| `evidence_type` | `guideline`、`public_health`、`review` | 资料类型 |
| `safety_boundary` | 12–180 字 | 本条不能推断、不能建议的边界 |
| `review_status` | `draft`、`approved`、`rejected` | 只有 `approved` 会进入检索 |
| `version` | `主版本.次版本`，例如 `1.0` | 资料更新追踪 |

任何一行为空、不是合法 JSON、字段缺失、字段超限或 `chunk_id` 重复，API 会直接返回 422 和行号；不会跳过坏行继续回答。

### 内容拆分规则

一个 chunk 只说一个可以独立引用的生活记录或日常养护要点。不要把整篇文章、多个互不相关的建议、诊断判断、疗效承诺或用药指导放在同一条里。

建议交付链路：来源链接 → 人工阅读 → 用自己的话压缩为一个 120–350 字条目 → 填写边界和标签 → 医疗边界审核 → 标记 `approved`。未审核材料保留为 `draft`，可以存在文件里，但不会被检索。

## 3. 检索规则与限制

代码位置：[knowledge_retrieval.py](../backend/app/services/knowledge_retrieval.py)。

1. 只读取 `approved` 条目。
2. 对中文查询取连续双字词，对英文取单词；与标题、内容、来源标题、场景标签、意图标签匹配。
3. 用户文本命中场景词时，同场景加 3 分；命中意图词时，同意图加 2 分。
4. 按分数降序、再按 `chunk_id` 升序稳定排序；最多返回 3 条，模型回答固定使用前 2 条。
5. 没有匹配条目时，预览接口返回空数组；真正调用模型的接口返回 422，且绝不调用模型。

固定场景词：

```text
menstrual: 经期、生理期、月经、经量、出血
joint_pain: 关节、膝盖、手腕、肩周、僵硬
emotion: 情绪、烦躁、焦虑、低落、压力、想哭
```

固定意图词：

```text
record: 记录、日记、账本
observe: 观察、变化、规律
routine: 作息、规律、节奏
sleep: 睡眠、入睡、醒来、起夜
movement: 运动、训练、拉伸、力量、有氧
warmth: 保暖、暖、热
emotion: 情绪、烦躁、焦虑、低落、压力
```

这不是“万能问答知识库”。它只支持当前产品明确的经期、关节、情绪记录场景；新功能被砍掉前不扩大标签和查询范围。

## 4. API 契约

| Method | Path | 输入 | 成功结果 |
|---|---|---|---|
| GET | `/api/knowledge/status` | 无 | `not_loaded`、`loaded_no_approved_chunks` 或 `ready`，附总数和审核通过数 |
| POST | `/api/knowledge/preview` | `{"query":"...","limit":1-3}` | 查询文本和可审查 passages；允许空 `passages` |
| POST | `/api/companion` | `{"user_text":"..."}` | 三句输出与本次使用的 1–2 条 passages |

`/api/companion` 的失败语义：

| HTTP | 含义 |
|---|---|
| 409 | chunks 文件尚未放入 |
| 422 | chunks 不合法，或没有已审核的匹配知识 |
| 503 | `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL` 尚未完整配置 |
| 502 | 上游模型请求失败，或模型输出不符合三句 JSON 契约 |

接口不会把问题伪装成可用的建议。

### `passages` 返回形状

```json
{
  "chunk_id": "...",
  "title": "...",
  "content": "...",
  "source_publisher": "...",
  "source_title": "...",
  "source_url": "https://...",
  "safety_boundary": "...",
  "relevance_score": 1,
  "matched_terms": ["..."]
}
```

`relevance_score` 只用于当前检索排序和调试，不是医学评分或健康风险评分。

## 5. 大模型配置

密钥只放在本机：

```bash
cd backend
cp .env.example .env
```

编辑 `backend/.env`：

```dotenv
LLM_API_KEY=你的服务商密钥
LLM_BASE_URL=https://你的服务商地址/v1
LLM_MODEL=你的模型名
```

服务期望 OpenAI-compatible Chat Completions 协议，因此最终会请求：

```text
{LLM_BASE_URL}/chat/completions
```

`.env` 被 Git 忽略，前端不会收到密钥。后端启动时由 `python-dotenv` 加载它；配置任何一个字段但漏掉其余字段时，接入状态显示 `configuration_error`，而不是猜测默认地址或模型。

请求参数固定为 `temperature: 0.2`、`max_tokens: 160`，超时固定为 20 秒，无重试。这样有利于稳定三句 JSON，并避免前端长时间等待。

## 6. 模型约束

代码位置：[companion_policy.py](../backend/app/services/companion_policy.py)。模型收到的系统约束是：

```text
你是面向围绝经期女性的陪伴式健康记录与生活调理助手。
你不具备医疗诊断、治疗、处方能力，只提供生活习惯、作息、情绪、日常养护和记录管理建议。
只返回 JSON：{"empathy":"第一句。","suggestion":"第二句。","outlook":"第三句。"}
三句话每句 10–20 个汉字。第一句鼓励共情；第二句给一项非医疗生活建议；第三句给轻量正向展望。
先在本次单次回答内判断用户意图，不要因为用户原文出现一个医疗词就拒答，也不要调用额外分类流程。
用户只是在记录或描述症状、转述既往说法、表达担心或记录变化时，继续按陪伴式记录回答，不触发医疗边界。
只有用户明确索要诊断、病因、治疗方案、用药建议、处方，或要求替代医生判断时，才触发医疗边界。
触发医疗边界时，必须返回：{"empathy":"我理解你想弄清这次变化。","suggestion":"这部分请带记录到线下门诊咨询医生。","outlook":"我们可以先继续记录变化和当时情境。"}
不得判断症状轻重，不得指导用药，不得替代医生，不得使用医疗禁词。
经期场景只谈记录、作息、日常暖护和规律观察；关节场景只谈保暖、轻度放松、作息和姿势；情绪场景只谈放松、节奏、自我接纳和记录。
出现疑似疾病问题时，只建议持续记录、规律观察，必要时线下就医。
只能依据下方已审核知识回答；没有依据时不得补充事实。
```

模型必须只返回 JSON 对象，且三个字段均为一个以中文句号结尾的 10–20 字句子。以下词出现即拒绝响应：`治愈`、`治好`、`治疗`、`病灶`、`炎症`、`病变`、`康复`、`药效`、`确诊`、`用药`、`药物`、`处方`、`严重`、`轻微`。

模型原始输出不合规时，后端返回 502；不自动修句、不追加兜底文案、不把未经验证的文本写入用户账本。

## 7. 前端边界

当前 UI 只显示 `overview.integrations` 的真实模型与知识库状态；没有把“模型已配置”展示成“模型已经可回答”。等 UI 交付合并后，调用 `/api/companion` 前先调用或读取 `/api/knowledge/status`，并在 409、422、503、502 时把后端具体错误直接呈现给开发者或内部测试人员。

前端请求封装已经保留 `getKnowledgeStatus`、`previewKnowledge`、`generateCompanion`，但尚未做一个假聊天页。这样不会让未完成 UI 占用页面数量，也不会产生无法验证的交互。

## 8. 本地验证

```bash
PYTHONPATH=backend python3 -m pytest backend/tests -q
cd frontend && npm run typecheck && npm run build
```

带有实际 chunks 与模型密钥后，可先用 `/docs` 的 `/api/knowledge/preview` 检查命中条目和来源，再调用 `/api/companion`。先验证检索再验证模型，两个阶段分开排错。

## 9. 首次模型建议

第一次接入优先选：`Qwen/Qwen2.5-7B-Instruct`。

原因不是它“医疗更权威”，模型不应承担医学判断；而是这个 MVP 只需要在 1–2 条已审核知识的约束下稳定输出很短的中文 JSON。7B Instruct 模型的计算开销较低、Apache-2.0 授权清晰，并且没有把推理过程混入输出的额外处理要求，适合先把协议跑通。官方模型页和 Qwen 文档都提供了标准部署入口；Qwen 文档也给出了通过 OpenAI-compatible 服务暴露 Qwen2.5-7B-Instruct 的路径。

建议首次配置：

```dotenv
LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
```

前提是主办方提供的算力或网关确实提供该模型与 OpenAI-compatible `/v1/chat/completions`。本项目不在代码里锁死该模型名：不同服务商只需要替换 `backend/.env` 的三项配置即可。

如果主办方只提供 Qwen3-8B，也能接，但必须确认服务端关闭思考输出或能保证 `message.content` 直接是 JSON。当前适配器会严格解析该字段，不会剥离 `<think>`、Markdown 代码块或自然语言前后缀；这正是为了让不合规输出立刻暴露。

参考：<https://huggingface.co/Qwen/Qwen2.5-7B-Instruct>、<https://github.com/QwenLM/Qwen3/blob/main/docs/source/quantization/gptq.md>。
