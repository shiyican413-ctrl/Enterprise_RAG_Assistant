import csv
import json
from pathlib import Path


class UnsupportedDocumentType(ValueError):
    pass


def load_document_text(path: Path) -> str:
    suffix = path.suffix.lower()

    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="ignore")

    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        return json.dumps(payload, ensure_ascii=False, indent=2)

    if suffix == ".csv":
        with path.open("r", encoding="utf-8", errors="ignore", newline="") as file:
            rows = list(csv.reader(file))
        return "\n".join(" | ".join(cell.strip() for cell in row) for row in rows)

    if suffix == ".pdf":
        return _load_pdf(path)

    raise UnsupportedDocumentType(f"Unsupported document type: {suffix}")


def _load_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise UnsupportedDocumentType(
            "PDF support requires installing optional dependency: pypdf"
        ) from exc

    reader = PdfReader(str(path))
    pages: list[str] = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n\n".join(pages).strip()
