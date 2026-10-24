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
    received_at: datetime | None = None  # 메일 수신 시각 (도착 시간대 통계용)


@dataclass
class CuratedArticle:
    """편집(분류·요약)을 마친 기사."""

    article: Article
    category: str
    summary: str
    importance: int = 0
    keywords: list[str] = field(default_factory=list)
    why: str = ""  # 왜 중요한가 (한 문장)
    reading_min: int = 1  # 원문 예상 읽기 시간(분)
    uid: str = ""  # 페이지 안 앵커/읽음 표시용 식별자


@dataclass
class Weather:
    city: str
    emoji: str
    text: str
    temp: float
    t_max: float
    t_min: float


@dataclass
class Stat:
    label: str
    value: int
    color: str = ""


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
    # ── 부가 지면 ──
    tagline: str = ""
    issue_no: int = 1
    schedule_label: str = ""
    briefing: list[str] = field(default_factory=list)  # 오늘의 3줄 브리핑
    editor_note: str = ""  # 편집장 한마디
    numbers: list[tuple[str, str]] = field(default_factory=list)  # 숫자로 보는 오늘 (값, 설명)
    keywords: list[tuple[str, int]] = field(default_factory=list)  # 오늘의 키워드 (단어, 빈도)
    weather: Weather | None = None
    category_stats: list[Stat] = field(default_factory=list)
    arrival_hist: list[int] = field(default_factory=list)  # 0~23시 메일 도착 건수
    source_count: int = 0
    total_reading_min: int = 0
    sns_count: int = 0
    weekly: list[dict] = field(default_factory=list)  # 이번 주 1면 모아보기
    prev_edition: str = ""  # 파일명
    next_edition: str = ""
    site_url: str = ""
    qr_svg: str = ""
    category_colors: dict[str, str] = field(default_factory=dict)
    llm_used: bool = False
