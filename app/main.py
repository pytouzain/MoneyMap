"""MoneyMap FastAPI application."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .categorize import categorize
from .extract import ScannedPdfError, UnreadablePdfError, extract_text
from .models import AnalyzeResponse
from .parse import parse_transactions
from .summary import summarize

app = FastAPI(title="MoneyMap", version="0.1.0")

STATIC_DIR = Path(__file__).parent / "static"

# 15 MB cap — statements are small; this guards against accidental huge uploads.
MAX_UPLOAD_BYTES = 15 * 1024 * 1024


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(file: UploadFile = File(...)) -> AnalyzeResponse:
    if not (file.filename or "").lower().endswith(".pdf") and file.content_type not in (
        "application/pdf",
        "application/x-pdf",
    ):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")

    pdf_bytes = await file.read()
    if len(pdf_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 15 MB).")
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        text = extract_text(pdf_bytes)
    except ScannedPdfError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except UnreadablePdfError as exc:
        raise HTTPException(
            status_code=400, detail=f"Could not read PDF: {exc}"
        ) from exc

    warnings: list[str] = []

    transactions = parse_transactions(text)
    if not transactions:
        warnings.append(
            "No transactions were detected. The statement layout may be "
            "unusual — try a different statement or check it is text-based."
        )

    transactions, llm_used = categorize(transactions)
    summary, total_spending, total_credits = summarize(transactions)

    return AnalyzeResponse(
        transactions=transactions,
        summary=summary,
        total_spending=total_spending,
        total_credits=total_credits,
        llm_used=llm_used,
        warnings=warnings,
    )


# Serve static assets (JS/CSS) under /static.
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
