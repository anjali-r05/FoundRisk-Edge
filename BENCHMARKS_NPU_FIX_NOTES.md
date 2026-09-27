# Runtime Benchmarks correction

- Removed the CPU arithmetic benchmark from the Benchmarks page; no CPU workload is shown as an accelerator benchmark.
- The page now focuses on Qualcomm AI Hub hosted-device report evidence and explicitly distinguishes model smoke-test scope from the full FoundRisk pipeline.
- Added NPU-report snapshots linked to the selected workspace, with listing, selected-report export, atomic JSON persistence, and server-side report validation.
- Benchmark UI shows status/runtime/device from imported report metadata and does not manufacture latency or utilization values.
- The hosted test tool requests QNN DLC compilation and NPU-targeted profile/inference for profiling/inference; its output still requires review of raw profile evidence and a successful real hosted run.
- Actual Qualcomm AI Hub execution was not run in this environment; no NPU result is pre-populated.
