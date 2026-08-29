# 有迹可循（Youjikexun）0.2代码解读（无RAG/LLM/硬件/UIUX前端）

> 历史阶段说明：本节保留早期代码解读，不代表 2026-08-29 当前状态。当前状态以本文后半部分“有迹可循（Youjikexun）项目对齐说明”为准。
先给结论：当前代码是“契约优先的内部 MVP”，真正闭环的是：

```text
真实历史数据读取
+ 新文字记录保存
+ 明确字段投影
+ 身体账本展示
```

语音、大模型、RAG、硬件都没有假装接通。这条回复只解释代码，没有继续修改。

## 一、整体架构

```text
历史数据 records.json ──→ 严格校验 ──→ 历史账本投影
                                         │
新文字记录 ──POST /entries──→ user_entries.jsonl
                                         │
                                         ↓
                                统一 LedgerEntry
                                         │
                      ┌──────────────────┼─────────────────┐
                      ↓                  ↓                 ↓
                   首页概览           身体账本          三类场景
```

技术栈：

- 后端：FastAPI + Pydantic。
- 前端：React 19 + TypeScript + Vite。
- 存储：内部 MVP 暂用 JSON/JSONL。
- 图表：原生 SVG。
- 没有数据库、Redux、路由库、图表库和模型 SDK。

完整说明在 [ARCHITECTURE.md](/Users/catherine/Documents/Codex/Youjikexun/docs/ARCHITECTURE.md)。

## 二、三个原始数据文件分别是什么

- `records.json`：40 条历史记录组成的 JSON 数组，是当前后端真正读取的运行时数据源。
- `records.jsonl`：相同数据的一行一条版本，当前代码不读取，保留给流式处理、导入或数据工具使用。
- `schema.json`：规定单条历史记录只能包含 `date`、`day_number`、`user_input`、`feedback`。

新提交的记录使用第四个文件：

```text
backend/data/user_entries.jsonl
```

三个真实数据文件都在 `.gitignore` 中：

```text
records.json
records.jsonl
user_entries.jsonl
```

仓库即使是 private，也不提交真实健康数据；未来公开 Demo 使用独立合成数据集。

## 三、后端数据模型

核心模型位于 [health.py](/Users/catherine/Documents/Codex/Youjikexun/backend/app/models/health.py:9)。

所有主要模型都继承 `StrictModel`：

```python
ConfigDict(extra="forbid")
```

意思是：API 或数据文件出现未定义字段时直接报错，不静默丢弃。

### 1. 历史记录 `HealthRecord`

```text
date
day_number
user_input
feedback.hot
feedback.cold
```

这是不可变的历史导入结构。旧 `hot/cold` 只保留在 `legacy_feedback`，不会被当成新版模型回复。

### 2. 晨起体征 `MorningVitals`

```text
record_date
body_weight
body_fat_rate
blood_pressure_readings[]
```

血压采用数组，因为一天可能测量多次：

```text
systolic_pressure
diastolic_pressure
heart_rate
measurement_context[]
```

不会先求平均，也不会把不同情境压缩成一个值。

### 3. 睡眠 `SleepObservation`

```text
recorded
raw_text
raw_value
raw_scale
normalized_1_10
comparable
bed_time
wake_time
interruptions
extraction_notes[]
```

“睡眠：70分”的实际结果：

```json
{
  "recorded": true,
  "raw_value": 70,
  "raw_scale": null,
  "normalized_1_10": null,
  "comparable": false,
  "extraction_notes": ["睡眠记录有效，但评分量表未确认"]
}
```

它会进入历史库，但不会自动变成 7 分。

如果明确写成 `70/100`：

```text
raw_value = 70
raw_scale = 100
normalized_1_10 = null
comparable = false
```

依然不转换。

### 4. 生活方式

```text
meals[]
exercise_type
exercise_duration
exercise_sets
sleep
```

餐次目前支持：

```text
breakfast / 早餐 / 早饭
lunch / 午餐 / 午饭
dinner / 晚餐 / 晚饭
snack / 加餐
```

`meal_tag` 当前始终为空数组，因为没有确定的标签字典，不会根据食物描述猜测标签。

运动目前只识别历史结构化字段：

```text
core_sets       → 核心
glute_leg_sets  → 力量
back_sets       → 力量
cardio_minutes  → 有氧
```

附件里的完整运动枚举被截断，所以代码暂时用 `string | null`，没有猜一个错误 Enum。

### 5. 身体信号

```text
symptom_location
symptom_desc
symptom_trend
symptom_triggers
```

当前只有原文明确包含 `body_signals` 或“身体信号”字段时才创建记录。

暂时不会从任意自由文本中自动推断：

