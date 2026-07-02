from backend.ai_service.agent.planner import PlannerService
from backend.ai_service.llm.chat_client import ChatModelResponse


def test_planner_uses_llm_for_complex_tasks() -> None:
    class FakePlannerChatClient:
        enabled = True

        def complete(self, messages, mode, temperature=0.2):
            assert mode == "thinking"
            assert "路由分类器" in messages[0]["content"]
            return ChatModelResponse(
                content=(
                    '{"needs_knowledge":true,'
                    '"reason":"Complex comparison needs enterprise documents."}'
                ),
                reasoning_content="",
                model="fake-planner",
            )

    planner = PlannerService(chat_client=FakePlannerChatClient())
    plan = planner.create_plan(
        question="Compare the reimbursement policy and travel policy, then summarize the differences.",
        answer_mode="thinking",
        memory=[],
    )

    assert plan.strategy == "llm"
    assert [step.step_type for step in plan.steps] == [
        "knowledge_search",
        "agent_answer",
    ]
