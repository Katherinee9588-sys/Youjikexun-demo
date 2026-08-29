from __future__ import annotations

import re
from datetime import time
from functools import lru_cache

from app.models.health import (
    AIContent,
    BloodPressureReading,
    HealthRecord,
    LedgerEntry,
    LifestyleInterventions,
    MealEntry,
    MentalModel,
    MorningVitals,
    PhysicalSignal,
    RecordContext,
    SleepObservation,
    StoredUserEntry,
)
from app.repositories.entries import EntryRepository
from app.repositories.records import RecordRepository
from app.services.exercise_projection import project_exercise


WEIGHT = re.compile(
    r"(?:weight_kg|体重(?:（[^\n：:]*）|\([^\n：:]*\))?)[：:]\s*[^\d\n]{0,18}(\d+(?:\.\d+)?)"
)
BODY_FAT = re.compile(
    r"(?:body_fat_percent|体脂(?:率)?(?:（[^\n：:]*）|\([^\n：:]*\))?)[：:]\s*(\d+(?:[\.。]\d+)?)"
)
NORMALIZED_READING = re.compile(
    r"systolic[：:]\s*(\d{2,3})[^\n]*\n\s*-?\s*diastolic[：:]\s*(\d{2,3})"
    r"(?:[^\n]*\n\s*-?\s*heart_rate[：:]\s*(\d{2,3}))?"
    r"(?:[^\n]*\n\s*-?\s*context[：:]\s*([^\n]+))?"
)
LEGACY_READING = re.compile(
    r"(?<!\d)(\d{2,3})\s*/\s*(\d{2,3})(?:\s+(\d{2,3}))?(?!\d)"
)
SLEEP_SCORE = re.compile(
    r"(?:sleep_score_1_10|睡眠)[：:；;]\s*(\d+(?:\.\d+)?)\s*分?"
)
SLEEP_SCORE_100 = re.compile(r"睡眠[：:；;]\s*(\d+(?:\.\d+)?)\s*/\s*100")
BED_TIME = re.compile(r"bed_time[：:]\s*([01]\d|2[0-3]):([0-5]\d)")
WAKE_TIME = re.compile(r"wake_time[：:]\s*([01]\d|2[0-3]):([0-5]\d)")
SLEEP_INTERRUPTION = re.compile(r"sleep_interruptions[：:]\s*(\d+)")
WEATHER_TEMP = re.compile(r"weather_temp[：:]\s*(-?\d+)")
SPECIAL_STRESS = re.compile(r"special_stress[：:]\s*([^\n]+)")

MEAL_KEYS = {
    "breakfast": "breakfast",
    "早餐": "breakfast",
    "早饭": "breakfast",
    "lunch": "lunch",
    "午餐": "lunch",
    "午饭": "lunch",
    "dinner": "dinner",
    "晚餐": "dinner",
    "晚饭": "dinner",
    "snack": "snack",
    "加餐": "snack",
}


def _first_float(pattern: re.Pattern[str], text: str) -> float | None:
    match = pattern.search(text)
    if match is None:
        return None
    return float(match.group(1).replace("。", "."))


def _clock(match: re.Match[str] | None) -> time | None:
    if match is None:
        return None
    return time(hour=int(match.group(1)), minute=int(match.group(2)))


def _line_containing(text: str, token: str) -> str | None:
    for line in text.splitlines():
        if token in line:
            return line.strip()
    return None


def _field_value(text: str, keys: tuple[str, ...]) -> str | None:
    for line in text.splitlines():
        stripped = line.strip().lstrip("-").strip()
        for key in keys:
            prefix = f"{key}："
            ascii_prefix = f"{key}:"
            if stripped.startswith(prefix):
                value = stripped[len(prefix) :].strip()
                return value if value else None
            if stripped.startswith(ascii_prefix):
                value = stripped[len(ascii_prefix) :].strip()
                return value if value else None
    return None


def _blood_pressure(text: str) -> list[BloodPressureReading]:
    readings: list[BloodPressureReading] = []
    for match in NORMALIZED_READING.finditer(text):
        context = []
        if match.group(4) is not None:
            context = [part.strip() for part in match.group(4).split("，") if part.strip()]
        readings.append(
            BloodPressureReading(
                systolic_pressure=int(match.group(1)),
                diastolic_pressure=int(match.group(2)),
                heart_rate=int(match.group(3)) if match.group(3) is not None else None,
                measurement_context=context,
            )
        )

    if readings:
        return readings

    for line in text.splitlines():
        if "血压" not in line:
            continue
        for match in LEGACY_READING.finditer(line):
            readings.append(
                BloodPressureReading(
                    systolic_pressure=int(match.group(1)),
                    diastolic_pressure=int(match.group(2)),
                    heart_rate=(
                        int(match.group(3)) if match.group(3) is not None else None
                    ),
                    measurement_context=[],
                )
            )
    return readings