- 身体部位；
- 变化趋势；
- 诱因；
- 症状严重程度。

### 6. 用户自己的心理模型

```text
today_highlight
tomorrow_one_change
execution_resistance
user_hypothesis
```

对应：

- 今天做对的一件事；
- 明天只改一件事；
- 今天最大的执行阻力；
- 我以为 / 用户假设。

这些只是用户自己的表达，不会升级为系统结论。

### 7. AI 内容

```text
ai_daily_summary
ai_hypothesis_validation
```

当前都为 `null`，因为真实模型未接入。

完整字段表见 [FIELD_CONTRACT.md](/Users/catherine/Documents/Codex/Youjikexun/docs/FIELD_CONTRACT.md)。

## 四、字段提取逻辑

提取器位于 [journal_projection.py](/Users/catherine/Documents/Codex/Youjikexun/backend/app/services/journal_projection.py:25)。

它不是大模型，也不是通用自然语言理解，只识别明确格式。

### 体重和体脂

支持：

```text
体重：55.6
体重（是否大便后）：55.75
weight_kg：55.9

体脂：28.4
体脂率：28.4
body_fat_percent：28.5
```

找不到就是 `null`。

### 血压

优先读取结构化形式：

```text
systolic
diastolic
heart_rate
context
```

找不到后，才在包含“血压”的行内读取：

```text
126/90 73
```

这样不会把其他 `70/100` 误认为血压。

### 睡眠

识别：

```text
sleep_score_1_10
睡眠：8分
睡眠：70分
睡眠：70/100
bed_time
wake_time
sleep_interruptions
```

量表不明确时保留原值，不做换算。

### 运动、餐次、身体信号、用户复盘

都只读取明确字段名。自由描述没有对应字段名时保持未提取状态。

## 五、新记录怎样保存

保存逻辑在 [entries.py](/Users/catherine/Documents/Codex/Youjikexun/backend/app/repositories/entries.py:10)。

用户提交：

```json
{
  "record_date": "2026-08-28",
  "original_text": "今天下午有点烦躁，昨晚睡得晚。",
  "input_method": "text"
}
```

后端生成：

```text
UUID
UTC 创建时间
extraction_status = pending
```

然后追加到 `user_entries.jsonl`，不会覆盖过去内容。

当前新记录会经过基础确定性投影，但 `pending` 表示“语义/模型整理还没完成”。这里命名存在一点歧义，我在最后列为需要确认项。

历史记录和新记录合并后，按照：

```text
record_date
→ 同日再按 created_at
```

排序。

允许同一天存在多条新记录：

- `entry_count` 会增加；
- `recorded_day_count` 按唯一日期统计，不会重复增加。

## 六、概览和三类场景

概览逻辑在 [overview.py](/Users/catherine/Documents/Codex/Youjikexun/backend/app/services/overview.py:15)。

当前真实数据统计：

```text
记录条数：40
实际记录日：40
自然跨度：51 天
缺失自然日：11 天

体重覆盖：39
体脂覆盖：30
血压覆盖：29
心率覆盖：26
睡眠记录：40
可比较睡眠评分：22
```

11 个缺失日不会生成空记录，更不会生成虚拟数据。

三类场景逻辑在 [scene_summary.py](/Users/catherine/Documents/Codex/Youjikexun/backend/app/services/scene_summary.py:8)。

关键词：

```text
关节不适：
关节、膝盖酸痛、手腕僵硬、肩周、僵硬酸痛

经期变化：
经期、生理期、月经、经量、出血

情绪波动：
情绪、烦躁、焦虑、低落、压力、想哭
```

当前出现次数：

```text
关节相关：1 条
经期相关：4 条
情绪相关：20 条
```

这不是“症状发生次数”，只是“有多少条原始记录包含相关表达”。

固定边界字符串是：

> 这里只统计关键词出现次数，不判断症状、原因或严重程度。

## 七、API

路由在 [routes.py](/Users/catherine/Documents/Codex/Youjikexun/backend/app/api/routes.py:17)。

| API | 逻辑 |
|---|---|
| `GET /api/health` | 存活检查 |
| `GET /api/overview` | 首屏概览、最近六条、覆盖率、场景计数 |
| `GET /api/ledger?limit=40` | 倒序读取账本，限制 1–100 |
| `GET /api/ledger/{id}` | 精确读取一条，不存在返回 404 |
| `POST /api/entries` | 追加原始记录 |
| `GET /api/integrations` | 返回真实接入状态 |

接入状态的固定值：

```json
{
  "voice_transcription": "not_configured",
  "language_model": "contract_ready_not_configured",
  "hardware_adapter": "interface_ready_not_configured",
  "rag_retriever": "interface_ready_not_configured"
}
```

