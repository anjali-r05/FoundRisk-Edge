from flask import Blueprint, jsonify, request, abort
from sqlalchemy import or_
from app.models import db, Project, Document, Claim, Metric, Evidence, RiskFinding
from app.services.risk_engine import refresh_findings

intelligence_bp=Blueprint("intelligence",__name__,url_prefix="/api/intelligence")

@intelligence_bp.route("/risks",methods=["GET","POST"])
def risks():
    pid=request.args.get("project_id",type=int) or (request.get_json(silent=True) or {}).get("project_id")
    if not pid: abort(400,description="project_id is required.")
    if not db.session.get(Project,pid): abort(404,description="Project not found.")
    findings=refresh_findings(pid) if request.method=="POST" or request.args.get("refresh")=="1" else RiskFinding.query.filter_by(project_id=pid).order_by(RiskFinding.updated_at.desc()).all()
    if request.method=="GET" and not findings: findings=refresh_findings(pid)
    status=request.args.get("status")
    severity=request.args.get("severity")
    items=[f for f in findings if (not status or f.status==status) and (not severity or f.severity.lower()==severity.lower())]
    counts={s:sum(1 for f in findings if f.status==s) for s in ("open","reviewing","resolved")}
    return jsonify({"findings":[f.to_dict() for f in items],"counts":counts,"total":len(items)}),200

@intelligence_bp.route("/risks/<int:finding_id>",methods=["PATCH"])
def update_risk(finding_id):
    f=db.session.get(RiskFinding,finding_id)
    if not f: abort(404,description="Finding not found.")
    status=(request.get_json(silent=True) or {}).get("status")
    if status not in ("open","reviewing","resolved"): abort(422,description="status must be open, reviewing, or resolved.")
    f.status=status; db.session.commit()
    return jsonify({"finding":f.to_dict()}),200

