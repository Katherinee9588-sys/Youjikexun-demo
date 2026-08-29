"""Forward one ESP32 USB serial stream: valid MAX30102 JSON and INMP441 voice."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from urllib.request import Request, urlopen

from app.integrations.serial_bridge import should_forward_max30102_sample
from app.integrations.serial_protocol import parse_max30102_json_line
from app.integrations.voice_protocol import (
    VoiceFrameHeader,
    parse_voice_begin_line,
    pcm_to_wav,
    validate_voice_end_line,
)
from app.integrations.zhipu_asr import (
    SpeechToTextRequestError,
    ZhipuSpeechToTextAdapter,
)
from app.services.asr_settings import ASRConfigurationError, ASRSettings


def post_json(endpoint: str, payload: dict[str, object], timeout_seconds: float) -> dict[str, object]:
    request = Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        if response.status != 201:
            raise RuntimeError(f"backend endpoint returned HTTP {response.status}")
        return json.loads(response.read().decode("utf-8"))


def read_exact(connection: object, byte_count: int) -> bytes:
    chunks: list[bytes] = []
    remaining = byte_count
    while remaining > 0:
        chunk = connection.read(remaining)
        if not chunk:
            raise RuntimeError("voice frame ended before all PCM bytes arrived")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def read_voice_frame(connection: object, begin_line: bytes) -> tuple[VoiceFrameHeader, bytes]:
    header = parse_voice_begin_line(begin_line)
    pcm = read_exact(connection, header.pcm_bytes)
    frame_end = connection.readline()
    validate_voice_end_line(frame_end, header)
    return header, pcm


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Forward valid MAX30102 samples and real INMP441 voice transcriptions."
    )
    parser.add_argument("--port", required=True, help="for example /dev/cu.usbmodem1101")
    parser.add_argument("--baud", type=int, default=921600)
    parser.add_argument("--backend", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=float, default=5.0)
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    try:
        import serial
    except ImportError as error:
        raise SystemExit(
            "pyserial is not installed. Install backend requirements before running the bridge."
        ) from error

    try:
        asr = ZhipuSpeechToTextAdapter(ASRSettings.from_environment())
    except ASRConfigurationError as error:
        raise SystemExit(str(error)) from error

    hardware_endpoint = f"{arguments.backend.rstrip('/')}/api/hardware/max30102/readings"
    entry_endpoint = f"{arguments.backend.rstrip('/')}/api/entries"
    connection = serial.Serial()
    connection.port = arguments.port
    connection.baudrate = arguments.baud
    connection.timeout = arguments.timeout
    # GPIO0 is the ESP32-S3 DevKitC-1 BOOT button. Keep the host-side serial
    # control lines released before opening the port so they do not hold GPIO0
    # low and prevent the next physical BOOT press from being observed.
    connection.dtr = False
    connection.rts = False

    with connection:
        print(f"Reading ESP32 serial data from {arguments.port}", file=sys.stderr)
        for raw_line in connection:
            if raw_line.startswith(b"#"):
                print(raw_line.decode("utf-8", errors="replace").rstrip(), file=sys.stderr)
                continue
            if raw_line.startswith(b"@voice_begin "):
                try:
                    header, pcm = read_voice_frame(connection, raw_line)
                    transcript = asr.transcribe_wav(pcm_to_wav(pcm, header))
                    entry = post_json(
                        entry_endpoint,
                        {
                            "record_date": date.today().isoformat(),
                            "original_text": transcript,
                            "input_method": "voice",
                        },
                        arguments.timeout,
                    )
                except (RuntimeError, SpeechToTextRequestError, ValueError) as error:
                    print(f"Voice capture rejected: {error}", file=sys.stderr)
                    continue
                print(
                    f"Stored voice capture id={header.capture_id} entry_id={entry['id']} text={transcript}",
                    file=sys.stderr,
                )
                continue

            try:
                sample = parse_max30102_json_line(raw_line)
            except ValueError as error:
                print(f"Serial line rejected: {error}", file=sys.stderr)
                continue
            if not should_forward_max30102_sample(sample):
                continue
            stored = post_json(
                hardware_endpoint,
                sample.model_dump(mode="json"),
                arguments.timeout,
            )
            print(
                f"Stored MAX30102 sequence={sample.sequence} reading_id={stored['id']}",
                file=sys.stderr,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
