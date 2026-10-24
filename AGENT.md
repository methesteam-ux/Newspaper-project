# AGENT.md — 나만의 신문 만들기 (My Daily Newspaper)

이 문서는 프로젝트에서 작업하는 개발자/AI 에이전트가 지켜야 할 **시스템 규격과 작업 규칙**을 정의한다.
제품 요구사항은 [PRD.md](PRD.md), 진행 순서는 [Roadmap.md](Roadmap.md)를 따른다.

## 1. 프로젝트 개요

스마트폰에서 관심 기사(네이버/다음 뉴스, X, Threads, Instagram, TikTok, YouTube 등)를 Gmail로 보내면,
Gmail 필터가 `News` 라벨을 붙이고, 이 프로그램이 매일 아침 08:00에 해당 메일을 모아
**LLM(Gemini)으로 편집한 일간 신문 HTML**(`Output/YYYY-MM-DD.html`)을 발행한다.

```
[스마트폰 공유] → [Gmail + News 라벨] → (IMAP 수집) → (Playwright 크롤링) → (중복 제거)
              → (Gemini 번역·중요도·분류·요약) → (Jinja2 렌더링) → Output/YYYY-MM-DD.html
```

## 2. 작업 단계

| 단계 | 범위 | 상태 |
|------|------|------|
| 1단계 | 가상환경, requirements.txt, Gmail IMAP 수집(News 라벨, 전날 08:00 ~ 당일 08:00), Playwright 크롤링(정형/비정형), 중복 기사 제거, 신문 메타데이터 | 완료 |
| 2단계 | Gemini 중요도 평가(메인 1 / 부 2 / 카테고리), SNS 한글 번역·헤드라인, 레퍼런스 이미지 1:1 디자인 템플릿, `Output/YYYY-MM-DD.html` 발행, 08:00 스케줄러 | 완료 |
| 응용과제 | PC가 꺼져 있어도 발행 — GitHub Actions 클라우드 실행 | 완료 |

> 정기 자동 발행(로컬 작업 스케줄러, GitHub Actions schedule)은 **기본값 꺼짐**이다. `automation.bat` 으로만 켜고 끈다.

## 3. 핵심 규칙

1. **비밀정보는 절대 커밋하지 않는다.** `GEMINI_API_KEY`, `GMAIL_APP_PASSWORD`, 쿠키/세션 파일은 `.env`(로컬) 또는
   GitHub Secrets(클라우드)에만 둔다. `.env`, `*cookies*.json`, `storage_state.json`, `secrets/`는 `.gitignore` 대상이다.
   저장소에는 값이 빈 `.env.example`만 둔다.
2. **수집 시간대**: 한국시간(KST, `Asia/Seoul`) 기준, 발행일 D의 신문은 `직전 발행일 08:00 ≤ 수신시각 < D 08:00` 메일만 대상으로 한다.
   발행 요일은 `PUBLISH_DAYS`(기본 월~금)이며, 월요일 호는 금 08:00 ~ 월 08:00(주말 포함)을 수집한다.
3. **IMAP 방식만 사용**: `imaplib` SSL(`imap.gmail.com:993`) + Gmail 앱 비밀번호. 메일은 `BODY.PEEK[]`로 읽어 읽음 표시를 바꾸지 않는다.
4. **크롤링은 Playwright**(Chromium headless)로 한다. 단, X(트위터)처럼 로그인 벽이 있는 경우에만 공개 API 폴백을 허용한다.
5. **정형 데이터(신문 기사)**: 기사 제목과 본문을 가공 없이 그대로 가져온다.
   **비정형 데이터(SNS 등)**: 링크를 크롤링해 본문·제목을 추출하고, 한국어로 번역한 뒤 본문을 참조해 짧은 기사 제목을 만든다.
