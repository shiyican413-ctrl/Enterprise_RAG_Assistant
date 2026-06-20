from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    text: str
    chunk_index: int


def split_text(text: str, chunk_size: int, overlap: int) -> list[TextChunk]:
    normalized = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if not normalized:
        return []

    chunks: list[TextChunk] = []
    start = 0
    index = 0

    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        window = normalized[start:end]

        if end < len(normalized):
            split_at = max(window.rfind("\n"), window.rfind("。"), window.rfind("."))
            if split_at > chunk_size * 0.45:
                end = start + split_at + 1
                window = normalized[start:end]

        chunks.append(TextChunk(text=window.strip(), chunk_index=index))
        index += 1

        if end >= len(normalized):
            break
        start = max(0, end - overlap)

    return chunks
