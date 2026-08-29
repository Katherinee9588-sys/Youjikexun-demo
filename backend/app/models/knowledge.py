from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import AnyHttpUrl, Field, field_validator

from app.models.health import StrictModel


SceneTag = Literal["menstrual", "joint_pain", "emotion"]
IntentTag = Literal[
    "record",
    "observe",
    "routine",
    "sleep",
    "movement",
    "warmth",
    "emotion",
]
EvidenceType = Literal["guideline", "public_health", "review"]
ReviewStatus = Literal["draft", "approved", "rejected"]


class KnowledgeChunk(StrictModel):
    chunk_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{2,63}$")
    scene_tags: list[SceneTag] = Field(min_length=1, max_length=3)
    intent_tags: list[IntentTag] = Field(min_length=1, max_length=3)
    title: str = Field(min_length=4, max_length=80)
    content: str = Field(min_length=120, max_length=350)
    source_publisher: str = Field(min_length=2, max_length=80)
    source_title: str = Field(min_length=4, max_length=160)
    source_url: AnyHttpUrl
    accessed_at: date
    evidence_type: EvidenceType
    safety_boundary: str = Field(min_length=12, max_length=180)
    review_status: ReviewStatus
    version: str = Field(pattern=r"^\d+\.\d+$")

    @field_validator("scene_tags", "intent_tags")
    @classmethod
    def reject_duplicate_tags(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("knowledge chunk tags must not repeat")
        return value


class KnowledgePassage(StrictModel):
    chunk_id: str
    title: str
    content: str
    source_publisher: str
    source_title: str
    source_url: AnyHttpUrl
    safety_boundary: str
    relevance_score: int = Field(ge=1)
    matched_terms: list[str]


class KnowledgeQuery(StrictModel):
    query: str = Field(min_length=2, max_length=500)
    limit: int = Field(ge=1, le=3)


class KnowledgePreview(StrictModel):
    query: str
    passages: list[KnowledgePassage]


class RAGStatus(StrictModel):
    status: Literal["not_loaded", "loaded_no_approved_chunks", "ready"]
    total_chunk_count: int = Field(ge=0)
    approved_chunk_count: int = Field(ge=0)


class CompanionGenerationRequest(StrictModel):
    user_text: str = Field(min_length=1, max_length=4000)

