import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories import knowledge as knowledge_module
from app.services.llm_settings import LLMSettings, language_model_status


client = TestClient(app)


def _chunk(chunk_id: str, review_status: str) -> dict[str, object]:
    return {
        "chunk_id": chunk_id,
        "scene_tags": ["emotion"],
        "intent_tags": ["sleep", "observe"],
        "title": "睡眠与情绪记录的观察方式",
        "content": (
            "当睡眠节奏出现变化并伴随情绪波动时，可以先按实际发生的时间记录入睡、醒来、"
            "白天精力和当下感受。连续记录帮助回看自己的节奏变化，但不用于判断症状原因、"
            "严重程度或替代线下专业评估。记录时不必要求每天完整填写，也不需要把没有发生的"
            "内容补写进去；只保留当下愿意表达、能够确认的信息，之后再结合自己的连续记录回看。"
        ),
        "source_publisher": "测试审核机构",
        "source_title": "睡眠与情绪记录说明",
        "source_url": "https://example.org/sleep-observation",
        "accessed_at": "2026-08-28",
        "evidence_type": "public_health",
        "safety_boundary": "本条只说明记录方法，不判断症状原因或严重程度。",
        "review_status": review_status,
        "version": "1.0",
    }


def _write_chunks(path: Path, chunks: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(chunk, ensure_ascii=False) for chunk in chunks) + "\n",
        encoding="utf-8",
    )


def test_knowledge_status_reports_missing_pack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(knowledge_module, "DATA_PATH", tmp_path / "missing.jsonl")

    response = client.get("/api/knowledge/status")

    assert response.status_code == 200
    assert response.json() == {
        "status": "not_loaded",
        "total_chunk_count": 0,
        "approved_chunk_count": 0,
    }


def test_preview_returns_only_approved_chunks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_path = tmp_path / "knowledge_chunks.jsonl"
    _write_chunks(
        data_path,
        [
            _chunk("approved-sleep-observation", "approved"),
            _chunk("draft-sleep-observation", "draft"),
        ],
    )
    monkeypatch.setattr(knowledge_module, "DATA_PATH", data_path)

    response = client.post(
        "/api/knowledge/preview",
        json={"query": "昨晚睡眠变差，今天想观察情绪和节奏。", "limit": 2},
    )

    assert response.status_code == 200
    passages = response.json()["passages"]
    assert [passage["chunk_id"] for passage in passages] == [
        "approved-sleep-observation"
    ]
    assert "睡眠" in passages[0]["matched_terms"]


def test_preview_exposes_missing_pack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(knowledge_module, "DATA_PATH", tmp_path / "missing.jsonl")

    response = client.post(
        "/api/knowledge/preview",
        json={"query": "今天想观察睡眠变化", "limit": 1},
    )

    assert response.status_code == 409
    assert "not loaded" in response.json()["detail"]


def test_companion_requires_knowledge_before_model_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(knowledge_module, "DATA_PATH", tmp_path / "missing.jsonl")

    response = client.post(
        "/api/companion",
        json={"user_text": "昨晚睡眠不稳，今天有点烦躁。"},
    )

    assert response.status_code == 409
    assert "not loaded" in response.json()["detail"]


def test_llm_configuration_state_requires_all_three_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)
    assert language_model_status() == "not_configured"

    monkeypatch.setenv("LLM_API_KEY", "test-key")
    assert language_model_status() == "configuration_error"

    monkeypatch.setenv("LLM_BASE_URL", "https://llm.example/v1")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    settings = LLMSettings.from_environment()
    assert settings.api_key == "test-key"
    assert settings.base_url == "https://llm.example/v1"
    assert settings.model == "test-model"
    assert language_model_status() == "configured"
