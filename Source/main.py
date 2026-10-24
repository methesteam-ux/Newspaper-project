"""나만의 신문 — 전체 파이프라인 통합 CLI.

Gmail(News 라벨) 수집 → Playwright 크롤링 → 중복 제거 → SNS 번역 → Gemini 편집 → Output/YYYY-MM-DD.html

사용법:
    python Source/main.py                    # 가장 최근 08:00 기준 신문 발행
    python Source/main.py --date 2026-10-24  # 특정 발행일
    python Source/main.py --demo             # 샘플 기사로 레이아웃 확인 (Output/demo.html)
    python Source/main.py --no-llm           # Gemini 없이 규칙 기반 편집
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import date, datetime

from config import OUTPUT_DIR, KST, collection_window, load_settings, resolve_edition_date

log = logging.getLogger("newspaper")


def setup_logging() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S")
    console = logging.StreamHandler(sys.stdout)
    file = logging.FileHandler(OUTPUT_DIR / "daily_run.log", encoding="utf-8")
    for handler in (console, file):
        handler.setFormatter(fmt)
    logging.basicConfig(level=logging.INFO, handlers=[console, file], force=True)
    for noisy in ("httpx", "google_genai", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def run(edition_date: date | None = None, demo: bool = False, use_llm: bool = True) -> int:
    # 무거운 모듈(Playwright, Gemini)은 실행 시점에 불러온다.
    from crawler import build_articles
    from curator import curate
    from filter_dedup import deduplicate
    from gmail_imap import fetch_mails
    from llm import make_gemini
    from models import Newspaper
    from renderer import render
    from sns_helper import localize_sns

    started = time.monotonic()
    settings = load_settings()
    edition_date = edition_date or resolve_edition_date(publish_hour=settings.publish_hour)
    start, end = collection_window(edition_date, settings.publish_hour)
    window_label = f"{start:%m-%d %H:%M} ~ {end:%m-%d %H:%M}"
    log.info("=== %s %s 호 제작 시작 (수집 %s KST) ===", settings.newspaper_title, edition_date, window_label)

    # 1단계: 수집 → 크롤링 → 중복 제거
    if demo:
        from demo_data import sample_articles

        articles = sample_articles()
        log.info("데모 모드: 샘플 기사 %d건", len(articles))
    else:
        mails = fetch_mails(settings, start, end)
        articles = build_articles(mails)
    articles = deduplicate(articles)
    log.info("중복 제거 후 기사 %d건", len(articles))

    # 2단계: SNS 번역 → 편집 → 렌더링
    gemini = make_gemini(settings.gemini_api_key, settings.gemini_model) if use_llm else None
    localize_sns(articles, gemini)
    main_story, subs, sections = curate(articles, gemini)

    paper = Newspaper(
        title=settings.newspaper_title,
        publisher=settings.publisher_name,
        edition=settings.edition_name,
        edition_date=edition_date,
        generated_at=datetime.now(KST),
        main=main_story,
        subs=subs,
        sections=sections,
        article_count=len(articles),
        window_label=window_label,
    )
    filename = "demo.html" if demo else f"{edition_date.isoformat()}.html"
    path = render(paper, OUTPUT_DIR / filename)
    log.info("=== 발행 완료: %s (기사 %d건, %.1f초) ===", path, len(articles), time.monotonic() - started)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="나만의 신문 발행")
    parser.add_argument("--date", help="발행일 YYYY-MM-DD (기본: 가장 최근 08:00 기준)")
    parser.add_argument("--demo", action="store_true", help="샘플 기사로 Output/demo.html 생성")
    parser.add_argument("--no-llm", action="store_true", help="Gemini 를 쓰지 않고 규칙 기반으로 편집")
    args = parser.parse_args()

    setup_logging()
    try:
        return run(
            edition_date=date.fromisoformat(args.date) if args.date else None,
            demo=args.demo,
            use_llm=not args.no_llm,
        )
    except Exception:
        log.exception("신문 발행 실패")
        return 1


if __name__ == "__main__":
    sys.exit(main())
