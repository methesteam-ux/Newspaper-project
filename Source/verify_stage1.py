"""[1단계] 검증 스크립트 — Gmail 수신, 본문 추출, Playwright 크롤링, 중복 제거를 차례로 확인한다.

사용법:
    .venv\\Scripts\\python.exe Source\\verify_stage1.py [--date YYYY-MM-DD] [--url URL ...]
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

sys.stdout.reconfigure(encoding="utf-8")

from config import collection_window, load_settings, resolve_edition_date
from crawler import Crawler, build_articles, sns_name
from filter_dedup import deduplicate
from gmail_imap import fetch_mails
from models import Article

DEFAULT_TEST_URLS = ["https://news.hada.io"]


def line(title: str) -> None:
    print(f"\n▶ {title}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="발행일 YYYY-MM-DD (기본: 가장 최근 08:00 기준)")
    parser.add_argument("--url", nargs="*", help="크롤링 테스트 URL")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    settings = load_settings()
    edition = date.fromisoformat(args.date) if args.date else resolve_edition_date(publish_hour=settings.publish_hour, publish_days=settings.publish_days)
    start, end = collection_window(edition, settings.publish_hour, settings.publish_days)
    print("=" * 70)
    print("  [1단계 검증] 데이터 수집, 본문 추출, Playwright 크롤링, 중복 제거")
    print("=" * 70)
    print(f"[*] 발행 기준일: {edition} ({settings.newspaper_title} - {settings.edition_name})")
    print(f"[*] 발행인 정보: {settings.publisher_name}")
    print(f"[*] 수집 시간대: {start:%Y-%m-%d %H:%M} ~ {end:%Y-%m-%d %H:%M} (KST, 24시간)")

    ok = True
    line("[검증 1] Gmail IMAP 연결 및 메일 수신")
    articles: list[Article] = []
    if not settings.has_gmail:
        print("  - 건너뜀: .env 에 GMAIL_USER / GMAIL_APP_PASSWORD 를 입력하면 실제 수신을 확인합니다.")
    else:
        try:
            mails = fetch_mails(settings, start, end)
            print(f"  ✓ '{settings.gmail_label}' 라벨에서 {len(mails)}건 수신")
            for i, m in enumerate(mails, 1):
                print(f"    [{i}] {m.received_at:%m-%d %H:%M} {m.subject}  ({m.urls[0] if m.urls else '링크 없음'})")

            line("[검증 2] 기사 본문 추출 (정형: 메일 그대로 / 비정형: Playwright 크롤링)")
            articles = build_articles(mails)
            for i, a in enumerate(articles, 1):
                tag = "SNS" if a.is_sns else ("정형" if a.kind == "structured" else "크롤링")
                print(f"    [{i}] ({tag}/{a.source_name}) {a.title}")
                print(f"        본문 {len(a.body)}자: {a.body[:80].replace(chr(10), ' ')}...")
                print(f"        이미지: {a.image_url or '(없음)'}")
        except Exception as exc:
            ok = False
            print(f"  ✗ 실패: {exc}")

    line("[검증 3] Playwright 웹 크롤링(비정형 데이터) 동작")
    try:
        with Crawler() as crawler:
            for url in args.url or DEFAULT_TEST_URLS:
                data = crawler.fetch(url)
                print(f"  [*] 타겟 URL: {url} → {data.final_url}")
                print(f"  ✓ 제목: {data.title!r}  (SNS: {sns_name(data.final_url) or '아님'})")
                print(f"  ✓ 본문({len(data.body)}자): {data.body[:100].replace(chr(10), ' ')!r}")
                print(f"  ✓ 대표 이미지: {data.image_url or '(없음)'}")
    except Exception as exc:
        ok = False
        print(f"  ✗ 크롤링 실패: {exc}")

    line("[검증 4] 중복 기사 제거 (동일 URL / 제목 유사도 65% 이상)")
    sample = [
        Article(title="지멘스·TSMC, AI 기반 반도체 설계 자동화 고도화", body="a" * 10, url="https://a.com/1?utm_source=x"),
        Article(title="[종합] 지멘스·TSMC, AI 기반 반도체 설계 자동화 고도화 - 인공지능신문", body="b" * 20, url="https://b.com/2"),
        Article(title="다른 기사", body="c", url="https://www.a.com/1"),
        Article(title="완전히 새로운 기사", body="d", url="https://c.com/3"),
    ]
    result = deduplicate(sample)
    passed = len(result) == 2 and result[0].mention_count == 3
    ok &= passed
    print(f"  {'✓' if passed else '✗'} 4건 → {len(result)}건 (언급 횟수: {[a.mention_count for a in result]})")
    if articles:
        print(f"  ✓ 실제 수집 기사 {len(articles)}건 → 중복 제거 후 {len(deduplicate(articles))}건")

    print("\n" + ("1단계 검증 완료" if ok else "1단계 검증 중 실패 항목이 있습니다"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