## 八、前端逻辑

主页面在 [App.tsx](/Users/catherine/Documents/Codex/Youjikexun/frontend/src/App.tsx:8)。

### 首页

- 首次只请求 `/api/overview`。
- 显示 40/51/11。
- 可以提交文字记录。
- 语音按钮禁用并写明“语音待接入”。
- 保存成功后重新请求 overview，并把账本缓存设为待重新读取。

### 身体账本

只有第一次进入时才请求：

```text
GET /api/ledger?limit=100
```

因此首屏不会加载全部长文本。

当前详情弹窗直接使用账本列表中已经返回的数据，不会再次请求 `/ledger/{id}`。单条接口为未来直接访问详情保留。

### 发现

只展示三类关键词证据，不展示原因、诊断或相关性结论。

### 方案

展示最近一条记录中的：

- 明天只改一件事；
- 今天做对的一件事；
- 执行阻力；
- 用户假设；
- 三句话模型契约。

不会生成假建议。

### 趋势图

代码在 [MetricTrend.tsx](/Users/catherine/Documents/Codex/Youjikexun/frontend/src/components/MetricTrend.tsx:26)。

逻辑：

1. 从最近六条记录中过滤有体重的记录；
2. 按真实日期排序；
3. X 轴按照真实时间间隔计算；
4. 相邻记录日期间隔超过一天时断线；
5. 不插值、不补点。

如果只有一个点或所有体重相同，代码使用 `1` 作为 SVG 除数保护。这只是避免除零，不会生成新的健康数据。

### 详情弹窗

代码在 [LedgerDialog.tsx](/Users/catherine/Documents/Codex/Youjikexun/frontend/src/components/LedgerDialog.tsx:10)。

睡眠显示规则：

```text
没有记录           → 未记录
只有文字           → 已记录文字描述
有分值但量表未知    → 70 分 · 量表未确认
明确 1–10          → 8 / 10
```

历史 `hot/cold` 会明确标为“历史反馈”。

## 九、大模型字符串和限制

代码在 [companion_policy.py](/Users/catherine/Documents/Codex/Youjikexun/backend/app/services/companion_policy.py:8)。

固定 JSON：

```json
{
  "empathy": "第一句。",
  "suggestion": "第二句。",
  "outlook": "第三句。"
}
```

规则：

- 必须正好三个字段；
- 每个字段只能有一句话；
- 必须以中文句号结束；
- 去除标点后每句 10–20 个字；
- 不允许额外字段；
- 整个输出命中禁词就拒绝；
- 不自动修改、不自动重试、不返回备用文案。

禁词：

```text
治愈、治好、治疗、病灶、炎症、病变、康复、药效、确诊
用药、药物、处方、严重、轻微
```

三类场景限制：

- 经期：只谈记录、作息、日常暖护、周期观察。
- 关节：只谈保暖、轻度放松、作息、姿势。
- 情绪：只谈放松、节奏、自我接纳、记录。
- 用户只是在记录或描述、转述既往说法、表达担心时，不因医学词触发拒答，仍按记录陪伴处理。
- 用户明确索要诊断、病因、治疗方案、用药建议、处方或替代医生判断时，模型返回固定的温和三句线下门诊边界回复。

这个意图判断包含在同一次模型调用的系统提示词中；不增加关键词拦截器、额外分类模型或第二次请求。没有审核知识、模型配置或合规输出时仍明确报错，不生成备用文案。

完整系统提示词逐字放在 [LLM_OUTPUT_POLICY.md](/Users/catherine/Documents/Codex/Youjikexun/docs/LLM_OUTPUT_POLICY.md)。

## 十、“不要兜底”在代码里的实际含义

目前没有：

- Mock 数据；
- 虚拟日期；
- 自动模型重试；
- 多供应商切换；
- 静默吞掉后端错误；
- `data || mockData`；
- `value ?? defaultHealthValue`；
- 假 AI 总结。

但保留了几个不制造数据的正常状态：

- 字段没记录：`null`，页面显示“未记录”。
- `user_entries.jsonl` 尚未创建：代表还没有新记录，返回空集合。
- 图表只有一个值：防止 SVG 除零。
- JavaScript 抛出的不是标准 `Error`：显示“请求失败”。
- DOM 弹窗引用不存在：不调用关闭方法。

这些是程序状态保护，不是业务数据兜底。

## 十一、当前明确限制

1. JSONL 适合内部 MVP，不支持多用户并发写入。

2. 每次读取新账本会扫描整个 `user_entries.jsonl`；数据很小时很快，长期正式使用需要数据库。

