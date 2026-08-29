from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import Field, model_validator

from app.models.health import StrictModel


class MAX30102SampleCreate(StrictModel):
    """One measurement window forwarded by the local USB serial bridge.

    ``received_at`` is assigned by the PC because an ESP32 without NTP has no
    trustworthy wall clock. Missing values are kept as null; this model never
    invents a SpO2 value from a heart-rate-only firmware.
    """

    schema_version: Literal[1] = 1
    device_id: str = Field(min_length=1, max_length=80)
    sequence: int = Field(ge=0)
    device_uptime_ms: int = Field(ge=0)
    ir_value: int = Field(ge=0)
    finger_present: bool
    heart_rate_bpm: Optional[float] = Field(default=None, ge=20, le=255)
    spo2_percent: Optional[float] = Field(default=None, ge=70, le=100)
    signal_quality: Literal["warming_up", "finger_absent", "unstable", "valid"]

    @model_validator(mode="after")
    def validate_measurement_state(self) -> "MAX30102SampleCreate":
        if not self.finger_present:
            if self.signal_quality != "finger_absent":
                raise ValueError("finger_present=false requires signal_quality=finger_absent")
            if self.heart_rate_bpm is not None or self.spo2_percent is not None:
                raise ValueError("finger-absent sample cannot contain vital values")
        if self.signal_quality == "valid" and (
            self.heart_rate_bpm is None and self.spo2_percent is None
        ):
            raise ValueError("valid sample requires at least one measured vital")
        return self


class StoredMAX30102Sample(MAX30102SampleCreate):
    id: str = Field(min_length=1)
    received_at: datetime
