"""Source/packaging and explicitly synthetic checker controls, never Rust execution evidence."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("anchor_margin_verify", ROOT / "diagnostics/anchor_margin/verify.py")
v = importlib.util.module_from_spec(spec); spec.loader.exec_module(v)


def corpus(): return v.load_json(ROOT / "diagnostics/anchor_margin/scenarios.json")


def synthetic_trace(inputs=None):
    """Synthetic arbitrary static origin80, not a GPUI observation or static-layout hypothesis."""
    inputs = copy.deepcopy(inputs if inputs is not None else corpus())
    observations = []
    for case in inputs["cases"]:
        events, frame = [], 0
        def emit(event, operation):
            events.append({"sequence": len(events), "operation": operation, "frame": frame, "event": event})
        for operation, scale, value in (("initial", 2, {"action": "open_window"}),
                ("configured", case["scale_factor"], {"action": "set_scale_factor", "scale_factor": case["scale_factor"]})):
            emit({"type": "operation_start", "input": value}, operation); frame += 1
            static = [16, 80, *case["popup"]["size"]]
            derivation = v.derive_placement(case, static, case["popup"]["size"], scale)
            geometry = {"$host": [0, 0, *case["window"]], "parent": [*case["parent_origin"], *case["parent_size"]],
                "button": [*case["parent_origin"], 120, v.snap_offset(65, scale)], "anchor": static, "deferred": static,
                "popup": [*derivation["expected_origin"], *case["popup"]["size"]]}
            emit({"type": "frame_start", "scale_factor": scale, "window_size": case["window"], "client_inset": None}, operation)
            def begin(phase, node):
                event = {"type": phase, "node": node}
                if phase in ("prepaint", "paint"): event["bounds"] = geometry[node].copy()
                if phase == "prepaint":
                    event.update(content_mask=[0, 0, *case["window"]], element_offset=derivation["logical_offset"].copy() if node == "popup" else [0, 0])
                emit(event, operation)
            def end(phase, node): emit({"type": phase + "_end", "node": node}, operation)
            for phase in ("request_layout", "prepaint", "paint"):
                begin(phase, "$host"); begin(phase, "parent"); begin(phase, "button"); end(phase, "button"); begin(phase, "deferred")
                if phase == "request_layout":
                    begin(phase, "anchor"); begin(phase, "popup"); end(phase, "popup"); end(phase, "anchor")
                end(phase, "deferred"); end(phase, "parent"); end(phase, "$host")
                if phase != "request_layout":
                    begin(phase, "anchor"); begin(phase, "popup"); end(phase, "popup"); end(phase, "anchor")
            emit({"type": "operation_end", "scale_factor": scale}, operation)
        observations.append({"id": case["id"], "events": events})
    return {"schema_version": 1, "layer": v.LAYER, "fixture": "font-free-bounded-anchor-margin", "text_system": "NoopTextSystem; no text used",
        "upstream_revision": v.UPSTREAM, "run_token": "synthetic-checker-only-0001", "input": inputs, "cases": observations}, inputs


def single(case_id="cross-right-margin8-scale1"):
    inputs = corpus(); inputs["cases"] = [next(c for c in inputs["cases"] if c["id"] == case_id)]
    return synthetic_trace(inputs)


def synthetic_bundle(directory):
    raw, inputs = synthetic_trace()
    profile = v.load_json(ROOT / "diagnostics/anchor_margin/profile.json")
    files = {"raw.json": json.dumps(raw).encode(), "raw.stderr": b"", "scenarios.json": (ROOT / "diagnostics/anchor_margin/scenarios.json").read_bytes(),
        "probe": b"\x7fELFsynthetic-checker-only", "toolchain.txt": b"rustc 1.98.1 synthetic only\n", "build.stdout": b"", "build.stderr": b""}
    files.update({v.retained_path(p): (ROOT / p).read_bytes() for p in v.RETAIN + list(profile["frozen_original"]["sha256"])})
    files.update({"upstream/" + p: b"synthetic upstream source only" for p in v.UPSTREAM_RETAIN})
    files["build-Cargo.toml"] = files[v.retained_path("adapters/anchor_margin_rust/Cargo.toml")].replace(b'"../../../zed-source/crates/gpui"', b'"/synthetic-upstream/crates/gpui"')
    files["build-Cargo.lock"] = files[v.retained_path("adapters/anchor_margin_rust/Cargo.lock")]
    build = ["cargo", "+1.98.1", "build", "--locked", "--manifest-path", str(directory.parent / ("anchor-margin-build-" + raw["run_token"]) / "adapter/Cargo.toml")]
    execute = [str(directory / "probe"), str(directory / "scenarios.json"), raw["run_token"]]
    environment = {"CARGO_BUILD_JOBS": "2", "CARGO_INCREMENTAL": "0", "DISPLAY": None, "WAYLAND_DISPLAY": None}
    sha = lambda name: v.hashlib.sha256(files[name]).hexdigest()
    plan = {"schema_version": 1, "layer": v.LAYER, "run_token": raw["run_token"], "build_command": build, "execution_command": execute,
        "environment": environment, "input_sha256": sha("scenarios.json"), "lock_sha256": sha(v.retained_path("adapters/anchor_margin_rust/Cargo.lock")),
        "build_manifest_sha256": sha("build-Cargo.toml"), "toolchain_sha256": sha("toolchain.txt")}
    files["build-plan.json"] = json.dumps(plan).encode()
    for name, content in files.items():
        path = directory / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(content)
    identity = {"commit": "a" * 40, "tree": "b" * 40, "clean": True}
    upstream = {"commit": v.UPSTREAM, "tree": v.UPSTREAM_TREE, "clean": True}
    manifest = {"schema_version": 1, "layer": v.LAYER, "suite": identity, "suite_after": identity.copy(), "upstream": upstream,
        "upstream_after": upstream.copy(), "upstream_source_path": "/synthetic-upstream", "run_token": raw["run_token"], "environment": environment,
        "build": {"command": build, "returncode": 0, "timed_out": False}, "execution": {"command": execute, "returncode": 0, "timed_out": False},
        "files": {name: {"sha256": v.digest(directory / name), "size": len(content)} for name, content in files.items()}}
    (directory / "manifest.json").write_text(json.dumps(manifest))
    return raw, files, manifest


class AnchorMarginContracts(unittest.TestCase):
    def test_authored_full_cross_product_and_frozen_originals(self):
        inputs = corpus(); v.validate_scenarios(inputs)
        self.assertEqual(len(inputs["cases"]), 88)
        groups = {}
        for case in inputs["cases"]:
            family = case["id"].split("-margin")[0]
            groups.setdefault(family, set()).add((case["popup"]["margin"], case["scale_factor"]))
        self.assertEqual(len(groups), 22)
        self.assertTrue(all(group == {(0, 1), (0, 1.25), (8, 1), (8, 1.25)} for group in groups.values()))
        profile = v.load_json(ROOT / "diagnostics/anchor_margin/profile.json")
        self.assertEqual(profile["input_sha256"], v.digest(ROOT / "diagnostics/anchor_margin/scenarios.json"))
        for relative, sha in profile["frozen_original"]["sha256"].items(): self.assertEqual(v.digest(ROOT / relative), sha, relative)
        self.assertEqual(len(v.load_json(ROOT / "diagnostics/anchor/scenarios.json")["cases"]), 24)
        self.assertEqual(profile["frozen_original"]["fractional_extension_case_count"], 2)

    def test_source_hypothesis_has_explicit_independent_examples(self):
        inputs = {c["id"]: c for c in corpus()["cases"]}
        examples = {
            "cross-right-margin8-scale1": ([112, 48], ["right"]),
            "cross-left-margin8-scale1": ([8, 48], ["left"]),
            "cross-bottom-margin8-scale1": ([64, 88], ["bottom"]),
            "cross-top-margin8-scale1": ([64, 8], ["top"]),
            "inside-right-margin8-scale1": ([119.5, 48], []),
            "exact-right-margin8-scale1": ([120, 48], []),
            "oversized-both-margin8-scale1": ([8, 8], ["right", "left", "bottom", "top"]),
            "margin-induced-opposite-crossing-margin8-scale1": ([8, 8], ["right", "left", "bottom", "top"]),
            "margin-induced-opposite-crossing-margin0-scale1": ([4, 4], ["right", "bottom"]),
        }
        for name, (origin, branches) in examples.items():
            c = inputs[name]; d = v.derive_placement(c, [16, 80], c["popup"]["size"], 1)
            self.assertEqual(d["desired_after_snap"], origin, name); self.assertEqual(d["source_predicate_branches"], branches, name)
        for sign, value, snapped in (("positive", 1, .8), ("negative", -1, -.8)):
            c = inputs[f"half-local-{sign}-margin8-scale1.25"]
            d = v.derive_placement(c, [16, 80], c["popup"]["size"], 1.25)
            self.assertEqual(d["logical_offset"], [value, value]); self.assertEqual(d["device_snapped_offset"], [snapped, snapped])

    def test_every_synthetic_case_checks_without_claiming_execution(self):
        raw, inputs = synthetic_trace(); result = v.verify_observations(raw, inputs)
        self.assertEqual(result["case_count"], 88); self.assertEqual(result["observed_frame_count"], 176)
        self.assertIn("no unchanged-example", result["claim"])

    def test_coherent_wrong_margin_always_inset_swapped_edge_and_rounding_controls(self):
        # These deliberately edited traces are checker sensitivity controls, never executed mutants.
        controls = [("cross-right-margin8-scale1", [120, 48], "wrong-zero-margin"),
            ("inside-left-margin8-scale1", [8, 48], "always-inset"),
            ("exact-right-margin8-scale1", [112, 48], "inclusive-edge-predicate"),
            ("oversized-both-margin8-scale1", [-48, -48], "swapped-edge-order"),
            ("half-local-positive-margin8-scale1.25", [16, 80], "lost-logical-rounding")]
        for case_id, origin, label in controls:
            raw, inputs = single(case_id)
            for entry in raw["cases"][0]["events"]:
                event = entry["event"]
                if event.get("node") == "popup" and "bounds" in event:
                    event["bounds"][:2] = origin
                    if "element_offset" in event: event["element_offset"] = [origin[0] - 16, origin[1] - 80]
            with self.subTest(control=label), self.assertRaises(ValueError): v.verify_observations(raw, inputs)

    def test_raw_logical_offset_is_observed_separately(self):
        raw, inputs = single("half-local-positive-margin8-scale1.25")
        for entry in raw["cases"][0]["events"]:
            event = entry["event"]
            if event.get("node") == "popup" and event["type"] == "prepaint": event["element_offset"] = [0, 0]
        with self.assertRaisesRegex(ValueError, "observed logical"): v.verify_observations(raw, inputs)

    def test_missing_extra_stale_lifecycle_and_identity(self):
        for mutation in ("missing", "extra", "sequence", "frame", "operation", "pin", "input", "scale", "inset", "viewport", "bool"):
            raw, inputs = single(); events = raw["cases"][0]["events"]
            if mutation == "missing": events.pop(4)
            if mutation == "extra": events.append(copy.deepcopy(events[-1]))
            if mutation == "sequence": events[4]["sequence"] = 99
            if mutation == "frame": events[4]["frame"] = 3
            if mutation == "operation": events[4]["operation"] = "configured"
            if mutation == "pin": raw["upstream_revision"] = "f" * 40
            if mutation == "input": raw["input"] = {}
            if mutation == "bool": events[1]["frame"] = True
            if mutation in ("scale", "inset", "viewport"):
                event = events[1]["event"]
                if mutation == "scale": event["scale_factor"] = 1
                if mutation == "inset": event["client_inset"] = 0
                if mutation == "viewport": event["window_size"][0] += 1
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): v.verify_observations(raw, inputs)

    def test_extra_real_frames_are_preserved_and_checked(self):
        raw, inputs = single(); events = raw["cases"][0]["events"]
        start = next(i for i,e in enumerate(events) if e["operation"] == "configured")
        extra = copy.deepcopy(events[start + 1:-1])
        for entry in extra + events[-1:]: entry["frame"] = 3
        events[-1:-1] = extra
        for index, entry in enumerate(events): entry["sequence"] = index
        result = v.verify_observations(raw, inputs)
        self.assertEqual(result["observed_frame_count"], 3)
        self.assertEqual(len(result["cases"][0]["operations"][1]["frames"]), 2)

    def test_input_expansion_and_nonfinite_values_rejected(self):
        changes = [lambda c:c["popup"].update(margin=4), lambda c:c["popup"].update(margin=[8]*4),
            lambda c:c["popup"].update(position_mode="SwitchAnchor"), lambda c:c["popup"].update(anchor="TopCenter"),
            lambda c:c["popup"].update(size=[40.25,24]), lambda c:c["popup"].update(position=[float("nan"),0]),
            lambda c:c.update(scale_factor=2), lambda c:c.update(hits=[]), lambda c:c["popup"].update(margin=True)]
        for mutate in changes:
            inputs = corpus(); mutate(inputs["cases"][0])
            with self.assertRaises(ValueError): v.validate_scenarios(inputs)

    def test_numerical_allowances_and_raw_domain_are_bounded(self):
        allowance = v.GEOMETRY_F32_ALLOWANCE
        v.close(0, allowance, "boundary")
        with self.assertRaises(ValueError): v.close(0, allowance + 2 ** -20, "beyond")
        for scale in (1, 1.25, 2):
            v.physical_grid([16 + (allowance - 2 ** -20) / scale, 80, 40, 24], scale)
            with self.assertRaisesRegex(ValueError, "physical grid"):
                v.physical_grid([16 + (allowance + 2 ** -20) / scale, 80, 40, 24], scale)
        for rectangle in ([4096.25, 0, 1, 1], [0, 0, 2048.25, 1], [4096, 0, 1, 1]):
            with self.assertRaisesRegex(ValueError, "numerically unqualified"): v.qualify_bounds(rectangle)

    def test_source_delegation_and_renamed_lock_only(self):
        source = (ROOT / "adapters/anchor_margin_rust/src/main.rs").read_text(); compact = "".join(source.split())
        for part in ("self.inner.request_layout(", "self.inner.prepaint(", "self.inner.paint(", "window.element_offset()", "window.client_inset()", ".snap_to_window_with_margin(px(popup.margin))", "TestAppContext::single()"):
            self.assertIn(part, compact)
        for part in ("expected_origin", "round(", "ceil(", "floor(", "layout_bounds(", "insert_hitbox(", "simulate_click", "set_client_inset"):
            self.assertNotIn(part, source)
        for name in ("Cargo.toml", "Cargo.lock"):
            self.assertEqual((ROOT / "adapters/anchor_margin_rust" / name).read_text(),
                (ROOT / "adapters/anchor_rust" / name).read_text().replace("gpui-anchor-diagnostic", "gpui-anchor-margin-diagnostic"))

    def test_schema_workflow_and_failure_retention(self):
        schema = v.load_json(ROOT / "diagnostics/anchor_margin/raw.schema.json"); v.Draft202012Validator.check_schema(schema)
        self.assertEqual(schema["$defs"]["popup"]["properties"]["margin"], {"enum":[0,8]})
        workflow = (ROOT / ".github/workflows/anchor-margin-diagnostic.yml").read_text()
        for part in (v.UPSTREAM, "if: always()", "--suite-tree", "jsonschema==4.26.0"): self.assertIn(part, workflow)
        runner = (ROOT / "diagnostics/anchor_margin/run.py").read_text()
        for part in ("8 * 1024**3", "verification-failure.json", "build-plan.json", "manifest.json"): self.assertIn(part, runner)
        self.assertNotIn("rmtree", runner)

    def test_bundle_exact_inventory_and_provenance_controls(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "_build/margin-evidence"
            raw, files, manifest = synthetic_bundle(directory)
            self.assertFalse(v.verify_bundle(directory)["source_bound"])
            for mutate in (lambda m:m.update(run_token="wrong-token-0000001"), lambda m:m["files"].pop("probe"),
                    lambda m:m["files"].update(extra={"size":0,"sha256":"f"*64}), lambda m:m["build"].update(timed_out=True),
                    lambda m:m["suite"].update(clean=False), lambda m:m["upstream"].update(commit="f"*40),
                    lambda m:m["execution"]["command"].__setitem__(1,"/wrong/input")):
                changed=copy.deepcopy(manifest); mutate(changed); (directory / "manifest.json").write_text(json.dumps(changed))
                with self.assertRaises(ValueError): v.verify_bundle(directory)
            (directory / "manifest.json").write_text(json.dumps(manifest))
            (directory / "extra").write_text("extra")
            with self.assertRaisesRegex(ValueError,"extra evidence"): v.verify_bundle(directory)
            (directory / "extra").unlink()
            (directory / "raw.stderr").write_text("changed")
            with self.assertRaisesRegex(ValueError,"changed evidence"): v.verify_bundle(directory)

    def test_copied_bundle_reopens_files_and_keeps_recorded_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            original=Path(temp)/"_build/margin-evidence"; synthetic_bundle(original)
            copy_path=Path(temp)/"downloaded"; original.rename(copy_path)
            with self.assertRaises(ValueError): v.verify_bundle(copy_path)
            self.assertFalse(v.verify_bundle(copy_path,recorded_execution_root=original)["source_bound"])
            (copy_path/"raw.json").write_text("{}")
            with self.assertRaisesRegex(ValueError,"changed evidence"): v.verify_bundle(copy_path,recorded_execution_root=original)

    def test_rehashed_observer_source_requires_exact_committed_blobs(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp)/"_build/margin-evidence"; _, files, manifest=synthetic_bundle(directory)
            def git(arguments,cwd=None,text=False):
                if arguments[1]=="rev-parse": return "b"*40+"\n"
                return files[v.retained_path(arguments[2].split(":",1)[1])]
            with patch.object(v.subprocess,"check_output",side_effect=git):
                v.verify_bundle(directory,"a"*40,"b"*40,suite_source=ROOT)
                relative=v.retained_path("adapters/anchor_margin_rust/src/main.rs")
                path=directory/relative; path.write_text("changed observer")
                manifest["files"][relative]={"sha256":v.digest(path),"size":path.stat().st_size}
                (directory/"manifest.json").write_text(json.dumps(manifest))
                with self.assertRaisesRegex(ValueError,"exact committed source"): v.verify_bundle(directory,"a"*40,"b"*40,suite_source=ROOT)

    def test_duplicate_json_nonfinite_symlink_hardlink_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp); p=directory/"x"
            for value in ('{"x":1,"x":2}', '{"x":NaN}'):
                p.write_text(value)
                with self.assertRaises(ValueError): v.load_json(p)
            p.write_text("ok"); (directory/"link").symlink_to(p)
            with self.assertRaises(ValueError): v.strict_file(directory,"link")
            os.link(p,directory/"hard")
            with self.assertRaises(ValueError): v.strict_file(directory,"x")
            for name in ("/x","../x","a/../x","./x"):
                with self.assertRaises(ValueError): v.strict_file(directory,name)


if __name__ == "__main__": unittest.main()
