"""Synthetic checker sensitivity controls, never actual Rust or engine-mutation evidence."""
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
spec = importlib.util.spec_from_file_location("nested_deferred_verify", ROOT / "diagnostics/nested_deferred/verify.py")
v = importlib.util.module_from_spec(spec); spec.loader.exec_module(v)


def corpus(): return v.load_json(ROOT / "diagnostics/nested_deferred/scenarios.json")


# Manually authored independent schedule witnesses: (round one, round two, global paint).
ORDERS = {
    "increasing": [("a b", "a.nested b.nested", "a b a.nested b.nested"), ("b a", "a.nested b.nested", "b a.nested a b.nested"), ("b a", "b.nested", "b a b.nested")],
    "child-lower": [("a b", "a.nested b.nested", "a.nested b.nested a b"), ("b a", "a.nested b.nested", "a.nested b.nested b a"), ("b a", "b.nested", "b.nested b a")],
    "all-equal": [("a b", "a.nested b.nested", "a b a.nested b.nested"), ("b a", "b.nested a.nested", "b b.nested a.nested a"), ("b a", "b.nested", "b b.nested a")],
    "reversed-parents": [("b a", "b.nested a.nested", "b a b.nested a.nested"), ("a b", "a.nested b.nested", "a b a.nested b.nested"), ("a b", "b.nested", "a b b.nested")],
}


def synthetic_trace(inputs=None):
    """Fixed authored transcripts from explicit witnesses above; not observed GPUI output."""
    inputs = copy.deepcopy(corpus() if inputs is None else inputs)
    observations = []
    for case in inputs["cases"]:
        events, frame = [], 0
        def emit(event, operation): events.append({"sequence": len(events), "operation": operation, "frame": frame, "event": event})
        family = case["id"].split("-scale")[0]
        operations = [("initial", {"action": "open_window"}, "base", 2),
            ("base", {"action": "set_scale_factor", "scale_factor": case["scale_factor"]}, "base", case["scale_factor"]),
            ("updated", {"action": "set_parent_priority", "layer": "a", "priority": case["update_priority"]}, "updated", case["scale_factor"]),
            ("removed", {"action": "remove_nested_child", "layer": "a"}, "removed", case["scale_factor"]),
            ("restored", {"action": "restore_original_tree"}, "restored", case["scale_factor"]),
            ("moved", {"action": "move_ancestor", "delta": [16, 12]}, "moved", case["scale_factor"])]
        for operation, action, stage, scale in operations:
            emit({"type": "operation_start", "input": action}, operation)
            frame += 1
            emit({"type": "frame_start", "scale_factor": scale, "window_size": [320, 240], "client_inset": None}, operation)
            first, second, paint = [order.split() for order in ORDERS[family][{"updated": 1, "removed": 2}.get(stage, 0)]]
            def callback(phase, node):
                event = {"type": phase, "node": node}
                if phase.startswith(("prepaint", "paint")):
                    origin = [40, 32] if stage == "moved" else [24, 20]
                    bounds, offset = [0, 0, 320, 240], [0, 0]
                    if node == "$ancestor": bounds = [*origin, 272, 192]
                    elif node.startswith("ordinary."):
                        delta = [8, 8] if node.endswith("after") else [0, 0]
                        bounds = [origin[a]+delta[a] for a in (0, 1)] + [12, 12]
                    elif not node.startswith("$"):
                        prefix, suffix = node[0], node.split(".")[-1]
                        outer = [24, 24] if prefix == "a" else [144, 64]
                        if ".nested." in node:
                            offset = outer[:]
                            bounds = [origin[a] + outer[a] for a in (0, 1)] + [40, 32]
                            if suffix == "root":
                                offset = [outer[a] + [32, 24][a] for a in (0, 1)]
                                bounds = [origin[a] + offset[a] for a in (0, 1)] + [40, 32]
                        elif suffix in ("deferred", "anchor"): bounds = [*origin, 96, 72]
                        else:
                            offset = outer[:]
                            delta = [16, 8] if suffix == "after" else [0, 0]
                            bounds = [origin[a]+outer[a]+delta[a] for a in (0, 1)] + ([96, 72] if suffix == "root" else [12, 12])
                    event.update(bounds=bounds, content_mask=[0, 0, 320, 240])
                    if phase.startswith("prepaint"): event["element_offset"] = offset
                emit(event, operation)
            def visit(phase, node, body=None):
                callback(phase, node)
                if body: body()
                callback(phase + "_end", node)
            def subtree(phase, prefix):
                def children():
                    if not prefix.endswith(".nested"):
                        visit(phase, prefix + ".before")
                        if stage != "removed" or prefix != "a":
                            visit(phase, prefix + ".nested.deferred", (lambda: subtree(phase, prefix + ".nested")) if phase == "request_layout" else None)
                        visit(phase, prefix + ".after")
                visit(phase, prefix + ".anchor", lambda: visit(phase, prefix + ".root", children))
            for phase in ("request_layout", "prepaint", "paint"):
                def ancestor():
                    visit(phase, "ordinary.before")
                    for prefix in ("a", "b"):
                        visit(phase, prefix + ".deferred", (lambda prefix=prefix: subtree(phase, prefix)) if phase == "request_layout" else None)
                    visit(phase, "ordinary.after")
                visit(phase, "$host", lambda: visit(phase, "$ancestor", ancestor))
                for prefix in (first + second if phase == "prepaint" else paint if phase == "paint" else []): subtree(phase, prefix)
            emit({"type": "operation_end", "scale_factor": scale}, operation)
        observations.append({"id": case["id"], "events": events})
    return {"schema_version": 1, "layer": v.LAYER, "fixture": "font-free-two-level-nested-deferred", "text_system": "NoopTextSystem; no text used", "upstream_revision": v.UPSTREAM, "run_token": "synthetic-checker-only-0001", "input": inputs, "cases": observations}, inputs


