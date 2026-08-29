from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv


ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(ENV_PATH, override=True)


class ASRConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ASRSettings:
    api_key: str
    base_url: str
    model: str

    @classmethod
    def from_environment(cls) -> "ASRSettings":
        api_key = os.getenv("ASR_API_KEY")
        base_url = os.getenv("ASR_BASE_URL")
        model = os.getenv("ASR_MODEL")
        missing = [
            name
            for name, value in (
                ("ASR_API_KEY", api_key),
                ("ASR_BASE_URL", base_url),
                ("ASR_MODEL", model),
            )
            if value is None or value.strip() == ""
        ]
        if missing:
            raise ASRConfigurationError(
                f"missing required ASR settings: {', '.join(missing)}"
            )
        return cls(api_key=api_key, base_url=base_url, model=model)


def asr_status() -> Literal["not_configured", "configuration_error", "configured"]:
    values = (
        os.getenv("ASR_API_KEY"),
        os.getenv("ASR_BASE_URL"),
        os.getenv("ASR_MODEL"),
    )
    if all(value is None or value.strip() == "" for value in values):
        return "not_configured"
    try:
        ASRSettings.from_environment()
    except ASRConfigurationError:
        return "configuration_error"
    return "configured"
