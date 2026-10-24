"""[2단계] Jinja2 렌더러 — 신문 HTML, 지난 신문(아카이브) 페이지, RSS 피드.

CSS/JS 는 HTML 안에 인라인으로 넣어 파일 하나만으로 열람할 수 있게 한다.
"""
from __future__ import annotations

import calendar
import json
from datetime import date, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

import archive
from config import KST, TEMPLATE_DIR, Settings, describe_days
from insights import category_color
from models import Newspaper

WEEKDAYS_KO = "월화수목금토일"


def date_ko(d: date) -> str:
    return f"{d.year}년 {d.month}월 {d.day}일 {WEEKDAYS_KO[d.weekday()]}요일"


def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["date_ko"] = date_ko
    env.filters["weekday_ko"] = lambda d: WEEKDAYS_KO[d.weekday()]
    env.filters["catcolor"] = category_color
    env.filters["paragraphs"] = lambda text, limit=2500: [
        p.strip() for p in (text or "")[:limit].splitlines() if p.strip()
    ]
    return env


def _asset(name: str) -> str:
    return (TEMPLATE_DIR / name).read_text(encoding="utf-8")


def make_qr_svg(url: str) -> str:
    if not url:
        return ""
    try:
        import segno

        return segno.make(url, error="m").svg_inline(scale=3, dark="#000", light=None, border=1)
    except Exception:
        return ""


def render(paper: Newspaper, output_path: Path) -> Path:
    items = ([paper.main] if paper.main else []) + paper.subs + [c for _, g in paper.sections for c in g]
    html = _env().get_template("newspaper.html").render(
        paper=paper,
        items=items,
        css=_asset("style.css"),
        js=_asset("newspaper.js"),
        page_url=(paper.site_url + output_path.name) if paper.site_url else "",
        stat_max=max([s.value for s in paper.category_stats] or [1]),
        hist_max=max(paper.arrival_hist or [1]) or 1,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path


def _months(editions: list[dict], publish_days: tuple[int, ...]) -> list[dict]:
    """발행 기록이 있는 달마다 월요일 시작 달력 격자를 만든다 (최근 달 먼저)."""
    by_day = {e["date"]: e for e in editions}
    keys = sorted({(int(d[:4]), int(d[5:7])) for d in by_day}, reverse=True)
    today = datetime.now(KST).date()
    months = []
    for year, month in keys:
        weeks = []
        for week in calendar.Calendar(firstweekday=0).monthdatescalendar(year, month):
            weeks.append([
                {
                    "day": d.day,
                    "in_month": d.month == month,
                    "edition": by_day.get(d.isoformat()),
                    "publish_day": d.weekday() in publish_days,
                    "today": d == today,
                }
                for d in week
            ])
        months.append({"label": f"{year}년 {month}월", "weeks": weeks})
    return months


def render_index(out_dir: Path, settings: Settings) -> Path:
    """지난 신문 페이지: 최신호 히어로, 달력, 전체 기사 검색, 호 목록 (GitHub Pages 첫 화면)."""
    editions = archive.load_all(out_dir)
    for e in editions:
        e["weekday"] = WEEKDAYS_KO[date.fromisoformat(e["date"]).weekday()]
    latest = editions[-1] if editions else None
    search_index = [
        {"d": e["date"], "f": e.get("file", f"{e['date']}.html"), "t": a.get("title", ""),
         "c": a.get("category", ""), "u": a.get("uid", "")}
        for e in editions for a in e.get("articles", [])
    ]
    keyword_count: dict[str, int] = {}
    for e in editions:
        for k in e.get("keywords", []):
            keyword_count[k] = keyword_count.get(k, 0) + 1
    html = _env().get_template("index.html").render(
        title=settings.newspaper_title,
        tagline=settings.tagline,
        publisher=settings.publisher_name,
        schedule_label=f"{describe_days(settings.publish_days)} {settings.publish_hour:02d}:00",
        editions=list(reversed(editions)),
        latest=latest,
        months=_months(editions, settings.publish_days),
        total_articles=sum(e.get("count", 0) for e in editions),
        top_keywords=sorted(keyword_count.items(), key=lambda kv: -kv[1])[:16],
        search_json=json.dumps(search_index, ensure_ascii=False).replace("</", "<\\/"),
        site_url=settings.site_url,
        css=_asset("style.css"),
    )
    path = out_dir / "index.html"
    path.write_text(html, encoding="utf-8")
    return path


def render_feed(out_dir: Path, settings: Settings, limit: int = 30) -> Path | None:
    """RSS 2.0 피드 (feed.xml). Pages 주소를 알 때만 만든다."""
    if not settings.site_url:
        return None
    editions = list(reversed(archive.load_all(out_dir)))[:limit]
    xml = _env().get_template("feed.xml").render(
        title=settings.newspaper_title,
        tagline=settings.tagline,
        site_url=settings.site_url,
        editions=editions,
        rfc822=lambda d: datetime.fromisoformat(d).replace(hour=settings.publish_hour, tzinfo=KST).strftime(
            "%a, %d %b %Y %H:%M:%S +0900"),
    )
    path = out_dir / "feed.xml"
    path.write_text(xml, encoding="utf-8")
    return path
