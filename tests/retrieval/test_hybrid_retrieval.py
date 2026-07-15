from pathlib import Path

from backend.ai_service.knowledge.service import KnowledgeService
from backend.ai_service.knowledge.repository import LocalKnowledgeRepository
from backend.ai_service.retrieval.embeddings import BailianEmbeddingClient
from backend.ai_service.retrieval.vector_store import LocalVectorStore


def test_bm25_retrieval_matches_exact_terms_without_embeddings(tmp_path: Path) -> None:
    vector_store = LocalVectorStore(
        index_file=tmp_path / "chunks.json",
        embedding_client=BailianEmbeddingClient(api_key=""),
    )
    vector_store.add_document(
        document_name="products.md",
        chunks=[
            "通用报销流程说明。",
            "产品型号 ZX-9000 支持私有化部署和审计日志。",
        ],
    )

    results = vector_store.search("ZX-9000 私有化", top_k=1)

    assert results
    assert "ZX-9000" in results[0].chunk.content


def test_ingest_keeps_tables_as_table_chunks_with_hash_metadata(tmp_path: Path) -> None:
    source = tmp_path / "travel.md"
    source.write_text(
        "# 差旅标准\n\n"
        "| 城市 | 住宿 |\n"
        "| --- | --- |\n"
        "| 上海 | 600 |\n",
        encoding="utf-8",
    )
    vector_store = LocalVectorStore(
        index_file=tmp_path / "chunks.json",
        embedding_client=BailianEmbeddingClient(api_key=""),
    )
    repository = LocalKnowledgeRepository(
        documents_file=tmp_path / "documents.json",
        chunks_file=tmp_path / "document_chunks.json",
        tasks_file=tmp_path / "ingest_tasks.json",
    )
    service = KnowledgeService(vector_store=vector_store, repository=repository)

    result = service.ingest_file(source, original_name="travel.md")
    chunks = service.list_document_chunks(result["document_id"], result["tenant_id"])

    table_chunks = [chunk for chunk in chunks if chunk["block_type"] == "table"]
    assert table_chunks
    assert table_chunks[0]["hash"]
    assert table_chunks[0]["metadata"]["block_type"] == "table"
    assert table_chunks[0]["title_path"] == ["差旅标准"]
