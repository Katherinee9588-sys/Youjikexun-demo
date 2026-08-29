from app.models.health import AppOverview, IntegrationStatus, MetricCoverage
from app.repositories.knowledge import KnowledgeRepository
from app.services.asr_settings import asr_status
from app.services.journal_projection import all_ledger
from app.services.llm_settings import language_model_status
from app.services.scene_summary import build_scene_summaries


def integration_status() -> IntegrationStatus:
    rag_status = KnowledgeRepository.status()
    return IntegrationStatus(
        voice_transcription=asr_status(),
        language_model=language_model_status(),
        hardware_adapter="interface_ready_not_configured",
        rag_retriever=rag_status.status,
    )


def build_overview() -> AppOverview:
    entries = all_ledger()
    dates = sorted({entry.record_date for entry in entries})
    first_date = dates[0]
    last_date = dates[-1]
    calendar_span_days = (last_date - first_date).days + 1

    coverage = MetricCoverage(
        body_weight=sum(
            entry.morning_vitals.body_weight is not None for entry in entries
        ),
        body_fat_rate=sum(
            entry.morning_vitals.body_fat_rate is not None for entry in entries
        ),
        blood_pressure=sum(
            bool(entry.morning_vitals.blood_pressure_readings) for entry in entries
        ),
        heart_rate=sum(
            any(
                reading.heart_rate is not None
                for reading in entry.morning_vitals.blood_pressure_readings
            )
            for entry in entries
        ),
        sleep_record=sum(entry.lifestyle.sleep.recorded for entry in entries),
        comparable_sleep_score=sum(
            entry.lifestyle.sleep.comparable for entry in entries
        ),
    )

    return AppOverview(
        data_origin="real",
        profile_display_name="Amy",
        entry_count=len(entries),
        recorded_day_count=len(dates),
        first_date=first_date,
        last_date=last_date,
        calendar_span_days=calendar_span_days,
        missing_calendar_days=calendar_span_days - len(dates),
        metric_coverage=coverage,
        latest_entry=entries[-1],
        recent_entries=list(reversed(entries[-6:])),
        scene_summaries=build_scene_summaries(entries),
        integrations=integration_status(),
    )
