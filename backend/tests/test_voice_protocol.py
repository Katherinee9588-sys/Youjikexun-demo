from io import BytesIO
import wave

import pytest

from app.integrations.voice_protocol import (
    VOICE_PCM_BYTES,
    parse_voice_begin_line,
    pcm_to_wav,
    validate_voice_end_line,
)
from app.integrations.zhipu_asr import (
    SpeechToTextRequestError,
    validate_transcript,
)
from app.services.asr_settings import ASRConfigurationError, ASRSettings


def valid_header_line() -> bytes:
    return (
        b"@voice_begin id=1 sample_rate_hz=16000 sample_width_bits=16 "
        b"channels=1 pcm_bytes=96000\n"
    )


def test_voice_frame_contract_builds_a_standard_wav() -> None:
    header = parse_voice_begin_line(valid_header_line())
    pcm = b"\x00\x00" * (VOICE_PCM_BYTES // 2)
    wav_bytes = pcm_to_wav(pcm, header)

    with wave.open(BytesIO(wav_bytes), "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getsampwidth() == 2
        assert wav_file.getframerate() == 16000
        assert wav_file.getnframes() == 48000
        assert wav_file.readframes(48000) == pcm

    validate_voice_end_line(b"@voice_end id=1\n", header)


def test_voice_frame_rejects_any_non_contract_size() -> None:
    with pytest.raises(ValueError, match="byte count"):
        parse_voice_begin_line(
            b"@voice_begin id=1 sample_rate_hz=16000 sample_width_bits=16 "
            b"channels=1 pcm_bytes=32000\n"
        )


def test_asr_settings_require_all_three_local_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ASR_API_KEY", raising=False)
    monkeypatch.delenv("ASR_BASE_URL", raising=False)
    monkeypatch.delenv("ASR_MODEL", raising=False)
    with pytest.raises(ASRConfigurationError, match="ASR_API_KEY"):
        ASRSettings.from_environment()

    monkeypatch.setenv("ASR_API_KEY", "test-key")
    monkeypatch.setenv("ASR_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
    monkeypatch.setenv("ASR_MODEL", "glm-asr-2512")
    settings = ASRSettings.from_environment()
    assert settings.model == "glm-asr-2512"


def test_asr_transcript_rejects_punctuation_only_response() -> None:
    with pytest.raises(SpeechToTextRequestError, match="no lexical text"):
        validate_transcript("#")

    assert validate_transcript(" 今天心情很好。 ") == "今天心情很好。"
