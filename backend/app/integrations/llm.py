from typing import Protocol

from app.models.knowledge import KnowledgePassage
from app.services.companion_policy import CompanionOutput


class LanguageModelAdapter(Protocol):
    def generate_companion_output(
        self,
        user_text: str,
        passages: list[KnowledgePassage],
    ) -> CompanionOutput: ...
