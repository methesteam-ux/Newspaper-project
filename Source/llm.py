"""[2단계] Gemini API 공통 클라이언트 — 스키마 고정 JSON 응답 + 재시도."""
from __future__ import annotations

import logging
import time
from typing import TypeVar

from pydantic import BaseModel

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class Gemini:
    def __init__(self, api_key: str, model: str):
        from google import genai

        self.client = genai.Client(api_key=api_key)
        self.model = model

    def generate_json(self, prompt: str, schema: type[T], retries: int = 2) -> T | None:
        from google.genai import types

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0.3,
        )
        for attempt in range(retries + 1):
            try:
                resp = self.client.models.generate_content(model=self.model, contents=prompt, config=config)
                if isinstance(resp.parsed, schema):
                    return resp.parsed
                return schema.model_validate_json(resp.text or "")
            except Exception as exc:
                log.warning("Gemini 호출 실패 (%d/%d): %s", attempt + 1, retries + 1, exc)
                if attempt < retries:
                    time.sleep(3 * (attempt + 1))
        return None


def make_gemini(api_key: str, model: str) -> Gemini | None:
    if not api_key:
        log.info("GEMINI_API_KEY 가 비어 있어 규칙 기반 편집으로 진행합니다.")
        return None
    try:
        return Gemini(api_key, model)
    except Exception as exc:
        log.warning("Gemini 클라이언트 생성 실패, 규칙 기반 편집으로 진행합니다: %s", exc)
        return None
