from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, Field


class HardwareReading(BaseModel):
    source_device: str = Field(min_length=1)
    captured_at: datetime
    metric: str = Field(min_length=1)
    value: float
    unit: str = Field(min_length=1)


class HardwareAdapter(Protocol):
    def normalize(self, payload: bytes) -> list[HardwareReading]: ...

