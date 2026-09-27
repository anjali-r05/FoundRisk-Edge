from app.services import metric_normalizer as norm


def test_parse_value_crore():
    result = norm.parse_value("Revenue reached ₹4.2 Cr in FY25.")
    assert result is not None
    assert result["normalized_value"] == 4.2 * 1e7
    assert result["currency"] == "INR"
    assert result["original_unit"].lower() == "cr"


def test_parse_value_lakh():
    result = norm.parse_value("We raised ₹25 Lakh in seed funding.")
    assert result["normalized_value"] == 25 * 1e5


def test_parse_value_usd_million():
    result = norm.parse_value("TAM is estimated at $2M.")
    assert result["normalized_value"] == 2_000_000
    assert result["currency"] == "USD"


def test_parse_value_bare_thousand_customers():
    values = norm.find_all_values("We have 10K customers.")
    assert len(values) == 1
    assert values[0]["normalized_value"] == 10_000


def test_bare_number_without_currency_or_magnitude_is_skipped():
    # "3" alone with no currency/magnitude is too ambiguous to treat as a metric value
    values = norm.find_all_values("We closed 3 deals this week.")
    assert values == []


def test_zero_value_is_skipped():
    values = norm.find_all_values("₹0 Cr in outstanding debt.")
    assert values == []


def test_currency_never_silently_converted():
    inr_result = norm.parse_value("₹5 Cr revenue")
    usd_result = norm.parse_value("$5M revenue")
    assert inr_result["currency"] == "INR"
    assert usd_result["currency"] == "USD"
    # normalized_value is the magnitude-adjusted number only, not cross-currency converted
    assert inr_result["normalized_value"] == 5e7
    assert usd_result["normalized_value"] == 5e6


def test_parse_period_fiscal_year():
    raw, normalized = norm.parse_period("Revenue in FY25 grew significantly.")
    assert raw.upper().replace(" ", "") == "FY25"
    assert normalized == "FY2025"


def test_parse_period_quarter():
    raw, normalized = norm.parse_period("Q1 2026 bookings were strong.")
    assert normalized == "Q1 2026"


def test_find_metric_keyword_revenue_synonym():
    keyword, metric_type = norm.find_metric_keyword("Our ARR grew 3x this year.")
    assert metric_type == "revenue"


def test_find_metric_keyword_market_size_synonym():
    keyword, metric_type = norm.find_metric_keyword("The TAM for this segment is large.")
    assert metric_type == "market_size"


def test_find_metric_keyword_no_match():
    keyword, metric_type = norm.find_metric_keyword("The office relocated to a new building.")
    assert keyword is None
    assert metric_type is None


def test_two_values_paired_with_nearest_period():
    text = "Revenue grew from ₹2.5 Cr in FY24 to ₹4.2 Cr in FY25."
    values = norm.find_all_values(text)
    periods = norm.find_all_periods(text)
    assert len(values) == 2
    assert len(periods) == 2

    p0 = norm.nearest_period(values[0]["span"], periods)
    p1 = norm.nearest_period(values[1]["span"], periods)
    assert p0["period_normalized"] == "FY2024"
    assert p1["period_normalized"] == "FY2025"
