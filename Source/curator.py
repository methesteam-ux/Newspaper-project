"""[2단계] 편집장 — 중요도 평가(메인 1 / 부 헤드라인 2), 카테고리 분류, 2~3줄 요약,
그리고 부가 지면(3줄 브리핑, 편집장 한마디, 숫자로 보는 오늘, 키워드, 왜 중요한가).

Gemini 가 없거나 실패하면 언급 횟수·본문 길이·이미지 유무 기반 규칙으로 편집한다.
"""
from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from pydantic import BaseModel

from llm import Gemini
from models import Article, CuratedArticle

log = logging.getLogger(__name__)

CATEGORIES = [
    "AI/ML", "반도체/하드웨어", "로봇", "데이터", "보안", "개발/소프트웨어",
    "과학/연구", "교육/산업협력", "경제/산업", "사회", "기타",
]
SUB_HEADLINES = 2
SUMMARY_MAX_CHARS = 230
READ_CHARS_PER_MIN = 500  # 한국어 기사 평균 읽기 속도


class ArticleEdit(BaseModel):
    id: int
    category: str
    summary: str
    importance: int
    keywords: list[str]
    why_it_matters: str


class NumberFact(BaseModel):
    value: str
    label: str


class EditorialPlan(BaseModel):
    main_id: int
    sub_ids: list[int]
    articles: list[ArticleEdit]
    briefing: list[str]
    editor_note: str
    numbers: list[NumberFact]


@dataclass
class Curation:
    main: CuratedArticle | None
    subs: list[CuratedArticle]
    sections: list[tuple[str, list[CuratedArticle]]]
    briefing: list[str] = field(default_factory=list)
    editor_note: str = ""
    numbers: list[tuple[str, str]] = field(default_factory=list)
    keywords: list[tuple[str, int]] = field(default_factory=list)
    llm_used: bool = False

    @property
    def all(self) -> list[CuratedArticle]:
        items = ([self.main] if self.main else []) + self.subs
        return items + [c for _, group in self.sections for c in group]


PROMPT = """너는 일간 테크 신문의 편집장이다. 오늘 수집된 기사 목록을 보고 지면을 편집하라.

[편집 규칙]
1. 중요도(importance, 1~100): 그날 여러 번 언급된 기사(mention_count 가 클수록), 산업·사회적 파급력,
   새로움, 독자 관심도를 기준으로 평가한다.
2. main_id: 가장 중요한 기사 1건 (1면 메인 헤드라인). 가능하면 이미지가 있는 기사(has_image=true)를 우선한다.
3. sub_ids: 메인 다음으로 중요한 기사 {subs}건 (부 헤드라인). main_id 와 겹치면 안 되며,
   메인과 같은 사건을 다룬 기사보다는 다른 소식을 우선한다.
4. category: 다음 중 하나를 고른다. 꼭 맞는 것이 없을 때만 짧은 새 분류명(2~8자)을 쓴다.
   {categories}
5. summary: 한국어 신문체로 2~3문장, 공백 포함 120~{max_chars}자. 2~3줄 분량을 넘기지 않는다.
   본문에 있는 사실만 쓰고, 추측·과장·새로운 수치를 만들지 않는다.
6. keywords: 기사마다 핵심어 2~4개 (고유명사·기술 용어 우선, 각 2~12자, 조사 없이).
7. why_it_matters: 독자에게 이 기사가 왜 중요한지 한 문장 (60자 이내).
8. articles 에는 입력된 모든 기사(id)를 빠짐없이 포함한다.

[부가 지면]
9. briefing: 오늘 지면 전체를 3줄로 요약한다. 각 줄은 서로 다른 소식, 45자 이내, "~했다/~이다" 체.
10. editor_note: '편집장 한마디' 1~2문장 (90자 이내). 오늘 기사들을 관통하는 흐름을 짚는 짧은 논평.
11. numbers: 기사 본문에 실제로 등장하는 인상적인 수치 최대 3개.
    value 는 숫자+단위만 (예: "69%", "12억 명", "320ms"), label 은 그 수치가 뜻하는 것 (25자 이내).
    본문에 없는 숫자를 만들면 안 되며, 마땅한 수치가 없으면 빈 목록으로 둔다.

[기사 목록 JSON]
{articles}
"""


