#!/usr/bin/env python3
"""Inspect actual anchor/deferred lifecycle output; checker fixtures are not GPUI output."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess

UPSTREAM = "5a5fbe79917971a4d52a96b6ddb04da198a5012e"
UPSTREAM_TREE = "990fb995914d51a546b20e5cf0382dafc105c299"
LAYER = "supplemental-headless-anchor-deferred"
RETAIN = ["adapters/anchor_rust/Cargo.toml", "adapters/anchor_rust/Cargo.lock",
    "adapters/anchor_rust/src/main.rs", "diagnostics/anchor/scenarios.json",
    "diagnostics/anchor/raw.schema.json", "diagnostics/anchor/run.py", "diagnostics/anchor/verify.py",
    "diagnostics/anchor/README.md", "diagnostics/anchor/epsilon-regression.json", "tests/test_anchor_diagnostic.py", ".github/workflows/anchor-diagnostic.yml"]
UPSTREAM_RETAIN = ["Cargo.toml", "Cargo.lock", "rust-toolchain.toml", "crates/gpui/Cargo.toml",
    "crates/gpui/src/elements/anchored.rs", "crates/gpui/src/elements/deferred.rs", "crates/gpui/src/elements/div.rs",
    "crates/gpui/src/element.rs", "crates/gpui/src/styled.rs", "crates/gpui/src/style.rs",
    "crates/gpui/src/taffy.rs", "crates/gpui/src/util.rs", "crates/gpui/src/geometry.rs", "crates/gpui/src/window.rs",
    "crates/gpui/src/app.rs", "crates/gpui/src/app/test_context.rs", "crates/gpui/src/keymap/context.rs",
    "crates/gpui/src/interactive.rs", "crates/gpui/src/platform/test/platform.rs",
    "crates/gpui/src/platform/test/window.rs", "crates/gpui/examples/anchor.rs"]
ANCHORS = {"TopLeft": (0, 0), "TopCenter": (.5, 0), "TopRight": (1, 0),
    "LeftCenter": (0, .5), "RightCenter": (1, .5), "BottomLeft": (0, 1),
    "BottomCenter": (.5, 1), "BottomRight": (1, 1)}

# Numerical eligibility for this fixed font-free corpus, not a layout witness.
# Derivation and logical/physical units are documented in README.md.
RAW_COORDINATE_LIMIT = 4096
RAW_SIZE_LIMIT = 2048
RAW_FAR_EDGE_LIMIT = 4096
GEOMETRY_F32_ALLOWANCE = 2 ** -10  # logical pixels
PHYSICAL_GRID_F32_ALLOWANCE = 2 ** -10  # device pixels

def retained_path(relative):
    return "retained/workflows/anchor-diagnostic.yml" if relative == RETAIN[-1] else "retained/" + relative

def require(condition, message):
    if not condition: raise ValueError(message)

def number(value, label):
    require(type(value) in (int, float) and math.isfinite(value), label + ": finite number required")

def close(actual, expected, label, allowance=GEOMETRY_F32_ALLOWANCE):
    number(actual, label)
    number(expected, label + " expected")
    require(abs(actual - expected) <= allowance, f"{label}: {actual} != {expected}; allowance {allowance}")

def vector(actual, expected, label, allowance=GEOMETRY_F32_ALLOWANCE):
    require(isinstance(actual, list) and len(actual) == len(expected), label + ": vector shape")
    for index, (a, b) in enumerate(zip(actual, expected)): close(a, b, label + f"[{index}]", allowance)

def exact_scale(actual, expected, label):
    number(actual, label)
    require(actual == expected, label + ": requested binary-exact scale mismatch")

def qualify_bounds(rectangle, label):
    require(isinstance(rectangle, list) and len(rectangle) == 4, label + ": bounds shape")
    for value in rectangle: number(value, label)
    require(all(abs(value) <= RAW_COORDINATE_LIMIT for value in rectangle[:2]), label + ": numerically unqualified raw coordinate")
    require(all(0 <= value <= RAW_SIZE_LIMIT for value in rectangle[2:]), label + ": numerically unqualified raw size")
    require(all(abs(rectangle[axis] + rectangle[axis + 2]) <= RAW_FAR_EDGE_LIMIT for axis in (0, 1)), label + ": numerically unqualified raw far edge")

def physical_grid(rectangle, scale, label):
    qualify_bounds(rectangle, label)
    for edge in (rectangle[0], rectangle[1], rectangle[0] + rectangle[2], rectangle[1] + rectangle[3]):
        physical = edge * scale
        close(physical, round(physical), label + " physical edge", PHYSICAL_GRID_F32_ALLOWANCE)

def bounded(values, count, low, high, label):
    require(isinstance(values, list) and len(values) == count, label + ": vector shape")
    for value in values:
        number(value, label)
        require(low <= value <= high and value * 4 == int(value * 4), label + ": bounded quarter pixels")

def validate_scenarios(corpus):
    require(set(corpus) == {"schema_version", "coordinate_system", "cases"} and corpus["schema_version"] == 1, "input schema")
    require(isinstance(corpus["coordinate_system"], str) and corpus["coordinate_system"], "coordinate system")
    require(isinstance(corpus["cases"], list) and 1 <= len(corpus["cases"]) <= 32, "bounded case count")
    identifiers = set()
    for case in corpus["cases"]:
        require(set(case) == {"id", "window", "parent_origin", "parent_size", "scale_factor", "popups", "later_sibling", "hits"}, "case shape")
        require(isinstance(case["id"], str) and case["id"] and case["id"] not in identifiers, "case id")
        identifiers.add(case["id"])
        bounded(case["window"], 2, 1, 2048, "window")
        bounded(case["parent_origin"], 2, 0, 2048, "parent origin")
        bounded(case["parent_size"], 2, 1, 1024, "parent size")
        number(case["scale_factor"], "scale")
        require(case["scale_factor"] in (1, 1.25, 2), "scale")
        require(isinstance(case["popups"], list) and 1 <= len(case["popups"]) <= 4, "bounded flat popup count")
        names = {"button", "sibling", "parent"}
        for popup in case["popups"]:
            require(set(popup) == {"id", "anchor", "position", "position_mode", "size", "priority", "interactive"}, "popup shape")
            require(isinstance(popup["id"], str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", popup["id"]) and not popup["id"].startswith(("anchor_", "deferred_")) and popup["id"] not in names, "popup id")
            names.add(popup["id"])
            require(popup["anchor"] in ANCHORS and popup["position_mode"] in ("Local", "Window"), "anchor/position mode")
            bounded(popup["position"], 2, -2048, 2048, "anchor position")
            bounded(popup["size"], 2, 1, 1024, "popup size")
            require(type(popup["priority"]) is int and popup["priority"] == 0, "only flat priority-zero ties supported")
            require(type(popup["interactive"]) is bool, "interactive bool")
        if case["later_sibling"] is not None:
            bounded(case["later_sibling"], 4, 0, 2048, "later sibling")
            require(min(case["later_sibling"][2:]) > 0, "sibling size")
        require(isinstance(case["hits"], list) and len(case["hits"]) <= 8, "bounded hits")
        hit_ids = {"initial", "configured"}
        for hit in case["hits"]:
            require(set(hit) == {"id", "position"} and isinstance(hit["id"], str) and hit["id"] and hit["id"] not in hit_ids, "hit shape/id")
            hit_ids.add(hit["id"])
            bounded(hit["position"], 2, 0, 2048, "hit")

def inside(position, rectangle):
    return rectangle[0] < position[0] < rectangle[0] + rectangle[2] and rectangle[1] < position[1] < rectangle[1] + rectangle[3]

def on_edge(position, rectangle):
    x, y = position
    return ((x in (rectangle[0], rectangle[0] + rectangle[2]) and rectangle[1] <= y <= rectangle[1] + rectangle[3])
        or (y in (rectangle[1], rectangle[1] + rectangle[3]) and rectangle[0] <= x <= rectangle[0] + rectangle[2]))

def round_away(value):
    return math.floor(value + .5) if value >= 0 else math.ceil(value - .5)

def snap_offset(value, scale):
    physical = value * scale
    return math.copysign(math.ceil(abs(physical) - .5), physical) / scale

def node_names(case):
    result = {"$host", "parent", "button"}
    if case["later_sibling"] is not None: result.add("sibling")
    for popup in case["popups"]: result.update((popup["id"], "anchor_" + popup["id"], "deferred_" + popup["id"]))
    return result

def verify_frame(entries, case, scale):
    label = case["id"] + f"/frame-{entries[0]['frame']}"
    first = entries[0]["event"]
    require(set(first) == {"type", "scale_factor", "window_size"} and first["type"] == "frame_start", label + ": frame start")
    exact_scale(first["scale_factor"], scale, label + " scale")
    vector(first["window_size"], case["window"], label + " viewport", 0)
    names = node_names(case)
    stack, phases, prepaint, painted, locations, parents = [], {}, {}, [], {}, {}
    for index, entry in enumerate(entries[1:], 1):
        event = entry["event"]
        kind, node = event["type"], event.get("node")
        require(node in names, label + ": unknown node")
        require(set(event) == ({"type", "node", "bounds", "content_mask"} if kind == "prepaint" else {"type", "node", "bounds"} if kind == "paint" else {"type", "node"}), label + ": lifecycle event shape")
        locations[kind, node] = index
        if kind in ("request_layout", "prepaint", "paint"):
            expected_phase = {"request_layout": 0, "prepaint": 2, "paint": 4}[kind]
            require(phases.get(node, 0) == expected_phase, label + ": repeated/out-of-order lifecycle")
            phases[node] = expected_phase + 1
            parents[kind, node] = stack[-1][1] if stack else None
            stack.append((kind, node))
            if kind in ("prepaint", "paint"):
                rectangle = event["bounds"]
                # Qualify the raw domain before applying the separately named
                # device-pixel grid allowance. This is not a static-origin witness.
                physical_grid(rectangle, scale, label)
                if kind == "prepaint":
                    qualify_bounds(event["content_mask"], label + " mask")
                    vector(event["content_mask"], [0, 0, *case["window"]], label + " content mask", 0)
                    prepaint[node] = event
                else:
                    vector(rectangle, prepaint[node]["bounds"], label + " paint/prepaint agreement", 0)
                    painted.append(node)
        elif kind in ("request_layout_end", "prepaint_end", "paint_end"):
            phase = kind[:-4]
            require(stack and stack.pop() == (phase, node), label + ": lifecycle return nesting")
            phases[node] += 1
        else: require(False, label + ": unknown lifecycle event")
    require(not stack and set(phases) == names and all(value == 6 for value in phases.values()), label + ": incomplete lifecycle")
    vector(prepaint["$host"]["bounds"], [0, 0, *case["window"]], label + " host")
    # This verifies ordinary authored host placement, never the absolute anchor's
    # unresolved block static-position origin. The latter remains raw evidence.
    vector(prepaint["parent"]["bounds"], [*case["parent_origin"], *case["parent_size"]], label + " parent")
    vector(prepaint["button"]["bounds"], [*case["parent_origin"], 120, math.ceil(65 * scale - .5) / scale], label + " button")
    for phase in ("request_layout", "prepaint", "paint"):
        expected_parents = {"$host": None, "parent": "$host", "button": "parent"}
        if case["later_sibling"] is not None: expected_parents["sibling"] = "$host"
        for popup in case["popups"]:
            expected_parents["deferred_" + popup["id"]] = "parent"
            expected_parents["anchor_" + popup["id"]] = "deferred_" + popup["id"] if phase == "request_layout" else None
            expected_parents[popup["id"]] = "anchor_" + popup["id"]
        require({node: parents[phase, node] for node in names} == expected_parents, label + ": observed lifecycle ancestry")
    for popup in case["popups"]:
        identifier = popup["id"]
        anchor_node, deferred_node = "anchor_" + identifier, "deferred_" + identifier
        static = prepaint[anchor_node]["bounds"]
        vector(prepaint[deferred_node]["bounds"], static, label + " shared deferred/anchored layout", 0)
        child = prepaint[identifier]["bounds"]
        vector(child[2:], static[2:], label + " child measured size", 0)
        # The corpus isolates anchor translation with integral physical sizes.
        vector(child[2:], popup["size"], label + " authored fixed popup size")
        fractions = ANCHORS[popup["anchor"]]
        desired = [popup["position"][axis] + (static[axis] if popup["position_mode"] == "Local" else 0)
            - fractions[axis] * child[axis + 2] for axis in (0, 1)]
        # Ordered right/bottom adjustment followed by left/top handles oversized
        # content; this small independently written checker uses observed sizes.
        desired = [max(0, min(desired[axis], case["window"][axis] - child[axis + 2])) for axis in (0, 1)]
        expected = [static[axis] + snap_offset(round_away(desired[axis] - static[axis]), scale) for axis in (0, 1)]
        vector(child[:2], expected, label + " anchor translation/clamp/logical rounding/device offset snap")
        require(locations["prepaint_end", "$host"] < locations["prepaint", anchor_node], label + ": child prepaint was not deferred")
        require(locations["paint_end", "$host"] < locations["paint", anchor_node], label + ": child paint was not deferred")
        for phase in ("request_layout", "prepaint", "paint"):
            require(locations[phase, anchor_node] < locations[phase, identifier] < locations[phase + "_end", anchor_node], label + ": popup lifecycle ancestry")
    ordered = [popup["id"] for popup in case["popups"]]
    require([node for node in painted if node in ordered] == ordered, label + ": flat stable deferred paint ties")
    require([entry["event"]["node"] for entry in entries if entry["event"]["type"] == "prepaint" and entry["event"]["node"] in ordered] == ordered, label + ": flat stable deferred prepaint ties")
    if case["later_sibling"] is not None:
        vector(prepaint["sibling"]["bounds"], case["later_sibling"], label + " authored sibling")
    interactive = {"button"} | {popup["id"] for popup in case["popups"] if popup["interactive"]}
    if case["later_sibling"] is not None: interactive.add("sibling")
    return {"frame": entries[0]["frame"], "scale_factor": scale,
        "bounds": {node: event["bounds"] for node, event in prepaint.items()},
        "painted_nodes": painted, "interactive_leaves": [prepaint[node] for node in painted if node in interactive],
        "anchor_static_origins": {popup["id"]: prepaint["anchor_" + popup["id"]]["bounds"][:2] for popup in case["popups"]}}

def verify_observations(raw, corpus):
    validate_scenarios(corpus)
    require(set(raw) == {"schema_version", "layer", "fixture", "text_system", "upstream_revision", "run_token", "input", "cases"}, "raw shape")
    require(raw["schema_version"] == 1 and raw["layer"] == LAYER, "raw layer/schema")
    require(raw["fixture"] == "font-free-bounded-anchor" and raw["text_system"] == "NoopTextSystem; no text used", "fixture/text claim")
    require(raw["upstream_revision"] == UPSTREAM, "wrong engine pin")
    require(isinstance(raw["run_token"], str) and len(raw["run_token"]) >= 16, "run token")
    require(raw["input"] == corpus, "input mismatch")
    require([observed["id"] for observed in raw["cases"]] == [case["id"] for case in corpus["cases"]], "case ordering/coverage")
    summaries = []
    for observed, case in zip(raw["cases"], corpus["cases"]):
        require(set(observed) == {"id", "events"}, "case output shape")
        events = observed["events"]
        require(all(set(entry) == {"sequence", "operation", "frame", "event"} for entry in events), "entry shape")
        require([entry["sequence"] for entry in events] == list(range(len(events))), "event sequence")
        operations = [("initial", {"action": "open_window"}), ("configured", {"action": "set_scale_factor", "scale_factor": case["scale_factor"]})]
        operations += [(hit["id"], {"action": "click", "position": hit["position"]}) for hit in case["hits"]]
        cursor, frame_number, latest, result = 0, 0, None, []
        for operation, input_value in operations:
            require(cursor < len(events), "missing operation")
            start = events[cursor]
            require(start["operation"] == operation and start["event"] == {"type": "operation_start", "input": input_value} and start["frame"] == frame_number, "operation start/input/frame")
            cursor += 1
            frames, callbacks, pending = [], [], []
            hit_frame = latest
            scale = 2 if operation == "initial" else case["scale_factor"]
            while cursor < len(events) and events[cursor]["event"]["type"] != "operation_end":
                entry = events[cursor]; cursor += 1
                require(entry["operation"] == operation, "operation interleaving")
                kind = entry["event"]["type"]
                if kind == "frame_start":
                    if pending:
                        latest = verify_frame(pending, case, scale); frames.append(latest)
                    pending = []
                    frame_number += 1
                require(entry["frame"] == frame_number, "frame sequence")
                if kind in ("mouse_down", "click"):
                    if pending:
                        latest = verify_frame(pending, case, scale); frames.append(latest); pending = []
                    require(input_value["action"] == "click", "unexpected pointer callback")
                    callbacks.append(entry["event"])
                else:
                    require(pending or kind == "frame_start", "lifecycle outside frame")
                    pending.append(entry)
            if pending:
                latest = verify_frame(pending, case, scale); frames.append(latest)
            require(cursor < len(events), "unfinished operation")
            end = events[cursor]; cursor += 1
            require(end["operation"] == operation and end["frame"] == frame_number and set(end["event"]) == {"type", "scale_factor"}, "operation end")
            exact_scale(end["event"]["scale_factor"], scale, "operation scale")
            if operation in ("initial", "configured"): require(frames, "required redraw absent")
            if input_value["action"] == "click":
                require(hit_frame is not None, "no rendered hit frame")
                position = input_value["position"]
                for leaf in hit_frame["interactive_leaves"]:
                    require(not on_edge(position, leaf["bounds"]) and not on_edge(position, leaf["content_mask"]), "edge hit excluded from this bounded contract")
                eligible = [leaf["node"] for leaf in hit_frame["interactive_leaves"] if inside(position, leaf["bounds"]) and inside(position, leaf["content_mask"])]
                expected_ids = eligible[-1:]
                require([callback["type"] for callback in callbacks] == (["mouse_down", "click"] if expected_ids else []), "actual callback kind/count/order")
                require([callback["node"] for callback in callbacks] == expected_ids * 2, "actual topmost hit differs from painted interactive leaves")
                if expected_ids:
                    node = expected_ids[0]
                    expected_contexts = ["AnchorRoot"] + ([] if node == "sibling" else ["AnchorParent"]) + ["Leaf_" + node]
                    for callback in callbacks:
                        require(callback["contexts"] == expected_contexts, "actual focused dispatch ancestry")
                        if callback["type"] == "mouse_down":
                            require(set(callback) == {"type", "node", "position", "contexts"}, "mouse callback shape")
                            vector(callback["position"], position, "mouse down", 0)
                        else:
                            require(set(callback) == {"type", "node", "detail", "contexts"} and callback["detail"].get("kind") == "mouse" and set(callback["detail"]) == {"kind", "down", "up"}, "click shape/kind")
                            vector(callback["detail"]["down"], position, "click down", 0)
                            vector(callback["detail"]["up"], position, "click up", 0)
            else: require(not callbacks, "callback without input")
            result.append({"id": operation, "frames": frames, "callbacks": callbacks})
        require(cursor == len(events), "trailing events")
        summaries.append({"id": case["id"], "operations": result})
    return {"schema_version": 1, "layer": LAYER, "cases": summaries,
        "claim": "Actual public GPUI anchor/deferred trace inspection; no unchanged-example, candidate-pair, text/font, screenshot, native-window, or app claim."}

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_bundle(directory, suite_commit=None, suite_tree=None, suite_source=None, upstream_source=None, recorded_execution_root=None):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    require(manifest["schema_version"] == 1 and manifest["layer"] == LAYER, "manifest schema/layer")
    require(manifest["upstream"]["commit"] == UPSTREAM and manifest["upstream"]["tree"] == UPSTREAM_TREE, "source identity")
    require(manifest["upstream"]["clean"] is True and manifest["suite"]["clean"] is True, "dirty provenance")
    require(manifest.get("suite_after") == manifest["suite"] and manifest.get("upstream_after") == manifest["upstream"], "source changed during run")
    require(suite_commit is None or manifest["suite"]["commit"] == suite_commit, "unexpected suite commit")
    require(suite_tree is None or manifest["suite"]["tree"] == suite_tree, "unexpected suite tree")
    for field in ("commit", "tree"):
        require(isinstance(manifest["suite"][field], str) and re.fullmatch("[0-9a-f]{40}", manifest["suite"][field]), "suite identity")
    required = {"raw.json", "raw.stderr", "scenarios.json", "probe", "toolchain.txt", "build.stdout", "build.stderr", "build-Cargo.toml"}
    required |= {retained_path(relative) for relative in RETAIN}
    required |= {"upstream/" + relative for relative in UPSTREAM_RETAIN}
    require(required <= set(manifest["files"]), "missing retained evidence")
    for relative, metadata in manifest["files"].items():
        require(not Path(relative).is_absolute() and ".." not in Path(relative).parts, "unsafe evidence name")
        path = directory / relative
        require(path.is_file() and path.resolve().is_relative_to(directory.resolve()) and not path.is_symlink(), "unsafe evidence path")
        require(digest(path) == metadata["sha256"] and path.stat().st_size == metadata["size"], "changed evidence: " + relative)
    require((directory / "scenarios.json").read_bytes() == (directory / "retained/diagnostics/anchor/scenarios.json").read_bytes(), "retained/run scenario mismatch")
    original_manifest = (directory / "retained/adapters/anchor_rust/Cargo.toml").read_text()
    placeholder = '"../../../zed-source/crates/gpui"'
    require(original_manifest.count(placeholder) == 1, "retained dependency path")
    relocated = original_manifest.replace(placeholder, json.dumps(manifest["upstream_source_path"] + "/crates/gpui"))
    require((directory / "build-Cargo.toml").read_text() == relocated, "build manifest changed beyond relocation")
    for source, identity, prefix, relatives in ((suite_source, manifest["suite"], "retained", RETAIN),
                                               (upstream_source, manifest["upstream"], "upstream", UPSTREAM_RETAIN)):
        if source is not None:
            tree = subprocess.check_output(["git", "rev-parse", identity["commit"] + "^{tree}"], cwd=source, text=True).strip()
            require(tree == identity["tree"], "independent source tree mismatch")
            for relative in relatives:
                expected = subprocess.check_output(["git", "show", identity["commit"] + ":" + relative], cwd=source)
                require((directory / (retained_path(relative) if prefix == "retained" else "upstream/" + relative)).read_bytes() == expected, "retained bytes differ from exact committed source: " + relative)
    require((directory / "probe").read_bytes().startswith(b"\x7fELF"), "probe is not a Linux executable")
    require((directory / "toolchain.txt").read_text().startswith("rustc 1.98.1 "), "compiler provenance")
    raw = json.loads((directory / "raw.json").read_text())
    require(raw["run_token"] == manifest["run_token"], "cross-run trace")
    require(manifest.get("execution", {}).get("returncode") == 0 and manifest["build"]["returncode"] == 0, "failed execution/build")
    require(manifest["execution"]["timed_out"] is False and manifest["build"]["timed_out"] is False, "timed out")
    require(manifest["build"]["command"][:4] == ["cargo", "+1.98.1", "build", "--locked"]
            and "--release" not in manifest["build"]["command"], "build compiler/mode/lock")
    execution_root = directory.resolve() if recorded_execution_root is None else Path(recorded_execution_root)
    require(execution_root.is_absolute() and str(execution_root) == str(execution_root.resolve()) and ".." not in execution_root.parts, "canonical recorded execution root")
    require(manifest["execution"].get("command") == [str(execution_root / "probe"),
            str(execution_root / "scenarios.json"), manifest["run_token"]], "execution executable/input/token")
    build_roots = [p for p in execution_root.parents if p.name == "_build"]
    require(len(build_roots) == 1, "execution root must identify one ignored build root")
    expected_build = ["cargo", "+1.98.1", "build", "--locked", "--manifest-path",
        str(build_roots[0] / ("anchor-build-" + manifest["run_token"]) / "adapter/Cargo.toml")]
    require(manifest["build"]["command"] in (expected_build, expected_build + ["--offline"]), "exact relocated build manifest command")
    result = verify_observations(raw, json.loads((directory / "scenarios.json").read_text()))
    result["source_bound"] = all(value is not None for value in (suite_commit, suite_tree, suite_source, upstream_source))
    result["inspection_scope"] = ("Source-bound retained evidence" if result["source_bound"]
                                  else "Integrity and semantic inspection only; source authenticity unqualified")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--suite-commit", help="Require this independently obtained exact CI checkout commit")
    parser.add_argument("--suite-tree", help="Require this independently obtained exact CI checkout tree")
    parser.add_argument("--suite-source", type=Path, help="Independently compare retained suite files to exact committed Git blobs")
    parser.add_argument("--upstream-source", type=Path, help="Independently compare retained source5a files to exact committed Git blobs")
    parser.add_argument("--recorded-execution-root", type=Path, help="Original canonical absolute run directory for unchanged copied evidence; path consistency is not execution attestation")
    arguments = parser.parse_args()
    result = verify_bundle(arguments.evidence, arguments.suite_commit, arguments.suite_tree, arguments.suite_source, arguments.upstream_source, arguments.recorded_execution_root)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
