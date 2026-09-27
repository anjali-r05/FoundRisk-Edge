from app.services import provenance


def test_pdf_page_gives_high_confidence():
    candidate = {"source_page": 7}
    assert provenance.evaluate(candidate) == "high"


def test_xlsx_sheet_and_cell_gives_high_confidence():
    candidate = {"source_sheet": "Financials", "source_cell": "B14"}
    assert provenance.evaluate(candidate) == "high"


def test_xlsx_sheet_without_cell_is_low_confidence():
    candidate = {"source_sheet": "Financials", "source_cell": None}
    assert provenance.evaluate(candidate) == "low"


def test_csv_row_and_column_gives_high_confidence():
    candidate = {"source_row": 5, "source_column": "Revenue FY25"}
    assert provenance.evaluate(candidate) == "high"


def test_no_source_fields_is_low_confidence():
    assert provenance.evaluate({}) == "low"


def test_source_location_never_fabricates_missing_fields():
    location = provenance.build_source_location("doc.pdf", {})
    assert "unconfirmed" in location.lower()


def test_source_location_pdf_format():
    location = provenance.build_source_location("Investor_Pitch.pdf", {"source_page": 12})
    assert location == "Investor_Pitch.pdf, page 12"


def test_source_location_xlsx_format():
    location = provenance.build_source_location(
        "Financial_Model.xlsx", {"source_sheet": "Revenue", "source_cell": "B14"}
    )
    assert location == "Financial_Model.xlsx, sheet: Revenue, cell: B14"
