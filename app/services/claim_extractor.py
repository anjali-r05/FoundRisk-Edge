"""Deterministic Phase-1 metric extraction for FoundRisk Edge."""
import re
from app.services import metric_normalizer as norm
from app.services.confidence import score_and_label

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z₹$]|$)")


def split_sentences(text: str):
    text = re.sub(r"\s+", " ", (text or "").replace("\n", " ")).strip()
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()] if text else []


def _keyword_occurrences(text: str):
    lowered = text.lower()
    found = []
    for keyword, metric_type in norm._SORTED_KEYWORDS:
        for match in re.finditer(r"\b" + re.escape(keyword) + r"\b", lowered):
            found.append((match.start(), match.end(), keyword, metric_type))
    # Prefer longer keyword matches when spans overlap.
    found.sort(key=lambda x: (x[0], -(x[1] - x[0])))
    selected = []
    for item in found:
        if any(item[0] < old[1] and item[1] > old[0] for old in selected):
            continue
        selected.append(item)
    return sorted(selected, key=lambda x: x[0])


def _candidate(segment, keyword, metric_type):
    values = norm.find_all_values(segment, allow_bare=(metric_type == "customer_count"))
    periods = norm.find_all_periods(segment)
    out = []
    for value in values:
        period = norm.nearest_period(value["span"], periods)
        signals = {
            "keyword": True,
            "number": True,
            "unit": bool(value["original_unit"] or value["currency"]),
            "period": period is not None,
        }
        score, label = score_and_label(signals)
        out.append({
            "raw_text": segment.strip(), "metric_type": metric_type,
            "matched_keyword": keyword, "signals": signals,
            "confidence_score": score, "confidence_label": label,
            "original_value": value["original_value"], "original_unit": value["original_unit"],
            "normalized_value": value["normalized_value"], "currency": value["currency"],
            "period_raw": period["period_raw"] if period else None,
            "period_normalized": period["period_normalized"] if period else None,
        })
    return out


def extract_from_text_segment(segment: str):
    """Extract values only from the context belonging to each metric keyword.

    This prevents a sentence such as 'revenue ₹8 Cr while customer base reached 340'
    from assigning ₹8 Cr to the customer metric or 340 customers to revenue.
    """
    occurrences = _keyword_occurrences(segment)
    if not occurrences:
        return []
    candidates = []
    for index, (start, end, keyword, metric_type) in enumerate(occurrences):
        next_start = occurrences[index + 1][0] if index + 1 < len(occurrences) else len(segment)
        # Keep each metric window bounded by the next metric keyword. Customer
        # counts are also commonly written before the keyword (e.g. "10,000
        # paying customers"). Only pull in a preceding number when it is directly
        # adjacent to the customer keyword; this avoids borrowing a prior metric.
        window = segment[start:next_start].strip()
        if metric_type == "customer_count" and not norm.find_all_values(window, allow_bare=True):
            prefix = segment[:start]
            prior_values = norm.find_all_values(prefix, allow_bare=True)
            if prior_values:
                last_value = prior_values[-1]
                between = prefix[last_value["span"][1]:]
                if re.fullmatch(r"[\s,:;–—-]*", between):
                    window_start = last_value["span"][0]
                    nearby_periods = [
                        period for period in norm.find_all_periods(prefix)
                        if 0 <= last_value["span"][0] - period["span"][1] <= 32
                    ]
                    if nearby_periods:
                        window_start = nearby_periods[-1]["span"][0]
                    window = segment[window_start:next_start].strip()
        candidates.extend(_candidate(window, keyword, metric_type))
    return candidates


def _period_record(period):
    return {
        "period_raw": period.get("period_raw"),
        "period_normalized": period.get("period_normalized"),
    }


def _is_metric_heading(line):
    """Recognize short table labels, not arbitrary prose containing a keyword."""
    cleaned = re.sub(r"^\s*\d+[.)]\s*", "", line).strip()
    cleaned = re.sub(r"^[\s-]+|[\s:：-]+$", "", cleaned).strip().lower()
    labels = {
        "revenue": "revenue", "annual revenue": "revenue", "arr": "revenue", "mrr": "revenue",
        "customer count": "customer_count", "customers": "customer_count",
        "market size": "market_size", "tam": "market_size", "sam": "market_size", "som": "market_size",
    }
    if cleaned in labels:
        return cleaned, labels[cleaned]
    return None, None


