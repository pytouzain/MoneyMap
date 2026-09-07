from app.categorize import categorize
from app.models import Transaction
from app.rules import CATEGORIES, categorize_by_rules
from app.summary import summarize


def test_rules_match_common_merchants():
    assert categorize_by_rules("WHOLE FOODS MARKET") == "Groceries"
    assert categorize_by_rules("UBER TRIP 123") == "Transport"
    assert categorize_by_rules("NETFLIX.COM") == "Entertainment"
    assert categorize_by_rules("SOMETHING UNKNOWN XYZ") is None


def test_longest_keyword_wins():
    # "uber eats" (Dining) should beat "uber" (Transport).
    assert categorize_by_rules("UBER EATS ORDER") == "Dining"


def test_categorize_falls_back_to_other_without_llm(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    txns = [
        Transaction(description="WHOLE FOODS", amount=10.0),
        Transaction(description="ZZZ MYSTERY MERCHANT", amount=5.0),
    ]
    result, llm_used = categorize(txns)
    assert llm_used is False
    assert result[0].category == "Groceries"
    assert result[0].source == "rule"
    assert result[1].category == "Other"
    assert result[1].source == "none"


def test_all_rule_categories_are_valid():
    from app.rules import _KEYWORDS

    for category in _KEYWORDS.values():
        assert category in CATEGORIES


def test_summary_splits_spending_and_credits():
    txns = [
        Transaction(description="A", amount=10.0, category="Groceries"),
        Transaction(description="B", amount=20.0, category="Groceries"),
        Transaction(description="C", amount=-100.0, category="Income"),
    ]
    summary, total_spending, total_credits = summarize(txns)
    assert total_spending == 30.0
    assert total_credits == 100.0
    assert summary[0].category == "Groceries"
    assert summary[0].total == 30.0
    assert summary[0].count == 2
