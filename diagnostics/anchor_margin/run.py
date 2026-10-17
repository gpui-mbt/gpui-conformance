#!/usr/bin/env python3
"""Build the separate font-free source5a GPUI scalar-margin diagnostic and retain raw evidence."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import uuid

from verify import LAYER, UPSTREAM, UPSTREAM_TREE, RETAIN, UPSTREAM_RETAIN, digest, require, retained_path, validate_scenarios, verify_bundle, load_json

ROOT = Path(__file__).resolve().parents[2]



def now():
    return datetime.now(timezone.utc).isoformat()


def command(arguments, cwd=None):
    return subprocess.check_output(arguments, cwd=cwd, text=True).strip()


def source_identity(path, expected=None, tree=None, enforce_clean=True):
    result = {"commit": command(["git", "rev-parse", "HEAD"], path),
              "tree": command(["git", "rev-parse", "HEAD^{tree}"], path),
              "clean": not command(["git", "status", "--porcelain", "--untracked-files=all"], path)}
    require(not enforce_clean or result["clean"], f"dirty source: {path}")
    require(expected is None or result["commit"] == expected, f"wrong commit: {path}")
    require(tree is None or result["tree"] == tree, f"wrong tree: {path}")
    return result


def execute(arguments, directory, stem, environment, timeout):
    started = now()
    with (directory / (stem + ".stdout")).open("wb") as stdout, (directory / (stem + ".stderr")).open("wb") as stderr:
        process = subprocess.Popen(arguments, cwd=ROOT, env=environment, stdout=stdout, stderr=stderr)
        timed_out = False
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            code = process.wait()
    return {"command": arguments, "started_at": started, "finished_at": now(), "returncode": code,
            "timed_out": timed_out, "pid": process.pid}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--online", action="store_true", help="Allow locked dependency downloads")
    arguments = parser.parse_args()
    upstream = arguments.upstream_source.resolve()
    suite_identity = source_identity(ROOT)
    upstream_identity = source_identity(upstream, UPSTREAM, UPSTREAM_TREE)
    require(shutil.disk_usage(ROOT).free >= 8 * 1024**3, "At least 8 GiB free is required. Use the dedicated CI job; do not delete retained evidence/caches.")
    scenarios_path = ROOT / "diagnostics/anchor_margin/scenarios.json"
    validate_scenarios(json.loads(scenarios_path.read_text()))
    out = arguments.output.resolve()
    require(out.is_relative_to(ROOT / "_build"), "output must be a fresh directory under the ignored _build directory")
    out.mkdir(parents=True, exist_ok=False)
    token = str(uuid.uuid4())
    build = ROOT / "_build" / ("anchor-margin-build-" + token)
    build.mkdir()
    stage = build / "adapter"
    shutil.copytree(ROOT / "adapters/anchor_margin_rust", stage)
    original = (stage / "Cargo.toml").read_text()
    placeholder = '"../../../zed-source/crates/gpui"'
    require(original.count(placeholder) == 1, "manifest dependency placeholder")
    (stage / "Cargo.toml").write_text(original.replace(placeholder, json.dumps(str(upstream / "crates/gpui"))))
    profile = load_json(ROOT / "diagnostics/anchor_margin/profile.json")
    require(digest(scenarios_path) == profile["input_sha256"], "authored corpus/profile mismatch")
    for relative, expected in profile["frozen_original"]["sha256"].items():
        require(digest(ROOT / relative) == expected, "frozen original changed: " + relative)
    for relative in RETAIN + list(profile["frozen_original"]["sha256"]):
        destination = out / retained_path(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    for relative in UPSTREAM_RETAIN:
        destination = out / "upstream" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(upstream / relative, destination)
    shutil.copy2(stage / "Cargo.toml", out / "build-Cargo.toml")
    shutil.copy2(scenarios_path, out / "scenarios.json")
    toolchain = command(["rustc", "+1.98.1", "--version", "--verbose"]) + "\n" + command(["cargo", "+1.98.1", "--version", "--verbose"]) + "\n"
    require(toolchain.startswith("rustc 1.98.1 "), "wrong Rust compiler")
    (out / "toolchain.txt").write_text(toolchain)
    environment = os.environ.copy()
    environment.pop("DISPLAY", None)
    environment.pop("WAYLAND_DISPLAY", None)
    environment["CARGO_TARGET_DIR"] = str(build / "target")
    environment["CARGO_BUILD_JOBS"] = "2"
    environment["CARGO_INCREMENTAL"] = "0"
    build_command = ["cargo", "+1.98.1", "build", "--locked", "--manifest-path", str(stage / "Cargo.toml")]
    if not arguments.online: build_command.append("--offline")
    manifest = {"schema_version": 1, "layer": LAYER, "run_token": token, "started_at": now(),
        "suite": suite_identity, "upstream": upstream_identity, "upstream_source_path": str(upstream),
        "platform": {"system": platform.system(), "machine": platform.machine(), "release": platform.release()},
        "ci": {key: os.environ.get(key) for key in ("GITHUB_REPOSITORY", "GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_WORKFLOW", "GITHUB_JOB")},
        "environment": {"CARGO_BUILD_JOBS": "2", "CARGO_INCREMENTAL": "0", "DISPLAY": None, "WAYLAND_DISPLAY": None},
        "files": {}}
    execution_command = [str(out / "probe"), str(out / "scenarios.json"), token]
    plan = {"schema_version": 1, "layer": LAYER, "run_token": token,
        "build_command": build_command, "execution_command": execution_command,
        "environment": manifest["environment"], "input_sha256": digest(out / "scenarios.json"),
        "lock_sha256": digest(stage / "Cargo.lock"), "build_manifest_sha256": digest(out / "build-Cargo.toml"),
        "toolchain_sha256": digest(out / "toolchain.txt")}
    (out / "build-plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    manifest["build"] = execute(build_command, out, "build", environment, 2100)
    if manifest["build"]["returncode"] == 0:
        shutil.copy2(build / "target/debug/gpui-anchor-margin-diagnostic", out / "probe")
        manifest["execution"] = execute(execution_command, out, "raw", environment, 120)
        (out / "raw.stdout").rename(out / "raw.json")
    manifest["suite_after"] = source_identity(ROOT, enforce_clean=False)
    manifest["upstream_after"] = source_identity(upstream, enforce_clean=False)
    shutil.copy2(stage / "Cargo.lock", out / "build-Cargo.lock")
    manifest["finished_at"] = now()
    for path in sorted(out.rglob("*")):
        if path.is_file():
            manifest["files"][str(path.relative_to(out))] = {"sha256": digest(path), "size": path.stat().st_size}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    try:
        result = verify_bundle(out, suite_identity["commit"], suite_identity["tree"], ROOT, upstream)
    except Exception as error:
        (out / "verification-failure.json").write_text(json.dumps({"error": str(error), "type": type(error).__name__}, indent=2) + "\n")
        raise
    (out / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"evidence": str(out), "cases": len(result["cases"]), "layer": LAYER}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
