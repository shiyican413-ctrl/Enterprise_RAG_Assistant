from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from backend.ai_service.knowledge.ingest_quality_service import IngestQualityService
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
    assert not any(chunk.metadata["chunk_type"] == "heading" for chunk in chunks)
    assert any(chunk.metadata["chunk_type"] == "table" for chunk in chunks)
    assert any(chunk.metadata["chunk_type"] == "faq" for chunk in chunks)
    assert any(chunk.metadata["section_path"] == ["员工制度", "报销流程"] for chunk in chunks)
    assert all("token_count" in chunk.metadata for chunk in chunks)


def test_split_text_uses_semantic_boundaries_for_long_paragraphs() -> None:
    text = (
        "# 假勤制度\n\n"
        "员工请假应提前提交申请，直属上级需要在一个工作日内完成审批。"
        "病假需要补充医院证明，证明材料应在返岗后三个工作日内提交。"
        "年假申请应避开团队关键交付周期，连续休假超过五天时需要部门负责人审批。"
        "如遇紧急情况无法提前申请，员工应先通过企业微信说明原因，并在返岗后补齐流程。"
    )

    chunks = split_text(text, chunk_size=70, overlap=10)

    paragraph_parts = [
        chunk for chunk in chunks
        if chunk.metadata["chunk_type"] == "paragraph_part"
    ]
    assert len(paragraph_parts) >= 2
    assert all(not chunk.text.startswith("章节：") for chunk in paragraph_parts)
    assert all(chunk.metadata["section_path"] == ["假勤制度"] for chunk in paragraph_parts)
    assert all(chunk.metadata["split_strategy"] == "semantic_hard_limit" for chunk in paragraph_parts)
    assert any("病假需要补充医院证明" in chunk.text for chunk in paragraph_parts)


def test_split_text_preserves_list_blocks() -> None:
    text = """# 账号权限

1. 新员工入职当天由 IT 开通基础账号。
2. 涉及财务系统的账号需要部门负责人审批。
3. 离职账号应在最后工作日关闭。
"""

    chunks = split_text(text, chunk_size=500, overlap=80)

    assert any(chunk.metadata["chunk_type"] == "list" for chunk in chunks)
    assert any("财务系统" in chunk.text for chunk in chunks)


def test_split_text_merges_short_blocks_beneath_the_same_section() -> None:
    text = """# 报销制度

员工先提交申请。

直属领导完成审批。

财务会在三个工作日内打款。
"""

    chunks = split_text(text, chunk_size=500, overlap=80)

    assert len(chunks) == 1
    assert chunks[0].metadata["section_path"] == ["报销制度"]
    assert "员工先提交申请" in chunks[0].text
    assert "三个工作日内打款" in chunks[0].text
    assert chunks[0].metadata["split_strategy"] == "section_pack"


def test_split_text_repeats_table_header_and_respects_hard_limit() -> None:
    rows = "\n".join(f"| 城市{i} | {300 + i} |" for i in range(30))
    text = f"""# 差旅标准

| 城市 | 住宿标准 |
| --- | --- |
{rows}
"""

    chunks = split_text(text, chunk_size=100, overlap=50)
    table_chunks = [chunk for chunk in chunks if chunk.metadata["chunk_type"] == "table_part"]

    assert len(table_chunks) > 1
    assert all("| 城市 | 住宿标准 |" in chunk.text for chunk in table_chunks)
    assert all(chunk.metadata["token_count"] <= 100 for chunk in chunks)


def test_split_text_enforces_hard_limit_for_an_oversized_sentence() -> None:
    chunks = split_text("# 制度\n\n" + "条" * 800, chunk_size=100, overlap=50)

    assert len(chunks) > 1
    assert all(chunk.metadata["token_count"] <= 100 for chunk in chunks)
    assert all(chunk.metadata["chunk_type"] != "heading" for chunk in chunks)


def test_quality_service_rejects_empty_document() -> None:
    service = IngestQualityService()
    report = service.inspect_chunks([], embedding_ready=True)

    assert report.metadata_ready is False
    with pytest.raises(ValueError, match="no indexable chunks"):
        service.ensure_usable(report)


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
