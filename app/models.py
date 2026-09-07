"""Shared data models for MoneyMap."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class Transaction(BaseModel):
    """A single parsed statement line."""

    date: Optional[str] = None  # ISO-ish string as found on the statement
    description: str
    amount: float  # positive = money out (spending), negative = credit/refund
    category: str = "Uncategorized"
    # How the category was assigned: "rule", "llm", "user", or "none".
    source: str = "none"


class CategorySummary(BaseModel):
    category: str
    total: float
    count: int


class AnalyzeResponse(BaseModel):
    transactions: list[Transaction]
    summary: list[CategorySummary]
    total_spending: float
    total_credits: float
    llm_used: bool
    warnings: list[str] = []
