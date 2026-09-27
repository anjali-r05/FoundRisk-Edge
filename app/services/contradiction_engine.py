"""Deterministic, evidence-first contradiction detection for normalized metrics.

Only compares observations with the same metric family, canonical period and
currency. Observations without a canonical period are deliberately excluded.
This produces review flags, not a fraud verdict or an investment-risk score.
"""
from collections import defaultdict
from itertools import combinations

METRIC_LABELS = {
    "revenue": "Revenue",
    "customer_count": "Customer Count",
    "market_size": "Market Size",
}


def _severity(percent_difference: float):
    if percent_difference < 5:
        return None
    if percent_difference <= 15:
        return "Low"
    if percent_difference <= 35:
        return "Medium"
    return "High"


def _source_observation(claim):
    metric = claim.metric
    if metric is None:
        return None
    return {
        "claim_id": claim.id,
        "document_id": claim.document_id,
        "document_name": claim.document.filename,
        "metric_type": metric.metric_type,
        "metric_label": METRIC_LABELS.get(metric.metric_type, metric.metric_type),
        "original_value": metric.original_value,
        "original_unit": metric.original_unit,
        "normalized_value": float(metric.normalized_value),
        "currency": metric.currency,
        "period": metric.period_raw,
        "period_normalized": metric.period_normalized,
        "source_location": claim.source_location(),
        "confidence_label": claim.confidence_label,
        "evidence_text": claim.raw_text,
    }


def detect_contradictions(claims, ready_document_count=None):
    """Return pairwise discrepancy flags plus a live observation ledger.

    Comparisons are deliberately restricted to different documents reporting the
    same metric, canonical period, and currency. Every extracted observation is
    still returned in ``observation_groups`` even when no comparison is possible.
    """
    claims = list(claims)
    groups = defaultdict(list)
    ledger_groups = defaultdict(list)
    missing_period = 0
    eligible = 0
    document_ids = set()

    for claim in claims:
        document_ids.add(claim.document_id)
        metric = getattr(claim, "metric", None)
        if metric is None:
            continue
        period_key = metric.period_normalized or "UNCONFIRMED"
        currency_key = metric.currency or "NONE"
        ledger_groups[(metric.metric_type, period_key, currency_key)].append(claim)
        if not metric.period_normalized:
            missing_period += 1
            continue
        key = (metric.metric_type, metric.period_normalized, currency_key)
        groups[key].append(claim)
        eligible += 1

    findings = []
    compared_pairs = 0
    observation_groups = []

    # A source-visible ledger for all observations, including single-document
    # projects. This is what keeps the page informative before a second file is added.
    for (metric_type, period_key, currency_key), observations in ledger_groups.items():
        observations = sorted(observations, key=lambda c: (c.document.filename.lower(), c.id or 0))
        distinct_docs = {c.document_id for c in observations}
        comparable = period_key != "UNCONFIRMED" and len(distinct_docs) >= 2
        group_findings = []
        if comparable:
            for left, right in combinations(observations, 2):
                if left.document_id == right.document_id:
                    continue
                a = float(left.metric.normalized_value)
                b = float(right.metric.normalized_value)
                denominator = max(abs(a), abs(b))
                pct = (abs(a - b) / denominator * 100.0) if denominator else 0.0
                severity = _severity(pct)
                if severity:
                    group_findings.append(severity)
        if period_key == "UNCONFIRMED":
            status = "period_unconfirmed"
        elif len(distinct_docs) < 2:
            status = "single_source"
        elif group_findings:
            status = "discrepancy"
        else:
            status = "within_threshold"

        observation_groups.append({
            "metric_type": metric_type,
            "metric_label": METRIC_LABELS.get(metric_type, metric_type),
            "period": "Period not confirmed" if period_key == "UNCONFIRMED" else period_key,
            "period_normalized": None if period_key == "UNCONFIRMED" else period_key,
            "currency": None if currency_key == "NONE" else currency_key,
            "source_count": len(distinct_docs),
            "observation_count": len(observations),
            "status": status,
            "observations": [_source_observation(c) for c in observations],
        })

    for (metric_type, period, currency), observations in groups.items():
        for left, right in combinations(observations, 2):
            if left.document_id == right.document_id:
                continue
            a = float(left.metric.normalized_value)
            b = float(right.metric.normalized_value)
            if a == 0 and b == 0:
                continue
            denominator = max(abs(a), abs(b))
            difference = abs(a - b)
            pct = (difference / denominator * 100.0) if denominator else 0.0
            severity = _severity(pct)
            compared_pairs += 1
            if severity is None:
                continue
            left_data = _source_observation(left)
            right_data = _source_observation(right)
            findings.append({
                "id": f"{left.id}:{right.id}",
                "metric_type": metric_type,
                "metric_label": METRIC_LABELS.get(metric_type, metric_type),
                "period": period,
                "currency": None if currency == "NONE" else currency,
                "severity": severity,
                "difference": round(difference, 4),
                "percent_difference": round(pct, 2),
                "comparison_basis": "same metric + same normalized period + same currency across different documents",
                "explanation": (
                    f"The two source documents report different {METRIC_LABELS.get(metric_type, metric_type).lower()} "
                    f"values for {period}. The absolute difference is {pct:.1f}% of the larger value. "
                    "This is a discrepancy to review, not proof that either source is wrong."
                ),
                "observations": [left_data, right_data],
            })

    severity_rank = {"High": 0, "Medium": 1, "Low": 2}
    findings.sort(key=lambda item: (severity_rank[item["severity"]], -item["percent_difference"], item["metric_label"]))
    observation_groups.sort(key=lambda item: (item["metric_label"], item["period"], item["currency"] or ""))

    if ready_document_count is None:
        ready_document_count = len(document_ids)
    if compared_pairs:
        no_comparable_reason = None
    elif ready_document_count < 2:
        no_comparable_reason = "Upload and process a second source document that reports the same metric, period, and currency to enable cross-document comparison."
    elif missing_period:
        no_comparable_reason = "No shared, confirmed reporting period was available for a cross-document pair. Observations without a canonical period are shown in the ledger but are not compared."
    else:
        no_comparable_reason = "No cross-document pair shared the same metric, normalized reporting period, and currency. Different currencies are never converted automatically."

    return {
        "findings": findings,
        "observation_groups": observation_groups,
        "summary": {
            "finding_count": len(findings),
            "high": sum(f["severity"] == "High" for f in findings),
            "medium": sum(f["severity"] == "Medium" for f in findings),
            "low": sum(f["severity"] == "Low" for f in findings),
            "total_observations": sum(len(group) for group in ledger_groups.values()),
            "ready_document_count": ready_document_count,
            "eligible_observations": eligible,
            "compared_pairs": compared_pairs,
            "comparable_groups": sum(1 for group in observation_groups if group["source_count"] >= 2 and group["period_normalized"]),
            "excluded_missing_period": missing_period,
            "no_comparable_reason": no_comparable_reason,
            "comparison_rule": "Only different documents with the same metric, same normalized period, and same currency are compared. No currency conversion is performed. Values remain visible in the observation ledger even when a comparison is not possible.",
        },
    }