3. 当前没有账号和用户隔离。

4. 前端四个页面使用 React 内部状态，不是 URL 路由；刷新后回到首页。

5. UI 文字目前直接写在组件里，没有做 i18n 或统一文案配置。

6. `Amy` 是场景故事中的内部演示名，不是已实现的 Profile 字段。

7. Profile 和 Device 的完整字段表没有提供，因此没有猜。

8. 场景发现只是关键词计数，不是统计相关性、趋势分析或医学判断。

9. 新自由文本没有模型时，只能提取明确字段名，不能完成语义整理。

10. 大模型输出契约已经完成，但调用、密钥、供应商、持久化、评测都未实现。

## 十二、现在需要我们确认的四个点

这四个不是增加功能，而是解决现有文件之间的契约细节：

1. **三句话如何落库存储**

   当前 `CompanionOutput` 是：

   ```text
   empathy / suggestion / outlook
   ```

   字段表却是：

   ```text
   ai_daily_summary / ai_hypothesis_validation
   ```

   我的建议：三句话完整合并存入 `ai_daily_summary`；只有用户确实写了假设时，才单独生成 `ai_hypothesis_validation`。

2. **`pending` 的准确含义**

   当前新记录已经做基础规则投影，但仍标记 `pending`，意思是“等待模型语义整理”。建议后续改名为 `semantic_extraction_status`，避免误解为整条记录完全没处理。

3. **运动 Enum**

   当前暂用“核心 / 力量 / 有氧”字符串。需要完整附件枚举后才能封闭为真正 Enum。

4. **Profile / Device**

   当前只有页面演示名和硬件 Protocol，没有存储字段。需要完整字段表后才能实现，不能从截图猜。

我认为第 1 项最需要先对齐，其余三个可以保持当前状态，不影响继续接大模型。














//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////



# 有迹可循（Youjikexun）项目对齐说明

> 用途：给产品、设计、前端和后端共同阅读的当前实现说明。本文描述的是仓库当前代码，不把计划中的能力写成已完成能力。
>
> 更新时间：2026-08-29

## 1. 当前版本一句话

这是一个面向围绝经期女性的个人身体记录 MVP：用户用一句话留下当天变化，系统保留原始表达，把能确认的字段投影到身体账本，再展示数据覆盖、真实日期趋势和三类场景中的原始证据。

当前完成了“记录—保存—投影—展示”闭环、最终运动 Enum、RAG 条目校验与检索 API，以及 OpenAI-compatible 模型适配器。当前工作机有 14 条 approved chunks，模型配置已被识别；真实 RAG → LLM 外部调用仍待验收。MAX30102 心率固件、严格协议、后端 API 和 valid-only 串口桥代码已完成；SpO2 独立测试固件已编译但尚未烧录/实测。真实 USB → API 联跑、SpO2 合入、INMP441/STT 和前端硬件展示尚未完成。

## 2. 最新资料和优先级

本实现依据以下最新资料：

- 路演文件：`/Users/catherine/Downloads/wip 路演.pdf`
- 黑客松功能方案：`/Users/catherine/Downloads/围绝经期女性健康记录管理软件场景故事与功能方案（黑客松参赛版）.pdf`
- 字段表与大模型输出规范：`/Users/catherine/Downloads/一、存储字段表.docx`

资料共同确认的产品方向：

- 移动端优先，桌面端兼容；
- 一句话记录，不强迫每日记录；
- 真实缺失日期保持缺失；
- 未来只砍功能，不继续扩张功能；
- 先展示共同出现、调整前后变化和记录证据，不擅自诊断或判断因果；
- 一次只给一个轻量生活调整方向。

## 3. 整体数据流

```text
历史 records.json
    ↓ RecordRepository 严格读取和校验
legacy HealthRecord
    ↓ project_legacy()
历史 LedgerEntry（partial）

新的一句话记录
    ↓ POST /api/entries
UserEntryCreate 严格校验
    ↓ EntryRepository.append()
backend/data/user_entries.jsonl（append-only）
    ↓ project_user_entry()
新 LedgerEntry（pending）

历史 LedgerEntry + 新 LedgerEntry
    ↓ all_ledger() 按日期排序
统一身体账本
    ↓ overview / ledger API
React 四个核心视图

审核型 RAG
    ↓ backend/data/knowledge_chunks.jsonl
严格行级校验 → 只选 approved → 确定性检索前 2 条
    ↓ /api/companion
OpenAI-compatible 模型调用 → 三句 JSON 安全校验
```

重要原则：

