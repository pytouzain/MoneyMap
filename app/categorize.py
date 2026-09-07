"""Categorize transactions: rules first, LLM fallback for the leftovers.

Privacy note: only the bare merchant *description* strings of transactions
that the rule engine could not classify are sent to the LLM. Amounts, dates,
account numbers, and balances never leave the server.
"""

from __future__ import annotations

import json
import os

from .models import Transaction
from .rules import CATEGORIES, categorize_by_rules

DEFAULT_MODEL = os.environ.get("MONEYMAP_MODEL", "claude-haiku-4-5")


def categorize(transactions: list[Transaction]) -> tuple[list[Transaction], bool]:
    """Assign a category to every transaction.

    Returns (transactions, llm_used).
    """
    unmatched_descriptions: list[str] = []

    for txn in transactions:
        category = categorize_by_rules(txn.description)
        if category:
            txn.category = category
            txn.source = "rule"
        else:
            unmatched_descriptions.append(txn.description)

    llm_used = False
    if unmatched_descriptions:
        # De-duplicate to keep the LLM request small and cheap.
        unique = sorted(set(unmatched_descriptions))
        mapping = _categorize_with_llm(unique)
        if mapping:
            llm_used = True
            for txn in transactions:
                if txn.source == "none":
                    guess = mapping.get(txn.description)
                    if guess and guess in CATEGORIES:
                        txn.category = guess
                        txn.source = "llm"

    # Anything still unresolved -> "Other".
    for txn in transactions:
        if txn.source == "none":
            txn.category = "Other"

    return transactions, llm_used


def _categorize_with_llm(descriptions: list[str]) -> dict[str, str] | None:
    """Ask the LLM to map each description to a category.

    Returns a {description: category} dict, or None if the LLM is
    unavailable (no API key, SDK missing, or a call error) so the caller
    can fall back to rules-only gracefully.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        import anthropic
    except ImportError:
        return None

    prompt = (
        "You categorize bank/credit-card transaction descriptions into a "
        "fixed set of spending categories.\n\n"
        f"Allowed categories (use these exact strings): {', '.join(CATEGORIES)}\n\n"
        "Return ONLY a JSON object mapping each input description (verbatim) "
        "to exactly one category. No prose, no code fences.\n\n"
        "Descriptions:\n"
        + "\n".join(f"- {d}" for d in descriptions)
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = "".join(
            block.text for block in message.content if block.type == "text"
        ).strip()
        return _parse_llm_json(raw)
    except Exception:
        # Any failure (auth, network, malformed output) -> rules-only.
        return None


def _parse_llm_json(raw: str) -> dict[str, str] | None:
    """Extract a {str: str} mapping from the model's response."""
    if not raw:
        return None
    # Be tolerant of stray code fences.
    if raw.startswith("```"):
        raw = raw.strip("`")
        # drop a possible leading "json" language hint
        raw = raw[4:] if raw.lower().startswith("json") else raw
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        data = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return {str(k): str(v) for k, v in data.items()}
