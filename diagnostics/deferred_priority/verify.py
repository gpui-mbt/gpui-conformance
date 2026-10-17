#!/usr/bin/env python3
"""Inspect retained real GPUI observations; source-derived predictions are never raw evidence."""
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
SUITE_BASE = "550e7f9a62190a31a76bd61a1de44fbf3944acf1"
SUITE_BASE_TREE = "930d673885e3eb21f2656fd6ef28413ae7a49fba"
LAYER = "supplemental-headless-deferred-priority"
RETAIN = ["adapters/deferred_priority_rust/Cargo.toml", "adapters/deferred_priority_rust/Cargo.lock",
    "adapters/deferred_priority_rust/src/main.rs", "diagnostics/deferred_priority/scenarios.json",
    "diagnostics/deferred_priority/profile.json", "diagnostics/deferred_priority/raw.schema.json",
    "diagnostics/deferred_priority/run.py", "diagnostics/deferred_priority/verify.py",
    "diagnostics/deferred_priority/README.md", "tests/test_deferred_priority_diagnostic.py",
    ".github/workflows/deferred-priority-diagnostic.yml"]
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


def validate_interaction(config):
    require(set(config) == {"listener", "propagation", "occlude"}, "interaction shape")
    require(config["listener"] in ("none", "bubble-left-mouse-down") and config["propagation"] in ("continue", "stop")
            and type(config["occlude"]) is bool, "interaction domain")
    require(config["listener"] != "none" or config == {"listener": "none", "propagation": "continue", "occlude": False}, "noninteractive layer configuration")


def validate_scenarios(corpus):
    require(set(corpus) == {"schema_version", "coordinate_system", "cases"} and type(corpus["schema_version"]) is int and corpus["schema_version"] == 1, "input schema")
    require(isinstance(corpus["coordinate_system"], str) and corpus["coordinate_system"], "coordinate system")
    require(isinstance(corpus["cases"], list) and 1 <= len(corpus["cases"]) <= 32, "case count")
    ids = set()
    for case in corpus["cases"]:
        require(set(case) == {"id", "window", "scale_factor", "position", "size", "probe_position", "ordinary_interaction", "layers", "update_layer", "update_priority"}, "case shape")
        require(isinstance(case["id"], str) and re.fullmatch(r"[a-z0-9.-]+", case["id"]) and case["id"] not in ids, "case id")
        ids.add(case["id"])
        # Deliberately bounded first-stage fixture, not general geometry support.
        for field, expected in (("window", [320, 240]), ("position", [48, 48]), ("size", [128, 96]), ("probe_position", [88, 80])):
            vector(case[field], expected, field, 0)
        number(case["scale_factor"], "scale"); require(case["scale_factor"] in (1, 1.25), "scale domain")
        validate_interaction(case["ordinary_interaction"])
        require(case["ordinary_interaction"] == {"listener": "bubble-left-mouse-down", "propagation": "continue", "occlude": False}, "ordinary interaction")
        require(isinstance(case["layers"], list) and len(case["layers"]) == 3 and {x["id"] for x in case["layers"]} == {"a", "b", "c"}, "flat layer identities")
        for layer in case["layers"]:
            require(set(layer) == {"id", "priority", "transparent", "interaction"}, "layer shape")
            require(type(layer["priority"]) is int and layer["priority"] in (0, 1, 2) and type(layer["transparent"]) is bool, "layer domain")
            validate_interaction(layer["interaction"])
            require(not layer["transparent"] or layer["interaction"]["listener"] == "none", "transparent layer explicitly noninteractive")
        require(case["update_layer"] in {x["id"] for x in case["layers"]} and type(case["update_priority"]) is int and case["update_priority"] in (0, 1, 2), "update domain")
        target = next(x for x in case["layers"] if x["id"] == case["update_layer"])
        require(target["priority"] != case["update_priority"], "update must change priority")


def active_layers(case, stage):
    return [dict(layer, priority=case["update_priority"] if stage in ("updated", "removed") and layer["id"] == case["update_layer"] else layer["priority"])
            for layer in case["layers"] if stage != "removed" or layer["id"] != case["update_layer"]]


