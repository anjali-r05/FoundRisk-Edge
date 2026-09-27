from app.services import claim_extractor as extractor


def test_extract_two_claims_from_one_sentence():
    sentence = "Revenue grew from ₹2.5 Cr in FY24 to ₹4.2 Cr in FY25."
    candidates = extractor.extract_from_text_segment(sentence)
    assert len(candidates) == 2
    assert all(c["metric_type"] == "revenue" for c in candidates)
    periods = {c["period_normalized"] for c in candidates}
    assert periods == {"FY2024", "FY2025"}


def test_no_keyword_produces_no_claim():
    candidates = extractor.extract_from_text_segment("The weather in Bangalore was pleasant.")
    assert candidates == []


def test_keyword_without_number_produces_no_claim():
    candidates = extractor.extract_from_text_segment("Our revenue is strong this quarter.")
    assert candidates == []


def test_customer_count_extraction():
    candidates = extractor.extract_from_text_segment("We ended FY25 with 10000 paying customers.")
    assert len(candidates) == 1
    assert candidates[0]["metric_type"] == "customer_count"
    assert candidates[0]["normalized_value"] == 10000


def test_customer_count_before_keyword_is_extracted_with_nearby_period():
    candidates = extractor.extract_from_text_segment("We ended FY25 with 10000 paying customers.")
    assert len(candidates) == 1
    assert candidates[0]["metric_type"] == "customer_count"
    assert candidates[0]["normalized_value"] == 10000
    assert candidates[0]["period_normalized"] == "FY2025"


def test_customer_count_does_not_borrow_previous_revenue_value():
    candidates = extractor.extract_from_text_segment("Revenue reached ₹8 Cr while customer base grew.")
    assert len(candidates) == 1
    assert candidates[0]["metric_type"] == "revenue"


def test_market_size_extraction():
    candidates = extractor.extract_from_text_segment("The TAM is estimated at $1.2 billion.")
    assert len(candidates) == 1
    assert candidates[0]["metric_type"] == "market_size"
    assert candidates[0]["normalized_value"] == 1.2e9


def test_confidence_high_when_all_signals_present():
    candidates = extractor.extract_from_text_segment("Revenue reached ₹4.2 Cr in FY25.")
    assert candidates[0]["confidence_label"] == "High"
    assert candidates[0]["signals"] == {"keyword": True, "number": True, "unit": True, "period": True}


def test_confidence_lower_without_period():
    candidates = extractor.extract_from_text_segment("Revenue reached ₹4.2 Cr.")
    assert candidates[0]["signals"]["period"] is False
    assert candidates[0]["confidence_label"] in ("Medium", "High")
    assert candidates[0]["confidence_score"] < 1.0


def test_extract_from_pdf_page_attaches_page_number():
    candidates = extractor.extract_from_pdf_page("Revenue reached ₹4.2 Cr in FY25.", page_number=7)
    assert len(candidates) == 1
    assert candidates[0]["source_page"] == 7
    assert candidates[0]["provenance_confidence"] == "high"


def test_extract_from_csv_row_wide_format_with_column_period():
    row = {"Revenue FY24": "₹2.5 Cr", "Revenue FY25": "₹8 Cr", "Customers FY24": "6500"}
    candidates = extractor.extract_from_csv_row(row, row_number=2)
    assert len(candidates) == 3
    by_column = {c["source_column"]: c for c in candidates}
    assert by_column["Revenue FY24"]["period_normalized"] == "FY2024"
    assert by_column["Revenue FY25"]["period_normalized"] == "FY2025"
    assert by_column["Revenue FY24"]["source_row"] == 2


def test_extract_from_xlsx_sheet_uses_real_cell_coordinate():
    rows = [{"Revenue FY25": {"value": "₹8 Cr", "cell": "B5"}}]
    candidates = extractor.extract_from_xlsx_sheet("Financials", rows)
    assert len(candidates) == 1
    assert candidates[0]["source_sheet"] == "Financials"
    assert candidates[0]["source_cell"] == "B5"  # real openpyxl coordinate, not reconstructed
    assert candidates[0]["provenance_confidence"] == "high"


def test_extract_from_xlsx_sheet_low_provenance_without_cell_coordinate():
    rows = [{"Revenue FY25": {"value": "₹8 Cr", "cell": None}}]
    candidates = extractor.extract_from_xlsx_sheet("Financials", rows)
    assert candidates[0]["provenance_confidence"] == "low"


def test_test_pdf_extracts_six_period_linked_metric_observations():
    import fitz
    from pathlib import Path
    pdf_path = Path(__file__).resolve().parents[1] / "testing" / "FoundRisk_Test_Due_Diligence.pdf"
    with fitz.open(pdf_path) as doc:
        candidates = []
        for page_number, page in enumerate(doc, start=1):
            candidates.extend(extractor.extract_from_pdf_page(page.get_text(), page_number))
    actual = {(c["metric_type"], c["normalized_value"], c["period_normalized"]) for c in candidates}
    expected = {
        ("revenue", 4.5e7, "FY2025"), ("revenue", 8.2e7, "FY2026"),
        ("customer_count", 180.0, "FY2025"), ("customer_count", 340.0, "FY2026"),
        ("market_size", 1.2e10, "FY2025"), ("market_size", 1.5e10, "FY2026"),
    }
    assert actual == expected
    assert len(candidates) == 6
