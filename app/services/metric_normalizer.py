"""
FoundRisk Edge — metric normalization.

Deterministic, rule-based only. No LLM, no ML model. Every function here is
pure and testable: given a piece of text, return the structured value(s) it
contains, or None if nothing reliable is found. Nothing here guesses silently —
ambiguous cases return None rather than a plausible-looking wrong answer.
"""
import re

# ---------------------------------------------------------------------------
# Canonical metric keyword dictionaries (exactly 3 families, per spec)
# ---------------------------------------------------------------------------

METRIC_KEYWORDS = {
    "revenue": [
        "revenue", "annual revenue", "arr", "mrr", "sales", "turnover",
    ],
    "customer_count": [
        "customer count", "number of customers", "customers", "paying customers", "active customers", "customer base",
        "users", "active users",
    ],
    "market_size": [
        "tam", "sam", "som",
        "total addressable market", "serviceable available market",
        "serviceable obtainable market", "market size",
    ],
}

# Longer phrases must be checked before shorter substrings that could
# false-positive-match inside them (e.g. "market size" contains no other
# keyword, but this ordering matters generally as the dictionary grows).
_SORTED_KEYWORDS = sorted(
    ((kw, mtype) for mtype, kws in METRIC_KEYWORDS.items() for kw in kws),
    key=lambda pair: len(pair[0]),
    reverse=True,
)


def find_metric_keyword(text: str):
    """Return (matched_keyword, metric_type) for the first/longest keyword found, or (None, None)."""
    lowered = text.lower()
    for keyword, metric_type in _SORTED_KEYWORDS:
        # word-boundary match so "users" doesn't match inside "browsers", etc.
        pattern = r"\b" + re.escape(keyword) + r"\b"
        if re.search(pattern, lowered):
            return keyword, metric_type
    return None, None


# ---------------------------------------------------------------------------
# Currency + magnitude unit parsing
# ---------------------------------------------------------------------------

_CURRENCY_SYMBOLS = {"₹": "INR", "i": "INR", "rs.": "INR", "rs": "INR", "inr": "INR", "$": "USD", "usd": "USD"}

# multiplier keywords, longest-first so "lakh" doesn't get shadowed by anything
_MAGNITUDE = [
    ("crore", 1e7), ("cr", 1e7),
    ("lakh", 1e5), ("lac", 1e5),
    ("billion", 1e9), ("bn", 1e9), ("b", 1e9),
    ("million", 1e6), ("mn", 1e6), ("m", 1e6),
    ("thousand", 1e3), ("k", 1e3),
]

# Matches: optional currency symbol/word, a number (with , . optionally), optional magnitude word.
# The leading (?<![A-Za-z0-9]) stops a match from starting mid-token — without
# it, "FY24" would let the engine match a bogus bare "4" (blocked from "24" by
# the letter "Y" before it, then retried starting at the "4" itself, which has
# only a digit before it). Requiring "not preceded by any letter or digit"
# closes both paths.
_VALUE_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?P<currency>₹|\$|rs\.?|inr|usd|I)?\s*"
    r"(?P<number>[0-9][0-9,]*\.?[0-9]*)\s*"
    r"(?P<magnitude>crore|cr|lakh|lac|billion|bn|million|mn|thousand|k|b|m)?",
    re.IGNORECASE,
)


