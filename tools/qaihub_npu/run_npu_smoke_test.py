#!/usr/bin/env python3
"""Run a real Qualcomm AI Hub Workbench QNN/NPU smoke test on hosted hardware.

This tests a tiny synthetic MLP, NOT FoundRisk's extraction or risk engine. The report
preserves actual job IDs/statuses and raw profile data; it never fabricates timings.
"""
from __future__ import annotations
import argparse
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
import qai_hub as hub

PRODUCT = "FoundRisk Edge — Qualcomm AI Hub NPU smoke test"

class SmokeNet(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.fc1 = torch.nn.Linear(16, 32)
        self.relu = torch.nn.ReLU()
        self.fc2 = torch.nn.Linear(32, 4)
    def forward(self, x):
        return self.fc2(self.relu(self.fc1(x)))

def to_jsonable(obj):
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (tuple, list)):
        return [to_jsonable(v) for v in obj]
    if hasattr(obj, "tolist"):
        try: return obj.tolist()
        except Exception: pass
    return str(obj)

def status_text(status):
    return str(status)

def require_success(job, label, timeout):
    status = job.wait(timeout=timeout)
    text = status_text(status)
    if "SUCCESS" not in text.upper():
        raise RuntimeError(f"{label} job did not succeed: {text} (job {getattr(job, 'job_id', 'unknown')})")
    return text

def main():
    parser = argparse.ArgumentParser(description="Qualcomm AI Hub hosted Snapdragon QNN/NPU smoke test")
    parser.add_argument("--device", required=True, help="Exact supported Snapdragon device name from qai-hub list-devices")
    parser.add_argument("--out", default="instance/qaihub_npu_report.json", help="JSON report output path")
    parser.add_argument("--timeout", type=int, default=1800, help="Per-job timeout in seconds")
    parser.add_argument("--tolerance", type=float, default=0.03, help="Maximum absolute difference vs local reference")
    args = parser.parse_args()
    started = time.perf_counter()
    report = {
        "product": PRODUCT,
        "test_scope": "Synthetic deterministic MLP smoke test; NOT FoundRisk application inference or performance.",
        "device_requested": args.device,
        "target_runtime_requested": "QNN DLC",
        "compute_unit_requested": "NPU",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "host": {"platform": platform.platform(), "python": platform.python_version(), "torch": torch.__version__},
        "model": {"architecture": "Linear(16,32) + ReLU + Linear(32,4)", "seed": 20260927},
        "checks": {}, "job_ids": {}, "job_urls": {},
    }
    output_path = Path(args.out).expanduser().resolve()
    try:
        torch.manual_seed(20260927)
        model = SmokeNet().eval()
        x = torch.linspace(-1.0, 1.0, steps=16, dtype=torch.float32).reshape(1, 16)
        with torch.no_grad():
            reference = model(x).cpu().numpy()
        exported = torch.export.export(model, (x,))
        report["input"] = {"name": "x", "shape": list(x.shape), "dtype": "float32"}
        report["checks"]["local_reference"] = "PASS"

        client = hub.Client()
        device = hub.Device(args.device)
        compile_job = client.submit_compile_job(
            model=exported,
            device=device,
            name="FoundRisk Edge synthetic NPU smoke test",
            input_specs={"x": tuple(x.shape)},
            options="--target_runtime qnn_dlc --qnn_options default_graph_htp_precision=FLOAT16",
        )
        report["job_ids"]["compile"] = str(compile_job.job_id)
        report["job_urls"]["compile"] = getattr(compile_job, "url", None)
        report["compile_status"] = require_success(compile_job, "Compile", args.timeout)
        target_model = compile_job.get_target_model()
        if target_model is None:
            raise RuntimeError("Compile job succeeded but returned no target model.")
        report["checks"]["qnn_compile"] = "PASS"

        profile_job = client.submit_profile_job(
            model=target_model, device=device,
            name="FoundRisk Edge NPU profile",
            options="--compute_unit npu",
        )
        report["job_ids"]["profile"] = str(profile_job.job_id)
        report["job_urls"]["profile"] = getattr(profile_job, "url", None)
        report["profile_status"] = require_success(profile_job, "Profile", args.timeout)
        profile = profile_job.download_profile()
        report["profile"] = to_jsonable(profile)
        report["checks"]["profile_job"] = "PASS"

        inference_job = client.submit_inference_job(
            model=target_model, device=device,
            inputs={"x": [x.numpy()]},
            name="FoundRisk Edge NPU numerical smoke test",
            options="--compute_unit npu",
        )
        report["job_ids"]["inference"] = str(inference_job.job_id)
        report["job_urls"]["inference"] = getattr(inference_job, "url", None)
        report["inference_status"] = require_success(inference_job, "Inference", args.timeout)
        output_data = inference_job.download_output_data()
        if not isinstance(output_data, dict) or not output_data:
            raise RuntimeError("Inference job completed but returned no output tensor dictionary.")
        out_name = next(iter(output_data))
        value = output_data[out_name]
        if isinstance(value, (list, tuple)):
            value = value[0]
        actual = np.asarray(value, dtype=np.float32)
        delta = np.abs(reference - actual)
        max_abs = float(np.max(delta))
        mean_abs = float(np.mean(delta))
        report["inference"] = {
            "output_name": out_name,
            "reference_output": reference.tolist(),
            "device_output": actual.tolist(),
            "max_absolute_difference": max_abs,
            "mean_absolute_difference": mean_abs,
            "tolerance": args.tolerance,
        }
        report["checks"]["numerical_agreement"] = "PASS" if max_abs <= args.tolerance else "FAIL"
        report["overall_status"] = "PASS" if report["checks"]["numerical_agreement"] == "PASS" else "FAIL"
        report["interpretation"] = (
            "QNN compile, NPU-targeted profile and inference jobs completed. Inspect raw profile/compute-unit mapping "
            "and job details before asserting that all operators executed on NPU. This smoke test does not validate FoundRisk's own pipeline."
        )
    except Exception as exc:
        report["overall_status"] = "ERROR"
        report["error_type"] = type(exc).__name__
        report["error"] = str(exc)
        report["interpretation"] = "This run does not establish successful NPU execution. Inspect the error and the AI Hub job details."
    finally:
        report["duration_seconds"] = round(time.perf_counter() - started, 3)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(to_jsonable(report), ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({
            "overall_status": report.get("overall_status"),
            "device_requested": report.get("device_requested"),
            "checks": report.get("checks"),
            "report_path": str(output_path),
            "job_ids": report.get("job_ids"),
            "job_urls": report.get("job_urls"),
            "error": report.get("error"),
        }, ensure_ascii=False, indent=2))
    return 0 if report.get("overall_status") == "PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
