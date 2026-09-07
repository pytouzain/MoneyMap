"""Heuristic transaction parser.

Bank statements vary wildly, so rather than write a parser per bank we look
for lines that have the universal shape of a transaction:

    <date> <description ...> <amount>

We support the common US/EU date formats and money formats, and we make a
best effort at the sign convention (money leaving the account is positive
"spending"; refunds/credits are negative).

The parsed table is meant to be shown to the user for correction, so
occasional misses are acceptable — the UI is the safety net.
"""

from __future__ import annotations

import re

from .models import Transaction

# --- date patterns -----------------------------------------------------------
# Matched at the START of a (stripped) line.
_MONTHS = (
    r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
    r"|January|February|March|April|May|June|July|August"
    r"|September|October|November|December"
)
_DATE_PATTERNS = [
    re.compile(r"^(\d{4}-\d{2}-\d{2})\b"),                      # 2024-01-31
    re.compile(r"^(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b"),          # 01/31/2024, 31-01-24
    re.compile(r"^(\d{1,2}[/-]\d{1,2})\b"),                     # 01/31 (no year)
    re.compile(rf"^((?:{_MONTHS})\.?\s+\d{{1,2}}(?:,?\s+\d{{4}})?)\b", re.I),  # Jan 31, 2024
    re.compile(rf"^(\d{{1,2}}\s+(?:{_MONTHS})\.?(?:\s+\d{{4}})?)\b", re.I),    # 31 Jan 2024
]

# --- amount pattern ----------------------------------------------------------
# Matches the LAST money-looking token on a line. Handles $, thousands
# separators, decimals, trailing/leading minus, parentheses for negatives,
# and a trailing CR/DR marker.
_AMOUNT_RE = re.compile(
    r"""
    (?P<paren_open>\()?          # optional opening paren (negative)
    \s*(?P<cur>[$€£])?\s*        # optional currency symbol
    (?P<sign>-)?                 # optional leading minus
    (?P<num>\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)
    (?P<paren_close>\))?         # optional closing paren
    \s*(?P<marker>CR|DR|-)?      # optional credit/debit marker or trailing minus
    \s*$
    """,
    re.VERBOSE | re.IGNORECASE,
)


def _find_date(line: str) -> tuple[str | None, str]:
    """Return (date_str_or_None, remainder_after_date)."""
    for pat in _DATE_PATTERNS:
        m = pat.match(line)
        if m:
            return m.group(1), line[m.end():].strip()
    return None, line


def _parse_amount(token_region: str) -> tuple[float, str, bool] | None:
    """Parse a trailing amount from the given text.

    Returns (amount, text_without_amount, has_cents) or None. Amount is
    positive for spending (money out) and negative for credits/refunds.
    has_cents indicates the amount had an explicit decimal part, which the
    caller uses to reject non-transaction noise (e.g. "Page 1 of 3").
    """
    m = _AMOUNT_RE.search(token_region)
    if not m:
        return None
    num_str = m.group("num")
    num = float(num_str.replace(",", ""))
    if num == 0:
        # A bare "0.00" is rarely a real transaction line on its own; skip.
        return None

    has_cents = "." in num_str
    is_negative = bool(
        m.group("paren_open")
        or m.group("paren_close")
        or m.group("sign")
        or (m.group("marker") and m.group("marker").upper() in {"-", "CR"})
    )
    # Credit (CR) means money in -> negative spending. DR / plain -> positive.
    amount = -num if is_negative else num
    remainder = token_region[: m.start()].rstrip()
    return amount, remainder, has_cents


def parse_transactions(text: str) -> list[Transaction]:
    """Parse statement text into a list of transactions."""
    transactions: list[Transaction] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        date, rest = _find_date(line)

        parsed = _parse_amount(rest)
        if parsed is None:
            continue
        amount, description, has_cents = parsed

        # Reject non-transaction noise: a real transaction line has either a
        # recognizable date or an amount with explicit cents (usually both).
        # This filters out lines like "Account Number: 1234" or "Page 1 of 3".
        if date is None and not has_cents:
            continue

        description = _clean_description(description)
        if not description:
            continue
        # A line that's only a date + amount with no description is suspicious.
        if len(description) < 2:
            continue

        transactions.append(
            Transaction(date=date, description=description, amount=amount)
        )

    return transactions


def _clean_description(desc: str) -> str:
    """Tidy a raw description: collapse whitespace, drop leading balance-ish
    numeric noise that some statements put between description and amount."""
    desc = re.sub(r"\s+", " ", desc).strip()
    # Some statements append a running balance after the amount; if a second
    # money token leaked into the description tail, trim an obvious trailing
    # balance figure.
    desc = re.sub(r"\s+[$€£]?-?\d{1,3}(?:,\d{3})*(?:\.\d{2})?$", "", desc).strip()
    return desc