6. **이미지는 있으면 표시, 없으면 없는 대로** 레이아웃을 구성한다(이미지가 없다고 기사를 버리지 않는다).
7. **LLM 실패 대비**: Gemini 키가 없거나 호출이 실패해도 신문은 반드시 발행되어야 한다(규칙 기반 폴백 편집).
8. 실행 시간은 20분 이내를 목표로 한다.

## 4. 디렉토리 구조 (Directory Structure)

```
Newspaper-project/
├── AGENT.md                  # 시스템 규격 및 에이전트 작업 규칙 (이 문서)
├── PRD.md                    # 1단계/2단계 제품 요구사항 정의서
├── Roadmap.md                # 단계별 작업 로드맵
├── README.md                 # 설치/실행 안내
├── requirements.txt          # 필수 라이브러리 목록
├── .env.example              # 환경설정 템플릿 (값은 비어 있음)
├── .gitignore
├── .gitattributes            # .bat/.ps1 CRLF 줄바꿈 고정
├── run_daily.bat             # 가상환경 기반 신문 발행 원클릭 실행
├── automation.bat            # 정기 자동 발행 켜기/끄기/상태 (기본: 모두 꺼짐)
├── register_task.bat         # = automation.bat local on (호환용)
├── register_task.ps1         # 실제 등록 로직 (WakeToRun, StartWhenAvailable)
├── .github/workflows/
│   └── daily-newspaper.yml   # [응용과제] GitHub Actions 클라우드 발행 + GitHub Pages 배포
├── Image/                    # 디자인 레퍼런스 이미지 (img_1 ~ img_3, 로컬 전용·저장소 미포함)
├── Output/                   # 신문(YYYY-MM-DD.html), 지난 신문(index.html), RSS(feed.xml), 발행 기록(data/*.json)
│                             #  로컬 전용: daily_run.log, preview.html, _demo/, _debug/
└── Source/
    ├── config.py             # .env 로딩, 발행 요일, 수집 시간대 계산
    ├── automation.py         # 정기 자동 발행 on/off (작업 스케줄러 / 워크플로 schedule 블록)
    ├── models.py             # Article / CuratedArticle / Newspaper 모델
    ├── gmail_imap.py         # [1단계] Gmail IMAP 수집 및 메일 파싱
    ├── crawler.py            # [1단계] Playwright 동적 크롤러 (정형/비정형)
    ├── filter_dedup.py       # [1단계] 중복 기사 제거 (URL + 제목 유사도 65%)
    ├── verify_stage1.py      # [1단계] 수집 파이프라인 검증 스크립트
    ├── llm.py                # [2단계] Gemini 공통 클라이언트 (스키마 고정 JSON, 재시도)
    ├── sns_helper.py         # [2단계] SNS 한글 번역 + 헤드라인 생성 (Gemini)
    ├── curator.py            # [2단계] 중요도 평가, 메인/부 헤드라인, 분류, 2~3줄 요약 (Gemini)
    ├── renderer.py           # [2단계] Jinja2 렌더러 (신문, 지난 신문 페이지, RSS)
    ├── archive.py            # [응용] 발행 기록: 호수, 이전/다음 호, 이번 주 1면, 예전 호 복원
    ├── insights.py           # [응용] 지면 데이터: 분야 분포, 도착 시간대, 출처 수, 분야 색
    ├── weather.py            # [응용] 제호 옆 날씨 (Open-Meteo, 키 불필요)
    ├── newsletter.py         # [응용] 뉴스레터 메일 (기본 꺼짐)
    ├── templates/
    │   ├── newspaper.html    # 신문 지면 템플릿
    │   ├── newspaper.js      # 지면 인터랙션 (테마, 검색, 음성, 읽음 표시, 단축키)
    │   ├── index.html        # 지난 신문 (GitHub Pages 첫 화면: 최신호, 달력, 검색)
    │   ├── feed.xml          # RSS 2.0
    │   └── style.css         # 지면 스타일 (img_1~3 레이아웃 골격 + 클래식 신문 디자인, 3가지 테마)
    ├── main.py               # 전체 파이프라인 통합 CLI
    ├── demo_data.py          # --demo 샘플 기사 (이번 주 데모 신문 → Output/_demo/)
    └── scheduler.py          # 파이썬 상주형 발행 데몬 (직접 실행할 때만 동작)
```

