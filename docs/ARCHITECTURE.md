# 有迹可循：整体架构与代码逻辑

## 1. 当前产品边界

最新敲定范围以路演文件、黑客松功能方案和字段/大模型输出规范为准。当前主流程是：

```text
一句话文字记录
    ↓ POST /api/entries
原始文本 append-only 保存
    ↓ 明确字段的确定性投影
身体账本 LedgerEntry
    ↓ 轻量聚合
首页概览 / 三类场景 / 小步方案
```

语音转写和硬件仍只有接口边界。RAG 已完成文件校验、审核过滤、确定性检索和 API；大模型已完成 OpenAI-compatible 调用适配器，但尚未配置供应商。页面显示真实状态，不会用前端假数据代替。

## 2. 数据分层

### 2.1 历史真实源

`backend/data/records.json` 包含 40 个真实记录日，日期从 `2026-07-01` 到 `2026-08-20`，自然跨度 51 天，11 天没有记录。原始结构是：

```text
HealthRecord
├── date
├── day_number
├── user_input
└── feedback.hot / feedback.cold
```

`RecordRepository` 只负责读取、严格校验、排序检查和重复日期检查。缺文件、空文件、字段错误、日期乱序都会直接报错。

### 2.2 新用户原始记录

`POST /api/entries` 把记录写入 `backend/data/user_entries.jsonl`：

```text
StoredUserEntry
├── id
├── record_date
├── created_at
├── original_text
├── input_method
└── extraction_status = pending
```

存储是 append-only。修改历史和删除接口尚未开放，避免新流程还未确认时覆盖原始证据。

### 2.3 结构化身体账本

`journal_projection.py` 把历史源和新记录统一映射为 `LedgerEntry`。映射只识别已确认格式：体重、体脂、血压/心率、餐次、部分结构化运动字段、睡眠、身体信号、用户复盘和上下文字段。没有匹配到的字段保持 `null` 或空数组。

这不是语义理解模型。自由文本中没有明确字段名时，解析器不会猜。

### 2.4 AI 内容

`AIContent` 中的 `ai_daily_summary` 和 `ai_hypothesis_validation` 已建模，但当前始终为 `null`。只有未来真实模型输出通过 `CompanionOutput` 校验后，才允许进入后续持久化流程。

历史 `feedback.hot/cold` 作为历史导入材料保留在 `legacy_feedback`，不会冒充新版三句话反馈。

## 3. 睡眠规则

睡眠使用独立 `SleepObservation`：

- `recorded`：原文是否确实包含睡眠记录；
- `raw_text`：睡眠相关原文；
- `raw_value`：原始分值；
- `raw_scale`：确认后的 10 分或 100 分量表；
- `normalized_1_10`：仅确认是 1–10 时写入；
- `comparable`：是否可以进入同量表比较；
- `extraction_notes`：为什么没有归一化。

例如“睡眠：70分”是有效睡眠记录：`recorded=true`、`raw_value=70`，但量表没有确认，因此 `raw_scale=null`、`normalized_1_10=null`、`comparable=false`。系统不擅自除以 10，也不丢弃这条记录。

## 4. 三类场景逻辑

`scene_summary.py` 当前只做关键词出现计数：

| 场景 | 关键词 |
|---|---|
| 关节不适 | 关节、膝盖酸痛、手腕僵硬、肩周、僵硬酸痛 |
| 经期变化 | 经期、生理期、月经、经量、出血 |
| 情绪波动 | 情绪、烦躁、焦虑、低落、压力、想哭 |

输出只有相关记录数、最近日期、证据说明和固定边界：

> 这里只统计关键词出现次数，不判断症状、原因或严重程度。

该逻辑复杂度是记录数乘少量关键词。没有分词模型、向量检索或多轮计算，不会阻塞首屏。

## 5. 后端模块

| 文件 | 职责 |
|---|---|
| `models/health.py` | 所有存储/API 的严格类型，未知字段禁止进入 |
| `repositories/records.py` | 历史真实数据只读加载，进程内缓存一次 |
| `repositories/entries.py` | 新原始记录 JSONL 追加与读取 |
| `models/hardware.py` | MAX30102 原始读数的严格契约和质量状态 |
| `repositories/hardware.py` | MAX30102 原始读数 JSONL 追加与读取，不混入用户账本 |
| `services/journal_projection.py` | 明确格式的确定性投影；历史投影缓存一次 |
| `services/scene_summary.py` | 三场景关键词证据计数 |
| `repositories/knowledge.py` | 严格读取 product 交付的 knowledge_chunks.jsonl |
| `services/knowledge_retrieval.py` | 只检索审核通过条目的确定性排序 |
| `services/llm_settings.py` | 从 backend/.env 加载三项模型配置并报告状态 |
| `services/overview.py` | 日期跨度、缺失天数、字段覆盖率、最近六条记录和真实接入状态 |
| `services/companion_policy.py` | 三句话输出、长度、句数和医疗禁词校验 |
| `integrations/openai_compatible_llm.py` | 检索完成后调用 /chat/completions，并校验返回 JSON |
| `integrations/llm.py` | 模型适配器协议 |
| `integrations/hardware.py` | 通用硬件读数标准化协议预留 |
| `integrations/serial_protocol.py` | MAX30102 NDJSON 串口行的纯解析器，未猜测调试文本 |
| `integrations/serial_bridge.py` | 只允许 `signal_quality=valid` 进入转发链路 |
| `scripts/forward_max30102_serial.py` | 指定 USB 串口到本地 FastAPI 的手动桥接进程 |
| `integrations/rag.py` | 有来源知识检索协议 |
| `api/routes.py` | HTTP 路由，不放业务计算 |

