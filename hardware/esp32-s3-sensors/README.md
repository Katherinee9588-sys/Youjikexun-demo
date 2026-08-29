# ESP32-S3 sensors (MAX30102 + LM393)

这是主项目中的**独立硬件工程**。它不会覆盖 `Downloads/code-project-1` 或 `Downloads/code-project-2`；后两者仍是你已经单独验收过的原始测试工程。

## 当前接线

| 模块 | ESP32-S3 引脚 |
|---|---|
| MAX30102 VIN / GND | 3V3 / GND |
| MAX30102 SDA / SCL | GPIO8 / GPIO9 |
| MAX30102 INT | GPIO6（本工程暂不使用） |
| LM393 `+` / `G` | 3V3 / GND |
| LM393 AO / DO | GPIO4 / GPIO5 |
| INMP441 VDD / GND | 3V3 / GND |
| INMP441 SCK / WS / SD | GPIO14 / GPIO15 / GPIO16 |
| INMP441 L/R | GND（左声道） |

LM393 已按 3V3 供电；不要把它切回 5V 再将 AO/DO 直接接入 ESP32。

INMP441 已加入**I2S 采样验收和语音采集**：它每秒输出一次 `# inmp441` 的真实采样数、峰值和 RMS 音量，方便确认接线和收音芯片本身工作。短按 ESP32 的 `BOOT` 后，固件采集固定 3 秒的 16 kHz 单声道 PCM，并交给电脑串口桥转写；它不在 ESP32 上做降噪或文字猜测。

## 输出规则

- 串口中**不带 `#` 的每行**都是可转发给后端的 MAX30102 JSON；格式见 [`docs/HARDWARE_CONTRACT.md`](../../docs/HARDWARE_CONTRACT.md)。
- `finger_present=false` 时，`heart_rate_bpm` 和 `spo2_percent` 都是 `null`，因此不会把移开手指前的旧 BPM 写入后端。
- 接触后的前八次有效心跳是 `warming_up`，不输出 BPM；之后只有八次心跳窗口的波动不超过 18 BPM、且连续两次确认相近，才输出 `valid`。同一次接触内若新窗口相对已确认值突跳超过 8 BPM，输出 `unstable` 与 `null`，直到移开手指重新开始。
- 心跳检测固定每 20ms 取一次样本，与已验证的单模块 MAX30102 测试节奏一致；不要为了提高刷新速度改成无间隔循环。
- 该版本只验证了心率，`spo2_percent` 始终是 `null`，不把“MAX30102 有硬件”误写成“已经测得血氧”。
- 以 `# lm393` 开头的是 LM393 调试行，只反映声音活动；它不能采集可供语音识别的音频，不能转写文字。
- 以 `# inmp441` 开头的是 INMP441 调试行；安静时 `peak`/`rms` 较低，对着麦克风正常说话时两者应明显升高。它不会被串口桥转发到后端。
- 正常运行后短按一次 `BOOT`：输出 `# voice state=capturing`，录音 3 秒后发送 `@voice_begin`、PCM 二进制数据和 `@voice_end`。此时不要运行 PlatformIO Serial Monitor；必须由 [`backend/scripts/forward_esp32_serial.py`](../../backend/scripts/forward_esp32_serial.py) 独占该串口。

## 在 VS Code 烧录

1. 关闭目前运行的串口监视器（否则串口会被占用）。
2. VS Code 选择 **File → Open Folder…**，打开：
   `/Users/catherine/Documents/Codex/Youjikexun/hardware/esp32-s3-sensors`
3. 等右下角 PlatformIO 完成加载；首次下载依赖可能需要几分钟。
4. 点击底部状态栏的右箭头 Upload，或按 `Cmd+Shift+P` 后运行 `PlatformIO: Upload`。
5. 上传出现 `[SUCCESS]` 后，再运行 `PlatformIO: Serial Monitor`，波特率为 `921600`。语音转写联调时则关闭 Monitor，改由电脑串口桥独占 USB 串口。

这一步会把 ESP32 当前运行的测试固件替换为本工程固件；两个下载目录里的源代码不会被删除，之后仍可打开并重新烧录作单模块回归。

## MAX30102 现场验收

1. 传感器空置约 5 秒：应看到 JSON 中 `ir_value` 接近几百、`finger_present:false`、两个生命体征均为 `null`。
2. 手指平稳覆盖发光面，保持 30–60 秒：IR 应明显升到数万以上；前几行是 `warming_up`，稳定后出现 `signal_quality:"valid"` 和 BPM；若有 `unstable`，应调整贴合后再次测量。
3. 移开手指：下一秒开始必须回到 `finger_absent` 和 BPM 为 `null`。若仍有数字 BPM，停止使用并把完整串口输出发来。

这只用于工程信号验证，不用作医疗诊断。