## 5. 모듈 규격

1. **설정 (`Source/config.py`)**: `.env`를 읽어 `Settings`를 만든다. `collection_window(edition_date)`가 `(start, end)`를 KST로 반환한다.
   `edition_date`가 없으면 "현재 시각 기준 가장 최근의 08:00"을 끝으로 잡는다.
2. **Gmail IMAP 수집기 (`Source/gmail_imap.py`)**:
   - `imaplib` SSL 접속, 라벨 폴더(`"News"`) SELECT(비ASCII 라벨은 IMAP modified UTF-7 인코딩).
   - `SINCE`로 1차 검색 후 `INTERNALDATE`로 시간대 정밀 필터.
   - 제목(MIME 디코딩), text/plain·text/html 본문, 본문 내 URL 목록을 `RawMail`로 반환.
3. **크롤러 (`Source/crawler.py`)**:
   - 메일 본문이 충분히 길면(정형: 뉴스레터/기사 전문) 메일 제목·본문을 그대로 사용하고 링크에서는 대표 이미지만 보강.
   - 그 외에는 Playwright로 링크를 열어(단축 URL 리다이렉트 포함) `og:*` 메타, 사이트별 본문 셀렉터(네이버/다음/일반 `article`), 대표 이미지 추출.
   - SNS 도메인(x.com, twitter.com, threads, instagram, tiktok, youtube, facebook)은 `is_sns=True`.
   - X는 `tweetText` 셀렉터 → 실패 시 `api.fxtwitter.com` 폴백.
4. **중복 제거 (`Source/filter_dedup.py`)**: 정규화된 URL 동일 또는 제목 유사도 ≥ 0.65이면 같은 기사로 보고,
   본문이 더 긴 1건만 남긴다. 병합된 건수는 `mention_count`로 기록해 "언급이 많은 기사" 신호로 쓴다.
5. **SNS 헬퍼 (`Source/sns_helper.py`)**: SNS 본문을 한국어로 번역하고 짧은 기사형 제목을 만든다. 원문은 `original_body`에 보관.
6. **큐레이터 (`Source/curator.py`)**: Gemini에 전체 기사 목록을 한 번에 보내 JSON(스키마 고정)으로
   메인 1건, 부 헤드라인 2건, 기사별 카테고리와 2~3문장 요약을 받는다. 실패 시 `mention_count`·본문 길이·이미지 유무 기반 폴백.
7. **렌더러 (`Source/renderer.py`)**: `templates/newspaper.html` + `style.css`(인라인)로 단일 HTML 파일을 만든다.
   - 헤더: 신문 이름, `YYYY-MM-DD 발행 (에디션)`, 발행인.
   - 메인: 1단 와이드 카드, `🔥 최고 주요 소식` 배지, 큰 이미지, 중앙 정렬 제목·요약.
   - 부 헤드라인: 2단 카드(메인의 1/2 폭).
   - 나머지: 카테고리 제목 + 2단(CSS columns) 목록, 제목/요약/썸네일(우측)/출처.
   - 요약은 2~3줄, `text-align: justify`. 출처는 **원문 URL 링크**로 표시.
8. **통합 CLI (`Source/main.py`)**: `python Source/main.py [--date YYYY-MM-DD] [--preview] [--demo] [--no-llm] [--newsletter]`.
9. **스케줄러 (기본: 모두 꺼짐)**: `run_daily.bat`(수동 1회 실행, `Output/daily_run.log` 기록),
   `scheduler.py`(직접 띄운 동안만 동작하는 상주형),
   `automation.bat local on|off`(Windows 작업 스케줄러: 발행 요일 08:00, WakeToRun, StartWhenAvailable / off = 작업 삭제),
   `automation.bat cloud on|off`(`.github/workflows/daily-newspaper.yml` 의 `AUTOMATION:schedule` 블록 전환 후 커밋·push.
   off = schedule 트리거 자체가 없어 GitHub 가 워크플로를 호출하지 않음. 수동 *Run workflow* 만 가능).
   워크플로는 결과를 커밋하고 GitHub Pages 로 배포한다. `AUTOMATION` 블록은 손으로 고치지 않는다.