def _table_candidates(page_text: str):
    """Read simple label/period/value tables while preserving column-period pairing.

    This handles text-extracted PDF tables where period headers precede metric rows
    and values appear on the following lines. Ambiguous rows are left to the
    ordinary sentence extractor instead of being assigned a guessed period.
    """
    lines = [re.sub(r"\s+", " ", line).strip() for line in (page_text or "").splitlines()]
    lines = [line for line in lines if line]
    candidates = []
    period_headers = []

    for idx, line in enumerate(lines):
        period_hits = norm.find_all_periods(line)
        if period_hits and len(line) < 40:
            for period in period_hits:
                if period.get("period_normalized") and period["period_normalized"] not in {p["period_normalized"] for p in period_headers}:
                    period_headers.append(period)
            period_headers = period_headers[-4:]

        label, metric_type = _is_metric_heading(line)
        if not metric_type:
            continue

        # Collect values until the next short metric heading or a new section.
        value_lines = []
        for nxt in lines[idx + 1:idx + 8]:
            next_label, next_type = _is_metric_heading(nxt)
            if next_type:
                break
            if re.match(r"^\d+[.)]\s+", nxt):
                break
            values = norm.find_all_values(nxt, allow_bare=(metric_type == "customer_count"))
            if values:
                value_lines.append((nxt, values))
            elif value_lines and len(value_lines) >= 2:
                break

        flat_values = [(line_text, value) for line_text, vals in value_lines for value in vals]
        periods = period_headers[-len(flat_values):] if len(period_headers) >= len(flat_values) else []
        period_alignment = len(periods) == len(flat_values) and len(flat_values) > 0

        for value_index, (line_text, value) in enumerate(flat_values):
            period = periods[value_index] if period_alignment else None
            signals = {
                "keyword": True,
                "number": True,
                "unit": bool(value.get("original_unit") or value.get("currency")),
                "period": bool(period),
            }
            score, label_conf = score_and_label(signals)
            period_data = _period_record(period) if period else {"period_raw": None, "period_normalized": None}
            candidates.append({
                "raw_text": f"{line} — {period_data['period_raw'] + ': ' if period_data['period_raw'] else ''}{line_text}",
                "metric_type": metric_type,
                "matched_keyword": label,
                "signals": signals,
                "confidence_score": score,
                "confidence_label": label_conf,
                "original_value": value["original_value"],
                "original_unit": value.get("original_unit"),
                "normalized_value": value["normalized_value"],
                "currency": value.get("currency"),
                "period_raw": period_data["period_raw"],
                "period_normalized": period_data["period_normalized"],
            })
    return candidates


def _deduplicate_page_candidates(candidates):
    """Avoid duplicate table/narrative mentions of the same metric observation.

    Prefer period-linked records over otherwise identical unperiodized mentions.
    Different values or reporting periods are never collapsed.
    """
    grouped = {}
    for candidate in candidates:
        key = (
            candidate.get("metric_type"),
            round(float(candidate.get("normalized_value") or 0), 6),
            candidate.get("currency"),
        )
        existing = grouped.get(key)
        if existing is None:
            grouped[key] = candidate
            continue
        current_period = candidate.get("period_normalized")
        existing_period = existing.get("period_normalized")
        if current_period and not existing_period:
            grouped[key] = candidate
        elif current_period and existing_period and current_period != existing_period:
            # Same value reported in two periods is meaningful; retain both.
            grouped[(key, current_period)] = candidate
        elif current_period and existing_period == current_period:
            # Keep the first source occurrence for a stable, non-duplicated ledger.
            pass
    return list(grouped.values())


def extract_from_pdf_page(page_text: str, page_number: int):
    # Table-aware extraction first: PDF text often puts FY headers above labels,
    # which a keyword-only sentence window cannot reliably associate.
    candidates = _table_candidates(page_text)
    for sentence in split_sentences(page_text):
        for candidate in extract_from_text_segment(sentence):
            candidates.append(candidate)

    candidates = _deduplicate_page_candidates(candidates)
    for candidate in candidates:
        candidate["source_page"] = page_number
        candidate["provenance_confidence"] = "high"
    return candidates


def extract_from_csv_row(row_text_by_column: dict, row_number: int):
    candidates = []
    for column, cell_value in row_text_by_column.items():
        cell_text = f"{column}: {cell_value}"
        keyword, metric_type = norm.find_metric_keyword(str(column))
        if not keyword:
            keyword, metric_type = norm.find_metric_keyword(cell_text)
        if not keyword:
            continue
        values = norm.find_all_values(str(cell_value), allow_bare=(metric_type == "customer_count"))
        if not values:
            continue
        value = values[0]
        periods = norm.find_all_periods(str(column))
        period = periods[0] if periods else None
        signals = {"keyword": True, "number": True, "unit": bool(value["original_unit"] or value["currency"]), "period": period is not None}
        score, label = score_and_label(signals)
        candidates.append({
            "raw_text": cell_text, "metric_type": metric_type, "matched_keyword": keyword,
            "signals": signals, "confidence_score": score, "confidence_label": label,
            "original_value": value["original_value"], "original_unit": value["original_unit"],
            "normalized_value": value["normalized_value"], "currency": value["currency"],
            "period_raw": period["period_raw"] if period else None,
            "period_normalized": period["period_normalized"] if period else None,
            "source_row": row_number, "source_column": column, "provenance_confidence": "high",
        })
    return candidates


def extract_from_xlsx_sheet(sheet_name: str, rows: list):
    candidates = []
    for row in rows:
        for column, info in row.items():
            cell_value, cell_ref = info.get("value"), info.get("cell")
            keyword, metric_type = norm.find_metric_keyword(str(column))
            if not keyword:
                keyword, metric_type = norm.find_metric_keyword(f"{column}: {cell_value}")
            if not keyword:
                continue
            values = norm.find_all_values(str(cell_value), allow_bare=(metric_type == "customer_count"))
            if not values:
                continue
            value = values[0]
            periods = norm.find_all_periods(str(column))
            period = periods[0] if periods else None
            signals = {"keyword": True, "number": True, "unit": bool(value["original_unit"] or value["currency"]), "period": period is not None}
            score, label = score_and_label(signals)
            candidates.append({
                "raw_text": f"{column}: {cell_value}", "metric_type": metric_type, "matched_keyword": keyword,
                "signals": signals, "confidence_score": score, "confidence_label": label,
                "original_value": value["original_value"], "original_unit": value["original_unit"],
                "normalized_value": value["normalized_value"], "currency": value["currency"],
                "period_raw": period["period_raw"] if period else None,
                "period_normalized": period["period_normalized"] if period else None,
                "source_sheet": sheet_name, "source_cell": cell_ref,
                "provenance_confidence": "high" if cell_ref else "low",
            })
    return candidates
