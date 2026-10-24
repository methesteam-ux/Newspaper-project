"""[2단계] SNS 게시물 한글 번역 + 본문을 참조한 짧은 기사 제목 생성."""
from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from llm import Gemini
from models import Article

log = logging.getLogger(__name__)

# "X의 OO 님 게시물", "X에서 OO(@id) 님" 처럼 제목 역할을 못 하는 SNS 기본 제목
_GENERIC_TITLE_RE = re.compile(r"^X(의|에서)\s|님 게시물|님$|on X:|on Instagram|Instagram|TikTok|Threads", re.IGNORECASE)


class SnsLocalized(BaseModel):
    headline: str
    body_ko: str


PROMPT = """너는 한국 신문사의 국제부 기자다. 아래 SNS 게시물을 신문 기사로 옮겨라.

1. body_ko: 게시물 본문 전체를 자연스러운 한국어로 번역한다. 이미 한국어면 그대로 둔다.
   의미를 더하거나 빼지 말고, 문단(줄바꿈)은 유지한다. URL·해시태그 나열은 생략해도 된다.
2. headline: 번역한 본문을 참조해 핵심을 담은 짧은 신문 기사 제목(공백 포함 35자 이내)을 만든다.
   "OO 님 게시물" 같은 형식적 제목은 쓰지 않는다. 예) 메타, '트랜스포머 시대 종말' 논문 공개…AI 판도 바뀔까

[플랫폼] {platform}
[기존 제목] {title}
[본문]
{body}
"""


def _fallback_title(article: Article) -> str:
    first = next((ln.strip() for ln in article.body.splitlines() if len(ln.strip()) > 5), "")
    return (first[:40] + "…") if len(first) > 40 else (first or article.title)


def localize_sns(articles: list[Article], gemini: Gemini | None) -> None:
    """SNS 기사의 본문을 한국어로 번역하고 제목을 새로 만든다 (in-place)."""
    for art in articles:
        if not art.is_sns or not art.body:
            continue
        result = None
        if gemini:
            result = gemini.generate_json(
                PROMPT.format(platform=art.source_name, title=art.title, body=art.body[:5000]),
                SnsLocalized,
            )
        if result and result.body_ko.strip():
            art.original_body = art.body
            art.body = result.body_ko.strip()
            art.title = result.headline.strip() or art.title
            log.info("SNS 번역/헤드라인: %s", art.title)
        elif not art.title or _GENERIC_TITLE_RE.search(art.title):
            art.title = _fallback_title(art)
