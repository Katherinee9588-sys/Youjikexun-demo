from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Feedback(StrictModel):
    hot: str = Field(min_length=1)
    cold: list[str] = Field(min_length=1, max_length=3)


class HealthRecord(StrictModel):
    """Immutable source record from the supplied internal data package."""

    date: date
    day_number: int = Field(ge=1)
    user_input: str = Field(min_length=1)
    feedback: Feedback


class BloodPressureReading(StrictModel):
    systolic_pressure: int = Field(ge=40, le=260)
    diastolic_pressure: int = Field(ge=30, le=180)
    heart_rate: Optional[int] = Field(default=None, ge=30, le=220)
    measurement_context: list[str] = Field(default_factory=list)


class SleepObservation(StrictModel):
    recorded: bool
    raw_text: Optional[str]
    raw_value: Optional[float]
    raw_scale: Optional[Literal[10, 100]]
    normalized_1_10: Optional[float] = Field(default=None, ge=1, le=10)
    comparable: bool
    bed_time: Optional[time]
    wake_time: Optional[time]
    interruptions: Optional[int] = Field(default=None, ge=0)
    extraction_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_recording_state(self) -> "SleepObservation":
        if not self.recorded:
            values = (
                self.raw_text,
                self.raw_value,
                self.raw_scale,
                self.normalized_1_10,
                self.bed_time,
                self.wake_time,
                self.interruptions,
            )
            if any(value is not None for value in values):
                raise ValueError("unrecorded sleep cannot contain measured values")
        if self.comparable and self.normalized_1_10 is None:
            raise ValueError("comparable sleep requires normalized_1_10")
        return self


class MorningVitals(StrictModel):
    record_date: date
    body_weight: Optional[float] = Field(default=None, gt=0)
    body_fat_rate: Optional[float] = Field(default=None, ge=0, le=100)
    blood_pressure_readings: list[BloodPressureReading] = Field(default_factory=list)


class MealEntry(StrictModel):
    meal_time_slot: Literal["breakfast", "lunch", "dinner", "snack"]
    meal_raw_text: str = Field(min_length=1, max_length=200)
    meal_tag: list[str] = Field(default_factory=list)


ExerciseType = Literal[
    "aerobic",
    "strength",
    "core",
    "stretching",
    "yoga",
    "walking",
    "other",
]


class ExerciseDetail(StrictModel):
    type: ExerciseType
    raw_name: str = Field(min_length=1, max_length=100)
    duration_minutes: Optional[int] = Field(default=None, ge=1, le=1440)
    sets: Optional[int] = Field(default=None, ge=1, le=200)


class LifestyleInterventions(StrictModel):
    meals: list[MealEntry] = Field(default_factory=list)
    exercise_type: list[ExerciseType] = Field(default_factory=list)
    exercise_duration: Optional[int] = Field(default=None, ge=1, le=1440)
    exercise_sets: Optional[int] = Field(default=None, ge=1, le=200)
    exercise_details: list[ExerciseDetail] = Field(default_factory=list)
    exercise_raw_text: Optional[str] = Field(default=None, max_length=4000)
    sleep: SleepObservation

    @model_validator(mode="after")
    def validate_exercise_summary(self) -> "LifestyleInterventions":
        if len(self.exercise_type) != len(set(self.exercise_type)):
            raise ValueError("exercise_type values must not repeat")
        summary_types = set(self.exercise_type)
        detail_types = {detail.type for detail in self.exercise_details}
        if not detail_types.issubset(summary_types):
            raise ValueError("exercise_details types must appear in exercise_type")
        if not self.exercise_type and self.exercise_raw_text is None:
            if self.exercise_details:
                raise ValueError("empty exercise_type cannot contain exercise_details")
            if self.exercise_duration is not None or self.exercise_sets is not None:
                raise ValueError("unrecorded exercise cannot contain duration or sets")
        return self


class PhysicalSignal(StrictModel):
    symptom_location: Optional[str]
    symptom_desc: str = Field(min_length=1)
    symptom_trend: Optional[Literal["better", "same", "worse", "unclear"]]
    symptom_triggers: Optional[str]


