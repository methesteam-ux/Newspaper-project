"""(선택) 뉴스레터 — 발행한 신문의 브리핑과 헤드라인을 메일로 보낸다. 기본값: 꺼짐.

켜기: .env 에 NEWSLETTER_ENABLED=true (받는 사람 NEWSLETTER_TO, 비우면 GMAIL_USER 본인)
      또는 main.py --newsletter
메일 프로그램은 CSS/JS 를 대부분 지원하지 않으므로 표(table) + 인라인 스타일로 만든다.
"""
from __future__ import annotations

import html
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import Settings
from insights import category_color
from models import Newspaper

log = logging.getLogger(__name__)


def build_html(paper: Newspaper, edition_url: str) -> str:
    e = html.escape
    items = ([paper.main] if paper.main else []) + paper.subs + [c for _, g in paper.sections for c in g]
    rows = []
    for i, c in enumerate(items):
        link = e(c.article.url or edition_url or "#")
        img = (f'<img src="{e(c.article.image_url)}" width="560" style="width:100%;max-width:560px;height:auto;'
               f'border-radius:4px;display:block;margin:0 0 12px" alt="">') if i == 0 and c.article.image_url else ""
        size = "22px" if i == 0 else "16px"
        rows.append(
            f'<tr><td style="padding:18px 0;border-bottom:1px solid #e4e1d8">{img}'
            f'<div style="font:700 11px sans-serif;letter-spacing:.06em;color:{category_color(c.category)}">'
            f'{"🔥 최고 주요 소식 · " if i == 0 else ""}{e(c.category)}</div>'
            f'<a href="{link}" style="display:block;margin:6px 0 8px;font:800 {size}/1.4 Georgia,serif;color:#121212;'
            f'text-decoration:none">{e(c.article.title)}</a>'
            f'<div style="font:14px/1.7 sans-serif;color:#50555c">{e(c.summary)}</div></td></tr>'
        )
    briefing = "".join(f'<li style="margin:4px 0">{e(b)}</li>' for b in paper.briefing)
    weather = (f"{e(paper.weather.city)} {paper.weather.emoji} {paper.weather.temp}° · " if paper.weather else "")
    cta = (f'<a href="{e(edition_url)}" style="display:inline-block;margin-top:18px;padding:10px 18px;background:#c8102e;'
           f'color:#fff;text-decoration:none;font:700 14px sans-serif;border-radius:3px">지면 전체 보기 →</a>') if edition_url else ""
    return f"""<!DOCTYPE html><html lang="ko"><body style="margin:0;background:#f3f1ea">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#fdfcf9;padding:28px 20px">
<tr><td align="center" style="border-bottom:3px double #121212;padding-bottom:12px">
<div style="font:700 11px sans-serif;letter-spacing:.3em;color:#c8102e">{e(paper.tagline)}</div>
<div style="font:900 40px/1.1 Georgia,serif;color:#121212;margin-top:4px">{e(paper.title)}</div>
<div style="font:13px sans-serif;color:#50555c;margin-top:8px">{weather}{paper.edition_date.isoformat()} 발행 · 제{paper.issue_no}호 · 발행인 {e(paper.publisher)}</div>
</td></tr>
<tr><td style="padding:18px 0 4px"><div style="font:900 15px Georgia,serif;color:#121212">오늘의 3줄 브리핑</div>
<ol style="font:15px/1.6 Georgia,serif;color:#121212;padding-left:20px;margin:8px 0">{briefing}</ol>
<div style="font:italic 14px/1.6 Georgia,serif;color:#24272b;border-left:3px solid #c8102e;padding:6px 12px;background:#f6f4ee">{e(paper.editor_note)}</div>
</td></tr>
{''.join(rows)}
<tr><td align="center">{cta}<div style="font:12px sans-serif;color:#7a7f87;margin-top:16px">이 메일은 {e(paper.title)} 발행 프로그램이 자동으로 보냈습니다.</div></td></tr>
</table></td></tr></table></body></html>"""


def send(settings: Settings, paper: Newspaper, body_html: str) -> bool:
    if not settings.has_gmail:
        log.warning("뉴스레터: GMAIL_USER / GMAIL_APP_PASSWORD 가 없어 보내지 않습니다.")
        return False
    to = settings.newsletter_to or settings.gmail_user
    msg = MIMEMultipart("alternative")
    headline = paper.main.article.title if paper.main else "오늘의 신문"
    msg["Subject"] = f"[{paper.title}] {paper.edition_date.isoformat()} 제{paper.issue_no}호 — {headline}"
    msg["From"] = settings.gmail_user
    msg["To"] = to
    text = "\n".join([paper.title, *[f"- {b}" for b in paper.briefing]])
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
            smtp.login(settings.gmail_user, settings.gmail_app_password)
            smtp.sendmail(settings.gmail_user, [a.strip() for a in to.split(",") if a.strip()], msg.as_string())
        log.info("뉴스레터 발송 완료 (%d명)", len([a for a in to.split(",") if a.strip()]))
        return True
    except Exception as exc:
        log.warning("뉴스레터 발송 실패: %s", exc)
        return False
