#!/usr/bin/env python3
"""Reset one hatch-pet image job in a run directory."""

from __future__ import annotations

import json
import sys
from pathlib import Path


RESET_KEYS = {
    "status",
    "source_path",
    "source_provenance",
    "source_sha256",
    "output_sha256",
    "synthetic_test_source",
    "completed_at",
    "metadata",
    "last_error",
    "secondary_fallback",
    "canonical_reference_path",
}


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: reset_hatch_job.py <run-dir> <job-id>", file=sys.stderr)
        return 2

    run_dir = Path(sys.argv[1]).resolve()
    job_id = sys.argv[2]
    manifest_path = run_dir / "imagegen-jobs.json"
    if not manifest_path.is_file():
        print(f"missing manifest: {manifest_path}", file=sys.stderr)
        return 1

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    jobs = manifest.get("jobs")
    if not isinstance(jobs, list):
        print("invalid imagegen-jobs.json: jobs must be a list", file=sys.stderr)
        return 1

    for job in jobs:
        if isinstance(job, dict) and job.get("id") == job_id:
            output_raw = job.get("output_path")
            if isinstance(output_raw, str):
                output_path = safe_job_output_path(run_dir, output_raw)
                if output_path is None:
                    print(f"refusing to delete unexpected path: {output_raw}", file=sys.stderr)
                    return 1
                if output_path.exists():
                    output_path.unlink()
            for key in RESET_KEYS:
                job.pop(key, None)
            job["status"] = "pending"
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            print(f"reset {job_id}")
            return 0

    print(f"unknown job id: {job_id}", file=sys.stderr)
    return 1


def safe_job_output_path(run_dir: Path, raw_path: str) -> Path | None:
    if not raw_path.strip():
        return None

    path = Path(raw_path)
    if path.is_absolute() or ".." in path.parts:
        return None

    resolved_run_dir = run_dir.resolve()
    resolved_output = (resolved_run_dir / path).resolve()
    try:
        resolved_output.relative_to(resolved_run_dir)
    except ValueError:
        return None
    return resolved_output


if __name__ == "__main__":
    raise SystemExit(main())