def derived_lifecycle(case, stage):
    """Checker-side pinned-source hypothesis; never emitted by the Rust observer."""
    structural = active_layers(case, stage)
    ordered = sorted(structural, key=lambda layer: layer["priority"])
    events = []
    def visit(phase, node, children=()):
        events.append((phase, node))
        for child in children: child()
        events.append((phase + "_end", node))
    def attachment(phase, layer):
        prefix = layer["id"]
        visit(phase, prefix + ".anchor", [lambda: visit(phase, prefix + ".root", [
            lambda: visit(phase, prefix + ".first"), lambda: visit(phase, prefix + ".second")])])
    for phase in ("request_layout", "prepaint", "paint"):
        def host_children():
            visit(phase, "ordinary.before")
            for layer in structural:
                visit(phase, layer["id"] + ".deferred", [lambda layer=layer: attachment(phase, layer)] if phase == "request_layout" else [])
            visit(phase, "ordinary.after")
        visit(phase, "$host", [host_children])
        if phase != "request_layout":
            for layer in ordered: attachment(phase, layer)
    return events, [layer["id"] for layer in ordered]


def verify_frame(entries, case, stage, scale):
    require(entries[0]["event"] == {"type": "frame_start", "scale_factor": scale, "window_size": case["window"], "client_inset": None}, "frame viewport/scale/inset")
    predicted, predicted_layers = derived_lifecycle(case, stage)
    observed = [(entry["event"]["type"], entry["event"].get("node")) for entry in entries[1:]]
    require(observed == predicted, "exact lifecycle order/IDs/return boundaries")
    prepaint, paint = {}, {}
    for entry in entries[1:]:
        event = entry["event"]; phase, node = event["type"], event["node"]
        if phase not in ("prepaint", "paint"): continue
        physical_grid(event["bounds"], scale)
        vector(event["content_mask"], [0, 0, *case["window"]], "observed viewport content mask", 0)
        (prepaint if phase == "prepaint" else paint)[node] = event
    vector(prepaint["$host"]["bounds"], [0, 0, *case["window"]], "host geometry")
    for node in ("ordinary.before", "ordinary.after"):
        vector(prepaint[node]["bounds"], [*case["position"], *case["size"]], "ordinary geometry")
        vector(prepaint[node]["element_offset"], [0, 0], "ordinary logical offset", 0)
    vector(prepaint["$host"]["element_offset"], [0, 0], "host logical offset", 0)
    for layer in active_layers(case, stage):
        prefix = layer["id"]
        static = prepaint[prefix + ".anchor"]["bounds"]
        vector(prepaint[prefix + ".deferred"]["bounds"], static, "deferred shared layout", 0)
        vector(static[2:], case["size"], "attachment measured size")
        for suffix in ("anchor", "deferred"):
            vector(prepaint[prefix + "." + suffix]["element_offset"], [0, 0], "outer offset", 0)
        # Qualified integral positions make anchor offset independent of device rounding.
        logical = [case["position"][axis] - static[axis] for axis in (0, 1)]
        require(all(value == round(value) for value in logical), "qualified integral static origin")
        for suffix, offset, dimensions in (("root", [0, 0], case["size"]), ("first", [0, 0], [80, 64]), ("second", [24, 16], [80, 64])):
            node = prefix + "." + suffix
            vector(prepaint[node]["bounds"], [case["position"][a] + offset[a] for a in (0, 1)] + dimensions, "subtree geometry")
            vector(prepaint[node]["element_offset"], logical, "observed attachment offset", 0)
    for node in prepaint:
        vector(paint[node]["bounds"], prepaint[node]["bounds"], "paint/prepaint geometry", 0)
    return {"frame": entries[0]["frame"], "scale_factor": scale,
        "observed_request_layout_order": [node for phase, node in observed if phase == "request_layout"],
        "observed_prepaint_order": list(prepaint), "observed_paint_order": list(paint),
        "observed_prepaint": prepaint, "observed_paint": paint,
        "checker_derivation_not_observation": {"flat_stable_priority_order": predicted_layers,
            "method": "pinned deferred.rs/window.rs flat-round stable priority sorting; exact subtree callback boundaries"}}


def interaction_for(case, node):
    if node in ("ordinary.before", "ordinary.after"): return case["ordinary_interaction"]
    parts = node.split(".")
    if len(parts) == 2 and parts[1] in ("root", "first", "second"):
        return next((layer["interaction"] for layer in case["layers"] if layer["id"] == parts[0]), None)
    return None


