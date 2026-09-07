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

# Lines that begin with a date but are NOT spending — statement summary rows,
# balances, limits, payment info. Matched case-insensitively against the
# description. Kept deliberately specific so real merchants (e.g. "TOTAL WINE")
# are not caught.
_SUMMARY_LABELS = (
    "previous balance",
    "new balance",
    "statement balance",
    "balance carried",
    "minimum payment",
    "payment due",
    "amount due",
    "credit limit",
    "available credit",
    "cash advance limit",
    "available cash",
    "pay over time limit",
    "available pay over time",
    "total available",
    "closing date",
    "opening balance",
    "closing balance",
    "account summary",
)


def _is_summary_label(description: str) -> bool:
    text = description.lower()
    return any(label in text for label in _SUMMARY_LABELS)


# Leading wallet/payment-method prefixes to drop from a merchant name.
_PAYMENT_PREFIXES = {
    "aplpay", "applepay", "gglpay", "gpay", "googlepay",
    "tapandpay", "contactless",
}

# Trailing 2-letter location codes (US states + common country codes) that
# statements append after the city. Only stripped when it is the final token.
_LOCATION_CODES = {
    # US states + DC / PR
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
    "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
    "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
    "WI", "WY", "DC", "PR",
    # common country codes
    "US", "UK", "GB", "MX", "FR", "DE", "ES", "IT", "NL", "BE", "CH", "AT",
    "PT", "IE", "SE", "NO", "DK", "FI", "PL", "CZ", "GR", "HU", "RO", "LU",
    "JP", "CN", "KR", "SG", "HK", "AE", "AU", "NZ", "BR", "AR", "CL", "ZA",
    "IL", "TR", "TH", "VN", "PH", "MY",
}


def _is_noise_token(token: str) -> bool:
    """True for a token that is a phone number or a URL/domain, not a name."""
    if re.fullmatch(r"\+?\d[\d\-().]{5,}\d", token):  # phone number
        return True
    if "/" in token or token.endswith("#"):  # url path / help code
        return True
    if re.search(r"\.[A-Za-z]{2,}", token):  # domain (amazon.com, g.co)
        return True
    return False


def _is_word(token: str) -> bool:
    """A substantive name token: has letters and is not a location code."""
    if token.strip(".,").upper() in _LOCATION_CODES:
        return False
    return bool(re.search(r"[A-Za-z]{2,}", token))

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

# Decorative symbols some issuers append to an amount (e.g. Amex's "Pay Over
# Time" lozenge "⧫", posting-date asterisks, bullets). Stripped from the end
# of a line before the amount is matched.
_TRAILING_DECORATION = "*⧫◆✦♦●•· \t"

# --- amount pattern ----------------------------------------------------------
# Matches the LAST money-looking token on a line. Handles $/€/£, thousands
# separators, decimals, a minus on either side of the currency symbol
# (-$8.70 and $-8.70), parentheses for negatives, and a trailing CR/DR marker.
_AMOUNT_RE = re.compile(
    r"""
    (?P<paren_open>\()?          # optional opening paren (negative)
    \s*(?P<sign1>-)?\s*          # optional minus BEFORE the currency symbol
    (?P<cur>[$€£])?\s*           # optional currency symbol
    (?P<sign2>-)?                # optional minus AFTER the currency symbol
    (?P<num>\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)
    (?P<paren_close>\))?         # optional closing paren
    \s*(?P<marker>CR|DR)?        # optional credit/debit marker
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


def _parse_amount(token_region: str) -> tuple[float, str] | None:
    """Parse a trailing amount from the given text.

    Returns (amount, text_without_amount) or None. Amount is positive for
    spending (money out) and negative for credits/refunds.
    """
    # Drop decorative trailing symbols (e.g. Amex's "⧫") so the amount is at
    # the true end of the line where the regex can anchor to it.
    region = token_region.rstrip(_TRAILING_DECORATION)

    m = _AMOUNT_RE.search(region)
    if not m:
        return None
    num = float(m.group("num").replace(",", ""))
    if num == 0:
        # A bare "0.00" is rarely a real transaction line on its own; skip.
        return None

    marker = m.group("marker")
    is_negative = bool(
        m.group("paren_open")
        or m.group("paren_close")
        or m.group("sign1")
        or m.group("sign2")
        or (marker and marker.upper() == "CR")
    )
    # Credit (CR) means money in -> negative spending. DR / plain -> positive.
    amount = -num if is_negative else num
    remainder = region[: m.start()].rstrip()
    return amount, remainder


def parse_transactions(text: str) -> list[Transaction]:
    """Parse statement text into a list of transactions."""
    transactions: list[Transaction] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        date, rest = _find_date(line)

        # A real transaction line begins with a date. Requiring one is the
        # single most effective filter: it drops account-summary rows,
        # balances, and credit limits (e.g. "Pay Over Time Limit $6,000.00")
        # that carry an amount but no date.
        if date is None:
            continue

        parsed = _parse_amount(rest)
        if parsed is None:
            continue
        amount, description = parsed

        description = _clean_description(description)
        if not description:
            continue
        # A line that's only a date + amount with no description is suspicious.
        if len(description) < 2:
            continue

        # Some summary rows (payment due, balances) do carry a date; drop them.
        if _is_summary_label(description):
            continue

        transactions.append(
            Transaction(date=date, description=description, amount=amount)
        )

    return transactions


def _clean_description(desc: str) -> str:
    """Tidy a raw description into a readable merchant name.

    Removes wallet prefixes, phone numbers, URLs, foreign-currency amounts,
    and a trailing state/country code, while never erasing the whole name.
    """
    desc = re.sub(r"\s+", " ", desc).strip()
    # Leading posting-date asterisk / decoration (e.g. "07/16/26*  MERCHANT").
    desc = re.sub(r"^[*⧫◆✦♦●•·\s]+", "", desc)
    # Trailing foreign-currency amount that precedes the USD amount on
    # international charges, e.g. "... AIX EN PROVENCE FR 7,60" (comma decimal).
    desc = re.sub(r"\s+\d{1,3}(?:[.\s]\d{3})*,\d{2}$", "", desc).strip()
    # A running-balance figure some statements append after the amount.
    desc = re.sub(r"\s+[$€£]?-?\d{1,3}(?:,\d{3})*\.\d{2}$", "", desc).strip()

    tokens = desc.split()
    # Drop a leading wallet prefix (Apple Pay, Google Pay, ...).
    if tokens and tokens[0].lower() in _PAYMENT_PREFIXES:
        tokens = tokens[1:]

    # Drop phone/URL noise tokens, but never the first token: the merchant name
    # leads the line and can itself be a domain (e.g. "SEATS.AERO"). If the
    # result still has no real word, fall back to the original tokens.
    if tokens:
        kept = [tokens[0]] + [t for t in tokens[1:] if not _is_noise_token(t)]
    else:
        kept = tokens
    if not any(_is_word(t) for t in kept):
        kept = tokens

    # Strip a single trailing state/country code (keeping at least one token).
    if len(kept) > 1 and kept[-1].strip(".,").upper() in _LOCATION_CODES:
        kept.pop()

    result = " ".join(kept).strip()
    return result or desc
