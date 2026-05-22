from collections.abc import AsyncIterator

from backend.ai_service.config import TOP_K
from backend.ai_service.services.chat_model_service import AnswerMode, GLMChatClient
from backend.ai_service.services.history_service import HistoryService, PostgresHistoryService
from backend.ai_service.services.vector_store_service import PostgresVectorStore, SearchResult


class RAGService:
    def __init__(
        self,
        vector_store: PostgresVectorStore | None = None,
        history_service: HistoryService | None = None,
        chat_client: GLMChatClient | None = None,
    ) -> None:
        self.vector_store = vector_store or PostgresVectorStore()
        self.history_service = history_service or PostgresHistoryService()
        self.chat_client = chat_client or GLMChatClient()

    def ask(
        self,
        question: str,
        conversation_id: str | None = None,
        top_k: int = TOP_K,
        answer_mode: AnswerMode = "fast",
    ) -> dict:
        results = self.vector_store.search(question, top_k=top_k)
        sources = [_source_payload(result) for result in results]
        answer, model = self._build_answer(
            question=question,
            results=results,
            answer_mode=answer_mode,
        )
        turn = self.history_service.append_turn(
            question=question,
            answer=answer,
            sources=sources,
            conversation_id=conversation_id,
        )

        return {
            "conversation_id": turn["conversation_id"],
            "answer": answer,
            "sources": sources,
            "answer_mode": answer_mode,
            "model": model,
        }

    async def stream_ask(
        self,
        question: str,
        conversation_id: str | None = None,
        top_k: int = TOP_K,
        answer_mode: AnswerMode = "fast",
    ) -> AsyncIterator[dict]:
        results = self.vector_store.search(question, top_k=top_k)
        sources = [_source_payload(result) for result in results]
        answer_parts: list[str] = []
        model: str | None = None

        if results and self.chat_client.enabled:
            try:
                async for delta in self.chat_client.stream_complete(
                    messages=_build_messages(question, results, answer_mode),
                    mode=answer_mode,
                    temperature=0.1 if answer_mode == "thinking" else 0.2,
                ):
                    model = delta.model
                    answer_parts.append(delta.content)
                    yield {"type": "answer_delta", "content": delta.content}
            except Exception as exc:
                fallback = _build_template_answer(question, results)
                if answer_parts:
                    fallback = f"\n\n模型流式输出中断，已保留已生成内容。错误信息：{exc}"
                else:
                    fallback = (
                        f"{fallback}\n\n"
                        f"模型生成暂时不可用，已退回本地模板回答。错误信息：{exc}"
                    )
                for chunk in _chunk_text(fallback):
                    answer_parts.append(chunk)
                    yield {"type": "answer_delta", "content": chunk}
                model = model if answer_parts else None

        if not answer_parts:
            answer = _build_template_answer(question, results)
            for chunk in _chunk_text(answer):
                answer_parts.append(chunk)
                yield {"type": "answer_delta", "content": chunk}

        answer = "".join(answer_parts)
        turn = self.history_service.append_turn(
            question=question,
            answer=answer,
            sources=sources,
            conversation_id=conversation_id,
        )

        yield {"type": "sources", "content": sources}
        yield {
            "type": "done",
            "conversation_id": turn["conversation_id"],
            "answer_mode": answer_mode,
            "model": model,
        }

    def _build_answer(
        self,
        question: str,
        results: list[SearchResult],
        answer_mode: AnswerMode,
    ) -> tuple[str, str | None]:
        if not results:
            return _build_template_answer(question, results), None

        if self.chat_client.enabled:
            try:
                response = self.chat_client.complete(
                    messages=_build_messages(question, results, answer_mode),
                    mode=answer_mode,
                    temperature=0.1 if answer_mode == "thinking" else 0.2,
                )
                return response.content, response.model
            except Exception as exc:
                fallback = _build_template_answer(question, results)
                return (
                    f"{fallback}\n\n"
                    f"模型生成暂时不可用，已退回本地模板回答。错误信息：{exc}",
                    None,
                )

        return _build_template_answer(question, results), None


def _build_template_answer(question: str, results: list[SearchResult]) -> str:
    if not results:
        return (
            "我还没有在当前知识库中检索到足够相关的内容。"
            "建议先上传企业制度、产品手册或 FAQ 文档后再提问。"
        )

    evidence = "\n".join(
        f"{index}. {result.chunk.content[:260]}"
        for index, result in enumerate(results[:3], start=1)
    )

    return (
        f"根据当前知识库中最相关的资料，关于“{question}”可以这样理解：\n\n"
        f"{evidence}\n\n"
        "以上回答来自检索片段的归纳整理。"
    )


def _chunk_text(text: str, size: int = 48) -> list[str]:
    return [text[index : index + size] for index in range(0, len(text), size)]
    return (
        f"根据当前知识库中最相关的资料，关于“{question}”可以这样理解：\n\n"
        f"{evidence}\n\n"
        "以上回答来自检索片段的归纳整理。第一版先使用本地检索和模板生成，"
        "后续可把这里替换为通义千问、Ollama 或 OpenAI Compatible API 生成。"
    )


def _build_messages(
    question: str,
    results: list[SearchResult],
    answer_mode: AnswerMode,
) -> list[dict[str, str]]:
    evidence = "\n\n".join(
        (
            f"[{index}] 来源：{result.chunk.document_name}，"
            f"片段：{result.chunk.chunk_index}\n"
            f"{result.chunk.content[:1200]}"
        )
        for index, result in enumerate(results, start=1)
    )
    mode_instruction = (
        "优先给出简洁直接的结论，控制在 3 到 6 条要点内。"
        if answer_mode == "fast"
        else "先认真分析资料之间的关系，再给出结构化答案；只输出最终答案，不输出隐藏推理过程。"
    )

    return [
        {
            "role": "system",
            "content": (
                "你是企业 RAG 知识库助手。必须严格基于提供的资料回答，"
                "不要编造资料外的信息。能回答时给出清晰结论，并在关键句后使用 [1]、[2] "
                "这样的编号标注依据。资料不足时，明确说明当前知识库依据不足。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"回答模式：{answer_mode}\n"
                f"回答要求：{mode_instruction}\n\n"
                f"用户问题：{question}\n\n"
                f"可用资料：\n{evidence}"
            ),
        },
    ]


def _source_payload(result: SearchResult) -> dict:
    chunk = result.chunk
    return {
        "document_id": chunk.document_id,
        "document_name": chunk.document_name,
        "chunk_id": chunk.id,
        "chunk_index": chunk.chunk_index,
        "snippet": chunk.content[:360],
        "score": round(result.score, 4),
        "metadata": chunk.metadata,
    }
