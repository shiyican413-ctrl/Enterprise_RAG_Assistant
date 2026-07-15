import re
from dataclasses import dataclass, field


HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$")
FAQ_PATTERN = re.compile(r"^(问|问题|Q|q)[:：]\s*(.+)$")
LIST_PATTERN = re.compile(
    r"^(\s*[-*+]\s+|\s*\d+[.)、]\s+|[一二三四五六七八九十]+[、.]\s+).+"
)
TABLE_SEPARATOR_PATTERN = re.compile(
    r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$"
)
PAGE_MARKER_PATTERN = re.compile(r"^\[\[page:(\d+)]]$")
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[。！？!?；;])\s+|(?<=[。！？!?；;])")


@dataclass(frozen=True)
class TextChunk:
    text: str
    chunk_index: int
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedBlock:
    text: str
    metadata: dict


def split_text(text: str, chunk_size: int, overlap: int) -> list[TextChunk]:
    """Create retrieval chunks without separating headings from their content.

    ``chunk_size`` is a hard ceiling. For normal enterprise documents we pack
    related blocks in the same section to about 350 tokens, while retaining
    smaller standalone FAQ/table/code blocks as intact semantic units.
    """
    blocks = _parse_blocks(text)
    if not blocks:
        return []

    hard_max = max(1, chunk_size)
    target = min(350, max(40, int(hard_max * 0.7)))
    min_tokens = min(80, max(12, target // 2))
    effective_overlap = min(max(0, overlap), 50)

    chunks: list[TextChunk] = []
    buffered_blocks: list[ParsedBlock] = []
    buffered_tokens = 0
    buffered_section: tuple[str, ...] | None = None

    def emit(text_value: str, metadata: dict) -> None:
        value = text_value.strip()
        if not value:
            return
        token_count = _rough_token_count(value)
        if token_count > hard_max:
            raise ValueError("chunk splitter emitted text above its hard token limit")
        chunks.append(
            TextChunk(
                text=value,
                chunk_index=len(chunks),
                metadata={**metadata, "token_count": token_count},
            )
        )

    def flush_buffer() -> None:
        nonlocal buffered_blocks, buffered_tokens, buffered_section
        if not buffered_blocks:
            return
        metadata = _combined_metadata(buffered_blocks)
        emit("\n\n".join(block.text.strip() for block in buffered_blocks), metadata)
        buffered_blocks = []
        buffered_tokens = 0
        buffered_section = None

    for block in blocks:
        block_type = str(block.metadata.get("chunk_type", "paragraph"))
        block_tokens = _rough_token_count(block.text)
        section = tuple(block.metadata.get("section_path") or [])

        if block_type in {"faq", "table", "code"}:
            flush_buffer()
            for part, metadata in _split_special_block(
                block,
                target=target,
                hard_max=hard_max,
                overlap=effective_overlap,
            ):
                emit(part, metadata)
            continue

        if block_tokens > hard_max:
            flush_buffer()
            for part in _split_text_to_budget(
                block.text,
                target=target,
                hard_max=hard_max,
                overlap=effective_overlap,
            ):
                emit(
                    part,
                    {
                        **block.metadata,
                        "chunk_type": f"{block_type}_part",
                        "split_strategy": "semantic_hard_limit",
                    },
                )
            continue

        if buffered_blocks and section != buffered_section:
            flush_buffer()

        if buffered_blocks and buffered_tokens + block_tokens > hard_max:
            flush_buffer()
        elif (
            buffered_blocks
            and buffered_tokens >= min_tokens
            and buffered_tokens + block_tokens > target
        ):
            flush_buffer()

        buffered_blocks.append(block)
        buffered_tokens += block_tokens
        buffered_section = section

        if buffered_tokens >= target:
            flush_buffer()

    flush_buffer()
    return chunks


def _parse_blocks(text: str) -> list[ParsedBlock]:
    lines = [line.rstrip() for line in text.splitlines()]
    blocks: list[ParsedBlock] = []
    section_stack: list[str] = []
    current_page: int | None = None
    paragraph: list[str] = []
    paragraph_start_page: int | None = None

    def flush_paragraph() -> None:
        nonlocal paragraph, paragraph_start_page
        content = "\n".join(line.strip() for line in paragraph if line.strip()).strip()
        if content:
            blocks.append(
                ParsedBlock(
                    text=content,
                    metadata=_block_metadata(
                        chunk_type="paragraph",
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
        line = lines[index].strip()

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
            index += 1
            continue

        if line.startswith("```"):
            flush_paragraph()
            code_lines = [line]
            start_page = current_page
            index += 1
            while index < len(lines):
                code_line = lines[index].rstrip()
                code_lines.append(code_line)
                index += 1
                if code_line.strip().startswith("```"):
                    break
            blocks.append(
                ParsedBlock(
                    text="\n".join(code_lines).strip(),
                    metadata=_block_metadata(
                        chunk_type="code",
                        section_stack=section_stack,
                        page_start=start_page,
                        page_end=current_page,
                    ),
                )
            )
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
                    text="\n".join(table_lines),
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
                    text="\n".join(faq_lines),
                    metadata=_block_metadata(
                        chunk_type="faq",
                        section_stack=section_stack,
                        page_start=start_page,
                        page_end=current_page,
                    ),
                )
            )
            continue

        if LIST_PATTERN.match(line):
            flush_paragraph()
            list_lines = [line]
            start_page = current_page
            index += 1
            while index < len(lines):
                next_line = lines[index].strip()
                if not next_line:
                    break
                if (
                    HEADING_PATTERN.match(next_line)
                    or FAQ_PATTERN.match(next_line)
                    or _is_table_line(next_line)
                ):
                    break
                if LIST_PATTERN.match(next_line) or _looks_like_list_continuation(next_line):
                    list_lines.append(next_line)
                    index += 1
                    continue
                break
            blocks.append(
                ParsedBlock(
                    text="\n".join(list_lines),
                    metadata=_block_metadata(
                        chunk_type="list",
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


def _split_special_block(
    block: ParsedBlock,
    *,
    target: int,
    hard_max: int,
    overlap: int,
) -> list[tuple[str, dict]]:
    block_type = str(block.metadata.get("chunk_type", "paragraph"))
    if _rough_token_count(block.text) <= hard_max:
        return [(block.text, {**block.metadata, "split_strategy": "structure"})]
    if block_type == "table":
        return _split_table(block, target=target, hard_max=hard_max)
    if block_type == "code":
        return [
            (
                part,
                {
                    **block.metadata,
                    "chunk_type": "code_part",
                    "split_strategy": "code_hard_limit",
                },
            )
            for part in _split_code(block.text, hard_max=hard_max, overlap=overlap)
        ]
    return [
        (
            part,
            {
                **block.metadata,
                "chunk_type": f"{block_type}_part",
                "split_strategy": "semantic_hard_limit",
            },
        )
        for part in _split_text_to_budget(
            block.text,
            target=target,
            hard_max=hard_max,
            overlap=overlap,
        )
    ]


def _split_table(block: ParsedBlock, *, target: int, hard_max: int) -> list[tuple[str, dict]]:
    lines = [line.strip() for line in block.text.splitlines() if line.strip()]
    if not lines:
        return []
    header_count = 2 if len(lines) > 1 and TABLE_SEPARATOR_PATTERN.match(lines[1]) else 1
    header = lines[:header_count]
    header_text = "\n".join(header)
    header_tokens = _rough_token_count(header_text)
    if header_tokens > hard_max:
        return [
            (
                part,
                {
                    **block.metadata,
                    "chunk_type": "table_part",
                    "split_strategy": "table_hard_limit",
                },
            )
            for part in _split_text_to_budget(
                header_text,
                target=target,
                hard_max=hard_max,
                overlap=0,
            )
        ]
    rows = lines[header_count:]
    if not rows:
        return [("\n".join(header), {**block.metadata, "split_strategy": "table"})]

    parts: list[tuple[str, dict]] = []
    current_rows: list[str] = []
    for row in rows:
        candidate = "\n".join([*header, *current_rows, row])
        if current_rows and _rough_token_count(candidate) > target:
            parts.append(
                (
                    "\n".join([*header, *current_rows]),
                    {
                        **block.metadata,
                        "chunk_type": "table_part",
                        "split_strategy": "table_rows",
                    },
                )
            )
            current_rows = []
        if _rough_token_count("\n".join([*header, row])) > hard_max:
            row_budget = hard_max - header_tokens
            for part in _split_text_to_budget(
                row,
                target=min(target, row_budget),
                hard_max=row_budget,
                overlap=0,
            ):
                parts.append(
                    (
                        "\n".join([*header, part]),
                        {
                            **block.metadata,
                            "chunk_type": "table_part",
                            "split_strategy": "table_rows",
                        },
                    )
                )
        else:
            current_rows.append(row)
    if current_rows:
        parts.append(
            (
                "\n".join([*header, *current_rows]),
                {
                    **block.metadata,
                    "chunk_type": "table_part",
                    "split_strategy": "table_rows",
                },
            )
        )
    return parts


def _split_code(text: str, *, hard_max: int, overlap: int) -> list[str]:
    lines = text.splitlines()
    opening = lines[0] if lines and lines[0].strip().startswith("```") else "```"
    body = lines[1:-1] if len(lines) > 1 and lines[-1].strip().startswith("```") else lines[1:]
    parts = _pack_units(body, target=hard_max, hard_max=hard_max, overlap=overlap)
    return ["\n".join([opening, part, "```"]) for part in parts if part.strip()]


def _split_text_to_budget(
    text: str,
    *,
    target: int,
    hard_max: int,
    overlap: int,
) -> list[str]:
    units = _semantic_units(text)
    return _pack_units(units, target=target, hard_max=hard_max, overlap=overlap)


def _pack_units(
    units: list[str],
    *,
    target: int,
    hard_max: int,
    overlap: int,
) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    current_tokens = 0

    def flush() -> None:
        nonlocal current, current_tokens
        if current:
            parts.append("\n".join(current).strip())
        current = []
        current_tokens = 0

    for unit in units:
        unit = unit.strip()
        if not unit:
            continue
        unit_tokens = _rough_token_count(unit)
        if unit_tokens > hard_max:
            flush()
            parts.extend(_hard_split(unit, hard_max=hard_max, overlap=overlap))
            continue
        if current and current_tokens + unit_tokens > hard_max:
            flush()
        elif current and current_tokens + unit_tokens > target:
            flush()
        current.append(unit)
        current_tokens += unit_tokens
        if current_tokens >= target:
            flush()
    flush()
    return parts


def _hard_split(text: str, *, hard_max: int, overlap: int) -> list[str]:
    """Split an oversized unit using the same token counter as every other path."""
    parts: list[str] = []
    remaining = text.strip()
    while remaining:
        if _rough_token_count(remaining) <= hard_max:
            parts.append(remaining)
            break
        cut = _character_cut_for_tokens(remaining, hard_max)
        window = remaining[:cut]
        preferred = max(window.rfind("。"), window.rfind("；"), window.rfind("，"), window.rfind("."), window.rfind(" "))
        if preferred > cut // 2:
            cut = preferred + 1
            window = remaining[:cut]
        part = window.strip()
        if not part:
            break
        parts.append(part)
        tail = _tail_by_tokens(part, overlap)
        next_remaining = f"{tail}{remaining[cut:]}".strip() if tail else remaining[cut:].strip()
        if next_remaining == remaining:
            next_remaining = remaining[cut:].strip()
        remaining = next_remaining
    return parts


def _character_cut_for_tokens(text: str, budget: int) -> int:
    consumed = 0
    in_word = False
    for index, char in enumerate(text, start=1):
        is_cjk = "\u4e00" <= char <= "\u9fff"
        is_word = char.isascii() and (char.isalnum() or char == "_")
        if is_cjk:
            consumed += 1
            in_word = False
        elif is_word and not in_word:
            consumed += 1
            in_word = True
        elif not is_word:
            in_word = False
        if consumed >= budget:
            return index
    return len(text)


def _tail_by_tokens(text: str, budget: int) -> str:
    if budget <= 0:
        return ""
    start = len(text)
    while start > 0 and _rough_token_count(text[start - 1 :]) <= budget:
        start -= 1
    return text[start:].strip()


def _semantic_units(text: str) -> list[str]:
    units: list[str] = []
    for paragraph in re.split(r"\n{2,}", text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
        if len(lines) > 1:
            units.extend(lines)
            continue
        sentences = [part.strip() for part in SENTENCE_SPLIT_PATTERN.split(paragraph) if part.strip()]
        units.extend(sentences or [paragraph])
    return units


def _combined_metadata(blocks: list[ParsedBlock]) -> dict:
    first = blocks[0].metadata
    block_types = {str(block.metadata.get("chunk_type", "paragraph")) for block in blocks}
    page_starts = [block.metadata.get("page_start") for block in blocks if block.metadata.get("page_start") is not None]
    page_ends = [block.metadata.get("page_end") for block in blocks if block.metadata.get("page_end") is not None]
    metadata = {
        **first,
        "chunk_type": next(iter(block_types)) if len(block_types) == 1 else "section",
        "split_strategy": "section_pack",
    }
    if page_starts:
        metadata["page_start"] = min(page_starts)
    if page_ends:
        metadata["page_end"] = max(page_ends)
    return metadata


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
    return bool(line) and (line.count("|") >= 2 or bool(TABLE_SEPARATOR_PATTERN.match(line)))


def _looks_like_list_continuation(line: str) -> bool:
    return line.startswith(("（", "(", "其中", "包括", "以及", "并且"))


def _rough_token_count(text: str) -> int:
    cjk_chars = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    latin_words = len(re.findall(r"[A-Za-z0-9_]+", text))
    return cjk_chars + latin_words
