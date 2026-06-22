from pathlib import Path
from tempfile import TemporaryDirectory

from backend.ai_service.knowledge.service import KnowledgeService
from backend.ai_service.knowledge.splitter import split_text
from backend.ai_service.retrieval.embeddings import BailianEmbeddingClient
from backend.ai_service.retrieval.vector_store import LocalVectorStore


def test_split_text_preserves_structure_metadata() -> None:
    text = """# 员工制度

## 报销流程

报销申请审批通过后，财务会在三个工作日内打款。

| 项目 | 标准 |
| --- | --- |
| 住宿 | 500 元 |

Q: 报销多久到账？
A: 三个工作日内。
"""

    chunks = split_text(text, chunk_size=500, overlap=80)

    assert chunks
    assert any(chunk.metadata["chunk_type"] == "heading" for chunk in chunks)
    assert any(chunk.metadata["chunk_type"] == "table" for chunk in chunks)
    assert any(chunk.metadata["chunk_type"] == "faq" for chunk in chunks)
    assert any(chunk.metadata["section_path"] == ["员工制度", "报销流程"] for chunk in chunks)
    assert all("token_count" in chunk.metadata for chunk in chunks)


def test_ingest_file_returns_quality_report_and_chunk_metadata() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "policy.md"
        source.write_text(
            "# 员工制度\n\n"
            "## 报销流程\n\n"
            "报销申请审批通过后，财务会在三个工作日内打款。\n",
            encoding="utf-8",
        )
        vector_store = LocalVectorStore(
            index_file=root / "chunks.json",
            embedding_client=BailianEmbeddingClient(api_key=""),
        )
        service = KnowledgeService(vector_store=vector_store)

        result = service.ingest_file(source, original_name="policy.md")

        assert result["chunk_count"] > 0
        assert result["quality_report"]["chunk_count"] == result["chunk_count"]
        assert result["quality_report"]["metadata_ready"] is True
        chunks = vector_store.list_document_chunks(result["document_id"])
        assert chunks
        assert any(
            chunk["metadata"].get("section_path") == ["员工制度", "报销流程"]
            for chunk in chunks
        )
        assert all("chunk_type" in chunk["metadata"] for chunk in chunks)