def _sleep(text: str) -> SleepObservation:
    score_match = SLEEP_SCORE.search(text)
    explicit_100 = SLEEP_SCORE_100.search(text)
    raw_value: float | None = None
    raw_scale: int | None = None
    normalized: float | None = None
    comparable = False
    notes: list[str] = []

    if explicit_100 is not None:
        raw_value = float(explicit_100.group(1))
        raw_scale = 100
        notes.append("100 分量表保留原值，未转换为 1–10 分")
    elif score_match is not None:
        raw_value = float(score_match.group(1))
        if 1 <= raw_value <= 10:
            raw_scale = 10
            normalized = raw_value
            comparable = True
        else:
            notes.append("睡眠记录有效，但评分量表未确认")

    raw_text = _line_containing(text, "睡眠")
    bed_time = _clock(BED_TIME.search(text))
    wake_time = _clock(WAKE_TIME.search(text))
    interruption_match = SLEEP_INTERRUPTION.search(text)
    interruptions = (
        int(interruption_match.group(1)) if interruption_match is not None else None
    )
    recorded = any(
        value is not None
        for value in (raw_text, raw_value, bed_time, wake_time, interruptions)
    )

    return SleepObservation(
        recorded=recorded,
        raw_text=raw_text,
        raw_value=raw_value,
        raw_scale=raw_scale,
        normalized_1_10=normalized,
        comparable=comparable,
        bed_time=bed_time,
        wake_time=wake_time,
        interruptions=interruptions,
        extraction_notes=notes,
    )


def _meals(text: str) -> list[MealEntry]:
    meals: list[MealEntry] = []
    for line in text.splitlines():
        stripped = line.strip().lstrip("-").strip()
        for key, slot in MEAL_KEYS.items():
            prefixes = (f"{key}：", f"{key}:")
            matched_prefix = next(
                (prefix for prefix in prefixes if stripped.startswith(prefix)), None
            )
            if matched_prefix is None:
                continue
            value = stripped[len(matched_prefix) :].strip()
            if value:
                meals.append(
                    MealEntry(
                        meal_time_slot=slot,
                        meal_raw_text=value,
                        meal_tag=[],
                    )
                )
            break
    return meals


def _physical_signals(text: str) -> list[PhysicalSignal]:
    description = _field_value(text, ("body_signals", "身体信号"))
    if description is None:
        return []
    return [
        PhysicalSignal(
            symptom_location=None,
            symptom_desc=description,
            symptom_trend=None,
            symptom_triggers=None,
        )
    ]


def _project(
    *,
    entry_id: str,
    source: str,
    record_date,
    day_number: int | None,
    created_at,
    original_text: str,
    input_method: str,
    extraction_status: str,
    legacy_feedback,
) -> LedgerEntry:
    exercise = project_exercise(original_text, legacy=source == "legacy_import")

    return LedgerEntry(
        id=entry_id,
        source=source,
        record_date=record_date,
        day_number=day_number,
        created_at=created_at,
        original_text=original_text,
        input_method=input_method,
        extraction_status=extraction_status,
        legacy_feedback=legacy_feedback,
        morning_vitals=MorningVitals(
            record_date=record_date,
            body_weight=_first_float(WEIGHT, original_text),
            body_fat_rate=_first_float(BODY_FAT, original_text),
            blood_pressure_readings=_blood_pressure(original_text),
        ),
        lifestyle=LifestyleInterventions(
            meals=_meals(original_text),
            exercise_type=exercise.exercise_type,
            exercise_duration=exercise.exercise_duration,
            exercise_sets=exercise.exercise_sets,
            exercise_details=exercise.exercise_details,
            exercise_raw_text=exercise.exercise_raw_text,
            sleep=_sleep(original_text),
        ),
        physical_signals=_physical_signals(original_text),
        mental_model=MentalModel(
            today_highlight=_field_value(
                original_text, ("today_highlight", "做对的一件事")
            ),
            tomorrow_one_change=_field_value(
                original_text, ("tomorrow_one_change", "明天只改一件事")
            ),
            execution_resistance=_field_value(
                original_text, ("execution_resistance", "今天最大的执行阻力")
            ),
            user_hypothesis=_field_value(original_text, ("i_assumed", "我以为")),
        ),
        ai_content=AIContent(
            ai_daily_summary=None,
            ai_hypothesis_validation=None,
        ),
        context=RecordContext(
            weather_temp=(
                int(WEATHER_TEMP.search(original_text).group(1))
                if WEATHER_TEMP.search(original_text) is not None
                else None
            ),
            special_stress=_field_value(original_text, ("special_stress",)),
        ),
    )


def project_legacy(record: HealthRecord) -> LedgerEntry:
    return _project(
        entry_id=f"legacy-{record.date.isoformat()}",
        source="legacy_import",
        record_date=record.date,
        day_number=record.day_number,
        created_at=None,
        original_text=record.user_input,
        input_method="import",
        extraction_status="partial",
        legacy_feedback=record.feedback,
    )


def project_user_entry(entry: StoredUserEntry) -> LedgerEntry:
    return _project(
        entry_id=entry.id,
        source="user_entry",
        record_date=entry.record_date,
        day_number=None,
        created_at=entry.created_at,
        original_text=entry.original_text,
        input_method=entry.input_method,
        extraction_status=entry.extraction_status,
        legacy_feedback=None,
    )


@lru_cache(maxsize=1)
def legacy_ledger() -> tuple[LedgerEntry, ...]:
    return tuple(project_legacy(record) for record in RecordRepository.all())


def all_ledger() -> tuple[LedgerEntry, ...]:
    entries = list(legacy_ledger())
    entries.extend(project_user_entry(entry) for entry in EntryRepository.all())
    entries.sort(
        key=lambda item: (
            item.record_date,
            item.created_at.isoformat() if item.created_at is not None else "",
        )
    )
    return tuple(entries)


def ledger_by_id(entry_id: str) -> LedgerEntry | None:
    for entry in all_ledger():
        if entry.id == entry_id:
            return entry
    return None
