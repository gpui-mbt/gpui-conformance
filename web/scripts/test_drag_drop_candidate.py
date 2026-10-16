#!/usr/bin/env python3
"""Retain bounded local candidate tests against an exact, clean core commit.

This deliberately does not emit a site build-manifest or change catalog pins.
Its output is source/model testing, not browser or unchanged-Rust evidence.
"""
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

WEB = Path(__file__).resolve().parents[1]
PACKAGE = "examples/conformance_drag_drop"


def command(args: list[str], cwd: Path) -> str:
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_logged(args: list[str], cwd: Path, log: Path) -> tuple[int, str]:
    result = subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    log.write_text(result.stdout)
    print(result.stdout, end="")
    return result.returncode, result.stdout


def one_replace(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise ValueError(f"mutation requires exactly one source anchor: {old!r}")
    return source.replace(old, new, 1)


def behavioral_mutants(source: str) -> dict[str, str]:
    return {
        "preview_payload_delivered_instead_of_original": one_replace(one_replace(source,
            "  match state.session.dispatch(tree, event, current_sources, current_targets) {",
            "  let preview_copy = preview_value(state)\n  match state.session.dispatch(tree, event, current_sources, current_targets) {"),
            "state.drop_on = Some(payload)", "state.drop_on = preview_copy"),
        "target_updated_on_activation": one_replace(source,
            '@element.Activated => "activated"',
            '@element.Activated => { state.drop_on = preview_value(state); "activated" }'),
        "active_hover_leaked": one_replace(source,
            "if active(state) {\n    return false\n  }", "if false {\n    return false\n  }"),
        "preview_half_alpha_rounded_to_byte": one_replace(source,
            "              0.5,\n              None,", "              128.0 / 255.0,\n              None,"),
        "green_uses_wrong_rgb": one_replace(source,
            "color(0, 128, 0)", "color(0, 255, 0)"),
        "signed_preview_snaps_combined": one_replace(source,
            "snap(position.x() - value.position.x(), scale) +\n    snap(value.position.x() - 60, scale)",
            "snap(position.x() - 60, scale)"),
        "preview_uses_down_offset": one_replace(source,
            "@element.Active(cursor_offset~, payload~, ..) =>",
            "@element.Active(source~, origin~, payload~, ..) =>")
            .replace("position: cursor_offset,", "position: point(origin.x() - state.tree.unwrap().node(source).unwrap().bounds().left(), origin.y() - state.tree.unwrap().node(source).unwrap().bounds().top()),", 1),
        "raw_input_replaced_with_fake_event": one_replace(source,
            "state.session.dispatch(tree, event, current_sources, current_targets)",
            "state.session.dispatch(tree, @primitives.PointerMoved(position=point(0, 0)), current_sources, current_targets)"),
    }


def test_candidate(core: Path, revision: str, tree: str, out: Path, mutations: bool) -> None:
    if out.exists():
        raise ValueError(f"refusing to overwrite retained tests: {out}")
    for value in (revision, tree):
        if not re.fullmatch(r"[0-9a-f]{40}", value):
            raise ValueError("exact 40-character core commit and tree are required")
    if command(["git", "rev-parse", "HEAD"], core) != revision:
        raise ValueError("core commit mismatch")
    if command(["git", "rev-parse", "HEAD^{tree}"], core) != tree:
        raise ValueError("core tree mismatch")
    if command(["git", "status", "--porcelain", "--untracked-files=no"], core):
        raise ValueError("tracked core source is dirty")
    out.mkdir(parents=True)
    archive = subprocess.check_output(["git", "archive", "HEAD"], cwd=core)
    (out / "core-source.tar").write_bytes(archive)
    work = out / "core"
    work.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(work, filter="data")
    core_hashes = {str(path.relative_to(work)): digest(path)
                   for path in sorted(work.rglob("*"))
                   if path.is_file() and (path.suffix == ".mbt" or path.name in {"moon.pkg", "moon.mod"})}
    candidate = work / PACKAGE
    shutil.copytree(WEB / "moonbit/drag_drop", candidate)
    original = (candidate / "drag_drop.mbt").read_text()
    retained_inputs = out / "inputs/web"
    input_paths = ["moonbit/site/host.mjs", "moonbit/site/drag-drop-host.mjs",
                   "tests/drag-drop-compiled.test.mjs", "tests/drag-drop-host.test.mjs",
                   "scripts/test_drag_drop_candidate.py"]
    for relative in input_paths:
        target = retained_inputs / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(WEB / relative, target)
    report = {
        "schema": "drag_drop_local_model_tests_v1", "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "evidence_kind": "local compiled candidate/model contracts; not browser or Rust evidence",
        "core": {"revision": revision, "tree": tree, "archive_sha256": digest(out / "core-source.tar"),
                 "source_sha256": core_hashes},
        "suite": {"revision": command(["git", "rev-parse", "HEAD"], WEB.parent),
                  "tree": command(["git", "rev-parse", "HEAD^{tree}"], WEB.parent),
                  "status": command(["git", "status", "--porcelain"], WEB.parent)},
        "candidate_source_sha256": {str(path.relative_to(WEB)): digest(path)
                                    for path in sorted((WEB / "moonbit/drag_drop").rglob("*")) if path.is_file()},
        "test_input_sha256": {relative: digest(retained_inputs / relative) for relative in input_paths},
        "compiler": command(["moon", "version", "--all"], work),
        "baseline": {}, "behavioral_mutations": {}, "compiler_rejection_controls": {},
    }
    report_path = out / "local-test-report.json"
    def save() -> None:
        report_path.write_text(json.dumps(report, indent=2) + "\n")
    save()
    for stage, args in [("check", ["moon", "check", PACKAGE, "--target", "js"]),
                        ("test", ["moon", "test", PACKAGE, "--target", "js"]),
                        ("release_build", ["moon", "build", PACKAGE, "--target", "js", "--release"])]:
        code, _ = run_logged(args, work, out / f"baseline-{stage}.log")
        report["baseline"][stage] = "passed" if code == 0 else "failed"
        save()
        if code:
            raise ValueError(f"candidate baseline {stage} failed; retained at {out}")
    runtime = work / "_build/js/release/build" / PACKAGE / "conformance_drag_drop.js"
    shutil.copy2(runtime, out / "drag_drop.mjs")
    report["runtime_sha256"] = digest(out / "drag_drop.mjs")
    os.environ["DRAG_DROP_RUNTIME"] = str(out / "drag_drop.mjs")
    code, _ = run_logged(["node", "--test", str(retained_inputs / "tests/drag-drop-compiled.test.mjs"),
                          str(retained_inputs / "tests/drag-drop-host.test.mjs")], WEB.parent, out / "compiled-host-tests.log")
    report["baseline"]["compiled_host"] = "passed" if code == 0 else "failed"
    save()
    if code:
        raise ValueError("compiled host tests failed")
    if mutations:
        for name, mutated in behavioral_mutants(original).items():
            folder = out / "behavioral-mutations" / name
            folder.mkdir(parents=True)
            (folder / "drag_drop.mbt").write_text(mutated)
            (candidate / "drag_drop.mbt").write_text(mutated)
            check, _ = run_logged(["moon", "check", PACKAGE, "--target", "js"], work, folder / "check.log")
            code, output = run_logged(["moon", "test", PACKAGE, "--target", "js"], work, folder / "test.log") if not check else (-1, "")
            rejected = check == 0 and code != 0 and re.search(r"failed: [1-9][0-9]*", output) is not None
            report["behavioral_mutations"][name] = {"compiled": check == 0, "runtime_rejected": rejected,
                "source_sha256": digest(folder / "drag_drop.mbt")}
            save()
            if not rejected:
                raise ValueError(f"mutant {name} did not compile and fail behaviorally")
        (candidate / "drag_drop.mbt").write_text(original)
        folder = out / "compiler-rejection-controls" / "wrong_payload_type"
        folder.mkdir(parents=True)
        mutated = one_replace(original, "session : @element.DragSession[DragInfo]", "session : @element.DragSession[String]")
        (folder / "drag_drop.mbt").write_text(mutated)
        (candidate / "drag_drop.mbt").write_text(mutated)
        code, _ = run_logged(["moon", "check", PACKAGE, "--target", "js"], work, folder / "check.log")
        report["compiler_rejection_controls"]["wrong_payload_type"] = {"compiler_rejected": code != 0,
            "source_sha256": digest(folder / "drag_drop.mbt")}
        save()
        if code == 0:
            raise ValueError("wrong payload type unexpectedly compiled")
        (candidate / "drag_drop.mbt").write_text(original)
        code, _ = run_logged(["moon", "test", PACKAGE, "--target", "js"], work, out / "restored-baseline.log")
        report["baseline"]["restored_after_mutations"] = "passed" if code == 0 else "failed"
        save()
        if code:
            raise ValueError("restored positive baseline failed")
    if command(["git", "rev-parse", "HEAD"], core) != revision or command(
            ["git", "rev-parse", "HEAD^{tree}"], core) != tree or command(
            ["git", "status", "--porcelain", "--untracked-files=no"], core):
        raise ValueError("core source identity changed during tests")
    report["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    save()
    print(f"Local contracts retained at {out}; no browser/conformance claim")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpui-source", required=True, type=Path)
    parser.add_argument("--core-revision", required=True)
    parser.add_argument("--core-tree", required=True)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--no-mutations", action="store_true")
    args = parser.parse_args()
    try:
        test_candidate(args.gpui_source.resolve(), args.core_revision, args.core_tree,
                       args.out.resolve(), not args.no_mutations)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"drag-drop local tests failed: {error}\n")
