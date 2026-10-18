#!/usr/bin/env python3
"""Prepare only static host inputs for the unchanged gradient Rust oracle.

No MoonBit compiler, candidate runtime, or upstream engine is executed here.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from build_moonbit import WEB, run
from build_rust import gradient_oracle_catalog_bytes


def prepare(out: Path) -> None:
    # This source-only profile carries its own immutable metadata. Registering
    # a candidate in the live catalog must not rewrite or disable this oracle.
    catalog_bytes = gradient_oracle_catalog_bytes(WEB)
    catalog = json.loads(catalog_bytes)
    if run(["git", "status", "--porcelain", "--untracked-files=no"], WEB.parent, True):
        raise ValueError("tracked suite files must be clean and committed before preparing evidence")
    if out.exists():
        raise ValueError("output exists; select a new site directory")
    revision = run(["git", "rev-parse", "HEAD"], WEB.parent, True)
    tree = run(["git", "rev-parse", "HEAD^{tree}"], WEB.parent, True)
    out.mkdir(parents=True)
    for name in ["load-timing.mjs", "_headers"]:
        shutil.copy2(WEB / name, out / name)
    (out / "examples.json").write_bytes(catalog_bytes)
    manifest = {
        "upstream": catalog["upstream"], "moonbit": catalog["moonbit"],
        "lab_revision": revision, "lab_tree": tree, "lab_tracked_dirty": False,
        "site_kind": "gradient_rust_oracle_only", "implemented": [],
        "moonbit_execution": "not_run", "comparison_status": "not_run", "rust_bundled": False,
        "moonbit_host_files_sha256": {"load-timing.mjs": hashlib.sha256((out / "load-timing.mjs").read_bytes()).hexdigest()},
    }
    (out / "build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Prepared unchanged Rust-only static host inputs in {out}; no runtime executed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("_build/gradient-browser-lab"))
    args = parser.parse_args()
    try:
        prepare(args.out.resolve())
    except (ValueError, OSError) as error:
        parser.exit(1, f"gradient site preparation failed: {error}\n")
