"""Keyword-based categorization rules.

The rule engine matches merchant keywords in a transaction description to a
category. This handles the large majority of everyday transactions for free,
instantly, and without sending anything to an LLM.

CATEGORIES is the canonical list; the LLM fallback is constrained to it too,
so categories stay consistent across both paths.
"""

from __future__ import annotations

import re

CATEGORIES: list[str] = [
    "Groceries",
    "Dining",
    "Transport",
    "Shopping",
    "Entertainment",
    "Utilities",
    "Housing",
    "Health",
    "Travel",
    "Income",
    "Fees & Interest",
    "Transfers",
    "Other",
]

# keyword (lowercased, matched as a whole word/substring) -> category
_KEYWORDS: dict[str, str] = {
    # Groceries
    "whole foods": "Groceries", "trader joe": "Groceries", "safeway": "Groceries",
    "kroger": "Groceries", "aldi": "Groceries", "costco": "Groceries",
    "walmart": "Groceries", "grocery": "Groceries", "supermarket": "Groceries",
    "carrefour": "Groceries", "tesco": "Groceries",
    # Dining
    "starbucks": "Dining", "mcdonald": "Dining", "restaurant": "Dining",
    "cafe": "Dining", "coffee": "Dining", "pizza": "Dining", "doordash": "Dining",
    "uber eats": "Dining", "grubhub": "Dining", "chipotle": "Dining",
    "bar ": "Dining", "diner": "Dining", "deli": "Dining",
    # Transport
    "uber": "Transport", "lyft": "Transport", "shell": "Transport",
    "chevron": "Transport", "exxon": "Transport", "gas ": "Transport",
    "fuel": "Transport", "parking": "Transport", "transit": "Transport",
    "metro": "Transport", "bp ": "Transport", "toll": "Transport",
    # Shopping
    "amazon": "Shopping", "target": "Shopping", "best buy": "Shopping",
    "ebay": "Shopping", "etsy": "Shopping", "ikea": "Shopping",
    "store": "Shopping", "shop": "Shopping",
    # Entertainment
    "netflix": "Entertainment", "spotify": "Entertainment", "hulu": "Entertainment",
    "disney": "Entertainment", "cinema": "Entertainment", "movie": "Entertainment",
    "steam": "Entertainment", "playstation": "Entertainment", "xbox": "Entertainment",
    "hbo": "Entertainment", "youtube": "Entertainment",
    # Utilities
    "electric": "Utilities", "water": "Utilities", "comcast": "Utilities",
    "at&t": "Utilities", "verizon": "Utilities", "t-mobile": "Utilities",
    "internet": "Utilities", "utility": "Utilities", "phone": "Utilities",
    "gas company": "Utilities",
    # Housing
    "rent": "Housing", "mortgage": "Housing", "landlord": "Housing",
    "hoa": "Housing", "property": "Housing",
    # Health
    "pharmacy": "Health", "cvs": "Health", "walgreens": "Health",
    "doctor": "Health", "dental": "Health", "clinic": "Health",
    "hospital": "Health", "fitness": "Health", "gym": "Health",
    # Travel
    "airline": "Travel", "airlines": "Travel", "hotel": "Travel",
    "airbnb": "Travel", "expedia": "Travel", "delta air": "Travel",
    "united air": "Travel", "marriott": "Travel", "hilton": "Travel",
    "booking.com": "Travel",
    # Income
    "payroll": "Income", "salary": "Income", "direct deposit": "Income",
    "deposit": "Income", "refund": "Income",
    # Fees & Interest
    "interest": "Fees & Interest", "fee": "Fees & Interest",
    "overdraft": "Fees & Interest", "service charge": "Fees & Interest",
    "atm": "Fees & Interest", "finance charge": "Fees & Interest",
    # Transfers
    "transfer": "Transfers", "venmo": "Transfers", "zelle": "Transfers",
    "paypal": "Transfers", "cash app": "Transfers", "wire": "Transfers",
    "payment thank you": "Transfers", "autopay": "Transfers",
}


def categorize_by_rules(description: str) -> str | None:
    """Return a category for the description, or None if no rule matches."""
    text = description.lower()
    # Prefer the longest matching keyword (more specific wins).
    best: tuple[int, str] | None = None
    for keyword, category in _KEYWORDS.items():
        if keyword in text:
            if best is None or len(keyword) > best[0]:
                best = (len(keyword), category)
    return best[1] if best else None
