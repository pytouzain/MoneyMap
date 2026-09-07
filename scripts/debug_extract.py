"""Debug helper: show what MoneyMap extracts and parses from a PDF.

Usage:
    python scripts/debug_extract.py path\\to\\statement.pdf

It prints, per page:
  1. the RAW extracted text (so you can see the real layout), and
  2. which lines the parser KEEPS as transactions vs how they parsed.

Nothing is uploaded or stored — this runs entirely on your machine. When
sharing output for tuning, redact amounts/account numbers as you see fit;
the parser only cares about line *shape*, not the values.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running as `python scripts/debug_extract.py` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.extract import extract_text  # noqa: E402
from app.parse import parse_transactions  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/debug_extract.py <statement.pdf>")
        return 2

    pdf_path = Path(sys.argv[1])
    if not pdf_path.exists():
        print(f"File not found: {pdf_path}")
        return 2

    text = extract_text(pdf_path.read_bytes())

    print("=" * 70)
    print("RAW EXTRACTED TEXT")
    print("=" * 70)
    for i, line in enumerate(text.splitlines(), 1):
        print(f"{i:4} | {line}")

    print()
    print("=" * 70)
    print("PARSED TRANSACTIONS (what MoneyMap keeps)")
    print("=" * 70)
    txns = parse_transactions(text)
    if not txns:
        print("(none)")
    for t in txns:
        print(f"  {str(t.date):>12}  {t.amount:>12.2f}  {t.description}")

    print()
    print(f"Total lines: {len(text.splitlines())}   Kept as transactions: {len(txns)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