def single(family="reversed-parents"):
    inputs = corpus(); inputs["cases"] = [next(case for case in inputs["cases"] if case["id"] == family + "-scale1")]
    return synthetic_trace(inputs)


def synthetic_bundle(directory):
    raw, inputs = synthetic_trace()
    profile = v.load_json(ROOT / "diagnostics/nested_deferred/profile.json")
    files = {"raw.json": json.dumps(raw).encode(), "raw.stdout": json.dumps(raw).encode(), "raw.stderr": b"", "scenarios.json": (ROOT / "diagnostics/nested_deferred/scenarios.json").read_bytes(),
        "probe": b"\x7fELFsynthetic-checker-only", "rustc.stdout": b"rustc 1.98.1 synthetic only\n", "cargo.stdout": b"cargo 1.98.1 synthetic only\n", "rustc.stderr": b"", "cargo.stderr": b"", "build.stdout": b"", "build.stderr": b""}
    files["toolchain.txt"] = files["rustc.stdout"] + files["cargo.stdout"]
    files.update({v.retained_path(p): (ROOT / p).read_bytes() for p in v.RETAIN + list(profile["frozen_original"]["sha256"])})
    files.update({"upstream/" + p: b"synthetic upstream source only" for p in v.UPSTREAM_RETAIN})
    files["build-Cargo.toml"] = files[v.retained_path("adapters/nested_deferred_rust/Cargo.toml")].replace(b'"../../../zed-source/crates/gpui"', b'"/synthetic-upstream/crates/gpui"')
    files["build-Cargo.lock"] = files[v.retained_path("adapters/nested_deferred_rust/Cargo.lock")]
    build = ["cargo", "+1.98.1", "build", "--locked", "--manifest-path", str(directory.parent / ("nested-deferred-build-" + raw["run_token"]) / "adapter/Cargo.toml")]
    execute = [str(directory / "probe"), str(directory / "scenarios.json"), raw["run_token"]]
    environment = {"CARGO_BUILD_JOBS": "2", "CARGO_INCREMENTAL": "0", "DISPLAY": None, "WAYLAND_DISPLAY": None}
    sha = lambda name: v.hashlib.sha256(files[name]).hexdigest()
    plan = {"schema_version": 1, "layer": v.LAYER, "run_token": raw["run_token"], "build_command": build, "execution_command": execute,
        "environment": environment, "input_sha256": sha("scenarios.json"), "lock_sha256": sha(v.retained_path("adapters/nested_deferred_rust/Cargo.lock")),
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


class NestedDeferredContracts(unittest.TestCase):
    def test_frozen_corpus_source_paths_and_budget(self):
        inputs = corpus(); v.validate_scenarios(inputs)
        self.assertEqual(len(inputs["cases"]), 8)
        self.assertEqual({c["id"].split("-scale")[0] for c in inputs["cases"]}, set(ORDERS))
        self.assertEqual({c["scale_factor"] for c in inputs["cases"]}, {1, 1.25})
        profile = v.load_json(ROOT / "diagnostics/nested_deferred/profile.json")
        self.assertEqual(profile["input_sha256"], v.digest(ROOT / "diagnostics/nested_deferred/scenarios.json"))
        self.assertEqual(profile["geometry_allowance_logical_px"], 2**-10)
        self.assertEqual(profile["physical_grid_allowance_px"], 2**-10)
        self.assertEqual(profile["order_and_ids_allowance"], 0)
        for name, sha in profile["baseline_tracked_sha256"].items(): self.assertEqual(v.digest(ROOT / name), sha)
        for name, sha in profile["frozen_original"]["sha256"].items(): self.assertEqual(v.digest(ROOT / name), sha)
        for name in v.RETAIN: self.assertTrue((ROOT / name).is_file(), name)

    def test_all_synthetic_controls_do_not_claim_execution(self):
        raw, inputs = synthetic_trace(); result = v.verify_observations(raw, inputs)
        self.assertEqual(result["case_count"], 8); self.assertEqual(result["observed_frame_count"], 48)
        self.assertIn("No input", result["claim"])
        self.assertIn("wrapper callbacks", result["claim"])

    def test_manual_reversed_parent_discovery_witness(self):
        raw, inputs = single(); result = v.verify_observations(raw, inputs)
        frame = result["cases"][0]["operations"][1]["frames"][0]
        derivation = frame["checker_derivation_not_observation"]
        self.assertEqual(derivation["prepaint_discovery_rounds"], [["b", "a"], ["b.nested", "a.nested"]])
        self.assertEqual([x["id"] for x in derivation["append_registry"]], ["a", "b", "b.nested", "a.nested"])
        self.assertEqual(derivation["global_stable_paint_registry"], ["b", "a", "b.nested", "a.nested"])
        self.assertEqual(frame["observed_paintable_box_projection"], ["ordinary.before", "ordinary.after", "b.root", "b.before", "b.after", "a.root", "a.before", "a.after", "b.nested.root", "a.nested.root"])
        self.assertIn("a.nested.deferred", frame["observed_paint_order"])
        self.assertNotIn("a.nested.deferred", frame["observed_paintable_box_projection"])

    def test_checker_rejects_structural_dfs_ties_and_parent_contiguity(self):
        for wrong in (["b", "a", "a.nested", "b.nested"], ["b", "b.nested", "a", "a.nested"]):
            raw, inputs = single(); events = raw["cases"][0]["events"]
            start = next(i for i, e in enumerate(events) if e["operation"] == "base" and e["event"]["type"] == "paint" and e["event"].get("node") == "b.anchor")
            end = next(i for i in range(start,len(events)) if events[i]["event"]["type"] == "operation_end")
            tail = events[start:end]; blocks = {}
            for prefix in ("a", "b", "a.nested", "b.nested"):
                lo = next(i for i,e in enumerate(tail) if e["event"]["type"] == "paint" and e["event"]["node"] == prefix + ".anchor")
                hi = next(i for i in range(lo,len(tail)) if tail[i]["event"]["type"] == "paint_end" and tail[i]["event"]["node"] == prefix + ".anchor") + 1
                blocks[prefix] = tail[lo:hi]
            events[start:end] = [e for prefix in wrong for e in blocks[prefix]]
            for i,e in enumerate(events): e["sequence"] = i
            with self.subTest(wrong=wrong), self.assertRaisesRegex(ValueError,"lifecycle order"): v.verify_observations(raw,inputs)

    def test_checker_rejects_missing_round_omitted_and_duplicated_nested_boxes(self):
        for mutation in ("second-round", "omitted-box", "duplicated-box", "return"):
            raw, inputs = single(); events=raw["cases"][0]["events"]
            if mutation == "second-round":
                events[:] = [e for e in events if not (e["operation"] == "base" and e["event"]["type"].startswith("prepaint") and e["event"].get("node") in ("a.nested.anchor","a.nested.root","b.nested.anchor","b.nested.root"))]
            else:
                ix = next(i for i,e in enumerate(events) if e["operation"] == "base" and e["event"]["type"] == "paint" and e["event"]["node"] == "a.nested.root")
                if mutation == "omitted-box": events.pop(ix)
                if mutation == "duplicated-box": events.insert(ix, copy.deepcopy(events[ix]))
                if mutation == "return": events[ix+1]["event"]["node"] = "b.nested.root"
            for i,e in enumerate(events): e["sequence"] = i
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError,"lifecycle order"): v.verify_observations(raw,inputs)

    def test_checker_rejects_ancestor_offset_mask_and_geometry_errors(self):
        for phase in ("prepaint", "prepaint_end", "paint", "paint_end"):
            for field in (("bounds", "content_mask", "element_offset") if phase.startswith("prepaint") else ("bounds", "content_mask")):
                raw, inputs=single(); event=next(e["event"] for e in raw["cases"][0]["events"] if e["operation"] == "moved" and e["event"]["type"] == phase and e["event"]["node"] == "a.nested.root")
                event[field][0] += 16
                with self.subTest(phase=phase,field=field), self.assertRaises(ValueError): v.verify_observations(raw,inputs)

    def test_checker_rejects_missing_extra_stale_and_unknown_trace(self):
        for mutation in ("sequence", "operation", "frame", "missing", "extra", "pin", "input", "unknown", "scale", "stale-nested"):
            raw,inputs=single(); entries=raw["cases"][0]["events"]
            if mutation in ("sequence","frame"): entries[4][mutation]=999
            if mutation == "operation": entries[4]["operation"]="wrong"
            if mutation == "missing": entries.pop(4)
            if mutation == "extra": entries.append(copy.deepcopy(entries[-1]))
            if mutation == "pin": raw["upstream_revision"]="0"*40
            if mutation == "input": raw["input"]=copy.deepcopy(inputs);raw["input"]["cases"][0]["margin"]=9
            if mutation == "unknown": entries[4]["event"]["invented"]=1
            if mutation == "scale": entries[1]["event"]["scale_factor"]=1
            if mutation == "stale-nested":
                event=next(e["event"] for e in entries if e["operation"]=="removed" and e["event"].get("node")=="b.nested.root");event["node"]="a.nested.root"
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):v.verify_observations(raw,inputs)

    def test_rejects_unqualified_inputs(self):
        for mutation in ("depth", "priority", "position", "margin", "listener", "update-noop", "nonfinite"):
            data=corpus();case=data["cases"][0]
            if mutation=="depth":case["layers"][0]["children"]=[]
            if mutation=="priority":case["layers"][0]["priority"]=True
            if mutation=="position":case["nested_position"][0]=32.25
            if mutation=="margin":case["margin"]=0
            if mutation=="listener":case["listener"]="mouse-down"
            if mutation=="update-noop":case["update_priority"]=1
            if mutation=="nonfinite":case["ancestor_origin"][0]=float("nan")
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):v.validate_scenarios(data)

    def test_source_scope_excludes_any_baseline_or_unowned_change(self):
        allowed = "\n".join("A\t" + name for name in v.RETAIN)
        with patch.object(v.subprocess, "check_output", side_effect=[v.SUITE_BASE_TREE + "\n", allowed]):
            v.validate_baseline_source(ROOT, "a" * 40)
        for changed in (allowed + "\nM\tdiagnostics/deferred_priority/verify.py", allowed + "\nA\tnew-unowned.py", allowed.replace("A\t" + v.RETAIN[0], "M\t" + v.RETAIN[0]), ""):
            with self.subTest(changed=changed), patch.object(v.subprocess, "check_output", side_effect=[v.SUITE_BASE_TREE, changed]), self.assertRaises(ValueError):
                v.validate_baseline_source(ROOT, "a" * 40)
        with patch.object(v.subprocess, "check_output", return_value="0" * 40), self.assertRaisesRegex(ValueError, "base tree"):
            v.validate_baseline_source(ROOT, "a" * 40)

    def test_checker_rejects_incomplete_restoration(self):
        raw, inputs = single(); events = raw["cases"][0]["events"]
        events[:] = [e for e in events if not (e["operation"] == "restored" and e["event"].get("node") == "a.nested.root")]
        for i, event in enumerate(events): event["sequence"] = i
        with self.assertRaisesRegex(ValueError, "lifecycle order"): v.verify_observations(raw, inputs)

    def test_observer_has_no_scheduling_or_input_model(self):
        source=(ROOT/"adapters/nested_deferred_rust/src/main.rs").read_text()
        for disallowed in ("sort_by", ".sort(", "hit_test(", "expected_order", "derived_", "simulate_click", "on_mouse", ".cached(", "scroll"):
            self.assertNotIn(disallowed,source)
        for required in ("self.inner.request_layout", "self.inner", "window.content_mask()", "window.element_offset()", "prepaint_end", "paint_end", ".with_priority(layer.nested_priority)", "AnchoredPositionMode::Local", ".snap_to_window_with_margin(px(margin))"):
            self.assertIn(required,source)
        # element_offset is a prepaint-only API at the exact pin.
        self.assertNotIn("element_offset()",source[source.index("    fn paint("):source.index("fn observed")])

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
                    changed = v.retained_path("diagnostics/nested_deferred/profile.json")
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
            relative = "adapters/nested_deferred_rust/src/main.rs"; path = out / v.retained_path(relative)
            path.write_text(path.read_text() + "// forged source\n")
            manifest["files"][v.retained_path(relative)] = {"sha256": v.digest(path), "size": path.stat().st_size}
            (out / "manifest.json").write_text(json.dumps(manifest))
            def show(command, cwd=None, text=False):
                if command[1] == "rev-parse": return manifest["suite"]["tree"] + "\n"
                name = command[2].split(":",1)[1]; return (ROOT / name).read_bytes()
            with patch.object(v, "validate_baseline_source"), patch.object(v.subprocess, "check_output", side_effect=show):
                with self.assertRaisesRegex(ValueError, "exact committed source"): v.verify_bundle(out, suite_source=ROOT)

    def test_safe_evidence_file_names_and_symlinks(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/"real").write_text("x"); (root/"link").symlink_to(root/"real")
            for name in ("../outside", "/absolute", "link"):
                with self.subTest(name=name), self.assertRaises(ValueError): v.strict_file(root,name)

    def test_runner_retains_original_build_and_runtime_failures(self):
        spec = importlib.util.spec_from_file_location("nested_deferred_run", ROOT / "diagnostics/nested_deferred/run.py")
        runner = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"verify": v}): spec.loader.exec_module(runner)
        for failure in ("build", "raw"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary)/"suite"; upstream=Path(temporary)/"upstream"
                profile=v.load_json(ROOT/"diagnostics/nested_deferred/profile.json")
                for relative in v.RETAIN + list(profile["baseline_tracked_sha256"]):
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
                        binary=Path(environment["CARGO_TARGET_DIR"])/"debug/gpui-nested-deferred-diagnostic"
                        binary.parent.mkdir(parents=True); binary.write_bytes(b"\x7fELFsynthetic")
                    return {"command":command,"returncode":1 if stem==failure else 0,"timed_out":False,"resource_floor_breached":False}
                output=root/"_build/evidence"
                argv=["run.py","--upstream-source",str(upstream),"--output",str(output)]
                with patch.object(runner,"validate_baseline_source"), patch.object(runner,"ROOT",root), patch.object(runner,"source_identity",return_value=identity), patch.object(runner,"execute",side_effect=execute), patch.object(runner.shutil,"disk_usage",return_value=type("Disk",(),{"free":9*1024**3})()), patch.object(sys,"argv",argv):
                    with self.assertRaisesRegex(ValueError,"failed; original"): runner.main()
                self.assertEqual((output/(failure+".stdout")).read_bytes(),(failure+" original partial bytes\n").encode())
                self.assertEqual((output/(failure+".stderr")).read_bytes(),b"retained failure stderr")
                if failure=="raw": self.assertEqual((output/"raw.json").read_bytes(),(output/"raw.stdout").read_bytes())
                manifest=v.load_json(output/"manifest.json")
                self.assertIn("run-failure.json",manifest["files"])
                for relative,metadata in manifest["files"].items(): self.assertEqual(v.digest(output/relative),metadata["sha256"])
                self.assertFalse((output/"verification.json").exists())


if __name__ == "__main__": unittest.main()
