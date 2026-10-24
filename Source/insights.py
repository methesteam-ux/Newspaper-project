"""지면 데이터 — 카테고리 분포, 메일 도착 시간대, 출처 수, 읽기 시간 등 '오늘의 지면 통계'."""
from __future__ import annotations

import zlib
from collections import Counter
from urllib.parse import urlparse

from config import KST
from models import CuratedArticle, Stat

# 카테고리 색 (신문 지면용으로 채도를 낮춘 팔레트)
CATEGORY_COLORS = {
    "AI/ML": "#2563eb",
    "반도체/하드웨어": "#7c3aed",
    "로봇": "#0891b2",
    "데이터": "#0d9488",
    "보안": "#dc2626",
    "개발/소프트웨어": "#4f46e5",
    "과학/연구": "#16a34a",
    "교육/산업협력": "#ca8a04",
    "경제/산업": "#ea580c",
    "사회": "#db2777",
    "기타": "#64748b",
}
_EXTRA = ["#9333ea", "#0284c7", "#65a30d", "#b45309", "#be123c", "#475569"]


def category_color(name: str) -> str:
    return CATEGORY_COLORS.get(name) or _EXTRA[zlib.crc32(name.encode()) % len(_EXTRA)]


def category_stats(items: list[CuratedArticle]) -> list[Stat]:
    counts = Counter(c.category for c in items)
    return [Stat(cat, n, category_color(cat)) for cat, n in counts.most_common()]


def arrival_histogram(items: list[CuratedArticle]) -> list[int]:
    hist = [0] * 24
    for c in items:
        when = c.article.received_at or c.article.published_at
        if when:
            hist[when.astimezone(KST).hour] += 1
    return hist


def source_count(items: list[CuratedArticle]) -> int:
    hosts = {urlparse(c.article.url).netloc.removeprefix("www.") or c.article.source_name for c in items}
    return len(hosts - {""})
