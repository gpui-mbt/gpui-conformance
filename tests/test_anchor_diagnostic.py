"""Synthetic checker controls and source inspection, never actual GPUI execution."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("anchor_diagnostic_verify", ROOT / "diagnostics/anchor/verify.py")
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


def synthetic_checker_input(interactive=False, count=1):
    """Hand-authored lifecycle fixture; all geometry is synthetic checker input."""
    case = {"id": "synthetic-checker-only", "window": [640, 480], "parent_origin": [80, 80],
        "parent_size": [160, 120], "scale_factor": 1, "popups": [
            {"id": "popup" + str(index), "anchor": "TopLeft", "position": [220, 180],
             "position_mode": "Window", "size": [80, 24], "priority": 0, "interactive": interactive}
            for index in range(count)], "later_sibling": [220, 180, 80, 24],
        "hits": [{"id": "overlap", "position": [230, 190]}]}
    corpus = {"schema_version": 1, "coordinate_system": "synthetic checker input only", "cases": [case]}
    geometry = {"$host": [0, 0, 640, 480], "parent": [80, 80, 160, 120],
        "button": [80, 80, 120, 65], "sibling": [220, 180, 80, 24]}
    for popup in case["popups"]:
        name = popup["id"]
        # This arbitrary static origin is NOT a measured GPUI result/witness.
        geometry.update({name: [220, 180, 80, 24], "anchor_" + name: [80, 145, 80, 24], "deferred_" + name: [80, 145, 80, 24]})
    events, frame = [], 0
    def emit(event, operation):
        events.append({"sequence": len(events), "operation": operation, "frame": frame, "event": event})
    for operation, scale, input_value in [("initial", 2, {"action": "open_window"}),
            ("configured", 1, {"action": "set_scale_factor", "scale_factor": 1})]:
        emit({"type": "operation_start", "input": input_value}, operation)
        frame += 1
        def event(value): emit(value, operation)
        def begin(phase, node):
            value = {"type": phase, "node": node}
            if phase in ("prepaint", "paint"): value["bounds"] = geometry[node].copy()
            if phase == "prepaint": value["content_mask"] = [0, 0, 640, 480]
            event(value)
        def end(phase, node): event({"type": phase + "_end", "node": node})
        event({"type": "frame_start", "scale_factor": scale, "window_size": [640, 480]})
        for phase in ("request_layout", "prepaint", "paint"):
            begin(phase, "$host"); begin(phase, "parent")
            begin(phase, "button"); end(phase, "button")
            for popup in case["popups"]:
                name = popup["id"]
                begin(phase, "deferred_" + name)
                if phase == "request_layout":
                    begin(phase, "anchor_" + name); begin(phase, name)
                    end(phase, name); end(phase, "anchor_" + name)
                end(phase, "deferred_" + name)
            end(phase, "parent")
            begin(phase, "sibling"); end(phase, "sibling")
            end(phase, "$host")
            if phase != "request_layout":
                for popup in case["popups"]:
                    name = popup["id"]
                    begin(phase, "anchor_" + name); begin(phase, name)
                    end(phase, name); end(phase, "anchor_" + name)
        emit({"type": "operation_end", "scale_factor": scale}, operation)
    emit({"type": "operation_start", "input": {"action": "click", "position": [230, 190]}}, "overlap")
    node = "popup" + str(count - 1) if interactive else "sibling"
    contexts = ["AnchorRoot"] + (["AnchorParent"] if interactive else []) + ["Leaf_" + node]
    emit({"type": "mouse_down", "node": node, "position": [230, 190], "contexts": contexts}, "overlap")
    emit({"type": "click", "node": node, "detail": {"kind": "mouse", "down": [230, 190], "up": [230, 190]}, "contexts": contexts}, "overlap")
    emit({"type": "operation_end", "scale_factor": 1}, "overlap")
    raw = {"schema_version": 1, "layer": verify.LAYER, "fixture": "font-free-bounded-anchor",
        "text_system": "NoopTextSystem; no text used", "upstream_revision": verify.UPSTREAM,
        "run_token": "synthetic-checker-only-0001", "input": corpus, "cases": [{"id": case["id"], "events": events}]}
    return raw, corpus


def resequence(raw):
    for sequence, entry in enumerate(raw["cases"][0]["events"]): entry["sequence"] = sequence


def synthetic_bundle(directory):
    raw, corpus = synthetic_checker_input()
    files = {"raw.json": json.dumps(raw).encode(), "raw.stderr": b"", "scenarios.json": json.dumps(corpus).encode(),
        "probe": b"\x7fELFsynthetic-checker-only", "toolchain.txt": b"rustc 1.98.1 synthetic checker only\n", "build.stdout": b"", "build.stderr": b""}
    files.update({verify.retained_path(relative): (ROOT / relative).read_bytes() for relative in verify.RETAIN})
    files.update({"upstream/" + relative: b"synthetic checker only" for relative in verify.UPSTREAM_RETAIN})
    files["retained/diagnostics/anchor/scenarios.json"] = files["scenarios.json"]
    files["build-Cargo.toml"] = files["retained/adapters/anchor_rust/Cargo.toml"].replace(b'"../../../zed-source/crates/gpui"', b'"/synthetic-source/crates/gpui"')
    for name, content in files.items():
        path = directory / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(content)
    identity = {"commit": "a" * 40, "tree": "b" * 40, "clean": True}
    upstream = {"commit": verify.UPSTREAM, "tree": verify.UPSTREAM_TREE, "clean": True}
    build_path = directory.parent / ("anchor-build-" + raw["run_token"]) / "adapter/Cargo.toml"
    manifest = {"schema_version": 1, "layer": verify.LAYER, "suite": identity, "suite_after": identity,
        "upstream": upstream, "upstream_after": upstream, "upstream_source_path": "/synthetic-source", "run_token": raw["run_token"],
        "build": {"command": ["cargo", "+1.98.1", "build", "--locked", "--manifest-path", str(build_path)], "returncode": 0, "timed_out": False},
        "execution": {"command": [str(directory / "probe"), str(directory / "scenarios.json"), raw["run_token"]], "returncode": 0, "timed_out": False},
        "files": {name: {"sha256": verify.digest(directory / name), "size": len(content)} for name, content in files.items()}}
    (directory / "manifest.json").write_text(json.dumps(manifest))
    return raw, corpus, files, manifest


class AnchorDiagnosticContracts(unittest.TestCase):
    def test_curated_input_contract_and_scope(self):
        corpus = json.loads((ROOT / "diagnostics/anchor/scenarios.json").read_text())
        verify.validate_scenarios(corpus)
        self.assertEqual(len(corpus["cases"]), 24)
        self.assertEqual(sum(len(case["hits"]) for case in corpus["cases"]), 5)
        cases = {case["id"]: case for case in corpus["cases"]}
        self.assertEqual({cases["example-local-" + name]["popups"][0]["anchor"] for name in verify.ANCHORS}, set(verify.ANCHORS))
        for sign in ("positive", "negative"):
            self.assertEqual({cases[f"half-translation-{sign}-{scale:g}"]["scale_factor"] for scale in (1, 1.25, 2)}, {1, 1.25, 2})
        transparent, interactive = [copy.deepcopy(cases["later-sibling-" + kind]) for kind in ("transparent", "interactive")]
        for case in (transparent, interactive): case.pop("id"); case["popups"][0]["interactive"] = False
        self.assertEqual(transparent, interactive)
        self.assertTrue(all(popup["priority"] == 0 for case in corpus["cases"] for popup in case["popups"]))

    def test_synthetic_trace_is_checker_input_only(self):
        for interactive, count in ((False, 1), (True, 1), (True, 3)):
            raw, corpus = synthetic_checker_input(interactive, count)
            result = verify.verify_observations(raw, corpus)
            expected = "popup" + str(count - 1) if interactive else "sibling"
            self.assertEqual(result["cases"][0]["operations"][2]["callbacks"][1]["node"], expected)
            self.assertEqual(result["cases"][0]["operations"][0]["frames"][0]["anchor_static_origins"]["popup0"], [80, 145])

    def test_static_origin_is_observed_not_a_guessed_witness(self):
        raw, corpus = synthetic_checker_input()
        for entry in raw["cases"][0]["events"]:
            event = entry["event"]
            if event.get("node") in ("anchor_popup0", "deferred_popup0") and "bounds" in event:
                event["bounds"][:2] = [77, 131]
        # Window mode repositions from this arbitrary original origin. No
        # required bottom-of-button witness may reject a valid raw observation.
        verify.verify_observations(raw, corpus)

    def test_logical_half_rounding_separate_from_device_rounding(self):
        self.assertEqual([verify.round_away(x) for x in (.5, -.5, 1.5, -1.5)], [1, -1, 2, -2])
        for anchor, position, expected in [("TopLeft", [.5, .5], [81, 146]), ("BottomRight", [79.5, 23.5], [79, 144])]:
            raw, corpus = synthetic_checker_input()
            popup = corpus["cases"][0]["popups"][0]
            popup.update(anchor=anchor, position=position, position_mode="Local")
            for entry in raw["cases"][0]["events"]:
                event = entry["event"]
                if event.get("node") == "popup0" and "bounds" in event: event["bounds"][:2] = expected
            verify.verify_observations(raw, corpus)
            for entry in raw["cases"][0]["events"]:
                event = entry["event"]
                if event.get("node") == "popup0" and "bounds" in event: event["bounds"][0] += 1
            with self.assertRaisesRegex(ValueError, "rounding"): verify.verify_observations(raw, corpus)

    def test_fractional_scale_has_a_second_device_offset_snap(self):
        raw, corpus = synthetic_checker_input()
        case = corpus["cases"][0]
        case["scale_factor"] = 1.25
        case["popups"][0].update(position_mode="Local", position=[.5, .5])
        for entry in raw["cases"][0]["events"]:
            event = entry["event"]
            configured = entry["operation"] != "initial"
            if event["type"] == "operation_start" and event["input"]["action"] == "set_scale_factor": event["input"]["scale_factor"] = 1.25
            if configured and "scale_factor" in event: event["scale_factor"] = 1.25
            if "bounds" in event:
                if configured and event["node"] == "button": event["bounds"][3] = 64.8
                if configured and event["node"] in ("anchor_popup0", "deferred_popup0"): event["bounds"][1] = 144.8
                if event["node"] == "popup0": event["bounds"][:2] = [80.8, 145.6] if configured else [81, 146]
        verify.verify_observations(raw, corpus)
        self.assertAlmostEqual(verify.snap_offset(1, 1.25), .8)
        self.assertAlmostEqual(verify.snap_offset(-1, 1.25), -.8)
        for entry in raw["cases"][0]["events"]:
            event = entry["event"]
            if entry["operation"] == "configured" and event.get("node") == "popup0" and "bounds" in event: event["bounds"][0] = 81
        with self.assertRaises(ValueError): verify.verify_observations(raw, corpus)

    def test_retained_original_epsilon_false_acceptance_now_rejected(self):
        report = json.loads((ROOT / "diagnostics/anchor/epsilon-regression.json").read_text())
        self.assertEqual(report["baseline_commit"], "abbc3c7337faec3239f07f54268a567a335f47c5")
        self.assertEqual(report["baseline_result"], "ACCEPTED (checker false acceptance)")
        self.assertEqual(len(report["affected_records"]), 4)
        raw, corpus = synthetic_checker_input()
        for entry in raw["cases"][0]["events"]:
            event = entry["event"]
            if event.get("node") == "popup0" and "bounds" in event: event["bounds"][0] += .004
        import hashlib
        canonical = json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()
        self.assertEqual(hashlib.sha256(canonical).hexdigest(), report["canonical_mutated_raw_sha256"])
        with self.assertRaisesRegex(ValueError, "physical edge"): verify.verify_observations(raw, corpus)

    def test_named_logical_geometry_allowance_boundaries(self):
        allowance = verify.GEOMETRY_F32_ALLOWANCE
        self.assertEqual(allowance, 2 ** -10)
        verify.close(220 + allowance, 220, "within logical geometry bound")
        with self.assertRaises(ValueError): verify.close(220 + allowance + 2 ** -20, 220, "beyond logical geometry bound")
        # Coherent raw jitter inside BOTH allowances is accepted as synthetic
        # checker input. It is never described as observed GPUI precision.
        raw, corpus = synthetic_checker_input()
        for entry in raw["cases"][0]["events"]:
            event = entry["event"]
            if event.get("node") == "popup0" and "bounds" in event: event["bounds"][0] += allowance / 2
        verify.verify_observations(raw, corpus)

    def test_named_physical_grid_allowance_boundaries_at_each_scale(self):
        allowance = verify.PHYSICAL_GRID_F32_ALLOWANCE
        self.assertEqual(allowance, 2 ** -10)
        for scale in (1, 1.25, 2):
            within = [220 + (allowance - 2 ** -20) / scale, 180, 80, 24]
            beyond = [220 + (allowance + 2 ** -20) / scale, 180, 80, 24]
            with self.subTest(scale=scale):
                verify.physical_grid(within, scale, "within device-pixel bound")
                with self.assertRaisesRegex(ValueError, "physical edge"):
                    verify.physical_grid(beyond, scale, "beyond device-pixel bound")

    def test_raw_coordinate_size_far_edge_numerical_qualification(self):
        verify.qualify_bounds([4095, -4096, 1, 2048], "boundary")
        for rectangle, reason in [([4096.25, 0, 0, 0], "coordinate"),
                ([0, 0, 2048.25, 1], "size"), ([4096, 0, .25, 1], "far edge")]:
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, "numerically unqualified raw " + reason):
                verify.qualify_bounds(rectangle, "out-of-domain synthetic output")
        raw, corpus = synthetic_checker_input()
        for entry in raw["cases"][0]["events"]:
            event = entry["event"]
            if event.get("node") == "anchor_popup0" and "bounds" in event: event["bounds"][0] = 4096.25
        with self.assertRaisesRegex(ValueError, "numerically unqualified"): verify.verify_observations(raw, corpus)

    def test_requested_scales_and_reused_bounds_are_exact(self):
        for kind in ("frame_start", "operation_end"):
            raw, corpus = synthetic_checker_input()
            event = next(entry["event"] for entry in raw["cases"][0]["events"] if entry["event"]["type"] == kind)
            event["scale_factor"] += verify.GEOMETRY_F32_ALLOWANCE / 2
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "binary-exact scale"):
                verify.verify_observations(raw, corpus)
        raw, corpus = synthetic_checker_input()
        event = next(entry["event"] for entry in raw["cases"][0]["events"] if entry["event"]["type"] == "paint" and entry["event"].get("node") == "popup0")
        event["bounds"][0] += 2 ** -20
        with self.assertRaisesRegex(ValueError, "paint/prepaint agreement"): verify.verify_observations(raw, corpus)

    def test_lifecycle_and_identity_corruptions(self):
        for mutation in ("return", "missing", "frame", "operation", "sequence", "trailing", "layer", "pin", "input"):
            raw, corpus = synthetic_checker_input()
            events = raw["cases"][0]["events"]
            if mutation == "return": events[5]["event"]["node"] = "$host"
            if mutation == "missing": events.pop(6); resequence(raw)
            if mutation == "frame": events[4]["frame"] += 1
            if mutation == "operation": events[4]["operation"] = "configured"
            if mutation == "sequence": events[4]["sequence"] = 99
            if mutation == "trailing": events.append(copy.deepcopy(events[-1])); resequence(raw)
            if mutation == "layer": raw["layer"] = "unchanged-example"
            if mutation == "pin": raw["upstream_revision"] = "d" * 40
            if mutation == "input": raw["input"] = {}
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): verify.verify_observations(raw, corpus)

    def test_coherent_engine_shaped_wrong_geometry_is_semantic_failure(self):
        for node, field, value in [("popup0", "bounds", [221, 180, 80, 24]),
                ("anchor_popup0", "bounds", [81, 145, 80, 24]),
                ("parent", "bounds", [81, 80, 160, 120]),
                ("popup0", "content_mask", [0, 0, 600, 480]),
                ("popup0", "bounds", [220, 180, float("nan"), 24])]:
            raw, corpus = synthetic_checker_input()
            for entry in raw["cases"][0]["events"]:
                event = entry["event"]
                if event.get("node") == node and field in event: event[field] = value
            with self.subTest(node=node, field=field), self.assertRaises(ValueError): verify.verify_observations(raw, corpus)

    def test_callbacks_and_actual_dispatch_ancestry_corruptions(self):
        mutations = [lambda e: e.update(node="popup0"), lambda e: e.update(contexts=["AnchorRoot", "Leaf_sibling", "AnchorParent"]),
            lambda e: e["detail"].update(down=[231, 190]), lambda e: e["detail"].update(kind="keyboard")]
        for mutate in mutations:
            raw, corpus = synthetic_checker_input()
            event = next(entry["event"] for entry in raw["cases"][0]["events"] if entry["event"]["type"] == "click")
            mutate(event)
            with self.assertRaises(ValueError): verify.verify_observations(raw, corpus)
        raw, corpus = synthetic_checker_input()
        corpus["cases"][0]["hits"][0]["position"] = [220, 190]
        raw["cases"][0]["events"][-4]["event"]["input"]["position"] = [220, 190]
        with self.assertRaisesRegex(ValueError, "edge hit"): verify.verify_observations(raw, corpus)

    def test_stable_deferred_order_rejects_coherent_permutation(self):
        raw, corpus = synthetic_checker_input(True, 3)
        for entry in raw["cases"][0]["events"]:
            event = entry["event"]
            if "node" in event and event["type"] not in ("mouse_down", "click"):
                event["node"] = event["node"].replace("popup0", "SWAP").replace("popup1", "popup0").replace("SWAP", "popup1")
        with self.assertRaisesRegex(ValueError, "stable deferred"): verify.verify_observations(raw, corpus)

    def test_invalid_or_expanded_input_rejected(self):
        mutations = [lambda c: c["cases"].append(copy.deepcopy(c["cases"][0])),
            lambda c: c["cases"][0].update(scale_factor=3), lambda c: c["cases"][0].update(parent_size=[0, 120]),
            lambda c: c["cases"][0]["popups"][0].update(priority=1), lambda c: c["cases"][0]["popups"][0].update(anchor="Center"),
            lambda c: c["cases"][0]["popups"][0].update(position_mode="SwitchAnchor"),
            lambda c: c["cases"][0]["popups"][0].update(position=[.1, 0]),
            lambda c: c["cases"][0]["popups"][0].update(offset=[0, 0]),
            lambda c: c["cases"][0]["popups"][0].update(id="button"),
            lambda c: c["cases"][0]["popups"][0].update(size=[float("nan"), 24])]
        for mutate in mutations:
            _, corpus = synthetic_checker_input(); mutate(corpus)
            with self.assertRaises(ValueError): verify.validate_scenarios(corpus)

    def test_multiple_real_frames_retained_after_host_return(self):
        raw, corpus = synthetic_checker_input()
        events = raw["cases"][0]["events"]
        first = next(i for i, e in enumerate(events) if e["operation"] == "configured")
        last = next(i for i, e in enumerate(events) if e["operation"] == "overlap") - 1
        extra = copy.deepcopy(events[first + 1:last])
        for entry in extra + events[last:]: entry["frame"] = 3
        events[last:last] = extra; resequence(raw)
        result = verify.verify_observations(raw, corpus)
        self.assertEqual(len(result["cases"][0]["operations"][1]["frames"]), 2)

    def test_source_delegates_without_expected_layout_or_hit_solver(self):
        source = (ROOT / "adapters/anchor_rust/src/main.rs").read_text()
        compact = "".join(source.split())
        for value in ("TestAppContext::single()", "VisualTestContext::from_window", "anchored()", "deferred(",
                ".snap_to_window()", ".with_priority(", "window.focus(", "simulate_click", "window.content_mask()"):

            self.assertIn(value, source)
        self.assertIn("window.context_stack()", compact)
        for value in ("self.inner.request_layout(", "self.inner.prepaint(", "self.inner.paint("): self.assertIn(value, compact)
        for value in ("witnesses.json", "expected_bounds", "floor(", "ceil(", "layout_as_root(", "layout_bounds(", "insert_hitbox("):
            self.assertNotIn(value, source)
        self.assertIn('let mut parent = div()\n            .relative()\n            .key_context("AnchorParent")', source)
        self.assertNotIn(".flex()", source)
        lock = (ROOT / "adapters/anchor_rust/Cargo.lock").read_text()
        self.assertEqual(lock, (ROOT / "adapters/grid_layout_rust/Cargo.lock").read_text().replace("gpui-grid-layout-diagnostic", "gpui-anchor-diagnostic"))

    def test_schema_and_ci_failure_retention(self):
        schema = json.loads((ROOT / "diagnostics/anchor/raw.schema.json").read_text())
        self.assertEqual(schema["properties"]["upstream_revision"]["const"], verify.UPSTREAM)
        self.assertEqual(schema["$defs"]["popup"]["properties"]["priority"], {"const": 0})
        try: import jsonschema
        except ImportError: pass
        else:
            jsonschema.Draft202012Validator.check_schema(schema)
            raw, _ = synthetic_checker_input(); jsonschema.validate(raw, schema)
        workflow = (ROOT / ".github/workflows/anchor-diagnostic.yml").read_text()
        self.assertIn(verify.UPSTREAM, workflow); self.assertIn("if: always()", workflow); self.assertIn("--suite-tree", workflow)
        self.assertNotIn("--release", workflow)
        runner = (ROOT / "diagnostics/anchor/run.py").read_text()
        self.assertIn("8 * 1024**3", runner); self.assertIn("verification-failure.json", runner); self.assertNotIn("rmtree", runner)

    def test_provenance_integrity_distinct_from_semantic_fault_controls(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "_build/anchor-evidence"
            raw, corpus, files, manifest = synthetic_bundle(directory)
            manifest_path = directory / "manifest.json"
            self.assertFalse(verify.verify_bundle(directory)["source_bound"])
            for mutate in [lambda m: m.update(run_token="wrong-run-token-0001"), lambda m: m["upstream"].update(commit="e" * 40),
                    lambda m: m["suite"].update(clean=False), lambda m: m["build"].update(timed_out=True),
                    lambda m: m["build"]["command"].__setitem__(-1, "/unrelated/Cargo.toml"),
                    lambda m: m["execution"]["command"].__setitem__(1, "/unrelated/input"), lambda m: m["files"].pop("probe")]:
                changed = copy.deepcopy(manifest); mutate(changed); manifest_path.write_text(json.dumps(changed))
                with self.assertRaises(ValueError): verify.verify_bundle(directory)
            manifest_path.write_text(json.dumps(manifest))
            (directory / "raw.stderr").write_bytes(b"corrupted")
            with self.assertRaisesRegex(ValueError, "changed evidence"): verify.verify_bundle(directory)
            (directory / "raw.stderr").write_bytes(b"")
            # Coherent wrong engine-shaped geometry, rehashed, must still fail
            # the semantic check. It is synthetic and is not called an engine bug.
            for entry in raw["cases"][0]["events"]:
                event = entry["event"]
                if event.get("node") == "popup0" and "bounds" in event: event["bounds"][0] += 1
            path = directory / "raw.json"; path.write_text(json.dumps(raw))
            manifest["files"]["raw.json"] = {"sha256": verify.digest(path), "size": path.stat().st_size}
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "translation/clamp"): verify.verify_bundle(directory)

    def test_copied_artifact_uses_exact_original_root_without_old_filesystem(self):
        with tempfile.TemporaryDirectory() as temporary:
            original = Path(temporary) / "_build/anchor-evidence"
            synthetic_bundle(original)
            copied = Path(temporary) / "downloaded-artifact"
            original.rename(copied)
            self.assertFalse(original.exists())
            with self.assertRaisesRegex(ValueError, "execution executable/input/token"):
                verify.verify_bundle(copied)
            self.assertFalse(verify.verify_bundle(copied, recorded_execution_root=original)["source_bound"])
            with self.assertRaises(ValueError): verify.verify_bundle(copied, recorded_execution_root="relative/root")
            with self.assertRaises(ValueError): verify.verify_bundle(copied, recorded_execution_root=original.parent / "wrong")
            manifest_path = copied / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            for mutate in (lambda m: m["execution"]["command"].__setitem__(0, str(original / "different-probe")),
                    lambda m: m["execution"]["command"].__setitem__(1, str(original / "different-input")),
                    lambda m: m["execution"]["command"].__setitem__(2, "wrong-token"),
                    lambda m: m["build"]["command"].__setitem__(-1, "/unrelated/Cargo.toml")):
                changed = copy.deepcopy(manifest); mutate(changed); manifest_path.write_text(json.dumps(changed))
                with self.assertRaises(ValueError): verify.verify_bundle(copied, recorded_execution_root=original)

    def test_rehashed_observer_source_still_requires_exact_git_blob(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "_build/anchor-evidence"
            _, _, files, manifest = synthetic_bundle(directory)
            def git(arguments, cwd=None, text=False):
                if arguments[1] == "rev-parse": return "b" * 40 + "\n"
                return files[verify.retained_path(arguments[2].split(":", 1)[1])]
            with patch.object(verify.subprocess, "check_output", side_effect=git):
                verify.verify_bundle(directory, "a" * 40, "b" * 40, suite_source=ROOT)
                relative = "retained/adapters/anchor_rust/src/main.rs"
                path = directory / relative; path.write_bytes(b"changed observer")
                manifest["files"][relative] = {"sha256": verify.digest(path), "size": path.stat().st_size}
                (directory / "manifest.json").write_text(json.dumps(manifest))
                with self.assertRaisesRegex(ValueError, "exact committed source"):
                    verify.verify_bundle(directory, "a" * 40, "b" * 40, suite_source=ROOT)


if __name__ == "__main__": unittest.main()
