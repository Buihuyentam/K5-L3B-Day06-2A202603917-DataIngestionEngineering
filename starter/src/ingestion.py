"""PDF extraction with physical-page traceability."""
from pathlib import Path
import re
import unicodedata

from pypdf import PdfReader

from .models import DocumentPage

_REPEATED_HEADER = {
    "NIST SP 800-63B-4",
    "July 2025",
    "Digital Identity Guidelines",
    "Authentication and Authenticator Management",
}
_TOP_LEVEL_SECTIONS = {
    "1": "1. Introduction",
    "2": "2. Authentication Assurance Levels",
    "3": "3. Authenticator and Verifier Requirements",
    "4": "4. Authenticator Event Management",
    "5": "5. Session Management",
    "6": "6. Threats and Security Considerations",
    "7": "7. Privacy Considerations",
    "8": "8. Customer Experience Considerations",
}


def normalize_text(text: str) -> str:
    """Normalize Unicode and whitespace while keeping paragraph/list boundaries."""
    text = unicodedata.normalize("NFKC", text).replace("\r\n", "\n").replace("\r", "\n")
    paragraphs: list[str] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            paragraphs.append(" ".join(current))
            current.clear()

    for raw_line in text.split("\n"):
        line = re.sub(r"[ \t]+", " ", raw_line).strip()
        if not line:
            flush()
            continue
        if line.startswith(("•", "▪", "–", "—")) or re.match(r"^\d+\.\s", line):
            flush()
            paragraphs.append(line)
        else:
            current.append(line)
    flush()
    normalized = "\n\n".join(paragraphs).strip()
    return re.sub(r"\s+([,.;:!?])", r"\1", normalized)


def _section_for_page(lines: list[str], current: str) -> str:
    for line in lines:
        match = re.match(r"^([1-8])\.\s+(.+)$", line.strip())
        if match and _TOP_LEVEL_SECTIONS[match.group(1)] == line.strip():
            return _TOP_LEVEL_SECTIONS[match.group(1)]
        appendix = re.match(r"^Appendix ([AB])\.\s+(.+)$", line.strip())
        if appendix:
            return f"Appendix {appendix.group(1)}. {appendix.group(2)}"
    return current


def load_pdf(path: Path, document_id: str, source: str) -> list[DocumentPage]:
    """Extract every physical page; preserve failures and empty-page records."""
    reader = PdfReader(str(path))
    pages: list[DocumentPage] = []
    section = "unclassified"
    for page_number, pdf_page in enumerate(reader.pages, start=1):
        try:
            raw_text = pdf_page.extract_text() or ""
            lines = [line.strip() for line in raw_text.splitlines()]
            lines = [line for line in lines if line and line not in _REPEATED_HEADER]
            printed_page = str(page_number - 11)
            if page_number >= 12 and lines and lines[-1] == printed_page:
                lines.pop()
            section = _section_for_page(lines, section)
            text = normalize_text("\n".join(lines))
            metadata = {
                "source_id": document_id,
                "section": section,
                "extraction_status": "empty" if not text else "ok",
                "replacement_characters": raw_text.count("\ufffd"),
            }
            if "\ufffd" in raw_text:
                metadata["extraction_warning"] = "PDF font mapping produced replacement characters"
            pages.append(DocumentPage(document_id, source, page_number, text, metadata))
        except Exception as exc:
            pages.append(
                DocumentPage(
                    document_id,
                    source,
                    page_number,
                    "",
                    {
                        "source_id": document_id,
                        "section": section,
                        "extraction_status": "failed",
                        "extraction_error": f"{type(exc).__name__}: {exc}",
                    },
                )
            )
    return pages
