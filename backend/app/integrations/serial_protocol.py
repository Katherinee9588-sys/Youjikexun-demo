from __future__ import annotations

import json

from app.models.hardware import MAX30102SampleCreate


def parse_max30102_json_line(raw_line: bytes) -> MAX30102SampleCreate:
    """Parse one UTF-8 NDJSON line emitted by the future ESP32 firmware.

    The USB reader itself is intentionally separate: this pure parser can be
    tested without a physical serial device and refuses the current human-only
    debug text instead of guessing at it.
    """

    try:
        decoded = raw_line.decode("utf-8").strip()
    except UnicodeDecodeError as error:
        raise ValueError("serial payload is not UTF-8") from error
    if not decoded:
        raise ValueError("serial payload is empty")
    try:
        payload = json.loads(decoded)
    except json.JSONDecodeError as error:
        raise ValueError("serial payload is not valid JSON") from error
    return MAX30102SampleCreate.model_validate(payload)
