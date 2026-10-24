"""정기 자동 발행 켜기/끄기 (기본값: 모두 꺼짐).

자동 발행 경로는 두 가지이고, 둘 다 기본으로 꺼져 있다.
  - local : Windows 작업 스케줄러 (PC 가 켜져/절전 상태일 때)
  - cloud : GitHub Actions 정기 실행 (PC 가 꺼져 있어도)

'꺼짐'은 "조건에 걸려 건너뜀"이 아니라 아예 호출되지 않는 상태다.
  - local off : 작업 스케줄러에 작업 자체가 없음
  - cloud off : 워크플로 파일에 schedule 트리거가 없음 → GitHub 가 이 워크플로를 스스로 실행하지 않음
                (Actions 탭에서 'Run workflow'를 직접 누를 때만 실행)

사용법 (automation.bat 으로 실행 권장):
    automation.bat                 상태 보기
    automation.bat local on|off    Windows 작업 스케줄러 등록/삭제
    automation.bat cloud on|off    GitHub Actions 정기 실행 켜기/끄기 (커밋 후 push 여부를 물어봄)
    automation.bat cloud on --push 묻지 않고 push
발행 요일·시각은 .env 의 PUBLISH_DAYS(기본 mon-fri), PUBLISH_HOUR(기본 8)를 따른다.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys

from config import BASE_DIR, DAY_NAMES, describe_days, load_settings

WORKFLOW = BASE_DIR / ".github" / "workflows" / "daily-newspaper.yml"
WORKFLOW_REL = ".github/workflows/daily-newspaper.yml"
TASK_NAME = "MyDailyNewspaper_MorningPublish"
BEGIN = "  # >>> AUTOMATION:schedule"
END = "  # <<< AUTOMATION:schedule"
BLOCK_RE = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.DOTALL)


def _run(cmd: list[str], check: bool = False, timeout: int = 60) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, cwd=BASE_DIR, capture_output=True, timeout=timeout)
    proc.stdout = proc.stdout.decode("utf-8", errors="replace") if proc.stdout else ""
    proc.stderr = proc.stderr.decode("utf-8", errors="replace") if proc.stderr else ""
    if check and proc.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} 실패:\n{proc.stdout}{proc.stderr}")
    return proc


# ---------------------------------------------------------------- cloud
def utc_cron(days: tuple[int, ...], hour_kst: int) -> str:
    """KST 발행 요일/시각을 GitHub cron(UTC)으로. 예) 월~금 08:00 KST → '0 23 * * 0-4'."""
    hour_utc = hour_kst - 9
    shift = 0
    if hour_utc < 0:
        hour_utc += 24
        shift = -1
    # 파이썬 요일(월=0) → cron 요일(일=0)
    cron_days = sorted({((d + shift) % 7 + 1) % 7 for d in days})
    if len(cron_days) == 7:
        dow = "*"
    elif cron_days == list(range(cron_days[0], cron_days[-1] + 1)):
        dow = f"{cron_days[0]}-{cron_days[-1]}" if len(cron_days) > 1 else str(cron_days[0])
    else:
        dow = ",".join(map(str, cron_days))
    return f"0 {hour_utc} * * {dow}"


def _block(on: bool, days: tuple[int, ...], hour: int) -> str:
    head = f"{BEGIN} — automation.bat cloud on/off 로만 전환하세요 (직접 수정 금지)"
    if not on:
        body = [
            "  # (꺼짐) schedule 트리거 없음 → GitHub 가 이 워크플로를 스스로 실행하지 않습니다.",
            "  # 켜기: automation.bat cloud on",
        ]
    else:
        body = [
            "  schedule:",
            f'    - cron: "{utc_cron(days, hour)}" # {describe_days(days)} {hour:02d}:00 KST (GitHub 사정으로 수 분~수십 분 지연될 수 있음)',
        ]
    return "\n".join([head, *body, END])


def cloud_state(text: str) -> str:
    match = BLOCK_RE.search(text)
    # 블록이 없는 구버전 파일은 파일 전체에서 활성 schedule 을 찾는다.
    scope = match.group(0) if match else text
    if not match and not re.search(r"^\s+schedule:", text, re.MULTILINE):
        return "꺼짐"
    cron = re.search(r'^\s+- cron: "([^"]+)"', scope, re.MULTILINE)
    return f"켜짐 (cron '{cron.group(1)}' UTC)" if cron else "꺼짐"


def _remote_workflow() -> str | None:
    _run(["git", "fetch", "-q", "origin"], timeout=30)
    proc = _run(["git", "show", f"origin/main:{WORKFLOW_REL}"])
    return proc.stdout if proc.returncode == 0 else None


def cloud_set(on: bool, push: bool | None) -> int:
    settings = load_settings()
    text = WORKFLOW.read_text(encoding="utf-8")
    if not BLOCK_RE.search(text):
        print(f"[!] {WORKFLOW_REL} 에서 AUTOMATION 블록을 찾지 못했습니다.")
        return 1
    new_text = BLOCK_RE.sub(lambda _: _block(on, settings.publish_days, settings.publish_hour), text)
    label = "켜기" if on else "끄기"
    if new_text == text:
        print(f"[=] 로컬 워크플로 파일은 이미 '{cloud_state(text)}' 상태입니다.")
    else:
        WORKFLOW.write_text(new_text, encoding="utf-8", newline="\n")
        when = f" ({describe_days(settings.publish_days)} {settings.publish_hour:02d}:00 KST)" if on else ""
        _run(["git", "commit", "-m", f"chore: 클라우드 정기 발행 {label}{when}", "--", WORKFLOW_REL], check=True)
        print(f"[OK] 워크플로 파일 수정 후 커밋했습니다 → {cloud_state(new_text)}")

    remote = _remote_workflow()
    if remote is not None and cloud_state(remote) == cloud_state(new_text):
        print(f"[=] GitHub 에도 이미 반영되어 있습니다: {cloud_state(remote)}")
        return 0

    ahead = _run(["git", "log", "--oneline", "origin/main..HEAD"]).stdout.strip()
    print("\nGitHub 에 반영하려면 push 가 필요합니다. push 하면 아래 커밋이 모두 올라갑니다:")
    print("  " + (ahead.replace("\n", "\n  ") or "(없음)"))
    if push is None:
        if not sys.stdin.isatty():
            print("\n[!] 확인할 수 없는 환경이라 push 하지 않았습니다. 직접 'git push' 하거나 --push 를 붙이세요.")
            return 0
        push = input("\n지금 push 할까요? [y/N] ").strip().lower() in ("y", "yes")
    if not push:
        print("[i] push 하지 않았습니다. GitHub 는 아직 이전 상태로 동작합니다.")
        return 0
    proc = _run(["git", "push", "origin", "HEAD:main"], timeout=120)
    if proc.returncode != 0:
        print(f"[!] push 실패:\n{proc.stderr}")
        return 1
    print(f"[OK] push 완료 → GitHub 정기 실행: {cloud_state(new_text)}")
    if on:
        print("    (Secrets: GMAIL_USER, GMAIL_APP_PASSWORD, GEMINI_API_KEY 가 저장소에 등록되어 있어야 합니다)")
    return 0


# ---------------------------------------------------------------- local
def local_state() -> str:
    proc = _run(["powershell", "-NoProfile", "-Command",
                 f"$t = Get-ScheduledTask -TaskName '{TASK_NAME}' -ErrorAction SilentlyContinue; "
                 "if ($t) { [Console]::OutputEncoding=[Text.Encoding]::UTF8; "
                 "$d = ($t.Triggers | ForEach-Object { $_.DaysOfWeek }) -join ','; "
                 "Write-Output \"$($t.State)|$d\" }"])
    out = proc.stdout.strip()
    if not out:
        return "꺼짐 (작업 스케줄러에 등록된 작업 없음)"
    state, _, _ = out.partition("|")
    return f"켜짐 (작업 '{TASK_NAME}', 상태 {state})"


def local_set(on: bool) -> int:
    settings = load_settings()
    script = str(BASE_DIR / "register_task.ps1")
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script, "-TaskName", TASK_NAME]
    if on:
        days = ",".join(DAY_NAMES[d] for d in settings.publish_days)
        cmd += ["-Time", f"{settings.publish_hour:02d}:00", "-Days", days]
    else:
        if local_state().startswith("꺼짐"):
            print("[=] 이미 꺼져 있습니다 (등록된 작업 없음).")
            return 0
        cmd += ["-Unregister"]
    # 등록 스크립트의 안내 문구를 그대로 보여 준다.
    return subprocess.run(cmd, cwd=BASE_DIR).returncode


# ---------------------------------------------------------------- status
def status() -> int:
    settings = load_settings()
    print("=" * 66)
    print("  자동 발행 상태  (기본값: 모두 꺼짐)")
    print("=" * 66)
    print(f"발행 일정 설정 : {describe_days(settings.publish_days)} {settings.publish_hour:02d}:00 KST  (.env PUBLISH_DAYS / PUBLISH_HOUR)")
    print(f"[local] Windows 작업 스케줄러 : {local_state()}")
    print(f"[cloud] 워크플로 파일(로컬)   : {cloud_state(WORKFLOW.read_text(encoding='utf-8'))}")
    remote = _remote_workflow()
    print(f"[cloud] GitHub 실제 상태      : {cloud_state(remote) if remote else '확인 불가 (원격에 파일 없음/오프라인)'}")
    print("-" * 66)
    print("켜기/끄기: automation.bat local on|off   ·   automation.bat cloud on|off")
    print("수동 발행: run_daily.bat (언제든 1회 실행)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="정기 자동 발행 켜기/끄기 (기본: 꺼짐)")
    parser.add_argument("target", nargs="?", choices=["status", "local", "cloud"], default="status")
    parser.add_argument("switch", nargs="?", choices=["on", "off"])
    parser.add_argument("--push", action="store_true", help="cloud 변경 후 묻지 않고 push")
    parser.add_argument("--no-push", action="store_true", help="cloud 변경 후 push 하지 않음")
    args = parser.parse_args()

    if args.target == "status":
        return status()
    if not args.switch:
        parser.error("on 또는 off 를 지정하세요. 예) automation.bat cloud off")
    if args.target == "local":
        return local_set(args.switch == "on")
    push = True if args.push else (False if args.no_push else None)
    return cloud_set(args.switch == "on", push)


if __name__ == "__main__":
    sys.exit(main())