def find_all_values(text: str, allow_bare: bool = False):
    """
    Find every plausible numeric value + unit + currency in `text`, each tagged
    with its character span so callers can pair values with nearby periods.

    By default a bare number with no currency symbol AND no magnitude word is
    skipped — that combination is too ambiguous (page numbers, list indices,
    etc.) to treat as a metric value. Pass allow_bare=True for metric types
    that are legitimately expressed as plain integers with no unit, like
    customer_count ("10000 paying customers") — the caller decides this based
    on which metric keyword already matched, not this function.
    """
    results = []
    for match in _VALUE_PATTERN.finditer(text):
        number_str = match.group("number")
        if not number_str:
            continue
        try:
            number = float(number_str.replace(",", ""))
        except ValueError:
            continue
        if number == 0:
            continue

        magnitude_word = match.group("magnitude")
        currency_word = match.group("currency")

        if not magnitude_word and not currency_word and not allow_bare:
            continue  # bare number, too ambiguous on its own without a metric context

        multiplier = 1.0
        original_unit = None
        if magnitude_word:
            for word, mult in _MAGNITUDE:
                if magnitude_word.lower() == word:
                    multiplier = mult
                    original_unit = magnitude_word
                    break

        currency = _CURRENCY_SYMBOLS.get(currency_word.lower()) if currency_word else None

        results.append({
            "original_value": number_str,
            "original_unit": original_unit,
            "normalized_value": number * multiplier,
            "currency": currency,
            "span": match.span(),
        })
    return results


def parse_value(text: str):
    """Convenience wrapper: first plausible value in `text`, or None."""
    values = find_all_values(text)
    return values[0] if values else None


# ---------------------------------------------------------------------------
# Period parsing
# ---------------------------------------------------------------------------

_FY_PATTERN = re.compile(r"\bFY\s?(\d{2,4})\b", re.IGNORECASE)
_QUARTER_PATTERN = re.compile(r"\bQ([1-4])\s?(\d{2,4})\b", re.IGNORECASE)
_YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")


def find_all_periods(text: str):
    """Find every period mention in `text`, each with its character span."""
    results = []
    for m in _QUARTER_PATTERN.finditer(text):
        quarter, year = m.group(1), m.group(2)
        year_norm = _normalize_year(year)
        results.append({
            "period_raw": m.group(0),
            "period_normalized": f"Q{quarter} {year_norm}" if year_norm else None,
            "span": m.span(),
        })
    for m in _FY_PATTERN.finditer(text):
        year = m.group(1)
        year_norm = _normalize_year(year)
        results.append({
            "period_raw": m.group(0),
            "period_normalized": f"FY{year_norm}" if year_norm else None,
            "span": m.span(),
        })
    # Bare 4-digit years, only if not already inside an FY/quarter match above
    covered = {r["span"] for r in results}
    for m in _YEAR_PATTERN.finditer(text):
        if any(m.start() >= s[0] and m.end() <= s[1] for s in covered):
            continue
        results.append({"period_raw": m.group(1), "period_normalized": m.group(1), "span": m.span()})
    results.sort(key=lambda r: r["span"][0])
    return results


def nearest_period(value_span, periods):
    """
    Pick the period mention that belongs to a value's span, or None.

    Prefers the nearest period that starts AFTER the value ("...₹4.2 Cr in
    FY25" -> the period following the value), since that's the dominant
    phrasing in financial prose. Falls back to the nearest period overall
    (by character distance) only if none follows — this avoids a plain
    midpoint-distance tie incorrectly re-using an earlier period for a later
    value in the same sentence (e.g. two value/period pairs equidistant from
    each other's neighbor).
    """
    if not periods:
        return None

    following = [p for p in periods if p["span"][0] >= value_span[1]]
    if following:
        return min(following, key=lambda p: p["span"][0] - value_span[1])

    v_mid = (value_span[0] + value_span[1]) / 2
    return min(periods, key=lambda p: abs((p["span"][0] + p["span"][1]) / 2 - v_mid))


def parse_period(text: str):
    """Convenience wrapper: first period mention in `text`, as (raw, normalized), or (None, None)."""
    periods = find_all_periods(text)
    if not periods:
        return None, None
    return periods[0]["period_raw"], periods[0]["period_normalized"]


def _normalize_year(year_str: str):
    if len(year_str) == 4:
        return year_str
    if len(year_str) == 2:
        # 2-digit FY year: assume 20xx for 00-79, 19xx for 80-99 (irrelevant range here, but explicit)
        num = int(year_str)
        return f"20{year_str}" if num <= 79 else f"19{year_str}"
    return None
