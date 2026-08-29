# 硬件接入整体逻辑与实现对齐

> 对齐范围：ESP32-S3、MAX30102、LM393，以及未来 INMP441。
> 当前性质：单用户、本机 USB 串口、本地 JSONL MVP；不是医疗设备或生产数据库。

## 1. 当前结论

| 模块 | 当前状态 | 是否进入后端 |
|---|---|---|
| ESP32-S3 | 当前源码已编译；同参数前序版本已完成实板烧录 | 作为串口数据源 |
| MAX30102 心率 | 静止单点工程验收通过 | 仅 `valid` 数据进入 |
| MAX30102 血氧 | 独立算法冒烟测试固件已编译，尚未烧录/实测 | 统一固件仍为 `null`，不进入后端 |
| LM393 | 声音活动调试可用 | 不进入后端 |
| INMP441 | 尚未到货/接线/验收 | 没有 I2S、音频或 STT 数据 |
| 电脑串口桥 | 代码与过滤测试已完成，尚未做真实串口到 API 联跑 | 手动启动后才转发 |
| 前端硬件展示 | 未实现 | 当前不会轮询硬件接口 |

最终心率人工对照：60 秒手动计数 63 次，即参考值 63 BPM。固件在同一轮产生 53 个 `valid` 样本，范围 56–69 BPM，均值 65.0 BPM；没有再次出现 100+ 的双倍误判。

当前系统 Python 尚未安装 `pyserial`。代码已把它固定在 `backend/requirements.txt`；真实桥接前必须先按第 11 节安装依赖、关闭 PlatformIO Serial Monitor，再进行串口到 API 的实机联跑。这里不把“代码测试通过”写成“真实桥接已经运行”。

## 2. 文件职责

```text
hardware/esp32-s3-sensors/
├── platformio.ini              ESP32-S3、Arduino、MAX3010x 依赖
├── src/main.cpp                MAX30102 + LM393 统一固件
└── README.md                   接线、烧录、现场验收

backend/app/models/hardware.py  串口/HTTP 硬件数据严格模型
backend/app/integrations/
├── serial_protocol.py          UTF-8 NDJSON 解析
└── serial_bridge.py            valid-only 判定
backend/scripts/
└── forward_max30102_serial.py  USB 串口 → FastAPI
backend/app/repositories/
└── hardware.py                 append-only JSONL 存储
backend/app/api/routes.py       写入和读取最新有效值 API
backend/tests/test_hardware.py  模型、解析、过滤、存储测试

hardware/esp32-s3-max30102-spo2-test/
├── platformio.ini              独立 SpO2 算法测试依赖
├── src/main.cpp                Red + IR 100 组滑动窗口
└── README.md                   烧录、实测和对照验收步骤
```

`Downloads/code-project-1` 和 `Downloads/code-project-2` 是原始独立测试工程。主仓库不修改、覆盖或依赖这两个下载目录。

## 3. 实际接线

| 模块端 | ESP32-S3 |
|---|---|
| LM393 `+` | 3V3 |
| LM393 `G` | GND |
| LM393 AO | GPIO4 / ADC1_CH3 |
| LM393 DO | GPIO5 |
| MAX30102 VIN | 3V3 |
| MAX30102 GND | GND |
| MAX30102 SDA | GPIO8 |
| MAX30102 SCL | GPIO9 |
| MAX30102 INT | GPIO6，当前未使用 |

LM393 不切回 5V 后再把 AO/DO 直接接入 ESP32。未来 INMP441 的接线和代码必须等实物到货后单独验收。

## 4. 运行链路

```text
MAX30102 光学样本
→ ESP32 每 20ms 送入心跳检测
→ 八次心跳窗口质量判断
→ 每秒输出一行 MAX30102 JSON
→ pyserial 读取指定 USB 串口
→ Pydantic 严格校验
→ 只保留 signal_quality = valid
→ POST /api/hardware/max30102/readings
→ hardware_max30102.jsonl 追加一行
```

LM393 走旁路：

```text
GPIO4 / GPIO5
→ 声音活动阈值
→ # lm393 ... 调试行
→ 串口桥直接忽略
```

## 5. MAX30102 状态机

