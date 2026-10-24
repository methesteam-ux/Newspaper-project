"""[2단계] Jinja2 신문 HTML 렌더러 — CSS 를 인라인으로 넣어 파일 하나로 열람 가능하게 만든다."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from config import TEMPLATE_DIR
from models import Newspaper

_EDITION_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.html$")


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _css() -> str:
    return (TEMPLATE_DIR / "style.css").read_text(encoding="utf-8")


def render(paper: Newspaper, output_path: Path) -> Path:
    html = _env().get_template("newspaper.html").render(paper=paper, css=_css())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path


@dataclass
class Edition:
    date: date
    file: str


def render_index(output_dir: Path, title: str, publisher: str) -> Path:
    """Output/ 의 YYYY-MM-DD.html 목록으로 지난 신문 페이지(index.html)를 만든다 (GitHub Pages 첫 화면)."""
    editions = sorted(
        (Edition(date.fromisoformat(m.group(1)), p.name) for p in output_dir.glob("*.html") if (m := _EDITION_RE.match(p.name))),
        key=lambda e: e.date,
        reverse=True,
    )
    html = _env().get_template("index.html").render(title=title, publisher=publisher, editions=editions, css=_css())
    path = output_dir / "index.html"
    path.write_text(html, encoding="utf-8")
    return path
