"""Synthetic comparator-sensitivity units. These never run or stand in for GPUI."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "diagnostics/uniform_list"))
import verify


def synthetic_checker_input():
    """Minimal hand-authored checker input, not an expected/observed Rust artifact."""
    configuration = {"window": [420, 420], "list": [40, 50, 220, 52], "count": 50, "inner_height": 26, "scale_factor": 2}
    scale_operation = {"id": "configure-dpr-one", "action": "set_scale_factor", "scale_factor": 1}
    scenario = {"id": "synthetic-checker-unit", "initial": configuration, "operations": [scale_operation]}
    corpus = {"schema_version": 2, "coordinate_system": "synthetic checker unit", "cases": [scenario]}
    events = []
    def emit(event, operation, frame):
        events.append({"sequence": len(events), "operation": operation, "frame": frame, "event": event})
    for frame, scale, operation in [(1, 2, {"id": "initial", "action": "open_window"}), (2, 1, scale_operation)]:
        config = configuration | {"scale_factor": scale}
        def event(value): emit(value, operation["id"], frame)
        event({"type": "operation_start", "input": operation,
               **({"applied_input": operation} if frame == 2 else {})})
        event({"type": "frame_start", "configuration": config})
        event({"type": "prepaint", "kind": "list", "item_id": None, "factory_call": None,
               "bounds": [40, 50, 220, 52], "content_mask": [0, 0, 420, 420]})
        for factory, ids in [(1, [0]), (2, [0]), (3, [0, 1])]:
            factory += (frame - 1) * 3
            event({"type": "factory", "factory_call": factory, "range": [ids[0], ids[-1] + 1]})
            for item in ids:
                event({"type": "constructed", "factory_call": factory, "item_id": item})
            for item in ids:
                for kind in ("row", "inner"):
                    event({"type": "request_layout", "kind": kind, "factory_call": factory, "item_id": item})
        for item in [0, 1]:
            for kind in ("row", "inner"):
                event({"type": "prepaint", "kind": kind, "factory_call": frame * 3, "item_id": item,
                       "bounds": [40, 50 + 26 * item, 220, 26], "content_mask": [40, 50, 220, 52]})
        scroll = {"offset": [0, 0], "max_offset": [0, 1248], "last_item_size": {"item": [220, 52], "contents": [220, 1300]}}
        event({"type": "frame_end", "scroll": scroll, "window_size": [420, 420], "scale_factor": scale})
        event({"type": "operation_end", "configuration": config, "scroll": scroll, "list_bounds": [40, 50, 220, 52], "scale_factor": scale})
    raw = {"schema_version": 2, "layer": verify.LAYER, "fixture": "font-free-nested-auto-height",
           "text_system": "NoopTextSystem; no text used", "upstream_revision": verify.UPSTREAM,
           "run_token": "synthetic-checker-only-0001", "input": corpus,
           "cases": [{"id": scenario["id"], "events": events}]}
    return raw, corpus


class DiagnosticContracts(unittest.TestCase):
    def test_real_corpus_is_well_formed(self):
        corpus = json.loads((ROOT / "diagnostics/uniform_list/scenarios.json").read_text())
        verify.validate_scenarios(corpus)
        self.assertEqual(len(corpus["cases"]), 9)
        ids = {operation["id"] for case in corpus["cases"] for operation in case["operations"]}
        self.assertTrue({"release-after-omission", "release-reused-index", "horizontal-only", "height-31", "far-offset"} <= ids)

    def test_minimal_synthetic_checker_input(self):
        raw, corpus = synthetic_checker_input()
        summary = verify.verify_observations(raw, corpus)
        self.assertEqual(summary["cases"][0]["operations"][0]["frames"][0]["visible_ids"], [0, 1])

    def test_corrupted_event_observations_are_rejected(self):
        changes = [
            ("factory", None, "range", [1, 2]),
            ("factory", None, "factory_call", 999),
            ("constructed", None, "item_id", 99),
            ("request_layout", "row", "item_id", 99),
            ("prepaint", "row", "item_id", 99),
            ("prepaint", "row", "factory_call", 1),
            ("prepaint", "row", "bounds", [40, 50, 220, 27]),
            ("prepaint", "inner", "bounds", [40, 50, 220, 25]),
            ("prepaint", "row", "content_mask", [0, 0, 420, 420]),
            ("prepaint", "list", "bounds", [40, 50, 220, 51]),
            ("frame_end", None, "scale_factor", 3),
            ("frame_end", None, "window_size", [1, 1]),
            ("operation_end", None, "list_bounds", [0, 0, 420, 420]),
        ]
        for event_type, kind, field, value in changes:
            with self.subTest(event_type=event_type, kind=kind, field=field):
                raw, corpus = synthetic_checker_input()
                event = next(entry["event"] for entry in raw["cases"][0]["events"]
                             if entry["event"]["type"] == event_type and (kind is None or entry["event"].get("kind") == kind))
                event[field] = value
                with self.assertRaises(ValueError): verify.verify_observations(raw, corpus)

    def test_virtual_extent_and_offset_corruption(self):
        for field, value in [("offset", [0, -1]), ("max_offset", [0, 0]),
                             ("last_item_size", {"item": [220, 52], "contents": [220, 52]})]:
            with self.subTest(field=field):
                raw, corpus = synthetic_checker_input()
                end = next(entry["event"] for entry in raw["cases"][0]["events"] if entry["event"]["type"] == "frame_end")
                end["scroll"][field] = value
                with self.assertRaises(ValueError): verify.verify_observations(raw, corpus)

    def test_eager_invisible_factory_call_rejected(self):
        raw, corpus = synthetic_checker_input()
        events = raw["cases"][0]["events"]
        events.insert(-2, {"sequence": 0, "operation": "initial", "frame": 1,
                           "event": {"type": "factory", "factory_call": 4, "range": [0, 50]}})
        for sequence, event in enumerate(events): event["sequence"] = sequence
        with self.assertRaises(ValueError): verify.verify_observations(raw, corpus)

    def test_sequence_missing_frame_and_operation_rejected(self):
        for mutate in (lambda events: events.reverse(), lambda events: events.pop(-2),
                       lambda events: events[0].update(operation="wrong"),
                       lambda events: events[1].update(frame=2)):
            raw, corpus = synthetic_checker_input()
            mutate(raw["cases"][0]["events"])
            with self.assertRaises(ValueError): verify.verify_observations(raw, corpus)

    def test_wrong_engine_input_token_and_layer_rejected(self):
        for field, value in [("schema_version", 1), ("upstream_revision", "d9afb21688e04f89d9e94d96d33eb530aef90886"),
                             ("input", {}), ("run_token", "short"), ("layer", "unchanged-example"),
                             ("text_system", "real font shaping")]:
            raw, corpus = synthetic_checker_input()
            raw[field] = value
            with self.assertRaises(ValueError): verify.verify_observations(raw, corpus)

    def test_no_down_click_rejected(self):
        raw, corpus = synthetic_checker_input()
        events = raw["cases"][0]["events"]
        events.insert(-1, {"sequence": 0, "operation": "initial", "frame": 1,
            "event": {"type": "click", "item_id": 0, "factory_call": 3,
                      "detail": {"kind": "mouse", "down": [100, 60], "up": [100, 60]}}})
        for sequence, event in enumerate(events): event["sequence"] = sequence
        with self.assertRaises(ValueError): verify.verify_observations(raw, corpus)

    def test_known_click_identity_and_edges(self):
        summary = [{"id": "one-item", "operations": [{"id": "one-click-up", "clicked_ids": [0]},
                                                      {"id": "below-item-up", "clicked_ids": []}]}]
        verify.verify_known_clicks(summary)
        summary[0]["operations"][1]["clicked_ids"] = [0]
        with self.assertRaises(ValueError): verify.verify_known_clicks(summary)
        self.assertTrue(verify.inside([40, 50], [40, 50, 220, 300]))
        self.assertFalse(verify.inside([260, 60], [40, 50, 220, 300]))
        self.assertFalse(verify.inside([100, 350], [40, 50, 220, 300]))

    def test_invalid_input_and_duplicate_ids_rejected(self):
        for mutation in (lambda c: c["cases"].append(copy.deepcopy(c["cases"][0])),
                         lambda c: c["cases"][0]["initial"].update(inner_height=0),
                         lambda c: c["cases"][0]["initial"].update(count=1_000_001),
                         lambda c: c["cases"][0]["initial"].update(inner_height=float("nan"))):
            _, corpus = synthetic_checker_input()
            mutation(corpus)
            with self.assertRaises(ValueError): verify.validate_scenarios(corpus)

    def test_separate_manifest_pin_and_public_api_contract(self):
        source = (ROOT / "adapters/uniform_list_rust/src/main.rs").read_text()
        manifest = (ROOT / "adapters/uniform_list_rust/Cargo.toml").read_text()
        workflow = (ROOT / ".github/workflows/uniform-list-diagnostic.yml").read_text()
        self.assertIn(verify.UPSTREAM, source)
        self.assertIn(verify.UPSTREAM, workflow)
        self.assertIn('default-features = false, features = ["test-support"]', manifest)
        self.assertIn("TestAppContext::single()", source)
        self.assertIn("self.inner.request_layout(", source)
        self.assertIn("self.inner.prepaint(", "".join(source.split()))
        self.assertIn("self.inner.paint(", "".join(source.split()))
        self.assertIn("window.content_mask()", source)
        self.assertIn("simulate_mouse_down", source)
        self.assertIn("simulate_mouse_up", source)
        self.assertIn("ScrollDelta::Pixels", source)
        self.assertNotIn("expected_range", source)
        self.assertNotIn("floor(", source)
        self.assertNotIn("ceil(", source)
        self.assertNotIn("--release", workflow)
        self.assertNotIn("harness.yml", workflow)
        self.assertTrue((ROOT / "adapters/uniform_list_rust/Cargo.lock").is_file())

    def test_multiple_actual_frames_and_no_redraw_operation(self):
        raw, corpus = synthetic_checker_input()
        entries = raw["cases"][0]["events"]
        start = next(index for index, entry in enumerate(entries) if entry["operation"] == "configure-dpr-one")
        frame = copy.deepcopy(entries[start + 1:-1])
        for entry in frame:
            entry["frame"] = 3
            event = entry["event"]
            if event.get("factory_call") is not None: event["factory_call"] += 3
        entries[-1:-1] = frame
        entries[-1]["frame"] = 3
        operation = {"id": "no-down", "action": "up", "position": [100, 60]}
        corpus["cases"][0]["operations"].append(operation)
        final = copy.deepcopy(entries[-1])
        final["operation"] = "no-down"
        entries.append({"sequence": 0, "operation": "no-down", "frame": 3,
                        "event": {"type": "operation_start", "input": operation, "applied_input": operation}})
        entries.append(final)
        for sequence, entry in enumerate(entries): entry["sequence"] = sequence
        summary = verify.verify_observations(raw, corpus)
        self.assertEqual(len(summary["cases"][0]["operations"][1]["frames"]), 2)
        self.assertEqual(summary["cases"][0]["operations"][2]["frames"], [])

    def test_missing_reordered_or_wrong_scale_transition_rejected(self):
        for mutate in (lambda case: case["operations"].clear(),
                       lambda case: case["operations"].insert(0, {"id": "early-up", "action": "up", "position": [100, 60]}),
                       lambda case: case["operations"][0].update(scale_factor=2),
                       lambda case: case["initial"].update(scale_factor=1)):
            _, corpus = synthetic_checker_input()
            mutate(corpus["cases"][0])
            with self.assertRaises(ValueError): verify.validate_scenarios(corpus)
        for event_type in ("frame_end", "operation_end"):
            raw, corpus = synthetic_checker_input()
            event = next(entry["event"] for entry in raw["cases"][0]["events"]
                         if entry["operation"] == "configure-dpr-one" and entry["event"]["type"] == event_type)
            event["scale_factor"] = 2
            with self.assertRaises(ValueError): verify.verify_observations(raw, corpus)
        raw, corpus = synthetic_checker_input()
        raw["cases"][0]["events"] = [entry for entry in raw["cases"][0]["events"] if entry["operation"] == "initial"]
        with self.assertRaises(ValueError): verify.verify_observations(raw, corpus)

    def test_original_and_applied_float_input_are_separate(self):
        raw, corpus = synthetic_checker_input()
        operation = {"id": "rounded-move", "action": "move", "position": [99999999, 0.1], "held": False}
        applied = verify.applied_operation(operation)
        self.assertEqual(applied["position"], [100000000, 0.10000000149011612])
        self.assertEqual(verify.applied_operation({"id": "large", "action": "set_offset", "y": 99999999})["y"], 100000000)
        corpus["cases"][0]["operations"].append(operation)
        entries = raw["cases"][0]["events"]
        end = copy.deepcopy(entries[-1])
        end["operation"] = operation["id"]
        entries.append({"sequence": len(entries), "operation": operation["id"], "frame": 2,
                        "event": {"type": "operation_start", "input": copy.deepcopy(operation), "applied_input": applied}})
        end["sequence"] = len(entries)
        entries.append(end)
        verify.verify_observations(raw, corpus)
        for field, replacement in (("input", applied), ("applied_input", operation)):
            modified = copy.deepcopy(raw)
            modified["cases"][0]["events"][-2]["event"][field] = replacement
            with self.assertRaises(ValueError): verify.verify_observations(modified, corpus)

    def test_workflow_retention_mapping_is_narrow_and_nonhidden(self):
        source = ".github/workflows/uniform-list-diagnostic.yml"
        self.assertEqual(verify.retained_path(source), "retained/workflows/uniform-list-diagnostic.yml")
        self.assertEqual(verify.retained_path("diagnostics/uniform_list/run.py"), "retained/diagnostics/uniform_list/run.py")
        self.assertFalse(any(part.startswith(".") for part in Path(verify.retained_path(source)).parts))
        self.assertNotIn("include-hidden-files: true", (ROOT / source).read_text())

    def test_bundle_retention_and_corruption_guards(self):
        raw, corpus = synthetic_checker_input()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            files = {
                "raw.json": json.dumps(raw).encode(), "raw.stderr": b"",
                "scenarios.json": json.dumps(corpus).encode(), "probe": b"\x7fELFsynthetic-unit-only",
                "toolchain.txt": b"rustc 1.98.1 synthetic unit only\n", "build.stdout": b"", "build.stderr": b"",
                "retained/adapters/uniform_list_rust/Cargo.toml": b"synthetic checker unit",
                "retained/adapters/uniform_list_rust/Cargo.lock": b"synthetic checker unit",
                "retained/adapters/uniform_list_rust/src/main.rs": b"synthetic checker unit",
                "retained/diagnostics/uniform_list/verify.py": b"synthetic checker unit",
            }
            files.update({verify.retained_path(relative): (ROOT / relative).read_bytes() for relative in verify.RETAIN})
            files.update({"upstream/" + relative: b"synthetic checker unit" for relative in verify.UPSTREAM_RETAIN})
            files["retained/diagnostics/uniform_list/scenarios.json"] = files["scenarios.json"]
            files["build-Cargo.toml"] = files["retained/adapters/uniform_list_rust/Cargo.toml"].replace(
                b'"../../../zed-source/crates/gpui"', b'"/synthetic-source/crates/gpui"')
            for relative, content in files.items():
                path = directory / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            identity = {"commit": "a" * 40, "tree": "b" * 40, "clean": True}
            upstream = {"commit": verify.UPSTREAM, "tree": verify.UPSTREAM_TREE, "clean": True}
            manifest = {"schema_version": 1, "layer": verify.LAYER, "suite": identity, "suite_after": identity,
                "upstream": upstream, "upstream_after": upstream, "run_token": raw["run_token"], "upstream_source_path": "/synthetic-source",
                "build": {"command": ["cargo", "+1.98.1", "build", "--locked"], "returncode": 0, "timed_out": False},
                "execution": {"returncode": 0, "timed_out": False},
                "files": {name: {"sha256": verify.digest(directory / name), "size": len(content)} for name, content in files.items()}}
            path = directory / "manifest.json"
            path.write_text(json.dumps(manifest))
            self.assertFalse(verify.verify_bundle(directory, "a" * 40, "b" * 40)["source_bound"])
            self.assertIn("unqualified", verify.verify_bundle(directory)["inspection_scope"])
            for mutate in (lambda m: m.update(run_token="other-run-token-0000"),
                           lambda m: m["suite"].update(clean=False),
                           lambda m: m["upstream"].update(commit="d" * 40),
                           lambda m: m["execution"].update(returncode=1),
                           lambda m: m["build"].update(timed_out=True),
                           lambda m: m["build"].update(command=["cargo", "build"]),
                           lambda m: m["files"].pop("probe"),
                           lambda m: m["files"].pop(verify.retained_path(".github/workflows/uniform-list-diagnostic.yml"))):
                modified = copy.deepcopy(manifest)
                mutate(modified)
                path.write_text(json.dumps(modified))
                with self.assertRaises(ValueError): verify.verify_bundle(directory)
            path.write_text(json.dumps(manifest))
            with self.assertRaises(ValueError): verify.verify_bundle(directory, "c" * 40)
            with self.assertRaises(ValueError): verify.verify_bundle(directory, suite_tree="c" * 40)
            def independent_git(arguments, cwd=None, text=False):
                if arguments[1] == "rev-parse": return "b" * 40 + "\n"
                relative = arguments[2].split(":", 1)[1]
                return files[verify.retained_path(relative)]
            with patch.object(verify.subprocess, "check_output", side_effect=independent_git):
                verify.verify_bundle(directory, "a" * 40, "b" * 40, suite_source=ROOT)
                workflow = verify.retained_path(".github/workflows/uniform-list-diagnostic.yml")
                (directory / workflow).write_bytes(b"mismatched relocated workflow")
                changed = copy.deepcopy(manifest)
                changed["files"][workflow] = {"sha256": verify.digest(directory / workflow), "size": (directory / workflow).stat().st_size}
                path.write_text(json.dumps(changed))
                with self.assertRaisesRegex(ValueError, "exact committed source"):
                    verify.verify_bundle(directory, "a" * 40, "b" * 40, suite_source=ROOT)
            (directory / workflow).write_bytes(files[workflow])
            path.write_text(json.dumps(manifest))
            (directory / "raw.stderr").write_bytes(b"tampered")
            with self.assertRaises(ValueError): verify.verify_bundle(directory)

    def test_machine_schema_covers_raw_and_input(self):
        schema = json.loads((ROOT / "diagnostics/uniform_list/raw.schema.json").read_text())
        self.assertIn("input", schema["$defs"])
        self.assertEqual(schema["properties"]["upstream_revision"]["const"], verify.UPSTREAM)
        event_names = {item["properties"]["type"]["const"] for item in schema["$defs"]["event"]["oneOf"]}
        self.assertTrue({"factory", "constructed", "request_layout", "prepaint", "click", "frame_start", "frame_end"} <= event_names)


if __name__ == "__main__":
    unittest.main()
