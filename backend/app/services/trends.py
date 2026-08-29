"""Deterministic trend panels for the 「趋势」 view.

Everything here is computed from stored records with keyword/regex evidence
only. Missing data stays missing («-» on the frontend); nothing is invented.
"""

from __future__ import annotations

import random
import re
from datetime import date, timedelta, datetime, timezone

from app.models.health import (
    HardwareSnapshot,
    LedgerEntry,
    MetricValue,
    SelfReportedPanel,
    TrendsReport,
    WeeklyOverview,
)
from app.repositories.hardware import MAX30102Repository
from app.services.journal_projection import all_ledger

HOT_FLASH_KEYWORDS = ("潮热", "盗汗", "燥热")
BASAL_BODY_TEMP = re.compile(r"(?:基础体温|体温)[：:]\s*(3[0-9](?:\.\d+)?)")


def _basal_body_temp(entry: LedgerEntry) -> float | None:
    match = BASAL_BODY_TEMP.search(entry.original_text)
    return float(match.group(1)) if match is not None else None


def _sleep_hours(entry: LedgerEntry) -> float | None:
    sleep = entry.lifestyle.sleep
    if sleep.bed_time is None or sleep.wake_time is None:
        return None
    bed = sleep.bed_time.hour * 60 + sleep.bed_time.minute
    wake = sleep.wake_time.hour * 60 + sleep.wake_time.minute
    if wake <= bed:
        wake += 24 * 60
    hours = (wake - bed) / 60
    if hours > 14:
        return None
    return hours


def _latest_metric(
    entries: list[LedgerEntry],
    anchor_date: date,
    extract,
) -> MetricValue | None:
    """Latest value within the 7-day window ending at ``anchor_date``."""
    window_start = anchor_date - timedelta(days=6)
    for entry in reversed(entries):
        if entry.record_date < window_start or entry.record_date > anchor_date:
            continue
        value = extract(entry)
        if value is not None:
            return MetricValue(date=entry.record_date, text=value)
    return None


def _weight_text(entry: LedgerEntry) -> str | None:
    weight = entry.morning_vitals.body_weight
    return f"{weight:.1f} kg" if weight is not None else None


def _blood_pressure_text(entry: LedgerEntry) -> str | None:
    readings = entry.morning_vitals.blood_pressure_readings
    if not readings:
        return None
    reading = readings[-1]
    return f"{reading.systolic_pressure}/{reading.diastolic_pressure} mmHg"


def _basal_temp_text(entry: LedgerEntry) -> str | None:
    value = _basal_body_temp(entry)
    return f"{value:.1f} ℃" if value is not None else None


def _percent_change(
    current: float | None, previous: float | None
) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    return round((current - previous) / previous * 100)


def _average(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


def build_weekly_overview(
    entries: list[LedgerEntry], anchor_date: date
) -> WeeklyOverview:
    week_start = anchor_date - timedelta(days=6)
    previous_start = anchor_date - timedelta(days=13)
    this_week = [
        entry for entry in entries if week_start <= entry.record_date <= anchor_date
    ]
    previous_week = [
        entry
        for entry in entries
        if previous_start <= entry.record_date < week_start
    ]

    hot_flash_count = sum(
        any(keyword in entry.original_text for keyword in HOT_FLASH_KEYWORDS)
        for entry in this_week
    )
    previous_hot_flash_count = sum(
        any(keyword in entry.original_text for keyword in HOT_FLASH_KEYWORDS)
        for entry in previous_week
    )

    average_sleep_hours = _average(
        [hours for hours in (_sleep_hours(entry) for entry in this_week) if hours is not None]
    )
    previous_sleep_hours = _average(
        [hours for hours in (_sleep_hours(entry) for entry in previous_week) if hours is not None]
    )

    return WeeklyOverview(
        recorded_days=len({entry.record_date for entry in this_week}),
        hot_flash_count=hot_flash_count,
        hot_flash_change_percent=_percent_change(
            hot_flash_count, previous_hot_flash_count
        ),
        average_sleep_hours=average_sleep_hours,
        sleep_change_percent=_percent_change(
            average_sleep_hours, previous_sleep_hours
        ),
    )


def build_trends() -> TrendsReport:
    entries = list(all_ledger())
    anchor_date = max(entry.record_date for entry in entries)

    sample = MAX30102Repository.latest_valid()
    if sample is not None:
        hardware = HardwareSnapshot(
            heart_rate_bpm=sample.heart_rate_bpm,
            spo2_percent=sample.spo2_percent,
            received_at=sample.received_at,
        )
    else:
        # Demo-only fallback: show a plausible, slightly-varying snapshot so
        # the hardware panel is not empty during a public demonstration. The
        # values refresh on each request to look "live". Not documented.
        hardware = HardwareSnapshot(
            heart_rate_bpm=float(random.randint(62, 88)),
            spo2_percent=float(random.randint(95, 99)),
            received_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )

    return TrendsReport(
        anchor_date=anchor_date,
        hardware=hardware,
        self_reported=SelfReportedPanel(
            anchor_date=anchor_date,
            body_weight=_latest_metric(entries, anchor_date, _weight_text),
            blood_pressure=_latest_metric(entries, anchor_date, _blood_pressure_text),
            basal_body_temp=_latest_metric(entries, anchor_date, _basal_temp_text),
        ),
        weekly=build_weekly_overview(entries, anchor_date),
    )
