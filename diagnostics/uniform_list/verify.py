#!/usr/bin/env python3
"""Verify raw GPUI observations. No report-provided status or candidate data is accepted."""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
import subprocess
from pathlib import Path

UPSTREAM = "5a5fbe79917971a4d52a96b6ddb04da198a5012e"
UPSTREAM_TREE = "990fb995914d51a546b20e5cf0382dafc105c299"
LAYER = "supplemental-headless-core-semantics"
RETAIN = ["adapters/uniform_list_rust/Cargo.toml", "adapters/uniform_list_rust/Cargo.lock",
          "adapters/uniform_list_rust/src/main.rs", "diagnostics/uniform_list/scenarios.json",
          "diagnostics/uniform_list/raw.schema.json", "diagnostics/uniform_list/run.py",
          "diagnostics/uniform_list/verify.py", "diagnostics/uniform_list/README.md",
          "tests/test_uniform_list_diagnostic.py", ".github/workflows/uniform-list-diagnostic.yml"]
UPSTREAM_RETAIN = ["Cargo.toml", "Cargo.lock", "rust-toolchain.toml", "crates/gpui/Cargo.toml",
    "crates/gpui/src/elements/uniform_list.rs", "crates/gpui/src/elements/div.rs",
    "crates/gpui/src/element.rs", "crates/gpui/src/window.rs", "crates/gpui/src/app/test_context.rs",
    "crates/gpui/src/platform/test/platform.rs", "crates/gpui/src/platform/test/window.rs",
    "crates/gpui/examples/uniform_list.rs"]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def close(actual, expected, label):
    require(isinstance(actual, (int, float)) and not isinstance(actual, bool) and math.isfinite(actual), f"{label}: nonfinite/non-numeric")
    require(abs(actual - expected) <= 0.01, f"{label}: {actual} != {expected}")


def vector(actual, expected, label):
    require(isinstance(actual, list) and len(actual) == len(expected), f"{label}: bad shape")
    for index, (left, right) in enumerate(zip(actual, expected)):
        close(left, right, f"{label}[{index}]")


def intersection(left, right):
    x, y = max(left[0], right[0]), max(left[1], right[1])
    return [x, y, max(0, min(left[0] + left[2], right[0] + right[2]) - x),
            max(0, min(left[1] + left[3], right[1] + right[3]) - y)]


def inside(position, rect):
    x, y = position
    return rect[0] <= x < rect[0] + rect[2] and rect[1] <= y < rect[1] + rect[3]


def validate_scenarios(scenarios):
    require(scenarios.get("schema_version") == 1, "input schema")
    require(isinstance(scenarios.get("cases"), list) and scenarios["cases"], "missing cases")
    case_ids = set()
    for case in scenarios["cases"]:
        require(isinstance(case.get("id"), str) and case["id"] not in case_ids, "case id")
        case_ids.add(case["id"])
        config = dict(case["initial"])
        identifiers = {"initial"}
        validate_configuration(config)
        for operation in case["operations"]:
            require(isinstance(operation.get("id"), str) and operation["id"] not in identifiers, "operation id")
            identifiers.add(operation["id"])
            action = operation["action"]
            fields = {"set_offset": {"y"}, "set_count": {"count"}, "set_inner_height": {"height"},
                      "resize_list": {"height"}, "resize_window": {"size"}, "wheel": {"position", "delta"},
                      "move": {"position", "held"}, "down": {"position"}, "up": {"position"}}
            require(action in fields and set(operation) == {"id", "action"} | fields[action], "operation shape")
            for field in ("position", "delta", "size"):
                if field in operation:
                    require(len(operation[field]) == 2, "coordinate shape")
                    for value in operation[field]:
                        close(value, value, "coordinate")
            if action == "set_offset":
                close(operation["y"], operation["y"], "offset")
            if action == "move":
                require(type(operation["held"]) is bool, "held bool")
            config = changed_configuration(config, operation)
            validate_configuration(config)


def validate_configuration(config):
    require(set(config) == {"window", "list", "count", "inner_height"}, "configuration shape")
    require(type(config["count"]) is int and 0 <= config["count"] <= 1_000_000, "count bound")
    require(len(config["window"]) == 2 and len(config["list"]) == 4, "configuration dimensions")
    for value in [*config["window"], *config["list"], config["inner_height"]]:
        close(value, value, "configuration coordinate")
    require(all(value > 0 for value in [*config["window"], *config["list"][2:], config["inner_height"]]), "positive size")


