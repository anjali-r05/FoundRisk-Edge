# Phase 2 — Contradiction Engine + Source Observation Visibility

## What is included
- Integrated deterministic discrepancy review inside the existing Analysis page.
- Comparison is limited to the same metric, normalized reporting period, and currency across different source documents.
- Observation ledger preserves actual values and source provenance even when there is only one source or periods differ.
- The Analysis contradiction section now includes a dedicated **Actual observations being checked** panel, so users can see the extracted numbers even when no cross-document discrepancy is possible.
- Findings show source A/source B, normalized and original values, source location, percentage difference, severity, and explanation.
- No currency conversion, fraud verdict, or invented risk score.

## Validation
- Python compileall passed.
- Synthetic test PDF extracted exactly six expected metric observations (Revenue, Customer Count, Market Size for FY2025 and FY2026) with expected normalized values.
- Analysis-page JavaScript syntax check passed.
- Contradiction-engine smoke tests passed for same-period cross-source discrepancy and different-period non-comparison.
- Full Flask/pytest integration suite could not be run in this environment because Flask dependencies are not installed and package downloads are unavailable.

## UI / workspace refinement — September 27, 2026

- Moved the Contradiction Engine out of the Analysis page into its own dedicated `/contradictions` workspace and sidebar item.
- Added a dedicated review dashboard with severity totals, comparison coverage, source observation ledger, severity filtering, search, refresh, and paired evidence views.
- Kept the existing `/api/analysis/contradictions` comparison service and deterministic comparison rules; this is a presentation/workspace separation, not a new risk verdict.
- Improved the Analysis observation ledger so it displays extracted evidence records instead of leaving the section unpopulated.
- Added responsive teal premium styling for the new workspace.


## Evidence Explorer — September 27, 2026

- Upgraded Evidence Explorer records to show the source filename, captured page/sheet/cell/row location, original excerpt, metric, period, value, and confidence.
- Added a richer evidence detail drawer with source document, exact captured location, extraction signals, source excerpt, and normalization details. Missing provenance is explicitly marked unavailable; no location is inferred.
- Expanded evidence search across excerpt text, original claim text, source filename, metric keyword, and captured spreadsheet location fields.
- Added clear-search/reset controls, improved empty/error states, and CSV export fields for source and metric details.
- Added responsive source-first styling for the evidence workspace and detail drawer.
- Updated API tests for source filename search and provenance fields.


## Evidence Explorer accuracy and export hardening — September 27, 2026

- Evidence cards and the detail drawer now foreground the value exactly as written in the source (original value + unit) and label the normalized absolute value separately.
- CSV export headers now distinguish original and normalized values and include provenance confidence.
- CSV export neutralizes formula-like text values to reduce spreadsheet formula-injection risk while preserving ordinary negative numeric values.
- Switching projects clears stale Evidence Explorer filters; document-filter loading now fails gracefully with a visible message.
- Validation performed for this revision: Python compile check, JavaScript syntax checks, and ZIP integrity. Full Flask/pytest runtime tests remain blocked in this environment because Flask dependencies are unavailable and package index DNS access failed.

- Fixed a confirmed extraction defect: plain customer counts written before terms such as "paying customers" were missed. The extractor now captures a directly adjacent count and preserves a nearby fiscal period without borrowing a prior metric's value. Added regression tests.

## Phase 3 — Risk Findings + Due Diligence Copilot
- Added persistent `RiskFinding` records with stable project-scoped keys, severity, category, confidence, status, evidence links and recommended actions.
- Added transparent rules for missing metric coverage, low-confidence extracted claims, and cross-document metric discrepancies. Findings are review signals—not fraud conclusions.
- Added risk queue API with refresh, status filters, severity filters and open/reviewing/resolved workflow.
- Added premium light-teal Risk Findings page with severity/status chips, evidence trail, impact, next-step guidance and status actions.
- Added a local evidence-retrieval Copilot endpoint and workspace UI with prompt suggestions, citations, source locations, normalized values/periods, and a no-evidence response. It does not call a remote model or paid API and is labeled as retrieval, not generative AI.
- Added navigation entries and Copilot/Risk APIs under `/api/intelligence`.
