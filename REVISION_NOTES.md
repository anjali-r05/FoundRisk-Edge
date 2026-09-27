# FoundRisk Edge — UI refinement notes

This integrated build includes deterministic document intelligence, cross-document contradiction review, evidence-grounded Copilot retrieval, rule-based review findings, optional local Tesseract OCR, and a report-backed Qualcomm AI Hub smoke-test integration. It does not claim full FoundRisk pipeline execution on the Snapdragon NPU.

## Improvements
- Larger, higher-contrast type and more generous spacing across active pages.
- Overview adds project-health prompts and a metric coverage map based on current API data.
- Documents displays processing duration and retains real processing status.
- Analysis includes a detailed evidence ledger, normalized values, human-review queue, and clear Phase 1 limitations.
- Evidence displays original source values and normalized values separately; search now includes source location and metric family.
- Keeps the original project data model and source-provenance workflow.
- Adds a live contradiction API and Analysis-page review cards with severity filters, matched periods/currencies, paired source references, and explicit comparison limitations.

## Run
Open the extracted folder containing `run.py` and `requirements.txt`, then follow the Windows quick-start instructions in `README.md`.

## Phase 3 reliability fix — Risk Findings + Copilot
- Risk Findings now creates visible processing-attention items for documents that are queued, failed, empty, or otherwise not ready, instead of silently leaving the queue at zero.
- Successful document processing triggers a best-effort findings refresh so newly extracted evidence is reflected without waiting for a manual refresh.
- Copilot retrieval now uses metric intent and common aliases, can return broader project evidence/findings for summary and diligence questions, and reports actionable project/document states when files are missing, unprocessed, or yielded no supported claims.
- Copilot remains local and evidence-grounded; no paid API key or generated financial figures are introduced.

## 2026-09-27 — Intelligence surfaces and runtime controls
- Added live Benchmarks and Settings navigation pages (replacing the old Soon placeholders).
- Added a measured, deterministic CPU arithmetic microbenchmark with elapsed time, throughput, checksum, host architecture, Python version, and explicit NPU-not-tested disclosure.
- Added persistent benchmark snapshot storage under the Flask instance directory, a per-workspace recent-snapshot list, and JSON export from the UI.
- Added a live workspace inventory endpoint and Settings dashboard for document/claim/evidence/finding counts and metric-family coverage.
- Added project rename endpoint and browser-persisted display preferences (compact cards, full excerpt preference flag, reduce motion).
- Added severity-specific Risk Findings KPI cards, live high/medium/low counts, and stronger contrast/color hierarchy.
- Added voice dictation using browser Web Speech API when available; typed input remains available.
- Expanded contradiction cards with absolute gap, calculation formula, threshold band, and reconciliation questions.
- Removed the external-API banner from the Copilot page header; Copilot remains deterministic evidence retrieval.
- Validation: Python compileall passed; Jinja template parsing passed; inline JavaScript syntax checks passed. Full pytest could not start because Flask is not installed in the build environment. No live browser or Snapdragon NPU device validation was possible.

## Reliability repair — 2026-09-27 (Risk Findings + Benchmarks)

- Risk Findings now force-refreshes the selected workspace through the risk API on page load and refresh, and shows live document/claim/evidence counts so an empty queue is distinguishable from a failed connection or unprocessed workspace.
- Empty Risk Findings states now explain the exact next step rather than leaving a blank panel. Findings remain tied to extracted evidence and rule-based signals; no artificial risk items are generated just to fill the page.
- Benchmark status copy now describes the CPU-only workload directly instead of showing a vague “Not verified” badge.
- Snapshot persistence uses atomic JSON writes, snapshot history is ordered by saved timestamp, and a new read endpoint supports exporting the latest or selected saved snapshot as JSON.
- Snapshot save/export controls now show progress and errors, preserve the selected saved snapshot, and revoke download URLs after the browser has had time to start the download.
- Refreshed the Risk Findings workspace strip and benchmark snapshot cards with light teal, mint, blue, and warm accent colors.

### Verification boundary

- Python compilation, inline JavaScript syntax, and template parsing are checked in this environment.
- The full Flask/API/browser workflow could not be run here because Flask is not installed in the current runtime.
- The runtime benchmark measures a CPU arithmetic loop only. It does not execute an ML model on Qualcomm Snapdragon NPU/QNN, so this build does not claim NPU benchmark validation.


## Hosted Qualcomm AI Hub smoke-test integration (Sep 27, 2026)
- Added an optional Qualcomm AI Hub Workbench test tool under `tools/qaihub_npu/` that submits a deterministic synthetic MLP for QNN DLC compilation, NPU-targeted profiling and inference, and records job IDs/URLs, raw profile, output comparison and status in JSON.
- Added a Benchmarks UI section to import and inspect the resulting JSON report; imported reports are explicitly scoped to the synthetic model and do not claim that FoundRisk's complete pipeline runs on the NPU.
- Added local report persistence endpoints with required-field/schema checks. No cloud job was run in this development environment because no Qualcomm AI Hub credentials/device reservation were available.
- Risk Findings now emits an actionable Medium-severity evidence-gap item when a workspace has no source documents, rather than rendering a blank queue. Analysis readiness now describes the risk engine as implemented.


## 2026-09-27 — Benchmark screen correction (supersedes earlier CPU benchmark notes)

- Removed the local Python CPU microbenchmark controls and the corresponding legacy benchmark/snapshot API routes. The Benchmarks page is now NPU-report-first; it does not present CPU workload output as an accelerator measurement.
- The page displays only fields from an imported Qualcomm AI Hub test report, with explicit scope that the smoke test is synthetic and does not validate the full FoundRisk pipeline.
- Added workspace-linked NPU report snapshots with durable atomic JSON storage, history, selection, and selected-report export.
- No NPU result is prefilled. A real hosted test is still required before reporting actual latency or NPU utilization.
- Static checks: Python compilation, Jinja template parsing, and Node JavaScript syntax passed. Full pytest could not run because Flask is missing in this environment.


## Reliability repair — 2026-09-27 (session token, findings, Copilot, OCR, report import)

- Added a same-origin API fetch bridge that attaches the current CSRF token to every API write request and refreshes/retries once when an old tab has a stale token. Added a no-cache session token endpoint.
- Persisted a random local fallback Flask secret under `instance/.secret_key` so local app restarts do not invalidate all signed sessions; production should still set `FOUNDRISK_SECRET_KEY`.
- Added low-severity, evidence-linked single-source corroboration findings for metric families represented by only one source document. This avoids treating a single-source claim as false while giving the reviewer a concrete next step.
- Added local scanned-PDF OCR via Tesseract and page provenance; OCR is attempted only on pages with little/no text. If Tesseract is unavailable, the document status explains the setup requirement.
- Added a clearer Benchmarks import message for selecting a PDF instead of the Qualcomm report JSON, wrapper-report support, and stricter checks-object validation. The UI distinguishes a passing smoke test from confirmed NPU profile evidence.
- Validation: Python compileall and Node syntax checks passed; local OCR test extracted a revenue claim from a scanned PDF. Full Flask/API pytest and live Qualcomm AI Hub jobs could not be run here because Flask dependencies and AI Hub credentials/device access were unavailable.
