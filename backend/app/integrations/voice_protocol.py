"""Strict framing for one ESP32 INMP441 PCM voice capture."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import wave


VOICE_BEGIN_PREFIX = b"@voice_begin "
VOICE_SAMPLE_RATE_HZ = 16000
VOICE_SAMPLE_WIDTH_BITS = 16
VOICE_CHANNELS = 1
VOICE_PCM_BYTES = VOICE_SAMPLE_RATE_HZ * 3 * 2


@dataclass(frozen=True)
class VoiceFrameHeader:
    capture_id: int
    sample_rate_hz: int
    sample_width_bits: int
    channels: int
    pcm_bytes: int


def parse_voice_begin_line(raw_line: bytes) -> VoiceFrameHeader:
    try:
        line = raw_line.decode("ascii").strip()
    except UnicodeDecodeError as error:
        raise ValueError("voice frame header is not ASCII") from error
    if not line.startswith(VOICE_BEGIN_PREFIX.decode("ascii")):
        raise ValueError("serial line is not a voice frame header")

    fields: dict[str, str] = {}
    for token in line[len(VOICE_BEGIN_PREFIX) :].split():
        name, separator, value = token.partition("=")
        if separator != "=" or not name or not value:
            raise ValueError("voice frame header contains an invalid field")
        if name in fields:
            raise ValueError(f"voice frame header duplicates {name}")
        fields[name] = value

    required_names = {
        "id",
        "sample_rate_hz",
        "sample_width_bits",
        "channels",
        "pcm_bytes",
    }
    if set(fields) != required_names:
        raise ValueError("voice frame header fields do not match the contract")

    try:
        header = VoiceFrameHeader(
            capture_id=int(fields["id"]),
            sample_rate_hz=int(fields["sample_rate_hz"]),
            sample_width_bits=int(fields["sample_width_bits"]),
            channels=int(fields["channels"]),
            pcm_bytes=int(fields["pcm_bytes"]),
        )
    except ValueError as error:
        raise ValueError("voice frame header contains a non-integer value") from error

    if header.capture_id < 1:
        raise ValueError("voice frame id must be positive")
    if header.sample_rate_hz != VOICE_SAMPLE_RATE_HZ:
        raise ValueError("voice sample rate does not match the contract")
    if header.sample_width_bits != VOICE_SAMPLE_WIDTH_BITS:
        raise ValueError("voice sample width does not match the contract")
    if header.channels != VOICE_CHANNELS:
        raise ValueError("voice channel count does not match the contract")
    if header.pcm_bytes != VOICE_PCM_BYTES:
        raise ValueError("voice PCM byte count does not match the contract")
    return header


def validate_voice_end_line(raw_line: bytes, header: VoiceFrameHeader) -> None:
    expected = f"@voice_end id={header.capture_id}".encode("ascii")
    if raw_line.strip() != expected:
        raise ValueError("voice frame end marker does not match its header")


def pcm_to_wav(pcm: bytes, header: VoiceFrameHeader) -> bytes:
    if len(pcm) != header.pcm_bytes:
        raise ValueError("voice PCM length does not match its header")

    output = BytesIO()
    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(header.channels)
        wav_file.setsampwidth(header.sample_width_bits // 8)
        wav_file.setframerate(header.sample_rate_hz)
        wav_file.writeframes(pcm)
    return output.getvalue()
