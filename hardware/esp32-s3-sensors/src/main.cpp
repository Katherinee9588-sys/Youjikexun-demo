#include <Arduino.h>
#include <Wire.h>
#include <math.h>

#include "driver/i2s.h"
#include "MAX30105.h"
#include "heartRate.h"

// The LM393 code below follows the already verified wiring from code-project-1.
#include "driver/adc.h"

namespace {

// MAX30102 wiring
constexpr int MAX30102_SDA_PIN = 8;
constexpr int MAX30102_SCL_PIN = 9;
constexpr long FINGER_IR_THRESHOLD = 50000;
constexpr unsigned long MAX_RETRY_INTERVAL_MS = 5000;
constexpr unsigned long MAX_OUTPUT_INTERVAL_MS = 1000;
// SparkFun's beat detector in the separately verified sketch was fed one
// sample every 20 ms. Calling it at an unconstrained loop frequency makes it
// see repeated/irregular samples and produces false beat intervals.
constexpr unsigned long HEART_SAMPLE_INTERVAL_MS = 20;
constexpr unsigned long STALE_BEAT_INTERVAL_MS = 5000;
// A four-beat mean reacts too strongly to one false beat. Keep eight beat
// intervals and emit their median only when the whole window is coherent.
constexpr byte RATE_SIZE = 8;
constexpr byte MAX_STABLE_RATE_SPREAD_BPM = 18;
// During one finger contact a resting heart rate should not jump by a large
// amount from one coherent window to the next. This is a signal-quality gate,
// not a medical rule: a large jump is withheld instead of being reported.
constexpr byte MAX_TRUSTED_BPM_DELTA = 8;
constexpr byte INITIAL_CONFIRMATIONS_REQUIRED = 2;

// LM393 wiring
constexpr int LM393_AO_PIN = 4;  // ADC1_CH3
constexpr int LM393_DO_PIN = 5;
constexpr int LM393_SAMPLE_COUNT = 400;
constexpr int LM393_SAMPLE_DELAY_US = 50;
constexpr int LM393_P2P_THRESHOLD = 12;
constexpr float LM393_CENTER_DEVIATION_THRESHOLD = 8.0F;
constexpr unsigned long LM393_WINDOW_INTERVAL_MS = 200;
constexpr unsigned long LM393_DEBUG_INTERVAL_MS = 1000;

// INMP441 I2S wiring. L/R is connected to GND, so only the left channel is read.
constexpr i2s_port_t INMP441_I2S_PORT = I2S_NUM_0;
constexpr int INMP441_SCK_PIN = 14;
constexpr int INMP441_WS_PIN = 15;
constexpr int INMP441_SD_PIN = 16;
constexpr int INMP441_SAMPLE_RATE = 16000;
constexpr size_t INMP441_FRAME_SAMPLES = 64;
constexpr unsigned long INMP441_DEBUG_INTERVAL_MS = 1000;
constexpr int VOICE_TRIGGER_PIN = 0;  // Board BOOT button; LOW while pressed.
constexpr size_t VOICE_CAPTURE_SECONDS = 3;
constexpr size_t VOICE_PCM_SAMPLE_COUNT =
    INMP441_SAMPLE_RATE * VOICE_CAPTURE_SECONDS;

enum class VoiceCaptureState {
  idle,
  capturing,
  transmitting,
};

constexpr char DEVICE_ID[] = "max30102-01";

MAX30105 particleSensor;
bool max30102Connected = false;
bool fingerPresent = false;
unsigned long lastMaxRetryAt = 0;
unsigned long lastMaxOutputAt = 0;
unsigned long lastHeartSampleAt = 0;
unsigned long lastBeatAt = 0;
unsigned long lastAcceptedBeatAt = 0;
unsigned long maxSequence = 0;

byte rates[RATE_SIZE] = {0};
byte rateSpot = 0;
byte rateCount = 0;
int medianBpm = 0;
byte rateSpreadBpm = 0;
bool rateWindowStable = false;
int trustedBpm = 0;
int initialCandidateBpm = 0;
byte initialCandidateConfirmations = 0;
bool hasTrustedBpm = false;
bool rateWindowMatchesTrust = false;

float lm393Baseline = 0.0F;
bool lm393BaselineInitialized = false;
int lm393PeakToPeak = 0;
float lm393Center = 0.0F;
int lm393Digital = HIGH;
bool lm393SoundDetected = false;
unsigned long lastLm393WindowAt = 0;
unsigned long lastLm393DebugAt = 0;

bool inmp441Connected = false;
int32_t inmp441Samples[INMP441_FRAME_SAMPLES] = {0};
unsigned long inmp441SamplesInInterval = 0;
int64_t inmp441SquaredTotalInInterval = 0;
int32_t inmp441PeakInInterval = 0;
unsigned long lastInmp441DebugAt = 0;

VoiceCaptureState voiceCaptureState = VoiceCaptureState::idle;
int16_t voicePcm[VOICE_PCM_SAMPLE_COUNT] = {0};
size_t voicePcmSampleCount = 0;
unsigned long voiceCaptureId = 0;
bool voiceTriggerArmed = false;
bool voiceTriggerStateKnown = false;
bool voiceTriggerWasPressed = false;

void resetHeartRateState() {
  rateSpot = 0;
  rateCount = 0;
  medianBpm = 0;
  rateSpreadBpm = 0;
  rateWindowStable = false;
  trustedBpm = 0;
  initialCandidateBpm = 0;
  initialCandidateConfirmations = 0;
  hasTrustedBpm = false;
  rateWindowMatchesTrust = false;
  lastBeatAt = 0;
  lastAcceptedBeatAt = 0;
  for (byte index = 0; index < RATE_SIZE; ++index) {
    rates[index] = 0;
  }
}

void configureMax30102() {
  particleSensor.setup();
  // Red LED pulse amplitude. 0x0A (~4%) is too dim for reliable beat detection
  // on many fingers: the AC component of the plethysmogram stays below the
  // beat detector's threshold and the firmware never leaves warming_up.
  // 0x24 (~14%) matches SparkFun's heart-rate example and produces a strong,
  // clean pulse waveform without saturating the ADC.
  particleSensor.setPulseAmplitudeRed(0x24);
  particleSensor.setPulseAmplitudeGreen(0);
}

void attemptMax30102Connection(unsigned long now) {
  if (max30102Connected) {
    return;
  }
  if (lastMaxRetryAt != 0 && now - lastMaxRetryAt < MAX_RETRY_INTERVAL_MS) {
    return;
  }

  lastMaxRetryAt = now;
  if (!particleSensor.begin(Wire, I2C_SPEED_FAST)) {
    Serial.println("# max30102 status=not_connected");
    return;
  }

  configureMax30102();
  max30102Connected = true;
  fingerPresent = false;
  lastHeartSampleAt = now;
  resetHeartRateState();
  Serial.println("# max30102 status=connected");
}

void printMax30102Json(
    long irValue,
    bool hasHeartRate,
    const char *signalQuality) {
  ++maxSequence;
  Serial.printf(
      "{\"schema_version\":1,\"device_id\":\"%s\",\"sequence\":%lu,"
      "\"device_uptime_ms\":%lu,\"ir_value\":%ld,\"finger_present\":%s,"
      "\"heart_rate_bpm\":",
      DEVICE_ID,
      maxSequence,
      millis(),
      irValue,
      fingerPresent ? "true" : "false");

  if (hasHeartRate) {
    Serial.printf("%d", trustedBpm);
  } else {
    Serial.print("null");
  }

  // This firmware has no verified SpO2 calculation. Never emit a made-up value.
  Serial.printf(
      ",\"spo2_percent\":null,\"signal_quality\":\"%s\"}\n",
      signalQuality);
}

void refreshHeartRateWindow() {
  rateWindowMatchesTrust = false;
  if (rateCount < RATE_SIZE) {
    rateWindowStable = false;
    return;
  }

  byte orderedRates[RATE_SIZE] = {0};
  for (byte index = 0; index < RATE_SIZE; ++index) {
    orderedRates[index] = rates[index];
  }
  for (byte left = 0; left < RATE_SIZE - 1; ++left) {
    for (byte right = left + 1; right < RATE_SIZE; ++right) {
      if (orderedRates[right] < orderedRates[left]) {
        const byte temporary = orderedRates[left];
        orderedRates[left] = orderedRates[right];
        orderedRates[right] = temporary;
      }
    }
  }

  rateSpreadBpm = orderedRates[RATE_SIZE - 1] - orderedRates[0];
  medianBpm = (orderedRates[(RATE_SIZE / 2) - 1] + orderedRates[RATE_SIZE / 2]) / 2;
  rateWindowStable = rateSpreadBpm <= MAX_STABLE_RATE_SPREAD_BPM;
  if (!rateWindowStable) {
    return;
  }

  if (!hasTrustedBpm) {
    if (initialCandidateConfirmations == 0) {
      initialCandidateBpm = medianBpm;
      initialCandidateConfirmations = 1;
      return;
    }
    if (abs(medianBpm - initialCandidateBpm) > MAX_TRUSTED_BPM_DELTA) {
      initialCandidateBpm = medianBpm;
      initialCandidateConfirmations = 1;
      return;
    }

    ++initialCandidateConfirmations;
    if (initialCandidateConfirmations >= INITIAL_CONFIRMATIONS_REQUIRED) {
      trustedBpm = medianBpm;
      hasTrustedBpm = true;
      rateWindowMatchesTrust = true;
    }
    return;
  }

  if (abs(medianBpm - trustedBpm) <= MAX_TRUSTED_BPM_DELTA) {
    trustedBpm = medianBpm;
    rateWindowMatchesTrust = true;
  }
}

void updateMax30102(unsigned long now) {
  attemptMax30102Connection(now);
  if (!max30102Connected) {
    return;
  }
  if (now - lastHeartSampleAt < HEART_SAMPLE_INTERVAL_MS) {
    return;
  }
  lastHeartSampleAt = now;

  const long irValue = particleSensor.getIR();
  const bool hasFingerNow = irValue >= FINGER_IR_THRESHOLD;

  if (!hasFingerNow) {
    if (fingerPresent) {
      resetHeartRateState();
    }
    fingerPresent = false;
    if (now - lastMaxOutputAt >= MAX_OUTPUT_INTERVAL_MS) {
      lastMaxOutputAt = now;
      printMax30102Json(irValue, false, "finger_absent");
    }
    return;
  }

  if (!fingerPresent) {
    // A new contact must collect fresh beats. Do not reuse a previous reading.
    resetHeartRateState();
  }
  fingerPresent = true;

  if (checkForBeat(irValue)) {
    if (lastBeatAt != 0) {
      const float bpm = 60.0F / ((now - lastBeatAt) / 1000.0F);
      if (bpm > 20.0F && bpm < 255.0F) {
        rates[rateSpot] = static_cast<byte>(bpm);
        rateSpot = (rateSpot + 1) % RATE_SIZE;
        if (rateCount < RATE_SIZE) {
          ++rateCount;
        }

        refreshHeartRateWindow();
        lastAcceptedBeatAt = now;
      }
    }
    lastBeatAt = now;
  }

  if (now - lastMaxOutputAt < MAX_OUTPUT_INTERVAL_MS) {
    return;
  }
  lastMaxOutputAt = now;

  if (rateCount < RATE_SIZE) {
    printMax30102Json(irValue, false, "warming_up");
    return;
  }
  if (!hasTrustedBpm) {
    printMax30102Json(irValue, false, "warming_up");
    return;
  }
  if (now - lastAcceptedBeatAt >= STALE_BEAT_INTERVAL_MS) {
    printMax30102Json(irValue, false, "unstable");
    return;
  }
  if (!rateWindowStable) {
    Serial.printf(
        "# max30102 rate_window median=%d trusted=%d spread=%u status=unstable\n",
        medianBpm,
        trustedBpm,
        rateSpreadBpm);
    printMax30102Json(irValue, false, "unstable");
    return;
  }
  if (!rateWindowMatchesTrust) {
    Serial.printf(
        "# max30102 rate_window median=%d trusted=%d spread=%u status=unstable\n",
        medianBpm,
        trustedBpm,
        rateSpreadBpm);
    printMax30102Json(irValue, false, "unstable");
    return;
  }
  printMax30102Json(irValue, true, "valid");
}

void configureLm393() {
  pinMode(LM393_DO_PIN, INPUT);
  adc1_config_width(ADC_WIDTH_BIT_12);
  adc1_config_channel_atten(ADC1_CHANNEL_3, ADC_ATTEN_DB_12);
}

void updateLm393(unsigned long now) {
  if (now - lastLm393WindowAt < LM393_WINDOW_INTERVAL_MS) {
    return;
  }
  lastLm393WindowAt = now;

  int minimum = 4095;
  int maximum = 0;
  long total = 0;
  for (int index = 0; index < LM393_SAMPLE_COUNT; ++index) {
    const int value = adc1_get_raw(ADC1_CHANNEL_3);
    minimum = min(minimum, value);
    maximum = max(maximum, value);
    total += value;
    delayMicroseconds(LM393_SAMPLE_DELAY_US);
  }

  lm393PeakToPeak = maximum - minimum;
  lm393Center = static_cast<float>(total) / LM393_SAMPLE_COUNT;
  if (!lm393BaselineInitialized) {
    lm393Baseline = lm393Center;
    lm393BaselineInitialized = true;
  } else {
    // Keep a fractional baseline: the old integer baseline could appear stuck.
    lm393Baseline = lm393Baseline * 0.95F + lm393Center * 0.05F;
  }

  lm393Digital = digitalRead(LM393_DO_PIN);
  const float centerDeviation = fabsf(lm393Center - lm393Baseline);
  lm393SoundDetected = false;
  if (lm393PeakToPeak > LM393_P2P_THRESHOLD) {
    lm393SoundDetected = true;
  }
  if (lm393Digital == LOW) {
    lm393SoundDetected = true;
  }
  if (centerDeviation > LM393_CENTER_DEVIATION_THRESHOLD) {
    lm393SoundDetected = true;
  }
}

void printLm393Debug(unsigned long now) {
  if (now - lastLm393DebugAt < LM393_DEBUG_INTERVAL_MS) {
    return;
  }
  lastLm393DebugAt = now;
  Serial.printf(
      "# lm393 peak_to_peak=%d center=%.1f baseline=%.1f digital=%d detected=%s\n",
      lm393PeakToPeak,
      lm393Center,
      lm393Baseline,
      lm393Digital,
      lm393SoundDetected ? "true" : "false");
}

void configureInmp441() {
  const i2s_config_t config = {
      .mode = static_cast<i2s_mode_t>(I2S_MODE_MASTER | I2S_MODE_RX),
      .sample_rate = INMP441_SAMPLE_RATE,
      .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
      .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
      .communication_format = I2S_COMM_FORMAT_STAND_I2S,
      .intr_alloc_flags = 0,
      .dma_buf_count = 4,
      .dma_buf_len = INMP441_FRAME_SAMPLES,
      .use_apll = false,
      .tx_desc_auto_clear = false,
      .fixed_mclk = -1,
  };
  const i2s_pin_config_t pins = {
      .bck_io_num = INMP441_SCK_PIN,
      .ws_io_num = INMP441_WS_PIN,
      .data_out_num = I2S_PIN_NO_CHANGE,
      .data_in_num = INMP441_SD_PIN,
  };

  const esp_err_t installResult =
      i2s_driver_install(INMP441_I2S_PORT, &config, 0, nullptr);
  if (installResult != ESP_OK) {
    Serial.printf("# inmp441 status=not_connected stage=driver error=%d\n", installResult);
    return;
  }

  const esp_err_t pinResult = i2s_set_pin(INMP441_I2S_PORT, &pins);
  if (pinResult != ESP_OK) {
    Serial.printf("# inmp441 status=not_connected stage=pins error=%d\n", pinResult);
    return;
  }

  i2s_zero_dma_buffer(INMP441_I2S_PORT);
  inmp441Connected = true;
  Serial.println("# inmp441 status=connected sample_rate_hz=16000 channel=left");
}

void beginVoiceCapture() {
  ++voiceCaptureId;
  voicePcmSampleCount = 0;
  voiceCaptureState = VoiceCaptureState::capturing;
  Serial.printf(
      "# voice state=capturing id=%lu duration_ms=%u\n",
      voiceCaptureId,
      static_cast<unsigned int>(VOICE_CAPTURE_SECONDS * 1000));
}

void updateVoiceTrigger() {
  const bool triggerPressed = digitalRead(VOICE_TRIGGER_PIN) == LOW;
  if (!voiceTriggerStateKnown || triggerPressed != voiceTriggerWasPressed) {
    Serial.printf(
        "# voice trigger gpio0=%s\n",
        triggerPressed ? "pressed" : "released");
    voiceTriggerStateKnown = true;
    voiceTriggerWasPressed = triggerPressed;
  }
  if (!triggerPressed) {
    voiceTriggerArmed = true;
    return;
  }
  if (!voiceTriggerArmed) {
    return;
  }
  if (voiceCaptureState != VoiceCaptureState::idle) {
    return;
  }

  voiceTriggerArmed = false;
  beginVoiceCapture();
}

void transmitVoiceCapture() {
  if (voiceCaptureState != VoiceCaptureState::transmitting) {
    return;
  }

  const size_t pcmBytes = voicePcmSampleCount * sizeof(voicePcm[0]);
  Serial.printf(
      "@voice_begin id=%lu sample_rate_hz=16000 sample_width_bits=16 "
      "channels=1 pcm_bytes=%u\n",
      voiceCaptureId,
      static_cast<unsigned int>(pcmBytes));
  Serial.write(reinterpret_cast<const uint8_t *>(voicePcm), pcmBytes);
  Serial.printf("@voice_end id=%lu\n", voiceCaptureId);
  Serial.flush();
  voiceCaptureState = VoiceCaptureState::idle;
  Serial.printf("# voice state=sent id=%lu\n", voiceCaptureId);
}

void updateInmp441(unsigned long now) {
  if (!inmp441Connected) {
    return;
  }

  size_t bytesRead = 0;
  const esp_err_t readResult = i2s_read(
      INMP441_I2S_PORT,
      inmp441Samples,
      sizeof(inmp441Samples),
      &bytesRead,
      pdMS_TO_TICKS(5));
  if (readResult != ESP_OK) {
    Serial.printf("# inmp441 status=read_error error=%d\n", readResult);
    return;
  }

  const size_t sampleCount = bytesRead / sizeof(inmp441Samples[0]);
  for (size_t index = 0; index < sampleCount; ++index) {
    // INMP441 sends 24-bit two's-complement I2S data in a 32-bit receive word.
    // Keep its upper 16 bits. Shifting by 14 then narrowing to int16_t wraps
    // louder samples and corrupts the PCM sent to speech-to-text.
    const int16_t sample = static_cast<int16_t>(inmp441Samples[index] >> 16);
    if (voiceCaptureState == VoiceCaptureState::capturing) {
      voicePcm[voicePcmSampleCount] = sample;
      ++voicePcmSampleCount;
      if (voicePcmSampleCount == VOICE_PCM_SAMPLE_COUNT) {
        voiceCaptureState = VoiceCaptureState::transmitting;
      }
      continue;
    }

    const int64_t amplitude = sample < 0 ? -static_cast<int64_t>(sample) : sample;
    inmp441PeakInInterval = max(inmp441PeakInInterval, static_cast<int32_t>(amplitude));
    inmp441SquaredTotalInInterval += amplitude * amplitude;
    ++inmp441SamplesInInterval;
  }

  if (now - lastInmp441DebugAt < INMP441_DEBUG_INTERVAL_MS) {
    return;
  }
  lastInmp441DebugAt = now;

  if (inmp441SamplesInInterval == 0) {
    Serial.println("# inmp441 status=no_samples");
    return;
  }

  const int32_t rms = static_cast<int32_t>(sqrt(
      static_cast<double>(inmp441SquaredTotalInInterval) / inmp441SamplesInInterval));
  Serial.printf(
      "# inmp441 status=sampled samples=%lu peak=%ld rms=%ld\n",
      inmp441SamplesInInterval,
      static_cast<long>(inmp441PeakInInterval),
      static_cast<long>(rms));
  inmp441SamplesInInterval = 0;
  inmp441SquaredTotalInInterval = 0;
  inmp441PeakInInterval = 0;
}

}  // namespace

void setup() {
  Serial.begin(921600);
  Wire.begin(MAX30102_SDA_PIN, MAX30102_SCL_PIN);
  configureLm393();
  configureInmp441();
  pinMode(VOICE_TRIGGER_PIN, INPUT_PULLUP);
  Serial.println("# youjikexun esp32-s3 sensors booted");
}

void loop() {
  const unsigned long now = millis();
  updateVoiceTrigger();
  updateMax30102(now);
  updateLm393(now);
  printLm393Debug(now);
  updateInmp441(now);
  transmitVoiceCapture();
}
