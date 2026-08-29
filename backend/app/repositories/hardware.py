from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.models.hardware import MAX30102SampleCreate, StoredMAX30102Sample


DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "hardware_max30102.jsonl"


class MAX30102Repository:
    """Append-only raw hardware evidence; separate from the human ledger."""

    @staticmethod
    def all() -> tuple[StoredMAX30102Sample, ...]:
        if not DATA_PATH.exists():
            return ()

        samples: list[StoredMAX30102Sample] = []
        for line_number, line in enumerate(
            DATA_PATH.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                raise ValueError(f"hardware_max30102.jsonl line {line_number} is empty")
            samples.append(StoredMAX30102Sample.model_validate_json(line))
        return tuple(samples)

    @staticmethod
    def append(payload: MAX30102SampleCreate) -> StoredMAX30102Sample:
        sample = StoredMAX30102Sample(
            **payload.model_dump(),
            id=str(uuid4()),
            received_at=datetime.now(timezone.utc),
        )
        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        with DATA_PATH.open("a", encoding="utf-8") as stream:
            stream.write(sample.model_dump_json())
            stream.write("\n")
        return sample

    @classmethod
    def latest_valid(cls) -> StoredMAX30102Sample | None:
        for sample in reversed(cls.all()):
            if sample.signal_quality == "valid":
                return sample
        return None
