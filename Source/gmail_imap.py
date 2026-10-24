"""[1단계] Gmail IMAP 수집기 — News 라벨, 전날 08:00 ~ 당일 08:00(KST)."""
from __future__ import annotations

import base64
import email
import html as html_lib
import imaplib
import logging
import re
from datetime import datetime, timedelta
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parseaddr

from config import KST, Settings
from models import RawMail

log = logging.getLogger(__name__)

URL_RE = re.compile(r"https?://[^\s<>\"'()\[\]{}]+", re.IGNORECASE)
# 기사 링크가 아닌 것으로 보이는 URL (이미지, 추적 픽셀, 앱스토어 등)
_IGNORED_URL_RE = re.compile(
    r"\.(png|jpe?g|gif|webp|svg|ico)(\?|$)|apps\.apple\.com|play\.google\.com|"
    r"schemas\.microsoft|w3\.org|mailto:|unsubscribe",
    re.IGNORECASE,
)


def imap_utf7_encode(text: str) -> str:
    """IMAP modified UTF-7 (RFC 3501) — '뉴스' 같은 비ASCII 라벨 이름용."""
    out, buf = [], []

    def flush():
        if buf:
            raw = "".join(buf).encode("utf-16-be")
            out.append("&" + base64.b64encode(raw).decode().rstrip("=").replace("/", ",") + "-")
            buf.clear()

    for ch in text:
        if 0x20 <= ord(ch) <= 0x7E:
            flush()
            out.append("&-" if ch == "&" else ch)
        else:
            buf.append(ch)
    flush()
    return "".join(out)


def _decode(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value))).strip()
    except Exception:
        return value.strip()


def _part_text(part: Message) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")


def _extract_bodies(msg: Message) -> tuple[str, str]:
    text, html = [], []
    for part in msg.walk() if msg.is_multipart() else [msg]:
        if part.get_content_maintype() == "multipart":
            continue
        if "attachment" in (part.get("Content-Disposition") or "").lower():
            continue
        ctype = part.get_content_type()
        if ctype == "text/plain":
            text.append(_part_text(part))
        elif ctype == "text/html":
            html.append(_part_text(part))
    return "\n".join(text).strip(), "\n".join(html).strip()


def extract_urls(text: str, html: str) -> list[str]:
    """본문에서 기사 링크 후보를 순서대로(중복 없이) 뽑는다."""
    candidates = re.findall(r'href=["\']([^"\']+)["\']', html, re.IGNORECASE)
    candidates += URL_RE.findall(text)
    candidates += URL_RE.findall(html_lib.unescape(re.sub(r"<[^>]+>", " ", html)))
    seen, urls = set(), []
    for url in candidates:
        url = html_lib.unescape(url).rstrip(".,;:!?)'\"")
        if not url.lower().startswith("http") or _IGNORED_URL_RE.search(url):
            continue
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def html_to_text(html: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "head"]):
        tag.decompose()
    lines = [ln.strip() for ln in soup.get_text("\n").splitlines()]
    return "\n".join(ln for ln in lines if ln)


def fetch_mails(settings: Settings, start: datetime, end: datetime) -> list[RawMail]:
    """라벨 폴더에서 [start, end) 구간에 받은 메일을 가져온다. 읽음 상태는 바꾸지 않는다."""
    if not settings.has_gmail:
        raise RuntimeError(".env 에 GMAIL_USER / GMAIL_APP_PASSWORD 가 설정되지 않았습니다.")

    log.info("IMAP 접속: %s:%s (%s)", settings.imap_server, settings.imap_port, settings.gmail_user)
    conn = imaplib.IMAP4_SSL(settings.imap_server, settings.imap_port)
    try:
        conn.login(settings.gmail_user, settings.gmail_app_password)
        mailbox = '"' + imap_utf7_encode(settings.gmail_label).replace('"', '\\"') + '"'
        status, _ = conn.select(mailbox, readonly=True)
        if status != "OK":
            raise RuntimeError(
                f"'{settings.gmail_label}' 라벨을 IMAP 에서 열 수 없습니다. "
                "Gmail 설정 > 라벨 > 'IMAP에 표시'가 체크되어 있는지 확인하세요."
            )

        # SINCE 는 날짜 단위라 하루 여유를 두고 검색한 뒤 INTERNALDATE 로 정밀 필터링한다.
        since = (start - timedelta(days=1)).strftime("%d-%b-%Y")
        status, data = conn.uid("search", None, "SINCE", since)
        uids = data[0].split() if status == "OK" and data and data[0] else []
        log.info("라벨 '%s' 검색 결과 %d건 (SINCE %s)", settings.gmail_label, len(uids), since)

        mails: list[RawMail] = []
        for uid in uids:
            status, parts = conn.uid("fetch", uid, "(INTERNALDATE BODY.PEEK[])")
            if status != "OK" or not parts or not isinstance(parts[0], tuple):
                continue
            meta, raw = parts[0]
            try:
                received_at = _internal_to_kst(meta)
            except ValueError:
                continue
            if not (start <= received_at < end):
                continue

            msg = email.message_from_bytes(raw)
            text, html = _extract_bodies(msg)
            if not text and html:
                text = html_to_text(html)
            mails.append(
                RawMail(
                    uid=uid.decode(),
                    subject=_decode(msg.get("Subject")),
                    sender=parseaddr(_decode(msg.get("From")))[1],
                    received_at=received_at,
                    text=text,
                    html=html,
                    urls=extract_urls(text, html),
                )
            )
        mails.sort(key=lambda m: m.received_at)
        log.info("수집 구간 내 메일 %d건", len(mails))
        return mails
    finally:
        try:
            conn.logout()
        except Exception:
            pass


_INTERNALDATE_RE = re.compile(rb'INTERNALDATE "([^"]+)"')


def _internal_to_kst(meta: bytes) -> datetime:
    """IMAP INTERNALDATE("24-Oct-2026 08:01:02 +0900")를 KST datetime 으로."""
    match = _INTERNALDATE_RE.search(meta)
    if not match:
        raise ValueError(f"INTERNALDATE 없음: {meta!r}")
    return datetime.strptime(match.group(1).decode(), "%d-%b-%Y %H:%M:%S %z").astimezone(KST)
