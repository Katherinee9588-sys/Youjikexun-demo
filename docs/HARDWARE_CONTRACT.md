# 硬件数据边界与第一版串口契约

## 三个彼此独立的区域

| 区域 | 本地文件 / 入口 | 内容 | 禁止事项 |
|---|---|---|---|
| 用户原始表达 | `backend/data/user_entries.jsonl` / `POST /api/entries` | 手动文字或真实转写文本；`input_method` 是 `text` 或 `voice` | 不把结构化猜测覆盖原文 |
| MAX30102 原始读数 | `backend/data/hardware_max30102.jsonl` / `POST /api/hardware/max30102/readings` | 每个传感器测量窗口、IR、心率、血氧、手指状态、质量状态 | 不把高频原始读数伪造成用户日记或知识库 |
| 审核过的知识 | `backend/data/knowledge_chunks.jsonl` | 围绝经期知识文本及来源 | 不放用户语音、用户文字或传感器读数 |

`hardware_max30102.jsonl` 是本地私密文件，已被 Git 忽略。当前项目仍是本地 JSONL MVP，不是多用户生产数据库。

## MAX30102 串口 NDJSON

ESP32 每次只输出一行 JSON。调试文本可以保留，但必须加 `#` 前缀。PC 串口桥会跳过调试行、解析 JSON，并且只转发 `signal_quality=valid` 的样本。

```json
{"schema_version":1,"device_id":"max30102-01","sequence":42,"device_uptime_ms":34600,"ir_value":89321,"finger_present":true,"heart_rate_bpm":72.5,"spo2_percent":null,"signal_quality":"valid"}
```

- `received_at` 由 PC 后端写入，因为 ESP32 在未配置 NTP 时不可靠地知道真实日期时间；
- 当前附件仅计算心率，必须发送 `"spo2_percent": null`，不能伪造血氧；
- `finger_present=false` 时，心率和血氧都必须为 `null`；
- `signal_quality=valid` 至少要有一个实际测得的生命体征；
- 未来升级为真实血氧算法后，只修改 `spo2_percent` 的来源，不改变 JSON 契约。

## 本地串口桥

桥接脚本在 `backend/scripts/forward_max30102_serial.py`。它不自动运行；需先启动 FastAPI，再在另一终端运行：

```bash
PYTHONPATH=backend python3 backend/scripts/forward_max30102_serial.py \
  --port /dev/cu.usbmodem5CBC0647211
```

运行前需要安装 `backend/requirements.txt` 中的 `pyserial`。串口桥不保存 LM393 的 `#` 调试行，不保存 MAX30102 的 `warming_up`、`unstable` 或 `finger_absent` 行；只有已通过 ESP32 信号质量门槛的心率样本会调用 `POST /api/hardware/max30102/readings` 并写入本地、Git 忽略的 `hardware_max30102.jsonl`。后端 POST 接口也会拒绝非 `valid` 状态，避免绕过串口桥写入无效数据。

## INMP441 语音边界

INMP441 不直接写入用户账本。ESP32 在用户短按运行中的 `BOOT` 后，采集固定 3 秒的 16 kHz、单声道、16-bit PCM；电脑串口桥在内存中封装 WAV，调用一次 STT。只有 STT 返回真实、非空文字时，才调用已有的：

```text
POST /api/entries
input_method = voice
original_text = 转写结果
```

原始音频默认不进入用户账本、也不写入知识库。是否保存音频需要另行明确同意与保留期限。

固件在 921600 波特率输出以下帧；音频字节不是 UTF-8，不能用 PlatformIO Monitor 解析：

```text
@voice_begin id=1 sample_rate_hz=16000 sample_width_bits=16 channels=1 pcm_bytes=96000
<96000 bytes raw signed little-endian PCM>
@voice_end id=1
```

新的唯一串口消费者是 `backend/scripts/forward_esp32_serial.py`。它同时：

- 忽略所有 `#` 调试行；
- 沿用既有规则，只转发 `signal_quality=valid` 的 MAX30102 JSON；
- 严格读取一帧 PCM、封装为 WAV、调用一次 STT；
- STT 失败、协议不匹配或后端拒绝时只打印实际错误，不创建用户记录、不重试；
- 不把音频保存到磁盘、JSONL 或知识库。

完整状态机、环境变量和实机命令见 [`VOICE_STT_IMPLEMENTATION.md`](./VOICE_STT_IMPLEMENTATION.md)。

## 尚未实现

- MAX30102 真正的 SpO2 算法：当前附件没有该算法；
- INMP441 的实机 STT 联调：需要用户在本地 `.env` 配置真实智谱 ASR 密钥后按文档运行电脑桥；
- 把有效硬件快照显示到前端或投影进身体账本。