def changed_configuration(config, operation):
    result = json.loads(json.dumps(config))
    action = operation["action"]
    if action == "set_count": result["count"] = operation["count"]
    if action == "set_inner_height": result["inner_height"] = operation["height"]
    if action == "resize_list": result["list"][3] = operation["height"]
    if action == "resize_window": result["window"] = operation["size"]
    return result


def verify_scroll(scroll, config, label):
    content_height = config["count"] * config["inner_height"]
    maximum = max(0, content_height - config["list"][3])
    vector(scroll["max_offset"], [0, maximum], label + " max")
    offset = scroll["offset"]
    close(offset[0], 0, label + " x")
    close(offset[1], offset[1], label + " y")
    require(-maximum <= offset[1] <= 0, label + " offset outside complete content")
    measured = scroll["last_item_size"]
    require(isinstance(measured, dict), label + " absent measured extent")
    vector(measured["item"], config["list"][2:], label + " viewport")
    vector(measured["contents"], [config["list"][2], content_height], label + " content extent")
    return -offset[1]


def verify_frame(events, config, label):
    require(events[0]["event"]["type"] == "frame_start" and events[-1]["event"]["type"] == "frame_end", label + " incomplete frame")
    require(events[0]["event"]["configuration"] == config, label + " configuration")
    end = events[-1]["event"]
    top = verify_scroll(end["scroll"], config, label)
    vector(end["window_size"], config["window"], label + " window")
    close(end["scale_factor"], 1, label + " scale")
    factories = [entry["event"] for entry in events if entry["event"]["type"] == "factory"]
    built = defaultdict(list)
    requested = defaultdict(lambda: defaultdict(list))
    prepaint = defaultdict(list)
    for entry in events:
        event = entry["event"]
        if event["type"] == "constructed": built[event["factory_call"]].append(event["item_id"])
        if event["type"] == "request_layout" and event["kind"] in ("row", "inner"):
            requested[event["kind"]][event["factory_call"]].append(event["item_id"])
        if event["type"] == "prepaint": prepaint[event["kind"]].append(event)
    require(len(prepaint["list"]) == 1, label + " list prepaint count")
    vector(prepaint["list"][0]["bounds"], config["list"], label + " list bounds")
    height = config["inner_height"]
    count = config["count"]
    first = math.floor(top / height)
    last = min(count, math.ceil((top + config["list"][3]) / height))
    visible_ids = list(range(first, last)) if count else []
    require(len(factories) == (3 if count else 0), label + " expected two prototype calls plus one visible call")
    expected_ranges = [[0, 1], [0, 1], [first, last]] if count else []
    require([entry["range"] for entry in factories] == expected_ranges, label + " callback ranges")
    calls = [entry["factory_call"] for entry in factories]
    require(len(set(calls)) == len(calls), label + " duplicate factory call")
    require(set(built) == set(calls), label + " unrelated/missing factory construction")
    for kind in ("row", "inner"):
        require(dict(requested[kind]) == dict(built), label + " prototype/visible request-layout IDs")
    for entry in factories:
        require(built[entry["factory_call"]] == list(range(*entry["range"])), label + " constructed identities")
    row_ids = [event["item_id"] for event in prepaint["row"]]
    inner_ids = [event["item_id"] for event in prepaint["inner"]]
    require(row_ids == visible_ids and inner_ids == visible_ids, label + " actual prepaint IDs")
    mask = intersection(config["list"], [0, 0, *config["window"]])
    for kind in ("row", "inner"):
        for event in prepaint[kind]:
            require(event["factory_call"] == calls[-1], label + " prototype reached live prepaint")
            item = event["item_id"]
            vector(event["bounds"], [config["list"][0], config["list"][1] + height * item - top,
                                     config["list"][2], height], label + f" {kind} {item} measured bounds")
            vector(event["content_mask"], mask, label + f" {kind} {item} content mask")
    require(sum(map(len, built.values())) <= len(visible_ids) + 2, label + " non-lazy construction")
    return {"frame": events[0]["frame"], "range": [first, last] if count else None,
            "prototype_calls": len(factories) - (1 if count else 0), "constructed_count": sum(map(len, built.values())),
            "visible_ids": row_ids, "top": top, "rows": prepaint["row"]}


