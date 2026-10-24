# Roadmap.md — 작업 로드맵

## 0단계: 기획 문서 ✅
- [x] AGENT.md — 시스템 규격 / 작업 규칙
- [x] PRD.md — 요구사항 정의
- [x] Roadmap.md — 로드맵
- [x] `.gitignore`, `.env.example`(값 비움), `Image/` 디자인 레퍼런스

## 1단계: 데이터 수집 및 정제
- [ ] 가상환경 `.venv` + `requirements.txt`
- [ ] `Source/config.py` — .env 로딩, 전날 08:00 ~ 당일 08:00(KST) 수집 구간 계산
- [ ] `Source/models.py` — 데이터 모델
- [ ] `Source/gmail_imap.py` — IMAP SSL 접속, `News` 라벨 수집, 제목/본문/URL 파싱
- [ ] `Source/crawler.py` — Playwright 크롤러 (정형: 그대로 / 비정형: 링크 크롤링, X 폴백)
- [ ] `Source/filter_dedup.py` — 동일 URL + 제목 유사도 65% 중복 제거
- [ ] `Source/verify_stage1.py` — 1단계 검증 스크립트
- [ ] 실제 Gmail 수신 검증 — `.env`에 `GMAIL_USER`, `GMAIL_APP_PASSWORD` 입력 후 `verify_stage1.py` 실행 (사용자)

## 2단계: 편집 및 발행
- [ ] `Source/sns_helper.py` — SNS 한글 번역 + 짧은 헤드라인
- [ ] `Source/curator.py` — Gemini 중요도 평가(메인 1 / 부 2), 카테고리 분류, 2~3줄 요약, 폴백 편집
- [ ] `Source/templates/newspaper.html`, `style.css` — img_1~3 1:1 디자인
- [ ] `Source/renderer.py` — HTML 렌더러 (요약 justify, 출처 URL 링크)
- [ ] `Source/main.py` — 통합 파이프라인 → `Output/YYYY-MM-DD.html`
- [ ] `Source/scheduler.py`, `run_daily.bat`, `register_task.bat`(+`.ps1`) — 매일 08:00 자동 발행
- [ ] 실제 Gemini 편집 검증 — `.env`에 `GEMINI_API_KEY` 입력 후 `run_daily.bat` 실행 (사용자)

## 응용과제
- [ ] PC가 꺼져 있어도 발행 — `.github/workflows/daily-newspaper.yml` (GitHub Actions, 매일 08:00 KST)
- [ ] GitHub 저장소 Secrets 등록 후 Actions 수동 실행으로 검증 (사용자)
- [ ] 신문 디자인 개선 (보류)
- [ ] 월요일~금요일 발행 (보류)
