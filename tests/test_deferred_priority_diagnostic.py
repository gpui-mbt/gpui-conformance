"""Lightweight source and synthetic corruption controls. These are not Rust execution evidence."""
import copy
import importlib.util
import json
import shutil
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("deferred_priority_verify", ROOT / "diagnostics/deferred_priority/verify.py")
v = importlib.util.module_from_spec(spec); spec.loader.exec_module(v)


def corpus(): return v.load_json(ROOT / "diagnostics/deferred_priority/scenarios.json")


# Authored independent examples, not calls to the verifier's priority derivation.
ORDERS = {
    "ascending": ["abc", "bac", "bc", "abc"],
    "descending": ["cba", "acb", "cb", "cba"],
    "equal-one": ["abc", "bca", "bc", "abc"],
    "equal-one-reverse": ["cba", "bac", "ba", "cba"],
    "equal-zero": ["abc", "bca", "bc", "abc"],
    "transparent-top": ["abc", "bac", "bc", "abc"],
    "occluding-top": ["abc", "bac", "bc", "abc"],
    "stopping-top": ["abc", "bac", "bc", "abc"],
}


def synthetic_trace(inputs=None):
    """Hand-authored fixed fixture transcripts, explicitly not observed GPUI traces."""
    inputs = copy.deepcopy(corpus() if inputs is None else inputs)
    observations = []
    for case in inputs["cases"]:
        events, frame = [], 0
        def emit(event, operation):
            events.append({"sequence": len(events), "operation": operation, "frame": frame, "event": event})
        family = case["id"].split("-scale")[0]
        stages = ["base", "updated", "removed", "restored"]
        operations = [("initial", {"action": "open_window"}, "base", 2, False)]
        for stage in stages:
            action = {"base": {"action": "set_scale_factor", "scale_factor": case["scale_factor"]},
                "updated": {"action": "set_priority", "layer": case["update_layer"], "priority": case["update_priority"]},
                "removed": {"action": "remove_layer", "layer": case["update_layer"]},
                "restored": {"action": "restore_original_layers"}}[stage]
            operations.append((stage, action, stage, case["scale_factor"], False))
            operations.append((stage + ".input", {"action": "left_click", "position": case["probe_position"]}, stage, case["scale_factor"], True))
        for operation, action, stage, scale, is_input in operations:
            emit({"type": "operation_start", "input": action}, operation)
            order = ORDERS[family][stages.index(stage)]
            if not is_input:
                frame += 1
                emit({"type": "frame_start", "scale_factor": scale, "window_size": case["window"], "client_inset": None}, operation)
                structural = [layer["id"] for layer in case["layers"] if stage != "removed" or layer["id"] != case["update_layer"]]
                def begin(phase, node):
                    event = {"type": phase, "node": node}
                    if phase in ("prepaint", "paint"):
                        suffix = node.split(".")[-1]
                        bounds = {"$host": [0, 0, 320, 240], "before": [48, 48, 128, 96], "after": [48, 48, 128, 96],
                            "deferred": [0, 0, 128, 96], "anchor": [0, 0, 128, 96], "root": [48, 48, 128, 96],
                            "first": [48, 48, 80, 64], "second": [72, 64, 80, 64]}[suffix]
                        event.update(bounds=bounds, content_mask=[0, 0, 320, 240])
                        if phase == "prepaint": event["element_offset"] = [48, 48] if suffix in ("root", "first", "second") else [0, 0]
                    emit(event, operation)
                def end(phase, node): emit({"type": phase + "_end", "node": node}, operation)
                def subtree(phase, id):
                    begin(phase, id + ".anchor"); begin(phase, id + ".root")
                    for suffix in ("first", "second"): begin(phase, id + "." + suffix); end(phase, id + "." + suffix)
                    end(phase, id + ".root"); end(phase, id + ".anchor")
                for phase in ("request_layout", "prepaint", "paint"):
                    begin(phase, "$host"); begin(phase, "ordinary.before"); end(phase, "ordinary.before")
                    for id in structural:
                        begin(phase, id + ".deferred")
                        if phase == "request_layout": subtree(phase, id)
                        end(phase, id + ".deferred")
                    begin(phase, "ordinary.after"); end(phase, "ordinary.after"); end(phase, "$host")
                    if phase != "request_layout":
                        for id in order: subtree(phase, id)
            else:
                if family in ("occluding-top", "stopping-top"):
                    callbacks = ["c.second"]
                else:
                    callbacks = [id + "." + suffix for id in reversed(order) if family != "transparent-top" or id != "c" for suffix in ("second", "first", "root")]
                    callbacks += ["ordinary.after", "ordinary.before"]
                for node in callbacks:
                    config = case["ordinary_interaction"] if node.startswith("ordinary.") else next(layer["interaction"] for layer in case["layers"] if layer["id"] == node[0])
                    emit({"type": "mouse_down", "node": node, "position": case["probe_position"], "button": "Left", "phase": "Bubble", **config}, operation)
            emit({"type": "operation_end", "scale_factor": scale}, operation)
        observations.append({"id": case["id"], "events": events})
    return {"schema_version": 1, "layer": v.LAYER, "fixture": "font-free-bounded-flat-deferred-priority", "text_system": "NoopTextSystem; no text used",
        "upstream_revision": v.UPSTREAM, "run_token": "synthetic-checker-only-0001", "input": inputs, "cases": observations}, inputs


