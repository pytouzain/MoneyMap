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


# --- American Express Gold Card format ---------------------------------------

def test_amex_charge_with_lozenge_marker():
    # Charges end with a "⧫" (Pay Over Time) marker that must not defeat the
    # amount match. The trailing state code is stripped; the city is kept.
    text = "07/18/26 Paramount+ SAN FRANCISCO CA $13.99⧫"
    (txn,) = parse_transactions(text)
    assert txn.amount == 13.99
    assert txn.description == "Paramount+ SAN FRANCISCO"


def test_amex_payment_minus_before_currency_is_credit():
    # "-$8.70": minus precedes the currency symbol, and a posting-date "*"
    # follows the date.
    text = "07/16/26* MOBILE PAYMENT - THANK YOU -$8.70"
    (txn,) = parse_transactions(text)
    assert txn.amount == -8.70
    assert txn.description == "MOBILE PAYMENT - THANK YOU"


def test_amex_foreign_charge_strips_foreign_amount():
    # International charge: a comma-decimal foreign amount precedes the USD one.
    # The wallet prefix and trailing country code are also removed.
    text = "07/14/26 AplPay ENJOY SUSHI AIX EN PROVENCE FR 18,50 $21.21⧫"
    (txn,) = parse_transactions(text)
    assert txn.amount == 21.21
    assert txn.description == "ENJOY SUSHI AIX EN PROVENCE"


def test_description_tidyup_strips_phone_url_and_location():
    cases = {
        "07/19/26 SPECTRUM 855-707-7328 MO $74.99⧫": "SPECTRUM",
        "07/27/26 Amazon Prime Amazon.com WA $16.45⧫": "Amazon Prime",
        "08/11/26 GOOGLE *YOUTUBEPREMIUM G.CO/HELPPAY# CA $15.99⧫": "GOOGLE *YOUTUBEPREMIUM",
        "08/02/26 PAYPAL *SNCFVOYAGEU 0646234299 FR 44,75 $51.62⧫": "PAYPAL *SNCFVOYAGEU",
    }
    for line, expected in cases.items():
        (txn,) = parse_transactions(line)
        assert txn.description == expected, f"{line!r} -> {txn.description!r}"


def test_tidyup_never_empties_description():
    # If cleanup would remove everything, the name is preserved.
    (txn,) = parse_transactions("07/27/26 AMAZON.COM WA $16.45")
    assert txn.description  # non-empty
    assert "AMAZON" in txn.description.upper()


def test_tidyup_keeps_merchant_that_is_a_domain():
    # The first token is the merchant even when it is a domain like SEATS.AERO;
    # it must not be dropped as URL noise.
    (txn,) = parse_transactions("07/31/26 SEATS.AERO WILMINGTON DE $9.99⧫")
    assert "SEATS.AERO" in txn.description


def test_amex_continuation_lines_are_ignored():
    # Lines below a charge (city, "European Union", "Euro", category) have no
    # date and must be dropped.
    text = """07/14/26 AplPay LOUCAU AIX EN PROVENCE FR 7,60 $8.70⧫
European Union
thomas.lacrambe@laddition Euro
RESTAURANT Euro"""
    txns = parse_transactions(text)
    assert len(txns) == 1
    assert txns[0].amount == 8.70
