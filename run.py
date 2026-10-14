#!/usr/bin/env python3
"""Build and execute both pinned implementations without native windows."""
import argparse
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import uuid

from comparator import compare, digest

ROOT = Path(__file__).resolve().parent


def now():
    return datetime.now(timezone.utc).isoformat()


def command(args, cwd=None):
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def source(path, revision):
    actual = command(["git", "rev-parse", "HEAD"], path)
    if actual != revision:
        raise ValueError(f"{path}: expected {revision}, got {actual}")
    dirty = bool(command(["git", "status", "--porcelain", "--untracked-files=no"], path))
    if dirty:
        raise ValueError(f"{path}: tracked source has local changes")
    return {"revision": actual, "source_tree": command(["git", "rev-parse", "HEAD^{tree}"], path), "dirty": dirty}


def artifact(path, root):
    return {"path": str(path.relative_to(root)), "sha256": digest(path.read_bytes())}


def execute(args, env, out, err, cwd, timeout):
    started = now()
    timed_out = False
    with out.open("wb") as stdout, err.open("wb") as stderr:
        proc = subprocess.Popen(args, env=env, stdout=stdout, stderr=stderr, cwd=cwd)
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()  # This owned child only; no global process/service cleanup.
            code = proc.wait()
    return {"command": args, "pid": proc.pid, "started_at": started, "finished_at": now(),
            "returncode": code, "timed_out": timed_out}


def prepare_moonbit(path, build):
    runtime = build / ("moonbit-runtime-" + str(uuid.uuid4()))
    runtime.mkdir(parents=True, exist_ok=True)
    archive = subprocess.check_output(["git", "archive", "HEAD"], cwd=path)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(runtime, filter="data")
    probe = runtime / "conformance_probe"
    shutil.copytree(ROOT / "adapters/moonbit", probe, dirs_exist_ok=True)
    return runtime


def prepare_rust(path, build):
    adapter = build / "rust-adapter"
    shutil.copytree(ROOT / "adapters/rust", adapter, dirs_exist_ok=True)
    manifest = adapter / "Cargo.toml"
    manifest.write_text(manifest.read_text().replace('"../../../zed-source/crates/gpui"', json.dumps(str(path / "crates/gpui"))))
    return adapter


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream-source", type=Path, default=ROOT.parent / "zed-source")
    parser.add_argument("--moonbit-source", type=Path, default=ROOT.parent / "gpui-reference")
    parser.add_argument("--candidate-revision", help="Explicit full SHA for a separately committed gpui.mbt candidate")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--online", action="store_true", help="Allow Cargo dependency downloads into configured CARGO_HOME")
    parser.add_argument("--negative-control", action="store_true", help="Perturb the MoonBit adapter's measured layout width by one pixel")
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    build = ROOT / "_build"
    build.mkdir(exist_ok=True)
    pins = json.loads((ROOT / "pins.json").read_text())
    if args.candidate_revision:
        if len(args.candidate_revision) != 40 or any(c not in "0123456789abcdef" for c in args.candidate_revision):
            parser.error("candidate revision must be a full immutable SHA")
        pins["moonbit"]["baseline_revision"] = pins["moonbit"]["revision"]
        pins["moonbit"]["revision"] = args.candidate_revision
    sources = {"upstream": args.upstream_source.resolve(), "moonbit": args.moonbit_source.resolve()}
    identities = {name: source(path, pins[name]["revision"]) for name, path in sources.items()}
    scenarios = (ROOT / "scenarios.json").read_bytes()
    (out / "scenarios.json").write_bytes(scenarios)
    host = {"os": platform.system(), "architecture": platform.machine(), "release": platform.release(),
            "macos": platform.mac_ver()[0]}
    manifest = {"schema_version": 1, "pins": pins, "platform": host, "negative_control": args.negative_control,
                "suite_revision": command(["git", "rev-parse", "HEAD"], ROOT),
                "suite_dirty": bool(command(["git", "status", "--porcelain"], ROOT)), "runs": {}}
    env = os.environ.copy()
    rust_adapter = prepare_rust(sources["upstream"], build)
    runtime = prepare_moonbit(sources["moonbit"], build)
    env["CARGO_TARGET_DIR"] = str(build / "rust")
    env["GPUI_SCENARIOS"] = scenarios.decode()
    env["GPUI_NEGATIVE_CONTROL"] = "1" if args.negative_control else "0"
    configs = {
        "upstream": {"build": ["cargo", "+1.98.1", "build", "--locked"] + ([] if args.online else ["--offline"]) + ["--manifest-path", str(rust_adapter / "Cargo.toml")],
                     "cwd": ROOT, "exe": build / "rust/debug/gpui-conformance-probe", "version": command(["rustc", "+1.98.1", "--version"])},
        "moonbit": {"build": ["moon", "build", "--target", "native", "--deny-warn", "conformance_probe"],
                    "cwd": runtime, "exe": runtime / "_build/native/debug/build/conformance_probe/conformance_probe.exe", "version": command(["moon", "version"])},
    }
    for name, config in configs.items():
        folder = out / name
        folder.mkdir()
        token = str(uuid.uuid4())
        run = {**identities[name], "implementation": name, "version": pins[name]["version"], "platform": host,
               "toolchain": config["version"], "scenarios_sha256": digest(scenarios), "run_token": token}
        run["build"] = execute(config["build"], env, folder / "build.stdout", folder / "build.stderr", config["cwd"], 600)
        run["build_stdout"] = artifact(folder / "build.stdout", out)
        run["build_stderr"] = artifact(folder / "build.stderr", out)
        if run["build"]["returncode"] == 0:
            exe = folder / "probe"
            shutil.copy2(config["exe"], exe)
            run["executable"] = artifact(exe, out)
            child_env = env.copy()
            child_env["GPUI_RUN_TOKEN"] = token
            run["execution"] = execute([str(exe)], child_env, folder / "stdout.log", folder / "stderr.log", ROOT, 30)
            run["stdout"] = artifact(folder / "stdout.log", out)
            run["stderr"] = artifact(folder / "stderr.log", out)
        manifest["runs"][name] = run
        # Verify the read-only inputs again after build and execution.
        source(sources[name], pins[name]["revision"])
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    result = compare(manifest, json.loads(scenarios), out)
    (out / "comparison.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["summary"]))
    print(out / "comparison.json")
    return 1 if result["summary"]["mismatch"] else 2 if result["summary"]["unverified"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
