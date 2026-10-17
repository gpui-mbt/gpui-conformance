#!/usr/bin/env python3
"""Source-bound actual GPUI diagnostic. Run only in the approved dedicated Rust CI job."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import time
import uuid
from verify import (LAYER, UPSTREAM, UPSTREAM_TREE, RETAIN, UPSTREAM_RETAIN, digest,
                    require, retained_path, validate_scenarios, verify_bundle, load_json)
ROOT = Path(__file__).resolve().parents[2]
DISK_FLOOR = 1024**3
BUILD_HEADROOM = 8 * 1024**3


def now(): return datetime.now(timezone.utc).isoformat()
def command(arguments, cwd=None): return subprocess.check_output(arguments, cwd=cwd, text=True).strip()


def source_identity(path, expected=None, tree=None, enforce_clean=True):
    result = {"commit": command(["git", "rev-parse", "HEAD"], path),
              "tree": command(["git", "rev-parse", "HEAD^{tree}"], path),
              "clean": not command(["git", "status", "--porcelain", "--untracked-files=all"], path)}
    require(not enforce_clean or result["clean"], f"dirty source: {path}")
    require(expected is None or result["commit"] == expected, f"wrong commit: {path}")
    require(tree is None or result["tree"] == tree, f"wrong tree: {path}")
    return result


def disk_available(): return {str(path): shutil.disk_usage(path).free for path in (ROOT, Path("/tmp"))}


def execute(arguments, directory, stem, environment, timeout):
    started, begin = now(), time.monotonic()
    with (directory / (stem + ".stdout")).open("wb") as stdout, (directory / (stem + ".stderr")).open("wb") as stderr:
        process = subprocess.Popen(arguments, cwd=ROOT, env=environment, stdout=stdout, stderr=stderr, start_new_session=True)
        timed_out = resource_floor = False
        while process.poll() is None:
            timed_out = time.monotonic() - begin > timeout
            resource_floor = min(disk_available().values()) < DISK_FLOOR
            if timed_out or resource_floor:
                os.killpg(process.pid, signal.SIGKILL); break
            time.sleep(.25)
        code = process.wait()
    return {"command": arguments, "started_at": started, "finished_at": now(), "returncode": code,
            "timed_out": timed_out, "resource_floor_breached": resource_floor, "pid": process.pid}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--online", action="store_true", help="Allow locked dependency downloads")
    args = parser.parse_args()
    upstream = args.upstream_source.resolve()
    suite = source_identity(ROOT)
    pinned = source_identity(upstream, UPSTREAM, UPSTREAM_TREE)
    require(shutil.disk_usage(ROOT).free >= BUILD_HEADROOM and min(disk_available().values()) >= DISK_FLOOR,
            "Dedicated CI needs 8 GiB build headroom and a strict 1 GiB floor on workspace and /tmp. Never delete retained evidence to proceed.")
    scenarios_path = ROOT / "diagnostics/deferred_priority/scenarios.json"
    validate_scenarios(load_json(scenarios_path))
    out = args.output.resolve()
    require(out.is_relative_to(ROOT / "_build"), "output must be a fresh ignored _build directory")
    out.mkdir(parents=True, exist_ok=False)
    token = str(uuid.uuid4())
    build = ROOT / "_build" / ("deferred-priority-build-" + token)
    environment = os.environ.copy()
    environment.pop("DISPLAY", None); environment.pop("WAYLAND_DISPLAY", None)
    environment.update(CARGO_TARGET_DIR=str(build / "target"), CARGO_BUILD_JOBS="2", CARGO_INCREMENTAL="0")
    manifest = {"schema_version": 1, "layer": LAYER, "run_token": token, "started_at": now(),
        "suite": suite, "upstream": pinned, "upstream_source_path": str(upstream),
        "platform": {"system": platform.system(), "machine": platform.machine(), "release": platform.release()},
        "ci": {key: os.environ.get(key) for key in ("GITHUB_REPOSITORY", "GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_WORKFLOW", "GITHUB_JOB")},
        "environment": {"CARGO_BUILD_JOBS": "2", "CARGO_INCREMENTAL": "0", "DISPLAY": None, "WAYLAND_DISPLAY": None},
        "disk_floor_bytes": DISK_FLOOR, "disk_start": disk_available(), "files": {}}
    error = None
    try:
        build.mkdir(); stage = build / "adapter"
        shutil.copytree(ROOT / "adapters/deferred_priority_rust", stage)
        original = (stage / "Cargo.toml").read_text(); placeholder = '"../../../zed-source/crates/gpui"'
        require(original.count(placeholder) == 1, "manifest dependency placeholder")
        (stage / "Cargo.toml").write_text(original.replace(placeholder, json.dumps(str(upstream / "crates/gpui"))))
        profile = load_json(ROOT / "diagnostics/deferred_priority/profile.json")
        require(digest(scenarios_path) == profile["input_sha256"], "input/profile mismatch")
        for relative, expected in profile["frozen_original"]["sha256"].items():
            require(digest(ROOT / relative) == expected, "unchanged reference changed: " + relative)
        for relative in RETAIN + list(profile["frozen_original"]["sha256"]):
            destination = out / retained_path(relative); destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, destination)
        for relative in UPSTREAM_RETAIN:
            destination = out / "upstream" / relative; destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(upstream / relative, destination)
        shutil.copy2(stage / "Cargo.toml", out / "build-Cargo.toml")
        shutil.copy2(stage / "Cargo.lock", out / "build-Cargo.lock")
        shutil.copy2(scenarios_path, out / "scenarios.json")
        for tool in ("rustc", "cargo"):
            manifest[tool] = execute([tool, "+1.98.1", "--version", "--verbose"], out, tool, environment, 120)
            require(manifest[tool]["returncode"] == 0, "toolchain invocation failed: " + tool)
        (out / "toolchain.txt").write_bytes((out / "rustc.stdout").read_bytes() + (out / "cargo.stdout").read_bytes())
        require((out / "toolchain.txt").read_text().startswith("rustc 1.98.1 "), "compiler version")
        build_command = ["cargo", "+1.98.1", "build", "--locked", "--manifest-path", str(stage / "Cargo.toml")]
        if not args.online: build_command.append("--offline")
        execute_command = [str(out / "probe"), str(out / "scenarios.json"), token]
        plan = {"schema_version": 1, "layer": LAYER, "run_token": token, "build_command": build_command,
            "execution_command": execute_command, "environment": manifest["environment"],
            "input_sha256": digest(out / "scenarios.json"), "lock_sha256": digest(stage / "Cargo.lock"),
            "build_manifest_sha256": digest(out / "build-Cargo.toml"), "toolchain_sha256": digest(out / "toolchain.txt")}
        (out / "build-plan.json").write_text(json.dumps(plan, indent=2) + "\n")
        manifest["build"] = execute(build_command, out, "build", environment, 2100)
        shutil.copy2(stage / "Cargo.lock", out / "build-Cargo.lock")
        require(manifest["build"]["returncode"] == 0, "Rust build failed; original logs retained")
        shutil.copy2(build / "target/debug/gpui-deferred-priority-diagnostic", out / "probe")
        manifest["execution"] = execute(execute_command, out, "raw", environment, 120)
        # Preserve exact original bytes even when execution fails or output is invalid JSON.
        shutil.copy2(out / "raw.stdout", out / "raw.json")
        require(manifest["execution"]["returncode"] == 0, "Rust execution failed; original raw bytes retained")
    except Exception as caught:
        error = caught
        (out / "run-failure.json").write_text(json.dumps({"type": type(caught).__name__, "error": str(caught)}, indent=2) + "\n")
    finally:
        manifest["suite_after"] = source_identity(ROOT, enforce_clean=False)
        manifest["upstream_after"] = source_identity(upstream, enforce_clean=False)
        manifest["finished_at"] = now(); manifest["disk_end"] = disk_available()
        for path in sorted(out.rglob("*")):
            if path.is_file(): manifest["files"][str(path.relative_to(out))] = {"sha256": digest(path), "size": path.stat().st_size}
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if error is not None: raise error
    try:
        result = verify_bundle(out, suite["commit"], suite["tree"], ROOT, upstream)
    except Exception as caught:
        (out / "verification-failure.json").write_text(json.dumps({"type": type(caught).__name__, "error": str(caught)}, indent=2) + "\n")
        raise
    (out / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"evidence": str(out), "cases": len(result["cases"]), "layer": LAYER}))


if __name__ == "__main__": main()