```text
finger_absent
      │ 手指 IR >= 50000
      ▼
 warming_up
      │ 八次窗口 + 二次相近确认
      ├──────────────→ valid
      │ 质量不满足
      └──────────────→ unstable

任何状态 ── 手指移开 ──→ finger_absent + 清空全部心率窗口
```

固定字符串只有：

```text
warming_up
finger_absent
unstable
valid
```

状态规则：

- `finger_absent`：`heart_rate_bpm=null`、`spo2_percent=null`；
- `warming_up`：正在收集和确认新窗口，心率为 `null`；
- `unstable`：存在过期、窗口离散或接触内突跳，心率为 `null`；
- `valid`：通过全部信号质量门槛，至少有实际心率；
- 手指重新放置必须重新预热，不复用上一次 BPM。

## 6. 固件固定参数

| 参数 | 当前值 | 作用 |
|---|---:|---|
| `FINGER_IR_THRESHOLD` | 50000 | 判断是否有手指 |
| `HEART_SAMPLE_INTERVAL_MS` | 20ms | 50Hz 心跳输入节奏 |
| `MAX_OUTPUT_INTERVAL_MS` | 1000ms | MAX JSON 输出频率 |
| `STALE_BEAT_INTERVAL_MS` | 5000ms | 超时后拒绝旧心跳 |
| `RATE_SIZE` | 8 | 心跳窗口长度 |
| `MAX_STABLE_RATE_SPREAD_BPM` | 18 | 窗口最大离散范围 |
| `INITIAL_CONFIRMATIONS_REQUIRED` | 2 | 首次稳定值确认次数 |
| `MAX_TRUSTED_BPM_DELTA` | 8 | 同次接触允许的窗口变化 |
| MAX 红光幅度 | `0x0A` | 复用已验收测试参数 |
| MAX 绿光幅度 | `0` | 当前关闭 |

这些是本次硬件实测得到的工程质量门槛，不是医学阈值。若门槛不满足，系统选择不输出心率。

## 7. LM393 参数与限制

| 参数 | 当前值 |
|---|---:|
| 模拟采样数 | 400 |
| 单次采样间隔 | 50µs |
| 声音窗口间隔 | 200ms |
| 调试输出间隔 | 1000ms |
| 峰峰值阈值 | 12 |
| 中心偏移阈值 | 8.0 |
| DO 有效电平 | LOW |

LM393 的移动、碰撞、吹气都会造成明显变化。它只能表示“检测到声学/机械活动”，不能提供可供 STT 使用的语音波形。蓝色电位器只调整 DO 比较阈值，不是降噪或音质调节器。

## 8. 串口 JSON 契约

一条有效示例：

```json
{"schema_version":1,"device_id":"max30102-01","sequence":42,"device_uptime_ms":34600,"ir_value":142300,"finger_present":true,"heart_rate_bpm":65,"spo2_percent":null,"signal_quality":"valid"}
```

字段：

| 字段 | 类型/限制 | 来源 |
|---|---|---|
| `schema_version` | 固定 `1` | 固件 |
| `device_id` | 1–80 字符 | 固件常量 |
| `sequence` | 非负整数 | 固件递增 |
| `device_uptime_ms` | 非负整数 | ESP32 `millis()` |
| `ir_value` | 非负整数 | MAX30102 IR |
| `finger_present` | 布尔值 | IR 阈值 |
| `heart_rate_bpm` | 20–255 或 `null` | 质量门槛后的心率 |
| `spo2_percent` | 70–100 或 `null` | 当前固定 `null` |
| `signal_quality` | 四个固定状态之一 | 固件状态机 |

ESP32 没有可信真实日期。`received_at` 和记录 `id` 由电脑后端在写入时生成。

任何额外字段、坏 UTF-8、空串、坏 JSON、非法状态、无手指却携带生命体征，都会校验失败。

## 9. 电脑串口桥

桥接脚本：`backend/scripts/forward_max30102_serial.py`。

明确行为：

1. 用户必须显式传入 `--port`；
2. 默认波特率 115200；
3. `#` 开头的 LM393/设备调试行被忽略；
4. 合法 JSON 进入严格模型；
5. 只有 `signal_quality=valid` 执行 HTTP POST；
6. `warming_up`、`unstable`、`finger_absent` 不转发；
7. 端口、JSON、模型或 HTTP 失败直接终止并显示错误；
8. 没有自动重试、备用端口、备用接口、默认数据或伪成功输出。

