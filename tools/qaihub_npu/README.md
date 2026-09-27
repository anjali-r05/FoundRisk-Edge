# Qualcomm AI Hub Workbench — hosted Snapdragon NPU smoke test

## Scope

This optional tool submits a small deterministic MLP to Qualcomm AI Hub Workbench, requests QNN DLC compilation and NPU-targeted profile/inference, compares device output with a local PyTorch reference, and writes a JSON report with actual job IDs, job URLs, statuses, output differences and raw profile data.

**It is not a benchmark of FoundRisk's PDF parsing, extraction, evidence engine, rules-based risk findings, or Copilot.** It does not prove every operator ran on the NPU. Review the raw profile and job details to confirm compute-unit mapping. No prefilled measurements are included.

## Run it (no Snapdragon PC needed)

1. Create/sign in to Qualcomm AI Hub Workbench: https://workbench.aihub.qualcomm.com/
2. Get an API token and configure the official client. Follow current setup instructions: https://workbench.aihub.qualcomm.com/docs/hub/getting_started.html
3. Use Python 3.10+ in a clean virtual environment and install dependencies:

   ```bash
   python -m pip install -r tools/qaihub_npu/requirements.txt
   qai-hub configure --api_token YOUR_API_TOKEN
   qai-hub list-devices
   ```

4. Copy an exact supported Snapdragon device name from `qai-hub list-devices`, then run:

   ```bash
   python tools/qaihub_npu/run_npu_smoke_test.py --device "EXACT DEVICE NAME" --out instance/qaihub_npu_report.json
   ```

The script exits with code 0 only when compile, profile, inference and numerical agreement pass. A failed run still writes a report with `overall_status: ERROR` or `FAIL`. Never put your API token in the project or commit it.

## Import the result into FoundRisk

Open **Runtime Benchmarks**, choose **Import AI Hub report JSON**, and select the generated report. FoundRisk checks its expected schema and stores the report locally. Imported data is shown as a *hosted model smoke test*, not as an end-to-end FoundRisk NPU benchmark.

Official references:
- API and jobs: https://workbench.aihub.qualcomm.com/docs/hub/api.html
- Compile job API: https://workbench.aihub.qualcomm.com/docs/hub/generated/qai_hub.submit_compile_job.html
- Profiling examples: https://workbench.aihub.qualcomm.com/docs/hub/profile_examples.html
