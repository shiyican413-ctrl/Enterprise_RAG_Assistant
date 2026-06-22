import re
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class QueryRewritePlan:
    original_query: str
    standalone_query: str
    semantic_queries: list[str]
    keyword_queries: list[str]
    sub_questions: list[str]
    filters: dict[str, str]
    must_include_terms: list[str]
    rewrite_strategy: str
    needs_clarification: bool = False
    clarification_reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


ENTERPRISE_SYNONYMS: dict[str, tuple[str, ...]] = {
    "报销": ("费用报销", "打款", "付款周期", "财务审批"),
    "差旅": ("出差", "差旅费用标准", "住宿标准", "交通补贴"),
    "权限": ("账号权限", "IT资源", "权限申请", "审批流程"),
    "竞业": ("保密", "竞业限制", "竞业规范"),
}

_NORMALIZATIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"^报销(?:一般)?(?:要)?多久(?:能|可以|会)?到账[？?]?$"),
        "员工费用报销审批通过后多久打款",
    ),
    (
        re.compile(r"^权限(?:要)?怎么申请[？?]?$"),
        "IT资源账号权限申请流程及审批要求",
    ),
    (
        re.compile(r"^差旅标准(?:是什么|有哪些)?[？?]?$"),
        "差旅费用标准，包括出差住宿、交通和补贴标准",
    ),
)


class QueryRewriteService:
    """Deterministic first-pass rewrite for enterprise knowledge retrieval."""

    def __init__(self, max_queries: int = 5) -> None:
        self.max_queries = max(1, max_queries)

    def rewrite(self, query: str) -> QueryRewritePlan:
        original = _clean_query(query)
        if not original:
            return QueryRewritePlan(
                original_query="",
                standalone_query="",
                semantic_queries=[],
                keyword_queries=[],
                sub_questions=[],
                filters={},
                must_include_terms=[],
                rewrite_strategy="rule",
                needs_clarification=True,
                clarification_reason="检索问题为空。",
            )

        standalone = _normalize(original)
        matched_terms = [term for term in ENTERPRISE_SYNONYMS if term in original]
        sub_questions = _decompose(original, matched_terms)
        expansion = _expanded_query(matched_terms)

        semantic_candidates = [original, standalone]
        if expansion:
            semantic_candidates.append(expansion)
        semantic_candidates.extend(sub_questions)
        semantic_queries = _unique(semantic_candidates)[: self.max_queries]

        keyword_queries = _keyword_queries(matched_terms)
        if not keyword_queries:
            keyword_queries = [original]

        return QueryRewritePlan(
            original_query=original,
            standalone_query=standalone,
            semantic_queries=semantic_queries,
            keyword_queries=keyword_queries,
            sub_questions=sub_questions,
            filters=_extract_filters(original),
            must_include_terms=matched_terms,
            rewrite_strategy="rule_normalize_expand",
        )


def _clean_query(query: str) -> str:
    return re.sub(r"\s+", " ", str(query or "")).strip()


def _normalize(query: str) -> str:
    for pattern, replacement in _NORMALIZATIONS:
        if pattern.fullmatch(query):
            return replacement
    return query


def _expanded_query(matched_terms: list[str]) -> str:
    if not matched_terms:
        return ""
    terms: list[str] = []
    for term in matched_terms:
        terms.append(term)
        terms.extend(ENTERPRISE_SYNONYMS[term])
    return " ".join(_unique(terms))


def _keyword_queries(matched_terms: list[str]) -> list[str]:
    queries: list[str] = []
    for term in matched_terms:
        synonyms = ENTERPRISE_SYNONYMS[term]
        queries.append(" ".join((term, *synonyms[:2])))
    return _unique(queries)


def _decompose(query: str, matched_terms: list[str]) -> list[str]:
    if len(matched_terms) < 2:
        return []

    asks_approval = "审批" in query or "谁批" in query
    asks_difference = "区别" in query or "不同" in query or "分别" in query
    questions: list[str] = []
    for term in matched_terms:
        if asks_approval:
            questions.append(f"{_canonical_subject(term)}由谁审批")
        elif asks_difference:
            questions.append(f"{_canonical_subject(term)}的规定是什么")

    if asks_difference:
        subjects = "和".join(_canonical_subject(term) for term in matched_terms)
        questions.append(f"{subjects}有什么区别")
    return _unique(questions)


def _canonical_subject(term: str) -> str:
    return {
        "报销": "费用报销",
        "差旅": "差旅申请",
        "权限": "账号权限申请",
        "竞业": "竞业限制",
    }.get(term, term)


def _extract_filters(query: str) -> dict[str, str]:
    filters: dict[str, str] = {}
    year = re.search(r"(?<!\d)(20\d{2})\s*年?", query)
    if year:
        filters["year"] = year.group(1)

    quarter = re.search(r"(?:第\s*)?[Qq]([1-4])|第\s*([一二三四1-4])\s*季度", query)
    if quarter:
        value = quarter.group(1) or quarter.group(2)
        chinese_quarters = {"一": "1", "二": "2", "三": "3", "四": "4"}
        filters["quarter"] = f"Q{chinese_quarters.get(value, value)}"

    document_types = {
        "制度": "policy",
        "规定": "policy",
        "通知": "notice",
        "手册": "manual",
        "FAQ": "faq",
    }
    for marker, document_type in document_types.items():
        if marker.lower() in query.lower():
            filters["document_type"] = document_type
            break
    return filters


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))
