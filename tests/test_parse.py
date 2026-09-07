from app.parse import parse_transactions


def test_parses_common_layout():
    text = """
    Date        Description                 Amount
    01/03/2024  WHOLE FOODS MARKET          54.20
    01/05/2024  UBER TRIP                    18.75
    01/07/2024  PAYROLL DIRECT DEPOSIT    2,500.00 CR
    """
    txns = parse_transactions(text)
    descs = {t.description for t in txns}
    assert any("WHOLE FOODS" in d for d in descs)
    assert any("UBER" in d for d in descs)

    uber = next(t for t in txns if "UBER" in t.description)
    assert uber.amount == 18.75
    assert uber.date == "01/05/2024"


def test_credit_marker_is_negative():
    text = "01/07/2024  PAYROLL DIRECT DEPOSIT  2,500.00 CR"
    (txn,) = parse_transactions(text)
    assert txn.amount == -2500.0


def test_parentheses_negative():
    text = "2024-02-01 REFUND AMAZON (25.00)"
    (txn,) = parse_transactions(text)
    assert txn.amount == -25.0
    assert txn.date == "2024-02-01"


def test_currency_symbol_and_month_name_date():
    text = "Jan 15, 2024  STARBUCKS STORE 123  $6.45"
    (txn,) = parse_transactions(text)
    assert txn.amount == 6.45
    assert "STARBUCKS" in txn.description


def test_ignores_non_transaction_lines():
    text = """
    ACME BANK STATEMENT
    Account Number: 1234
    Page 1 of 3
    """
    assert parse_transactions(text) == []


def test_ignores_summary_amounts_without_dates():
    # The Amex-style account-summary box: labels and amounts with no dates.
    text = """
    Pay Over Time Limit
    Available Pay Over Time Limit
    $6,000.00
    $5,239.36
    01/12/2024  STARBUCKS STORE 123  6.45
    """
    txns = parse_transactions(text)
    assert len(txns) == 1
    assert "STARBUCKS" in txns[0].description
    assert txns[0].amount == 6.45


def test_ignores_dated_summary_rows():
    # Some summary rows do carry a date; they must still be dropped.
    text = """
    01/15/2024  Previous Balance            1,234.56
    01/15/2024  Minimum Payment Due           35.00
    01/16/2024  WHOLE FOODS MARKET            54.20
    """
    txns = parse_transactions(text)
    descs = [t.description for t in txns]
    assert descs == ["WHOLE FOODS MARKET"] or (
        len(txns) == 1 and "WHOLE FOODS" in txns[0].description
    )


def test_amount_line_without_date_is_ignored():
    assert parse_transactions("$6,000.00") == []
    assert parse_transactions("Available Pay Over Time Limit $5,239.36") == []
