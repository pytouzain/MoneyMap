"""Aggregate categorized transactions into a summary."""

from __future__ import annotations

from collections import defaultdict

from .models import CategorySummary, Transaction


def summarize(transactions: list[Transaction]) -> tuple[list[CategorySummary], float, float]:
    """Return (per-category summary, total_spending, total_credits).

    Spending totals only include money out (positive amounts). Credits are
    reported separately. The per-category list is sorted by total spend
    descending and excludes categories with no spending.
    """
    totals: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
    total_spending = 0.0
    total_credits = 0.0

    for txn in transactions:
        if txn.amount >= 0:
            totals[txn.category] += txn.amount
            counts[txn.category] += 1
            total_spending += txn.amount
        else:
            total_credits += -txn.amount

    summary = [
        CategorySummary(category=cat, total=round(total, 2), count=counts[cat])
        for cat, total in totals.items()
        if total > 0
    ]
    summary.sort(key=lambda s: s.total, reverse=True)

    return summary, round(total_spending, 2), round(total_credits, 2)
