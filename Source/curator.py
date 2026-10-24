"""[2단계] 편집장 — 중요도 평가(메인 1 / 부 헤드라인 2), 카테고리 분류, 2~3줄 요약.

Gemini 가 없거나 실패하면 언급 횟수·본문 길이·이미지 유무 기반 규칙으로 편집한다.
"""
from __future__ import annotations

import json
import logging
import re
from collections import defaultdict

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


class ArticleEdit(BaseModel):
    id: int
    category: str
    summary: str
    importance: int


class EditorialPlan(BaseModel):
    main_id: int
    sub_ids: list[int]
    articles: list[ArticleEdit]


PROMPT = """너는 일간 테크 신문의 편집장이다. 오늘 수집된 기사 목록을 보고 지면을 편집하라.

[편집 규칙]
1. 중요도(importance, 1~100): 그날 여러 번 언급된 기사(mention_count 가 클수록), 산업·사회적 파급력,
   새로움, 독자 관심도를 기준으로 평가한다.
2. main_id: 가장 중요한 기사 1건 (1면 메인 헤드라인). 가능하면 이미지가 있는 기사(has_image=true)를 우선한다.
3. sub_ids: 메인 다음으로 중요한 기사 {subs}건 (부 헤드라인). main_id 와 겹치면 안 된다.
4. category: 다음 중 하나를 고른다. 꼭 맞는 것이 없을 때만 짧은 새 분류명(2~8자)을 쓴다.
   {categories}
5. summary: 한국어 신문체로 2~3문장, 공백 포함 120~{max_chars}자. 2~3줄 분량을 넘기지 않는다.
   본문에 있는 사실만 쓰고, 추측·과장·새로운 수치를 만들지 않는다.
6. articles 에는 입력된 모든 기사(id)를 빠짐없이 포함한다.

[기사 목록 JSON]
{articles}
"""


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


def curate(
    articles: list[Article], gemini: Gemini | None
) -> tuple[CuratedArticle | None, list[CuratedArticle], list[tuple[str, list[CuratedArticle]]]]:
    """(메인, 부 헤드라인 목록, [(카테고리, 기사 목록), ...]) 을 반환한다."""
    if not articles:
        return None, [], []

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
        curated.append(
            CuratedArticle(
                article=art,
                category=(edit.category.strip() if edit and edit.category.strip() else fallback_category(art)),
                summary=summary,
                importance=edit.importance if edit else _fallback_score(art),
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
    return main, subs, sections
