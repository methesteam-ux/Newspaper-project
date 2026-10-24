# Roadmap.md — 작업 로드맵

## 0단계: 기획 문서 ✅
- [x] AGENT.md — 시스템 규격 / 작업 규칙
- [x] PRD.md — 요구사항 정의
- [x] Roadmap.md — 로드맵
- [x] `.gitignore`, `.env.example`(값 비움), `Image/` 디자인 레퍼런스(로컬 전용)

## 1단계: 데이터 수집 및 정제 ✅
- [x] 가상환경 `.venv` + `requirements.txt`
- [x] `Source/config.py` — .env 로딩, 전날 08:00 ~ 당일 08:00(KST) 수집 구간 계산
- [x] `Source/models.py` — 데이터 모델
- [x] `Source/gmail_imap.py` — IMAP SSL 접속, `News` 라벨 수집, 제목/본문/URL 파싱
- [x] `Source/crawler.py` — Playwright 크롤러 (정형: 그대로 / 비정형: 링크 크롤링, X 폴백)
- [x] `Source/filter_dedup.py` — 동일 URL + 제목 유사도 65% 중복 제거
- [x] `Source/verify_stage1.py` — 1단계 검증 스크립트
- [x] 실제 Gmail 수신 검증 — `verify_stage1.py` (News 라벨 5건 수신 확인)

## 2단계: 편집 및 발행 ✅
- [x] `Source/sns_helper.py` — SNS 한글 번역 + 짧은 헤드라인
- [x] `Source/curator.py` — Gemini 중요도 평가(메인 1 / 부 2), 카테고리 분류, 2~3줄 요약, 폴백 편집
- [x] `Source/templates/newspaper.html`, `style.css` — img_1~3 1:1 디자인
- [x] `Source/renderer.py` — HTML 렌더러 (요약 justify, 출처 URL 링크)
- [x] `Source/main.py` — 통합 파이프라인 → `Output/YYYY-MM-DD.html`
- [x] `Source/scheduler.py`, `run_daily.bat`, `register_task.bat`(+`.ps1`) — 매일 08:00 자동 발행
- [x] 실제 Gemini 편집 검증 — GitHub Actions 수동 실행으로 10/25호 발행

## 응용과제
- [x] PC가 꺼져 있어도 발행 — `.github/workflows/daily-newspaper.yml` (GitHub Actions, 정기 실행은 `automation.bat cloud on`)
- [x] GitHub Pages 배포 — `Output/index.html`(지난 신문 목록) + 신문 HTML 공개
- [x] GitHub 저장소 Secrets 등록, Pages Source = GitHub Actions 설정 후 Actions 수동 실행으로 검증
- [x] 신문 디자인 개선 — 클래식 제호·이중 괘선·귀퉁이(호수·날씨), 티커, 라이트/종이/다크 테마, 모바일, 인쇄 레이아웃
- [x] 부가 기능 — 3줄 브리핑·편집장 한마디·숫자로 보는 오늘·키워드·왜 중요한가, 음성 듣기, 검색·필터,
      읽음 표시, 지면 데이터 그래프, 이번 주 1면, 이전/다음 호, 발행 달력·전체 검색, RSS, QR, (선택) 뉴스레터
- [x] 월요일~금요일 발행 — `PUBLISH_DAYS`(기본 mon-fri), 월요일 호는 주말 메일 포함
- [x] 정기 자동 발행 기본 꺼짐 + 켜기 옵션 — `automation.bat local|cloud on|off`
