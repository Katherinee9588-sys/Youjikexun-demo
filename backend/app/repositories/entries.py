from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.models.health import StoredUserEntry, UserEntryCreate


DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "user_entries.jsonl"


class EntryRepository:
    """Append-only storage for new local user records."""

    @staticmethod
    def all() -> tuple[StoredUserEntry, ...]:
        if not DATA_PATH.exists():
            return ()

        entries: list[StoredUserEntry] = []
        for line_number, line in enumerate(
            DATA_PATH.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                raise ValueError(f"user_entries.jsonl line {line_number} is empty")
            entries.append(StoredUserEntry.model_validate_json(line))
        return tuple(entries)

    @staticmethod
    def append(payload: UserEntryCreate) -> StoredUserEntry:
        entry = StoredUserEntry(
            id=str(uuid4()),
            record_date=payload.record_date,
            created_at=datetime.now(timezone.utc),
            original_text=payload.original_text,
            input_method=payload.input_method,
            extraction_status="pending",
        )
        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        with DATA_PATH.open("a", encoding="utf-8") as stream:
            stream.write(entry.model_dump_json())
            stream.write("\n")
        return entry

    @classmethod
    def by_id(cls, entry_id: str) -> StoredUserEntry | None:
        for entry in cls.all():
            if entry.id == entry_id:
                return entry
        return None
