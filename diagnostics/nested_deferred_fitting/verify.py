#!/usr/bin/env python3
"""Inspect retained real GPUI observations; source-derived predictions are never raw evidence."""
from __future__ import annotations
import argparse
import hashlib
from fractions import Fraction
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
SUITE_BASE = "ca784321838a59942cfdbc2a24804f038484974f"
SUITE_BASE_TREE = "e61878c51a5c42dfd0d5fd34b485c48a76586007"
LAYER = "supplemental-headless-nested-deferred-fitting"
RETAIN = ["adapters/nested_deferred_fitting_rust/Cargo.toml", "adapters/nested_deferred_fitting_rust/Cargo.lock",
    "adapters/nested_deferred_fitting_rust/src/main.rs", "diagnostics/nested_deferred_fitting/scenarios.json",
    "diagnostics/nested_deferred_fitting/profile.json", "diagnostics/nested_deferred_fitting/raw.schema.json",
    "diagnostics/nested_deferred_fitting/run.py", "diagnostics/nested_deferred_fitting/verify.py",
    "diagnostics/nested_deferred_fitting/README.md", "tests/test_nested_deferred_fitting_diagnostic.py",
    ".github/workflows/nested-deferred-fitting-diagnostic.yml"]
UPSTREAM_RETAIN = ["Cargo.toml", "Cargo.lock", "rust-toolchain.toml", "crates/gpui/Cargo.toml",
    "crates/gpui/src/elements/anchored.rs", "crates/gpui/src/elements/deferred.rs", "crates/gpui/src/elements/div.rs",
    "crates/gpui/src/element.rs", "crates/gpui/src/styled.rs", "crates/gpui/src/style.rs",
    "crates/gpui/src/taffy.rs", "crates/gpui/src/util.rs", "crates/gpui/src/geometry.rs", "crates/gpui/src/window.rs",
    "crates/gpui/src/app.rs", "crates/gpui/src/app/test_context.rs", "crates/gpui/src/interactive.rs",
    "crates/gpui/src/platform/test/platform.rs", "crates/gpui/src/platform/test/window.rs", "crates/gpui/examples/popover.rs"]
# Frozen before any real execution. Order, identifiers and configuration remain exact.
GEOMETRY_F32_ALLOWANCE = 2 ** -10
PHYSICAL_GRID_F32_ALLOWANCE = 2 ** -10


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


def vector(actual, expected, label, allowance=GEOMETRY_F32_ALLOWANCE):
    require(isinstance(actual, list) and len(actual) == len(expected), label + ": vector shape")
    for a, e in zip(actual, expected):
        number(a, label); number(e, label)
        require(abs(a - e) <= allowance, f"{label}: {a} != {e}; allowance {allowance}")


def bounded_vector(values, count, low, high, label):
    require(isinstance(values, list) and len(values) == count, label + " shape")
    for value in values:
        number(value, label)
        require(low <= value <= high and value * 4 == int(value * 4), label + " domain")


def physical_grid(bounds, scale):
    require(isinstance(bounds, list) and len(bounds) == 4, "bounds shape")
    for value in bounds:
        number(value, "bounds")
        require(0 <= value <= 2048, "qualified bounds domain")
    for edge in (bounds[0], bounds[1], bounds[0] + bounds[2], bounds[1] + bounds[3]):
        require(abs(edge * scale - round(edge * scale)) <= PHYSICAL_GRID_F32_ALLOWANCE, "physical grid")


