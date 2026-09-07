# 🗺️ MoneyMap

Drop a bank or credit-card statement (PDF) and MoneyMap analyzes it, parses
the transactions, and sorts each one into a spending category — then shows you
a summary and a per-category breakdown.

This is the **MVP**: one input format (text-based PDF), a rule-based
categorizer with an AI fallback, and a minimal single-page UI.

## How it works

```
PDF statement → extract text → parse transactions → categorize → summarize
   (in memory)   (pdfplumber)   (heuristic regex)   (rules + LLM)  (per category)
```

- **Extraction** (`app/extract.py`) reads the PDF **in memory** — it is never
  written to disk. Scanned/image-only PDFs are detected and rejected with a
  clear message (OCR is out of scope for the MVP).
- **Parsing** (`app/parse.py`) uses a single layout-agnostic heuristic: it
  finds lines shaped like `date … description … amount`. It handles the common
  US/EU date and money formats, `CR`/`DR` markers, and parenthesized negatives.
- **Categorization** (`app/categorize.py`) tries a keyword **rule engine**
  first (`app/rules.py`). Only the descriptions it *can't* match are sent,
  batched and de-duplicated, to the LLM. If no `ANTHROPIC_API_KEY` is set the
  app runs **rules-only** and still works.
- **Summary** (`app/summary.py`) aggregates spending per category.

The parsed table is editable in the UI, so any parsing or categorization miss
can be corrected by hand — the UI is the safety net.

## Privacy model (server-side hybrid)

- The PDF is uploaded to the server, parsed in memory, and discarded.
- Amounts, dates, account numbers, and balances **never** leave the server.
- Only bare merchant **description strings** of unmatched transactions are sent
  to the LLM.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# optional: enable the AI fallback
cp .env.example .env   # then put your ANTHROPIC_API_KEY in .env
export $(grep -v '^#' .env | xargs)   # or use your own env loader

uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 and upload a PDF statement.

Without an `ANTHROPIC_API_KEY`, categorization uses the rule engine only;
unmatched transactions fall into **Other**.

## Test

```bash
pip install pytest
pytest
```

## Not in the MVP (deliberately deferred)

- OCR for scanned/image PDFs
- Bank-specific tuned parsers
- Accounts, login, and persistent history
- Multi-currency handling
- CSV/OFX/QFX import

## Project layout

```
app/
  main.py        FastAPI app + /api/analyze endpoint
  extract.py     PDF → text (in memory), scanned-PDF detection
  parse.py       text → transactions (heuristic)
  rules.py       keyword → category rules + canonical category list
  categorize.py  rules-first categorization with LLM fallback
  summary.py     per-category aggregation
  models.py      pydantic models
  static/        minimal HTML/CSS/JS frontend
tests/           parser + categorizer tests
```
