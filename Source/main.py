"""나만의 신문 — 전체 파이프라인 통합 CLI.

Gmail(News 라벨) 수집 → Playwright 크롤링 → 중복 제거 → SNS 번역 → Gemini 편집 → Output/YYYY-MM-DD.html
발행할 때마다 지난 신문 페이지(index.html), RSS(feed.xml), 발행 기록(data/*.json)도 갱신한다.

사용법:
    python Source/main.py                    # 가장 최근 발행일(월~금 08:00) 기준 신문 발행
    python Source/main.py --date 2026-10-26  # 특정 발행일
    python Source/main.py --preview          # 실제 메일로 만들되 발행 기록에 남기지 않음 (Output/preview.html)
    python Source/main.py --demo             # 샘플 기사로 지난주~오늘 데모 신문 (Output/_demo/)
    python Source/main.py --no-llm           # Gemini 없이 규칙 기반 편집
    python Source/main.py --newsletter       # 발행 후 뉴스레터 메일 발송 (기본: 꺼짐)
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from config import OUTPUT_DIR, KST, Settings, collection_window, describe_days, load_settings, resolve_edition_date

log = logging.getLogger("newspaper")
DEMO_DIR = OUTPUT_DIR / "_demo"


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


def assemble(settings: Settings, edition_date: date, window_label: str, articles, gemini, out_dir: Path, weather):
    """편집 결과와 부가 지면(통계, 이번 주, 이전/다음 호, QR)을 모아 Newspaper 를 만든다."""
    import archive
    import insights
    from curator import curate
    from models import Newspaper
    from renderer import make_qr_svg
    from sns_helper import localize_sns

    localize_sns(articles, gemini)
    cur = curate(articles, gemini)
    items = cur.all
    prev_file, next_file = archive.neighbors(out_dir, edition_date)
    page_url = f"{settings.site_url}{edition_date.isoformat()}.html" if settings.site_url and out_dir == OUTPUT_DIR else ""
    return Newspaper(
        title=settings.newspaper_title,
        publisher=settings.publisher_name,
        edition=settings.edition_name,
        edition_date=edition_date,
        generated_at=datetime.now(KST),
        main=cur.main,
        subs=cur.subs,
        sections=cur.sections,
        article_count=len(articles),
        window_label=window_label,
        tagline=settings.tagline,
        issue_no=archive.issue_number(out_dir, edition_date),
        schedule_label=describe_days(settings.publish_days),
        briefing=cur.briefing,
        editor_note=cur.editor_note,
        numbers=cur.numbers,
        keywords=cur.keywords,
        weather=weather,
        category_stats=insights.category_stats(items),
        arrival_hist=insights.arrival_histogram(items),
        source_count=insights.source_count(items),
        total_reading_min=sum(c.reading_min for c in items),
        sns_count=sum(1 for c in items if c.article.is_sns),
        weekly=archive.this_week(out_dir, edition_date),
        prev_edition=prev_file,
        next_edition=next_file,
        site_url=settings.site_url if out_dir == OUTPUT_DIR else "",
        qr_svg=make_qr_svg(page_url),
        llm_used=cur.llm_used,
    )


def publish(paper, settings: Settings, out_dir: Path) -> Path:
    """신문 HTML + 발행 기록 + 지난 신문 페이지 + RSS."""
    import archive
    from renderer import render, render_feed, render_index

    path = render(paper, out_dir / f"{paper.edition_date.isoformat()}.html")
    archive.save(paper, out_dir)
    render_index(out_dir, settings)
    if out_dir == OUTPUT_DIR:
        render_feed(out_dir, settings)
    return path


def _weather(settings: Settings):
    if not settings.weather_enabled:
        return None
    from weather import fetch_weather

    return fetch_weather(settings.weather_city, settings.weather_lat, settings.weather_lon)


def run(edition_date: date | None = None, demo: bool = False, use_llm: bool = True,
        preview: bool = False, newsletter: bool = False) -> int:
    # 무거운 모듈(Playwright, Gemini)은 실행 시점에 불러온다.
    from crawler import build_articles
    from filter_dedup import deduplicate
    from gmail_imap import fetch_mails
    from llm import make_gemini
    from renderer import render

    started = time.monotonic()
    settings = load_settings()
    edition_date = edition_date or resolve_edition_date(publish_hour=settings.publish_hour, publish_days=settings.publish_days)
    start, end = collection_window(edition_date, settings.publish_hour, settings.publish_days)
    window_label = f"{start:%m-%d %H:%M} ~ {end:%m-%d %H:%M}"
    log.info("=== %s %s 호 제작 시작 (수집 %s KST) ===", settings.newspaper_title, edition_date, window_label)
    weather = _weather(settings)

    if demo:
        return _run_demo(settings, edition_date, weather, started)

    # 1단계: 수집 → 크롤링 → 중복 제거
    mails = fetch_mails(settings, start, end)
    articles = deduplicate(build_articles(mails))
    log.info("중복 제거 후 기사 %d건", len(articles))

    # 2단계: SNS 번역 → 편집 → 렌더링
    gemini = make_gemini(settings.gemini_api_key, settings.gemini_model) if use_llm else None
    paper = assemble(settings, edition_date, window_label, articles, gemini, OUTPUT_DIR, weather)

    if preview:
        path = render(paper, OUTPUT_DIR / "preview.html")
        log.info("=== 미리보기 완료 (발행 기록 없음): %s (%.1f초) ===", path, time.monotonic() - started)
        return 0

    path = publish(paper, settings, OUTPUT_DIR)
    _github_output(edition=edition_date.isoformat())
    log.info("=== 발행 완료: %s (기사 %d건, %.1f초) ===", path, len(articles), time.monotonic() - started)

    if newsletter or settings.newsletter_enabled:
        import newsletter as nl

        body = nl.build_html(paper, f"{settings.site_url}{path.name}" if settings.site_url else "")
        (OUTPUT_DIR / "_debug").mkdir(exist_ok=True)
        (OUTPUT_DIR / "_debug" / "newsletter.html").write_text(body, encoding="utf-8")
        nl.send(settings, paper, body)
    return 0


def _run_demo(settings: Settings, edition_date: date, weather, started: float) -> int:
    """샘플 기사로 이번 주(월요일~발행일)의 데모 신문들을 Output/_demo/ 에 만든다 (아카이브·이번 주 기능 확인용)."""
    import shutil

    import newsletter as nl
    from demo_data import sample_articles
    from filter_dedup import deduplicate

    shutil.rmtree(DEMO_DIR, ignore_errors=True)
    days = [edition_date - timedelta(days=i) for i in range(6, -1, -1)]
    days = [d for d in days if d.weekday() in settings.publish_days]
    for variant, day in enumerate(days, start=1):
        start, end = collection_window(day, settings.publish_hour, settings.publish_days)
        is_last = day == days[-1]
        articles = deduplicate(sample_articles(0 if is_last else variant, start))
        paper = assemble(settings, day, f"{start:%m-%d %H:%M} ~ {end:%m-%d %H:%M}", articles, None, DEMO_DIR, weather)
        path = publish(paper, settings, DEMO_DIR)
    (DEMO_DIR / "newsletter.html").write_text(nl.build_html(paper, path.name), encoding="utf-8")
    log.info("=== 데모 완료: %s (지난 신문: %s, %.1f초) ===", path, DEMO_DIR / "index.html", time.monotonic() - started)
    return 0


def _github_output(**values: str) -> None:
    """GitHub Actions 에서 실행 중이면 다음 단계가 쓸 값을 남긴다 (예: 커밋 메시지의 발행일)."""
    target = os.getenv("GITHUB_OUTPUT")
    if target:
        with open(target, "a", encoding="utf-8") as fh:
            fh.writelines(f"{k}={v}\n" for k, v in values.items())


def main() -> int:
    parser = argparse.ArgumentParser(description="나만의 신문 발행")
    parser.add_argument("--date", help="발행일 YYYY-MM-DD (기본: 가장 최근 발행일 08:00 기준)")
    parser.add_argument("--demo", action="store_true", help="샘플 기사로 Output/_demo/ 에 데모 신문 생성")
    parser.add_argument("--preview", action="store_true", help="실제 메일로 Output/preview.html 생성 (발행 기록 없음)")
    parser.add_argument("--no-llm", action="store_true", help="Gemini 를 쓰지 않고 규칙 기반으로 편집")
    parser.add_argument("--newsletter", action="store_true", help="발행 후 뉴스레터 메일 발송")
    args = parser.parse_args()

    setup_logging()
    try:
        return run(
            edition_date=date.fromisoformat(args.date) if args.date else None,
            demo=args.demo,
            use_llm=not args.no_llm,
            preview=args.preview,
            newsletter=args.newsletter,
        )
    except Exception:
        log.exception("신문 발행 실패")
        return 1


if __name__ == "__main__":
    sys.exit(main())
