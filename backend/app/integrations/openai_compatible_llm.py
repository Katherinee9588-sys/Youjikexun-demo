from __future__ import annotations

import json
import socket
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import ValidationError

from app.models.knowledge import KnowledgePassage
from app.services.companion_policy import COMPANION_SYSTEM_PROMPT, CompanionOutput
from app.services.llm_settings import LLMSettings


class LanguageModelRequestError(RuntimeError):
    pass


def _knowledge_context(passages: list[KnowledgePassage]) -> str:
    blocks = []
    for passage in passages:
        blocks.append(
            "\n".join(
                (
                    f"标题：{passage.title}",
                    f"内容：{passage.content}",
                    f"边界：{passage.safety_boundary}",
                    f"来源：{passage.source_publisher}｜{passage.source_title}",
                )
            )
        )
    return "\n\n---\n\n".join(blocks)


class OpenAICompatibleLanguageModelAdapter:
    """Calls an OpenAI-compatible chat endpoint after RAG retrieval succeeds."""

    def __init__(self, settings: LLMSettings):
        self.settings = settings

    def generate_companion_output(
        self,
        user_text: str,
        passages: list[KnowledgePassage],
    ) -> CompanionOutput:
        # Non-reasoning chat models occasionally return a fenced/over-length
        # reply on the first attempt. Retry once with a stricter instruction
        # before surfacing an error, so the user rarely sees the generic fallback.
        for attempt in range(2):
            try:
                return self._call_once(user_text, passages, reinforce=attempt > 0)
            except (LanguageModelRequestError, ValidationError):
                if attempt == 1:
                    raise

    def _call_once(
        self,
        user_text: str,
        passages: list[KnowledgePassage],
        reinforce: bool,
    ) -> CompanionOutput:
        context = _knowledge_context(passages)
        user_content = (
            f"用户原始记录：\n{user_text}\n\n"
            f"已审核知识：\n{context}"
        )
        if reinforce:
            user_content += (
                "\n\n注意：上一轮输出不符合格式。请只输出纯 JSON（不要 markdown 代码块），"
                "三个字段 empathy/suggestion/outlook，每句 8-25 个汉字，以句号结尾。"
            )
        payload = {
            "model": self.settings.model,
            "temperature": 0.2,
            "max_tokens": 2048,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        f"{COMPANION_SYSTEM_PROMPT}\n"
                        "只能依据下方已审核知识回答；没有依据时不得补充事实。"
                    ),
                },
                {
                    "role": "user",
                    "content": user_content,
                },
            ],
        }
        request = Request(
            url=f"{self.settings.base_url.rstrip('/')}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.settings.api_key}",
                "Content-Type": "application/json",
                # Some OpenAI-compatible gateways sit behind Cloudflare and
                # reject urllib's default "Python-urllib" signature with
                # HTTP 403 / Cloudflare error 1010. A browser-like UA passes.
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"
                ),
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=60) as response:
                payload_json = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise LanguageModelRequestError(
                f"language model returned HTTP {error.code}"
            ) from error
        except URLError as error:
            raise LanguageModelRequestError(
                f"language model request failed: {error.reason}"
            ) from error
        except (socket.timeout, TimeoutError) as error:
            # Reasoning models (e.g. glm-5.x) sometimes exceed the connect/read
            # budget. urllib raises a bare socket.timeout that is NOT a URLError,
            # so without this clause FastAPI returns a raw 500. Surface it as a
            # clean 502 so the frontend can show the real reason.
            raise LanguageModelRequestError(
                "language model request timed out, please retry"
            ) from error
        except json.JSONDecodeError as error:
            raise LanguageModelRequestError(
                "language model response is not valid JSON"
            ) from error

        try:
            content = payload_json["choices"][0]["message"]["content"]
        except (IndexError, KeyError, TypeError) as error:
            raise LanguageModelRequestError(
                "language model response is missing choices[0].message.content"
            ) from error
        if not isinstance(content, str):
            raise LanguageModelRequestError("language model content is not text")
        # Some chat models (e.g. glm-4-flash) wrap JSON in a markdown fence
        # like ```json ... ```; strip it so json.loads can parse the payload.
        text = content.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().endswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        try:
            output_json = json.loads(text)
        except json.JSONDecodeError as error:
            raise LanguageModelRequestError(
                "language model did not return valid JSON"
            ) from error
        return CompanionOutput.model_validate(output_json)
