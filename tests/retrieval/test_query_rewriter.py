from backend.ai_service.retrieval.query_rewriter import QueryRewriteService


def test_rewrites_colloquial_reimbursement_question():
    plan = QueryRewriteService().rewrite("报销多久到账")

    assert plan.standalone_query == "员工费用报销审批通过后多久打款"
    assert any("费用报销" in query for query in plan.semantic_queries)
    assert any("打款" in query for query in plan.semantic_queries)
    assert plan.must_include_terms == ["报销"]


def test_decomposes_multi_intent_question():
    plan = QueryRewriteService().rewrite("差旅和报销分别谁审批，有什么区别？")

    assert "差旅申请由谁审批" in plan.sub_questions
    assert "费用报销由谁审批" in plan.sub_questions
    assert any("区别" in question for question in plan.sub_questions)
    assert len(plan.semantic_queries) <= 5


def test_extracts_time_and_document_filters():
    plan = QueryRewriteService().rewrite("2026 年 Q2 差旅制度标准")

    assert plan.filters == {
        "year": "2026",
        "quarter": "Q2",
        "document_type": "policy",
    }


def test_keeps_english_query_unchanged():
    query = "When are reimbursements paid?"
    plan = QueryRewriteService().rewrite(query)

    assert plan.standalone_query == query
    assert plan.semantic_queries == [query]


def test_empty_query_requests_clarification_without_search_queries():
    plan = QueryRewriteService().rewrite("  ")

    assert plan.semantic_queries == []
    assert plan.needs_clarification is True
