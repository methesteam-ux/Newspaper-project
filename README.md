# Newspaper-project — 나만의 신문 만들기

스마트폰에서 관심 기사·SNS 게시물을 Gmail로 보내 두면, **Gmail `News` 라벨 메일을 모아
Gemini가 편집한 신문 HTML**(`Output/YYYY-MM-DD.html`)을 발행합니다. 발행 일정은 월~금 08:00(KST)이며,
**정기 자동 발행은 기본으로 꺼져 있습니다** (켜는 방법은 4절).

- 설계 문서: [AGENT.md](AGENT.md) · [PRD.md](PRD.md) · [Roadmap.md](Roadmap.md)
- 디자인 레퍼런스: 로컬 `Image/img_1~3.png` (강의 자료 스크린샷이라 저장소에는 포함하지 않음)

## 1. 설치

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m playwright install chromium
copy .env.example .env
```

## 2. `.env` 설정 (직접 입력, GitHub에 올라가지 않음)

| 항목 | 발급/설정 방법 |
|------|----------------|
| `GEMINI_API_KEY` | https://aistudio.google.com/api-keys 에서 키 생성 |
| `GMAIL_USER` | Gmail 주소 |
| `GMAIL_APP_PASSWORD` | https://myaccount.google.com/apppasswords (2단계 인증 필요) 16자리 |
| `NEWSPAPER_TITLE`, `PUBLISHER_NAME`, `EDITION_NAME` | 신문 이름 / 발행인 / 에디션 |
| `PUBLISH_DAYS`, `PUBLISH_HOUR` | 발행 요일(기본 `mon-fri`) / 시각(기본 `8`) |

Gmail 준비:
1. 라벨 `News` 만들기 → 필터(보낸 사람 또는 제목 `[신문]`)로 라벨 자동 적용
2. 설정 > 라벨 > `News` 의 **IMAP에 표시** 체크

## 3. 실행

```powershell
.venv\Scripts\python.exe Source\verify_stage1.py   # 1단계 검증 (Gmail 수신·크롤링·중복 제거)
run_daily.bat                                      # 오늘자 신문 발행 → Output\YYYY-MM-DD.html
run_daily.bat --date 2026-10-24                    # 특정 발행일
run_daily.bat --demo                               # 샘플 기사로 레이아웃 확인 → Output\demo.html
```

- 수집 구간: 직전 발행일 08:00 ~ 발행일 08:00 (KST). 월~금 발행이면 **월요일 호는 금 08:00 ~ 월 08:00**(주말 메일 포함)
- 주말에 날짜 없이 실행하면 가장 최근 발행일(금요일) 호가 만들어집니다.
- `GEMINI_API_KEY`가 비어 있으면 규칙 기반 편집(요약=본문 앞 2~3문장, 키워드 분류)으로 발행됩니다.
- 실행 로그: `Output/daily_run.log`

## 4. 자동 발행 (기본값: 모두 꺼짐)

정기 자동 발행은 **기본으로 전부 꺼져 있고**, 꺼진 상태에서는 아무것도 스스로 실행되지 않습니다.
- 로컬: 작업 스케줄러에 작업 자체가 없음
- GitHub: 워크플로에 `schedule` 트리거가 없음 → GitHub 가 워크플로를 호출하지 않음 (Actions 탭에서 직접 *Run workflow* 를 누를 때만 실행)

켜고 끄는 방법은 `automation.bat` 하나로 통일되어 있습니다. 발행 요일·시각은 `.env`의 `PUBLISH_DAYS`/`PUBLISH_HOUR`를 따릅니다.

```powershell
automation.bat                 # 현재 상태 보기 (로컬 / 워크플로 파일 / GitHub 실제 상태)
automation.bat local on        # Windows 작업 스케줄러 등록 (월~금 08:00, 절전 시 깨우기, 놓친 작업 즉시 실행)
automation.bat local off       # 작업 삭제
automation.bat cloud on        # GitHub Actions 정기 실행 켜기 → 커밋 후 push 여부를 물어봄
automation.bat cloud off       # 정기 실행 끄기 (schedule 트리거 제거)
```

| 방식 | 켜기 | PC 상태 |
|------|------|---------|
| Windows 작업 스케줄러 | `automation.bat local on` | 켜짐/절전 (꺼져 있었다면 켜진 직후 실행) |
| 파이썬 상주 데몬 | `.venv\Scripts\python.exe Source\scheduler.py` (창을 켜 둔 동안만) | 켜짐 |
| **GitHub Actions** (응용과제) | `automation.bat cloud on` + push | **꺼져 있어도 됨** |

> `cloud on/off`는 GitHub 에 push 해야 실제로 반영됩니다. push 하면 그동안 로컬에만 있던 커밋도 함께 올라가므로,
> 도구가 올라갈 커밋 목록을 보여 주고 확인을 받습니다.

### GitHub Actions 설정

1. 저장소 **Settings > Secrets and variables > Actions**
   - Secrets: `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `GEMINI_API_KEY`
   - Variables(선택): `NEWSPAPER_TITLE`, `PUBLISHER_NAME`, `EDITION_NAME`
2. **Settings > Pages > Build and deployment > Source** 를 **GitHub Actions** 로 선택
3. **Actions** 탭 > *Daily Newspaper* > *Run workflow* 로 수동 실행해 확인 (정기 실행이 꺼져 있어도 수동 실행은 가능)
4. 정기 실행을 켜면(`automation.bat cloud on`) 월~금 08:00 KST에 실행되고, 발행된 `Output/`이 저장소에 커밋됩니다.
5. 신문은 GitHub Pages 에서 바로 읽을 수 있습니다: `https://<계정>.github.io/<저장소>/`
   - 첫 화면(`index.html`)은 지난 신문 목록, 최신호는 맨 위
   - 실행 로그는 Pages 에 올리지 않고 Actions 실행 페이지의 Artifacts 에서만 받을 수 있습니다.

> GitHub Pages 사이트는 **공개**됩니다(무료 플랜은 저장소도 public 이어야 Pages 사용 가능).
> 신문에는 수집한 기사 제목·요약·원문 링크만 들어가며, 메일 주소나 키는 포함되지 않습니다.

> GitHub Actions 봇이 저장소에 커밋하므로, 로컬에서 작업하기 전에 `git pull` 해 주세요.
