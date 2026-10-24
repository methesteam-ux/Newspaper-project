"""[1단계] Playwright 기반 동적 크롤러.

- 정형 데이터(메일 본문에 기사 전문이 있는 경우): 메일 제목·본문을 그대로 사용, 링크에서는 대표 이미지만 보강
- 비정형 데이터(링크 공유, SNS 등): 링크를 Playwright 로 열어 제목·본문·대표 이미지를 추출
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from models import Article, RawMail

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)
STRUCTURED_MIN_CHARS = 400  # 메일 본문이 이보다 길면 기사 전문이 메일에 들어 있다고 본다
MAX_BODY_CHARS = 8000

SNS_DOMAINS = {
    "x.com": "X",
    "twitter.com": "X",
    "threads.net": "Threads",
    "threads.com": "Threads",
    "instagram.com": "Instagram",
    "tiktok.com": "TikTok",
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
    "facebook.com": "Facebook",
}
KNOWN_SOURCES = {
    "naver.com": "네이버 뉴스",
    "daum.net": "다음 뉴스",
    "hankyung.com": "한국경제",
    "aitimes.kr": "인공지능신문",
    "aitimes.com": "AI타임스",
    "news.hada.io": "GeekNews",
}
# 본문 컨테이너 후보 (사이트별 → 일반)
BODY_SELECTORS = [
    "#dic_area", "#newsct_article", "#articleBodyContents", "#articeBody",  # 네이버
    ".article_view section", ".article_view", "[data-cloud-area='article']",  # 다음
    "#article-view-content-div", "#articletxt", "#articleBody", "#article_body",
    "[itemprop='articleBody']", ".article-body", ".article_body", ".article_txt",
    ".news_body", ".view_con", ".topic-contents", "article",
]
NOISE_SELECTORS = [
    "script", "style", "noscript", "iframe", "button", "form", "nav", "aside",
    "figcaption", ".img_desc", ".end_photo_org", ".reporter_area", ".byline", ".copyright", "[class*='related']",
    "[class*='recommend']", "[class*='share']",
]
# 기사 본문 끝에 붙는 상투 문구
BOILERPLATE_RE = re.compile(
    r"무단\s*전재|재배포\s*금지|재판매 및 DB 금지|저작권자|Copyright|ⓒ|©|기사를 더 자주 볼 수|구독하기|좋아요|"
    r"Sent from my|나의 iPhone에서 보냄|Galaxy에서 보냄|^\s*https?://\S+\s*$",
    re.IGNORECASE,
)
MAIL_NOISE_RE = re.compile(
    r"나의 iPhone에서 보냄|Sent from my \w+|Galaxy\S*에서 보냄|^\s*-+\s*$", re.IGNORECASE
)


def domain_of(url: str) -> str:
    host = urlparse(url).netloc.lower().split(":")[0]
    return host[4:] if host.startswith("www.") else host


def _match_domain(url: str, table: dict[str, str]) -> str:
    host = domain_of(url)
    for dom, name in table.items():
        if host == dom or host.endswith("." + dom):
            return name
    return ""


def sns_name(url: str) -> str:
    return _match_domain(url, SNS_DOMAINS)


def clean_text(text: str) -> str:
    lines = []
    for line in re.split(r"\n+", text.replace("\r", "")):
        line = re.sub(r"[ \t ]+", " ", line).strip()
        if len(line) < 2 or BOILERPLATE_RE.search(line):
            continue
        lines.append(line)
    return "\n".join(lines)[:MAX_BODY_CHARS]


def clean_mail_text(text: str) -> str:
    text = re.sub(r"https?://\S+", "", text)
    lines = [ln.strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln and not MAIL_NOISE_RE.search(ln)).strip()


@dataclass
class PageData:
    final_url: str = ""
    title: str = ""
    body: str = ""
    image_url: str = ""
    site_name: str = ""
    published_at: datetime | None = None


def _meta(soup: BeautifulSoup, *names: str) -> str:
    for name in names:
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return tag["content"].strip()
    return ""


def parse_html(html: str, url: str) -> PageData:
    """HTML 에서 제목/본문/대표 이미지를 추출한다 (사이트별 셀렉터 → 문단 밀도 휴리스틱 → og:description)."""
    soup = BeautifulSoup(html, "lxml")
    data = PageData(final_url=url)
    data.title = _meta(soup, "og:title", "twitter:title") or (soup.title.string.strip() if soup.title and soup.title.string else "")
    data.site_name = _meta(soup, "og:site_name")
    image = _meta(soup, "og:image", "og:image:url", "twitter:image", "twitter:image:src")
    data.image_url = urljoin(url, image) if image else ""
    published = _meta(soup, "article:published_time", "og:article:published_time")
    if published:
        try:
            data.published_at = datetime.fromisoformat(published.replace("Z", "+00:00"))
        except ValueError:
            pass

    for sel in NOISE_SELECTORS:
        for tag in soup.select(sel):
            tag.decompose()

    best = ""
    for sel in BODY_SELECTORS:
        for node in soup.select(sel):
            text = clean_text(node.get_text("\n"))
            if len(text) > len(best):
                best = text
        if len(best) >= 200:
            break

    if len(best) < 200:
        # 문단(p)이 가장 많이 모인 부모 요소를 본문으로 본다.
        scores: dict[int, tuple[int, object]] = {}
        for p in soup.find_all("p"):
            text = p.get_text(" ", strip=True)
            if len(text) < 30 or p.parent is None:
                continue
            score, _ = scores.get(id(p.parent), (0, None))
            scores[id(p.parent)] = (score + len(text), p.parent)
        if scores:
            _, node = max(scores.values(), key=lambda v: v[0])
            text = clean_text(node.get_text("\n"))
            if len(text) > len(best):
                best = text

    if len(best) < 80:
        best = _meta(soup, "og:description", "description", "twitter:description") or best
    data.body = best

    if not data.image_url and soup.select_one("article img[src]"):
        data.image_url = urljoin(url, soup.select_one("article img[src]")["src"])
    return data


class Crawler:
    """Chromium 을 한 번 띄워 여러 URL 을 순서대로 크롤링한다."""

    def __init__(self, timeout_ms: int = 25000):
        self.timeout_ms = timeout_ms
        self._pw = self._browser = self._context = None

    def __enter__(self) -> "Crawler":
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True)
        self._context = self._browser.new_context(
            user_agent=USER_AGENT, locale="ko-KR", viewport={"width": 1280, "height": 900}
        )
        self._context.set_default_timeout(self.timeout_ms)
        return self

    def __exit__(self, *exc) -> None:
        for closer in (self._context, self._browser):
            try:
                closer and closer.close()
            except Exception:
                pass
        if self._pw:
            self._pw.stop()

    # ------------------------------------------------------------------ fetch
    def fetch(self, url: str) -> PageData:
        page = self._context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=6000)
            except PlaywrightError:
                pass
            final_url = page.url
            name = sns_name(final_url)
            if name == "X":
                data = self._fetch_x(page, final_url)
            else:
                data = parse_html(page.content(), final_url)
                if name == "YouTube":
                    desc = page.evaluate(
                        "() => window.ytInitialPlayerResponse?.videoDetails?.shortDescription || ''"
                    )
                    if desc and len(desc) > len(data.body):
                        data.body = clean_text(desc)
            data.final_url = final_url
            return data
        finally:
            page.close()

    def _fetch_x(self, page, url: str) -> PageData:
        data = PageData(final_url=url, site_name="X")
        try:
            page.wait_for_selector('article [data-testid="tweetText"]', timeout=10000)
            article = page.locator("article").first
            data.body = clean_text(article.locator('[data-testid="tweetText"]').first.inner_text())
            img = article.locator('[data-testid="tweetPhoto"] img')
            if img.count():
                data.image_url = img.first.get_attribute("src") or ""
            data.title = parse_html(page.content(), url).title
        except PlaywrightError:
            log.info("X 페이지에서 본문을 찾지 못해 fxtwitter API 로 대체합니다: %s", url)
        if not data.body:
            data = _fetch_x_api(url) or data
        return data


def _fetch_x_api(url: str) -> PageData | None:
    """로그인 벽 등으로 X 페이지 렌더링이 실패할 때의 폴백 (api.fxtwitter.com)."""
    match = re.search(r"/([^/]+)/status/(\d+)", urlparse(url).path)
    if not match:
        return None
    user, tweet_id = match.groups()
    try:
        resp = requests.get(
            f"https://api.fxtwitter.com/{user}/status/{tweet_id}",
            headers={"User-Agent": USER_AGENT}, timeout=15,
        )
        tweet = resp.json().get("tweet") or {}
    except (requests.RequestException, ValueError):
        return None
    if not tweet.get("text"):
        return None
    photos = (tweet.get("media") or {}).get("photos") or []
    author = tweet.get("author") or {}
    return PageData(
        final_url=url,
        title=f"X에서 {author.get('name', user)}(@{author.get('screen_name', user)}) 님",
        body=clean_text(tweet["text"]),
        image_url=photos[0]["url"] if photos else "",
        site_name="X",
    )


# ---------------------------------------------------------------------- 조립
def _source_name(url: str, page: PageData | None) -> str:
    return (
        sns_name(url)
        or _match_domain(url, KNOWN_SOURCES)
        or (page.site_name if page else "")
        or domain_of(url)
        or "Gmail"
    )


def article_from_mail(mail: RawMail, crawler: Crawler) -> Article | None:
    url = mail.urls[0] if mail.urls else ""
    mail_body = clean_mail_text(mail.text)
    structured = len(mail_body) >= STRUCTURED_MIN_CHARS

    page: PageData | None = None
    if url:
        try:
            page = crawler.fetch(url)
        except Exception as exc:  # 개별 기사 실패가 전체를 막지 않도록
            log.warning("크롤링 실패 (%s): %s", url, exc)

    final_url = page.final_url if page and page.final_url else url
    is_sns = bool(sns_name(final_url) or sns_name(url))

    if structured:
        # 정형 데이터: 메일 제목과 본문을 그대로
        title, body, kind = mail.subject, mail_body, "structured"
    else:
        # 비정형 데이터: 크롤링 결과 우선, 없으면 메일 내용
        title = (page.title if page else "") or mail.subject
        if not is_sns and mail.subject and not mail.subject.startswith("X의"):
            title = mail.subject.removeprefix("[신문]").strip() or title
        body = (page.body if page else "") or mail_body
        kind = "crawled"

    if not title and not body:
        log.warning("제목/본문을 얻지 못해 제외: uid=%s", mail.uid)
        return None

    return Article(
        title=title.strip(),
        body=body.strip(),
        url=final_url,
        image_url=page.image_url if page else "",
        source_name=_source_name(final_url, page),
        published_at=(page.published_at if page and page.published_at else mail.received_at),
        is_sns=is_sns,
        kind=kind,
        mail_subject=mail.subject,
    )


def build_articles(mails: list[RawMail]) -> list[Article]:
    articles: list[Article] = []
    if not mails:
        return articles
    with Crawler() as crawler:
        for i, mail in enumerate(mails, 1):
            log.info("[%d/%d] %s", i, len(mails), mail.subject or mail.urls[:1])
            article = article_from_mail(mail, crawler)
            if article:
                articles.append(article)
    return articles