1. 原始文本永远保留，结构化字段不能覆盖原文。
2. 没有记录的日期不创建空记录，也不创建虚拟健康数据。
3. 解析器只识别明确格式，不猜测自由文本的医学含义。
4. API 或模型出错时显示错误，不渲染假数据。

## 4. 数据文件和隐私

### 4.1 历史数据

```text
backend/data/records.json
backend/data/records.jsonl
backend/data/schema.json
```

- `records.json`：40 条历史记录的 JSON 数组，当前后端运行时读取它。
- `records.jsonl`：相同记录的一行一条版本，当前后端不直接读取。
- `schema.json`：历史记录的 JSON Schema。

### 4.2 新记录

```text
backend/data/user_entries.jsonl
backend/data/knowledge_chunks.jsonl
```

每次新增一行，不覆盖旧内容。缺少该文件代表还没有新记录，这是正常的空存储状态；文件存在但出现空行或坏 JSON 时直接报错。

### 4.3 Git 规则

以上文件都在根目录 `.gitignore` 中。当前仓库是 private，也不提交真实健康数据或审核知识包。未来 public demo 必须使用单独的合成数据集，并明确标记为 Demo，不得复制真实源文件。

## 5. 历史数据事实

当前真实数据经代码读取后的事实：

```text
实际记录条数：40
实际记录日：40
最早日期：2026-07-01
最晚日期：2026-08-20
自然跨度：51 天
没有记录的自然日：11 天
```

当前字段覆盖：

```text
体重：39 条
体脂率：30 条
血压：29 个记录日
心率：26 个记录日
睡眠记录：40 条
可比较的 1–10 睡眠评分：22 条
```

这些数字是从真实源数据计算出来的，不是填充数据。

## 6. 后端技术栈和文件职责

### 6.1 技术栈

- Python 3.10+
- FastAPI
- Pydantic 2
- python-dotenv
- Uvicorn
- pytest

### 6.2 文件职责

| 文件 | 职责 |
|---|---|
| `backend/app/main.py` | 创建 FastAPI 应用、CORS 和路由 |
| `backend/app/api/routes.py` | HTTP 路由，只负责入参和调用服务 |
| `backend/app/models/health.py` | 严格的数据模型和 API 响应模型 |
| `backend/app/repositories/records.py` | 读取和校验历史 records.json |
| `backend/app/repositories/entries.py` | 追加和读取 user_entries.jsonl |
| `backend/app/services/journal_projection.py` | 从原文投影结构化字段 |
| `backend/app/services/overview.py` | 计算日期跨度、覆盖率和接入状态 |
| `backend/app/services/scene_summary.py` | 三类场景的关键词证据计数 |
| `backend/app/repositories/knowledge.py` | 读取、行级校验和审核状态统计 |
| `backend/app/services/knowledge_retrieval.py` | 小型知识包确定性检索 |
| `backend/app/services/llm_settings.py` | 从 `backend/.env` 读取模型配置 |
| `backend/app/services/companion_policy.py` | 大模型三句话输出校验与引用条目响应模型 |
| `backend/app/integrations/openai_compatible_llm.py` | 调用 OpenAI-compatible `/chat/completions` |
| `backend/app/integrations/llm.py` | 语言模型适配器 Protocol |
| `backend/app/integrations/hardware.py` | 未来硬件读数适配器 Protocol |
| `backend/app/integrations/rag.py` | 知识检索适配器 Protocol |

### 6.3 严格模型

主要模型都禁止未知字段：

```python
class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
```

因此，字段拼错、传入附件没有定义的字段、结构不完整，都会直接暴露。

## 7. 存储字段契约

完整字段对齐见 [FIELD_CONTRACT.md](./FIELD_CONTRACT.md)。当前核心结构如下。

### 7.1 晨起客观体征

```text
record_date
body_weight
body_fat_rate
blood_pressure_readings[]
```

每条血压读数：

```text
systolic_pressure
diastolic_pressure
heart_rate
measurement_context[]
```

同一天允许多组读数，不先平均。

### 7.2 生活方式

```text
meals[]
exercise_type
exercise_duration
exercise_sets
sleep
```

餐次固定为：

```text
breakfast / lunch / dinner / snack
```

`meal_tag` 当前为空数组，因为附件没有给出完整标签规则，系统不根据食物文本猜标签。

### 7.3 身体信号

```text
symptom_location
symptom_desc
symptom_trend
symptom_triggers
```

目前只有原文明确出现 `body_signals` 或“身体信号”时，才创建 `PhysicalSignal`。

### 7.4 用户自己的复盘

```text
today_highlight
tomorrow_one_change
execution_resistance
user_hypothesis
```

每个字段最多 100 字，只保存用户表达，不把用户假设升级成系统结论。

### 7.5 AI 内容

