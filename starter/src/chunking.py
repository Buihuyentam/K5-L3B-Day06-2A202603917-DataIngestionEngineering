"""Traceable fixed-size and paragraph-aware chunking."""
import hashlib
import re

from .models import Chunk, DocumentPage

_TOP_LEVEL_HEADINGS = {
    "1. Introduction",
    "2. Authentication Assurance Levels",
    "3. Authenticator and Verifier Requirements",
    "4. Authenticator Event Management",
    "5. Session Management",
    "6. Threats and Security Considerations",
    "7. Privacy Considerations",
    "8. Customer Experience Considerations",
}


def _chunk(page: DocumentPage, index: int, text: str) -> Chunk:
    stable_key = f"{page.document_id}\0{page.page}\0{index}\0{text}"
    chunk_id = hashlib.sha256(stable_key.encode("utf-8")).hexdigest()
    return Chunk(
        chunk_id,
        page.document_id,
        page.source,
        page.page,
        text,
        dict(page.metadata),
    )


def _split_oversized(text: str, max_size: int) -> list[str]:
    result: list[str] = []
    remaining = text.strip()
    while len(remaining) > max_size:
        split_at = remaining.rfind(" ", 0, max_size + 1)
        if split_at < max_size // 2:
            split_at = max_size
        result.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    if remaining:
        result.append(remaining)
    return result


def _is_heading(paragraph: str) -> bool:
    return (
        paragraph in _TOP_LEVEL_HEADINGS
        or bool(re.match(r"^\d+(?:\.\d+)+\.\s+\S", paragraph))
        or bool(re.match(r"^Appendix [AB]\.\s+\S", paragraph))
    )


def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    """Split a page into overlapping character windows, retaining its metadata."""
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("size must be positive and overlap must be in [0, size)")
    text = page.text.strip()
    if not text:
        return []
    chunks: list[Chunk] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundary = text.rfind(" ", start, end + 1)
            if boundary > start + size // 2:
                end = boundary
        piece = text[start:end].strip()
        if piece:
            chunks.append(_chunk(page, len(chunks), piece))
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return chunks


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    """Group adjacent paragraphs up to a size limit; split only oversized ones."""
    if max_size <= 0:
        raise ValueError("max_size must be positive")
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", page.text) if part.strip()]
    attached: list[str] = []
    index = 0
    while index < len(paragraphs):
        if not _is_heading(paragraphs[index]):
            attached.append(paragraphs[index])
            index += 1
            continue
        headings = [paragraphs[index]]
        index += 1
        while index < len(paragraphs) and _is_heading(paragraphs[index]):
            headings.append(paragraphs[index])
            index += 1
        if index < len(paragraphs):
            headings.append(paragraphs[index])
            index += 1
        attached.append("\n\n".join(headings))

    grouped: list[str] = []
    current = ""
    for paragraph in attached:
        pieces = _split_oversized(paragraph, max_size)
        for piece in pieces:
            if current and len(current) + 2 + len(piece) > max_size:
                grouped.append(current)
                current = ""
            current = f"{current}\n\n{piece}".strip()
    if current:
        grouped.append(current)
    return [_chunk(page, index, text) for index, text in enumerate(grouped)]
