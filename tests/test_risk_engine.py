from app.models import db, Document, Claim, Metric
from app.services.risk_engine import refresh_findings


def test_single_source_metrics_create_traceable_review_findings(app, project):
    doc = Document(project_id=project.id, filename="financials.pdf", stored_path="/tmp/financials.pdf", file_type="pdf", status="ready")
    db.session.add(doc)
    db.session.flush()
    for metric_type, value in (("revenue", 45000000), ("customer_count", 180), ("market_size", 12000000000)):
        claim = Claim(document_id=doc.id, raw_text=f"{metric_type}: {value} FY2025", metric_type=metric_type, confidence_score=0.9, confidence_label="High", source_page=1)
        db.session.add(claim)
        db.session.flush()
        db.session.add(Metric(claim_id=claim.id, metric_type=metric_type, original_value=str(value), normalized_value=value, currency="INR", period_raw="FY2025", period_normalized="FY2025"))
    db.session.commit()

    findings = refresh_findings(project.id)
    single_source = [f for f in findings if f.finding_key.startswith("single-source:")]
    assert {f.finding_key for f in single_source} == {"single-source:revenue", "single-source:customer_count", "single-source:market_size"}
    assert all(f.severity == "Low" and f.evidence_json != "[]" for f in single_source)
