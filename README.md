# 有迹可循 / Youjikexun — Public Demo

面向围绝经期女性的个人身体记录 MVP。一句话留下当天变化，系统永久保留原始表达，把可确认字段投影到身体账本，并在证据足够时给出基于审核知识的 AI 轻量反馈。

> **本仓库是面向评委的公开演示版本。** `backend/data/records.json` 与 `knowledge_chunks.jsonl` 是**明确标记的合成演示数据**，不是任何真实用户的健康数据。真实数据与 API 密钥仅在本地私有仓库中使用，从不提交到公开仓库。

## 技术栈

- 后端：FastAPI + Pydantic 严格模型 + append-only 本地持久化
- 前端：React 19 + TypeScript + Vite，移动端优先
- 硬件：ESP32-S3 + MAX30102（心率）+ INMP441（语音）独立固件
- AI：审核型 RAG 检索 + OpenAI 兼容大模型，输出受校验的三句反馈

## 本地运行

要求 Python 3.10+、Node.js 20.19+。

后端：

```bash
cd backend
python3 -m pip install -r requirements-dev.txt
# 可选：配置 AI 后复制 .env.example -> .env 并填入密钥；不配置时 AI/语音接口会明确返回「未配置」
PYTHONPATH=. python3 -m uvicorn app.main:app --reload
```

前端：

```bash
cd frontend
npm install
npm run dev
```

默认地址：前端 `http://127.0.0.1:5173`，API `http://127.0.0.1:8000`，API 文档 `http://127.0.0.1:8000/docs`。

## 核心页面

- **首页**：一句话记录入口（文字 / 语音长按），保存后 AI 基于审核知识给三句非医疗反馈
- **今日记录**：最近三个真实记录日的当日卡片（标签、总结、推荐继续做 / 不建议做）
- **趋势**：设备采集（心率/血氧）、自述指标（体重/血压/基础体温）、本周总览

## 产品原则

- 缺失就是缺失，不补造未记录日期
- 原始记录与结构化字段分层保存，后续整理不覆盖原文
- 只展示共同出现和调整前后变化，不诊断、不承诺因果
- 一次只给一个轻量行动方向
- 接口未接通时明确显示未配置，不使用 Mock 或静默兜底

## 验证

```bash
PYTHONPATH=backend python3 -m pytest backend/tests -q
cd frontend && npm run typecheck && npm run build
```

## 许可与边界

本项目不是医疗诊断、治疗或处方工具。AI 反馈仅提供生活习惯与记录管理建议，出现疑似疾病问题时只建议持续记录并必要时线下就医。


产品原则：

- 缺失就是缺失，不补造未记录日期；
- 原始记录与结构化字段分层保存，后续整理不覆盖原文；
- 先展示共同出现和调整前后变化，不诊断、不承诺因果；
- 一次只给一个轻量行动方向，不给用户每日打卡压力；
- 接口未接通时明确显示未配置，不使用 Mock 或静默兜底。

## 本次已经实现

- FastAPI + Pydantic 严格后端模型；
- 40 个历史真实记录日的只读导入和确定性字段投影；
- 新文字记录的 append-only 本地持久化；
- 晨起体征、生活方式、身体信号、用户假设、AI 内容和上下文字段；
- 最终运动 Enum、分项时长/组数、原始表达保留和历史字段迁移；
- 睡眠原文、原始分值、量表和可比较性分开存储；
- 关节不适、经期变化、情绪波动三个场景的关键词证据计数；
- React + TypeScript + Vite 移动端优先界面；
- 新手记录、首页、身体账本、发现、方案五个核心视图；
- 新手页的真实文字保存、运行时响应校验、已保存状态和健康数据导航；
- 真实保存、加载、失败、空数据、窄屏、键盘焦点和 reduced-motion 状态；
- 大模型三句话输出契约及禁词校验；
- 审核型 RAG 的条目校验、状态、确定性检索和 OpenAI-compatible 模型接口；
- 语音、大模型、硬件和 RAG 的真实接入状态；
- ESP32-S3 + MAX30102 + LM393 独立固件、严格串口协议和 valid-only 本地桥。

