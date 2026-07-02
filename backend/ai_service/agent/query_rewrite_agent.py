import json
import re
from typing import Any

from backend.ai_service.llm.chat_client import BailianChatClient
from backend.ai_service.retrieval.query_rewriter import (
    QueryRewritePlan,
    QueryRewriteService,
)


class QueryRewriteAgent:
    """LLM powered query rewrite agent for knowledge retrieval."""

    def __init__(
        self,
        *,
        chat_client: BailianChatClient,
        fallback: QueryRewriteService | None = None,
        max_queries: int = 5,
    ) -> None:
        self.chat_client = chat_client
        self.fallback = fallback or QueryRewriteService(max_queries=max_queries)
        self.max_queries = max(1, max_queries)

    def rewrite(self, query: str) -> QueryRewritePlan:
        fallback_plan = self.fallback.rewrite(query)
        if fallback_plan.needs_clarification or not self.chat_client.enabled:
            return fallback_plan

        try:
            response = self.chat_client.complete(
                messages=_build_messages(
                    query=fallback_plan.original_query,
                    max_queries=self.max_queries,
                ),
                mode="fast",
                temperature=0.0,
            )
            payload = _extract_json_object(response.content)
            return _plan_from_payload(
                payload,
                original_query=fallback_plan.original_query,
                fallback_plan=fallback_plan,
                max_queries=self.max_queries,
            )
        except Exception:
            return fallback_plan


def _build_messages(query: str, max_queries: int) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "你是企业知识库 RAG 的 query rewrite agent。"
                "你的任务是把用户问题改写为更适合向量检索的查询。"
                "只输出 JSON，不要输出 Markdown、解释或多余文本。"
                "不要编造用户没有提到的事实、数字、制度结论。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请基于用户问题输出如下 JSON 对象：\n"
                "{\n"
                '  "standalone_query": "可独立理解的检索问题",\n'
                '  "semantic_queries": ["用于向量检索的改写问题"],\n'
                '  "keyword_queries": ["关键词检索词"],\n'
                '  "sub_questions": ["必要时拆出的子问题"],\n'
                '  "filters": {"year": "", "quarter": "", "document_type": ""},\n'
                '  "must_include_terms": ["必须覆盖的核心词"],\n'
                '  "rewrite_strategy": "llm_rewrite"\n'
                "}\n\n"
                f"约束：semantic_queries 最多 {max_queries} 条；"
                "第一条必须尽量贴近用户原问题；空字段用空数组或空对象。"
                f"\n\n用户问题：{query}"
            ),
        },
    ]


def _extract_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)

    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        value = json.loads(match.group(0))

    if not isinstance(value, dict):
        raise ValueError("query rewrite response must be a JSON object")
    return value


def _plan_from_payload(
    payload: dict[str, Any],
    *,
    original_query: str,
    fallback_plan: QueryRewritePlan,
    max_queries: int,
) -> QueryRewritePlan:
    standalone = _clean_string(payload.get("standalone_query")) or original_query
    semantic_queries = _string_list(payload.get("semantic_queries"))
    semantic_queries = _unique([original_query, standalone, *semantic_queries])[:max_queries]
    if not semantic_queries:
        semantic_queries = fallback_plan.semantic_queries

    keyword_queries = _string_list(payload.get("keyword_queries"))
    if not keyword_queries:
        keyword_queries = fallback_plan.keyword_queries

    sub_questions = _string_list(payload.get("sub_questions"))
    filters = _string_dict(payload.get("filters"))
    if not filters:
        filters = fallback_plan.filters

    must_include_terms = _string_list(payload.get("must_include_terms"))
    if not must_include_terms:
        must_include_terms = fallback_plan.must_include_terms

    strategy = _clean_string(payload.get("rewrite_strategy")) or "llm_rewrite"
    return QueryRewritePlan(
        original_query=original_query,
        standalone_query=standalone,
        semantic_queries=semantic_queries,
        keyword_queries=keyword_queries,
        sub_questions=sub_questions,
        filters=filters,
        must_include_terms=must_include_terms,
        rewrite_strategy=strategy,
    )


def _clean_string(value: object) -> str:
    return str(value).strip() if isinstance(value, str) else ""


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return _unique([str(item).strip() for item in value if str(item).strip()])


def _string_dict(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key).strip(): str(item).strip()
        for key, item in value.items()
        if str(key).strip() and str(item).strip()
    }


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
