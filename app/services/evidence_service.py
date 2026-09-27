"""
FoundRisk Edge — evidence assembly.

Takes the claim-candidate dicts produced by claim_extractor/document_parser
and turns them into persisted Claim + Metric + Evidence rows. This is the
only place that writes extraction output to the database, so the extractor
and parser stay pure/testable without a DB, and there's one place to change
if the persistence shape changes later.
"""
from app.models import db, Claim, Metric, Evidence
from app.services import provenance


def persist_candidates(document, candidates: list):
    """
    document: a persisted Document row (has .id, .project_id, .filename)
    candidates: list of claim-candidate dicts from claim_extractor

    Returns dict of counts: {claims, metrics, evidence}
    """
    counts = {"claims": 0, "metrics": 0, "evidence": 0}

    for candidate in candidates:
        provenance_confidence = provenance.evaluate(candidate)

        claim = Claim(
            document_id=document.id,
            raw_text=candidate["raw_text"],
            metric_type=candidate["metric_type"],
            matched_keyword=candidate["matched_keyword"],
            signal_keyword=candidate["signals"]["keyword"],
            signal_number=candidate["signals"]["number"],
            signal_unit=candidate["signals"]["unit"],
            signal_period=candidate["signals"]["period"],
            confidence_score=candidate["confidence_score"],
            confidence_label=candidate["confidence_label"],
            source_page=candidate.get("source_page"),
            source_sheet=candidate.get("source_sheet"),
            source_cell=candidate.get("source_cell"),
            source_row=candidate.get("source_row"),
            source_column=candidate.get("source_column"),
            provenance_confidence=provenance_confidence,
        )
        db.session.add(claim)
        db.session.flush()  # assigns claim.id without a full commit
        counts["claims"] += 1

        metric = Metric(
            claim_id=claim.id,
            metric_type=candidate["metric_type"],
            original_value=candidate["original_value"],
            original_unit=candidate.get("original_unit"),
            normalized_value=candidate["normalized_value"],
            currency=candidate.get("currency"),
            period_raw=candidate.get("period_raw"),
            period_normalized=candidate.get("period_normalized"),
        )
        db.session.add(metric)
        db.session.flush()
        counts["metrics"] += 1

        source_location = provenance.build_source_location(document.filename, candidate)
        excerpt = candidate["raw_text"]
        if len(excerpt) > 280:
            excerpt = excerpt[:277] + "..."

        evidence = Evidence(
            project_id=document.project_id,
            document_id=document.id,
            claim_id=claim.id,
            metric_id=metric.id,
            evidence_text=excerpt,
            source_location=source_location,
            confidence_label=candidate["confidence_label"],
        )
        db.session.add(evidence)
        counts["evidence"] += 1

    db.session.commit()
    return counts