```text
ai_daily_summary
ai_hypothesis_validation
```

当前始终为 `null`。原因是模型供应商尚未接入，不能生成假的总结。

### 7.6 上下文

```text
weather_temp
special_stress
```

### 7.7 暂不猜测的字段

附件中 Profile、Device 的具体字段和部分 Enum 截图没有完整提供。当前不创建猜测字段，避免先做错数据契约再绑架前端。

## 8. 确定性字段投影

代码位置：[journal_projection.py](../backend/app/services/journal_projection.py)

这不是 NLP 模型，只做低成本、可审计的明确格式识别。

### 8.1 体重和体脂

支持的主要格式：

```text
体重：55.6
体重（是否大便后）：55.75
weight_kg：55.9
体脂：28.4
体脂率：28.4
body_fat_percent：28.5
```

没有匹配时返回 `null`。

### 8.2 血压

优先识别结构化文本：

```text
systolic：123
diastolic：92
heart_rate：75
context：起床后，大便后
```

如果没有结构化格式，再只扫描包含“血压”的行，例如：

```text
126/90 73
```

这样不会把其他文本中的 `70/100` 误判为血压。

### 8.3 睡眠

支持：

```text
睡眠：8分
睡眠：70分
睡眠：70/100
sleep_score_1_10：8
bed_time：22:00
wake_time：06:00
sleep_interruptions：1
```

睡眠 1–10 规则：

| 输入 | `recorded` | `raw_value` | `raw_scale` | `normalized_1_10` | `comparable` |
|---|---:|---:|---:|---:|---:|
| `睡眠：8分` | true | 8 | 10 | 8 | true |
| `睡眠：70分` | true | 70 | null | null | false |
| `睡眠：70/100` | true | 70 | 100 | null | false |
| 没有睡眠信息 | false | null | null | null | false |

“70 分”是有效睡眠记录，但量表未知，不会擅自除以 10。

### 8.4 餐次、运动和复盘

只有明确的字段名或明确的餐次前缀才会被投影。普通自由文本中的暗示不会自动升级为结构化字段。

当前运动字段只识别：

```text
core_sets       → 核心
glute_leg_sets  → 力量
back_sets       → 力量
cardio_minutes  → 有氧
```

### 8.5 当前刻意不做的事情

- 不自动识别所有症状部位；
- 不自动判断症状变好、变差或严重程度；
- 不自动打食物标签；
- 不从自由文本计算热量、激素、HRV、体温或睡眠分期；
- 不把用户的因果猜想变成系统事实。

## 9. 三类核心场景

代码位置：[scene_summary.py](../backend/app/services/scene_summary.py)

当前只做关键词出现计数。

| 场景 ID | 展示名 | 当前关键词 |
|---|---|---|
| `joint_pain` | 关节不适 | 关节、膝盖酸痛、手腕僵硬、肩周、僵硬酸痛 |
| `menstrual` | 经期变化 | 经期、生理期、月经、经量、出血 |
| `emotion` | 情绪波动 | 情绪、烦躁、焦虑、低落、压力、想哭 |

当前真实数据中的关键词记录数为：

```text
关节不适：1
经期变化：4
情绪波动：20
```

这些不是症状发生次数，也不是诊断结果。固定边界字符串：

> 这里只统计关键词出现次数，不判断症状、原因或严重程度。

## 10. API 契约

代码位置：[routes.py](../backend/app/api/routes.py)

| Method | Path | 作用 |
|---|---|---|
| GET | `/api/health` | 后端存活检查 |
| GET | `/api/overview` | 首屏概览、覆盖率、最近 6 条记录和场景证据 |
| GET | `/api/ledger?limit=40` | 按日期倒序读取账本，limit 为 1–100 |
| GET | `/api/ledger/{entry_id}` | 读取单条账本；不存在时返回 404 |
| POST | `/api/entries` | 追加一条用户原始记录，返回 201 |
| GET | `/api/integrations` | 返回真实接入状态 |
| GET | `/api/knowledge/status` | 返回知识包文件和审核通过数 |
| POST | `/api/knowledge/preview` | 查询实际会命中的审核知识条目，不调用模型 |
| POST | `/api/companion` | 检索审核知识后调用模型，返回三句输出与使用条目 |

新增记录请求：

```json
{
  "record_date": "2026-08-28",
  "original_text": "今天下午有点烦躁，昨晚睡得晚。",
  "input_method": "text"
}
```

生成的内部字段：

```text
id：UUID
created_at：UTC 时间
extraction_status：pending
source：user_entry
```

## 11. 接入状态字符串

当前 API 根据真实本地配置返回：

