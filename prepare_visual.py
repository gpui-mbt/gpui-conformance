#!/usr/bin/env python3
"""Build pinned vlmkit in a fresh task-owned directory; no browser, VLM or GUI."""
import argparse
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile

from comparator import digest, load_json
from native_images import PINS
from run import artifact, command, execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vlmkit-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--online", action="store_true", help="Allow public dependency downloads; default is offline")
    args = parser.parse_args()
    pins = load_json(PINS)
    source, output = args.vlmkit_source.resolve(), args.output.resolve()
    if output.exists():
        raise ValueError("output already exists; prior evidence cannot be overwritten")
    if (command(["git", "rev-parse", "HEAD"], source) != pins["revision"] or
            command(["git", "rev-parse", "HEAD^{tree}"], source) != pins["source_tree"] or
            command(["git", "status", "--porcelain", "--untracked-files=no"], source)):
        raise ValueError("vlmkit source must be clean at the reviewed immutable pin")
    if (load_json(source / "package.json")["version"] != pins["version"] or
            digest((source / "pnpm-lock.yaml").read_bytes()) != pins["lock_sha256"] or
            digest((source / "LICENSE").read_bytes()) != pins["license_sha256"]):
        raise ValueError("vlmkit package/lock differs")
    output.mkdir(parents=True)
    runtime = output / "runtime"
    runtime.mkdir()
    archive = subprocess.check_output(["git", "archive", "HEAD"], cwd=source)
    if digest(archive) != pins["archive_sha256"]:
        raise ValueError("pinned vlmkit source archive differs")
    (output / "source.tar").write_bytes(archive)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(runtime, filter="data")
    receipt = {"schema_version": 1, "status": "unverified", "pins": pins,
               "node": command(["node", "--version"]), "pnpm": command(["pnpm", "--version"]),
               "moon": command(["moon", "version", "--all"]),
               "suite_revision": command(["git", "rev-parse", "HEAD"], Path(__file__).parent),
               "suite_dirty": bool(command(["git", "status", "--porcelain", "--untracked-files=no"], Path(__file__).parent))}
    if receipt["suite_dirty"]:
        raise ValueError("visual preparation tracked source is dirty")
    install = ["pnpm", "install", "--frozen-lockfile", "--ignore-scripts", "--store-dir", str(args.store.resolve()), "--registry", "https://registry.npmjs.org"]
    if not args.online:
        install.append("--offline")
    steps = (("install", install),
             ("moon_build", ["moon", "-C", "packages/vlmkit-markup", "build", "markup-core", "markup-core-api", "markup-core-cli", "--target", "js"]),
             ("build", ["pnpm", "build:packages:js"]))
    for name, argv in steps:
        receipt[name] = execute(argv, os.environ.copy(), output / (name + ".stdout"), output / (name + ".stderr"), runtime, 180)
        if receipt[name]["returncode"] or receipt[name]["timed_out"]:
            (output / "toolchain.json").write_text(json.dumps(receipt, indent=2) + "\n")
            return 2
    if command(["git", "rev-parse", "HEAD"], source) != pins["revision"] or command(["git", "status", "--porcelain", "--untracked-files=no"], source):
        raise ValueError("reference source changed during visual preparation")
    files = [output / "source.tar", runtime / "pnpm-lock.yaml"] + [output / (n + suffix) for n in ("install", "moon_build", "build") for suffix in (".stdout", ".stderr")]
    files += sorted(runtime.glob("packages/*/dist/*.mjs"))
    files += sorted(runtime.glob("packages/*/dist/**/*.mjs"))
    files += sorted(runtime.glob("packages/vlmkit-markup/_build/js/debug/build/**/*.js"))
    receipt["artifacts"] = [artifact(p, output) for p in sorted(set(files))]
    receipt["status"] = "ready"
    (output / "toolchain.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"status": "ready", "revision": pins["revision"], "artifacts": len(receipt["artifacts"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
