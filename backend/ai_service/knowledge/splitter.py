import re
from dataclasses import dataclass, field


HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$")
FAQ_PATTERN = re.compile(r"^(问|问题|Q|q)[:：]\s*(.+)$")
TABLE_SEPARATOR_PATTERN = re.compile(
    r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$"
)
PAGE_MARKER_PATTERN = re.compile(r"^\[\[page:(\d+)]]$")


@dataclass(frozen=True)
class TextChunk:
    text: str
    chunk_index: int
    metadata: dict = field(default_factory=dict)


def split_text(text: str, chunk_size: int, overlap: int) -> list[TextChunk]:
    blocks = _parse_blocks(text)
    if not blocks:
        return []

    chunks: list[TextChunk] = []
    for block in blocks:
        if len(block.text) <= chunk_size:
            chunks.append(
                TextChunk(
                    text=block.text.strip(),
                    chunk_index=len(chunks),
                    metadata=block.metadata,
                )
            )
            continue

        for part in _split_long_text(block.text, chunk_size=chunk_size, overlap=overlap):
            chunks.append(
                TextChunk(
                    text=part.strip(),
                    chunk_index=len(chunks),
                    metadata={
                        **block.metadata,
                        "chunk_type": f"{block.metadata.get('chunk_type', 'paragraph')}_part",
                    },
                )
            )

    return [
        TextChunk(
            text=chunk.text,
            chunk_index=index,
            metadata={
                **chunk.metadata,
                "token_count": _rough_token_count(chunk.text),
            },
        )
        for index, chunk in enumerate(chunks)
        if chunk.text.strip()
    ]


@dataclass(frozen=True)
class ParsedBlock:
    text: str
    metadata: dict


def _parse_blocks(text: str) -> list[ParsedBlock]:
    lines = [line.rstrip() for line in text.splitlines()]
    blocks: list[ParsedBlock] = []
    section_stack: list[str] = []
    current_page: int | None = None
    paragraph: list[str] = []
    paragraph_start_page: int | None = None

    def flush_paragraph(chunk_type: str = "paragraph") -> None:
        nonlocal paragraph, paragraph_start_page
        content = "\n".join(line.strip() for line in paragraph if line.strip()).strip()
        if not content:
            paragraph = []
            paragraph_start_page = None
            return
        blocks.append(
            ParsedBlock(
                text=_with_section_context(content, section_stack),
                metadata=_block_metadata(
                    chunk_type=chunk_type,
                    section_stack=section_stack,
                    page_start=paragraph_start_page or current_page,
                    page_end=current_page,
                ),
            )
        )
        paragraph = []
        paragraph_start_page = None

    index = 0
    while index < len(lines):
        raw_line = lines[index]
        line = raw_line.strip()

        page_match = PAGE_MARKER_PATTERN.match(line)
        if page_match:
            flush_paragraph()
            current_page = int(page_match.group(1))
            index += 1
            continue

        if not line:
            flush_paragraph()
            index += 1
            continue

        heading_match = HEADING_PATTERN.match(line)
        if heading_match:
            flush_paragraph()
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            section_stack = section_stack[: level - 1]
            section_stack.append(title)
            blocks.append(
                ParsedBlock(
                    text=_with_section_context(title, section_stack),
                    metadata=_block_metadata(
                        chunk_type="heading",
                        section_stack=section_stack,
                        page_start=current_page,
                        page_end=current_page,
                    ),
                )
            )
            index += 1
            continue

        if _is_table_line(line):
            flush_paragraph()
            table_lines = [line]
            start_page = current_page
            index += 1
            while index < len(lines) and _is_table_line(lines[index].strip()):
                table_lines.append(lines[index].strip())
                index += 1
            blocks.append(
                ParsedBlock(
                    text=_with_section_context("\n".join(table_lines), section_stack),
                    metadata=_block_metadata(
                        chunk_type="table",
                        section_stack=section_stack,
                        page_start=start_page,
                        page_end=current_page,
                    ),
                )
            )
            continue

        faq_match = FAQ_PATTERN.match(line)
        if faq_match:
            flush_paragraph()
            faq_lines = [line]
            start_page = current_page
            index += 1
            while index < len(lines):
                next_line = lines[index].strip()
                if not next_line:
                    break
                if HEADING_PATTERN.match(next_line) or FAQ_PATTERN.match(next_line):
                    break
                faq_lines.append(next_line)
                index += 1
            blocks.append(
                ParsedBlock(
                    text=_with_section_context("\n".join(faq_lines), section_stack),
                    metadata=_block_metadata(
                        chunk_type="faq",
                        section_stack=section_stack,
                        page_start=start_page,
                        page_end=current_page,
                    ),
                )
            )
            continue

        if paragraph_start_page is None:
            paragraph_start_page = current_page
        paragraph.append(line)
        index += 1

    flush_paragraph()
    return blocks


def _with_section_context(content: str, section_stack: list[str]) -> str:
    if not section_stack:
        return content
    section = " > ".join(section_stack)
    if content.startswith(section):
        return content
    return f"章节：{section}\n{content}"


def _block_metadata(
    *,
    chunk_type: str,
    section_stack: list[str],
    page_start: int | None,
    page_end: int | None,
) -> dict:
    metadata = {
        "chunk_type": chunk_type,
        "title": section_stack[-1] if section_stack else "",
        "section_path": list(section_stack),
    }
    if page_start is not None:
        metadata["page_start"] = page_start
    if page_end is not None:
        metadata["page_end"] = page_end
    return metadata


def _is_table_line(line: str) -> bool:
    if not line:
        return False
    return line.count("|") >= 2 or bool(TABLE_SEPARATOR_PATTERN.match(line))


def _split_long_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    normalized = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if not normalized:
        return []

    parts: list[str] = []
    start = 0

    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        window = normalized[start:end]

        if end < len(normalized):
            split_at = max(window.rfind("\n"), window.rfind("。"), window.rfind("."))
            if split_at > chunk_size * 0.45:
                end = start + split_at + 1
                window = normalized[start:end]

        parts.append(window.strip())

        if end >= len(normalized):
            break
        start = max(0, end - overlap)

    return parts


def _rough_token_count(text: str) -> int:
    cjk_chars = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    latin_words = len(re.findall(r"[A-Za-z0-9_]+", text))
    return cjk_chars + latin_words