```json
{
  "voice_transcription": "not_configured",
  "language_model": "configured",
  "hardware_adapter": "interface_ready_not_configured",
  "rag_retriever": "ready"
}
```

`language_model` 可以是 `not_configured`、`configuration_error`、`configured`；`rag_retriever` 可以是 `not_loaded`、`loaded_no_approved_chunks`、`ready`。上述是当前工作机状态，忽略文件或环境变量变化后会动态改变。`hardware_adapter` 仍使用保守兼容字符串：它不代表固件和桥代码不存在，只表示 API 不确认串口桥正在运行。前端不能把这些字符串改写为“已连接”。完整语义见 [RAG_HANDOFF.md](./RAG_HANDOFF.md) 和 [HARDWARE_IMPLEMENTATION_ALIGNMENT.md](./HARDWARE_IMPLEMENTATION_ALIGNMENT.md)。

## 12. 前端技术栈和页面

### 12.1 技术栈

- React 19
- TypeScript
- Vite
- 原生 CSS
- 原生 SVG
- 原生 `<dialog>`

没有引入图表库、全局状态库或路由库。

### 12.2 页面

| View ID | 中文名 | 当前内容 |
|---|---|---|
| `record` | 新手记录 | 默认入口；真实文字保存、已保存状态与“健康数据”导航；语音仍待 STT |
| `home` | 首页 | 一句话记录、接入状态、体重趋势、覆盖率、最近记录 |
| `ledger` | 身体账本 | 延迟加载完整记录，点击查看详情 |
| `discoveries` | 发现 | 三类场景的关键词证据 |
| `plan` | 方案 | 用户复盘和模型三句话输出契约 |

导航字符串集中在 `NAVIGATION`：

```text
记录
首页
身体账本
发现
方案
```

### 12.3 首页保存流程

1. 日期默认使用当前日期。
2. 文本为空时显示“请先写下今天想记录的内容。”，不发请求。
3. 保存中按钮显示“正在保存…”。
4. 成功后显示“原始记录已保存；结构化整理等待模型接入。”。
5. 保存成功后刷新 overview，并让账本列表下次进入时重新读取。
6. 失败时直接显示服务端错误。

语音按钮为禁用状态，展示：

```text
语音待接入
```

### 12.4 身体账本和详情

身体账本首次进入才请求最多 100 条记录。记录详情显示：

```text
体重
体脂率
睡眠
整理状态
身体信号（有才显示）
历史反馈（历史记录才显示）
原始记录
```

睡眠展示字符串：

```text
未记录
已记录文字描述
70 分 · 量表未确认
8 / 10
```

### 12.5 体重趋势图

代码位置：[MetricTrend.tsx](../frontend/src/components/MetricTrend.tsx)

- 只取最近 6 条记录中的有体重数据；
- X 轴按真实日期间隔计算；
- 日期间隔超过 1 天就断线；
- 不插值、不补点；
- 使用原生 SVG，避免图表库体积和额外运行时。

### 12.6 响应式和交互

- 桌面端：顶部导航；
- 小于 900px：导航转为底部固定导航；
- 小于 640px：卡片、列表、详情重新排版；
- 键盘 focus 有明显轮廓；
- `prefers-reduced-motion` 下减少动画；
- 不使用 3D、复杂拖拽或高频动画。

## 13. 大语言模型输出契约

完整版本见 [LLM_OUTPUT_POLICY.md](./LLM_OUTPUT_POLICY.md)。

### 13.1 固定 JSON

```json
{
  "empathy": "第一句。",
  "suggestion": "第二句。",
  "outlook": "第三句。"
}
```

三句分别是：

1. 鼓励共情；
2. 一项非医疗生活或记录建议；
3. 轻量正向展望。

每句要求：

- 只有一句话；
- 以中文句号结尾；
- 去除标点和空格后 10–20 个汉字；
- 不得有额外字段；
- 不得出现医疗禁词。

