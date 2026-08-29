from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv


ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(ENV_PATH, override=True)


class LLMConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMSettings:
    api_key: str
    base_url: str
    model: str

    @classmethod
    def from_environment(cls) -> "LLMSettings":
        api_key = os.getenv("LLM_API_KEY")
        base_url = os.getenv("LLM_BASE_URL")
        model = os.getenv("LLM_MODEL")
        missing = [
            name
            for name, value in (
                ("LLM_API_KEY", api_key),
                ("LLM_BASE_URL", base_url),
                ("LLM_MODEL", model),
            )
            if value is None or value.strip() == ""
        ]
        if missing:
            raise LLMConfigurationError(
                f"missing required LLM settings: {', '.join(missing)}"
            )
        return cls(
            api_key=api_key,
            base_url=base_url,
            model=model,
        )


def language_model_status() -> Literal[
    "not_configured", "configuration_error", "configured"
]:
    values = (
        os.getenv("LLM_API_KEY"),
        os.getenv("LLM_BASE_URL"),
        os.getenv("LLM_MODEL"),
    )
    if all(value is None or value.strip() == "" for value in values):
        return "not_configured"
    try:
        LLMSettings.from_environment()
    except LLMConfigurationError:
        return "configuration_error"
    return "configured"
