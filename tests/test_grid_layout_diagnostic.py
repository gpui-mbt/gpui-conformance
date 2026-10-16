"""Synthetic checker sensitivity units. These do not execute or impersonate GPUI."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("grid_diagnostic_verify", ROOT / "diagnostics/grid_layout/verify.py")
verify = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify)


def synthetic_checker_input():
    """Hand-authored checker-only geometry, never retained as Rust observations."""
    leaf = {"id": "leaf", "kind": "box", "width": 10, "height": 7}
    query = {"id": "query", "kind": "query", "children": [leaf]}
    root = {"id": "grid", "kind": "grid", "width": 100, "height": 60,
            "cols": 1, "rows": 1, "gap": 0, "children": [query]}
    case = {"id": "synthetic-checker-only", "window": [640, 640], "origin": [20, 30],
            "scale_factor": 1, "root": root, "hits": [{"id": "inside", "position": [21, 31]}]}
    corpus = {"schema_version": 1, "coordinate_system": "synthetic checker unit", "cases": [case]}
    geometry = {"$host": [0, 0, 640, 640], "grid": [20, 30, 100, 60],
                "query": [20, 30, 100, 60], "leaf": [20, 30, 10, 7]}
    events, frame = [], 0
    def emit(event, operation):
        events.append({"sequence": len(events), "operation": operation, "frame": frame, "event": event})
    for operation, scale, input_value in [("initial", 2, {"action": "open_window"}),
            ("configured", 1, {"action": "set_scale_factor", "scale_factor": 1})]:
        emit({"type": "operation_start", "input": input_value}, operation)
        frame += 1
        def event(value): emit(value, operation)
        event({"type": "frame_start", "scale_factor": scale, "window_size": case["window"]})
        for name in ("$host", "grid", "query"):
            event({"type": "request_layout", "node": name})
        for name in ("query", "grid", "$host"):
            event({"type": "request_layout_end", "node": name})
        for name in ("$host", "grid", "query"):
            event({"type": "prepaint", "node": name, "bounds": geometry[name], "content_mask": [0, 0, 640, 640]})
        event({"type": "callback", "node": "query", "size": [100, 60]})
        event({"type": "request_layout", "node": "leaf"})
        event({"type": "request_layout_end", "node": "leaf"})
        event({"type": "prepaint", "node": "leaf", "bounds": geometry["leaf"], "content_mask": [0, 0, 640, 640]})
        for name in ("leaf", "query", "grid", "$host"):
            event({"type": "prepaint_end", "node": name})
        for name in ("$host", "grid", "query", "leaf"):
            event({"type": "paint", "node": name, "bounds": geometry[name]})
        for name in ("leaf", "query", "grid", "$host"):
            event({"type": "paint_end", "node": name})
        event({"type": "frame_end", "scale_factor": scale, "window_size": case["window"]})
        event({"type": "operation_end", "scale_factor": scale})
    emit({"type": "operation_start", "input": {"action": "click", "position": [21, 31]}}, "inside")
    emit({"type": "click", "node": "leaf", "detail": {"kind": "mouse", "down": [21, 31], "up": [21, 31]}}, "inside")
    emit({"type": "operation_end", "scale_factor": 1}, "inside")
    raw = {"schema_version": 1, "layer": verify.LAYER, "fixture": "font-free-bounded-grid",
        "text_system": "NoopTextSystem; no text used", "upstream_revision": verify.UPSTREAM,
        "run_token": "synthetic-checker-only-0001", "input": corpus, "cases": [{"id": case["id"], "events": events}]}
    witnesses = {"schema_version": 1, "cases": {case["id"]: {"bounds": geometry, "hits": {"inside": ["leaf"]}}}}
    return raw, corpus, witnesses


def resequence(events):
    for index, entry in enumerate(events): entry["sequence"] = index


class GridDiagnosticContracts(unittest.TestCase):
    def test_curated_input_contract(self):
        corpus = json.loads((ROOT / "diagnostics/grid_layout/scenarios.json").read_text())
        verify.validate_scenarios(corpus)
        self.assertEqual(len(corpus["cases"]), 12)
        self.assertEqual({case["scale_factor"] for case in corpus["cases"]}, {1, 1.25, 2})
        ids = {case["id"] for case in corpus["cases"]}
        self.assertTrue({"sparse-hole", "explicit-collision", "full-column-lines", "nested-query",
                         "content-independent-small", "content-independent-large"} <= ids)
        cases = {case["id"]: case for case in corpus["cases"]}
        small = copy.deepcopy(cases["content-independent-small"])
        large = copy.deepcopy(cases["content-independent-large"])
        for case in (small, large):
            case.pop("id")
            case["root"]["children"][0]["children"][0].update(width=1, height=1)
        self.assertEqual(small, large)

    def test_synthetic_fixture_is_checker_input_only(self):
        raw, corpus, witnesses = synthetic_checker_input()
        result = verify.verify_observations(raw, corpus, witnesses)
        self.assertEqual(result["cases"][0]["operations"][2]["clicked_ids"], ["leaf"])
        self.assertEqual(result["cases"][0]["operations"][0]["frames"][0]["callbacks"], {"query": [100, 60]})

    def test_callback_size_timing_and_count_corruptions(self):
        for mutation in ("size", "node", "duplicate", "early", "missing"):
            with self.subTest(mutation=mutation):
                raw, corpus, witnesses = synthetic_checker_input()
                events = raw["cases"][0]["events"]
                index = next(i for i, e in enumerate(events) if e["event"]["type"] == "callback")
                if mutation == "size": events[index]["event"]["size"] = [101, 60]
                if mutation == "node": events[index]["event"]["node"] = "leaf"
                if mutation == "duplicate": events.insert(index, copy.deepcopy(events[index]))
                if mutation == "early": events.insert(3, events.pop(index))
                if mutation == "missing": events.pop(index)
                resequence(events)
                with self.assertRaises(ValueError): verify.verify_observations(raw, corpus, witnesses)

    def test_bounds_origin_scale_mask_and_paint_corruptions(self):
        for kind, node, field, value in [
            ("prepaint", "leaf", "bounds", [21, 30, 10, 7]),
            ("prepaint", "query", "bounds", [20, 30, 101, 60]),
            ("prepaint", "leaf", "content_mask", [20, 30, 100, 60]),
            ("paint", "leaf", "bounds", [20, 30, 11, 7]),
            ("prepaint", "leaf", "bounds", [20.1, 30, 10, 7]),
            ("frame_end", None, "scale_factor", 1),
            ("frame_start", None, "window_size", [600, 600]),
            ("prepaint", "leaf", "bounds", [20, 30, float("nan"), 7]),
        ]:
            with self.subTest(kind=kind, field=field, value=value):
                raw, corpus, witnesses = synthetic_checker_input()
                event = next(e["event"] for e in raw["cases"][0]["events"] if e["event"]["type"] == kind and (node is None or e["event"].get("node") == node))
                event[field] = value
                with self.assertRaises(ValueError): verify.verify_observations(raw, corpus, witnesses)

    def test_lifecycle_and_sequence_corruptions(self):
        for mutation in ("return", "missing", "frame", "operation", "sequence", "trailing"):
            raw, corpus, witnesses = synthetic_checker_input()
            events = raw["cases"][0]["events"]
            if mutation == "return": events[5]["event"]["node"] = "$host"
            if mutation == "missing": events.pop(6); resequence(events)
            if mutation == "frame": events[4]["frame"] += 1
            if mutation == "operation": events[4]["operation"] = "configured"
            if mutation == "sequence": events[4]["sequence"] = 99
            if mutation == "trailing": events.append(copy.deepcopy(events[-1])); resequence(events)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): verify.verify_observations(raw, corpus, witnesses)

    def test_hits_are_actual_callbacks_not_metadata(self):
        for mutate in (lambda event: event.update(node="query"),
                       lambda event: event["detail"].update(down=[22, 31]),
                       lambda event: event["detail"].update(kind="keyboard")):
            raw, corpus, witnesses = synthetic_checker_input()
            click = next(e["event"] for e in raw["cases"][0]["events"] if e["event"]["type"] == "click")
            mutate(click)
            with self.assertRaises(ValueError): verify.verify_observations(raw, corpus, witnesses)
        self.assertFalse(verify.inside([30, 31], [20, 30, 10, 7]))
        self.assertTrue(verify.inside([20, 30], [20, 30, 10, 7]))

    def test_multiple_frames_are_retained_without_fake_input_frame_counts(self):
        raw, corpus, witnesses = synthetic_checker_input()
        events = raw["cases"][0]["events"]
        start = next(i for i, e in enumerate(events) if e["operation"] == "configured")
        end = next(i for i, e in enumerate(events) if e["operation"] == "inside") - 1
        extra = copy.deepcopy(events[start + 1:end])
        for e in extra: e["frame"] = 3
        for e in events[end:]: e["frame"] = 3
        events[end:end] = extra
        resequence(events)
        result = verify.verify_observations(raw, corpus, witnesses)
        self.assertEqual(len(result["cases"][0]["operations"][1]["frames"]), 2)
        self.assertEqual(result["cases"][0]["operations"][2]["frames"], [])

    def test_invalid_input_is_bounded_and_unambiguous(self):
        mutations = [lambda c: c["cases"].append(copy.deepcopy(c["cases"][0])),
            lambda c: c["cases"][0].update(scale_factor=3),
            lambda c: c["cases"][0]["root"].update(cols=0),
            lambda c: c["cases"][0]["root"].update(width=0),
            lambda c: c["cases"][0]["root"].update(width=.1),
            lambda c: c["cases"][0]["root"].update(width=float("nan")),
            lambda c: c["cases"][0]["root"].update(full_columns=True, col_span=2),
            lambda c: c["cases"][0]["root"].update(col_start=0),
            lambda c: c["cases"][0]["root"]["children"][0].update(children=[]),
            lambda c: c["cases"][0]["root"]["children"][0].update(id="grid"),
            lambda c: c["cases"][0]["root"]["children"][0].update(rows=2)]
        for mutate in mutations:
            _, corpus, _ = synthetic_checker_input()
            mutate(corpus)
            with self.assertRaises(ValueError): verify.validate_scenarios(corpus)

    def test_raw_identity_corruptions(self):
        for field, value in [("upstream_revision", "d" * 40), ("layer", "unchanged-example"),
                ("fixture", "native-gui"), ("text_system", "font shaping"), ("run_token", "tiny"), ("input", {})]:
            raw, corpus, witnesses = synthetic_checker_input()
            raw[field] = value
            with self.assertRaises(ValueError): verify.verify_observations(raw, corpus, witnesses)

    def test_rust_delegates_actual_public_apis_without_layout_solver(self):
        source = (ROOT / "adapters/grid_layout_rust/src/main.rs").read_text()
        compact = "".join(source.split())
        for value in ("TestAppContext::single()", "VisualTestContext::from_window", "container_query(",
                      ".grid_cols(", ".grid_rows(", ".col_span_full()", "simulate_click", "window.content_mask()"):
            self.assertIn(value, source)
        for value in ("self.inner.request_layout(", "self.inner.prepaint(", "self.inner.paint("):
            self.assertIn(value, compact)
        for value in ("witnesses.json", "expected_bounds", "floor(", "ceil(", "layout_as_root(", "layout_bounds("):
            self.assertNotIn(value, source)
        self.assertIn(verify.UPSTREAM, source)
        manifest = (ROOT / "adapters/grid_layout_rust/Cargo.toml").read_text()
        self.assertIn('default-features = false, features = ["test-support"]', manifest)
        lock = (ROOT / "adapters/grid_layout_rust/Cargo.lock").read_text()
        original = (ROOT / "adapters/uniform_list_rust/Cargo.lock").read_text()
        self.assertEqual(lock, original.replace("gpui-uniform-list-diagnostic", "gpui-grid-layout-diagnostic"))

    def test_ci_and_retention_are_separate_and_failure_preserving(self):
        source = ".github/workflows/grid-layout-diagnostic.yml"
        workflow = (ROOT / source).read_text()
        self.assertIn(verify.UPSTREAM, workflow)
        self.assertIn("if: always()", workflow)
        self.assertIn("--suite-tree", workflow)
        self.assertNotIn("--release", workflow)
        self.assertNotIn("include-hidden-files: true", workflow)
        self.assertEqual(verify.retained_path(source), "retained/workflows/grid-layout-diagnostic.yml")
        runner = (ROOT / "diagnostics/grid_layout/run.py").read_text()
        self.assertIn("8 * 1024**3", runner)
        self.assertIn("verification-failure.json", runner)
        self.assertNotIn("rmtree", runner)

    def test_machine_schema_covers_contract(self):
        schema = json.loads((ROOT / "diagnostics/grid_layout/raw.schema.json").read_text())
        self.assertEqual(schema["properties"]["upstream_revision"]["const"], verify.UPSTREAM)
        names = {e["properties"]["type"]["const"] for e in schema["$defs"]["event"]["oneOf"]}
        self.assertTrue({"request_layout", "request_layout_end", "prepaint", "paint", "callback", "click"} <= names)
        try: import jsonschema
        except ImportError: return
        jsonschema.Draft202012Validator.check_schema(schema)
        raw, _, _ = synthetic_checker_input()
        jsonschema.validate(raw, schema)

    def test_bundle_source_elf_raw_and_corruption_guards(self):
        raw, corpus, witnesses = synthetic_checker_input()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            files = {"raw.json": json.dumps(raw).encode(), "raw.stderr": b"",
                "scenarios.json": json.dumps(corpus).encode(), "probe": b"\x7fELFsynthetic-checker-only",
                "toolchain.txt": b"rustc 1.98.1 synthetic checker only\n", "build.stdout": b"", "build.stderr": b""}
            files.update({verify.retained_path(relative): (ROOT / relative).read_bytes() for relative in verify.RETAIN})
            files.update({"upstream/" + relative: b"synthetic checker only" for relative in verify.UPSTREAM_RETAIN})
            files["retained/diagnostics/grid_layout/scenarios.json"] = files["scenarios.json"]
            files["retained/diagnostics/grid_layout/witnesses.json"] = json.dumps(witnesses).encode()
            files["build-Cargo.toml"] = files["retained/adapters/grid_layout_rust/Cargo.toml"].replace(b'"../../../zed-source/crates/gpui"', b'"/synthetic-source/crates/gpui"')
            for name, content in files.items():
                path = directory / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            identity = {"commit": "a" * 40, "tree": "b" * 40, "clean": True}
            upstream = {"commit": verify.UPSTREAM, "tree": verify.UPSTREAM_TREE, "clean": True}
            manifest = {"schema_version": 1, "layer": verify.LAYER, "suite": identity, "suite_after": identity,
                "upstream": upstream, "upstream_after": upstream, "upstream_source_path": "/synthetic-source",
                "run_token": raw["run_token"], "build": {"command": ["cargo", "+1.98.1", "build", "--locked"], "returncode": 0, "timed_out": False},
                "execution": {"command": [str(directory / "probe"), str(directory / "scenarios.json"), raw["run_token"]], "returncode": 0, "timed_out": False},
                "files": {name: {"sha256": verify.digest(directory / name), "size": len(content)} for name, content in files.items()}}
            manifest_path = directory / "manifest.json"
            manifest_path.write_text(json.dumps(manifest))
            self.assertFalse(verify.verify_bundle(directory)["source_bound"])
            for mutate in (lambda m: m.update(run_token="cross-run-token-0000"),
                           lambda m: m["upstream"].update(commit="e" * 40),
                           lambda m: m["suite"].update(clean=False),
                           lambda m: m["execution"].update(returncode=1),
                           lambda m: m["execution"].update(command=["/bin/true"]),
                           lambda m: m["build"].update(timed_out=True),
                           lambda m: m["build"].update(command=["cargo", "build"]),
                           lambda m: m["files"].pop("probe"),
                           lambda m: m["files"].pop("retained/diagnostics/grid_layout/witnesses.json")):
                changed = copy.deepcopy(manifest)
                mutate(changed)
                manifest_path.write_text(json.dumps(changed))
                with self.assertRaises(ValueError): verify.verify_bundle(directory)
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaises(ValueError): verify.verify_bundle(directory, suite_commit="e" * 40)
            with self.assertRaises(ValueError): verify.verify_bundle(directory, suite_tree="e" * 40)
            def git(arguments, cwd=None, text=False):
                if arguments[1] == "rev-parse": return "b" * 40 + "\n"
                return files[verify.retained_path(arguments[2].split(":", 1)[1])]
            with patch.object(verify.subprocess, "check_output", side_effect=git):
                verify.verify_bundle(directory, "a" * 40, "b" * 40, suite_source=ROOT)
                name = "retained/adapters/grid_layout_rust/src/main.rs"
                (directory / name).write_bytes(b"changed observer but rehashed inventory")
                changed = copy.deepcopy(manifest)
                changed["files"][name] = {"sha256": verify.digest(directory / name), "size": (directory / name).stat().st_size}
                manifest_path.write_text(json.dumps(changed))
                with self.assertRaisesRegex(ValueError, "exact committed source"):
                    verify.verify_bundle(directory, "a" * 40, "b" * 40, suite_source=ROOT)
            (directory / name).write_bytes(files[name])
            manifest_path.write_text(json.dumps(manifest))
            (directory / "raw.stderr").write_bytes(b"tampered raw stream")
            with self.assertRaises(ValueError): verify.verify_bundle(directory)


if __name__ == "__main__": unittest.main()