def derive_input_from_observed_frame(case, frame):
    """Separate source-derived prediction, NOT a candidate-core reverse-paint hit test.

    GPUI window.rs hit_test uses reverse PREPAINT hitboxes and BlockMouse;
    dispatch_mouse_event separately reverses PAINT-registered bubble listeners.
    div.rs installs the explicit listener and occlusion configuration below.
    """
    point = case["probe_position"]
    hovered = []
    for node in reversed(frame["observed_prepaint_order"]):
        config = interaction_for(case, node)
        if config is None or (config["listener"] == "none" and not config["occlude"]): continue
        event = frame["observed_prepaint"][node]; bounds, mask = event["bounds"], event["content_mask"]
        if all(max(bounds[a], mask[a]) <= point[a] < min(bounds[a] + bounds[a + 2], mask[a] + mask[a + 2]) for a in (0, 1)):
            hovered.append(node)
            if config["occlude"]: break
    callbacks = []
    for node in reversed(frame["observed_paint_order"]):
        config = interaction_for(case, node)
        if node not in hovered or config is None or config["listener"] == "none": continue
        callbacks.append(node)
        if config["propagation"] == "stop": break
    return {"hovered_hitboxes_from_observed_prepaint": hovered, "bubble_callbacks_from_observed_paint_registration": callbacks,
            "method": "pinned GPUI hitbox occlusion and bubble listener dispatch; no topmost-only or core hit-test assumption"}


def operation_plan(case):
    yield "initial", {"action": "open_window"}, "base", 2, False
    for stage in ("base", "updated", "removed", "restored"):
        action = {"base": {"action": "set_scale_factor", "scale_factor": case["scale_factor"]},
            "updated": {"action": "set_priority", "layer": case["update_layer"], "priority": case["update_priority"]},
            "removed": {"action": "remove_layer", "layer": case["update_layer"]},
            "restored": {"action": "restore_original_layers"}}[stage]
        yield stage, action, stage, case["scale_factor"], False
        yield stage + ".input", {"action": "left_click", "position": case["probe_position"]}, stage, case["scale_factor"], True