FIXTURES = {
    "exact-inside": (8, ((200, 140), (199.75, 139.75)), ((56, 32), (55.75, 31.75))),
    "outer-only": (8, ((200.25, 140.25), (-24.25, -28.25)), ((32, 24), (32, 24))),
    "inner-only": (8, ((24, 24), (24, 24)), ((232.25, 148.25), (-48.25, -60.25))),
    "both-levels": (8, ((200.25, 140.25), (-24.25, -28.25)), ((64.25, 40.25), (-8.25, -16.25))),
    "threshold-device-half": (8, ((.25, -.25), (.75, -.75)), ((1.75, -1.75), (1.25, -1.25))),
    "signed-half-composed": (8, ((.5, -.5), (-.5, .5)), ((1.5, -1.5), (-1.5, 1.5))),
    "fit-created-half": (.5, ((200.25, 140.25), (-24.25, -28.25)), ((56.25, 32.25), (-.25, -8.25))),
    "window-local": (8, ((200.25, 140.25), (200.25, 140.25)), ((80, 96), (80, 96))),
}


def validate_scenarios(corpus):
    require(set(corpus) == {"schema_version", "coordinate_system", "cases"} and type(corpus["schema_version"]) is int and corpus["schema_version"] == 1, "input schema")
    require(isinstance(corpus["coordinate_system"], str) and corpus["coordinate_system"], "coordinate system")
    require(isinstance(corpus["cases"], list) and 1 <= len(corpus["cases"]) <= 8, "case count")
    ids = set()
    for case in corpus["cases"]:
        require(set(case) == {"id", "window", "ancestor_origin", "ancestor_size", "ancestor_movement", "reference_size", "updated_nested_reference_height", "anchor", "margin", "outer_size", "nested_size", "layers"}, "case shape")
        require(isinstance(case["id"], str) and case["id"] not in ids and case["id"] in FIXTURES, "case id"); ids.add(case["id"])
        margin, outer, inner = FIXTURES[case["id"]]
        for field, expected in (("window", [320, 240]), ("ancestor_origin", [24, 20]), ("ancestor_size", [272, 192]), ("ancestor_movement", [16, 12]), ("reference_size", [12, 8]), ("outer_size", [96, 72]), ("nested_size", [40, 32])):
            vector(case[field], expected, field, 0)
        number(case["margin"], "margin"); require(case["anchor"] == "TopLeft" and case["margin"] == margin, "frozen anchor/margin")
        require(type(case["updated_nested_reference_height"]) is int and case["updated_nested_reference_height"] == 12, "reference height input")
        require(isinstance(case["layers"], list) and len(case["layers"]) == 2, "two outer attachments")
        for ix, layer in enumerate(case["layers"]):
            require(set(layer) == {"id", "priority", "nested_priority", "position", "nested_position", "nested_mode"}, "layer shape")
            require(layer["id"] == "ab"[ix], "structural outer IDs")
            require(type(layer["priority"]) is int and layer["priority"] == (2, 1)[ix] and type(layer["nested_priority"]) is int and layer["nested_priority"] == 3, "baseline priorities")
            vector(layer["position"], outer[ix], "outer authored reference", 0)
            vector(layer["nested_position"], inner[ix], "nested authored reference", 0)
            require(layer["nested_mode"] == ("Window" if case["id"] == "window-local" and ix == 0 else "Local"), "nested mode")


def active_layers(case, stage):
    priorities = [2, 0, 3, 1] if stage == "child-lower" else [1, 1, 1, 1] if stage == "all-equal" else [2, 3, 1, 3]
    return [dict(layer, priority=priorities[ix * 2], nested_priority=priorities[ix * 2 + 1]) for ix, layer in enumerate(case["layers"])]


def authored_metadata(node, case, stage):
    group = node.split(".")[0] if node.startswith(("a.", "b.")) else "ordinary"
    if group == "ordinary": return {"group": group, "priority": None}
    layer = next(layer for layer in active_layers(case, stage) if layer["id"] == group)
    nested = ".nested." in node
    return {"group": group + (".nested" if nested else ""), "priority": layer["nested_priority" if nested else "priority"]}


