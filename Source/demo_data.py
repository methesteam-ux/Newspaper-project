"""--demo 용 샘플 기사 (Gmail/Gemini 자격 증명 없이 레이아웃 확인용)."""
from __future__ import annotations

from datetime import datetime

from config import KST
from models import Article


def _img(seed: str) -> str:
    return f"https://picsum.photos/seed/{seed}/800/450"


def sample_articles() -> list[Article]:
    now = datetime.now(KST)
    rows = [
        ("지멘스·TSMC, AI 기반 반도체 설계 자동화 고도화…공동 혁신 통해 생산성 향상",
         "지멘스 EDA 사업부가 TSMC와 협력하여 인공지능(AI) 기반 반도체 설계 자동화 기술을 한층 고도화합니다. "
         "양사는 TSMC 오픈 이노베이션 플랫폼(OIP) 생태계를 기반으로 반도체 설계 워크플로우 전반에 걸쳐 혁신을 추진합니다. "
         "공동 고객의 생산성 향상과 설계 주기 단축을 목표로 합니다. 이는 복잡해지는 첨단 반도체 설계 환경에서 AI 기술이 핵심 역할을 할 것임을 보여줍니다.",
         "https://www.aitimes.kr/news/articleView.html?idxno=42200", _img("chip"), 3, False),
        ("아마존서 '음성 AI' 개발하다가 '피지컬 AI' 로봇 회사 수장으로…보스턴다이내믹스 CEO 선임",
         "보스턴다이내믹스가 아마존에서 인공지능(AI) 조직을 이끌어 온 인사를 신임 최고경영자(CEO)로 영입했다. "
         "AI와 로보틱스를 결합한 '피지컬 AI' 분야의 경쟁력을 끌어올리기 위한 인사다. 보스턴다이내믹스는 휴머노이드 아틀라스 등 차세대 로봇 개발에 박차를 가할 계획이다.",
         "https://www.hankyung.com/article/2026100773991", _img("robot"), 2, False),
        ("Meta published a paper that might end the transformer era.",
         "Meta published a paper that might end the transformer era.\nFor the last seven years, every major AI has been built on the exact same architecture.\n"
         "Transformer.\nBut Transformers have a massive, expensive flaw.",
         "https://x.com/example/status/2081285857605962370", _img("paper"), 1, True),
        ("노벨 물리학상에 '뉴트리노 관측' 연구자…천체물리학 발전 기여",
         "올해 노벨 물리학상은 우주에서 날아오는 뉴트리노 관측에 지대한 공헌을 한 물리학자에게 돌아갔다. "
         "스웨덴 왕립과학원 노벨위원회는 아이스큐브 뉴트리노 관측소에 대한 결정적 기여와 천체물리학 발전에 기여한 업적을 높이 평가했다.",
         "https://www.youtube.com/watch?v=example", _img("space"), 1, False),
        ("인천대, 공학페스티벌 성황리 개최…새로운 시작과 글로벌 도약을 꿈꾸다",
         "인천대학교가 제12회 공학페스티벌 주간 행사를 성황리에 개최하며 공학 교육과 연구의 새 지평을 열었다. "
         "이번 행사에는 주요 기업 현직 졸업생들이 참여해 산학 연계의 중요성을 강조했다.",
         "https://n.news.naver.com/mnews/article/000/0000000001", _img("campus"), 1, False),
        ("벡터 데이터베이스여, 안녕 | GeekNews",
         "벡터 데이터베이스 turbopuffer가 v3 개편을 통해 문서와 벡터 인덱스의 배치를 분리하는 저장 구조 개편을 추진 중이다. "
         "v3는 문서 저장소를 분리하여 속성 필터링과 전문 검색, 집계 쿼리 성능을 최적화했다.",
         "https://news.hada.io/topic?id=00000", _img("database"), 1, False),
        ("리눅스 커널, LLM 취약점 보고서 검증과 보안 대응책 발표",
         "리눅스 커널 보안팀이 LLM이 생성한 취약점 보고서가 급증함에 따라 검증 절차와 대응 정책을 발표했다. "
         "재현 가능한 증거가 없는 자동 생성 보고서는 우선순위를 낮추기로 했다.",
         "https://news.hada.io/topic?id=00001", "", 1, False),
        ("MS, 실시간 전사·음성합성 AI 모델 3종 공개",
         "마이크로소프트가 실시간 음성 전사 모델 1종과 음성합성 모델 2종을 포함한 신규 AI 모델을 공개했다. "
         "핵심인 스트리밍 전사 모델은 320밀리초 내에 첫 전사 결과를 제공하며 60개 이상의 언어를 지원한다.",
         "https://n.news.naver.com/mnews/article/000/0000000002", _img("microsoft"), 1, False),
    ]
    return [
        Article(title=t, body=b, url=u, image_url=img, source_name="데모", published_at=now,
                is_sns=sns, mention_count=mc, kind="crawled")
        for t, b, u, img, mc, sns in rows
    ]
