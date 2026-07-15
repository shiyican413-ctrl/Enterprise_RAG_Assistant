from pathlib import Path

from backend.ai_service.knowledge.loaders.document_loader import load_document_text


class DocumentParserService:
    """Structure-first parser with optional Docling/Unstructured backends.

    The optional parsers return Markdown-like text so the existing splitter can
    preserve headings, tables, lists, FAQ blocks, and page markers.
    """

    def parse(self, path: Path) -> str:
        for parser in (_parse_with_docling, _parse_with_unstructured):
            text = parser(path)
            if text:
                return text
        return load_document_text(path)


def _parse_with_docling(path: Path) -> str:
    try:
        from docling.document_converter import DocumentConverter
    except Exception:
        return ""

    try:
        result = DocumentConverter().convert(str(path))
        document = getattr(result, "document", None)
        if document is None:
            return ""
        if hasattr(document, "export_to_markdown"):
            return str(document.export_to_markdown()).strip()
        if hasattr(document, "export_to_text"):
            return str(document.export_to_text()).strip()
    except Exception:
        return ""
    return ""


def _parse_with_unstructured(path: Path) -> str:
    try:
        from unstructured.partition.auto import partition
    except Exception:
        return ""

    try:
        elements = partition(filename=str(path))
    except Exception:
        return ""

    parts: list[str] = []
    for element in elements:
        text = str(element).strip()
        if not text:
            continue
        category = str(getattr(element, "category", "") or "")
        metadata = getattr(element, "metadata", None)
        page_number = getattr(metadata, "page_number", None) if metadata else None
        if page_number:
            marker = f"[[page:{page_number}]]"
            if not parts or parts[-1] != marker:
                parts.append(marker)
        if category == "Title":
            parts.append(f"## {text}")
        elif category == "Table":
            parts.append(_normalize_table_text(text))
        elif category in {"ListItem", "BulletedText"}:
            parts.append(f"- {text}")
        else:
            parts.append(text)
    return "\n\n".join(parts).strip()


def _normalize_table_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return text
    if any("|" in line for line in lines):
        return "\n".join(lines)
    rows = [line.split("\t") for line in lines]
    if not any(len(row) > 1 for row in rows):
        return text
    width = max(len(row) for row in rows)
    normalized = [row + [""] * (width - len(row)) for row in rows]
    output = ["| " + " | ".join(row) + " |" for row in normalized]
    if len(output) > 1:
        output.insert(1, "| " + " | ".join("---" for _ in range(width)) + " |")
    return "\n".join(output)
