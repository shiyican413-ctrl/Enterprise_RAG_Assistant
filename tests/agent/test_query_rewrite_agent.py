from backend.ai_service.agent.query_rewrite_agent import QueryRewriteAgent
from backend.ai_service.llm.chat_client import ChatModelResponse


class _FakeChatClient:
    enabled = True

    def __init__(self, content: str | None = None, error: Exception | None = None):
        self.content = content
        self.error = error
        self.calls = []

    def complete(self, messages, mode, temperature=0.2, tools=None, tool_choice=None):
        self.calls.append(
            {
                "messages": messages,
                "mode": mode,
                "temperature": temperature,
            }
        )
        if self.error:
            raise self.error
        return ChatModelResponse(
            content=self.content or "{}",
            reasoning_content=None,
            model="fake-model",
        )


def test_llm_query_rewrite_agent_returns_structured_plan():
    client = _FakeChatClient(
        """
        {
          "standalone_query": "员工费用报销审批通过后多久打款",
          "semantic_queries": ["费用报销打款周期", "财务审批后付款时间"],
          "keyword_queries": ["报销 打款 财务审批"],
          "sub_questions": [],
          "filters": {"document_type": "policy"},
          "must_include_terms": ["报销", "打款"],
          "rewrite_strategy": "llm_rewrite"
        }
        """
    )

    plan = QueryRewriteAgent(chat_client=client).rewrite("报销多久到账")

    assert client.calls[0]["mode"] == "fast"
    assert client.calls[0]["temperature"] == 0.0
    assert plan.original_query == "报销多久到账"
    assert plan.standalone_query == "员工费用报销审批通过后多久打款"
    assert plan.semantic_queries[:3] == [
        "报销多久到账",
        "员工费用报销审批通过后多久打款",
        "费用报销打款周期",
    ]
    assert plan.keyword_queries == ["报销 打款 财务审批"]
    assert plan.filters == {"document_type": "policy"}
    assert plan.rewrite_strategy == "llm_rewrite"


def test_llm_query_rewrite_agent_falls_back_to_rule_plan_on_error():
    client = _FakeChatClient(error=RuntimeError("model unavailable"))

    plan = QueryRewriteAgent(chat_client=client).rewrite("报销多久到账")

    assert client.calls
    assert plan.standalone_query == "员工费用报销审批通过后多久打款"
    assert plan.rewrite_strategy == "rule_normalize_expand"
