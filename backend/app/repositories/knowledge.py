from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from app.models.knowledge import KnowledgeChunk, RAGStatus


DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "knowledge_chunks.jsonl"


class KnowledgeBaseUnavailable(RuntimeError):
    pass


class KnowledgeDataError(RuntimeError):
    pass


class KnowledgeRepository:
    """Reads reviewed knowledge supplied by the product team without mutation."""

    @staticmethod
    def all() -> tuple[KnowledgeChunk, ...]:
        if not DATA_PATH.exists():
            raise KnowledgeBaseUnavailable(
                "knowledge_chunks.jsonl is not loaded; add approved chunks before retrieval"
            )

        chunks: list[KnowledgeChunk] = []
        chunk_ids: set[str] = set()
        for line_number, line in enumerate(
            DATA_PATH.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                raise KnowledgeDataError(
                    f"knowledge_chunks.jsonl line {line_number} is empty"
                )
            try:
                chunk = KnowledgeChunk.model_validate_json(line)
            except ValidationError as error:
                raise KnowledgeDataError(
                    f"knowledge_chunks.jsonl line {line_number} is invalid: {error}"
                ) from error
            if chunk.chunk_id in chunk_ids:
                raise KnowledgeDataError(
                    f"knowledge_chunks.jsonl duplicates chunk_id: {chunk.chunk_id}"
                )
            chunk_ids.add(chunk.chunk_id)
            chunks.append(chunk)
        return tuple(chunks)

    @classmethod
    def approved(cls) -> tuple[KnowledgeChunk, ...]:
        return tuple(chunk for chunk in cls.all() if chunk.review_status == "approved")

    @classmethod
    def status(cls) -> RAGStatus:
        if not DATA_PATH.exists():
            return RAGStatus(
                status="not_loaded",
                total_chunk_count=0,
                approved_chunk_count=0,
            )

        chunks = cls.all()
        approved_count = sum(chunk.review_status == "approved" for chunk in chunks)
        if approved_count == 0:
            return RAGStatus(
                status="loaded_no_approved_chunks",
                total_chunk_count=len(chunks),
                approved_chunk_count=0,
            )
        return RAGStatus(
            status="ready",
            total_chunk_count=len(chunks),
            approved_chunk_count=approved_count,
        )
