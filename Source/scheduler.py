"""파이썬 상주형 발행 데몬 — 발행 요일(기본 월~금) PUBLISH_HOUR(기본 08:00)에 main.py 를 실행한다.

직접 실행해서 창을 띄워 둔 동안만 동작한다(기본으로는 실행되지 않음).
PC 를 켜 두지 않아도 되는 방식은 automation.bat local on(작업 스케줄러) / cloud on(GitHub Actions).

사용법:
    .venv\\Scripts\\python.exe Source\\scheduler.py [--now]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime

import schedule

from config import BASE_DIR, DAY_NAMES, SOURCE_DIR, describe_days, load_settings

_WEEKDAY_JOBS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def publish() -> None:
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 신문 발행 시작", flush=True)
    # 매 회차를 새 프로세스로 실행해 Playwright/네트워크 상태가 누적되지 않게 한다.
    result = subprocess.run([sys.executable, str(SOURCE_DIR / "main.py")], cwd=BASE_DIR)
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 종료 코드 {result.returncode}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--now", action="store_true", help="시작하자마자 한 번 발행")
    args = parser.parse_args()

    settings = load_settings()
    at = f"{settings.publish_hour:02d}:00"
    for day in settings.publish_days:
        getattr(schedule.every(), _WEEKDAY_JOBS[day]).at(at).do(publish)
    print(f"스케줄러 시작: {describe_days(settings.publish_days)} {at}(PC 로컬 시간) 발행. 종료하려면 Ctrl+C", flush=True)
    print("  예정: " + ", ".join(DAY_NAMES[d] for d in settings.publish_days), flush=True)
    if args.now:
        publish()
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("스케줄러 종료")
