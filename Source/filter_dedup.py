"""[1단계] 중복 기사 제거 — 동일 URL 또는 제목 유사도 65% 이상이면 1건만 유지."""
from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from models import Article

log = logging.getLogger(__name__)

TITLE_SIMILARITY = 0.65
_TRACKING_PARAMS = re.compile(r"^(utm_|fbclid|gclid|igshid|si$|s$|t$|ref|shem|from|feature)", re.IGNORECASE)


def normalize_url(url: str) -> str:
    if not url:
        return ""
    parts = urlparse(url.strip())
    host = parts.netloc.lower().removeprefix("www.").removeprefix("m.").removeprefix("mobile.")
    if host == "twitter.com":
        host = "x.com"
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query) if not _TRACKING_PARAMS.match(k)))
    return urlunparse(("https", host, parts.path.rstrip("/"), "", query, ""))


def normalize_title(title: str) -> str:
    title = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", title)  # [속보], (종합) 등
    title = re.sub(r"\s[-|│]\s.*$", "", title)  # " - 언론사명" 꼬리
    return re.sub(r"[^\w가-힣]+", "", title).lower()


def title_similarity(a: str, b: str) -> float:
    a, b = normalize_title(a), normalize_title(b)
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


class _Group:
    """같은 기사로 판정된 묶음. 병합된 모든 기사의 URL·제목을 기억해 이후 비교에 쓴다."""

    def __init__(self, art: Article):
        self.best = art
        self.urls = {normalize_url(art.url)} - {""}
        self.titles = [] if art.is_sns else [art.title]

    def matches(self, art: Article) -> bool:
        if art.url and normalize_url(art.url) in self.urls:
            return True
        # SNS 의 "X의 OO 님 게시물" 처럼 형식적인 제목끼리는 제목 비교를 하지 않는다.
        if art.is_sns:
            return False
        return any(title_similarity(art.title, t) >= TITLE_SIMILARITY for t in self.titles)

    def add(self, art: Article) -> None:
        # 본문이 더 풍부한 쪽을 대표로 남기고, 언급 횟수는 합산한다.
        winner, loser = (art, self.best) if len(art.body) > len(self.best.body) else (self.best, art)
        winner.mention_count = self.best.mention_count + art.mention_count
        winner.image_url = winner.image_url or loser.image_url
        log.info("중복 제거: '%s' ≈ '%s'", loser.title[:40], winner.title[:40])
        self.best = winner
        self.urls |= {normalize_url(art.url)} - {""}
        if not art.is_sns:
            self.titles.append(art.title)


def deduplicate(articles: list[Article]) -> list[Article]:
    groups: list[_Group] = []
    for art in articles:
        group = next((g for g in groups if g.matches(art)), None)
        if group:
            group.add(art)
        else:
            groups.append(_Group(art))
    return [g.best for g in groups]