脚本每秒最多处理固件的一条 MAX JSON，并同步执行一次本地 HTTP 请求。没有后台任务队列、模型调用、聚合计算或前端刷新，因此当前本机 MVP 不会把复杂计算带到前端。

## 10. 后端接口与存储

```text
POST /api/hardware/max30102/readings
GET  /api/hardware/max30102/latest
```

- POST 严格校验，只接受 `valid`，并追加到 `backend/data/hardware_max30102.jsonl`；
- GET 返回最近一条已存储的 `valid` 样本；不存在时返回 404；
- 硬件 JSONL 已在 `.gitignore`；
- 硬件数据不会进入 `user_entries.jsonl`、身体账本或知识库；
- 当前前端没有请求这些接口，因此本轮不会增加页面请求或渲染计算。

## 11. 本地运行

先关闭 PlatformIO Serial Monitor，因为一个串口不能同时被 Monitor 和桥占用。

首次安装后端依赖：

```bash
cd /Users/catherine/Documents/Codex/Youjikexun/backend
python3 -m pip install -r requirements.txt
```

终端一启动 FastAPI：

```bash
cd /Users/catherine/Documents/Codex/Youjikexun/backend
PYTHONPATH=. python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

终端二启动串口桥：

```bash
cd /Users/catherine/Documents/Codex/Youjikexun
PYTHONPATH=backend python3 backend/scripts/forward_max30102_serial.py \
  --port /dev/cu.usbmodem5CBC0647211
```

停止桥使用 `Ctrl+C`。脚本不会随系统或后端自动启动。

## 12. 数据与隐私分区

| 数据 | 文件 | 是否提交 |
|---|---|---|
| 用户手动文字/未来真实 STT | `user_entries.jsonl` | 否 |
| MAX30102 有效样本 | `hardware_max30102.jsonl` | 否 |
| 审核知识 | `knowledge_chunks.jsonl` | 否 |
| 私有工程日志 | `.development-logs/` | 否 |
| 本地模型密钥 | `backend/.env` | 否 |

串口桥不会把硬件读数转成用户语言，不会自动生成日记，不会把生命体征写进 RAG 知识库。

## 13. SpO2 独立测试边界

`hardware/esp32-s3-max30102-spo2-test/` 已按 SparkFun Example8 参数建立并通过 PlatformIO release build。它同时读取 Red 和 IR，以 25 组/秒收集 100 组窗口，再调用 Maxim/SparkFun 算法。所有输出都使用 `# spo2_test` 前缀，因此现有串口桥会忽略。

截至当前，没有烧录记录、实机串口样本或指夹式血氧仪对照结果。该工程没有合入已验收的统一心率固件，后端 `spo2_percent` 仍必须为 `null`；只有完成连续 `spo2_valid=1` 和三轮外部设备对照后，才能评估是否合入。

## 14. 当前未实现

- MAX30102 SpO2 实机验收、统一固件合并与后端入库；
- 心律不齐判断、诊断或医疗告警；
- INMP441 I2S 音频采集；
- 降噪、VAD、STT 和原始音频保存策略；
- 硬件数据投影到身体账本；
- 前端实时硬件卡片；
- 多用户账号、鉴权、云数据库、并发写入与部署。

未来 INMP441 只有在真实 STT 返回文本后，才复用：

```text
POST /api/entries
input_method = voice
original_text = 真实转写文本
```

没有真实转写时，不创建用户文字记录。

## 15. 验证标准

固件：

- PlatformIO `pio run` 必须成功；
- 无手指时生命体征为 `null`；
- 手指放置后先预热；
- 不稳定时拒绝数字；
- 移开手指立即清空；
- SpO2 始终不伪造。

后端：

- 严格模型拒绝非法组合；
- 串口解析器拒绝人类调试文字和坏 JSON；
- 桥只转发 `valid`；
- POST 接口拒绝所有非 `valid` 状态；
- 有效样本写入硬件独立 JSONL；
- 最新有效值接口返回已持久化记录；
- 全量后端测试必须通过。

本文件描述的是当前已实现代码；计划项均明确留在“当前未实现”，不写成已完成。