def verify_observations(raw, corpus, schema=None):
    schema = load_json(ROOT / "diagnostics/deferred_priority/raw.schema.json") if schema is None else schema
    try: Draft202012Validator(schema).validate(raw)
    except ValidationError as error: raise ValueError("raw schema: " + error.message) from error
    validate_scenarios(corpus)
    require(raw["input"] == corpus, "raw input mismatch")
    require([c["id"] for c in raw["cases"]] == [c["id"] for c in corpus["cases"]], "case IDs/order")
    results = []
    for observed, case in zip(raw["cases"], corpus["cases"]):
        entries = observed["events"]
        require([e["sequence"] for e in entries] == list(range(len(entries))), "event sequence")
        cursor, frame_id, last_frame = 0, 0, None
        operations = []
        for name, action, stage, scale, is_input in operation_plan(case):
            require(cursor < len(entries), "missing operation")
            start = entries[cursor]; cursor += 1
            require(start == {"sequence": cursor - 1, "operation": name, "frame": frame_id,
                "event": {"type": "operation_start", "input": action}}, "operation start/input/frame")
            pending, frames, callbacks, prediction = [], [], [], None
            if is_input:
                require(last_frame is not None, "input before rendered frame")
                prediction = derive_input_from_observed_frame(case, last_frame)
            while cursor < len(entries) and entries[cursor]["event"]["type"] != "operation_end":
                entry = entries[cursor]; cursor += 1
                require(entry["operation"] == name, "operation interleaving")
                kind = entry["event"]["type"]
                if kind == "frame_start":
                    if pending: frames.append(verify_frame(pending, case, stage, scale))
                    pending = []; frame_id += 1
                require(entry["frame"] == frame_id, "frame sequence")
                if kind == "mouse_down":
                    require(is_input, "callback outside input operation")
                    if pending: frames.append(verify_frame(pending, case, stage, scale)); pending = []
                    event = entry["event"]; config = interaction_for(case, event["node"])
                    require(config is not None and config["listener"] != "none", "callback without listener")
                    require(event == {"type": "mouse_down", "node": event["node"], "position": case["probe_position"],
                        "button": "Left", "phase": "Bubble", **config}, "callback configuration/position")
                    callbacks.append(event)
                else:
                    require(pending or kind == "frame_start", "lifecycle outside frame")
                    pending.append(entry)
            if pending: frames.append(verify_frame(pending, case, stage, scale))
            require(is_input or frames, "missing required redraw")
            if frames: last_frame = frames[-1]
            require(cursor < len(entries), "missing operation end")
            end = entries[cursor]; cursor += 1
            require(end == {"sequence": cursor - 1, "operation": name, "frame": frame_id,
                "event": {"type": "operation_end", "scale_factor": scale}}, "operation end/scale/frame")
            if is_input:
                require([c["node"] for c in callbacks] == prediction["bubble_callbacks_from_observed_paint_registration"], "actual callback sequence differs from pinned GPUI listener/occlusion derivation")
            operations.append({"id": name, "frames": frames, "observed_input_callbacks": callbacks,
                "checker_input_derivation_not_observation": prediction})
        require(cursor == len(entries), "trailing operations/events")
        results.append({"id": case["id"], "operations": operations})
    return {"schema_version": 1, "layer": LAYER, "cases": results, "case_count": len(results),
        "observed_frame_count": sum(len(op["frames"]) for c in results for op in c["operations"]),
        "claim": "Actual public GPUI flat deferred lifecycle, geometry/masks and authored input callbacks only; no nesting, outside-click, cache, arbitrary content, unchanged popover, core, browser, raster or native-window parity."}


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
    profile = load_json(strict_file(directory, retained_path("diagnostics/deferred_priority/profile.json")))
    require(profile["layer"] == LAYER and profile["suite_base"] == SUITE_BASE and profile["upstream_commit"] == UPSTREAM
            and profile["upstream_tree"] == UPSTREAM_TREE and profile["suite_base_tree"] == SUITE_BASE_TREE, "profile source identity")
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
    require((directory / "scenarios.json").read_bytes() == (directory / retained_path("diagnostics/deferred_priority/scenarios.json")).read_bytes(), "retained/run scenario mismatch")
    require(digest(directory / "scenarios.json") == profile["input_sha256"], "profile/input hash mismatch")
    require((directory / "raw.stdout").read_bytes() == (directory / "raw.json").read_bytes(), "original raw stdout bytes changed")
    require(profile["geometry_allowance_logical_px"] == GEOMETRY_F32_ALLOWANCE and profile["physical_grid_allowance_px"] == PHYSICAL_GRID_F32_ALLOWANCE and profile["order_and_ids_allowance"] == 0, "predeclared comparison budget")
    corpus = load_json(directory / "scenarios.json")
    require(len(corpus["cases"]) == profile["case_count"], "profile/case count")
    require((directory / "build-Cargo.lock").read_bytes() == (directory / retained_path("adapters/deferred_priority_rust/Cargo.lock")).read_bytes(), "locked build changed dependency lock")
    original = (directory / retained_path("adapters/deferred_priority_rust/Cargo.toml")).read_text()
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
    require(manifest["disk_floor_bytes"] == 1024**3 and all(type(x) is int and x >= 1024**3 for phase in ("disk_start", "disk_end") for x in manifest[phase].values()), "disk floor")
    execution_root = directory.resolve() if recorded_execution_root is None else Path(recorded_execution_root)
    require(execution_root.is_absolute() and str(execution_root) == str(execution_root.resolve()) and ".." not in execution_root.parts, "canonical recorded execution root")
    build_roots = [p for p in execution_root.parents if p.name == "_build"]
    require(len(build_roots) == 1, "one ignored build root required")
    expected_build = ["cargo", "+1.98.1", "build", "--locked", "--manifest-path", str(build_roots[0] / ("deferred-priority-build-" + manifest["run_token"]) / "adapter/Cargo.toml")]
    expected_execute = [str(execution_root / "probe"), str(execution_root / "scenarios.json"), manifest["run_token"]]
    require(manifest["build"]["command"] in (expected_build, expected_build + ["--offline"]), "exact build command")
    require(manifest["execution"]["command"] == expected_execute, "execution executable/input/token")
    plan = load_json(directory / "build-plan.json")
    require(plan == {"schema_version": 1, "layer": LAYER, "run_token": manifest["run_token"],
        "build_command": manifest["build"]["command"], "execution_command": expected_execute,
        "environment": {"CARGO_BUILD_JOBS": "2", "CARGO_INCREMENTAL": "0", "DISPLAY": None, "WAYLAND_DISPLAY": None},
        "input_sha256": digest(directory / "scenarios.json"), "lock_sha256": digest(directory / retained_path("adapters/deferred_priority_rust/Cargo.lock")),
        "build_manifest_sha256": digest(directory / "build-Cargo.toml"), "toolchain_sha256": digest(directory / "toolchain.txt")}, "build plan binding")
    require(manifest["environment"] == plan["environment"], "build environment binding")
    result = verify_observations(raw, corpus, load_json(directory / retained_path("diagnostics/deferred_priority/raw.schema.json")))
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
