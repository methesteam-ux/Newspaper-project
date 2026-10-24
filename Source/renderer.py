"""[2단계] Jinja2 신문 HTML 렌더러 — CSS 를 인라인으로 넣어 파일 하나로 열람 가능하게 만든다."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from config import TEMPLATE_DIR
from models import Newspaper


def render(paper: Newspaper, output_path: Path) -> Path:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    css = (TEMPLATE_DIR / "style.css").read_text(encoding="utf-8")
    html = env.get_template("newspaper.html").render(paper=paper, css=css)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