## 明确没有实现

- INMP441 语音采集、降噪和转写尚未接入；MAX30102 心率已完成独立硬件接入；血氧仅有已编译的独立冒烟测试固件，尚未烧录、实测或接入后端；
- 当前工作机已装载并校验 14 条审核通过的 chunks，模型配置也已被后端识别；真实 RAG → LLM 外部调用仍需单独验收；
- 新记录只保存原始文本，不伪造 AI 总结；
- 不生成 11 个缺失自然日，也不把演示用虚拟数据混入真实数据；
- 不推断附件未给出的 Profile / Device 字段；
- 没有账号、权限、云数据库、部署和生产级隐私方案；
- 历史数据内的旧 `hot/cold` 仅作为历史材料保留，不代表新版模型输出；
- 本项目不是医疗诊断、治疗或处方工具。

## 数据文件

内部真实数据放在：

```text
backend/data/records.json
backend/data/records.jsonl
```

运行时以 `records.json` 为历史导入源；`records.jsonl` 是同一数据的逐行版本。新记录写入：

```text
backend/data/user_entries.jsonl
backend/data/knowledge_chunks.jsonl
backend/data/hardware_max30102.jsonl
```

以上文件均被 `.gitignore` 排除。即使当前仓库是 private，真实健康数据与审核知识库仍不应跟随代码提交；将来 public demo 应使用单独、明确标记的合成数据集，而不是修改或复制真实源文件。

## 本地启动

要求：Python 3.10+、Node.js 20.19+。

后端：

```bash
cd backend
python3 -m pip install -r requirements-dev.txt
PYTHONPATH=. python3 -m uvicorn app.main:app --reload
```

前端：

```bash
cd frontend
npm install
npm run dev
```

默认地址：

- 前端：`http://127.0.0.1:5173`
- API：`http://127.0.0.1:8000`
- API 文档：`http://127.0.0.1:8000/docs`

## 当前 API

| Method | Path | 作用 |
|---|---|---|
| GET | `/api/health` | 存活检查 |
| GET | `/api/overview` | 首屏概览、覆盖率、最近记录和三类场景 |
| GET | `/api/ledger?limit=40` | 按时间倒序读取身体账本 |
| GET | `/api/ledger/{entry_id}` | 读取单条账本记录；不存在时返回 404 |
| POST | `/api/entries` | 追加一条原始用户记录 |
| POST | `/api/hardware/max30102/readings` | 追加一条经过严格校验的 MAX30102 原始读数 |
| GET | `/api/hardware/max30102/latest` | 读取最近一条有效 MAX30102 测量；不存在时返回 404 |
| GET | `/api/integrations` | 返回语音、模型、硬件和 RAG 的真实状态 |
| GET | `/api/knowledge/status` | 返回 chunks 文件和审核通过条目的真实状态 |
| POST | `/api/knowledge/preview` | 不调用模型地预览本次检索命中的知识条目 |
| POST | `/api/companion` | 检索 1–2 条审核知识后，调用模型生成受校验的三句反馈 |

## 验证

```bash
PYTHONPATH=backend python3 -m pytest backend/tests -q
cd frontend && npm run typecheck && npm run build
```

## 对齐文档

- [整体架构与代码逻辑](docs/ARCHITECTURE.md)
- [字段与存储契约](docs/FIELD_CONTRACT.md)
- [运动字段最终数据契约](docs/EXERCISE_DATA_CONTRACT.md)
- [大语言模型输出规范](docs/LLM_OUTPUT_POLICY.md)
- [RAG 接入、产品 chunks 交接与模型配置](docs/RAG_HANDOFF.md)
- [硬件数据边界与串口契约](docs/HARDWARE_CONTRACT.md)
- [硬件实现、状态机、参数与限制](docs/HARDWARE_IMPLEMENTATION_ALIGNMENT.md)
- [新手页前端交付包审查与接入边界](docs/FRONTEND_HANDOFF_REVIEW.md)
- [当前实现、限制与阶段对齐](docs/PROJECT_ALIGNMENT.md)
- [历史数据包说明](source-materials/README.data-package.md)
