#!/usr/bin/env python3
"""Pin, attest, and join independent full Browser Lab builds before comparison."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess

ROOT = Path(__file__).resolve().parents[2]
ROOT_FILES = ("index.html", "style.css", "app.js", "routing.mjs", "load-timing.mjs",
              "load-comparison.mjs", "examples.json")
FONT_FILES = ("IBMPlexSans-Regular.ttf", "IBMPlexSans-Italic.ttf", "IBMPlexSans-SemiBold.ttf")
MOONBIT_FONTS = (*FONT_FILES, "font-license.txt", "Lilex-Regular.ttf", "Lilex-license.txt")
RUST_FIELDS = ("lab_tree", "rust_bundled", "rust_implemented", "rust_oracle_only",
               "rust_subset_sources", "rust")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest(value: str, length: int, label: str) -> None:
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{" + str(length) + "}", value),
            f"invalid {label}: requires {length} lowercase hexadecimal characters")


def relative(value: str) -> str:
    require(isinstance(value, str) and value and "\\" not in value,
            "invalid artifact relative path")
    path = PurePosixPath(value)
    require(not path.is_absolute() and ".." not in path.parts and str(path) == value
            and value != ".", f"unsafe artifact path: {value}")
    return value


def no_symlinks(path: Path) -> None:
    for part in (path, *path.parents):
        require(not part.is_symlink(), f"symlink is not an artifact input: {part}")


def sha256(path: Path) -> str:
    no_symlinks(path)
    require(stat.S_ISREG(path.stat().st_mode), f"expected regular file: {path}")
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def files(directory: Path) -> dict[str, str]:
    no_symlinks(directory)
    require(directory.is_dir(), f"expected directory: {directory}")
    result = {}
    for path in sorted(directory.rglob("*")):
        require(not path.is_symlink(), f"artifact contains symlink: {path}")
        if not path.is_dir():
            result[relative(path.relative_to(directory).as_posix())] = sha256(path)
    return result


def unique_object(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON field: {key}")
        result[key] = value
    return result


def read_json(path: Path) -> dict:
    no_symlinks(path)
    value = json.loads(path.read_bytes(), object_pairs_hook=unique_object)
    require(isinstance(value, dict), f"expected JSON object: {path}")
    return value


def write_json(path: Path, value: dict) -> None:
    no_symlinks(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def git(*arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], cwd=ROOT, text=True).strip()


def github() -> dict | None:
    values = {key: os.environ.get("GITHUB_" + key.upper(), "")
              for key in ("run_id", "run_attempt", "repository")}
    if not any(values.values()):
        return None
    require(all(values.values()) and all(re.fullmatch(r"[1-9][0-9]*", values[key])
            for key in ("run_id", "run_attempt")), "incomplete GitHub run identity")
    return values


def current_inputs(run: dict | None) -> dict:
    require(not git("status", "--porcelain", "--untracked-files=no"), "tracked lab source is dirty")
    # Dependency checkouts live outside web; untracked build sources can affect copying.
    require(not git("ls-files", "--others", "--exclude-standard", "--", "web"),
            "untracked lab source under web")
    revision, tree = git("rev-parse", "HEAD"), git("rev-parse", "HEAD^{tree}")
    digest(revision, 40, "lab revision")
    digest(tree, 40, "lab tree")
    catalog = read_json(ROOT / "web/examples.json")
    require(catalog.get("schema_version") == 1, "unsupported example catalog schema")
    for role, repository in (("upstream", "zed-industries/zed"), ("moonbit", "gpui-mbt/gpui.mbt")):
        require(catalog[role].get("repository") == repository, f"unexpected {role} repository")
        digest(catalog[role].get("revision"), 40, role + " revision")
    digest(catalog["moonbit"].get("tree"), 40, "MoonBit tree")
    digest(catalog["upstream"].get("hello_world_blob"), 40, "hello_world source blob")
    names, sources, candidates = [], {}, {}
    for entry in catalog["examples"]:
        name = entry["id"]
        require(isinstance(name, str) and re.fullmatch(r"[a-z][a-z0-9_]*", name)
                and name not in names, "invalid or duplicate example id")
        names.append(name)
        if entry.get("moonbit") != "implemented":
            continue
        blob = entry.get("source_blob", catalog["upstream"]["hello_world_blob"] if name == "hello_world" else None)
        digest(blob, 40, name + " source blob")
        if name == "hello_world":
            require(blob == catalog["upstream"]["hello_world_blob"], "conflicting hello_world source blobs")
        sources[name] = {"source": relative(entry["source"]), "source_blob": blob}
        candidate = relative(entry["candidate_source"])
        require(candidate.startswith(f"web/moonbit/{name}/"), f"unexpected candidate source for {name}")
        candidate_blob = git("rev-parse", f"HEAD:{candidate}")
        digest(candidate_blob, 40, name + " candidate blob")
        candidates[name] = {"source": candidate, "source_blob": candidate_blob,
                            "sha256": sha256(ROOT / candidate)}
    require("hello_world" in sources, "full Browser Lab build requires hello_world")
    return {"schema_version": 1, "lab": {"revision": revision, "tree": tree},
            "upstream": catalog["upstream"], "moonbit": catalog["moonbit"],
            "implemented": list(sources), "implemented_sources": sources,
            "candidate_sources": candidates,
            "catalog_sha256": sha256(ROOT / "web/examples.json"),
            "cargo_lock_sha256": sha256(ROOT / "web/rust/Cargo.lock"), "github": run}


def pin(out: Path) -> dict:
    require(not out.exists(), f"pin output already exists: {out}")
    inputs = current_inputs(github())
    write_json(out, inputs)
    if os.environ.get("GITHUB_OUTPUT"):
        with Path(os.environ["GITHUB_OUTPUT"]).open("a") as stream:
            for name, value in {"lab": inputs["lab"]["revision"], "gpui": inputs["moonbit"]["revision"],
                                "zed": inputs["upstream"]["revision"], "inputs_sha256": sha256(out)}.items():
                stream.write(f"{name}={value}\n")
    return inputs


def verify_inputs(path: Path, expected: str) -> dict:
    digest(expected, 64, "trusted input SHA256")
    require(sha256(path) == expected, "build inputs SHA256 mismatch")
    inputs = read_json(path)
    pinned_run, current_run = inputs.get("github"), github()
    if pinned_run is not None:
        require(isinstance(pinned_run, dict) and set(pinned_run) == {"run_id", "run_attempt", "repository"}
                and all(isinstance(pinned_run[key], str) and re.fullmatch(r"[1-9][0-9]*", pinned_run[key])
                        for key in ("run_id", "run_attempt")), "invalid pinned GitHub run identity")
    require((pinned_run is None and current_run is None) or
            (pinned_run is not None and current_run is not None and
             all(pinned_run[key] == current_run[key] for key in ("run_id", "repository"))),
            "build inputs belong to a different GitHub run")
    # A failed-job rerun can reuse a successful build from an earlier attempt.
    require(inputs == current_inputs(pinned_run), "pinned inputs differ from the clean lab checkout")
    return inputs


def rust_seed(inputs: dict) -> dict:
    return {"site_kind": "browser_lab_rust_build", "build_role": "rust",
            "upstream": inputs["upstream"], "moonbit": inputs["moonbit"],
            "lab_revision": inputs["lab"]["revision"], "lab_tree": inputs["lab"]["tree"],
            "lab_tracked_dirty": False, "implemented": [], "rust_bundled": False,
            "comparison_status": "unverified"}


def fresh(path: Path) -> None:
    no_symlinks(path)
    require(not path.exists(), f"output already exists: {path}")
    path.mkdir(parents=True)


def seed_rust(inputs_path: Path, expected: str, site: Path) -> None:
    inputs = verify_inputs(inputs_path, expected)
    fresh(site)
    shutil.copy2(ROOT / "web/examples.json", site / "examples.json")
    write_json(site / "build-manifest.json", rust_seed(inputs))


def match_hashes(recorded: dict, actual: dict, label: str) -> None:
    require(isinstance(recorded, dict), f"missing {label} file hashes")
    for name, value in recorded.items():
        relative(name)
        digest(value, 64, label + " hash")
    require(recorded == actual, f"{label} file set or SHA256 mismatch")


def validate_site(site: Path, kind: str, inputs: dict) -> tuple[dict, dict]:
    hashes = files(site)
    manifest = read_json(site / "build-manifest.json")
    require(hashes.get("examples.json") == inputs["catalog_sha256"], "shipped catalog differs from pinned inputs")
    for role in ("upstream", "moonbit"):
        require(manifest.get(role) == inputs[role], role + " manifest pin mismatch")
    require(manifest.get("lab_revision") == inputs["lab"]["revision"] and
            manifest.get("lab_tracked_dirty") is False, "manifest lab revision or cleanliness mismatch")
    require(manifest.get("comparison_status") == "unverified", "artifact cannot claim a browser comparison")
    if "lab_tree" in manifest:
        require(manifest["lab_tree"] == inputs["lab"]["tree"], "manifest lab tree mismatch")
    if kind == "moonbit":
        require(manifest.get("rust_bundled") is False and "rust" not in manifest and "site_kind" not in manifest,
                "MoonBit artifact has the wrong build role")
        require(manifest.get("implemented") == inputs["implemented"] and
                manifest.get("implemented_sources") == inputs["implemented_sources"], "incomplete MoonBit sources")
        require(manifest.get("moonbit_unit_tests") == "passed" and isinstance(manifest.get("compiler"), str)
                and bool(manifest["compiler"].strip()), "missing MoonBit compiler or unit-test evidence")
        hosts = {"moonbit/" + name: value for name, value in files(ROOT / "web/moonbit/site").items()}
        static = {name: sha256(ROOT / "web" / name) for name in ROOT_FILES} | hosts
        for name, value in static.items():
            require(hashes.get(name) == value, f"shipped MoonBit/static source differs: {name}")
        host_map = {name: value for name, value in static.items()
                    if name == "load-timing.mjs" or name.startswith("moonbit/") and name.endswith(".mjs")}
        match_hashes(manifest.get("moonbit_host_files_sha256"), host_map, "MoonBit host")
        runtime_paths = {name: "moonbit/" + ("runtime.mjs" if name == "hello_world" else name + ".mjs")
                         for name in inputs["implemented"]}
        match_hashes(manifest.get("runtime_sha256_by_example"),
                     {name: hashes.get(path) for name, path in runtime_paths.items()}, "MoonBit runtime")
        require(manifest.get("runtime_sha256") == hashes.get("moonbit/runtime.mjs"), "hello_world runtime SHA256 mismatch")
        font_hashes = {name: hashes.get("moonbit/" + name) for name in FONT_FILES}
        match_hashes(manifest.get("font_sha256_by_file"), font_hashes, "MoonBit font")
        require(manifest.get("font_sha256") == font_hashes[FONT_FILES[0]], "default font SHA256 mismatch")
        expected_files = set(static) | set(runtime_paths.values()) | {"moonbit/" + name for name in MOONBIT_FONTS}
        require(set(hashes) == expected_files | {"build-manifest.json"}, "unexpected or missing MoonBit site files")
    else:
        seed = rust_seed(inputs)
        require(set(manifest) == set(seed) | set(RUST_FIELDS), "unexpected Rust manifest fields or wrong build role")
        for key, value in seed.items():
            if key != "rust_bundled":
                require(manifest.get(key) == value, f"Rust seed changed: {key}")
        rust = manifest.get("rust")
        require(isinstance(rust, dict) and manifest.get("rust_bundled") is True and
                manifest.get("rust_implemented") == inputs["implemented"] and
                manifest.get("rust_oracle_only") == [] and manifest.get("rust_subset_sources") == [],
                "incomplete Rust build or unexpected oracle/subset")
        require(rust.get("source_revision") == inputs["upstream"]["revision"] and rust.get("source_modified") is False
                and rust.get("oracle_only") is False and rust.get("implemented_subset") is None,
                "Rust source identity or build scope mismatch")
        digest(rust.get("source_tree"), 40, "Rust source tree")
        require(rust.get("packaging", {}).get("upstream_files_modified") is False,
                "Rust packaging changed upstream sources")
        require(all(isinstance(rust.get(key), str) and rust[key].strip() for key in ("toolchain", "bindings")),
                "missing Rust compiler or binding generator evidence")
        command = rust.get("command")
        require(isinstance(command, list) and all(isinstance(part, str) for part in command)
                and "--locked" in command and
                [part for index, part in enumerate(command) if index and command[index - 1] == "--bin"] == inputs["implemented"],
                "Rust command does not build the complete pinned set with --locked")
        rust_files = files(site / "rust")
        match_hashes(rust.get("files"), rust_files, "Rust")
        static_rust = files(ROOT / "web/rust")
        for name, value in static_rust.items():
            require(rust_files.get(name) == value, f"shipped Rust source differs: {name}")
        require(rust_files.get("Cargo.lock") == inputs["cargo_lock_sha256"], "shipped Cargo.lock differs")
        for name in inputs["implemented"]:
            require(all(path in rust_files for path in (name + ".js", name + "_bg.wasm")),
                    f"missing Rust compiled output: {name}")
        retained_pattern = retained_pattern_sources(rust, site, inputs)
        licenses = {"LICENSE-APACHE", "ibm-plex-sans-license.txt", "lilex-license.txt"}
        generated = {name + suffix for name in inputs["implemented"]
                     for suffix in (".js", "_bg.wasm", ".d.ts", "_bg.wasm.d.ts")}
        require(licenses <= set(rust_files) and set(rust_files) <= set(static_rust) | licenses | generated | retained_pattern |
                {name for name in rust_files if name.startswith("snippets/")}, "unexpected or missing Rust files")
        require(hashes.get("_headers") == sha256(ROOT / "web/_headers"), "isolation headers differ from pinned source")
        require(set(hashes) == {"examples.json", "build-manifest.json", "_headers"} |
                {"rust/" + name for name in rust_files}, "unexpected files in Rust-only site")
    return manifest, hashes


def attest(inputs_path: Path, expected: str, kind: str, site: Path, out: Path) -> None:
    inputs = verify_inputs(inputs_path, expected)
    require(kind in ("moonbit", "rust"), "unknown build role")
    _, hashes = validate_site(site, kind, inputs)
    require(not out.absolute().is_relative_to(site.absolute()), "bundle output overlaps its site input")
    fresh(out)
    shutil.copytree(site, out / "site")
    match_hashes(hashes, files(out / "site"), "copied artifact")
    write_json(out / "provenance.json", {"schema_version": 1, "kind": kind, "inputs_sha256": expected,
               "inputs": inputs, "build_github": github(), "files": hashes,
               "comparison_status": "unverified"})


def validate_bundle(bundle: Path, kind: str, inputs: dict, expected: str) -> tuple[dict, dict]:
    no_symlinks(bundle)
    require({path.name for path in bundle.iterdir()} == {"site", "provenance.json"}, "unexpected bundle entries")
    provenance = read_json(bundle / "provenance.json")
    require(set(provenance) == {"schema_version", "kind", "inputs_sha256", "inputs", "build_github", "files", "comparison_status"}
            and provenance["schema_version"] == 1 and provenance["kind"] == kind and
            provenance["inputs_sha256"] == expected and provenance["inputs"] == inputs and
            provenance["comparison_status"] == "unverified", "artifact role or common input identity mismatch")
    built, pinned = provenance["build_github"], inputs["github"]
    require((built is None and pinned is None) or (isinstance(built, dict) and isinstance(pinned, dict)
            and set(built) == set(pinned) and all(built[key] == pinned[key] for key in ("run_id", "repository"))
            and isinstance(built.get("run_attempt"), str) and re.fullmatch(r"[1-9][0-9]*", built["run_attempt"])),
            "artifact was built in a different GitHub run")
    manifest, actual = validate_site(bundle / "site", kind, inputs)
    match_hashes(provenance["files"], actual, "artifact")
    return manifest, provenance


def retained_pattern_sources(rust: dict, site: Path, inputs: dict) -> set[str]:
    retained_pattern = set()
    if "pattern" in inputs["implemented"]:
        record = rust.get("pattern_source")
        require(isinstance(record, dict) and record.get("id") == "pattern" and
                record.get("source") == inputs["implemented_sources"]["pattern"]["source"] and
                record.get("source_blob") == inputs["implemented_sources"]["pattern"]["source_blob"] and
                record.get("retained_file") == "unchanged-source/pattern.rs", "missing or changed Rust pattern source provenance")
        source = site / "rust/unchanged-source/pattern.rs"
        no_symlinks(source)
        raw = source.read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        require(blob == record["source_blob"] and sha256(source) == record.get("source_sha256"),
                "retained unchanged pattern source identity mismatch")
        retained_pattern.add("unchanged-source/pattern.rs")
    return retained_pattern


def merge(inputs_path: Path, expected: str, moonbit: Path, rust: Path, out: Path, evidence: Path) -> None:
    inputs = verify_inputs(inputs_path, expected)
    moon_manifest, moon_provenance = validate_bundle(moonbit, "moonbit", inputs, expected)
    rust_manifest, rust_provenance = validate_bundle(rust, "rust", inputs, expected)
    for bundle in (moonbit, rust):
        require(not out.absolute().is_relative_to(bundle.absolute()), "merged output overlaps an input artifact")
    no_symlinks(out)
    require(not out.exists(), f"merged output already exists: {out}")
    evidence = evidence / "build-artifacts"
    fresh(evidence)
    shutil.copytree(moonbit / "site", out)
    shutil.copytree(rust / "site/rust", out / "rust")
    shutil.copy2(rust / "site/_headers", out / "_headers")
    manifest = moon_manifest | {key: rust_manifest[key] for key in RUST_FIELDS}
    manifest["comparison_status"] = "unverified"
    manifest["parallel_build"] = {"inputs_sha256": expected,
                                  "moonbit_provenance_sha256": sha256(moonbit / "provenance.json"),
                                  "rust_provenance_sha256": sha256(rust / "provenance.json"),
                                  "verification": "input-and-artifact-integrity-only"}
    write_json(out / "build-manifest.json", manifest)
    expected_files = moon_provenance["files"] | {name: value for name, value in rust_provenance["files"].items()
                                                if name.startswith("rust/") or name == "_headers"}
    expected_files["build-manifest.json"] = sha256(out / "build-manifest.json")
    match_hashes(expected_files, files(out), "merged site")
    shutil.copy2(inputs_path, evidence / "inputs.json")
    for kind, bundle in (("moonbit", moonbit), ("rust", rust)):
        shutil.copy2(bundle / "provenance.json", evidence / f"{kind}-provenance.json")
        shutil.copy2(bundle / "site/build-manifest.json", evidence / f"{kind}-build-manifest.json")
    shutil.copy2(out / "build-manifest.json", evidence / "merged-build-manifest.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("pin").add_argument("--out", type=Path, required=True)
    for name in ("verify-inputs", "seed-rust", "attest", "merge"):
        command = commands.add_parser(name)
        command.add_argument("--inputs", type=Path, required=True)
        command.add_argument("--sha256", required=True)
        if name in ("seed-rust", "attest"):
            command.add_argument("--site", type=Path, required=True)
        if name == "attest":
            command.add_argument("--kind", choices=("moonbit", "rust"), required=True)
        if name in ("attest", "merge"):
            command.add_argument("--out", type=Path, required=True)
        if name == "merge":
            command.add_argument("--moonbit", type=Path, required=True)
            command.add_argument("--rust", type=Path, required=True)
            command.add_argument("--evidence", type=Path, required=True)
    args = vars(parser.parse_args())
    command = args.pop("command")
    if "inputs" in args:
        args["inputs_path"] = args.pop("inputs")
        args["expected"] = args.pop("sha256")
    try:
        if command == "verify-inputs":
            verify_inputs(args["inputs_path"], args["expected"])
        else:
            {"pin": pin, "seed-rust": seed_rust, "attest": attest, "merge": merge}[command](**args)
    except (ValueError, OSError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"browser build artifacts {command} failed: {error}\n")
    print(f"browser build artifacts {command}: completed; comparison remains unverified")


if __name__ == "__main__":
    main()
