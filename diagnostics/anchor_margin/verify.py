#!/usr/bin/env python3
"""Independently inspect actual margin probe traces; synthetic tests are not Rust evidence."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import stat
import subprocess
from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).resolve().parents[2]

UPSTREAM = "5a5fbe79917971a4d52a96b6ddb04da198a5012e"
UPSTREAM_TREE = "990fb995914d51a546b20e5cf0382dafc105c299"
SUITE_BASE = "46659f7e8d8e503964e41c4e9eb20e0ace08931a"
LAYER = "supplemental-headless-anchor-margin"
RETAIN = ["adapters/anchor_margin_rust/Cargo.toml", "adapters/anchor_margin_rust/Cargo.lock",
    "adapters/anchor_margin_rust/src/main.rs", "diagnostics/anchor_margin/scenarios.json",
    "diagnostics/anchor_margin/profile.json", "diagnostics/anchor_margin/raw.schema.json",
    "diagnostics/anchor_margin/run.py", "diagnostics/anchor_margin/verify.py",
    "diagnostics/anchor_margin/README.md", "tests/test_anchor_margin_diagnostic.py",
    ".github/workflows/anchor-margin-diagnostic.yml"]
UPSTREAM_RETAIN = ["Cargo.toml", "Cargo.lock", "rust-toolchain.toml", "crates/gpui/Cargo.toml",
    "crates/gpui/src/elements/anchored.rs", "crates/gpui/src/elements/deferred.rs", "crates/gpui/src/elements/div.rs",
    "crates/gpui/src/element.rs", "crates/gpui/src/styled.rs", "crates/gpui/src/style.rs",
    "crates/gpui/src/taffy.rs", "crates/gpui/src/util.rs", "crates/gpui/src/geometry.rs", "crates/gpui/src/window.rs",
    "crates/gpui/src/app.rs", "crates/gpui/src/app/test_context.rs", "crates/gpui/src/keymap/context.rs",
    "crates/gpui/src/interactive.rs", "crates/gpui/src/platform/test/platform.rs",
    "crates/gpui/src/platform/test/window.rs", "crates/gpui/examples/anchor.rs"]
ANCHORS = {"TopLeft": (0, 0), "BottomRight": (1, 1)}
NODES = {"$host", "parent", "button", "deferred", "anchor", "popup"}
GEOMETRY_F32_ALLOWANCE = 2 ** -10  # logical pixels, qualified finite corpus
PHYSICAL_GRID_F32_ALLOWANCE = 2 ** -10  # physical pixels


def require(condition, message):
    if not condition: raise ValueError(message)


def load_json(path):
    def pairs(entries):
        result = {}
        for key, value in entries:
            require(key not in result, "duplicate JSON key: " + key)
            result[key] = value
        return result
    def reject(value): raise ValueError("non-finite JSON constant: " + value)
    return json.loads(Path(path).read_text(), object_pairs_hook=pairs, parse_constant=reject)


def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def retained_path(relative):
    if relative.startswith(".github/workflows/"): return "retained/workflows/" + Path(relative).name
    return "retained/" + relative


def number(value, label):
    require(type(value) in (int, float) and math.isfinite(value), label + ": finite number required")


def close(actual, expected, label, allowance=GEOMETRY_F32_ALLOWANCE):
    number(actual, label); number(expected, label)
    require(abs(actual - expected) <= allowance, f"{label}: {actual} != {expected}; allowance {allowance}")


def vector(actual, expected, label, allowance=GEOMETRY_F32_ALLOWANCE):
    require(isinstance(actual, list) and len(actual) == len(expected), label + ": vector shape")
    for a, e in zip(actual, expected): close(a, e, label, allowance)


def qualify_bounds(rectangle):
    require(isinstance(rectangle, list) and len(rectangle) == 4, "raw bounds shape")
    for value in rectangle: number(value, "raw bounds")
    require(all(abs(value) <= 4096 for value in rectangle[:2]), "numerically unqualified coordinate")
    require(all(0 <= value <= 2048 for value in rectangle[2:]), "numerically unqualified size")
    require(all(abs(rectangle[a] + rectangle[a + 2]) <= 4096 for a in (0, 1)), "numerically unqualified far edge")


def physical_grid(rectangle, scale):
    qualify_bounds(rectangle)
    for edge in (rectangle[0], rectangle[1], rectangle[0] + rectangle[2], rectangle[1] + rectangle[3]):
        close(edge * scale, round(edge * scale), "physical grid", PHYSICAL_GRID_F32_ALLOWANCE)


def bounded(values, count, low, high, label):
    require(isinstance(values, list) and len(values) == count, label + " shape")
    for value in values:
        number(value, label)
        require(low <= value <= high and value * 4 == int(value * 4), label + " bounded quarter pixels")


def validate_scenarios(corpus):
    require(set(corpus) == {"schema_version", "coordinate_system", "cases"} and corpus["schema_version"] == 1, "input schema")
    require(isinstance(corpus["coordinate_system"], str) and corpus["coordinate_system"], "coordinate system")
    require(isinstance(corpus["cases"], list) and 1 <= len(corpus["cases"]) <= 128, "bounded case count")
    identifiers = set()
    for case in corpus["cases"]:
        require(set(case) == {"id", "window", "parent_origin", "parent_size", "scale_factor", "popup"}, "case shape")
        require(isinstance(case["id"], str) and re.fullmatch(r"[A-Za-z0-9_.-]+", case["id"]) and case["id"] not in identifiers, "case id")
        identifiers.add(case["id"])
        for key, low, high in (("window", 1, 2048), ("parent_origin", 0, 2048), ("parent_size", 1, 1024)):
            bounded(case[key], 2, low, high, key)
        number(case["scale_factor"], "scale")
        require(case["scale_factor"] in (1, 1.25), "requested scale")
        popup = case["popup"]
        require(set(popup) == {"anchor", "position", "position_mode", "size", "margin"}, "popup shape")
        require(popup["anchor"] in ANCHORS and popup["position_mode"] in ("Local", "Window"), "anchor/mode")
        bounded(popup["position"], 2, -2048, 2048, "position")
        bounded(popup["size"], 2, 1, 1024, "size")
        number(popup["margin"], "margin")
        require(popup["margin"] in (0, 8), "scalar margin domain")
        # This corpus excludes fractional physical extents; no general Taffy-size claim.
        require(all(value * case["scale_factor"] == int(value * case["scale_factor"])
                    for value in case["window"] + case["parent_origin"] + case["parent_size"] + popup["size"]),
                "integral physical authored extents required")


def round_away(value): return math.floor(value + .5) if value >= 0 else math.ceil(value - .5)


def snap_offset(value, scale):
    physical = value * scale
    return math.copysign(math.ceil(abs(physical) - .5), physical) / scale


def derive_placement(case, static, child_size, scale):
    """Checker-side source hypothesis only. Never supplied to the observing binary."""
    popup = case["popup"]
    desired = [popup["position"][a] + (static[a] if popup["position_mode"] == "Local" else 0)
               - ANCHORS[popup["anchor"]][a] * child_size[a] for a in (0, 1)]
    original = desired.copy(); margin = popup["margin"]; branches = []
    # Raw viewport predicates. Sequential left/top observe prior right/bottom corrections.
    if desired[0] + child_size[0] > case["window"][0]:
        desired[0] -= desired[0] + child_size[0] - case["window"][0] + margin; branches.append("right")
    if desired[0] < 0:
        desired[0] = margin; branches.append("left")
    if desired[1] + child_size[1] > case["window"][1]:
        desired[1] -= desired[1] + child_size[1] - case["window"][1] + margin; branches.append("bottom")
    if desired[1] < 0:
        desired[1] = margin; branches.append("top")
    logical = [round_away(desired[a] - static[a]) for a in (0, 1)]
    snapped = [snap_offset(value, scale) for value in logical]
    return {"desired_before_snap": original, "source_predicate_branches": branches,
        "desired_after_snap": desired, "logical_offset": logical, "device_snapped_offset": snapped,
        "expected_origin": [static[a] + snapped[a] for a in (0, 1)]}


def verify_frame(entries, case, scale):
    first = entries[0]["event"]
    require(first == {"type": "frame_start", "scale_factor": scale, "window_size": case["window"], "client_inset": None}, "frame viewport/scale/client inset")
    stack, phases, prepaint, painted, locations, parents = [], {}, {}, [], {}, {}
    for index, entry in enumerate(entries[1:], 1):
        event = entry["event"]; kind, node = event["type"], event.get("node")
        require(node in NODES, "unknown node")
        fields = {"type", "node"} | ({"bounds", "content_mask", "element_offset"} if kind == "prepaint" else {"bounds"} if kind == "paint" else set())
        require(set(event) == fields, "lifecycle event shape")
        locations[kind, node] = index
        if kind in ("request_layout", "prepaint", "paint"):
            expected_phase = {"request_layout": 0, "prepaint": 2, "paint": 4}[kind]
            require(phases.get(node, 0) == expected_phase, "repeated/out-of-order lifecycle")
            phases[node] = expected_phase + 1
            parents[kind, node] = stack[-1][1] if stack else None
            stack.append((kind, node))
            if kind in ("prepaint", "paint"):
                physical_grid(event["bounds"], scale)
                if kind == "prepaint":
                    qualify_bounds(event["content_mask"])
                    vector(event["content_mask"], [0, 0, *case["window"]], "logical viewport content mask", 0)
                    bounded(event["element_offset"], 2, -8192, 8192, "actual logical element offset")
                    prepaint[node] = event
                else:
                    vector(event["bounds"], prepaint[node]["bounds"], "paint/prepaint agreement", 0)
                    painted.append(node)
        else:
            require(kind in ("request_layout_end", "prepaint_end", "paint_end"), "unknown lifecycle kind")
            require(stack and stack.pop() == (kind[:-4], node), "lifecycle return nesting")
            phases[node] += 1
    require(not stack and set(phases) == NODES and all(v == 6 for v in phases.values()), "incomplete lifecycle")
    vector(prepaint["$host"]["bounds"], [0, 0, *case["window"]], "authored host")
    vector(prepaint["parent"]["bounds"], [*case["parent_origin"], *case["parent_size"]], "authored parent")
    vector(prepaint["button"]["bounds"], [*case["parent_origin"], 120, snap_offset(65, scale)], "authored button")
    for phase in ("request_layout", "prepaint", "paint"):
        expected = {"$host": None, "parent": "$host", "button": "parent", "deferred": "parent",
            "anchor": "deferred" if phase == "request_layout" else None, "popup": "anchor"}
        require({node: parents[phase, node] for node in NODES} == expected, "lifecycle ancestry")
        if phase != "request_layout":
            require(locations[phase + "_end", "$host"] < locations[phase, "anchor"], "genuine deferred lifecycle")
    require(painted == ["$host", "parent", "button", "deferred", "anchor", "popup"], "paint callback order")
    static = prepaint["anchor"]["bounds"]
    vector(prepaint["deferred"]["bounds"], static, "shared deferred/anchor layout", 0)
    child = prepaint["popup"]["bounds"]
    vector(child[2:], static[2:], "child measured size", 0)
    vector(child[2:], case["popup"]["size"], "authored popup fixed size")
    derivation = derive_placement(case, static, child[2:], scale)
    for node in NODES - {"popup"}:
        vector(prepaint[node]["element_offset"], [0, 0], "untranslated outer element offset", 0)
    vector(prepaint["popup"]["element_offset"], derivation["logical_offset"], "observed logical ties-away offset", 0)
    vector(child[:2], derivation["expected_origin"], "raw-edge margin/order/logical rounding/device snap")
    return {"frame": entries[0]["frame"], "scale_factor": scale,
        "observed_bounds": {node: value["bounds"] for node, value in prepaint.items()},
        "observed_content_mask": prepaint["popup"]["content_mask"],
        "observed_logical_offset": prepaint["popup"]["element_offset"],
        "observed_static_origin": static[:2], "painted_nodes": painted,
        "checker_derivation_not_observation": derivation}


def verify_observations(raw, corpus):
    schema = load_json(ROOT / "diagnostics/anchor_margin/raw.schema.json")
    try: Draft202012Validator(schema).validate(raw)
    except ValidationError as error: raise ValueError("raw schema: " + error.message) from error
    validate_scenarios(corpus)
    require(set(raw) == {"schema_version", "layer", "fixture", "text_system", "upstream_revision", "run_token", "input", "cases"}, "raw shape")
    require(raw["schema_version"] == 1 and raw["layer"] == LAYER and raw["fixture"] == "font-free-bounded-anchor-margin", "raw layer/schema/fixture")
    require(raw["text_system"] == "NoopTextSystem; no text used" and raw["upstream_revision"] == UPSTREAM, "text/source pin")
    require(isinstance(raw["run_token"], str) and re.fullmatch(r"[A-Za-z0-9-]{16,64}", raw["run_token"]), "run token")
    require(raw["input"] == corpus, "input mismatch")
    require([observed["id"] for observed in raw["cases"]] == [case["id"] for case in corpus["cases"]], "case ordering/coverage")
    results = []
    for observed, case in zip(raw["cases"], corpus["cases"]):
        require(set(observed) == {"id", "events"} and 1 <= len(observed["events"]) <= 10000, "case output shape/count")
        events = observed["events"]
        require(all(set(entry) == {"sequence", "operation", "frame", "event"} for entry in events), "entry shape")
        require([entry["sequence"] for entry in events] == list(range(len(events))), "event sequence")
        cursor, frame_number, operations = 0, 0, []
        for operation, input_value, scale in (("initial", {"action": "open_window"}, 2),
                ("configured", {"action": "set_scale_factor", "scale_factor": case["scale_factor"]}, case["scale_factor"])):
            require(cursor < len(events), "missing operation")
            start = events[cursor]; cursor += 1
            require(start == {"sequence": cursor - 1, "operation": operation, "frame": frame_number,
                              "event": {"type": "operation_start", "input": input_value}}, "operation start/input/frame")
            pending, frames = [], []
            while cursor < len(events) and events[cursor]["event"]["type"] != "operation_end":
                entry = events[cursor]; cursor += 1
                require(entry["operation"] == operation, "operation interleaving")
                if entry["event"]["type"] == "frame_start":
                    if pending: frames.append(verify_frame(pending, case, scale))
                    pending = []; frame_number += 1
                require(entry["frame"] == frame_number and (pending or entry["event"]["type"] == "frame_start"), "frame sequence/boundary")
                pending.append(entry)
            if pending: frames.append(verify_frame(pending, case, scale))
            require(frames and cursor < len(events), "missing redraw/operation end")
            end = events[cursor]; cursor += 1
            require(end == {"sequence": cursor - 1, "operation": operation, "frame": frame_number,
                            "event": {"type": "operation_end", "scale_factor": scale}}, "operation end/scale")
            operations.append({"id": operation, "frames": frames})
        require(cursor == len(events), "trailing events")
        results.append({"id": case["id"], "operations": operations})
    return {"schema_version": 1, "layer": LAYER, "cases": results,
        "case_count": len(results), "observed_frame_count": sum(len(op["frames"]) for c in results for op in c["operations"]),
        "claim": "Public GPUI margin layout/lifecycle observations only; no unchanged-example, candidate, hit, raster clipping, browser, native-window or full popover parity."}


def strict_file(directory, relative):
    require(isinstance(relative, str) and relative and not Path(relative).is_absolute()
            and str(Path(relative)) == relative and not set(Path(relative).parts) & {".", ".."}, "unsafe evidence name")
    current = directory
    for part in Path(relative).parts:
        current = current / part
        require(not current.is_symlink(), "symlink evidence path")
    info = current.stat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= 512 * 1024**2, "unsafe evidence file")
    return current


def verify_bundle(directory, suite_commit=None, suite_tree=None, suite_source=None, upstream_source=None, recorded_execution_root=None):
    directory = Path(directory)
    require(not directory.is_symlink(), "symlink evidence root")
    manifest = load_json(strict_file(directory, "manifest.json"))
    require(manifest["schema_version"] == 1 and manifest["layer"] == LAYER, "manifest schema/layer")
    require(manifest["upstream"] == {"commit": UPSTREAM, "tree": UPSTREAM_TREE, "clean": True}, "upstream source identity")
    require(manifest["suite"]["clean"] is True and manifest["suite_after"] == manifest["suite"] and manifest["upstream_after"] == manifest["upstream"], "source changed/dirty")
    require(suite_commit is None or manifest["suite"]["commit"] == suite_commit, "unexpected suite commit")
    require(suite_tree is None or manifest["suite"]["tree"] == suite_tree, "unexpected suite tree")
    for field in ("commit", "tree"):
        require(isinstance(manifest["suite"][field], str) and re.fullmatch("[0-9a-f]{40}", manifest["suite"][field]), "suite identity")
    profile = load_json(strict_file(directory, retained_path("diagnostics/anchor_margin/profile.json")))
    require(profile["layer"] == LAYER and profile["suite_base"] == SUITE_BASE and profile["upstream_commit"] == UPSTREAM
            and profile["upstream_tree"] == UPSTREAM_TREE, "profile source identity")
    frozen = profile["frozen_original"]["sha256"]
    relatives = RETAIN + list(frozen)
    required = {"raw.json", "raw.stderr", "scenarios.json", "probe", "toolchain.txt", "build.stdout", "build.stderr", "build-Cargo.toml", "build-Cargo.lock", "build-plan.json"}
    required |= {retained_path(relative) for relative in relatives} | {"upstream/" + relative for relative in UPSTREAM_RETAIN}
    require(set(manifest["files"]) == required, "missing/extra retained inventory")
    actual = {str(path.relative_to(directory)) for path in directory.rglob("*") if path.is_file() or path.is_symlink()}
    require(required | {"manifest.json"} <= actual <= required | {"manifest.json", "verification.json", "verification-failure.json"}, "missing/extra evidence file")
    for relative, metadata in manifest["files"].items():
        path = strict_file(directory, relative)
        require(set(metadata) == {"sha256", "size"} and digest(path) == metadata["sha256"] and path.stat().st_size == metadata["size"], "changed evidence: " + relative)
    for relative, sha in frozen.items():
        require(digest(directory / retained_path(relative)) == sha, "frozen original changed: " + relative)
    require((directory / "scenarios.json").read_bytes() == (directory / retained_path("diagnostics/anchor_margin/scenarios.json")).read_bytes(), "retained/run scenario mismatch")
    require(digest(directory / "scenarios.json") == profile["input_sha256"], "profile/input hash mismatch")
    corpus = load_json(directory / "scenarios.json")
    require(len(corpus["cases"]) == profile["case_count"], "profile/case count")
    require((directory / "build-Cargo.lock").read_bytes() == (directory / retained_path("adapters/anchor_margin_rust/Cargo.lock")).read_bytes(), "locked build changed dependency lock")
    original = (directory / retained_path("adapters/anchor_margin_rust/Cargo.toml")).read_text()
    placeholder = '"../../../zed-source/crates/gpui"'
    require(original.count(placeholder) == 1, "retained dependency path")
    require((directory / "build-Cargo.toml").read_text() == original.replace(placeholder, json.dumps(manifest["upstream_source_path"] + "/crates/gpui")), "build relocation")
    for source, identity, prefix, paths in ((suite_source, manifest["suite"], "retained", relatives), (upstream_source, manifest["upstream"], "upstream", UPSTREAM_RETAIN)):
        if source is not None:
            tree = subprocess.check_output(["git", "rev-parse", identity["commit"] + "^{tree}"], cwd=source, text=True).strip()
            require(tree == identity["tree"], "independent source tree mismatch")
            for relative in paths:
                expected = subprocess.check_output(["git", "show", identity["commit"] + ":" + relative], cwd=source)
                require((directory / (retained_path(relative) if prefix == "retained" else "upstream/" + relative)).read_bytes() == expected, "retained bytes differ from exact committed source: " + relative)
    with (directory / "probe").open("rb") as executable: require(executable.read(4) == b"\x7fELF", "probe is not ELF")
    require((directory / "toolchain.txt").read_text().startswith("rustc 1.98.1 "), "compiler provenance")
    require((directory / "raw.stderr").stat().st_size == 0, "runtime stderr is not empty")
    raw = load_json(directory / "raw.json")
    require(raw["run_token"] == manifest["run_token"], "cross-run trace")
    for kind in ("execution", "build"):
        require(manifest[kind]["returncode"] == 0 and manifest[kind]["timed_out"] is False, "failed/timed out " + kind)
    execution_root = directory.resolve() if recorded_execution_root is None else Path(recorded_execution_root)
    require(execution_root.is_absolute() and str(execution_root) == str(execution_root.resolve()) and ".." not in execution_root.parts, "canonical recorded execution root")
    build_roots = [p for p in execution_root.parents if p.name == "_build"]
    require(len(build_roots) == 1, "one ignored build root required")
    expected_build = ["cargo", "+1.98.1", "build", "--locked", "--manifest-path", str(build_roots[0] / ("anchor-margin-build-" + manifest["run_token"]) / "adapter/Cargo.toml")]
    expected_execute = [str(execution_root / "probe"), str(execution_root / "scenarios.json"), manifest["run_token"]]
    require(manifest["build"]["command"] in (expected_build, expected_build + ["--offline"]), "exact build command")
    require(manifest["execution"]["command"] == expected_execute, "execution executable/input/token")
    plan = load_json(directory / "build-plan.json")
    require(plan == {"schema_version": 1, "layer": LAYER, "run_token": manifest["run_token"],
        "build_command": manifest["build"]["command"], "execution_command": expected_execute,
        "environment": {"CARGO_BUILD_JOBS": "2", "CARGO_INCREMENTAL": "0", "DISPLAY": None, "WAYLAND_DISPLAY": None},
        "input_sha256": digest(directory / "scenarios.json"), "lock_sha256": digest(directory / retained_path("adapters/anchor_margin_rust/Cargo.lock")),
        "build_manifest_sha256": digest(directory / "build-Cargo.toml"), "toolchain_sha256": digest(directory / "toolchain.txt")}, "build plan binding")
    require(manifest["environment"] == plan["environment"], "build environment binding")
    result = verify_observations(raw, corpus)
    result["source_bound"] = all(v is not None for v in (suite_commit, suite_tree, suite_source, upstream_source))
    result["inspection_scope"] = "Source-bound retained observations" if result["source_bound"] else "Integrity and semantic inspection only; source authenticity unqualified"
    result["frozen_original_rerun"] = False
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--suite-commit"); parser.add_argument("--suite-tree")
    parser.add_argument("--suite-source", type=Path); parser.add_argument("--upstream-source", type=Path)
    parser.add_argument("--recorded-execution-root", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify_bundle(args.evidence, args.suite_commit, args.suite_tree, args.suite_source, args.upstream_source, args.recorded_execution_root), indent=2))


if __name__ == "__main__": main()