@intelligence_bp.route("/copilot", methods=["POST"])
def copilot():
    """Local, deterministic evidence retrieval with clear project-state feedback."""
    import re
    import json

    data = request.get_json(silent=True) or {}
    pid = data.get("project_id")
    question = (data.get("question") or "").strip()
    if not pid:
        abort(400, description="project_id is required.")
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        abort(400, description="project_id must be a number.")
    if not db.session.get(Project, pid):
        abort(404, description="Project not found.")
    if not question:
        abort(422, description="Enter a question.")
    if len(question) > 1200:
        abort(422, description="Question must be 1,200 characters or fewer.")

    docs = Document.query.filter_by(project_id=pid).order_by(Document.created_at.desc()).all()
    ready_docs = [d for d in docs if d.status == "ready"]
    claims = (Claim.query.join(Document)
              .filter(Document.project_id == pid, Document.status == "ready")
              .order_by(Claim.id.asc()).all())
    findings = RiskFinding.query.filter_by(project_id=pid).order_by(RiskFinding.updated_at.desc()).all()

    raw_tokens = set(re.findall(r"[a-z0-9]+", question.lower()))
    stop = {"what","which","when","where","does","this","that","with","from","about","have","has","are","was","were","the","and","for","can","could","show","tell","give","please","based","evidence","document","documents","is","in","of","to","a","an","my","our","startup","company","project","me","all","find","list","explain","summarize"}
    metric_aliases = {
        "revenue": {"revenue","sales","turnover","arr","mrr","income"},
        "customer_count": {"customer","customers","client","clients","users","subscriber","subscribers","customer_count"},
        "market_size": {"market","market_size","tam","sam","som","addressable","marketplace"},
    }
    normalized_question = question.lower().replace("_", " ")
    wanted_metrics = {metric for metric, aliases in metric_aliases.items() if any(alias in raw_tokens or alias.replace("_", " ") in normalized_question for alias in aliases)}
    risk_intent = any(t in raw_tokens for t in {"risk","risks","finding","findings","issue","issues","concern","concerns","gap","gaps","missing","discrepancy","contradiction","inconsistency","diligence","health","summary","overview","status"})
    broad_intent = risk_intent or any(t in raw_tokens for t in {"summary","overview","everything","all","overall","project","startup"}) or not wanted_metrics
    tokens = {t for t in raw_tokens if t not in stop and len(t) > 1}
    for metric in wanted_metrics:
        tokens.update(metric.replace("_", " ").split())

    scored = []
    for c in claims:
        metric_type = c.metric_type or (c.metric.metric_type if c.metric else "")
        if wanted_metrics and metric_type not in wanted_metrics:
            continue
        haystack = f"{c.raw_text or ''} {metric_type} {c.document.filename} {c.matched_keyword or ''}".lower().replace("_", " ")
        score = sum(2 if t in haystack.split() else 0 for t in tokens)
        if c.metric and c.metric.period_raw and c.metric.period_raw.lower() in normalized_question:
            score += 5
        if c.document.filename.lower() in normalized_question:
            score += 5
        if wanted_metrics and metric_type in wanted_metrics:
            score += 4
        if score > 0 or broad_intent:
            scored.append((score, c))
    scored.sort(key=lambda item: (-item[0], item[1].id))

    selected = []
    seen_ids = set()
    for _, claim in scored:
        if claim.id not in seen_ids:
            selected.append(claim)
            seen_ids.add(claim.id)
        if len(selected) >= 10:
            break

    relevant_findings = []
    if risk_intent:
        for finding in findings:
            if finding.status == "resolved" and not any(t in raw_tokens for t in {"resolved","closed","all"}):
                continue
            ftext = f"{finding.title} {finding.summary} {finding.category} {finding.impact} {finding.recommendation}".lower().replace("_", " ")
            if broad_intent or any(t in ftext for t in tokens) or "risk" in raw_tokens or "risks" in raw_tokens:
                relevant_findings.append(finding)
            if len(relevant_findings) >= 10:
                break
        for finding in relevant_findings:
            try:
                refs = json.loads(finding.evidence_json or "[]")
            except (TypeError, ValueError):
                refs = []
            for ref in refs:
                cid = ref.get("claim_id")
                claim = next((item for item in claims if item.id == cid), None)
                if claim and claim.id not in seen_ids:
                    selected.append(claim)
                    seen_ids.add(claim.id)
                    if len(selected) >= 10:
                        break

    evidence = [{
        "citation": f"[E{c.id}]", "claim_id": c.id, "metric": c.metric_type,
        "text": c.raw_text, "source": c.source_location(), "document": c.document.filename,
        "confidence": c.confidence_label,
        "value": c.metric.normalized_value if c.metric else None,
        "original_value": c.metric.original_value if c.metric else None,
        "unit": c.metric.original_unit if c.metric else None,
        "period": c.metric.period_raw if c.metric else None,
        "currency": c.metric.currency if c.metric else None,
    } for c in selected]

    if not docs:
        answer = "This project has no uploaded documents yet. Upload a text-based PDF, CSV, or XLSX from the Documents page, then wait until its status is Processed."
        mode = "empty_project"
    elif not ready_docs:
        state_lines = [f"• {d.filename}: {d.status}" + (f" — {d.status_detail}" if d.status_detail else "") for d in docs[:8]]
        answer = ("I can't answer from source evidence because no document is successfully processed yet.\n\n"
                  "Current document status:\n" + "\n".join(state_lines) +
                  "\n\nOpen Documents and retry any failed/queued file. Scanned PDFs require local Tesseract OCR; check the document status for setup guidance if OCR is unavailable.")
        mode = "documents_not_processed"
    elif not claims:
        answer = "The documents are marked processed, but no supported Revenue, Customer Count, or Market Size claims were extracted. Check whether the file contains selectable text and these metric keywords. I won't invent figures."
        mode = "no_extracted_claims"
    elif not evidence and not relevant_findings:
        answer = "I couldn't find a matching source statement for that wording. Try a metric or synonym such as revenue/sales, customers/users, market size/TAM, a reporting period (FY2025), or a document filename."
        mode = "no_match"
    else:
        sections = []
        if relevant_findings:
            sections.append("PROJECT REVIEW FINDINGS\n" + "\n\n".join(
                f"• {f.title} — {f.severity} priority · {f.status}\n{f.summary}\nPotential impact: {f.impact}\nNext step: {f.recommendation}"
                for f in relevant_findings[:8]))
        if evidence:
            lines = []
            for e in evidence[:8]:
                value = ""
                if e["original_value"] is not None:
                    value = f" | reported value: {e['original_value']} {e['unit'] or ''}".rstrip()
                if e["period"]:
                    value += f" | period: {e['period']}"
                lines.append(f"{e['citation']} {e['text']}{value}\nSource: {e['source']} · {e['document']} · extraction confidence: {e['confidence']}")
            sections.append("MATCHED SOURCE EVIDENCE\n" + "\n\n".join(lines))
        answer = "\n\n".join(sections) + "\n\nThese are extracted source statements and rule-based review signals, not independent verification or investment advice."
        mode = "evidence_and_findings" if relevant_findings else "evidence_retrieval"

    return jsonify({"answer": answer, "mode": mode, "citations": evidence,
                    "matched_count": len(evidence), "findings": [f.to_dict() for f in relevant_findings[:8]],
                    "project_status": {"documents": len(docs), "processed": len(ready_docs), "claims": len(claims)},
                    "disclaimer": "Local evidence retrieval only; no external AI service is called. Verify cited source material."}), 200

@intelligence_bp.route("/copilot/suggestions",methods=["GET"])
def suggestions():
    pid=request.args.get("project_id",type=int)
    if not pid or not db.session.get(Project,pid): abort(400,description="Valid project_id is required.")
    return jsonify({"suggestions":["What revenue figures were extracted, and for which periods?","What customer-count evidence is available?","What market-size claims were found?","Which claims have low extraction confidence?","What evidence is missing for a basic diligence review?"]}),200
