#!/usr/bin/env python3
"""Compile the pinned, unchanged upstream examples in a disposable archive."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
from build_moonbit import WEB, check_source, run

TOOLCHAIN = "nightly-2026-10-14"
GALLERY = Path("crates/gpui_web/examples/hello_web")


def prepare_gallery(source: Path, gallery: Path, examples: list[str]) -> dict:
    """Register additional unchanged examples outside the upstream source tree."""
    original = source / GALLERY
    manifest = (original / "Cargo.toml").read_text()
    gallery.mkdir()
    # Relocate the upstream standalone package, retaining all dependency and
    # binary source paths. This avoids patching any archived upstream file.
    def relocate(match: re.Match) -> str:
        target = (original / match[1]).resolve()
        target.relative_to(source)
        return 'path = "' + os.path.relpath(target, gallery) + '"'
    manifest = re.sub(r'path = "([^"]+)"', relocate, manifest)
    additional_bins = []
    for name in ["tree", "scrollable", "focus_visible", "tab_stop"]:
        if name in examples:
            relative = f"crates/gpui/examples/{name}.rs"
            path = os.path.relpath(source / relative, gallery)
            manifest += f'\n[[bin]]\nname = "{name}"\npath = "{path}"\n'
            additional_bins.append({"name": name, "source": relative})
    (gallery / "Cargo.toml").write_text(manifest)
    shutil.copytree(original / ".cargo", gallery / ".cargo")
    shutil.copy2(WEB / "rust/Cargo.lock", gallery / "Cargo.lock")
    return {"kind": "relocated standalone upstream package",
            "original_manifest": str(GALLERY / "Cargo.toml"),
            "additional_bins": additional_bins,
            "manifest_sha256": hashlib.sha256(manifest.encode()).hexdigest(),
            "upstream_files_modified": False}


def extra_oracle_records(names: list[str]) -> list[dict]:
    """Opt-in unchanged Rust baselines never imply a candidate implementation."""
    records = []
    for name in names:
        if name not in {"scrollable", "focus_visible", "tab_stop"} or name in [record["id"] for record in records]:
            raise ValueError(f"unknown or duplicate extra oracle: {name}")
        record = json.loads((WEB / "oracles" / f"{name}.json").read_text())
        if (record["id"] != name or record["source"] != f"crates/gpui/examples/{name}.rs"
                or record["status"] != "rust_oracle_only" or record["candidate"] != "not_implemented"):
            raise ValueError(f"invalid source identity for extra oracle: {name}")
        records.append(record)
    return records


def selected_examples(catalog: dict, records: list[dict], oracle_only: bool = False,
                      implemented_examples: list[str] | None = None) -> list[str]:
    if implemented_examples is not None:
        if oracle_only or records:
            raise ValueError("--implemented-example cannot be combined with --oracle-only or --extra-example")
        if not implemented_examples or len(set(implemented_examples)) != len(implemented_examples):
            raise ValueError("implemented subset must be nonempty with no duplicate examples")
        implemented = {example["id"] for example in catalog["examples"]
                       if example.get("moonbit") == "implemented"}
        for name in implemented_examples:
            if name not in implemented:
                raise ValueError(f"unknown or unimplemented subset example: {name}")
        return list(implemented_examples)
    if oracle_only and not records:
        raise ValueError("--oracle-only requires at least one recognized --extra-example")
    examples = [] if oracle_only else [example["id"] for example in catalog["examples"]
                                      if example.get("moonbit") == "implemented"]
    for record in records:
        if any(example["id"] == record["id"] and example.get("moonbit") == "implemented"
               for example in catalog["examples"]):
            raise ValueError(f"extra oracle already has an implemented catalog entry: {record['id']}")
        examples.append(record["id"])
    return examples


def build(upstream: Path, site: Path, target: Path, extra_examples: list[str] | None = None,
          oracle_only: bool = False, implemented_examples: list[str] | None = None) -> None:
    catalog = json.loads((WEB / "examples.json").read_text())
    check_source(upstream, catalog["upstream"]["revision"])
    oracle_records = extra_oracle_records(extra_examples or [])
    examples = selected_examples(catalog, oracle_records, oracle_only, implemented_examples)
    for record in oracle_records:
        if record["upstream_revision"] != catalog["upstream"]["revision"]:
            raise ValueError(f"extra oracle revision mismatch: {record['id']}")
        if run(["git", "rev-parse", f"HEAD:{record['source']}"], upstream, True) != record["source_blob"]:
            raise ValueError(f"extra oracle source blob mismatch: {record['id']}")
        if record.get("source_sha256") and hashlib.sha256((upstream / record["source"]).read_bytes()).hexdigest() != record["source_sha256"]:
            raise ValueError(f"extra oracle source SHA256 mismatch: {record['id']}")
    subset_records = []
    if implemented_examples is not None:
        entries = {example["id"]: example for example in catalog["examples"]}
        for name in examples:
            entry = entries[name]
            expected_blob = entry.get("source_blob", catalog["upstream"].get("hello_world_blob") if name == "hello_world" else None)
            if not expected_blob or run(["git", "rev-parse", f"HEAD:{entry['source']}"], upstream, True) != expected_blob:
                raise ValueError(f"implemented subset source blob mismatch: {name}")
            subset_records.append({"id": name, "source": entry["source"], "source_blob": expected_blob,
                                   "source_sha256": hashlib.sha256((upstream / entry["source"]).read_bytes()).hexdigest(),
                                   "upstream_revision": catalog["upstream"]["revision"],
                                   "status": "implemented_subset", "candidate": "implemented"})
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
        gallery = Path(work) / "gallery"
        packaging = prepare_gallery(source, gallery, examples)
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
        embedded_fonts = {}
        if oracle_only or implemented_examples is not None:
            shutil.copy2(gallery / "Cargo.toml", rust / "packaging-Cargo.toml")
            for family, names in {
                "ibm-plex-sans": ["IBMPlexSans-Regular.ttf", "IBMPlexSans-Italic.ttf", "IBMPlexSans-SemiBold.ttf", "IBMPlexSans-SemiBoldItalic.ttf"],
                "lilex": ["Lilex-Regular.ttf", "Lilex-Bold.ttf", "Lilex-Italic.ttf", "Lilex-BoldItalic.ttf"],
            }.items():
                for name in names:
                    relative = f"assets/fonts/{family}/{name}"
                    output = rust / "embedded-font-inputs" / name
                    output.parent.mkdir(exist_ok=True)
                    shutil.copy2(source / relative, output)
                    embedded_fonts[relative] = {"file": str(output.relative_to(rust)),
                                                "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}
            for record in [*oracle_records, *subset_records]:
                output = rust / "unchanged-source" / (record["id"] + ".rs")
                output.parent.mkdir(exist_ok=True)
                shutil.copy2(source / record["source"], output)
        check_source(upstream, catalog["upstream"]["revision"])
        manifest["lab_tree"] = run(["git", "rev-parse", "HEAD^{tree}"], WEB.parent, True)
        manifest["rust_bundled"] = True
        manifest["rust_implemented"] = examples
        manifest["rust_oracle_only"] = oracle_records
        manifest["rust_subset_sources"] = subset_records
        manifest["rust"] = {
            "toolchain": run(["rustc", f"+{TOOLCHAIN}", "--version"], gallery, True),
            "bindings": run(["wasm-bindgen", "--version"], gallery, True),
            "command": command[:-1] + ["<target-dir>"],
            "source_modified": False,
            "oracle_only": oracle_only,
            "implemented_subset": list(implemented_examples) if implemented_examples is not None else None,
            "build_completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "embedded_fonts": embedded_fonts,
            "packaging": packaging,
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
    parser.add_argument("--extra-example", action="append", choices=["scrollable", "focus_visible", "tab_stop"], default=[],
                        help="also build an unchanged Rust-only oracle without claiming a MoonBit counterpart")
    parser.add_argument("--oracle-only", action="store_true",
                        help="build only explicitly named Rust-only oracles; requires --extra-example")
    parser.add_argument("--implemented-example", action="append", default=None,
                        help="build only explicitly named implemented examples; incompatible with extra/oracle flags")
    args = parser.parse_args()
    try:
        build(args.upstream_source.resolve(), args.site.resolve(), args.target_dir.resolve(), args.extra_example, args.oracle_only, args.implemented_example)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"upstream WASM build failed: {error}\n")