def derive_schedule(case, stage):
    """Source hypothesis only: two sorted discovery rounds, then globally stable append registry."""
    outer = active_layers(case, stage)
    registry = [{"id": layer["id"], "priority": layer["priority"]} for layer in outer]
    first = sorted(outer, key=lambda layer: layer["priority"])
    discovered = [{"id": layer["id"] + ".nested", "priority": layer["nested_priority"]} for layer in first]
    registry += discovered
    return {"prepaint_discovery_rounds": [[layer["id"] for layer in first], [item["id"] for item in sorted(discovered, key=lambda item: item["priority"])]], "append_registry": registry, "global_stable_paint_registry": [item["id"] for item in sorted(registry, key=lambda item: item["priority"])]}


def derived_lifecycle(case, stage):
    structural = active_layers(case, stage); schedule = derive_schedule(case, stage); events = []
    def visit(phase, node, children=()):
        events.append((phase, node))
        for child in children: child()
        events.append((phase + "_end", node))
    def attachment(phase, prefix):
        if prefix.endswith(".nested"):
            visit(phase, prefix + ".anchor", [lambda: visit(phase, prefix + ".root")]); return
        def children():
            visit(phase, prefix + ".before"); visit(phase, prefix + ".reference")
            visit(phase, prefix + ".nested.deferred", [lambda: attachment(phase, prefix + ".nested")] if phase == "request_layout" else [])
            visit(phase, prefix + ".after")
        visit(phase, prefix + ".anchor", [lambda: visit(phase, prefix + ".root", [children])])
    for phase in ("request_layout", "prepaint", "paint"):
        def ancestor_children():
            visit(phase, "ordinary.before"); visit(phase, "ordinary.reference")
            for layer in structural:
                visit(phase, layer["id"] + ".deferred", [lambda layer=layer: attachment(phase, layer["id"])] if phase == "request_layout" else [])
            visit(phase, "ordinary.after")
        visit(phase, "$host", [lambda: visit(phase, "$ancestor", [ancestor_children])])
        if phase == "prepaint":
            for batch in schedule["prepaint_discovery_rounds"]:
                for prefix in batch: attachment(phase, prefix)
        elif phase == "paint":
            for prefix in schedule["global_stable_paint_registry"]: attachment(phase, prefix)
    return events, schedule


def logical_round(value):
    value = Fraction(value); magnitude = abs(value)
    integer = (magnitude.numerator * 2 + magnitude.denominator) // (2 * magnitude.denominator)
    return -integer if value < 0 else integer