def verify_observations(raw, scenarios):
    validate_scenarios(scenarios)
    require(raw.get("schema_version") == 1 and raw.get("layer") == LAYER, "raw layer/schema")
    require(raw.get("fixture") == "font-free-nested-auto-height", "fixture")
    require(raw.get("upstream_revision") == UPSTREAM, "wrong engine pin")
    require(raw.get("text_system") == "NoopTextSystem; no text used", "text claim")
    require(isinstance(raw.get("run_token"), str) and len(raw["run_token"]) >= 16, "run token")
    require(raw.get("input") == scenarios, "input mismatch")
    require([case["id"] for case in raw["cases"]] == [case["id"] for case in scenarios["cases"]], "case ordering/coverage")
    summaries = []
    for observed, scenario in zip(raw["cases"], scenarios["cases"]):
        entries = observed["events"]
        require([entry["sequence"] for entry in entries] == list(range(len(entries))), "event ordering")
        operations = [{"id": "initial", "action": "open_window"}, *scenario["operations"]]
        starts = [entry for entry in entries if entry["event"]["type"] == "operation_start"]
        ends = [entry for entry in entries if entry["event"]["type"] == "operation_end"]
        require(len(starts) == len(operations) == len(ends), "operation coverage")
        configuration = scenario["initial"]
        previous_top, last_frame, frame_number = 0, None, 0
        previous_end, pending_down = -1, None
        all_factories = [entry["event"]["factory_call"] for entry in entries if entry["event"]["type"] == "factory"]
        require(all_factories == list(range(1, len(all_factories) + 1)), "factory sequence")
        case_summary = {"id": scenario["id"], "operations": []}
        for operation, start, end in zip(operations, starts, ends):
            label = scenario["id"] + "/" + operation["id"]
            require(start["sequence"] == previous_end + 1, label + " unassigned events")
            previous_end = end["sequence"]
            require(start["operation"] == end["operation"] == operation["id"] and start["sequence"] < end["sequence"], label + " operation boundary")
            require(start["event"]["input"] == operation, label + " raw operation")
            interval = entries[start["sequence"]:end["sequence"] + 1]
            require(all(entry["operation"] == operation["id"] for entry in interval), label + " interleaved operation")
            configuration = changed_configuration(configuration, operation)
            frames = []
            pending = None
            for entry in interval:
                event = entry["event"]
                if event["type"] == "frame_start":
                    require(pending is None, label + " nested frame")
                    frame_number += 1
                    require(entry["frame"] == frame_number, label + " frame sequence")
                    pending = []
                if pending is not None:
                    require(entry["frame"] == frame_number, label + " frame identity")
                    pending.append(entry)
                if event["type"] == "frame_end":
                    require(pending is not None, label + " orphan frame end")
                    last_frame = verify_frame(pending, configuration, label)
                    frames.append(last_frame)
                    pending = None
            require(pending is None and last_frame is not None, label + " missing complete frame")
            require(end["event"]["configuration"] == configuration, label + " snapshot config")
            vector(end["event"]["list_bounds"], configuration["list"], label + " debug list bounds")
            top = verify_scroll(end["event"]["scroll"], configuration, label)
            maximum = max(0, configuration["count"] * configuration["inner_height"] - configuration["list"][3])
            expected_top = previous_top
            if operation["action"] == "set_offset": expected_top = operation["y"]
            if operation["action"] == "wheel" and inside(operation["position"], intersection(configuration["list"], [0, 0, *configuration["window"]])):
                x, y = operation["delta"]
                expected_top -= y if y else x
            close(top, min(maximum, max(0, expected_top)), label + " operation scroll policy/clamp")
            close(top, last_frame["top"], label + " snapshot vs last frame")
            clicks = [entry["event"] for entry in interval if entry["event"]["type"] == "click"]
            require(len(clicks) <= 1 and (not clicks or operation["action"] == "up"), label + " click operation")
            if operation["action"] == "down":
                hits = [row for row in last_frame["rows"] if inside(operation["position"], intersection(row["bounds"], row["content_mask"]))]
                pending_down = (hits[0]["item_id"], operation["position"]) if hits else None
            for click in clicks:
                require(pending_down is not None and click["item_id"] == pending_down[0], label + " click without matching pressed identity")
                vector(click["detail"]["down"], pending_down[1], label + " click press position")
                require(click["detail"]["kind"] == "mouse", label + " unexpected keyboard click")
                vector(click["detail"]["up"], operation["position"], label + " click release position")
                rows = [row for row in last_frame["rows"] if row["item_id"] == click["item_id"]]
                require(len(rows) == 1 and inside(operation["position"], intersection(rows[0]["bounds"], rows[0]["content_mask"])), label + " click outside live clipped row")
            case_summary["operations"].append({"id": operation["id"], "frames": frames, "top": top,
                "clicked_ids": [click["item_id"] for click in clicks]})
            previous_top = top
            if operation["action"] == "up": pending_down = None
        require(previous_end == len(entries) - 1, "unassigned trailing events")
        summaries.append(case_summary)
    verify_known_clicks(summaries)
    return {"layer": LAYER, "cases": summaries, "claim": "Observed supplemental test-platform semantics only; no candidate or unchanged-example claim"}


