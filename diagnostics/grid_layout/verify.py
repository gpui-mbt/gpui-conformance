#!/usr/bin/env python3
"""Independently validate retained actual-GPUI events and curated semantic witnesses."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

UPSTREAM = "5a5fbe79917971a4d52a96b6ddb04da198a5012e"
UPSTREAM_TREE = "990fb995914d51a546b20e5cf0382dafc105c299"
LAYER = "supplemental-headless-grid-container-query"
RETAIN = ["adapters/grid_layout_rust/Cargo.toml", "adapters/grid_layout_rust/Cargo.lock",
    "adapters/grid_layout_rust/src/main.rs", "diagnostics/grid_layout/scenarios.json",
    "diagnostics/grid_layout/witnesses.json", "diagnostics/grid_layout/raw.schema.json",
    "diagnostics/grid_layout/run.py", "diagnostics/grid_layout/verify.py",
    "diagnostics/grid_layout/README.md", "tests/test_grid_layout_diagnostic.py",
    ".github/workflows/grid-layout-diagnostic.yml"]
UPSTREAM_RETAIN = ["Cargo.toml", "Cargo.lock", "rust-toolchain.toml", "crates/gpui/Cargo.toml",
    "crates/gpui/src/elements/container_query.rs", "crates/gpui/src/elements/div.rs",
    "crates/gpui/src/element.rs", "crates/gpui/src/styled.rs", "crates/gpui/src/style.rs",
    "crates/gpui/src/taffy.rs", "crates/gpui/src/geometry.rs", "crates/gpui/src/window.rs",
    "crates/gpui/src/app.rs", "crates/gpui/src/app/test_context.rs",
    "crates/gpui/src/platform/test/platform.rs", "crates/gpui/src/platform/test/window.rs",
    "crates/gpui/examples/grid_layout.rs"]

def retained_path(relative):
    return "retained/workflows/grid-layout-diagnostic.yml" if relative == RETAIN[-1] else "retained/" + relative

def require(condition, message):
    if not condition: raise ValueError(message)

def number(value, label):
    require(type(value) in (int, float) and math.isfinite(value), label + ": finite number required")

def close(actual, expected, label):
    number(actual, label)
    require(abs(actual - expected) <= .01, f"{label}: {actual} != {expected}")

def vector(actual, expected, label):
    require(isinstance(actual, list) and len(actual) == len(expected), label + ": vector shape")
    for index, (a, b) in enumerate(zip(actual, expected)): close(a, b, label + f"[{index}]")

def nodes(root):
    yield root
    for child in root.get("children", []): yield from nodes(child)

def validate_scenarios(corpus):
    require(set(corpus) == {"schema_version", "coordinate_system", "cases"} and corpus["schema_version"] == 1, "input schema")
    require(isinstance(corpus["cases"], list) and 1 <= len(corpus["cases"]) <= 32, "bounded case count")
    identifiers = set()
    common = {"id", "kind", "width", "height", "col_span", "row_span", "col_start", "col_end", "row_start", "row_end", "full_columns"}
    for case in corpus["cases"]:
        require(set(case) in ({"id", "window", "origin", "scale_factor", "root", "hits"}, {"id", "window", "origin", "scale_factor", "root", "hits", "host"}), "case shape")
        if "host" in case:
            require(case["host"] == {"layout": "flex-row", "align_items": "end"} and case["origin"] == [0, 0], "explicit flex-end host")
        require(isinstance(case["id"], str) and case["id"] not in identifiers, "case id")
        identifiers.add(case["id"])
        for field in ("window", "origin"):
            vector(case[field], case[field], field)
            require(len(case[field]) == 2 and all(0 <= n <= 2048 and n * 4 == int(n * 4) for n in case[field]), "bounded quarter-pixel window/origin")
        require(min(case["window"]) > 0 and case["scale_factor"] in (1, 1.25, 2), "window/scale")
        require({"width", "height"} <= set(case["root"]), "root requires assigned dimensions")
        tree = list(nodes(case["root"]))
        require(len(tree) <= 32, "bounded node count")
        names = set()
        def validate(node, depth):
            require(depth <= 5, "bounded nesting")
            require(isinstance(node["id"], str) and node["id"] and node["id"] != "$host" and node["id"] not in names, "node id")
            names.add(node["id"])
            kind = node["kind"]
            allowed = common | ({"cols", "rows", "gap", "children"} if kind == "grid" else {"children"} if kind == "query" else set())
            require(kind in ("grid", "query", "box") and set(node) <= allowed, "node kind/fields")
            if kind == "grid":
                require({"cols", "rows", "gap", "children"} <= set(node), "grid fields")
                for axis in ("cols", "rows"): require(type(node[axis]) is int and 1 <= node[axis] <= (8 if axis == "rows" else 6), "track count")
                number(node["gap"], "gap")
                require(0 <= node["gap"] <= 32 and node["gap"] * 4 == int(node["gap"] * 4), "bounded quarter-pixel gap")
            if kind == "query": require(len(node.get("children", [])) == 1, "query needs one child")
            for field in ("width", "height"):
                if field in node:
                    number(node[field], field)
                    require(0 < node[field] <= 1024 and node[field] * 4 == int(node[field] * 4), "bounded quarter-pixel node size")
            for field in ("col_span", "row_span"):
                if field in node: require(type(node[field]) is int and 1 <= node[field] <= 6, "span bound")
            for field in ("col_start", "col_end", "row_start", "row_end"):
                if field in node: require(type(node[field]) is int and 1 <= abs(node[field]) <= 7, "line bound")
            if "full_columns" in node: require(type(node["full_columns"]) is bool, "full_columns bool")
            require(not (node.get("full_columns") and any(f in node for f in ("col_span", "col_start", "col_end"))), "ambiguous full-column placement")
            for axis in ("col", "row"):
                require(not (axis + "_span" in node and any(axis + suffix in node for suffix in ("_start", "_end"))), "ambiguous span/line placement")
            for child in node.get("children", []): validate(child, depth + 1)
        validate(case["root"], 0)
        hit_ids = {"initial", "configured"}
        require(isinstance(case["hits"], list) and len(case["hits"]) <= 16, "bounded hits")
        for hit in case["hits"]:
            require(set(hit) == {"id", "position"} and isinstance(hit["id"], str) and hit["id"] not in hit_ids, "hit shape/id")
            hit_ids.add(hit["id"])
            require(len(hit["position"]) == 2, "hit shape")
            vector(hit["position"], hit["position"], "hit")
            require(all(abs(n) <= 2048 and n * 4 == int(n * 4) for n in hit["position"]), "bounded quarter-pixel hit")

def inside(position, rect):
    return rect[0] <= position[0] < rect[0] + rect[2] and rect[1] <= position[1] < rect[1] + rect[3]

def verify_frame(entries, case, scale, witnesses):
    label = case["id"] + f"/frame-{entries[0]['frame']}"
    require(entries[0]["event"]["type"] == "frame_start" and entries[-1]["event"]["type"] == "frame_end", label + ": frame boundary")
    by_id = {node["id"]: node for node in nodes(case["root"])}
    by_id["$host"] = {"kind": "host"}
    stack, phases, prepaint, painted, callbacks = [], {}, {}, [], {}
    for entry in entries:
        event = entry["event"]
        kind, node = event["type"], event.get("node")
        if kind in ("frame_start", "frame_end"):
            close(event["scale_factor"], scale, label + " scale")
            vector(event["window_size"], case["window"], label + " window")
            continue
        require(node in by_id, label + ": unknown node")
        if kind in ("request_layout", "prepaint", "paint"):
            expected_phase = {"request_layout": 0, "prepaint": 2, "paint": 4}[kind]
            require(phases.get(node, 0) == expected_phase, label + ": repeated/out-of-order lifecycle")
            phases[node] = expected_phase + 1
            stack.append((kind, node))
            if kind in ("prepaint", "paint"):
                rect = event["bounds"]
                require(isinstance(rect, list) and len(rect) == 4 and min(rect[2:]) >= 0, label + ": bounds shape")
                vector(rect, rect, label + " bounds")
                # Actual source5a bounds must end on device pixels; no logical track solver.
                for edge in (rect[0], rect[1], rect[0] + rect[2], rect[1] + rect[3]):
                    close(edge * scale, round(edge * scale), label + " physical edge")
                if kind == "prepaint":
                    vector(event["content_mask"], [0, 0, *case["window"]], label + " unclipped content mask")
                    prepaint[node] = event
                else:
                    vector(rect, prepaint[node]["bounds"], label + " paint/prepaint agreement")
                    painted.append(node)
        elif kind.endswith("_end"):
            phase = kind[:-4]
            require(stack and stack.pop() == (phase, node), label + ": lifecycle return nesting")
            phases[node] += 1
        elif kind == "callback":
            require(by_id[node]["kind"] == "query" and stack and stack[-1] == ("prepaint", node), label + ": callback must run inside own prepaint")
            require(node not in callbacks, label + ": repeated callback")
            vector(event["size"], prepaint[node]["bounds"][2:], label + " callback assigned size")
            callbacks[node] = event
        else: require(False, label + ": unexpected frame event " + kind)
    require(not stack and set(phases) == set(by_id) and all(value == 6 for value in phases.values()), label + ": incomplete node lifecycle")
    require(set(callbacks) == {key for key, node in by_id.items() if node["kind"] == "query"}, label + ": callback coverage")
    for key in callbacks:
        child = by_id[key]["children"][0]["id"]
        vector(prepaint[child]["bounds"][:2], prepaint[key]["bounds"][:2], label + " query child assigned origin")
        callback_index = next(i for i, e in enumerate(entries) if e["event"]["type"] == "callback" and e["event"]["node"] == key)
        child_index = next(i for i, e in enumerate(entries) if e["event"]["type"] == "request_layout" and e["event"]["node"] == child)
        require(callback_index < child_index, label + ": query child request-layout before callback")
    # Hand-authored integer cases use exact witnesses at 1x and 2x; fractional
    # inputs retain every actual coordinate without an unearned solver claim.
    known = witnesses.get(case["id"], {})
    expected_bounds = dict(known.get("bounds", {}), **known.get("bounds_by_scale", {}).get(format(scale, "g"), {}))
    for node, rect in expected_bounds.items():
        vector(prepaint[node]["bounds"], rect, label + " curated witness " + node)
    leaves = [prepaint[key] for key in painted if by_id[key]["kind"] == "box"]
    return {"frame": entries[0]["frame"], "scale_factor": scale,
        "bounds": {key: value["bounds"] for key, value in prepaint.items()},
        "callbacks": {key: value["size"] for key, value in callbacks.items()}, "painted_leaves": leaves}

def verify_observations(raw, corpus, witness_document=None):
    validate_scenarios(corpus)
    require(raw.get("schema_version") == 1 and raw.get("layer") == LAYER, "raw layer/schema")
    require(raw.get("fixture") == "font-free-bounded-grid" and raw.get("text_system") == "NoopTextSystem; no text used", "fixture/text claim")
    require(raw.get("upstream_revision") == UPSTREAM, "wrong engine pin")
    require(isinstance(raw.get("run_token"), str) and len(raw["run_token"]) >= 16, "run token")
    require(raw.get("input") == corpus, "input mismatch")
    require([c["id"] for c in raw["cases"]] == [c["id"] for c in corpus["cases"]], "case ordering/coverage")
    witnesses = (witness_document or {"cases": {}})["cases"]
    summaries = []
    for observed, case in zip(raw["cases"], corpus["cases"]):
        events = observed["events"]
        require([event["sequence"] for event in events] == list(range(len(events))), "event sequence")
        operations = [("initial", {"action": "open_window"}), ("configured", {"action": "set_scale_factor", "scale_factor": case["scale_factor"]})]
        operations += [(hit["id"], {"action": "click", "position": hit["position"]}) for hit in case["hits"]]
        cursor, frame_number, latest, result = 0, 0, None, []
        for operation, input_value in operations:
            require(cursor < len(events), "missing operation")
            start = events[cursor]
            require(start["operation"] == operation and start["event"] == {"type": "operation_start", "input": input_value}, "operation start/input")
            require(start["frame"] == frame_number, "operation frame")
            cursor += 1
            frames, clicks, pending = [], [], None
            hit_frame = latest
            scale = 2 if operation == "initial" else case["scale_factor"]
            while cursor < len(events) and events[cursor]["event"]["type"] != "operation_end":
                entry, cursor = events[cursor], cursor + 1
                event = entry["event"]
                require(entry["operation"] == operation, "operation interleaving")
                if event["type"] == "frame_start":
                    require(pending is None, "nested frame")
                    frame_number += 1
                    pending = []
                require(entry["frame"] == frame_number, "frame sequence")
                if pending is not None:
                    pending.append(entry)
                    if event["type"] == "frame_end":
                        latest = verify_frame(pending, case, scale, witnesses)
                        frames.append(latest)
                        pending = None
                elif event["type"] == "click":
                    require(input_value["action"] == "click" and event["detail"]["kind"] == "mouse", "unexpected click")
                    vector(event["detail"]["down"], input_value["position"], "click down")
                    vector(event["detail"]["up"], input_value["position"], "click up")
                    clicks.append(event["node"])
                else: require(False, "event outside frame")
            require(cursor < len(events) and pending is None, "unfinished operation/frame")
            end = events[cursor]
            require(end["operation"] == operation and end["frame"] == frame_number, "operation end")
            close(end["event"]["scale_factor"], scale, "operation scale")
            cursor += 1
            if operation in ("initial", "configured"): require(frames, "required redraw absent")
            if input_value["action"] == "click":
                eligible = [leaf["node"] for leaf in hit_frame["painted_leaves"] if inside(input_value["position"], leaf["bounds"]) and inside(input_value["position"], leaf["content_mask"])]
                require(clicks == eligible[-1:], "actual hit disagrees with observed opaque leaf bounds/paint order")
                known = witnesses.get(case["id"], {}).get("hits", {})
                if operation in known: require(clicks == known[operation], "curated hit witness")
            result.append({"id": operation, "frames": frames, "clicked_ids": clicks})
        require(cursor == len(events), "trailing events")
        summaries.append({"id": case["id"], "operations": result})
    return {"schema_version": 1, "layer": LAYER, "cases": summaries,
        "claim": "Actual public GPUI grid/container-query trace inspection; no unchanged-example, candidate-pair, font, screenshot, native-window, or app claim."}

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
        require(len(manifest["suite"][field]) == 40, "suite identity")
    required = {"raw.json", "raw.stderr", "scenarios.json", "probe", "toolchain.txt", "build.stdout", "build.stderr", "build-Cargo.toml"}
    required |= {retained_path(relative) for relative in RETAIN}
    required |= {"upstream/" + relative for relative in UPSTREAM_RETAIN}
    require(required <= set(manifest["files"]), "missing retained evidence")
    for relative, metadata in manifest["files"].items():
        require(not Path(relative).is_absolute() and ".." not in Path(relative).parts, "unsafe evidence name")
        path = directory / relative
        require(path.is_file() and path.resolve().is_relative_to(directory.resolve()) and not path.is_symlink(), "unsafe evidence path")
        require(digest(path) == metadata["sha256"] and path.stat().st_size == metadata["size"], "changed evidence: " + relative)
    require((directory / "scenarios.json").read_bytes() == (directory / "retained/diagnostics/grid_layout/scenarios.json").read_bytes(), "retained/run scenario mismatch")
    original_manifest = (directory / "retained/adapters/grid_layout_rust/Cargo.toml").read_text()
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
    if recorded_execution_root is not None:
        build_roots = [p for p in execution_root.parents if p.name == "_build"]
        require(len(build_roots) == 1, "recorded execution root must identify one ignored build root")
        expected_build = ["cargo", "+1.98.1", "build", "--locked", "--manifest-path",
            str(build_roots[0] / ("grid-layout-build-" + manifest["run_token"]) / "adapter/Cargo.toml")]
        require(manifest["build"]["command"] in (expected_build, expected_build + ["--offline"]), "exact relocated build manifest command")
    result = verify_observations(raw, json.loads((directory / "scenarios.json").read_text()),
        json.loads((directory / "retained/diagnostics/grid_layout/witnesses.json").read_text()))
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
