# INMP441 → STT → 当日记忆：实现对齐

> 状态：固件、协议、电脑桥和单元测试已实现；真实智谱 API 调用必须由本机的 `ASR_API_KEY` 配置和实机操作验收。

## 1. 这版只解决什么

把用户一次**主动触发**的短语音变成一条真实文字记录：

```text
短按 BOOT
→ ESP32 录 3 秒 INMP441 音频
→ Type-C USB 串口
→ Mac 电脑桥
→ 智谱 GLM-ASR-2512
→ POST /api/entries
→ user_entries.jsonl
→ 前端现有账本读取到 input_method=voice 的原文
```

MAX30102 仍由同一个电脑桥读取，但仍只保存 `signal_quality=valid` 的生命体征。LM393 只保留为调试模块，不参与本版的录音触发或转写。

## 2. 明确不做的事

- 不自动开始录音；唯一入口是用户短按 `BOOT`。
- 不使用 LM393 的 `DO`、不根据 RMS 猜测“用户在说话”。
- 不在 ESP32 做降噪、端点检测、文字猜测或语音模型推理。
- 不保存原始音频；PCM 与 WAV 仅在 ESP32/电脑内存中存在一次。
- 不在前端上传音频、轮询转写状态或等待模型，避免浏览器变慢。
- 不创建第二种用户账本格式；转写成功后固定复用 `/api/entries`。
- 不自动重试。协议、ASR 或保存失败会打印实际错误，且不写入任何用户条目。

## 3. 固件状态和固定字符串

| 状态 | 触发条件 | 串口输出 | 下一步 |
|---|---|---|---|
| `idle` | 正常运行 | 现有 `# inmp441`、MAX30102 JSON | 短按 BOOT |
| `capturing` | BOOT 按下沿 | `# voice state=capturing id=<n> duration_ms=3000` | 累积 48,000 个采样 |
| `transmitting` | 采样完整 | `@voice_begin ...` + 96,000 PCM 字节 + `@voice_end id=<n>` | 返回 `idle` |
| `sent` | 串口字节已写完 | `# voice state=sent id=<n>` | 等待下次 BOOT |

固定音频契约：

| 字段 | 值 | 原因 |
|---|---:|---|
| 时长 | 3 秒 | 先验证短语音，不占用大量 ESP32 内存 |
| 采样率 | 16,000 Hz | 当前 INMP441 已验证配置，适合语音转写 |
| 声道 | 1（左） | INMP441 `L/R → GND` |
| 位宽 | 16 bit PCM | 由 I2S 原始 32-bit 采样转换，便于标准 WAV/STT |
| PCM 长度 | 96,000 bytes | `16000 × 3 × 1 × 2`，桥严格校验 |
| USB 波特率 | 921600 | 传输 96 KB PCM 所需；115200 不够快 |

`BOOT` 只在固件已正常启动后短按一次才用于录音。上传卡在 `Connecting...` 时，它仍可能用于烧录模式；`RST` 始终只用于重启。

## 4. 电脑桥的职责

文件：`backend/scripts/forward_esp32_serial.py`

1. 独占 `/dev/cu.usbmodem...`，因此运行时必须关闭 PlatformIO Monitor。
2. 读到 `#` 开头的调试行，只打印，不解析。
3. 读到 MAX30102 JSON，沿用 `valid-only` 规则写入 `hardware_max30102.jsonl`。
4. 读到 `@voice_begin`，严格检查字段和 96,000 字节长度。
5. 将 PCM 临时封装为 WAV，不落盘。
6. 向智谱 `/audio/transcriptions` 请求一次 `glm-asr-2512` 转写。
7. 仅当响应中的 `text` 是非空字符串时，发送：

```json
{
  "record_date": "电脑本地当天日期",
  "original_text": "智谱返回的原始转写文字",
  "input_method": "voice"
}
```

8. FastAPI 继续负责生成 `id`、`created_at` 和 JSONL 追加；前端无需知道音频存在过。

## 5. STT 服务配置

在本机、Git 忽略的 `backend/.env` 中新增以下三项。不要把真实密钥发送到聊天框，也不要写进 `.env.example`：

```dotenv
ASR_API_KEY=你的智谱开放平台真实密钥
ASR_BASE_URL=https://open.bigmodel.cn/api/paas/v4
ASR_MODEL=glm-asr-2512
```

这里使用的是智谱官方语音转写接口：`POST /audio/transcriptions`。它接受 WAV，单次限制 30 秒/25 MB；本版 3 秒 WAV 远低于限制。[官方文档](https://docs.bigmodel.cn/api-reference/%E6%A8%A1%E5%9E%8B-api/%E8%AF%AD%E9%9F%B3%E8%BD%AC%E6%96%87%E6%9C%AC)

已有的 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL` 不被复用；聊天模型配置与语音转写配置是两件事。若 ASR 变量缺失，桥在启动时直接报 `missing required ASR settings: ...` 并停止，不伪装为已转写。

## 6. 实机操作顺序

### 一次性准备

1. 在 `backend/.env` 写入上面三个 ASR 变量。
2. 把 ESP32 工程重新 Upload 一次；固件串口已改为 `921600`。
3. 不要打开 PlatformIO Monitor。

### 每次语音记录

终端 A，在仓库根目录运行后端：

```bash
PYTHONPATH=backend python3 -m uvicorn app.main:app --reload
```

终端 B，在仓库根目录运行唯一的电脑桥：

```bash
PYTHONPATH=backend python3 backend/scripts/forward_esp32_serial.py \
  --port /dev/cu.usbmodem1101
```

端口名以 Upload 输出实际显示的 `/dev/cu.usbmodem...` 为准。

然后让 ESP32 正常运行，短按一次 `BOOT`，距离 INMP441 约 20–30 cm 正常说一句完整的话。3 秒后，终端 B 应出现：

```text
Stored voice capture id=1 entry_id=<uuid> text=<真实转写文字>
```

刷新前端的账本/记录页或调用 `GET /api/ledger?limit=1`，最新条目应显示 `input_method: "voice"`。

## 7. 验收与失败语义

| 结果 | 含义 | 是否写入用户记录 |
|---|---|---|
| `Stored voice capture ...` | 采集、传输、ASR 和保存均成功 | 是 |
| `Voice capture rejected: voice frame ...` | 固件/串口帧不符合固定协议 | 否 |
| `Voice capture rejected: speech-to-text ...` | 智谱请求或响应失败 | 否 |
| `Voice capture rejected: backend endpoint ...` | 转写成功但本地后端未保存 | 否 |
| `missing required ASR settings: ...` | 本机未配置 ASR | 否，桥不启动 |

没有“用旧文字代替”“空文本保存”“模拟成功”或自动重试。这样任何失败都能定位在唯一一层。

## 8. 文件地图

| 文件 | 责任 |
|---|---|
| `hardware/esp32-s3-sensors/src/main.cpp` | I2S 采样、BOOT 触发、固定 PCM 帧 |
| `backend/app/integrations/voice_protocol.py` | 严格解析帧、PCM 转 WAV |
| `backend/app/services/asr_settings.py` | 读取 ASR 私有环境变量 |
| `backend/app/integrations/zhipu_asr.py` | 一次智谱 WAV → text 请求 |
| `backend/scripts/forward_esp32_serial.py` | 唯一 USB 读者；硬件和语音的电脑桥 |
| `backend/app/api/routes.py` | 不改；继续使用现有 `/api/entries` |
| `backend/data/user_entries.jsonl` | 只保存真实转写文字，不保存音频 |
