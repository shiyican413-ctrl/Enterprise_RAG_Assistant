from dataclasses import dataclass

from backend.ai_service.knowledge.splitter import TextChunk


@dataclass(frozen=True)
class IngestQualityReport:
    chunk_count: int
    avg_chunk_tokens: int
    max_chunk_tokens: int
    short_chunk_ratio: float
    heading_chunk_count: int
    empty_chunk_count: int
    duplicate_ratio: float
    metadata_ready: bool
    embedding_ready: bool
    warnings: list[str]

    def to_dict(self) -> dict:
        return {
            "chunk_count": self.chunk_count,
            "avg_chunk_tokens": self.avg_chunk_tokens,
            "max_chunk_tokens": self.max_chunk_tokens,
            "short_chunk_ratio": self.short_chunk_ratio,
            "heading_chunk_count": self.heading_chunk_count,
            "empty_chunk_count": self.empty_chunk_count,
            "duplicate_ratio": self.duplicate_ratio,
            "metadata_ready": self.metadata_ready,
            "embedding_ready": self.embedding_ready,
            "warnings": self.warnings,
        }


class IngestQualityService:
    def inspect_chunks(
        self,
        chunks: list[TextChunk],
        *,
        embedding_ready: bool,
    ) -> IngestQualityReport:
        empty_count = sum(1 for chunk in chunks if not chunk.text.strip())
        non_empty = [chunk for chunk in chunks if chunk.text.strip()]
        token_counts = [
            int(chunk.metadata.get("token_count") or len(chunk.text))
            for chunk in non_empty
        ]
        avg_tokens = int(sum(token_counts) / len(token_counts)) if token_counts else 0
        max_tokens = max(token_counts, default=0)
        short_ratio = (
            sum(token_count < 80 for token_count in token_counts) / len(token_counts)
            if token_counts
            else 0.0
        )
        heading_count = sum(
            chunk.metadata.get("chunk_type") == "heading" for chunk in non_empty
        )
        duplicate_ratio = _duplicate_ratio([chunk.text for chunk in non_empty])
        metadata_ready = bool(non_empty) and all(
            _has_required_metadata(chunk.metadata)
            for chunk in non_empty
        )

        warnings: list[str] = []
        if not non_empty:
            warnings.append("No non-empty chunks were produced.")
        if avg_tokens and avg_tokens < 40:
            warnings.append("Average chunk length is very short; retrieval may be fragmented.")
        if short_ratio > 0.1:
            warnings.append("Too many chunks are shorter than 80 tokens.")
        if heading_count:
            warnings.append("Heading-only chunks should not be indexed.")
        if duplicate_ratio > 0.2:
            warnings.append("Duplicate chunk ratio is high; source may include repeated headers or footers.")
        if not metadata_ready:
            warnings.append("Some chunks are missing required metadata.")
        if not embedding_ready:
            warnings.append("Embedding client is disabled; dense retrieval will not be available.")

        return IngestQualityReport(
            chunk_count=len(non_empty),
            avg_chunk_tokens=avg_tokens,
            max_chunk_tokens=max_tokens,
            short_chunk_ratio=round(short_ratio, 4),
            heading_chunk_count=heading_count,
            empty_chunk_count=empty_count,
            duplicate_ratio=round(duplicate_ratio, 4),
            metadata_ready=metadata_ready,
            embedding_ready=embedding_ready,
            warnings=warnings,
        )

    def ensure_usable(self, report: IngestQualityReport) -> None:
        if report.chunk_count == 0:
            raise ValueError("Document parsing produced no indexable chunks.")
        if not report.metadata_ready:
            raise ValueError("Document chunks are missing required retrieval metadata.")


def _duplicate_ratio(contents: list[str]) -> float:
    if not contents:
        return 0.0
    normalized = [" ".join(content.split()) for content in contents]
    duplicate_count = len(normalized) - len(set(normalized))
    return duplicate_count / len(normalized)


def _has_required_metadata(metadata: dict) -> bool:
    return all(key in metadata for key in ("chunk_type", "section_path", "token_count"))
