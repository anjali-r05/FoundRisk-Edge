from app.models import db, Project, Document, Claim, Metric
from app.services.contradiction_engine import detect_contradictions


def _observation(project_id, filename, value, period="FY2025", metric_type="revenue", currency="INR"):
    doc = Document(project_id=project_id, filename=filename, stored_path=f"/tmp/{filename}", file_type="pdf", status="ready")
    db.session.add(doc)
    db.session.flush()
    claim = Claim(document_id=doc.id, raw_text=f"{metric_type}: {value} in {period}", metric_type=metric_type,
                  confidence_score=0.9, confidence_label="High", source_page=1)
    db.session.add(claim)
    db.session.flush()
    metric = Metric(claim_id=claim.id, metric_type=metric_type, original_value=str(value), original_unit="Cr" if currency else None,
                    normalized_value=float(value) * 10_000_000 if metric_type != "customer_count" else float(value),
                    currency=currency, period_raw=period, period_normalized=period)
    db.session.add(metric)
    db.session.flush()
    return claim


def test_flags_same_metric_period_currency_across_documents(app, project):
    _observation(project.id, "pitch.pdf", 4.5)
    _observation(project.id, "financials.pdf", 8.2)
    result = detect_contradictions(Claim.query.join(Document).filter(Document.project_id == project.id).all())
    assert result["summary"]["finding_count"] == 1
    finding = result["findings"][0]
    assert finding["severity"] == "High"
    assert finding["metric_type"] == "revenue"
    assert len(finding["observations"]) == 2
    assert finding["observations"][0]["source_location"]


def test_does_not_compare_different_periods(app, project):
    _observation(project.id, "fy25.pdf", 4.5, period="FY2025")
    _observation(project.id, "fy26.pdf", 8.2, period="FY2026")
    result = detect_contradictions(Claim.query.join(Document).filter(Document.project_id == project.id).all())
    assert result["summary"]["finding_count"] == 0
    assert result["summary"]["compared_pairs"] == 0


def test_does_not_compare_different_currencies(app, project):
    _observation(project.id, "inr.pdf", 4.5, currency="INR")
    _observation(project.id, "usd.pdf", 4.5, currency="USD")
    result = detect_contradictions(Claim.query.join(Document).filter(Document.project_id == project.id).all())
    assert result["summary"]["finding_count"] == 0


def test_missing_period_is_excluded(app, project):
    _observation(project.id, "one.pdf", 4.5, period=None)
    _observation(project.id, "two.pdf", 8.2, period=None)
    # Explicitly clear canonical periods to model an unconfirmed period.
    for metric in Metric.query.all():
        metric.period_normalized = None
    db.session.commit()
    result = detect_contradictions(Claim.query.join(Document).filter(Document.project_id == project.id).all())
    assert result["summary"]["finding_count"] == 0
    assert result["summary"]["excluded_missing_period"] == 2


def test_api_returns_project_contradiction_summary(client, project):
    _observation(project.id, "one.pdf", 4.5)
    _observation(project.id, "two.pdf", 8.2)
    db.session.commit()
    response = client.get(f"/api/analysis/contradictions?project_id={project.id}")
    assert response.status_code == 200
    body = response.get_json()
    assert body["summary"]["finding_count"] == 1
    assert body["findings"][0]["observations"][0]["document_name"] in {"one.pdf", "two.pdf"}