# ------------------------------------------------------------------ 폴백 규칙
def _sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    return [s.strip() for s in re.split(r"(?<=[.!?。])\s+|(?<=다\.)\s*", text) if s.strip()]


def fallback_summary(body: str, max_chars: int = SUMMARY_MAX_CHARS) -> str:
    """본문 앞부분에서 2~3문장을 뽑아 요약으로 쓴다."""
    out = ""
    for i, sent in enumerate(_sentences(body)):
        if i >= 3 or (out and len(out) + len(sent) > max_chars):
            break
        out = f"{out} {sent}".strip()
    if not out:
        out = re.sub(r"\s+", " ", body).strip()
    return out if len(out) <= max_chars else out[: max_chars - 1].rstrip() + "…"


_KEYWORDS = [
    ("보안", r"보안|해킹|취약점|랜섬웨어|security|CVE|malware"),
    ("반도체/하드웨어", r"반도체|칩|GPU|TSMC|엔비디아|NVIDIA|파운드리|HBM|하드웨어"),
    ("로봇", r"로봇|휴머노이드|robot"),
    ("데이터", r"데이터베이스|데이터|DB|벡터|database|SQL"),
    ("AI/ML", r"AI|인공지능|LLM|GPT|Gemini|제미니|Claude|클로드|머신러닝|딥러닝|모델|트랜스포머"),
    ("교육/산업협력", r"대학|교육|학생|캠퍼스|산학"),
    ("과학/연구", r"연구|논문|과학|물리|노벨|우주|천문|science"),
    ("개발/소프트웨어", r"개발|오픈소스|소프트웨어|프로그래밍|코드|github|Docker"),
    ("경제/산업", r"경제|주가|투자|매출|시장|기업|인수|CEO"),
]


def fallback_category(article: Article) -> str:
    text = f"{article.title} {article.body[:600]}"
    for cat, pattern in _KEYWORDS:
        if re.search(pattern, text, re.IGNORECASE):
            return cat
    return "기타"


