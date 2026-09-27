"""Transparent rule-based findings. Every finding is tied to actual extracted evidence."""
import json
from app.models import db, Project, Document, Claim, Metric, Evidence, RiskFinding
from app.services.contradiction_engine import detect_contradictions

METRICS = ("revenue", "customer_count", "market_size")

def _evidence(claims):
    out=[]
    for c in claims:
        out.append({"claim_id":c.id,"document_id":c.document_id,"document":c.document.filename,
                    "text":c.raw_text,"source":c.source_location(),"metric":c.metric_type,
                    "confidence":c.confidence_label})
    return out

def refresh_findings(project_id):
    project=db.session.get(Project, project_id)
    if not project: return []
    docs=Document.query.filter_by(project_id=project_id).all()
    ready=[d for d in docs if d.status=="ready"]
    claims=Claim.query.join(Document).filter(Document.project_id==project_id, Document.status=="ready").all()
    candidates=[]
    # A genuinely empty workspace must still show an actionable diligence item,
    # rather than a blank Risk Findings screen.
    if not docs:
        candidates.append({
            "key": "workspace:no-source-documents",
            "title": "Due diligence has not started · No source documents",
            "category": "Evidence gap",
            "severity": "Medium",
            "summary": "No source documents have been uploaded to this workspace, so evidence-based risk checks cannot run yet.",
            "impact": "Revenue, customer-count and market-size claims cannot be assessed from source evidence.",
            "recommendation": "Upload source-backed PDF, CSV or XLSX files in Documents, then process them to generate evidence-linked findings.",
            "confidence": "High", "evidence": []
        })
    # Make ingestion state visible instead of showing an empty queue while files
    # are queued, failed, or contain no readable text.
    for doc in docs:
        if doc.status != "ready":
            status_label = (doc.status or "unknown").replace("_", " ").title()
            candidates.append({
                "key": f"document-state:{doc.id}:{doc.status}",
                "title": f"Source document needs attention · {doc.filename}",
                "category": "Document processing",
                "severity": "High" if doc.status == "failed" else "Medium",
                "summary": f"This source is currently marked '{status_label}' and is not included in evidence-based analysis.",
                "impact": "Risk checks and Copilot answers may be incomplete until this source is successfully processed.",
                "recommendation": "Open Documents, inspect the processing status, and retry processing or upload a text-based PDF/CSV/XLSX file.",
                "confidence": "High", "evidence": []
            })
    # Coverage gaps are clearly labeled as diligence gaps, not claims of fraud.
    for metric in METRICS:
        subset=[c for c in claims if c.metric_type==metric]
        label=metric.replace("_"," ").title()
        if ready and not subset:
            candidates.append({"key":f"coverage:{metric}","title":f"{label} evidence missing",
                "category":"Evidence gap","severity":"Medium","summary":f"No extractable {label.lower()} claim was found in the processed documents.",
                "impact":f"The project’s {label.lower()} cannot be independently assessed from the current evidence set.",
                "recommendation":f"Request a dated, source-backed {label.lower()} disclosure and add it to the workspace.","confidence":"High","evidence":[]})
        elif subset and len({c.document_id for c in subset}) == 1:
            # A single source is not treated as a false claim, but the lack of
            # corroboration is a concrete diligence gap worth reviewing.
            source_name = subset[0].document.filename
            candidates.append({"key":f"single-source:{metric}","title":f"{label} claims rely on a single source",
                "category":"Evidence coverage","severity":"Low",
                "summary":f"The workspace contains {len(subset)} extracted {label.lower()} observation(s), all from one document: {source_name}.",
                "impact":"These observations have not been corroborated by a second independent source in this workspace.",
                "recommendation":f"Request a second source for {label.lower()} (for example, a ledger, audited statement, or dated operating report) and compare the reporting period and definition.",
                "confidence":"High","evidence":_evidence(subset[:8])})
    for c in claims:
        if c.confidence_label=="Low":
            candidates.append({"key":f"low-confidence:{c.id}","title":"Low-confidence extracted claim",
                "category":"Data quality","severity":"Low","summary":"A metric-like statement was extracted with limited matching signals.",
                "impact":"This value may be misclassified or incomplete and should not be relied on without review.",
                "recommendation":"Open the cited source, verify the wording and unit, then correct or dismiss the claim.",
                "confidence":"High","evidence":_evidence([c])})
    contradiction_result=detect_contradictions(claims, ready_document_count=len(ready))
    for item in contradiction_result.get("findings", []):
        severity=(item.get("severity") or "medium").capitalize()
        if severity not in ("High","Medium","Low"): severity="Medium"
        ev=[]
        for raw in item.get("observations", []):
            cid=raw.get("claim_id")
            match=next((c for c in claims if c.id==cid),None)
            if match: ev.extend(_evidence([match]))
        key=f"contradiction:{item.get('key') or item.get('id') or item.get('title') or len(candidates)}"
        candidates.append({"key":key,"title":f"{item.get('metric_label', 'Metric')} discrepancy · {item.get('period', 'period not stated')}",
            "category":"Cross-document inconsistency","severity":severity,
            "summary":item.get("explanation") or "The same metric appears with values that require reconciliation.",
            "impact":"Conflicting figures can change the interpretation of operating performance or market assumptions.",
            "recommendation":"Confirm the reporting period, definition, units and source of truth; document the reconciliation.",
            "confidence":"Medium","evidence":ev})
    existing={f.finding_key:f for f in RiskFinding.query.filter_by(project_id=project_id).all()}
    active_keys={c["key"] for c in candidates}
    for c in candidates:
        f=existing.get(c["key"])
        if f:
            # Preserve a user's resolved/review state; update finding evidence and narrative.
            f.title=c["title"]; f.category=c["category"]; f.severity=c["severity"]
            f.summary=c["summary"]; f.impact=c["impact"]; f.recommendation=c["recommendation"]
            f.confidence=c["confidence"]; f.evidence_json=json.dumps(c["evidence"],ensure_ascii=False)
        else:
            db.session.add(RiskFinding(project_id=project_id,finding_key=c["key"],title=c["title"],category=c["category"],
                severity=c["severity"],summary=c["summary"],impact=c["impact"],recommendation=c["recommendation"],
                confidence=c["confidence"],evidence_json=json.dumps(c["evidence"],ensure_ascii=False)))
    # Mark stale open findings resolved only if their triggering source is no longer present.
    for key,f in existing.items():
        if key not in active_keys and f.status=="open": f.status="resolved"
    db.session.commit()
    return RiskFinding.query.filter_by(project_id=project_id).order_by(RiskFinding.updated_at.desc()).all()
