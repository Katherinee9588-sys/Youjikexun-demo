from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.api import routes
from app.repositories import entries as entries_module
from app.repositories import hardware as hardware_module
from app.services.asr_settings import ASRSettings
from app.services.companion_policy import COMPANION_SYSTEM_PROMPT, CompanionOutput
from app.services.journal_projection import legacy_ledger


client = TestClient(app)


@pytest.fixture
def legacy_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Isolate the read endpoints from demo writes in data/user_entries.jsonl."""
    monkeypatch.setattr(entries_module, "DATA_PATH", tmp_path / "user_entries.jsonl")


def test_overview_preserves_source_dates(
    legacy_only: None,
) -> None:
    response = client.get("/api/overview")
    assert response.status_code == 200
    payload = response.json()

    assert payload["data_origin"] == "real"
    assert payload["entry_count"] == 11
    assert payload["recorded_day_count"] == 11
    assert payload["first_date"] == "2026-08-19"
    assert payload["last_date"] == "2026-08-30"
    assert payload["calendar_span_days"] == 12
    assert payload["missing_calendar_days"] == 1


def test_sleep_score_is_recorded_and_comparable() -> None:
    entry = next(
        item for item in legacy_ledger() if item.record_date.isoformat() == "2026-08-19"
    )
    sleep = entry.lifestyle.sleep

    assert sleep.recorded is True
    assert sleep.raw_value == 7
    assert sleep.raw_scale == 10
    assert sleep.normalized_1_10 == 7
    assert sleep.comparable is True


def test_scene_summaries_only_report_keyword_evidence() -> None:
    response = client.get("/api/overview")
    summaries = response.json()["scene_summaries"]

    assert [item["id"] for item in summaries] == [
        "joint_pain",
        "menstrual",
        "emotion",
    ]
    assert all("不判断症状" in item["boundary"] for item in summaries)


def test_unknown_ledger_id_is_explicit() -> None:
    response = client.get("/api/ledger/does-not-exist")
    assert response.status_code == 404
    assert response.json()["detail"] == "Ledger entry does not exist"


def test_new_entry_is_appended_without_fake_ai_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_path = tmp_path / "user_entries.jsonl"
    monkeypatch.setattr(entries_module, "DATA_PATH", data_path)

    response = client.post(
        "/api/entries",
        json={
            "record_date": "2026-08-28",
            "original_text": "今天下午有点烦躁，先把感受记下来。",
            "input_method": "text",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["source"] == "user_entry"
    assert payload["extraction_status"] == "pending"
    assert payload["ai_content"]["ai_daily_summary"] is None
    assert data_path.read_text(encoding="utf-8").count("\n") == 1


def test_voice_transcription_uses_asr_without_storing_audio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = ASRSettings(
        api_key="test-key",
        base_url="https://asr.example.test/v1",
        model="glm-asr",
    )
    monkeypatch.setattr(routes.ASRSettings, "from_environment", lambda: settings)
    monkeypatch.setattr(
        routes.ZhipuSpeechToTextAdapter,
        "transcribe_wav",
        lambda _adapter, audio: "今天下午有些烦躁。",
    )

    response = client.post(
        "/api/voice/transcriptions",
        content=b"RIFF" + b"0" * 64,
        headers={"content-type": "audio/wav"},
    )

    assert response.status_code == 200
    assert response.json() == {"text": "今天下午有些烦躁。"}


def test_companion_output_enforces_three_safe_sentences() -> None:
    output = CompanionOutput(
        empathy="你愿意记录今天的变化很不容易。",
        suggestion="今晚可以早点休息并观察感受。",
        outlook="慢慢积累后会更熟悉身体节奏。",
    )
    assert output.as_text().count("\n") == 2

    for unsafe_suggestion in (
        "这个方法可以治疗你的不适。",
        "今晚可以按时用药并早点休息。",
    ):
        with pytest.raises(ValidationError):
            CompanionOutput(
                empathy="你愿意认真记录真的很好。",
                suggestion=unsafe_suggestion,
                outlook="慢慢积累后会更熟悉身体节奏。",
            )


def test_medical_boundary_is_intent_based_and_uses_valid_gentle_copy() -> None:
    assert "不要因为用户原文出现一个医疗词就拒答" in COMPANION_SYSTEM_PROMPT
    assert "记录或描述症状、转述既往说法、表达担心或记录变化" in COMPANION_SYSTEM_PROMPT
    assert "明确索要诊断、病因、治疗方案、用药建议、处方" in COMPANION_SYSTEM_PROMPT

    boundary_output = CompanionOutput(
        empathy="我理解你想弄清这次变化。",
        suggestion="这部分请带记录到线下门诊咨询医生。",
        outlook="我们可以先继续记录变化和当时情境。",
    )
    assert boundary_output.as_text().count("\n") == 2


def test_daily_summaries_returns_three_most_recent_recorded_days(
    legacy_only: None,
) -> None:
    response = client.get("/api/daily-summaries")

    assert response.status_code == 200
    cards = response.json()
    assert [card["record_date"] for card in cards] == [
        "2026-08-30",
        "2026-08-29",
        "2026-08-28",
    ]

    latest = cards[0]
    assert latest["entry_count"] == 1
    assert len(latest["tags"]) <= 3
    assert len(latest["copy_lines"]) in (0, 2)
    assert len(latest["recommend"]) <= 1
    assert len(latest["avoid"]) <= 1


def test_daily_summary_scene_card_uses_preset_copy(
    legacy_only: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_path = tmp_path / "user_entries.jsonl"
    monkeypatch.setattr(entries_module, "DATA_PATH", data_path)

    response = client.post(
        "/api/entries",
        json={
            "record_date": "2026-08-31",
            "original_text": "今天早上起床膝盖僵硬酸痛，持续了10分钟。",
            "input_method": "text",
        },
    )
    assert response.status_code == 201

    cards = client.get("/api/daily-summaries").json()
    assert cards[0]["record_date"] == "2026-08-31"
    assert "关节不适" in cards[0]["tags"]
    assert cards[0]["copy_lines"][0] == "你已经把模糊的不适，变成了清晰的记录。"


def test_trends_report_is_deterministic_and_keeps_missing_data_missing(
    legacy_only: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        hardware_module, "DATA_PATH", tmp_path / "hardware_max30102.jsonl"
    )

    response = client.get("/api/trends")

    assert response.status_code == 200
    payload = response.json()

    assert payload["anchor_date"] == "2026-08-30"
    hardware = payload["hardware"]
    assert hardware is not None
    assert 60 <= hardware["heart_rate_bpm"] <= 90
    assert 94 <= hardware["spo2_percent"] <= 100

    self_reported = payload["self_reported"]
    assert self_reported["body_weight"] == {"date": "2026-08-30", "text": "55.3 kg"}
    assert self_reported["blood_pressure"] == {
        "date": "2026-08-30",
        "text": "118/76 mmHg",
    }
    assert self_reported["basal_body_temp"] == {"date": "2026-08-30", "text": "36.7 ℃"}

    weekly = payload["weekly"]
    assert weekly["recorded_days"] == 7
    assert weekly["hot_flash_count"] == 1
    assert weekly["average_sleep_hours"] == 7.4
    assert weekly["sleep_change_percent"] == -1


def test_trends_hardware_panel_uses_latest_valid_sample(
    legacy_only: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    hardware_path = tmp_path / "hardware_max30102.jsonl"
    monkeypatch.setattr(hardware_module, "DATA_PATH", hardware_path)

    create = client.post(
        "/api/hardware/max30102/readings",
        json={
            "schema_version": 1,
            "device_id": "esp32-test",
            "sequence": 1,
            "device_uptime_ms": 1000,
            "ir_value": 120000,
            "finger_present": True,
            "heart_rate_bpm": 72.0,
            "spo2_percent": 98.0,
            "signal_quality": "valid",
        },
    )
    assert create.status_code == 201

    payload = client.get("/api/trends").json()
    assert payload["hardware"]["heart_rate_bpm"] == 72.0
    assert payload["hardware"]["spo2_percent"] == 98.0