def single(family="ascending"):
    inputs = corpus(); inputs["cases"] = [next(case for case in inputs["cases"] if case["id"] == family + "-scale1")]
    return synthetic_trace(inputs)


def synthetic_bundle(directory):
    raw, inputs = synthetic_trace()
    profile = v.load_json(ROOT / "diagnostics/deferred_priority/profile.json")
    files = {"raw.json": json.dumps(raw).encode(), "raw.stdout": json.dumps(raw).encode(), "raw.stderr": b"", "scenarios.json": (ROOT / "diagnostics/deferred_priority/scenarios.json").read_bytes(),
        "probe": b"\x7fELFsynthetic-checker-only", "rustc.stdout": b"rustc 1.98.1 synthetic only\n", "cargo.stdout": b"cargo 1.98.1 synthetic only\n", "rustc.stderr": b"", "cargo.stderr": b"", "build.stdout": b"", "build.stderr": b""}
    files["toolchain.txt"] = files["rustc.stdout"] + files["cargo.stdout"]
    files.update({v.retained_path(p): (ROOT / p).read_bytes() for p in v.RETAIN + list(profile["frozen_original"]["sha256"])})
    files.update({"upstream/" + p: b"synthetic upstream source only" for p in v.UPSTREAM_RETAIN})
    files["build-Cargo.toml"] = files[v.retained_path("adapters/deferred_priority_rust/Cargo.toml")].replace(b'"../../../zed-source/crates/gpui"', b'"/synthetic-upstream/crates/gpui"')
    files["build-Cargo.lock"] = files[v.retained_path("adapters/deferred_priority_rust/Cargo.lock")]
    build = ["cargo", "+1.98.1", "build", "--locked", "--manifest-path", str(directory.parent / ("deferred-priority-build-" + raw["run_token"]) / "adapter/Cargo.toml")]
    execute = [str(directory / "probe"), str(directory / "scenarios.json"), raw["run_token"]]
    environment = {"CARGO_BUILD_JOBS": "2", "CARGO_INCREMENTAL": "0", "DISPLAY": None, "WAYLAND_DISPLAY": None}
    sha = lambda name: v.hashlib.sha256(files[name]).hexdigest()
    plan = {"schema_version": 1, "layer": v.LAYER, "run_token": raw["run_token"], "build_command": build, "execution_command": execute,
        "environment": environment, "input_sha256": sha("scenarios.json"), "lock_sha256": sha(v.retained_path("adapters/deferred_priority_rust/Cargo.lock")),
        "build_manifest_sha256": sha("build-Cargo.toml"), "toolchain_sha256": sha("toolchain.txt")}
    files["build-plan.json"] = json.dumps(plan).encode()
    for name, content in files.items():
        path = directory / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(content)
    identity = {"commit": "a" * 40, "tree": "b" * 40, "clean": True}
    upstream = {"commit": v.UPSTREAM, "tree": v.UPSTREAM_TREE, "clean": True}
    run = lambda cmd: {"command": cmd, "returncode": 0, "timed_out": False, "resource_floor_breached": False}
    manifest = {"schema_version": 1, "layer": v.LAYER, "suite": identity, "suite_after": identity.copy(), "upstream": upstream,
        "upstream_after": upstream.copy(), "upstream_source_path": "/synthetic-upstream", "run_token": raw["run_token"], "environment": environment,
        "disk_floor_bytes": 1024**3, "disk_start": {"/tmp": 2*1024**3}, "disk_end": {"/tmp": 2*1024**3},
        "build": run(build), "execution": run(execute), "rustc": run(["rustc", "+1.98.1", "--version", "--verbose"]), "cargo": run(["cargo", "+1.98.1", "--version", "--verbose"]),
        "files": {name: {"sha256": v.digest(directory / name), "size": len(content)} for name, content in files.items()}}
    (directory / "manifest.json").write_text(json.dumps(manifest))
    return manifest


