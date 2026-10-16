#!/usr/bin/env python3
"""Compile the pinned, unchanged upstream examples in a disposable archive."""
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
from build_moonbit import WEB, check_source, run

TOOLCHAIN = "nightly-2026-10-14"
GALLERY = Path("crates/gpui_web/examples/hello_web")


def build(upstream: Path, site: Path, target: Path) -> None:
    catalog = json.loads((WEB / "examples.json").read_text())
    check_source(upstream, catalog["upstream"]["revision"])
    manifest_path = site / "build-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest["upstream"] != catalog["upstream"] or (site / "rust").exists():
        raise ValueError("site provenance mismatch or Rust output already exists")
    with tempfile.TemporaryDirectory(prefix="gpui-rust-", dir=site.parent) as work:
        source = Path(work) / "source"
        source.mkdir()
        archive = subprocess.run(["git", "archive", "HEAD"], cwd=upstream,
                                 check=True, stdout=subprocess.PIPE).stdout
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(source, filter="data")
        gallery = source / GALLERY
        shutil.copy2(WEB / "rust/Cargo.lock", gallery / "Cargo.lock")
        examples = [example["id"] for example in catalog["examples"] if example.get("moonbit") == "implemented"]
        command = ["cargo", f"+{TOOLCHAIN}", "build", "--locked", "--release",
                   "--config", "profile.release.codegen-units=1", "--target",
                   "wasm32-unknown-unknown", *[arg for name in examples for arg in ("--bin", name)], "--target-dir", str(target)]
        run(command, gallery)
        rust = Path(work) / "rust"
        rust.mkdir()
        for name in examples:
            wasm = target / f"wasm32-unknown-unknown/release/{name}.wasm"
            run(["wasm-bindgen", "--target", "web", "--out-dir", str(rust),
                 "--out-name", name, str(wasm)], gallery)
        shutil.copytree(WEB / "rust", rust, dirs_exist_ok=True)
        shutil.copy2(gallery / "Cargo.lock", rust / "Cargo.lock")
        # Font and source licenses travel with the binary that embeds these fonts.
        shutil.copy2(source / "LICENSE-APACHE", rust / "LICENSE-APACHE")
        for family, license_name in [("ibm-plex-sans", "license.txt"), ("lilex", "OFL.txt")]:
            shutil.copy2(source / "assets/fonts" / family / license_name, rust / f"{family}-license.txt")
        check_source(upstream, catalog["upstream"]["revision"])
        manifest["rust_bundled"] = True
        manifest["rust_implemented"] = examples
        manifest["rust"] = {
            "toolchain": run(["rustc", f"+{TOOLCHAIN}", "--version"], gallery, True),
            "bindings": run(["wasm-bindgen", "--version"], gallery, True),
            "command": command[:-1] + ["<target-dir>"],
            "source_modified": False,
            "files": {str(p.relative_to(rust)): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in sorted(rust.rglob("*")) if p.is_file()},
        }
        shutil.copytree(rust, site / "rust")
        shutil.copy2(WEB / "_headers", site / "_headers")
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Bundled real upstream WASM in {site}; browser comparison still requires execution")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream-source", required=True, type=Path)
    parser.add_argument("--site", type=Path, default=Path("_build/browser-lab"))
    parser.add_argument("--target-dir", type=Path, default=Path("_build/rust-target"))
    args = parser.parse_args()
    try:
        build(args.upstream_source.resolve(), args.site.resolve(), args.target_dir.resolve())
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"upstream WASM build failed: {error}\n")