## 6. 前端结构

前端使用 React 19 + TypeScript + Vite，不依赖图表库、状态管理库或路由库。

| 视图 | 当前内容 |
|---|---|
| 首页 | 一句话保存、真实接入状态、近期体重、字段覆盖率、最近记录 |
| 身体账本 | 首次进入时才加载最多 100 条记录，支持详情弹窗 |
| 发现 | 三类场景的关键词证据和医学边界 |
| 方案 | 最近一次用户复盘与大模型三句话契约 |

关键文件：

- `App.tsx`：四视图、请求状态和保存后刷新；
- `api.ts`：只请求真实 `/api`，非 2xx 直接抛错；
- `MetricTrend.tsx`：原生 SVG，只画真实体重点，跨缺失日期时断线；
- `LedgerDialog.tsx`：原生 `dialog` 展示分层字段与原始文本；
- `styles.css`：移动端优先、响应式、键盘焦点和 reduced-motion。

## 7. 性能策略

- 历史 JSON 和历史投影通过 `lru_cache(maxsize=1)` 每进程只计算一次；
- 首屏只返回最近 6 条完整记录，不下载全部账本；
- 全量账本只在用户第一次打开“身体账本”时请求；
- 图表使用原生 SVG，避免引入大体积依赖；
- 场景统计只做固定关键词扫描；
- RAG 每次最多遍历当前审核通过的本地条目，最多返回 3 条，模型只接收前 2 条；
- 模型请求固定 `max_tokens: 160`、20 秒超时且不重试；
- 不引入向量数据库、Embedding、重排模型、缓存或第二次模型调用；
- 没有自动重试、轮询、客户端 Mock、兼容分支或模型级联。

## 8. 失败策略

本项目刻意不隐藏问题：

- 历史真实数据缺失或格式错误：后端启动/请求直接失败；
- 新 JSONL 出现空行或坏记录：直接报错并指出行号；
- API 非成功响应：前端显示服务端错误；
- 账本 ID 不存在：返回 404；
- 知识包缺失：预览与模型接口返回 409；
- 知识条目有空行、字段错误或重复 ID：返回 422 和明确错误；
- 没有审核通过的匹配条目：模型接口返回 422，不调用模型；
- 模型配置不完整：返回 503；上游或输出不合规：返回 502；
- 模型输出超长、多句或含禁词：Pydantic 校验拒绝；
- 集成未接入：返回明确状态，不生成替代内容。

## 9. API 数据流

| Method | Path | 数据流 |
|---|---|---|
| GET | `/api/overview` | 历史缓存 + 新记录 → 统一账本 → 轻量聚合 |
| GET | `/api/ledger` | 统一账本 → 倒序 + limit |
| GET | `/api/ledger/{id}` | 统一账本 → 精确 ID；不存在返回 404 |
| POST | `/api/entries` | 严格校验 → JSONL 追加 → 返回待整理账本项 |
| GET | `/api/integrations` | 当前真实接入状态 |
| GET | `/api/knowledge/status` | chunks 文件状态与审核通过数量 |
| POST | `/api/knowledge/preview` | 确定性检索预览，不调用模型 |
| POST | `/api/companion` | 前 2 条审核知识 → 模型 → 三句安全输出校验 |

## 10. 现有限制与下一接入点

1. 新记录还没有语义字段提取，`extraction_status` 保持 `pending`；确定性字段投影只是可检查的基础层。
2. 大模型适配器、密钥位置和输出校验已完成，但没有供应商配置、真实调用验证、持久化和离线评测。
3. 语音按钮不可用，直到转写服务真实接入。
4. RAG 框架已经完成，但没有审核通过的真实 chunks；硬件只有 Protocol，没有实现。
5. Profile / Device 字段以及字段截图中被截断的完整枚举未提供，因此没有猜测实现。
6. 本地 JSONL 适合内部 MVP，不具备多用户并发写入和权限隔离能力。
7. 真实数据仍在 `.gitignore` 内；公开 demo 必须使用独立合成数据集并明确标记来源。

下一步是产品侧交付审核后的 chunks，再使用 `/api/knowledge/preview` 核查命中；随后填入模型配置并验证 `/api/companion`。详见 [RAG_HANDOFF.md](./RAG_HANDOFF.md)。
