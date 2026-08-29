from typing import Protocol

from app.models.knowledge import KnowledgePassage


class KnowledgeRetriever(Protocol):
    def retrieve(self, query: str, limit: int) -> list[KnowledgePassage]: ...
