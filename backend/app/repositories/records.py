from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

from app.models.health import HealthRecord


DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "records.json"


class RecordDataError(RuntimeError):
    pass


class RecordRepository:
    """Loads and validates the source package once per backend process."""

    @staticmethod
    @lru_cache(maxsize=1)
    def all() -> tuple[HealthRecord, ...]:
        raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        records = tuple(HealthRecord.model_validate(item) for item in raw)

        if len(records) == 0:
            raise RecordDataError("records.json contains no records")

        dates = [record.date for record in records]
        if dates != sorted(dates):
            raise RecordDataError("records.json must be sorted by date")
        if len(dates) != len(set(dates)):
            raise RecordDataError("records.json contains duplicate dates")

        return records

    @classmethod
    def by_date(cls, record_date: str) -> Optional[HealthRecord]:
        for record in cls.all():
            if record.date.isoformat() == record_date:
                return record
        return None
