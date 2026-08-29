"""One synchronous GLM-ASR request for one real WAV recording."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.services.asr_settings import ASRSettings


class SpeechToTextRequestError(RuntimeError):
    pass


def validate_transcript(text: object) -> str:
    if not isinstance(text, str):
        raise SpeechToTextRequestError("speech-to-text response is missing text")
    transcript = text.strip()
    if not transcript:
        raise SpeechToTextRequestError("speech-to-text response text is empty")
    if not any(character.isalnum() for character in transcript):
        raise SpeechToTextRequestError(
            "speech-to-text response has no lexical text"
        )
    return transcript


def _multipart_body(wav_bytes: bytes, model: str) -> tuple[bytes, str]:
    boundary = "----youjikexun-asr-boundary"
    body = bytearray()

    def append_text_field(name: str, value: str) -> None:
        body.extend(f"--{boundary}\r\n".encode("ascii"))
        body.extend(
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(
                "ascii"
            )
        )
        body.extend(value.encode("utf-8"))
        body.extend(b"\r\n")

    append_text_field("model", model)
    body.extend(f"--{boundary}\r\n".encode("ascii"))
    body.extend(
        b'Content-Disposition: form-data; name="file"; filename="voice.wav"\r\n'
    )
    body.extend(b"Content-Type: audio/wav\r\n\r\n")
    body.extend(wav_bytes)
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode("ascii"))
    return bytes(body), boundary


class ZhipuSpeechToTextAdapter:
    def __init__(self, settings: ASRSettings):
        self.settings = settings

    def transcribe_wav(self, wav_bytes: bytes) -> str:
        body, boundary = _multipart_body(wav_bytes, self.settings.model)
        request = Request(
            url=f"{self.settings.base_url.rstrip('/')}/audio/transcriptions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.settings.api_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                # Mirrors the LLM adapter: Cloudflare-protected gateways
                # reject urllib's default "Python-urllib" signature (1010).
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"
                ),
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=30) as response:
                response_json = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise SpeechToTextRequestError(
                f"speech-to-text service returned HTTP {error.code}"
            ) from error
        except URLError as error:
            raise SpeechToTextRequestError(
                f"speech-to-text request failed: {error.reason}"
            ) from error
        except json.JSONDecodeError as error:
            raise SpeechToTextRequestError(
                "speech-to-text response is not valid JSON"
            ) from error

        return validate_transcript(response_json.get("text"))
