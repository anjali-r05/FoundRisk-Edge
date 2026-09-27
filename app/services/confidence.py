"""
FoundRisk Edge — extraction confidence scoring.

Purely rule-based, four binary signals. This is deliberately NOT called
"AI confidence" anywhere — Phase 1 has no model in the loop. The score exists
so the UI can show *why* a claim was trusted more or less, not just a number.
"""

# Signal weights — sum to 1.0. Keyword + number are load-bearing (a claim with
# neither shouldn't exist at all); unit and period each add supporting confidence.
_WEIGHTS = {
    "keyword": 0.35,
    "number": 0.35,
    "unit": 0.15,
    "period": 0.15,
}


def score_signals(signals: dict) -> float:
    """signals: {'keyword': bool, 'number': bool, 'unit': bool, 'period': bool} -> float 0.0-1.0"""
    return round(sum(_WEIGHTS[k] for k, present in signals.items() if present), 4)


def label_for_score(score: float) -> str:
    if score >= 0.75:
        return "High"
    if score >= 0.45:
        return "Medium"
    return "Low"


def score_and_label(signals: dict):
    score = score_signals(signals)
    return score, label_for_score(score)
