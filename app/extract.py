"""Extract text from a PDF statement, in memory.

The PDF bytes are never written to disk. We also detect image-only
(scanned) PDFs so the caller can reject them with a clear message instead
of silently returning zero transactions.
"""

from __future__ import annotations

import io

import pdfplumber


class ScannedPdfError(Exception):
    """Raised when a PDF appears to be image-only (needs OCR, unsupported)."""


class UnreadablePdfError(Exception):
    """Raised when the bytes could not be opened as a PDF at all."""


def extract_text(pdf_bytes: bytes) -> str:
    """Return the concatenated text of every page.

    Raises ScannedPdfError if the document has pages but essentially no
    extractable text (a strong signal it is a scan/image).
    """
    try:
        pdf = pdfplumber.open(io.BytesIO(pdf_bytes))
    except Exception as exc:  # pdfplumber/pdfminer raise a variety of types
        raise UnreadablePdfError(str(exc)) from exc

    pages_text: list[str] = []
    with pdf:
        if not pdf.pages:
            raise UnreadablePdfError("PDF has no pages")
        for page in pdf.pages:
            pages_text.append(page.extract_text() or "")

    full_text = "\n".join(pages_text)

    # Heuristic: a real statement has plenty of characters. If we got almost
    # nothing across all pages, it's very likely a scanned/image PDF.
    if len(full_text.strip()) < 40:
        raise ScannedPdfError(
            "This PDF appears to be scanned or image-based. "
            "OCR is not supported yet — please upload a text-based statement."
        )

    return full_text