def device_snap(value, scale):
    value = Fraction(value) * Fraction(scale); magnitude = abs(value)
    shifted = magnitude - Fraction(1, 2)
    integer = -((-shifted.numerator) // shifted.denominator)
    # ceil(abs(value)-1/2), followed by its original sign; exact halves toward zero.
    return Fraction(-integer if value < 0 else integer, 1) / Fraction(scale)


def fit(origin, dimensions, viewport, margin):
    result = list(map(Fraction, origin))
    for axis in (0, 1):
        # Strict overflow tests; margin is not applied to exact or inside edges.
        if result[axis] + dimensions[axis] > viewport[axis]: result[axis] = Fraction(viewport[axis] - dimensions[axis]) - Fraction(margin)
        if result[axis] < 0: result[axis] = Fraction(margin)
    return result


def derived_geometry(case, stage, scale):
    """Independent exact-rational hypothesis using authored layout, never raw bounds as placement input."""
    origin = [Fraction(case["ancestor_origin"][a] + (case["ancestor_movement"][a] if stage == "moved" else 0)) for a in (0, 1)]
    height = case["updated_nested_reference_height"] if stage == "reference-height" else case["reference_size"][1]
    outer_static = [origin[0], origin[1] + case["reference_size"][1]]
    nested_static_base = [outer_static[0], outer_static[1] + height]
    geometry = {"$host": ([0, 0, *case["window"]], [0, 0]), "$ancestor": ([*origin, *case["ancestor_size"]], [0, 0]), "ordinary.reference": ([*origin, *case["reference_size"]], [0, 0])}
    for suffix, pos in (("before", [0, 0]), ("after", [8, 8])):
        geometry["ordinary." + suffix] = ([origin[a] + pos[a] for a in (0, 1)] + [12, 12], [0, 0])
    derivations = {}
    for layer in active_layers(case, stage):
        prefix = layer["id"]
        outer_fitted = fit([outer_static[a] + Fraction(layer["position"][a]) for a in (0, 1)], case["outer_size"], case["window"], case["margin"])
        outer_delta = [logical_round(outer_fitted[a] - outer_static[a]) for a in (0, 1)]
        outer_snapped = [device_snap(delta, scale) for delta in outer_delta]
        outer_final = [outer_static[a] + outer_snapped[a] for a in (0, 1)]
        inner_static = [nested_static_base[a] + outer_snapped[a] for a in (0, 1)]
        inner_desired = [Fraction(layer["nested_position"][a]) + (inner_static[a] if layer["nested_mode"] == "Local" else 0) for a in (0, 1)]
        inner_fitted = fit(inner_desired, case["nested_size"], case["window"], case["margin"])
        inner_delta = [logical_round(inner_fitted[a] - inner_static[a]) for a in (0, 1)]
        composed = [outer_delta[a] + inner_delta[a] for a in (0, 1)]
        nested_final = [nested_static_base[a] + device_snap(composed[a], scale) for a in (0, 1)]
        for suffix in ("anchor", "deferred"): geometry[prefix + "." + suffix] = ([*outer_static, *case["outer_size"]], [0, 0])
        geometry[prefix + ".root"] = ([*outer_final, *case["outer_size"]], outer_delta)
        geometry[prefix + ".reference"] = ([*outer_final, case["reference_size"][0], height], outer_delta)
        for suffix, pos in (("before", [0, 0]), ("after", [16, 8])):
            geometry[prefix + "." + suffix] = ([outer_final[a] + pos[a] for a in (0, 1)] + [12, 12], outer_delta)
        for suffix in ("anchor", "deferred"): geometry[prefix + ".nested." + suffix] = ([*inner_static, *case["nested_size"]], outer_delta)
        geometry[prefix + ".nested.root"] = ([*nested_final, *case["nested_size"]], composed)
        derivations[prefix] = {"outer_static": outer_static, "outer_fitted": outer_fitted, "outer_logical_delta": outer_delta, "nested_layout_static": nested_static_base, "nested_inherited_static": inner_static, "nested_fitted": inner_fitted, "nested_logical_delta": inner_delta, "composed_logical_offset": composed}
    return {node: ([float(value) for value in bounds], offset) for node, (bounds, offset) in geometry.items()}, {prefix: {key: [float(value) for value in values] for key, values in data.items()} for prefix, data in derivations.items()}


def is_box(node): return node.startswith("ordinary.") or node.endswith((".root", ".before", ".after", ".reference"))


def verify_frame(entries, case, stage, scale):
    require(entries[0]["event"] == {"type": "frame_start", "scale_factor": scale, "window_size": case["window"], "client_inset": None}, "frame viewport/scale/inset")
    predicted, schedule = derived_lifecycle(case, stage)
    observed = [(entry["event"]["type"], entry["event"].get("node")) for entry in entries[1:]]
    require(observed == predicted, "exact lifecycle order/IDs/return boundaries or discovery round")
    geometry, derivations = derived_geometry(case, stage, scale); prepaint, paint = {}, {}
    for entry in entries[1:]:
        event = entry["event"]; phase, node = event["type"], event["node"]
        require({key: event[key] for key in ("group", "priority")} == authored_metadata(node, case, stage), "authored group/priority metadata")
        if phase in ("request_layout", "request_layout_end"): continue
        physical_grid(event["bounds"], scale)
        vector(event["content_mask"], [0, 0, *case["window"]], "observed viewport content mask", 0)
        vector(event["bounds"], geometry[node][0], "rational authored reference/fitting geometry")
        if phase in ("prepaint", "prepaint_end"): vector(event["element_offset"], geometry[node][1], "exact inherited/composed logical offset", 0)
        if phase == "prepaint": prepaint[node] = event
        if phase == "paint": paint[node] = event
    for node in prepaint: vector(paint[node]["bounds"], prepaint[node]["bounds"], "paint/prepaint geometry", 0)
    boxes = [node for node in paint if is_box(node)]
    require(len(boxes) == len(set(boxes)) == 13, "exact paintable box projection cardinality")
    return {"frame": entries[0]["frame"], "scale_factor": scale, "observed_request_layout_order": [node for phase, node in observed if phase == "request_layout"], "observed_prepaint_order": list(prepaint), "observed_paint_order": list(paint), "observed_paintable_box_projection": boxes, "observed_prepaint": prepaint, "observed_paint": paint, "checker_derivation_not_observation": {**schedule, "rational_geometry": derivations, "method": "authored flow references; strict viewport fit; logical half-away; composed offset device half-toward-zero; two discovery rounds then global stable paint"}}


def operation_plan(case):
    yield "initial", {"action": "open_window"}, "initial", 2
    yield "scale1", {"action": "set_scale_factor", "scale_factor": 1}, "scale1", 1
    yield "scale1.25", {"action": "set_scale_factor", "scale_factor": 1.25}, "scale1.25", 1.25
    yield "child-lower", {"action": "set_priorities", "priorities": [2, 0, 3, 1]}, "child-lower", 1.25
    yield "all-equal", {"action": "set_priorities", "priorities": [1, 1, 1, 1]}, "all-equal", 1.25
    yield "moved", {"action": "restore_priorities_and_move_ancestor", "delta": case["ancestor_movement"]}, "moved", 1.25
    yield "reference-height", {"action": "restore_ancestor_and_set_nested_reference_height", "height": case["updated_nested_reference_height"]}, "reference-height", 1.25
    yield "restored", {"action": "restore_original_state"}, "restored", 1.25


def verify_observations(raw, corpus, schema=None):
    schema = load_json(ROOT / "diagnostics/nested_deferred_fitting/raw.schema.json") if schema is None else schema
    try: Draft202012Validator(schema).validate(raw)
    except ValidationError as error: raise ValueError("raw schema: " + error.message) from error
    validate_scenarios(corpus)
    require(raw["input"] == corpus, "raw input mismatch")
    require([c["id"] for c in raw["cases"]] == [c["id"] for c in corpus["cases"]], "case IDs/order")
    results = []
    for observed, case in zip(raw["cases"], corpus["cases"]):
        entries = observed["events"]
        require([e["sequence"] for e in entries] == list(range(len(entries))), "event sequence")
        cursor, frame_id = 0, 0
        operations = []
        for name, action, stage, scale in operation_plan(case):
            require(cursor < len(entries), "missing operation")
            start = entries[cursor]; cursor += 1
            require(start == {"sequence": cursor - 1, "operation": name, "frame": frame_id,
                "event": {"type": "operation_start", "input": action}}, "operation start/input/frame")
            pending, frames = [], []
            while cursor < len(entries) and entries[cursor]["event"]["type"] != "operation_end":
                entry = entries[cursor]; cursor += 1
                require(entry["operation"] == name, "operation interleaving")
                kind = entry["event"]["type"]
                if kind == "frame_start":
                    if pending: frames.append(verify_frame(pending, case, stage, scale))
                    pending = []; frame_id += 1
                require(entry["frame"] == frame_id, "frame sequence")
                require(pending or kind == "frame_start", "lifecycle outside frame")
                pending.append(entry)
            if pending: frames.append(verify_frame(pending, case, stage, scale))
            require(frames, "missing required redraw")
            require(cursor < len(entries), "missing operation end")
            end = entries[cursor]; cursor += 1
            require(end == {"sequence": cursor - 1, "operation": name, "frame": frame_id,
                "event": {"type": "operation_end", "scale_factor": scale}}, "operation end/scale/frame")
            operations.append({"id": name, "frames": frames})
        require(cursor == len(entries), "trailing operations/events")
        results.append({"id": case["id"], "operations": operations})
    return {"schema_version": 1, "layer": LAYER, "cases": results, "case_count": len(results),
        "observed_frame_count": sum(len(op["frames"]) for c in results for op in c["operations"]),
        "claim": "Actual public GPUI two-level nested fitting/rounding lifecycle and authored flow-reference geometry/offsets/masks only; wrapper callbacks and paintable-box projection remain distinct. No input, cache, scroll, arbitrary nesting/content, unchanged popover, core, browser, raster or native-window parity."}


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


def validate_baseline_source(source, suite_commit):
    tree = subprocess.check_output(["git", "rev-parse", SUITE_BASE + "^{tree}"], cwd=source, text=True).strip()
    require(tree == SUITE_BASE_TREE, "immutable suite base tree")
    changed = subprocess.check_output(["git", "diff", "--name-status", SUITE_BASE, suite_commit, "--"], cwd=source, text=True).splitlines()
    require(all(line.split("\t") == ["A", line.split("\t")[-1]] and line.split("\t")[-1] in RETAIN for line in changed), "changed baseline or non-owned source path")
    require({line.split("\t")[-1] for line in changed} == set(RETAIN), "complete exclusively additive diagnostic scope")


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
    profile = load_json(strict_file(directory, retained_path("diagnostics/nested_deferred_fitting/profile.json")))
    require(profile["layer"] == LAYER and profile["suite_base"] == SUITE_BASE and profile["upstream_commit"] == UPSTREAM
            and profile["upstream_tree"] == UPSTREAM_TREE and profile["suite_base_tree"] == SUITE_BASE_TREE, "profile source identity")
    if suite_source is not None:
        validate_baseline_source(suite_source, manifest["suite"]["commit"])
    frozen = profile["frozen_original"]["sha256"]
    relatives = RETAIN + list(frozen)
    required = {"raw.stdout", "rustc.stdout", "rustc.stderr", "cargo.stdout", "cargo.stderr", "raw.json", "raw.stderr", "scenarios.json", "probe", "toolchain.txt", "build.stdout", "build.stderr", "build-Cargo.toml", "build-Cargo.lock", "build-plan.json"}
    required |= {retained_path(relative) for relative in relatives} | {"upstream/" + relative for relative in UPSTREAM_RETAIN}
    require(set(manifest["files"]) == required, "missing/extra retained inventory")
    actual = {str(path.relative_to(directory)) for path in directory.rglob("*") if path.is_file() or path.is_symlink()}
    require(required | {"manifest.json"} <= actual <= required | {"manifest.json", "verification.json", "verification-failure.json"}, "missing/extra evidence file")
    for relative, metadata in manifest["files"].items():
        path = strict_file(directory, relative)
        require(set(metadata) == {"sha256", "size"} and digest(path) == metadata["sha256"] and path.stat().st_size == metadata["size"], "changed evidence: " + relative)
    for relative, sha in frozen.items():
        require(digest(directory / retained_path(relative)) == sha, "frozen original changed: " + relative)
    require((directory / "scenarios.json").read_bytes() == (directory / retained_path("diagnostics/nested_deferred_fitting/scenarios.json")).read_bytes(), "retained/run scenario mismatch")
    require(digest(directory / "scenarios.json") == profile["input_sha256"], "profile/input hash mismatch")
    require((directory / "raw.stdout").read_bytes() == (directory / "raw.json").read_bytes(), "original raw stdout bytes changed")
    require(profile["requested_scales"] == [1, 1.25] and profile["bootstrap_scale"] == 2 and profile["client_inset"] is None, "profile scale/inset contract")
    require(profile["stages"] == ["initial", "scale1", "scale1.25", "child-lower", "all-equal", "moved", "reference-height", "restored"], "profile operation contract")
    require(profile["rounding_contract"]["logical"] == "nearest integer; exact halves away from zero" and profile["rounding_contract"]["device"] == "nearest device integer; exact halves toward zero" and profile["rounding_contract"]["composition"] == "deviceSnap(outerDelta+innerDelta), not sum of separately snapped offsets", "predeclared rounding contract")
    require(len(profile["baseline_git_entries"]) == 693 and set(profile["baseline_git_entries"]) == set(profile["baseline_tracked_sha256"]), "complete immutable baseline inventory")
    require(profile["geometry_allowance_logical_px"] == GEOMETRY_F32_ALLOWANCE and profile["physical_grid_allowance_px"] == PHYSICAL_GRID_F32_ALLOWANCE and profile["order_and_ids_allowance"] == 0, "predeclared comparison budget")
    corpus = load_json(directory / "scenarios.json")
    require(len(corpus["cases"]) == profile["case_count"], "profile/case count")
    require((directory / "build-Cargo.lock").read_bytes() == (directory / retained_path("adapters/nested_deferred_fitting_rust/Cargo.lock")).read_bytes(), "locked build changed dependency lock")
    original = (directory / retained_path("adapters/nested_deferred_fitting_rust/Cargo.toml")).read_text()
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
    for kind in ("execution", "build", "rustc", "cargo"):
        require(manifest[kind]["returncode"] == 0 and manifest[kind]["timed_out"] is False and manifest[kind]["resource_floor_breached"] is False, "failed/timed out " + kind)
    for tool in ("rustc", "cargo"):
        require(manifest[tool]["command"] == [tool, "+1.98.1", "--version", "--verbose"], "toolchain command")
        require((directory / (tool + ".stderr")).stat().st_size == 0, "toolchain stderr")
    require((directory / "toolchain.txt").read_bytes() == (directory / "rustc.stdout").read_bytes() + (directory / "cargo.stdout").read_bytes(), "original toolchain bytes")
    require((directory / "cargo.stdout").read_text().startswith("cargo 1.98.1 "), "cargo version")
    require(manifest["disk_floor_bytes"] == 1024**3 + 32*1024**2 and all(type(x) is int and x >= 1024**3 + 32*1024**2 for phase in ("disk_start", "disk_end") for x in manifest[phase].values()), "disk floor")
    execution_root = directory.resolve() if recorded_execution_root is None else Path(recorded_execution_root)
    require(execution_root.is_absolute() and str(execution_root) == str(execution_root.resolve()) and ".." not in execution_root.parts, "canonical recorded execution root")
    build_roots = [p for p in execution_root.parents if p.name == "_build"]
    require(len(build_roots) == 1, "one ignored build root required")
    expected_build = ["cargo", "+1.98.1", "build", "--locked", "--manifest-path", str(build_roots[0] / ("nested-deferred-fitting-build-" + manifest["run_token"]) / "adapter/Cargo.toml")]
    expected_execute = [str(execution_root / "probe"), str(execution_root / "scenarios.json"), manifest["run_token"]]
    require(manifest["build"]["command"] in (expected_build, expected_build + ["--offline"]), "exact build command")
    require(manifest["execution"]["command"] == expected_execute, "execution executable/input/token")
    plan = load_json(directory / "build-plan.json")
    require(plan == {"schema_version": 1, "layer": LAYER, "run_token": manifest["run_token"],
        "build_command": manifest["build"]["command"], "execution_command": expected_execute,
        "environment": {"CARGO_BUILD_JOBS": "2", "CARGO_INCREMENTAL": "0", "DISPLAY": None, "WAYLAND_DISPLAY": None},
        "input_sha256": digest(directory / "scenarios.json"), "lock_sha256": digest(directory / retained_path("adapters/nested_deferred_fitting_rust/Cargo.lock")),
        "build_manifest_sha256": digest(directory / "build-Cargo.toml"), "toolchain_sha256": digest(directory / "toolchain.txt")}, "build plan binding")
    require(manifest["environment"] == plan["environment"], "build environment binding")
    result = verify_observations(raw, corpus, load_json(directory / retained_path("diagnostics/nested_deferred_fitting/raw.schema.json")))
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