def verify_known_clicks(summaries):
    by_case = {case["id"]: {operation["id"]: operation["clicked_ids"] for operation in case["operations"]} for case in summaries}
    expected = {
        "stable-click-and-press-scroll": {"no-down-up": [], "row-three-up": [3], "duplicate-up": [],
            "same-id-new-position-up": [3], "release-row-three-moved": [3], "other-row-up": [], "outside-release-up": []},
        "one-item": {"one-click-up": [0], "below-item-up": []},
        "empty-list": {"empty-click-up": []},
        "nested-mask-half-open-edges": {"clipped-top-up": [], "top-edge-up": [0], "just-inside-right-up": [2],
            "right-edge-up": [], "beyond-right-up": [], "just-inside-bottom-up": [12], "bottom-edge-up": [],
            "clipped-tail-up": [], "left-outside-up": [], "left-edge-up": [2]},
    }
    for case, operations in expected.items():
        if case in by_case:
            for operation, ids in operations.items():
                require(by_case[case].get(operation) == ids, f"{case}/{operation}: callback identity")
    # Omitted or removed rows are observations, not presumed persistent identities.
    # Their actual results are retained for the future production-core comparator.


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_bundle(directory, suite_commit=None, suite_tree=None, suite_source=None, upstream_source=None):
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
    required |= {"retained/" + relative for relative in RETAIN}
    required |= {"upstream/" + relative for relative in UPSTREAM_RETAIN}
    require(required <= set(manifest["files"]), "missing retained evidence")
    for relative, metadata in manifest["files"].items():
        require(not Path(relative).is_absolute() and ".." not in Path(relative).parts, "unsafe evidence name")
        path = directory / relative
        require(path.is_file() and path.resolve().is_relative_to(directory.resolve()) and not path.is_symlink(), "unsafe evidence path")
        require(digest(path) == metadata["sha256"] and path.stat().st_size == metadata["size"], "changed evidence: " + relative)
    require((directory / "scenarios.json").read_bytes() == (directory / "retained/diagnostics/uniform_list/scenarios.json").read_bytes(), "retained/run scenario mismatch")
    original_manifest = (directory / "retained/adapters/uniform_list_rust/Cargo.toml").read_text()
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
                require((directory / prefix / relative).read_bytes() == expected, "retained bytes differ from exact committed source: " + relative)
    require((directory / "probe").read_bytes().startswith(b"\x7fELF"), "probe is not a Linux executable")
    require((directory / "toolchain.txt").read_text().startswith("rustc 1.98.1 "), "compiler provenance")
    raw = json.loads((directory / "raw.json").read_text())
    require(raw["run_token"] == manifest["run_token"], "cross-run trace")
    require(manifest.get("execution", {}).get("returncode") == 0 and manifest["build"]["returncode"] == 0, "failed execution/build")
    require(manifest["execution"]["timed_out"] is False and manifest["build"]["timed_out"] is False, "timed out")
    require("--locked" in manifest["build"]["command"] and "--release" not in manifest["build"]["command"], "build mode/lock")
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
    arguments = parser.parse_args()
    result = verify_bundle(arguments.evidence, arguments.suite_commit, arguments.suite_tree, arguments.suite_source, arguments.upstream_source)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