### 13.2 当前系统提示词

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
```

### 13.3 禁止词

基础禁词：

```text
治愈、治好、治疗、病灶、炎症、病变、康复、药效、确诊
```

工程增强禁词：

```text
用药、药物、处方、严重、轻微
```

命中任何词都拒绝整个输出，不做自动替换、自动改写或备用文案。

## 14. 性能策略

### 后端

- 历史文件通过 `lru_cache(maxsize=1)` 每个进程只读取一次；
- 历史投影也只计算一次；
- 场景统计只有固定关键词扫描；
- RAG 不做向量搜索、Embedding、重排、缓存或多轮模型调用；每次最多返回 3 条，模型只收到前 2 条。

### 前端

- 首屏只请求一次 overview；
- overview 只携带最近 6 条完整记录；
- 完整账本延迟到用户进入“身体账本”时加载；
- 使用原生 SVG，不引入大型图表依赖；
- 没有自动轮询和自动重试。

## 15. “不写兜底”具体意味着什么

业务层没有：

- Mock 数据；
- 虚拟日期；
- 假 AI 文案；
- `data || mockData`；
- `value ?? defaultHealthValue`；
- 多供应商自动切换；
- 自动重试和静默吞错。

仍然存在的正常状态保护：

- 未记录字段显示 `null` 或“未记录”；
- 新记录文件尚不存在时返回空集合；
- 图表单点时使用除零保护；
- DOM 引用不存在时不调用关闭方法；
- 非标准异常显示“请求失败”。

这些保护不会产生健康数据，也不会把错误伪装成成功。

## 16. 当前限制

1. 新自由文本目前只做确定性字段投影，尚未做模型语义整理。
2. 新记录状态是 `pending`，表示等待模型语义整理，不表示原文没有保存。
3. 大模型已有 OpenAI-compatible 调用适配器、提示词、校验器和本地配置；真实外部调用、持久化和离线评测仍未验收。
4. 语音按钮不可用，直到真实转写服务接入。
5. RAG 当前本地为 14/14 approved；MAX30102 固件、协议、API 与串口桥代码已完成，但真实 USB → API 联跑、血氧和前端展示仍未完成。
6. JSONL 不适合多用户并发写入，正式产品需要数据库、身份和权限。
7. 当前没有 URL 路由，刷新页面会回到新手记录入口。
8. UI 文案大多直接写在 React 组件中，还没有 i18n 或统一文案文件。
9. `Amy` 是场景故事中的内部演示名，不是已实现的 Profile 存储字段。
10. 场景页只做关键词计数，不做趋势、相关性或医学判断。
11. 最终运动 Enum 已实现；未提供的 Profile/Device 字段仍不猜测。

## 17. 需要共同确认的现有契约点

这些不是新增功能，而是把已有资料中不完全一致的地方定死。

### 17.1 三句话如何落库

当前运行时输出是：

```text
empathy
suggestion
outlook
```

字段表是：

```text
ai_daily_summary
ai_hypothesis_validation
```

建议方案：

- 三句话完整合并到 `ai_daily_summary`；
- 只有用户确实写了假设时，才写 `ai_hypothesis_validation`；
- 模型接入前，两个字段继续保持 `null`。

### 17.2 `pending` 是否改名

当前 `pending` 的实际含义是“等待模型语义整理”。如果要避免误解，可以改为：

```text
semantic_extraction_status
```

但这会改动前后端字段，需要统一确认后再改。

### 17.3 运动 Enum

最终契约已经进入 Pydantic、确定性投影、历史迁移、TypeScript 类型和详情展示。封闭枚举为 `aerobic / strength / core / stretching / yoga / walking / other`；没有运动记录时为空数组和 `null`，不生成默认活动。完整规则见 [EXERCISE_DATA_CONTRACT.md](./EXERCISE_DATA_CONTRACT.md)。

### 17.4 Profile / Device 字段

当前不创建猜测字段。拿到完整字段表后，先更新 Pydantic、API 和 TypeScript 类型，再让前端消费。

## 18. 验收方式

后端：

```bash
PYTHONPATH=backend python3 -m pytest backend/tests -q
```

前端：

```bash
cd frontend
npm run typecheck
npm run build
```

当前验收结果：

```text
后端：26 passed
前端：typecheck 通过
前端：生产构建通过
浏览器：桌面端和 390px 手机宽度无横向溢出
控制台：无 warning/error
```

## 19. 本地启动

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

```text
前端：http://127.0.0.1:5173
API：http://127.0.0.1:8000
API 文档：http://127.0.0.1:8000/docs
```

## 20. 相关文档

- [README.md](../README.md)：快速启动和当前能力。
- [ARCHITECTURE.md](./ARCHITECTURE.md)：按模块拆分的架构说明。
- [EXERCISE_DATA_CONTRACT.md](./EXERCISE_DATA_CONTRACT.md)：运动最终 Enum、明细、历史映射与空值规则。
- [FRONTEND_HANDOFF_REVIEW.md](./FRONTEND_HANDOFF_REVIEW.md)：新手页交付包的可复用部分、阻塞项与直接接入顺序。
- [FIELD_CONTRACT.md](./FIELD_CONTRACT.md)：字段逐项契约。
- [LLM_OUTPUT_POLICY.md](./LLM_OUTPUT_POLICY.md)：模型提示词和输出校验。
- [source-materials/README.data-package.md](../source-materials/README.data-package.md)：历史数据包说明。
