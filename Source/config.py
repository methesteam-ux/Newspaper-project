"""설정 로딩, 발행 요일, 수집 시간대(직전 발행일 08:00 ~ 발행일 08:00, KST) 계산."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
SOURCE_DIR = BASE_DIR / "Source"
OUTPUT_DIR = BASE_DIR / "Output"
TEMPLATE_DIR = SOURCE_DIR / "templates"

KST = ZoneInfo("Asia/Seoul")

# .env 가 없어도(GitHub Actions 등) 환경 변수만으로 동작한다.
load_dotenv(BASE_DIR / ".env")


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name, "").strip()
    return value or default


DAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_NAMES_KO = "월화수목금토일"
DEFAULT_PUBLISH_DAYS = "mon-fri"


def parse_publish_days(text: str) -> tuple[int, ...]:
    """'mon-fri', 'mon,wed,fri', 'daily', '월-금' 등을 요일 번호(월=0 … 일=6) 튜플로."""
    text = (text or DEFAULT_PUBLISH_DAYS).strip().lower()
    if text in ("daily", "everyday", "매일", "all"):
        return tuple(range(7))

    def to_num(token: str) -> int:
        token = token.strip()
        if token[:3] in DAY_NAMES:
            return DAY_NAMES.index(token[:3])
        if token[:1] and token[:1] in DAY_NAMES_KO:
            return DAY_NAMES_KO.index(token[:1])
        raise ValueError(f"PUBLISH_DAYS 를 해석할 수 없습니다: {token!r}")

    days: set[int] = set()
    for part in re.split(r"[,\s]+", text):
        if not part:
            continue
        if "-" in part or "~" in part:
            a, b = (to_num(x) for x in re.split(r"[-~]", part, maxsplit=1))
            days.update((a + i) % 7 for i in range((b - a) % 7 + 1))
        else:
            days.add(to_num(part))
    if not days:
        raise ValueError("PUBLISH_DAYS 가 비어 있습니다.")
    return tuple(sorted(days))


def describe_days(days: tuple[int, ...]) -> str:
    if len(days) == 7:
        return "매일"
    if days == (0, 1, 2, 3, 4):
        return "월~금"
    return ",".join(DAY_NAMES_KO[d] for d in days)


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    gemini_model: str
    gmail_user: str
    gmail_app_password: str
    gmail_label: str
    imap_server: str
    imap_port: int
    newspaper_title: str
    publisher_name: str
    edition_name: str
    publish_hour: int
    publish_days: tuple[int, ...] = (0, 1, 2, 3, 4)
    tagline: str = ""
    weather_enabled: bool = True
    weather_city: str = "서울"
    weather_lat: float = 37.5665
    weather_lon: float = 126.9780
    site_url: str = ""
    newsletter_enabled: bool = False
    newsletter_to: str = ""

    @property
    def has_gmail(self) -> bool:
        return bool(self.gmail_user and self.gmail_app_password)

    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key)


def load_settings() -> Settings:
    return Settings(
        gemini_api_key=_env("GEMINI_API_KEY"),
        gemini_model=_env("GEMINI_MODEL", "gemini-flash-latest"),
        gmail_user=_env("GMAIL_USER"),
        # 앱 비밀번호는 "abcd efgh ijkl mnop"처럼 공백 포함으로 복사되는 경우가 많다.
        gmail_app_password=_env("GMAIL_APP_PASSWORD").replace(" ", ""),
        gmail_label=_env("GMAIL_LABEL", "News"),
        imap_server=_env("GMAIL_IMAP_SERVER", "imap.gmail.com"),
        imap_port=int(_env("GMAIL_IMAP_PORT", "993")),
        newspaper_title=_env("NEWSPAPER_TITLE", "My Tech Daily"),
        publisher_name=_env("PUBLISHER_NAME", "Publisher"),
        edition_name=_env("EDITION_NAME", "My 에디션"),
        publish_hour=int(_env("PUBLISH_HOUR", "8")),
        publish_days=parse_publish_days(_env("PUBLISH_DAYS", DEFAULT_PUBLISH_DAYS)),
        tagline=_env("TAGLINE", "AI 편집장이 고른 오늘의 테크 뉴스"),
        weather_enabled=_flag("WEATHER_ENABLED", True),
        weather_city=_env("WEATHER_CITY", "서울"),
        weather_lat=float(_env("WEATHER_LAT", "37.5665")),
        weather_lon=float(_env("WEATHER_LON", "126.9780")),
        site_url=detect_site_url(),
        newsletter_enabled=_flag("NEWSLETTER_ENABLED", False),
        newsletter_to=_env("NEWSLETTER_TO"),
    )


def _flag(name: str, default: bool) -> bool:
    value = _env(name).lower()
    if not value:
        return default
    return value in ("1", "true", "yes", "on", "y")


def detect_site_url() -> str:
    """GitHub Pages 주소: SITE_URL > GitHub Actions 저장소 > 로컬 git origin 순으로 찾는다."""
    explicit = _env("SITE_URL")
    if explicit:
        return explicit.rstrip("/") + "/"
    repo = _env("GITHUB_REPOSITORY")
    if not repo:
        git_config = BASE_DIR / ".git" / "config"
        if git_config.exists():
            match = re.search(r"url\s*=\s*(?:https://github\.com/|git@github\.com:)([^/\s]+/[^/\s]+?)(?:\.git)?\s*$",
                              git_config.read_text(encoding="utf-8", errors="ignore"), re.MULTILINE)
            repo = match.group(1) if match else ""
    if not repo:
        return ""
    owner, name = repo.split("/", 1)
    return f"https://{owner.lower()}.github.io/{name}/"


ALL_DAYS = tuple(range(7))


def resolve_edition_date(
    now: datetime | None = None, publish_hour: int = 8, publish_days: tuple[int, ...] = ALL_DAYS
) -> date:
    """현재 시각 기준 가장 최근의 '발행 요일 08:00'이 속한 날짜를 발행일로 본다.

    예) 월~금 발행일 때 화 08:05 실행 → 화요일 호, 화 07:30 → 월요일 호, 토/일 실행 → 금요일 호
    """
    now = (now or datetime.now(KST)).astimezone(KST)
    day = now.date() if now.time() >= time(publish_hour) else now.date() - timedelta(days=1)
    while day.weekday() not in publish_days:
        day -= timedelta(days=1)
    return day


def collection_window(
    edition_date: date, publish_hour: int = 8, publish_days: tuple[int, ...] = ALL_DAYS
) -> tuple[datetime, datetime]:
    """발행일 D 의 수집 구간: [직전 발행일 08:00, D 08:00) KST.

    월~금 발행이면 월요일 호는 금 08:00 ~ 월 08:00 (주말 메일 포함), 화요일 호는 월 08:00 ~ 화 08:00.
    """
    end = datetime.combine(edition_date, time(publish_hour), tzinfo=KST)
    prev = edition_date - timedelta(days=1)
    while prev.weekday() not in publish_days:
        prev -= timedelta(days=1)
    return datetime.combine(prev, time(publish_hour), tzinfo=KST), end