class MentalModel(StrictModel):
    today_highlight: Optional[str] = Field(default=None, max_length=100)
    tomorrow_one_change: Optional[str] = Field(default=None, max_length=100)
    execution_resistance: Optional[str] = Field(default=None, max_length=100)
    user_hypothesis: Optional[str] = Field(default=None, max_length=100)


class AIContent(StrictModel):
    ai_daily_summary: Optional[str] = Field(default=None, max_length=150)
    ai_hypothesis_validation: Optional[str] = Field(default=None, max_length=50)


class RecordContext(StrictModel):
    weather_temp: Optional[int]
    special_stress: Optional[str]


class StoredUserEntry(StrictModel):
    id: str = Field(min_length=1)
    record_date: date
    created_at: datetime
    original_text: str = Field(min_length=1, max_length=4000)
    input_method: Literal["text", "voice", "accessibility"]
    extraction_status: Literal["pending"]


class UserEntryCreate(StrictModel):
    record_date: date
    original_text: str = Field(min_length=1, max_length=4000)
    input_method: Literal["text", "voice", "accessibility"]


class LedgerEntry(StrictModel):
    id: str
    source: Literal["legacy_import", "user_entry"]
    record_date: date
    day_number: Optional[int]
    created_at: Optional[datetime]
    original_text: str
    input_method: Literal["import", "text", "voice", "accessibility"]
    extraction_status: Literal["completed", "partial", "pending"]
    legacy_feedback: Optional[Feedback]
    morning_vitals: MorningVitals
    lifestyle: LifestyleInterventions
    physical_signals: list[PhysicalSignal]
    mental_model: MentalModel
    ai_content: AIContent
    context: RecordContext


class MetricCoverage(StrictModel):
    body_weight: int
    body_fat_rate: int
    blood_pressure: int
    heart_rate: int
    sleep_record: int
    comparable_sleep_score: int


class SceneSummary(StrictModel):
    id: Literal["joint_pain", "menstrual", "emotion"]
    title: str
    record_count: int
    latest_date: Optional[date]
    evidence_text: str
    boundary: str


class IntegrationStatus(StrictModel):
    voice_transcription: Literal[
        "not_configured", "configuration_error", "configured"
    ]
    language_model: Literal[
        "not_configured", "configuration_error", "configured"
    ]
    hardware_adapter: Literal["interface_ready_not_configured"]
    rag_retriever: Literal["not_loaded", "loaded_no_approved_chunks", "ready"]


class AppOverview(StrictModel):
    data_origin: Literal["real"]
    profile_display_name: Literal["Amy"]
    entry_count: int
    recorded_day_count: int
    first_date: date
    last_date: date
    calendar_span_days: int
    missing_calendar_days: int
    metric_coverage: MetricCoverage
    latest_entry: LedgerEntry
    recent_entries: list[LedgerEntry]
    scene_summaries: list[SceneSummary]
    integrations: IntegrationStatus


class DailySummary(StrictModel):
    """One full-page card of the 「今日记录」 view (today / yesterday / the day before)."""

    record_date: date
    entry_count: int = Field(ge=1)
    tags: list[str] = Field(default_factory=list, max_length=3)
    copy_lines: list[str] = Field(default_factory=list, max_length=2)
    recommend: list[str] = Field(default_factory=list, max_length=2)
    avoid: list[str] = Field(default_factory=list, max_length=2)


class VoiceTranscript(StrictModel):
    text: str = Field(min_length=1, max_length=4000)


class MetricValue(StrictModel):
    date: date
    text: str = Field(min_length=1)


class SelfReportedPanel(StrictModel):
    anchor_date: date
    body_weight: Optional[MetricValue]
    blood_pressure: Optional[MetricValue]
    basal_body_temp: Optional[MetricValue]


class HardwareSnapshot(StrictModel):
    heart_rate_bpm: Optional[float]
    spo2_percent: Optional[float]
    received_at: datetime


class WeeklyOverview(StrictModel):
    recorded_days: int = Field(ge=0, le=7)
    hot_flash_count: int = Field(ge=0)
    hot_flash_change_percent: Optional[float]
    average_sleep_hours: Optional[float] = Field(default=None, ge=0)
    sleep_change_percent: Optional[float]


class TrendsReport(StrictModel):
    anchor_date: date
    hardware: Optional[HardwareSnapshot]
    self_reported: SelfReportedPanel
    weekly: WeeklyOverview
