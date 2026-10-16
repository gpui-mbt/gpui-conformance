#!/usr/bin/env python3
"""Build the actual MoonBit port in a disposable copy of the pinned candidate."""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

WEB = Path(__file__).resolve().parents[1]


def run(args: list[str], cwd: Path, capture: bool = False) -> str:
    result = subprocess.run(args, cwd=cwd, check=True, text=True,
                            stdout=subprocess.PIPE if capture else None)
    return result.stdout.strip() if capture else ""


def check_source(path: Path, revision: str) -> None:
    if run(["git", "rev-parse", "HEAD"], path, True) != revision:
        raise ValueError(f"revision mismatch in {path}: expected {revision}")
    if run(["git", "status", "--porcelain", "--untracked-files=no"], path, True):
        raise ValueError(f"tracked source is dirty: {path}")


def build(gpui: Path, upstream: Path, out: Path) -> None:
    catalog = json.loads((WEB / "examples.json").read_text())
    check_source(gpui, catalog["moonbit"]["revision"])
    check_source(upstream, catalog["upstream"]["revision"])
    if out.exists():
        raise ValueError(f"output exists: {out}; select a new --out directory")
    source = (upstream / "crates/gpui/examples/hello_world.rs").read_bytes()
    digest = hashlib.sha1(b"blob " + str(len(source)).encode() + b"\0" + source).hexdigest()
    if digest != catalog["upstream"]["hello_world_blob"]:
        raise ValueError("upstream hello_world.rs does not match the recorded source blob")
    implemented = [example for example in catalog["examples"] if example.get("moonbit") == "implemented"]
    for example in implemented:
        if example.get("source_blob"):
            actual = run(["git", "rev-parse", f"HEAD:{example['source']}"], upstream, True)
            if actual != example["source_blob"]:
                raise ValueError(f"upstream source blob mismatch for {example['id']}")
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gpui-web-", dir=out.parent) as work:
        candidate = Path(work) / "candidate"
        candidate.mkdir()
        archive = subprocess.run(["git", "archive", "HEAD"], cwd=gpui, check=True, stdout=subprocess.PIPE).stdout
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(candidate, filter="data")
        version = run(["moon", "version", "--all"], candidate, True)
        runtimes = {}
        for example in implemented:
            name = example["id"]
            package = f"examples/conformance_{name}"
            shutil.copytree(WEB / "moonbit" / name, candidate / package)
            run(["moon", "test", package, "--target", "js"], candidate)
            run(["moon", "build", package, "--target", "js", "--release"], candidate)
            runtime = candidate / "_build/js/release/build" / package / f"conformance_{name}.js"
            if not runtime.is_file():
                raise ValueError(f"expected generated ESM module missing: {runtime}")
            runtimes[name] = runtime
        staging = Path(work) / "site"
        staging.mkdir()
        for name in ["index.html", "style.css", "app.js", "routing.mjs", "examples.json"]:
            shutil.copy2(WEB / name, staging / name)
        shutil.copytree(WEB / "moonbit/site", staging / "moonbit")
        for name, runtime in runtimes.items():
            shutil.copy2(runtime, staging / "moonbit" / ("runtime.mjs" if name == "hello_world" else f"{name}.mjs"))
        font_dir = upstream / "assets/fonts/ibm-plex-sans"
        for font_name in ["IBMPlexSans-Regular.ttf", "IBMPlexSans-Italic.ttf", "IBMPlexSans-SemiBold.ttf"]:
            shutil.copy2(font_dir / font_name, staging / "moonbit")
        shutil.copy2(font_dir / "license.txt", staging / "moonbit/font-license.txt")
        # Record the measured compiler, not an invented reproducibility claim.
        manifest = {"upstream": catalog["upstream"], "moonbit": catalog["moonbit"],
                    "lab_revision": run(["git", "rev-parse", "HEAD"], WEB.parent, True),
                    "lab_tracked_dirty": bool(run(["git", "status", "--porcelain", "--untracked-files=no"], WEB.parent, True)),
                    "compiler": version, "runtime_sha256": hashlib.sha256(runtimes["hello_world"].read_bytes()).hexdigest(),
                    "font_sha256": hashlib.sha256((font_dir / "IBMPlexSans-Regular.ttf").read_bytes()).hexdigest(),
                    "implemented": list(runtimes),
                    "runtime_sha256_by_example": {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in runtimes.items()}, "rust_bundled": False,
                    "comparison_status": "unverified", "moonbit_unit_tests": "passed"}
        (staging / "build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        check_source(gpui, catalog["moonbit"]["revision"])
        check_source(upstream, catalog["upstream"]["revision"])
        shutil.copytree(staging, out)
    print(f"Built {out}; Rust comparison remains unverified")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpui-source", required=True, type=Path)
    parser.add_argument("--upstream-source", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=Path("_build/browser-lab"))
    args = parser.parse_args()
    try:
        build(args.gpui_source.resolve(), args.upstream_source.resolve(), args.out.resolve())
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"browser example build failed: {error}\n")