def _fallback_score(article: Article) -> int:
    return article.mention_count * 20 + (10 if article.image_url else 0) + min(len(article.body) // 300, 10)


_STOPWORDS = {
    "있다", "했다", "한다", "위해", "통해", "대한", "관련", "이번", "오늘", "지난", "기자", "뉴스",
    "the", "and", "for", "with", "that", "this", "from", "종합", "단독", "속보", "공개", "발표",
    "기반", "가장", "최근", "새로운", "국내", "전체", "올해", "있는", "없는", "하는", "되는", "등을",
    "published", "paper", "might", "end", "era", "every", "over", "just", "more", "have", "has", "been", "will", "was", "are", "its", "into", "about",
}
_JOSA_RE = re.compile(r"(으로|에서|에게|까지|부터|이며|이다|하는|했다|한다|으로써|은|는|이|가|을|를|의|에|로|와|과|도|만)$")


def fallback_keywords(text: str, limit: int = 3) -> list[str]:
    words = []
    for tok in re.findall(r"[A-Za-z][A-Za-z0-9.+-]{1,}|[가-힣]{2,}", text):
        tok = _JOSA_RE.sub("", tok) if re.match(r"[가-힣]", tok) else tok.rstrip(".+-")
        if len(tok) >= 2 and tok.lower() not in _STOPWORDS:
            words.append(tok)
    return [w for w, _ in Counter(words).most_common(limit)]


_NUMBER_RE = re.compile(r"\d[\d,.]*\s?(?:%|배|억\s?명|만\s?명|억\s?원|조\s?원|억|조|만|달러|ms|밀리초|개국)")


def fallback_numbers(items: list[CuratedArticle], limit: int = 3) -> list[tuple[str, str]]:
    out = []
    for c in items:
        match = _NUMBER_RE.search(c.summary)
        if match:
            label = c.article.title if len(c.article.title) <= 25 else c.article.title[:24] + "…"
            out.append((match.group(0).replace(" ", ""), label))
        if len(out) >= limit:
            break
    return out


def reading_minutes(text: str) -> int:
    return max(1, math.ceil(len(text) / READ_CHARS_PER_MIN))


# ------------------------------------------------------------------ LLM 편집
def _plan_with_llm(articles: list[Article], gemini: Gemini) -> EditorialPlan | None:
    payload = [
        {
            "id": i,
            "title": a.title,
            "source": a.source_name,
            "is_sns": a.is_sns,
            "mention_count": a.mention_count,
            "has_image": bool(a.image_url),
            "body": a.body[:1500],
        }
        for i, a in enumerate(articles)
    ]
    prompt = PROMPT.format(
        subs=SUB_HEADLINES,
        categories=", ".join(CATEGORIES),
        max_chars=SUMMARY_MAX_CHARS,
        articles=json.dumps(payload, ensure_ascii=False, indent=1),
    )
    return gemini.generate_json(prompt, EditorialPlan)


def _clean_keywords(words: list[str]) -> list[str]:
    seen, out = set(), []
    for w in words:
        w = w.strip().strip("#").strip()
        if 2 <= len(w) <= 14 and w.lower() not in seen:
            seen.add(w.lower())
            out.append(w)
    return out[:4]


def curate(articles: list[Article], gemini: Gemini | None) -> Curation:
    if not articles:
        return Curation(None, [], [])

    plan = _plan_with_llm(articles, gemini) if gemini else None
    edits = {e.id: e for e in plan.articles if 0 <= e.id < len(articles)} if plan else {}
    if plan:
        log.info("Gemini 편집 완료: 메인=%s, 부=%s", plan.main_id, plan.sub_ids)

    curated: list[CuratedArticle] = []
    for i, art in enumerate(articles):
        edit = edits.get(i)
        summary = edit.summary.strip() if edit and edit.summary.strip() else fallback_summary(art.body or art.title)
        if len(summary) > SUMMARY_MAX_CHARS + 40:
            summary = fallback_summary(summary)
        keywords = _clean_keywords(edit.keywords) if edit else []
        curated.append(
            CuratedArticle(
                article=art,
                category=(edit.category.strip() if edit and edit.category.strip() else fallback_category(art)),
                summary=summary,
                importance=max(1, min(100, edit.importance)) if edit else min(100, _fallback_score(art)),
                keywords=keywords or fallback_keywords(f"{art.title} {summary}"),
                why=(edit.why_it_matters.strip() if edit else ""),
                reading_min=reading_minutes(art.body or summary),
                uid=f"a{i + 1}",
            )
        )

    # 메인/부 헤드라인 선정 — LLM 결과를 검증하고 부족하면 중요도 순으로 채운다.
    by_rank = sorted(range(len(curated)), key=lambda i: curated[i].importance, reverse=True)
    picked: list[int] = []
    if plan:
        for idx in [plan.main_id, *plan.sub_ids]:
            if 0 <= idx < len(curated) and idx not in picked:
                picked.append(idx)
    for idx in by_rank:
        if len(picked) >= 1 + SUB_HEADLINES:
            break
        if idx not in picked:
            picked.append(idx)
    picked = picked[: 1 + SUB_HEADLINES]

    main = curated[picked[0]]
    subs = [curated[i] for i in picked[1:]]
    rest = [curated[i] for i in by_rank if i not in picked]

    groups: dict[str, list[CuratedArticle]] = defaultdict(list)
    for c in rest:
        groups[c.category].append(c)
    # 기사가 많은 분류부터, '기타'는 맨 뒤
    sections = sorted(groups.items(), key=lambda kv: (kv[0] == "기타", -len(kv[1])))

    result = Curation(main, subs, sections, llm_used=plan is not None)
    keyword_counts = Counter(k for c in curated for k in c.keywords)
    result.keywords = keyword_counts.most_common(12)

    if plan:
        result.briefing = [b.strip() for b in plan.briefing if b.strip()][:3]
        result.editor_note = plan.editor_note.strip()
        result.numbers = [(n.value.strip(), n.label.strip()) for n in plan.numbers if n.value.strip()][:3]
    if not result.briefing:
        result.briefing = [c.article.title for c in ([main] + subs)][:3]
    if not result.editor_note:
        top_cat, top_n = Counter(c.category for c in curated).most_common(1)[0]
        result.editor_note = f"오늘 지면은 '{top_cat}' 소식이 {top_n}건으로 가장 많았습니다."
    if not result.numbers:
        result.numbers = fallback_numbers(result.all)
    return result