10. **로그 공개 주의**: 로그는 Artifacts 로 공개될 수 있으므로 메일 주소·키를 로그에 남기지 않는다. Pages 에는 HTML 만 올린다.

### 응용과제 — 디자인·부가 기능 규격
- 기본 레이아웃(메인 1단 / 부 2단 / 분야별 2단 + 썸네일, 요약 2~3줄 justify, 출처 URL)은 유지하고, 그 위에 지면을 더한다.
- 부가 지면(브리핑, 편집장 한마디, 숫자, 키워드, 왜 중요한가)은 Gemini 편집 결과(`EditorialPlan`)에서 오며,
  숫자는 본문에 있는 값만 허용한다. LLM 이 없으면 `curator.py` 의 규칙 기반 폴백을 쓴다.
- 지면은 단일 HTML 파일(CSS/JS 인라인)로 유지한다. JS 가 꺼져 있어도 내용은 모두 보여야 한다(`.js` 클래스로만 애니메이션).
- 브라우저 저장소(테마, 글자 크기, 읽음 표시)는 개인 편의 기능이며 실패해도 지면은 정상 동작해야 한다.
- 날씨·뉴스레터 등 외부 호출은 실패해도 발행을 막지 않는다. 뉴스레터는 기본 꺼짐.

## 6. 환경 변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `GEMINI_API_KEY` | Google AI Studio API 키 | (비움 → 폴백 편집) |
| `GEMINI_MODEL` | 사용할 Gemini 모델 | `gemini-flash-latest` |
| `GMAIL_USER` | Gmail 주소 | (필수) |
| `GMAIL_APP_PASSWORD` | 16자리 앱 비밀번호 | (필수) |
| `GMAIL_LABEL` | 수집 대상 라벨 | `News` |
| `GMAIL_IMAP_SERVER` / `GMAIL_IMAP_PORT` | IMAP 서버 | `imap.gmail.com` / `993` |
| `NEWSPAPER_TITLE` | 신문 이름 | `My Tech Daily` |
| `PUBLISHER_NAME` | 발행인 | `Publisher` |
| `EDITION_NAME` | 에디션(편집인) 이름 | `My 에디션` |
| `PUBLISH_HOUR` | 발행·수집 기준 시각(시) | `8` |
| `PUBLISH_DAYS` | 발행 요일 (`mon-fri`, `daily`, `mon,wed,fri` …) | `mon-fri` |
| `TAGLINE` | 제호 위 한 줄 소개 | `AI 편집장이 고른 오늘의 테크 뉴스` |
| `WEATHER_ENABLED` / `WEATHER_CITY` / `WEATHER_LAT` / `WEATHER_LON` | 제호 옆 날씨 | `true` / 서울 |
| `SITE_URL` | GitHub Pages 주소 (RSS·QR·OG) | git origin 에서 자동 추정 |
| `NEWSLETTER_ENABLED` / `NEWSLETTER_TO` | 뉴스레터 메일 발송 / 받는 사람 | `false` / `GMAIL_USER` |

## 7. 작업 규칙 (에이전트용)

- 단계 경계를 지킨다. 사용자가 다음 단계 시작을 명시하기 전에는 범위를 넘어 구현하지 않는다.
- 작업이 끝나면 AGENT.md / PRD.md / Roadmap.md의 상태를 갱신하고 커밋한다. `git push`는 사용자가 직접 한다.
- 실제 Gmail/Gemini 자격 증명 없이 확인할 때는 `--demo`(샘플 기사)와 `--no-llm` 옵션을 사용한다.
