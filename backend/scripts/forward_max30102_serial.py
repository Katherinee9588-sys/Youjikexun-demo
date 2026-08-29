"""Forward verified MAX30102 NDJSON from one USB serial port to FastAPI.

Run this only after the FastAPI backend is running. It never starts by itself,
and it forwards only samples marked ``signal_quality=valid`` by the ESP32.
"""

from __future__ import annotations

import argparse
import sys
from urllib.request import Request, urlopen

from app.integrations.serial_bridge import should_forward_max30102_sample
from app.integrations.serial_protocol import parse_max30102_json_line


def post_sample(endpoint: str, payload: bytes, timeout_seconds: float) -> None:
    request = Request(
        endpoint,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        if response.status != 201:
            raise RuntimeError(f"hardware endpoint returned HTTP {response.status}")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Forward valid MAX30102 serial JSON to the local FastAPI API."
    )
    parser.add_argument("--port", required=True, help="for example /dev/cu.usbmodem123")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument(
        "--endpoint",
        default="http://127.0.0.1:8000/api/hardware/max30102/readings",
    )
    parser.add_argument("--timeout", type=float, default=3.0)
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    try:
        import serial
    except ImportError as error:
        raise SystemExit(
            "pyserial is not installed. Install backend requirements before running the bridge."
        ) from error

    with serial.Serial(arguments.port, arguments.baud, timeout=1) as connection:
        print(f"Reading MAX30102 serial data from {arguments.port}", file=sys.stderr)
        for raw_line in connection:
            if raw_line.lstrip().startswith(b"#"):
                continue
            sample = parse_max30102_json_line(raw_line)
            if not should_forward_max30102_sample(sample):
                continue
            post_sample(
                arguments.endpoint,
                sample.model_dump_json().encode("utf-8"),
                arguments.timeout,
            )
            print(
                f"Stored sequence={sample.sequence} bpm={sample.heart_rate_bpm}",
                file=sys.stderr,
            )


if __name__ == "__main__":
    raise SystemExit(main())
