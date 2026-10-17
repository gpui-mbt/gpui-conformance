#!/usr/bin/env python3
"""Prepare an independent Rust site and verify/assemble both CI-built runtimes."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

WEB = Path(__file__).resolve().parents[1]
SHA1 = re.compile(r"[0-9a-f]{40}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def repo_identity() -> tuple[str, str]:
    root = WEB.parent

    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=root, check=True, text=True,
                              capture_output=True).stdout.strip()

    if git("status", "--porcelain", "--untracked-files=no"):
        raise ValueError("tracked lab checkout is dirty")
    return git("rev-parse", "HEAD"), git("rev-parse", "HEAD^{tree}")


def catalog() -> dict:
    return json.loads((WEB / "examples.json").read_text())


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_manifest(site: Path) -> dict:
    return json.loads((site / "build-manifest.json").read_text())


def pinned(manifest: dict, expected: dict, revision: str) -> None:
    if manifest.get("upstream") != expected["upstream"] or manifest.get("moonbit") != expected["moonbit"]:
        raise ValueError("artifact source pins do not match the checked-out catalog")
    if manifest.get("lab_revision") != revision or manifest.get("lab_tracked_dirty") is not False:
        raise ValueError("artifact lab SHA differs or tracked sources were dirty")


def safe_file(root: Path, name: str) -> Path:
    relative = Path(name)
    if (not name or relative.is_absolute() or ".." in relative.parts
            or relative.as_posix() != name):
        raise ValueError(f"unsafe artifact file name: {name!r}")
    target = root / relative
    if not target.is_file() or target.is_symlink():
        raise ValueError(f"missing or symlinked artifact file: {name}")
    return target


def verified_hashes(root: Path, expected: dict) -> None:
    if not isinstance(expected, dict) or not expected:
        raise ValueError("empty artifact digest map")
    for name, sha256 in expected.items():
        if not isinstance(name, str) or not isinstance(sha256, str) or not SHA256.fullmatch(sha256):
            raise ValueError(f"invalid artifact digest: {name!r}")
        if digest(safe_file(root, name)) != sha256:
            raise ValueError(f"artifact digest mismatch: {name}")


def prepare_rust_site(site: Path) -> None:
    revision, _ = repo_identity()
    if not SHA1.fullmatch(revision) or site.exists():
        raise ValueError("Rust standalone site must be new and use a full commit SHA")
    expected = catalog()
    site.mkdir(parents=True)
    # This is packaging metadata only: the Rust builder still checks the pinned
    # upstream Git revision and never treats an unbuilt candidate as verified.
    manifest = {
        "upstream": expected["upstream"],
        "moonbit": expected["moonbit"],
        "lab_revision": revision,
        "lab_tracked_dirty": False,
        "rust_bundled": False,
        "standalone_rust_site": True,
        "comparison_status": "unverified",
    }
    (site / "build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def merge_sites(moonbit_site: Path, rust_site: Path, evidence: Path) -> None:
    revision, tree = repo_identity()
    expected = catalog()
    moon = read_manifest(moonbit_site)
    rust = read_manifest(rust_site)
    pinned(moon, expected, revision)
    pinned(rust, expected, revision)
    if rust.get("lab_tree") != tree or not SHA1.fullmatch(tree):
        raise ValueError("Rust artifact lab tree differs from the checked-out source tree")
    if rust.get("standalone_rust_site") is not True or rust.get("rust_bundled") is not True:
        raise ValueError("Rust artifact was not independently built")
    if moon.get("rust_bundled") is not False or (moonbit_site / "rust").exists():
        raise ValueError("MoonBit artifact already includes Rust")
    if moon.get("moonbit_unit_tests") != "passed" or moon.get("comparison_status") != "unverified":
        raise ValueError("MoonBit tests or comparison provenance are unexpected")
    if rust.get("comparison_status") != "unverified":
        raise ValueError("standalone Rust artifact must not claim browser validation")
    examples = [entry["id"] for entry in expected["examples"] if entry.get("moonbit") == "implemented"]
    if moon.get("implemented") != examples or rust.get("rust_implemented") != examples:
        raise ValueError("compiled runtime lists do not match the pinned catalog")
    if rust.get("rust_oracle_only") != [] or rust.get("rust_subset_sources") != []:
        raise ValueError("unexpected additional Rust sources in the matched pair")

    runtimes = moon.get("runtime_sha256_by_example")
    if not isinstance(runtimes, dict) or set(runtimes) != set(examples):
        raise ValueError("candidate runtime digest list is incomplete")
    verified_hashes(moonbit_site, {f"moonbit/{'runtime' if name == 'hello_world' else name}.mjs": sha
                                    for name, sha in runtimes.items()})
    verified_hashes(moonbit_site, moon.get("moonbit_host_files_sha256"))
    fonts = moon.get("font_sha256_by_file")
    if not isinstance(fonts, dict) or not {"IBMPlexSans-Regular.ttf", "IBMPlexSans-Italic.ttf",
                                          "IBMPlexSans-SemiBold.ttf"} <= set(fonts):
        raise ValueError("candidate font provenance is incomplete")
    verified_hashes(moonbit_site, {f"moonbit/{name}": sha for name, sha in fonts.items()})

    rust_provenance = rust.get("rust")
    if not isinstance(rust_provenance, dict) or rust_provenance.get("source_modified") is not False:
        raise ValueError("Rust bundle lacks clean-source provenance")
    if rust_provenance.get("source_revision") != expected["upstream"]["revision"] or not SHA1.fullmatch(rust_provenance.get("source_tree", "")):
        raise ValueError("Rust upstream source identity is not pinned")
    rust_root = rust_site / "rust"
    rust_files = rust_provenance.get("files")
    verified_hashes(rust_root, rust_files)
    actual = {str(path.relative_to(rust_root)) for path in rust_root.rglob("*") if path.is_file()}
    if actual != set(rust_files):
        raise ValueError("Rust bundle has unrecorded or missing files")
    if (moonbit_site / "_headers").exists() or safe_file(rust_site, "_headers").read_bytes() != (WEB / "_headers").read_bytes():
        raise ValueError("invalid Rust site security headers")
    # No input artifacts are trusted solely by name: validate their content,
    # immutable source identities, and exact Git tree before attaching them.
    shutil.copytree(rust_root, moonbit_site / "rust")
    shutil.copy2(rust_site / "_headers", moonbit_site / "_headers")
    for field in ("lab_tree", "rust_bundled", "rust_implemented",
                  "rust_oracle_only", "rust_subset_sources", "rust"):
        moon[field] = rust[field]
    (moonbit_site / "build-manifest.json").write_text(json.dumps(moon, indent=2) + "\n")
    log = rust_site / "rust-build.log"
    if log.is_file():
        evidence.mkdir(parents=True, exist_ok=True)
        shutil.copy2(log, evidence / "rust-build.log")
    print(f"Verified and assembled {len(examples)} pinned Rust/MoonBit runtime pairs at {revision}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("prepare-rust", "merge"))
    parser.add_argument("--rust-site", type=Path, required=True)
    parser.add_argument("--moonbit-site", type=Path, default=Path("_build/browser-lab"))
    parser.add_argument("--evidence", type=Path, default=Path("_build/browser-example-evidence"))
    args = parser.parse_args()
    try:
        if args.operation == "prepare-rust":
            prepare_rust_site(args.rust_site)
        else:
            merge_sites(args.moonbit_site, args.rust_site, args.evidence)
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"browser artifact assembly failed: {error}\n")
