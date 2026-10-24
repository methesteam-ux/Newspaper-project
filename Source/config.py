"""설정 로딩 및 수집 시간대(전날 08:00 ~ 당일 08:00, KST) 계산."""
from __future__ import annotations

import os
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
    )


def resolve_edition_date(now: datetime | None = None, publish_hour: int = 8) -> date:
    """현재 시각 기준 가장 최근의 발행 시각(08:00)이 속한 날짜를 발행일로 본다.

    예) 10/24 08:05 실행 → 10/24 호, 10/24 07:30 실행 → 10/23 호
    """
    now = (now or datetime.now(KST)).astimezone(KST)
    if now.time() >= time(publish_hour):
        return now.date()
    return now.date() - timedelta(days=1)


def collection_window(edition_date: date, publish_hour: int = 8) -> tuple[datetime, datetime]:
    """발행일 D 의 수집 구간: [D-1 08:00, D 08:00) KST."""
    end = datetime.combine(edition_date, time(publish_hour), tzinfo=KST)
    return end - timedelta(days=1), end
