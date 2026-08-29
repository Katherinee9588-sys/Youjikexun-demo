# 字段与存储契约

本文件把附件《一、存储字段表》中可确认的字段，与当前代码的实际实现逐项对齐。截图中没有完整显示的内容不会被猜测。

## 1. 晨起客观体征

| 附件字段 | 类型 | 当前实现 | 说明 |
|---|---|---|---|
| `record_date` | Date | `MorningVitals.record_date` | 必填 |
| `body_weight` | Float kg | `float / null` | 未记录为 `null` |
| `body_fat_rate` | Float % | `float / null` | 0–100 |
| `systolic_pressure` | Int mmHg | `BloodPressureReading.systolic_pressure` | 同日可多组 |
| `diastolic_pressure` | Int mmHg | `BloodPressureReading.diastolic_pressure` | 同日可多组 |
| `heart_rate` | Int bpm | `BloodPressureReading.heart_rate` | 每组读数独立，可为空 |
| `measurement_context` | String 多选 | `list[str]` | 不把多个情境压成单字符串 |

血压/心率采用读数组，而不是一天一个平均数，以免丢失同日不同测量条件。

## 2. 生活方式干预

| 附件字段 | 类型 | 当前实现 | 说明 |
|---|---|---|---|
| `meal_time_slot` | Enum | breakfast/lunch/dinner/snack | 早/午/晚/加餐 |
| `meal_raw_text` | Text 200 | `str`，最多 200 字 | 保留食物原始描述 |
| `meal_tag` | Array[String] | `list[str]` | 当前为空；不自动猜标签 |
| `exercise_type` | Enum 多选 | `ExerciseType[]` | `aerobic/strength/core/stretching/yoga/walking/other`，无记录为 `[]` |
| `exercise_duration` | min | `int / null` | 只汇总明确分钟数，1–1440；不从组数或模糊时长换算 |
| `exercise_sets` | sets | `int / null` | 只有单项运动的明确组数进入顶层，多项运动保持 `null` |
| `exercise_details` | Array | `ExerciseDetail[]` | 分项保留类型、原始名称、分钟和组数 |
| `exercise_raw_text` | Text | `str / null` | 保留运动原始表达，不被结构化结果覆盖 |
| `sleep_bed_time` | Time | `SleepObservation.bed_time` | 未记录为 `null` |
| `sleep_wake_time` | Time | `SleepObservation.wake_time` | 未记录为 `null` |
| `sleep_interruptions` | Int | `SleepObservation.interruptions` | 未记录为 `null` |

运动完整契约与迁移规则见 [EXERCISE_DATA_CONTRACT.md](./EXERCISE_DATA_CONTRACT.md)。附件截图只显示到 `sleep_interruptions`，其后的行不可确认。现有历史数据还包含睡眠主观分值，因此增加了可审计字段：

| 扩展字段 | 作用 |
|---|---|
| `sleep.recorded` | 是否真的记录了睡眠 |
| `sleep.raw_text` | 睡眠原文 |
| `sleep.raw_value` | 原始分值，例如 70 |
| `sleep.raw_scale` | 仅在量表确定时为 10 或 100 |
| `sleep.normalized_1_10` | 仅确认 1–10 时写入 |
| `sleep.comparable` | 是否可进入同量表比较 |
| `sleep.extraction_notes` | 量表未知等边界说明 |

## 3. 主观身体信号

| 附件字段 | 当前实现 |
|---|---|
| `symptom_location` | `str / null` |
| `symptom_desc` | 非空原始描述 |
| `symptom_trend` | better/same/worse/unclear/null |
| `symptom_triggers` | `str / null` |

目前仅当原始记录有 `body_signals` 或“身体信号”字段时建立一条 `PhysicalSignal`。自由文本不会被自动诊断成症状。

## 4. 用户心理模型与迭代

| 附件字段 | 当前实现 | 长度 |
|---|---|---:|
| `today_highlight` | 今天做对的一件事 | 100 |
| `tomorrow_one_change` | 明天只改一件事 | 100 |
| `execution_resistance` | 今天最大的执行阻力 | 100 |
| `user_hypothesis` | 用户自己的假设 | 100 |

这些字段只保存用户表达，不把用户猜测升级成系统结论。

## 5. AI 生成内容

| 附件字段 | 当前实现 | 状态 |
|---|---|---|
| `ai_daily_summary` | `AIContent.ai_daily_summary`，最多 150 字 | `null` |
| `ai_hypothesis_validation` | `AIContent.ai_hypothesis_validation`，最多 50 字 | `null` |

模型尚未接入，因此不生成字符串兜底。新版三句话回复使用独立 `CompanionOutput` 契约，接入后必须先校验再决定如何持久化。

## 6. 上下文

| 附件字段 | 当前实现 |
|---|---|
| `weather_temp` | `int / null`，摄氏度 |
| `special_stress` | `str / null` |

## 7. 系统审计字段

这些字段来自工程需要，用于区分来源和状态：

| 字段 | 作用 |
|---|---|
| `id` | 唯一账本项 ID |
| `source` | `legacy_import` 或 `user_entry` |
| `created_at` | 新记录创建时间；历史导入为空 |
| `original_text` | 永不被结构化字段覆盖的原始表达 |
| `input_method` | import/text/voice/accessibility |
| `extraction_status` | completed/partial/pending |
| `legacy_feedback` | 历史 hot/cold；新记录为空 |

## 8. 暂不实现的字段

附件提到 Profile 与 Device 只做去标识化和设备校准，但没有提供具体字段名、类型或枚举。当前版本不创建猜测字段。等完整表格确认后，应先更新本契约和 Pydantic 模型，再让前端消费。

首页的“Amy”来自当前场景故事，只是 `AppOverview.profile_display_name` 中的内部演示文案，不是已实现的用户 Profile 存储字段。
