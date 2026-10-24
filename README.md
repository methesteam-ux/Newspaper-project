# Newspaper-project — 나만의 신문 만들기

스마트폰에서 관심 기사·SNS 게시물을 Gmail로 보내 두면, 매일 아침 08:00에 **Gmail `News` 라벨 메일을 모아
Gemini가 편집한 일간 신문 HTML**(`Output/YYYY-MM-DD.html`)을 발행합니다.

- 설계 문서: [AGENT.md](AGENT.md) · [PRD.md](PRD.md) · [Roadmap.md](Roadmap.md)
- 디자인 레퍼런스: [Image/](Image/)

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

- 수집 구간: 발행일 전날 08:00 ~ 당일 08:00 (KST)
- `GEMINI_API_KEY`가 비어 있으면 규칙 기반 편집(요약=본문 앞 2~3문장, 키워드 분류)으로 발행됩니다.
- 실행 로그: `Output/daily_run.log`

## 4. 자동 발행

| 방식 | 방법 | PC 상태 |
|------|------|---------|
| Windows 작업 스케줄러 | `register_task.bat` 우클릭 → 관리자 권한으로 실행 (해제: `register_task.bat -Unregister`) | 켜짐/절전 (꺼져 있었다면 켜진 직후 실행) |
| 파이썬 상주 데몬 | `.venv\Scripts\python.exe Source\scheduler.py` | 창을 켜 둔 동안 |
| **GitHub Actions** (응용과제) | 아래 참고 | **꺼져 있어도 됨** |

### GitHub Actions 설정

1. 저장소 **Settings > Secrets and variables > Actions**
   - Secrets: `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `GEMINI_API_KEY`
   - Variables(선택): `NEWSPAPER_TITLE`, `PUBLISHER_NAME`, `EDITION_NAME`
2. **Settings > Pages > Build and deployment > Source** 를 **GitHub Actions** 로 선택
3. **Actions** 탭 > *Daily Newspaper* > *Run workflow* 로 수동 실행해 확인
4. 이후 매일 08:00 KST(23:00 UTC)에 자동 실행되고, 발행된 `Output/YYYY-MM-DD.html`이 저장소에 커밋됩니다.
5. 신문은 GitHub Pages 에서 바로 읽을 수 있습니다: `https://<계정>.github.io/<저장소>/`
   - 첫 화면(`index.html`)은 지난 신문 목록, 최신호는 맨 위
   - 실행 로그는 Pages 에 올리지 않고 Actions 실행 페이지의 Artifacts 에서만 받을 수 있습니다.

> GitHub Pages 사이트는 **공개**됩니다(무료 플랜은 저장소도 public 이어야 Pages 사용 가능).
> 신문에는 수집한 기사 제목·요약·원문 링크만 들어가며, 메일 주소나 키는 포함되지 않습니다.

> GitHub Actions 봇이 저장소에 커밋하므로, 로컬에서 작업하기 전에 `git pull` 해 주세요.
