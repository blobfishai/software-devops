#!/usr/bin/env python3
"""Seal the built + qualified DevOpsBench-100 release with a file manifest.

Run AFTER builder.py and run_suite.py.  Inventories every file in
dist/devopsbench-100 with its size and sha256, and writes
release-manifest.json at the release root (counselbench-100 parity).

Run:  python3 benchmark/devopsbench100/finalize.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def seal(release: pathlib.Path) -> dict:
    release = release.resolve()
    manifest_path = release / "release-manifest.json"
    required = [
        release / "harbor" / "dataset" / "dataset.toml",
        release / "reports" / "build.json",
        release / "reports" / "qualification.json",
        release / "huggingface" / "data" / "tasks.jsonl",
        release / "huggingface" / "README.md",
        release / "huggingface" / "LICENSE-CODE",
        release / "huggingface" / "LICENSE-DATA",
    ]
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(f"release is incomplete: {path}")
    qualification = json.loads((release / "reports" / "qualification.json").read_text())
    if not qualification.get("release_passed"):
        raise ValueError("refusing to seal: qualification.json is not green")

    files = sorted(path for path in release.rglob("*")
                   if path.is_file() and path != manifest_path)
    manifest = {
        "schema_version": "1.0",
        "benchmark": "DevOpsBench-100",
        "version": "1.0.0",
        "qualification": {
            "release_passed": qualification["release_passed"],
            "executions": qualification["executions"],
            "oracle_passes": qualification["oracle"]["passes"],
            "determinism_matches": qualification["determinism"]["exact_report_matches"],
            "negative_false_accepts": sum(
                row["false_accepts"]
                for row in qualification["negative_controls"].values()),
        },
        "files": [
            {
                "path": path.relative_to(release).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in files
        ],
    }
    manifest["manifest_sha256"] = hashlib.sha256(
        json.dumps(manifest, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"files": len(manifest["files"]),
            "manifest_sha256": manifest["manifest_sha256"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", type=pathlib.Path,
                        default=pathlib.Path(__file__).resolve().parents[2]
                        / "dist" / "devopsbench-100")
    print(json.dumps(seal(parser.parse_args().release), indent=2, sort_keys=True))
