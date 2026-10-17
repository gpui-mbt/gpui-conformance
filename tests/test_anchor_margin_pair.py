"""Source contracts and explicitly synthetic checker-unit tests.

Nothing in this file executes either engine, supplies production-mutant evidence,
reproduces candidate anchor arithmetic, or proves a real margin-pair pass. The
candidate fixtures copy coordinates from the frozen Rust checker's synthetic
observation records. The arbitrary static origin belongs only to those fixtures.
"""
import copy
import importlib.util
import json
from pathlib import Path
import shlex
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PAIR = ROOT / "diagnostics/anchor_margin_pair"


def load_module(name, path, imports=None):
    """Avoid colliding with the frozen suite's bare compare/run module names."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, imports or {}):
        spec.loader.exec_module(module)
    return module


compare = load_module("anchor_margin_pair_compare_tests", PAIR / "compare.py")
runner = load_module("anchor_margin_pair_run_tests", PAIR / "run.py", {"compare": compare})
verifier = load_module("anchor_margin_pair_verify_tests", PAIR / "verify.py", {"compare": compare, "run": runner})
helper = load_module("anchor_margin_synthetic_helper", ROOT / "tests/test_anchor_margin_diagnostic.py")
mutants = load_module("anchor_margin_pair_mutants_tests", PAIR / "run_mutants.py",
                      {"compare": compare, "run": runner, "verify": verifier})


def synthetic_pair(case_id=None):
    """Checker data only: copy baseline observations, never candidate anchor math."""
    rust, inputs = helper.single(case_id) if case_id else helper.synthetic_trace()
    candidates = []
    for case, original in zip(inputs["cases"], rust["cases"]):
        events, frame = [], 0
        for operation in ("initial", "configured"):
            records = [e for e in original["events"] if e["operation"] == operation]
            start = records[0]["event"]
            frame_start = next(e["event"] for e in records if e["event"]["type"] == "frame_start")
            observed = {e["event"]["node"]: copy.deepcopy(e["event"]["bounds"])
                        for e in records if e["event"]["type"] == "prepaint"}
            observed["$parent_position"] = [0, 0, 0, 0]
            scale = frame_start["scale_factor"]
            def emit(event):
                events.append(dict(sequence=len(events), operation=operation, frame=frame, event=copy.deepcopy(event)))
            emit(start)
            frame += 1
            emit(dict(type="frame_start", scale_factor=scale, window_size=case["window"]))
            for kind in ("request_start", "request_end", "prepaint_start"):
                emit(dict(type=kind))
            emit(dict(type="prepaint_end", overflow=False))
            for name, node in compare.topology().items():
                emit(dict(type="node", node=name, id=node["id"], parent=node["parent"],
                          bounds=observed[name], pointer_events=False, focusable=False))
            viewport = [0, 0, *case["window"]]
            for kind, name, bounds in (("clip_push", "$host", viewport),
                    ("quad", "button", observed["button"]), ("clip_pop", "$host", None),
                    ("clip_push", "anchor", viewport), ("quad", "popup", observed["popup"]),
                    ("clip_pop", "anchor", None)):
                emit(dict(type="scene", kind=kind, node=name, bounds=bounds))
            width, height = case["window"]
            for side, position in (("right", [width + 1, height / 2]), ("bottom", [width / 2, height + 1])):
                emit(dict(type="viewport_hit", side=side, position=position, target=None))
            emit(dict(type="frame_end", scale_factor=scale, window_size=case["window"]))
            emit(dict(type="operation_end", scale_factor=scale))
        candidates.append(dict(id=case["id"], events=events))
    candidate = dict(schema_version=1, layer=compare.CANDIDATE_LAYER,
                     fixture="font-free-bounded-anchor-margin", input=copy.deepcopy(inputs),
                     run_token="synthetic-checker-only-0001", cases=candidates)
    return rust, candidate, inputs


def event_entries(raw, kind=None, operation=None, frame=None):
    return [e for e in raw["cases"][0]["events"]
            if (kind is None or e["event"]["type"] == kind)
            and (operation is None or e["operation"] == operation)
            and (frame is None or e["frame"] == frame)]


def first(raw, kind, operation="configured", node=None):
    return next(e["event"] for e in event_entries(raw, kind, operation)
                if node is None or e["event"].get("node") == node)


def renumber(raw):
    for case in raw["cases"]:
        for index, entry in enumerate(case["events"]):
            entry["sequence"] = index


def append_configured_frame(raw):
    """Repeat a synthetic recorded frame; no engine is run and no output is dropped."""
    events = raw["cases"][0]["events"]
    configured = [e for e in events if e["operation"] == "configured"]
    copied = copy.deepcopy(configured[1:-1])
    next_frame = configured[-1]["frame"] + 1
    for entry in copied:
        entry["frame"] = next_frame
    events[-1]["frame"] = next_frame
    events[-1:-1] = copied
    renumber(raw)


def change_node_bounds(raw, node, index=0, delta=1, frame=2):
    """Keep synthetic scene geometry coherent so the paired check sees the error."""
    for entry in event_entries(raw, frame=frame):
        event = entry["event"]
        if event.get("node") == node and (event["type"] == "node" or event.get("kind") == "quad"):
            event["bounds"][index] += delta


class SyntheticMarginPairTests(unittest.TestCase):
    def setUp(self):
        self.rust, self.raw, self.inputs = synthetic_pair("cross-right-margin8-scale1")

    def test_full_88_case_synthetic_pair_and_claim_boundary(self):
        rust, candidate, inputs = synthetic_pair()
        result = compare.compare_observations(rust, candidate, inputs)
        self.assertTrue(result["passed"])
        self.assertEqual(result["counts"], dict(cases=88, rust_frames=176, candidate_frames=176,
            compared_operations=176, configured_comparisons=88, paired_clicks=0,
            candidate_only_noninteractive_hit_probes=352))
        self.assertIn("No paired pointer", result["claim"])
        self.assertIn("Redraw counts never paired", result["frame_policy"])

    def test_extra_candidate_and_rust_redraw_counts_need_not_match(self):
        for extra_candidate, extra_rust in ((True, False), (False, True)):
            rust, candidate, inputs = synthetic_pair("cross-right-margin8-scale1")
            append_configured_frame(candidate if extra_candidate else rust)
            result = compare.compare_observations(rust, candidate, inputs)
            self.assertTrue(result["passed"])
            self.assertEqual(result["counts"]["candidate_frames"], 3 if extra_candidate else 2)
            self.assertEqual(result["counts"]["rust_frames"], 3 if extra_rust else 2)
            self.assertEqual(result["counts"]["compared_operations"], 2)
            self.assertEqual(result["counts"]["configured_comparisons"], 1)
            operation = result["cases"][0]["operations"][1]
            self.assertEqual(operation["candidate_frame_ids"], [2, 3] if extra_candidate else [2])
            self.assertEqual(operation["rust_frame_ids"], [2, 3] if extra_rust else [2])
            self.assertEqual(operation["compared_candidate_frame"], 3 if extra_candidate else 2)
            self.assertEqual(operation["compared_rust_frame"], 3 if extra_rust else 2)

    def test_operation_final_is_compared_but_every_frame_is_retained(self):
        append_configured_frame(self.raw)
        change_node_bounds(self.raw, "popup", delta=1, frame=2)
        # A structurally valid intermediate redraw is retained, not paired to a
        # different engine's redraw. Only the operation's final is compared.
        result = compare.compare_observations(self.rust, self.raw, self.inputs)
        self.assertTrue(result["passed"])
        self.assertEqual(result["cases"][0]["operations"][1]["candidate_frame_ids"], [2, 3])
        change_node_bounds(self.raw, "popup", delta=1, frame=3)
        result = compare.compare_observations(self.rust, self.raw, self.inputs)
        self.assertFalse(result["passed"])
        self.assertEqual({m["operation"] for m in result["mismatches"]}, {"configured"})

    def test_initial_and_intermediate_invalid_frames_cannot_be_hidden(self):
        for frame in (1, 2):
            raw = copy.deepcopy(self.raw)
            append_configured_frame(raw)
            event = next(e["event"] for e in event_entries(raw, "node", frame=frame))
            event["bounds"][0] = 5000
            with self.subTest(frame=frame), self.assertRaises(ValueError):
                compare.compare_observations(self.rust, raw, self.inputs)
        append_configured_frame(self.rust)
        first(self.rust, "prepaint", "configured")["content_mask"][0] = 1
        with self.assertRaises(ValueError):
            compare.compare_observations(self.rust, self.raw, self.inputs)

    def test_all_paired_geometry_including_static_anchor_is_compared(self):
        for node in ("$host", "parent", "button", "anchor", "popup"):
            raw = copy.deepcopy(self.raw)
            change_node_bounds(raw, node)
            result = compare.compare_observations(self.rust, raw, self.inputs)
            with self.subTest(node=node):
                self.assertFalse(result["passed"])
                self.assertIn("bounds/" + node, {m["field"] for m in result["mismatches"]})
                with self.assertRaisesRegex(ValueError, "actual margin pair mismatch"):
                    compare.require_semantic_match(result)
        for coordinate in (1, 2, 3):
            raw = copy.deepcopy(self.raw)
            change_node_bounds(raw, "popup", index=coordinate)
            self.assertFalse(compare.compare_observations(self.rust, raw, self.inputs)["passed"])

    def test_rust_getter_and_candidate_bounds_translation_are_not_equated(self):
        rust, candidate, inputs = synthetic_pair("half-local-positive-margin8-scale1.25")
        result = compare.compare_observations(rust, candidate, inputs)
        operation = result["cases"][0]["operations"][1]
        self.assertTrue(result["passed"])
        self.assertEqual(operation["rust_logical_offset_getter_observed"], [1, 1])
        for component in operation["candidate_bounds_translation_derived"]:
            self.assertAlmostEqual(component, .8)
        self.assertNotEqual(operation["rust_logical_offset_getter_observed"], operation["candidate_bounds_translation_derived"])
        self.assertNotIn("candidate_logical_offset_getter_observed", operation)
        first(candidate, "node")["logical_offset"] = [1, 1]
        with self.assertRaises(ValueError):
            compare.verify_candidate(candidate, inputs)

    def test_six_structural_nodes_and_all_noninteractive(self):
        verified = compare.verify_candidate(self.raw, self.inputs)
        expected = ["$host", "$parent_position", "parent", "button", "anchor", "popup"]
        self.assertEqual(list(verified[0]["operations"][0]["frames"][0]["observed_bounds"]), expected)
        for node in expected:
            for flag in ("pointer_events", "focusable"):
                raw = copy.deepcopy(self.raw)
                first(raw, "node", node=node)[flag] = True
                with self.subTest(node=node, flag=flag), self.assertRaises(ValueError):
                    compare.verify_candidate(raw, self.inputs)

    def test_missing_duplicate_and_misordered_lifecycle_each_frame_rejected(self):
        kinds = ("frame_start", "request_start", "request_end", "prepaint_start", "prepaint_end", "node", "scene", "viewport_hit", "frame_end")
        for frame in (1, 2):
            for kind in kinds:
                for mutation in ("omit", "duplicate"):
                    raw = copy.deepcopy(self.raw)
                    events = raw["cases"][0]["events"]
                    index = next(i for i, e in enumerate(events) if e["frame"] == frame and e["event"]["type"] == kind)
                    if mutation == "omit":
                        events.pop(index)
                    else:
                        events.insert(index, copy.deepcopy(events[index]))
                    renumber(raw)
                    with self.subTest(frame=frame, kind=kind, mutation=mutation), self.assertRaises(ValueError):
                        compare.verify_candidate(raw, self.inputs)
            raw = copy.deepcopy(self.raw)
            entries = event_entries(raw, frame=frame)
            start = next(e for e in entries if e["event"]["type"] == "request_start")
            end = next(e for e in entries if e["event"]["type"] == "request_end")
            start["event"], end["event"] = end["event"], start["event"]
            with self.assertRaises(ValueError):
                compare.verify_candidate(raw, self.inputs)

    def test_missing_duplicate_misordered_nodes_and_structural_lineage_rejected(self):
        for mutation in ("swap", "unknown", "wrong_id", "wrong_parent"):
            raw = copy.deepcopy(self.raw)
            nodes = event_entries(raw, "node", "configured")
            if mutation == "swap":
                nodes[2]["event"], nodes[3]["event"] = nodes[3]["event"], nodes[2]["event"]
            elif mutation == "unknown": nodes[2]["event"]["node"] = "invented"
            elif mutation == "wrong_id": nodes[2]["event"]["id"] = "999"
            else: nodes[2]["event"]["parent"] = "$host"
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                compare.verify_candidate(raw, self.inputs)

    def test_event_sequence_frame_and_operation_binding(self):
        for mutation in ("sequence", "frame", "interleave", "start_input", "end_scale", "trailing", "no_configured", "frame_skip"):
            raw = copy.deepcopy(self.raw)
            events = raw["cases"][0]["events"]
            if mutation == "sequence": events[3]["sequence"] = 999
            elif mutation == "frame": events[3]["frame"] = 0
            elif mutation == "interleave": events[3]["operation"] = "configured"
            elif mutation == "start_input": first(raw, "operation_start")["input"]["scale_factor"] = 1.25
            elif mutation == "end_scale": first(raw, "operation_end")["scale_factor"] = 2
            elif mutation == "trailing": events.append(copy.deepcopy(events[-1])); renumber(raw)
            elif mutation == "no_configured": events[:] = [e for e in events if e["operation"] != "configured"]
            elif mutation == "frame_skip":
                for entry in event_entries(raw, frame=2): entry["frame"] = 3
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                compare.verify_candidate(raw, self.inputs)

    def test_scene_balance_order_effective_masks_and_tree_geometry(self):
        for mutation in ("unbalanced", "reversed_leaves", "wrong_mask", "nested_mask", "quad_bounds", "unknown_leaf", "extra_root", "pop_bounds"):
            raw = copy.deepcopy(self.raw)
            scenes = event_entries(raw, "scene", "configured")
            if mutation == "unbalanced": scenes[-1]["event"]["node"] = "$host"
            elif mutation == "reversed_leaves": scenes[1]["event"], scenes[4]["event"] = scenes[4]["event"], scenes[1]["event"]
            elif mutation == "wrong_mask": scenes[3]["event"]["bounds"][2] -= 1
            elif mutation == "nested_mask": scenes[3]["event"]["node"] = "parent"; scenes[5]["event"]["node"] = "parent"
            elif mutation == "quad_bounds": scenes[4]["event"]["bounds"][0] += 1
            elif mutation == "unknown_leaf": scenes[4]["event"]["node"] = "anchor"
            elif mutation == "extra_root": scenes[3]["event"]["node"] = "$host"; scenes[5]["event"]["node"] = "$host"
            elif mutation == "pop_bounds": scenes[5]["event"]["bounds"] = [0, 0, 0, 0]
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                compare.verify_candidate(raw, self.inputs)

    def test_equivalent_root_clip_around_deferred_pass_is_accepted(self):
        events = self.raw["cases"][0]["events"]
        scenes = event_entries(self.raw, "scene", "configured")
        root_pop = scenes[2]
        events.remove(root_pop)
        events.insert(events.index(scenes[-1]) + 1, root_pop)
        renumber(self.raw)
        self.assertTrue(compare.compare_observations(self.rust, self.raw, self.inputs)["passed"])

    def test_candidate_only_hits_are_exact_noninteractive_smoke(self):
        for mutation in ("target", "position", "side", "order"):
            raw = copy.deepcopy(self.raw)
            probes = event_entries(raw, "viewport_hit", "configured")
            if mutation == "target": probes[0]["event"]["target"] = "popup"
            elif mutation == "position": probes[0]["event"]["position"][0] -= 2
            elif mutation == "side": probes[0]["event"]["side"] = "bottom"
            else: probes[0]["event"], probes[1]["event"] = probes[1]["event"], probes[0]["event"]
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                compare.verify_candidate(raw, self.inputs)

    def test_strict_transport_schema_identity_and_exact_corpus(self):
        for mutation in ("extra_top", "extra_case", "extra_entry", "extra_event", "schema", "layer", "fixture", "token_short", "token_long", "input", "case_id", "case_missing", "case_duplicate"):
            raw = copy.deepcopy(self.raw)
            if mutation == "extra_top": raw["unexpected"] = 1
            elif mutation == "extra_case": raw["cases"][0]["unexpected"] = 1
            elif mutation == "extra_entry": raw["cases"][0]["events"][0]["unexpected"] = 1
            elif mutation == "extra_event": first(raw, "frame_start")["unexpected"] = 1
            elif mutation in ("schema", "layer", "fixture"): raw[{"schema": "schema_version"}.get(mutation, mutation)] = "wrong"
            elif mutation == "token_short": raw["run_token"] = "short"
            elif mutation == "token_long": raw["run_token"] = "x" * 65
            elif mutation == "input": raw["input"]["cases"][0]["popup"]["margin"] = 0
            elif mutation == "case_id": raw["cases"][0]["id"] = "invented"
            elif mutation == "case_missing": raw["cases"] = []
            elif mutation == "case_duplicate": raw["cases"].append(copy.deepcopy(raw["cases"][0]))
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                compare.decode_transport(raw, self.raw["run_token"], self.inputs)
        with self.assertRaisesRegex(ValueError, "session token"):
            compare.decode_transport(self.raw, "different-session-token-0001", self.inputs)

    def test_boolean_wrong_type_and_nonfinite_raw_values_rejected(self):
        for mutation in ("sequence", "frame", "scale", "coordinate_bool", "coordinate_nan", "coordinate_inf", "rectangle_short", "id_number", "overflow", "window", "flag"):
            raw = copy.deepcopy(self.raw)
            if mutation in ("sequence", "frame"): raw["cases"][0]["events"][0][mutation] = False
            elif mutation == "scale": first(raw, "frame_start")["scale_factor"] = True
            elif mutation == "coordinate_bool": first(raw, "node")["bounds"][0] = True
            elif mutation == "coordinate_nan": first(raw, "node")["bounds"][0] = float("nan")
            elif mutation == "coordinate_inf": first(raw, "node")["bounds"][0] = float("inf")
            elif mutation == "rectangle_short": first(raw, "node")["bounds"].pop()
            elif mutation == "id_number": first(raw, "node")["id"] = 1
            elif mutation == "overflow": first(raw, "prepaint_end")["overflow"] = 0
            elif mutation == "window": first(raw, "frame_start")["window_size"][0] += 1
            elif mutation == "flag": first(raw, "node")["focusable"] = 0
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                compare.verify_candidate(raw, self.inputs)

    def test_strict_json_duplicate_keys_nonfinite_and_trailing_content(self):
        for text in ('{"x":1,"x":2}', '{"nested":{"x":1,"x":2}}', '[NaN]', '[Infinity]', '[-Infinity]', '{} {}', '{'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                compare.load_json(text)
        self.assertEqual(compare.load_json('{"x":[1,1.25,null,false]}'), {"x": [1, 1.25, None, False]})

    def test_input_expansion_and_boolean_margin_rejected(self):
        for mutation in ({"margin": 4}, {"margin": True}, {"margin": [8, 8, 8, 8]},
                         {"position_mode": "SwitchAnchor"}, {"anchor": "TopCenter"}, {"size": [40.25, 24]}):
            inputs = copy.deepcopy(self.inputs)
            inputs["cases"][0]["popup"].update(mutation)
            raw = copy.deepcopy(self.raw)
            raw["input"] = inputs
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                compare.verify_candidate(raw, inputs)

    def test_fixed_tolerance_is_predeclared_and_not_fitted(self):
        allowance = 2 ** -10
        self.assertEqual(compare.TOLERANCE, allowance)
        self.assertEqual(compare.GRID_TOLERANCE, allowance)
        change_node_bounds(self.raw, "popup", delta=allowance)
        result = compare.compare_observations(self.rust, self.raw, self.inputs)
        self.assertTrue(result["passed"])
        self.assertEqual(result["numeric_policy"]["maximum_observed_difference"], allowance)
        change_node_bounds(self.raw, "popup", delta=2 ** -20)
        with self.assertRaisesRegex(ValueError, "physical grid"):
            compare.compare_observations(self.rust, self.raw, self.inputs)
        compare.baseline.vector([0], [allowance], "fixed boundary", compare.TOLERANCE)
        with self.assertRaises(ValueError):
            compare.baseline.vector([0], [allowance + 2 ** -20], "fixed beyond", compare.TOLERANCE)

    def test_candidate_raw_numeric_domain_is_bounded(self):
        for bounds in ([4096.25, 0, 1, 1], [0, 0, 2048.25, 1], [4096, 0, 1, 1], [0, 0, -1, 1]):
            raw = copy.deepcopy(self.raw)
            first(raw, "node")["bounds"] = bounds
            with self.subTest(bounds=bounds), self.assertRaises(ValueError):
                compare.verify_candidate(raw, self.inputs)


class MarginPairSourceContracts(unittest.TestCase):
    def test_88_case_corpus_and_37_frozen_files_unchanged(self):
        inputs = helper.corpus()
        compare.baseline.validate_scenarios(inputs)
        self.assertEqual(len(inputs["cases"]), 88)
        groups = {}
        for case in inputs["cases"]:
            groups.setdefault(case["id"].split("-margin")[0], set()).add((case["popup"]["margin"], case["scale_factor"]))
        self.assertEqual(len(groups), 22)
        self.assertTrue(all(values == {(0, 1), (0, 1.25), (8, 1), (8, 1.25)} for values in groups.values()))
        profile = compare.load_json((PAIR / "profile.json").read_text())
        self.assertEqual(len(profile["approved_fixture_sha256"]), 37)
        for relative, expected in profile["approved_fixture_sha256"].items():
            self.assertEqual(compare.baseline.digest(ROOT / relative), expected, relative)
        self.assertEqual(profile["margin_cases"], 88)
        self.assertEqual(profile["original_regression"], dict(cases=24, compared_operations=53, paired_clicks=5))
        self.assertEqual(profile["fractional_regression"], dict(cases=2, compared_operations=8, paired_clicks=4))
        self.assertEqual(profile["numeric_policy"]["absolute_logical_allowance"], compare.TOLERANCE)

    def test_adapter_calls_real_core_apis_and_transmits_margin(self):
        source = (ROOT / "adapters/anchor_margin_moonbit/main.mbt").read_text()
        compact = "".join(source.split())
        for part in ('@element.Element::anchored_after(', 'margin=number(field(popup,"margin"))',
                     '.deferred()', '.request_layout_with_device_scale(', 'requested.prepaint()',
                     'frame.tree().nodes()', 'frame.paint().commands()', 'node.bounds()',
                     'node.accepts_pointer_events()', 'node.is_focusable()', 'frame.tree().hit_test(point)',
                     '@env.get_env_var("GPUI_SCENARIOS")', '@env.get_env_var("GPUI_RUN_TOKEN")'):
            self.assertIn(part, compact)
        for part in ('expected_origin', 'derive_placement', 'snap_offset', 'logical_offset',
                     '.round(', '.floor(', '.ceil(', '.clamp(', 'static_origin', 'simulate_click'):
            self.assertNotIn(part, source)
        self.assertNotRegex(source, r'\bfn\s+(?:snap|clamp|place|placement)\b')
        package = (ROOT / "adapters/anchor_margin_moonbit/moon.pkg").read_text()
        for name in ("element", "layout", "primitives", "scene"):
            self.assertIn('"f4ah6o/gpui/' + name + '"', package)

    def test_schema_is_closed_and_uses_approved_margin_corpus(self):
        schema = compare.load_json((PAIR / "raw.schema.json").read_text())
        compare.Draft202012Validator.check_schema(schema)
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["$defs"]["popup"]["properties"]["margin"], {"enum": [0, 8]})
        self.assertEqual(schema["$defs"]["popup"]["properties"]["position_mode"]["enum"], ["Local", "Window"])
        self.assertNotIn("logical_offset", json.dumps(schema))

    def test_pending_candidate_publication_pin_fails_before_evidence_or_git(self):
        identity = {"tree": "b" * 40}
        manifest = dict(schema_version=1, layer=compare.LAYER, qualification="exact-clean-source-pair",
                        review_or_publication_claim=False, core=identity, core_after=identity,
                        suite={}, suite_after={}, requested_core_commit="a" * 40)
        real_load = compare.load_json
        def pending_profile(text):
            value = real_load(text)
            if "candidate_pin_status" in value:
                value.update(candidate_commit="a" * 40, candidate_tree="b" * 40,
                             candidate_pin_status="pending-reviewed-published-core")
            return value
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "manifest.json").write_text(json.dumps(manifest))
            with patch.object(verifier, "load_json", side_effect=pending_profile), \
                    patch.object(verifier.subprocess, "check_output") as git:
                with self.assertRaisesRegex(ValueError, "publication pin still pending"):
                    verifier.verify(directory, ROOT, ROOT, ROOT, "c" * 40, "a" * 40)
                git.assert_not_called()
        profile = compare.load_json((PAIR / "profile.json").read_text())
        if profile["candidate_pin_status"] != "published-exact-commit-tree":
            self.assertIsNone(profile["candidate_commit"])
            self.assertIsNone(profile["candidate_tree"])

    def test_retained_source_inventory_covers_frozen_dependencies_and_new_tests(self):
        self.assertEqual(len(runner.SUITE_FILES), len(set(runner.SUITE_FILES)))
        profile = compare.load_json((PAIR / "profile.json").read_text())
        self.assertTrue(set(profile["approved_fixture_sha256"]) <= set(runner.SUITE_FILES))
        self.assertIn("tests/test_anchor_margin_pair.py", runner.SUITE_FILES)
        self.assertIn("diagnostics/anchor_margin_pair/regressions.py", runner.SUITE_FILES)
        self.assertIn("diagnostics/anchor_margin_pair/verify_mutants.py", runner.SUITE_FILES)
        for path in ("element/anchored.mbt", "layout/tree.mbt", "primitives/moon.pkg", "scene/scene.mbt"):
            self.assertTrue(runner.production_file(path), path)
        for path in ("element/anchored_wbtest.mbt", "element/anchored_test.mbt", "element/nested/file.mbt", "external/file.mbt"):
            self.assertFalse(runner.production_file(path), path)


class SyntheticMutationClassificationTests(unittest.TestCase):
    """Classifier inputs are synthetic, never executed production-mutant kills."""
    def setUp(self):
        self.descriptors = compare.load_json((PAIR / "mutations.json").read_text())
        self.good = dict(returncode=0, timed_out=False)

    def test_three_targeted_witnesses_classify_only_actual_semantic_mismatches(self):
        self.assertEqual([d["name"] for d in self.descriptors], ["wrong-margin", "always-inset", "swapped-opposite-edges"])
        for descriptor in self.descriptors:
            self.assertEqual(descriptor["path"], "element/anchored.mbt")
            self.assertEqual(descriptor["scope"], "rust-paired-margin-semantics")
            self.assertNotEqual(descriptor["old"], descriptor["new"])
            self.assertTrue(descriptor["required_witnesses"])
            witnesses = copy.deepcopy(descriptor["required_witnesses"])
            comparison = dict(passed=False, mismatches=witnesses)
            with self.subTest(mutation=descriptor["name"]):
                self.assertEqual(mutants.classify(self.good, self.good, comparison, descriptor=descriptor),
                                 "executed-paired-margin-rejection")
                self.assertEqual(mutants.classify(self.good, self.good, dict(passed=True), descriptor=descriptor), "survived")
                for field, value in (("case", "unrelated-case"), ("operation", "initial"), ("field", "bounds/anchor")):
                    unrelated = copy.deepcopy(comparison)
                    unrelated["mismatches"][0][field] = value
                    self.assertEqual(mutants.classify(self.good, self.good, unrelated, descriptor=descriptor),
                                     "executed-unrelated-rejection-not-margin-kill")
                self.assertEqual(mutants.classify(self.good, self.good, comparison),
                                 "executed-unrelated-rejection-not-margin-kill")

    def test_compile_crash_timeout_transport_and_validation_failures_never_kill(self):
        descriptor = self.descriptors[0]
        comparison = dict(passed=False, mismatches=copy.deepcopy(descriptor["required_witnesses"]))
        controls = [
            (dict(returncode=1, timed_out=False), self.good, {}, "compile-rejection-not-executed"),
            (dict(returncode=0, timed_out=True), self.good, {}, "compile-rejection-not-executed"),
            (self.good, None, {}, "execution-missing-not-semantic-kill"),
            (self.good, dict(returncode=1, timed_out=False), {}, "executed-runtime-rejection-not-semantic-kill"),
            (self.good, dict(returncode=0, timed_out=True), {}, "executed-timeout-not-semantic-kill"),
            (self.good, self.good, dict(transport_error="bad JSON/session"), "executed-transport-rejection-not-semantic-kill"),
            (self.good, self.good, dict(validation_error="scene/lifecycle invalid"), "executed-observation-validation-rejection-not-margin-kill"),
        ]
        for build, execution, kwargs, expected in controls:
            with self.subTest(outcome=expected):
                outcome = mutants.classify(build, execution, comparison, descriptor=descriptor, **kwargs)
                self.assertEqual(outcome, expected)
                self.assertNotEqual(outcome, "executed-paired-margin-rejection")
        self.assertEqual(mutants.classify(self.good, self.good, descriptor=descriptor), "comparison-missing-not-semantic-kill")

    def test_every_predefined_witness_and_exact_control_coverage_required(self):
        descriptor = copy.deepcopy(self.descriptors[0])
        descriptor["required_witnesses"].append(dict(case="another-case", operation="configured", field="bounds/popup"))
        comparison = dict(passed=False, mismatches=copy.deepcopy(descriptor["required_witnesses"][:1]))
        self.assertEqual(mutants.classify(self.good, self.good, comparison, descriptor=descriptor),
                         "executed-unrelated-rejection-not-margin-kill")
        comparison["mismatches"] = copy.deepcopy(descriptor["required_witnesses"])
        self.assertEqual(mutants.classify(self.good, self.good, comparison, descriptor=descriptor),
                         "executed-paired-margin-rejection")
        good = [dict(mutation=d["name"], outcome="executed-paired-margin-rejection") for d in self.descriptors]
        compare.validate_mutation_outcomes(good)
        for altered in (good[:-1], good + [good[0]], list(reversed(good)),
                        [dict(item, outcome="executed-observation-validation-rejection-not-margin-kill") for item in good]):
            with self.subTest(altered=altered), self.assertRaises(ValueError):
                compare.validate_mutation_outcomes(altered)


class SyntheticNativeLineageTests(unittest.TestCase):
    """Non-executable text fixtures exercise the retained direct-native lineage."""
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.stage = Path(self.temporary.name) / "source"
        self.stage.mkdir()
        (self.stage / "moon.mod").write_text(runner.MODULE)
        self.dependencies = {"primitives": [], "scene": ["primitives"], "layout": ["primitives"],
            "element": ["layout", "primitives", "scene"], "probe": ["element", "env", "json", "layout", "primitives", "scene"]}
        self.filenames = {package: ("main" if package == "probe" else "anchored" if package == "element" else package) + ".mbt"
                          for package in self.dependencies}
        for package, dependencies in self.dependencies.items():
            directory = self.stage / package
            directory.mkdir()
            (directory / self.filenames[package]).write_text("// synthetic checker fixture only; not compiled")
            imports = ['"' + ("moonbitlang/core/" if name in ("env", "json") else "f4ah6o/gpui/") + name + '",' for name in dependencies]
            (directory / "moon.pkg").write_text(("import { " + " ".join(imports) + " }" if imports else "")
                + ('\noptions("is-main": true)' if package == "probe" else ""))

    def tools(self):
        return dict(moonc=dict(path="/tools/moonc"), cc=dict(path="/usr/bin/cc"), ar=dict(path="/usr/bin/ar"))

    def plan(self):
        prefix = "./_build/native/debug/build/"
        std = "$MOON_HOME/lib/core/_build/native/release/bundle/"
        order = ("primitives", "layout", "scene", "element", "probe")
        commands = []
        for package in order:
            imports = []
            for name in sorted(self.dependencies[package] + ["prelude"]):
                path = std + name + "/" + name + ".mi" if name in ("prelude", "env", "json") else prefix + name + "/" + name + ".mi"
                imports += ["-i", path + ":" + name]
            commands.append(["moonc", "build-package", "./" + package + "/" + self.filenames[package], "-w", "@a", "-o",
                prefix + package + "/" + package + ".core", "-pkg", "f4ah6o/gpui/" + package,
                "-pkg-type", "executable" if package == "probe" else "library", "-std-path", std[:-1]] + imports +
                ["-pkg-sources", "f4ah6o/gpui/" + package + ":./" + package, "-target", "native", "-g", "-O0",
                 "-workspace-path", ".", "-all-pkgs", prefix + "all_pkgs.json"])
        link = ["moonc", "link-core", std + "abort/abort.core", std + "core.core"]
        link += [prefix + package + "/" + package + ".core" for package in order]
        link += ["-main", "f4ah6o/gpui/probe", "-o", prefix + "probe/__moonbit_link_core__/probe.o", "-pkg-config-path", "./probe/moon.pkg"]
        for package in order:
            link += ["-pkg-sources", "f4ah6o/gpui/" + package + ":./" + package]
        commands.append(link + ["-pkg-sources", "moonbitlang/core:$MOON_HOME/lib/core", "-target", "x86_64-unknown-linux-gnu", "-g", "-O0"])
        runtime = ("utf", "sync_io", "runtime", "env", "backtrace")
        archive = prefix + "libruntime-04d24968c494e3bb.a"
        for name in runtime:
            commands.append(["/usr/bin/cc", "-o", prefix + "runtime-" + name + ".o", "-I$MOON_HOME/include", "-g", "-c", "-fwrapv",
                "-fno-strict-aliasing", "-O2", "-DMOONBIT_ALLOW_STACKTRACE", "-DMOONBIT_ALLOCATOR=MOONBIT_ALLOCATOR_MIMALLOC",
                "$MOON_HOME/lib/runtime/" + name + ".c"])
        commands.append(["/usr/bin/ar", "-r", "-c", "-s", archive] + [prefix + "runtime-" + name + ".o" for name in sorted(runtime)])
        commands.append(["/usr/bin/cc", "-o", prefix + "probe/probe.exe", "$MOON_HOME/lib/libmoonbitrun.o",
                         prefix + "probe/__moonbit_link_core__/probe.o", archive, "-lm", "$MOON_HOME/lib/libbacktrace.a"])
        return "\n".join(shlex.join(command) for command in commands)

    def test_exact_native_plan_and_unknown_lineage_rejected(self):
        plan = runner.native_build_plan(self.plan(), self.tools(), self.stage)
        self.assertEqual(plan["backend"], "direct-native-object")
        self.assertIn("probe/__moonbit_link_core__/probe.o", plan["required_generated"])
        for old, new in (("./element/anchored.mbt", "/tmp/unretained.mbt"),
                         ("probe/__moonbit_link_core__/probe.o", "probe/probe.c"),
                         ("x86_64-unknown-linux-gnu", "native"), ("/usr/bin/cc", "/wrong/cc"),
                         ("-target native -g -O0", "-target native -g -O0 -O2"),
                         (" -lm ", " -lm -lunknown "), ("runtime/runtime.c", "runtime/utf.c")):
            with self.subTest(old=old), self.assertRaises(ValueError):
                runner.native_build_plan(self.plan().replace(old, new), self.tools(), self.stage)

    def test_native_environment_is_bound(self):
        env = dict(CC="/usr/bin/cc", MOON_CC=None, MOON_HOME="/tools", MOONBIT_NEW_NATIVE=None)
        runner.require_native_environment(env, self.tools())
        for change in (dict(CC="/wrong/cc"), dict(MOON_CC="/wrong/cc"), dict(MOON_HOME="relative"), dict(MOONBIT_NEW_NATIVE="0")):
            with self.subTest(change=change), self.assertRaises(ValueError):
                runner.require_native_environment(dict(env, **change), self.tools())

    def test_generated_inventory_retains_objects_and_detects_missing_or_changed_bytes(self):
        plan = runner.native_build_plan(self.plan(), self.tools(), self.stage)
        source = Path(self.temporary.name) / "build"
        source.mkdir()
        with self.assertRaises(ValueError):
            runner.native_generated_inventory(source, plan)
        for name in plan["required_generated"]:
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("synthetic non-executable checker fixture: " + name)
        retained = runner.native_generated_inventory(source, plan)
        path = source / "probe/__moonbit_link_core__/probe.o"
        path.write_text("changed synthetic bytes")
        self.assertNotEqual(runner.native_generated_inventory(source, plan), retained)
        path.unlink()
        with self.assertRaises(ValueError):
            runner.native_generated_inventory(source, plan)

    def test_staged_sources_and_package_imports_cannot_escape_inventory(self):
        source = self.stage / "element/anchored.mbt"
        source.rename(source.with_name("replacement.mbt"))
        with self.assertRaises(ValueError):
            runner.native_build_plan(self.plan(), self.tools(), self.stage)
        source.with_name("replacement.mbt").rename(source)
        package = self.stage / "element/moon.pkg"
        original = package.read_text()
        for extra in ('import { "external/unknown", }', 'options("compile-flags": ["-O2"])', 'import {} for "unknown"'):
            package.write_text(original + "\n" + extra)
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                runner.native_build_plan(self.plan(), self.tools(), self.stage)
        package.write_text(original)




class FrozenObserverCompatibilityTests(unittest.TestCase):
    """Deterministic compatibility boundary; no native execution claim."""
    def setUp(self):
        self.regressions = load_module('anchor_margin_compatibility_tests', PAIR / 'regressions.py')
        self.descriptor = json.loads((PAIR / 'observer_compatibility.json').read_text())
        self.source = (ROOT / 'adapters/anchor_moonbit/main.mbt').read_bytes()

    def test_exact_one_site_derivation_and_explicit_paint_abort(self):
        derived = self.regressions.derive_observer(self.source, self.descriptor)
        self.assertEqual(derived, self.source.replace(self.descriptor['old'].encode(), self.descriptor['new'].encode()))
        self.assertEqual(derived.count(b'@scene.Paint => abort("unexpected non-quad paint")'), 1)
        self.assertEqual(self.source.count(b'@scene.Paint'), 0)
        self.assertNotIn(b'--warn-list', (PAIR / 'regressions.py').read_bytes())
        self.assertIn(b"'--deny-warn'", (PAIR / 'regressions.py').read_bytes())

    def test_source_drift_and_wrong_expected_hash_fail_closed(self):
        for value in (self.source + b'\n', self.source.replace(b'@scene.Quad', b'@scene.Paint')):
            with self.assertRaisesRegex(ValueError, 'source drift'):
                self.regressions.derive_observer(value, self.descriptor)
        descriptor = dict(self.descriptor, derived_source_sha256='0' * 64)
        with self.assertRaisesRegex(ValueError, 'derived observer source hash'):
            self.regressions.derive_observer(self.source, descriptor)

    def test_unexpected_match_count_or_nonaborting_paint_arm_rejects(self):
        for changed in ({'exact_occurrences': 2}, {'old': 'different'},
                        {'new': '@scene.ClipPop => "clip_pop"; @scene.Paint => "quad" }'}):
            with self.assertRaises(ValueError):
                self.regressions.derive_observer(self.source, dict(self.descriptor, **changed))
        import hashlib
        duplicate = self.source + self.descriptor['old'].encode()
        descriptor = dict(self.descriptor, frozen_source_sha256=hashlib.sha256(duplicate).hexdigest())
        with self.assertRaisesRegex(ValueError, 'exact one-site match'):
            self.regressions.derive_observer(duplicate, descriptor)

    def test_actual_original_compile_rejection_must_name_paint(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            record = {'compatibility_original_build': {'returncode': 255, 'timed_out': False}}
            path = directory / 'frozen-original-build.stderr'
            path.write_text('Error: [0011] partial_match Paint')
            self.regressions._require_original_compile_rejection(directory, record)
            for text in ('compile failed', '[0011] partial_match Other', '[0011] Paint'):
                path.write_text(text)
                with self.assertRaises(ValueError): self.regressions._require_original_compile_rejection(directory, record)
            path.write_text('Error: [0011] partial_match Paint')
            for process in ({'returncode': 0, 'timed_out': False}, {'returncode': 255, 'timed_out': True}):
                with self.assertRaises(ValueError):
                    self.regressions._require_original_compile_rejection(directory, {'compatibility_original_build': process})


if __name__ == "__main__":
    unittest.main()