class DeferredPriorityContracts(unittest.TestCase):
    def test_frozen_corpus_source_paths_and_budget(self):
        inputs = corpus(); v.validate_scenarios(inputs)
        self.assertEqual(len(inputs["cases"]), 16)
        self.assertEqual({c["id"].split("-scale")[0] for c in inputs["cases"]}, set(ORDERS))
        self.assertEqual({c["scale_factor"] for c in inputs["cases"]}, {1, 1.25})
        profile = v.load_json(ROOT / "diagnostics/deferred_priority/profile.json")
        self.assertEqual(profile["input_sha256"], v.digest(ROOT / "diagnostics/deferred_priority/scenarios.json"))
        self.assertEqual(profile["geometry_allowance_logical_px"], 2**-10)
        self.assertEqual(profile["physical_grid_allowance_px"], 2**-10)
        self.assertEqual(profile["order_and_ids_allowance"], 0)
        for name, sha in profile["frozen_original"]["sha256"].items(): self.assertEqual(v.digest(ROOT / name), sha)
        for name in v.RETAIN: self.assertTrue((ROOT / name).is_file(), name)
        self.assertIn("crates/gpui/examples/popover.rs", v.UPSTREAM_RETAIN)
        self.assertIn("crates/gpui/src/window.rs", v.UPSTREAM_RETAIN)

    def test_all_synthetic_controls_do_not_claim_execution(self):
        raw, inputs = synthetic_trace(); result = v.verify_observations(raw, inputs)
        self.assertEqual(result["case_count"], 16); self.assertEqual(result["observed_frame_count"], 80)
        self.assertIn("no nesting", result["claim"])

    def test_explicit_distinct_stacking_and_input_semantics(self):
        for family, expected_count in (("ascending", 11), ("transparent-top", 8), ("occluding-top", 1), ("stopping-top", 1)):
            raw, inputs = single(family); report = v.verify_observations(raw, inputs)
            observed = report["cases"][0]["operations"][2]["observed_input_callbacks"]
            self.assertEqual(len(observed), expected_count, family)
            if expected_count == 1: self.assertEqual(observed[0]["node"], "c.second")

    def test_rejects_priority_sort_tie_reversal_and_subtree_interleaving(self):
        for family in ("ascending", "descending", "equal-one", "equal-one-reverse", "equal-zero"):
            for phase in ("request_layout", "prepaint", "paint"):
                raw, inputs = single(family); events = raw["cases"][0]["events"]
                matches = [e for e in events if e["operation"] == "base" and e["event"]["type"] == phase and e["event"]["node"].endswith(".root")]
                matches[0]["event"]["node"], matches[1]["event"]["node"] = matches[1]["event"]["node"], matches[0]["event"]["node"]
                with self.subTest(family=family, phase=phase), self.assertRaisesRegex(ValueError, "lifecycle order"): v.verify_observations(raw, inputs)

    def test_rejects_stale_removed_layer_and_incomplete_restoration(self):
        for operation in ("updated", "removed", "restored"):
            raw, inputs = single(); events = raw["cases"][0]["events"]
            event = next(e for e in events if e["operation"] == operation and e["event"]["type"] == "prepaint" and e["event"]["node"].endswith(".root"))
            event["event"]["node"] = "stale.root"
            with self.subTest(operation=operation), self.assertRaises(ValueError): v.verify_observations(raw, inputs)

    def test_rejects_topmost_only_and_callback_reordering(self):
        for mutation in ("drop", "reverse", "extra", "listener", "propagation", "occlude", "position", "transparent"):
            raw, inputs = single("transparent-top" if mutation == "transparent" else "ascending")
            events = raw["cases"][0]["events"]; indices = [i for i,e in enumerate(events) if e["operation"] == "base.input" and e["event"]["type"] == "mouse_down"]
            if mutation == "drop": events.pop(indices[1])
            if mutation == "reverse": events[indices[0]]["event"], events[indices[1]]["event"] = events[indices[1]]["event"], events[indices[0]]["event"]
            if mutation == "extra": events.insert(indices[0], copy.deepcopy(events[indices[0]]))
            if mutation == "listener": events[indices[0]]["event"]["listener"] = "none"
            if mutation == "propagation": events[indices[0]]["event"]["propagation"] = "stop"
            if mutation == "occlude": events[indices[0]]["event"]["occlude"] = True
            if mutation == "position": events[indices[0]]["event"]["position"][0] += 4
            if mutation == "transparent": events[indices[0]]["event"]["node"] = "c.second"
            for i,e in enumerate(events): e["sequence"] = i
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): v.verify_observations(raw, inputs)

    def test_rejects_geometry_mask_offset_and_nonfinite(self):
        for field, value in (("bounds", [49,48,128,96]), ("content_mask", [0,0,319,240]), ("element_offset", [47,48]), ("bounds", [float("nan"),48,128,96]), ("bounds", [True,48,128,96])):
            raw, inputs = single()
            event = next(e["event"] for e in raw["cases"][0]["events"] if e["operation"] == "base" and e["event"]["type"] == "prepaint" and e["event"]["node"] == "a.root")
            event[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError): v.verify_observations(raw, inputs)

    def test_rejects_missing_extra_out_of_order_and_unknown_trace(self):
        for mutation in ("sequence", "operation", "frame", "missing", "extra", "pin", "input", "unknown", "scale"):
            raw, inputs = single(); entries = raw["cases"][0]["events"]
            if mutation in ("sequence", "frame"): entries[4][mutation] = 999
            if mutation == "operation": entries[4]["operation"] = "wrong"
            if mutation == "missing": entries.pop(4)
            if mutation == "extra": entries.append(copy.deepcopy(entries[-1]))
            if mutation == "pin": raw["upstream_revision"] = "0" * 40
            if mutation == "input": raw["input"] = copy.deepcopy(inputs); raw["input"]["cases"][0]["update_priority"] = 1
            if mutation == "unknown": entries[4]["event"]["invented"] = 1
            if mutation == "scale": entries[1]["event"]["scale_factor"] = 1
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): v.verify_observations(raw, inputs)

    def test_manifest_integrity_and_non_source_bound_label(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "_build/evidence"; out.mkdir(parents=True)
            synthetic_bundle(out); report = v.verify_bundle(out)
            self.assertFalse(report["source_bound"])
            self.assertIn("authenticity unqualified", report["inspection_scope"])
            (out / "raw.stdout").write_bytes(b"corruption")
            with self.assertRaisesRegex(ValueError, "changed evidence"): v.verify_bundle(out)

    def test_rejects_rehashed_original_stdout_token_commands_and_budget(self):
        for mutation in ("stdout", "token", "command", "build", "budget", "lock", "toolchain", "floor"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                out = Path(temp) / "_build/evidence"; out.mkdir(parents=True); manifest = synthetic_bundle(out)
                changed = None
                if mutation == "stdout": changed = "raw.stdout"; (out / changed).write_bytes(b"{}");
                if mutation == "token": manifest["run_token"] = "different-run-token-0000"
                if mutation == "command": manifest["execution"]["command"][0] = "/other/probe"
                if mutation == "build": manifest["build"]["command"].remove("--locked")
                if mutation == "budget":
                    changed = v.retained_path("diagnostics/deferred_priority/profile.json")
                    profile = v.load_json(out / changed); profile["geometry_allowance_logical_px"] = 1
                    (out / changed).write_text(json.dumps(profile))
                if mutation == "lock": changed = "build-Cargo.lock"; (out / changed).write_bytes(b"changed lock")
                if mutation == "toolchain": manifest["cargo"]["command"][1] = "+stable"
                if mutation == "floor": manifest["disk_end"]["/tmp"] = 0
                if changed: manifest["files"][changed] = {"sha256": v.digest(out / changed), "size": (out / changed).stat().st_size}
                (out / "manifest.json").write_text(json.dumps(manifest))
                with self.assertRaises(ValueError): v.verify_bundle(out)

    def test_source_binding_rejects_coherently_rehashed_changed_source(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "_build/evidence"; out.mkdir(parents=True); manifest = synthetic_bundle(out)
            relative = "adapters/deferred_priority_rust/src/main.rs"; path = out / v.retained_path(relative)
            path.write_text(path.read_text() + "// forged source\n")
            manifest["files"][v.retained_path(relative)] = {"sha256": v.digest(path), "size": path.stat().st_size}
            (out / "manifest.json").write_text(json.dumps(manifest))
            def show(command, cwd=None, text=False):
                if command[1] == "rev-parse": return manifest["suite"]["tree"] + "\n"
                name = command[2].split(":",1)[1]; return (ROOT / name).read_bytes()
            with patch.object(v.subprocess, "check_output", side_effect=show):
                with self.assertRaisesRegex(ValueError, "exact committed source"): v.verify_bundle(out, suite_source=ROOT)

    def test_safe_evidence_file_names_and_symlinks(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/"real").write_text("x"); (root/"link").symlink_to(root/"real")
            for name in ("../outside", "/absolute", "link"):
                with self.subTest(name=name), self.assertRaises(ValueError): v.strict_file(root,name)

    def test_rejects_nested_arbitrary_geometry_and_implicit_interaction_inputs(self):
        for mutation in ("nested", "priority", "position", "implicit", "interactive-transparent", "update-noop"):
            data=corpus(); case=data["cases"][0]
            if mutation == "nested": case["layers"][0]["children"] = []
            if mutation == "priority": case["layers"][0]["priority"] = True
            if mutation == "position": case["position"][0] = 48.25
            if mutation == "implicit": del case["layers"][0]["interaction"]["occlude"]
            if mutation == "interactive-transparent": case["layers"][0]["transparent"] = True
            if mutation == "update-noop": case["update_priority"] = case["layers"][0]["priority"]
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): v.validate_scenarios(data)

    def test_runner_retains_original_build_and_runtime_failures(self):
        spec = importlib.util.spec_from_file_location("deferred_priority_run", ROOT / "diagnostics/deferred_priority/run.py")
        runner = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"verify": v}): spec.loader.exec_module(runner)
        for failure in ("build", "raw"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary)/"suite"; upstream=Path(temporary)/"upstream"
                profile=v.load_json(ROOT/"diagnostics/deferred_priority/profile.json")
                for relative in v.RETAIN + list(profile["frozen_original"]["sha256"]):
                    destination=root/relative; destination.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copy2(ROOT/relative,destination)
                for relative in v.UPSTREAM_RETAIN:
                    destination=upstream/relative; destination.parent.mkdir(parents=True,exist_ok=True)
                    destination.write_text("synthetic upstream bytes; never compiled\n")
                identity={"commit":"a"*40,"tree":"b"*40,"clean":True}
                def execute(command,directory,stem,environment,timeout):
                    output=(stem+" original partial bytes\n").encode()
                    if stem in ("rustc","cargo"): output=(stem+" 1.98.1 synthetic\n").encode()
                    (directory/(stem+".stdout")).write_bytes(output)
                    (directory/(stem+".stderr")).write_bytes(b"retained failure stderr" if stem==failure else b"")
                    if stem=="build" and failure!="build":
                        binary=Path(environment["CARGO_TARGET_DIR"])/"debug/gpui-deferred-priority-diagnostic"
                        binary.parent.mkdir(parents=True); binary.write_bytes(b"\x7fELFsynthetic")
                    return {"command":command,"returncode":1 if stem==failure else 0,"timed_out":False,"resource_floor_breached":False}
                output=root/"_build/evidence"
                argv=["run.py","--upstream-source",str(upstream),"--output",str(output)]
                with patch.object(runner,"ROOT",root), patch.object(runner,"source_identity",return_value=identity), patch.object(runner,"execute",side_effect=execute), patch.object(runner.shutil,"disk_usage",return_value=type("Disk",(),{"free":9*1024**3})()), patch.object(sys,"argv",argv):
                    with self.assertRaisesRegex(ValueError,"failed; original"): runner.main()
                self.assertEqual((output/(failure+".stdout")).read_bytes(),(failure+" original partial bytes\n").encode())
                self.assertEqual((output/(failure+".stderr")).read_bytes(),b"retained failure stderr")
                if failure=="raw": self.assertEqual((output/"raw.json").read_bytes(),(output/"raw.stdout").read_bytes())
                manifest=v.load_json(output/"manifest.json")
                self.assertIn("run-failure.json",manifest["files"])
                for relative,metadata in manifest["files"].items(): self.assertEqual(v.digest(output/relative),metadata["sha256"])
                self.assertFalse((output/"verification.json").exists())

    def test_observer_contains_no_predicted_sort_or_hit_test(self):
        source = (ROOT / "adapters/deferred_priority_rust/src/main.rs").read_text()
        for disallowed in ("sort_by", ".sort(", "hit_test(", "expected_order", "derive_input", "derive_lifecycle"):
            self.assertNotIn(disallowed, source)
        for required in (".with_priority(priority)", "self.inner.request_layout", "self.inner", "window.content_mask()", "simulate_click", "stop_propagation", ".occlude()", "rgba(0x00000000)"):
            self.assertIn(required, source)
        run=(ROOT / "diagnostics/deferred_priority/run.py").read_text()
        self.assertIn('"raw.stdout", out / "raw.json"',run)
        self.assertIn('"run-failure.json"',run)
        self.assertIn('DISK_FLOOR = 1024**3',run)


if __name__ == "__main__": unittest.main()
