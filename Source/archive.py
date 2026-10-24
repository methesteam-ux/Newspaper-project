"""발행 기록(아카이브) — 호수, 이전/다음 호, 이번 주 1면 모아보기, 지난 신문 목록·검색·RSS 의 데이터.

발행할 때마다 Output/data/YYYY-MM-DD.json 에 지면 요약을 남긴다.
JSON 이 없는 예전 호(HTML 만 있는 경우)는 HTML 에서 1면 제목을 읽어 최소 정보로 복원한다.
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path

from models import Newspaper

_EDITION_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.html$")


def data_dir(out_dir: Path) -> Path:
    return out_dir / "data"


def edition_dates(out_dir: Path) -> list[date]:
    found = {date.fromisoformat(m.group(1)) for p in out_dir.glob("*.html") if (m := _EDITION_RE.match(p.name))}
    found |= {date.fromisoformat(p.stem) for p in data_dir(out_dir).glob("*.json") if re.match(r"\d{4}-\d{2}-\d{2}$", p.stem)}
    return sorted(found)


def _from_html(path: Path, day: date) -> dict:
    from bs4 import BeautifulSoup

    entry = {"date": day.isoformat(), "file": path.name, "main": {}, "articles": [], "keywords": [], "count": 0}
    if not path.exists():
        return entry
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "lxml")
    head = soup.select_one(".main-story h2")
    img = soup.select_one(".main-story img")
    if head:
        entry["main"] = {"title": head.get_text(strip=True), "image": img["src"] if img else "", "summary": ""}
    titles = [h.get_text(strip=True) for h in soup.select(".main-story h2, .sub-story h3, .item h4")]
    entry["articles"] = [{"title": t, "category": "", "url": ""} for t in titles]
    entry["count"] = len(titles)
    return entry


def load(out_dir: Path, day: date) -> dict:
    path = data_dir(out_dir) / f"{day.isoformat()}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return _from_html(out_dir / f"{day.isoformat()}.html", day)


def load_all(out_dir: Path) -> list[dict]:
    return [load(out_dir, d) for d in edition_dates(out_dir)]


def save(paper: Newspaper, out_dir: Path) -> Path:
    def brief(c):
        return {
            "uid": c.uid,
            "title": c.article.title,
            "summary": c.summary,
            "url": c.article.url,
            "image": c.article.image_url,
            "category": c.category,
            "keywords": c.keywords,
        }

    items = ([paper.main] if paper.main else []) + paper.subs + [c for _, g in paper.sections for c in g]
    entry = {
        "date": paper.edition_date.isoformat(),
        "file": f"{paper.edition_date.isoformat()}.html",
        "issue_no": paper.issue_no,
        "title": paper.title,
        "generated_at": paper.generated_at.isoformat(timespec="seconds"),
        "main": brief(paper.main) if paper.main else {},
        "subs": [brief(c) for c in paper.subs],
        "articles": [brief(c) for c in items],
        "briefing": paper.briefing,
        "editor_note": paper.editor_note,
        "keywords": [k for k, _ in paper.keywords],
        "count": paper.article_count,
    }
    path = data_dir(out_dir) / f"{paper.edition_date.isoformat()}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entry, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def issue_number(out_dir: Path, day: date) -> int:
    """이 호보다 앞선 발행 수 + 1 (같은 날 재발행하면 같은 호수)."""
    return sum(1 for d in edition_dates(out_dir) if d < day) + 1


def neighbors(out_dir: Path, day: date) -> tuple[str, str]:
    dates = [d for d in edition_dates(out_dir) if d != day]
    prev = max((d for d in dates if d < day), default=None)
    nxt = min((d for d in dates if d > day), default=None)
    return (f"{prev.isoformat()}.html" if prev else "", f"{nxt.isoformat()}.html" if nxt else "")


def this_week(out_dir: Path, day: date) -> list[dict]:
    """같은 주(월요일 시작)에 이 호보다 먼저 나온 호들의 1면."""
    monday = day - timedelta(days=day.weekday())
    out = []
    for d in edition_dates(out_dir):
        if monday <= d < day:
            entry = load(out_dir, d)
            if entry.get("main", {}).get("title"):
                out.append({"date": d, "file": f"{d.isoformat()}.html", **entry["main"]})
    return out
