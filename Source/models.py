"""신문 파이프라인 데이터 모델."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class RawMail:
    """Gmail 에서 가져온 원본 메일 한 통."""

    uid: str
    subject: str
    sender: str
    received_at: datetime
    text: str
    html: str
    urls: list[str] = field(default_factory=list)


@dataclass
class Article:
    """수집·크롤링을 마친 기사 한 건."""

    title: str
    body: str
    url: str = ""
    image_url: str = ""
    source_name: str = ""
    published_at: datetime | None = None
    is_sns: bool = False
    # "structured"(메일 본문/신문 기사 그대로) 또는 "crawled"(링크 크롤링)
    kind: str = "crawled"
    original_body: str = ""  # SNS 번역 전 원문
    mention_count: int = 1  # 중복 병합된 건수 = 그날 언급 횟수
    mail_subject: str = ""


@dataclass
class CuratedArticle:
    """편집(분류·요약)을 마친 기사."""

    article: Article
    category: str
    summary: str
    importance: int = 0


@dataclass
class Newspaper:
    title: str
    publisher: str
    edition: str
    edition_date: date
    generated_at: datetime
    main: CuratedArticle | None
    subs: list[CuratedArticle]
    sections: list[tuple[str, list[CuratedArticle]]]  # (카테고리, 기사 목록)
    article_count: int = 0
    window_label: str = ""
