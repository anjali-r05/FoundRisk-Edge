"""
FoundRisk Edge — provenance validation.

Single source of truth for "is this source location trustworthy enough to
show as precise, or should it be marked provenance_confidence = low?"
Extraction services (document_parser / claim_extractor) attach whatever
source fields they found; this module is the gate that runs right before
persistence and decides the final provenance_confidence — it never invents
a location, it only ever downgrades confidence when what was captured is
incomplete.
"""


def evaluate(candidate: dict) -> str:
    """
    candidate: a claim-candidate dict as produced by claim_extractor, possibly
    with source_page / source_sheet+source_cell / source_row+source_column set.
    Returns "high" or "low".
    """
    if candidate.get("source_page") is not None:
        return "high"

    if candidate.get("source_sheet") is not None and candidate.get("source_cell") is not None:
        return "high"

    if candidate.get("source_row") is not None and candidate.get("source_column") is not None:
        return "high"

    return "low"


def build_source_location(filename: str, candidate: dict) -> str:
    """Build the human-readable source string strictly from fields actually present."""
    if candidate.get("source_page") is not None:
        return f"{filename}, page {candidate['source_page']}"

    if candidate.get("source_sheet") is not None:
        loc = f"{filename}, sheet: {candidate['source_sheet']}"
        if candidate.get("source_cell"):
            loc += f", cell: {candidate['source_cell']}"
        return loc

    if candidate.get("source_row") is not None:
        loc = f"{filename}, row {candidate['source_row']}"
        if candidate.get("source_column"):
            loc += f", column: {candidate['source_column']}"
        return loc

    return f"{filename} (location unconfirmed)"
