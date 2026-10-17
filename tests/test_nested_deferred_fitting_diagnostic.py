"""Synthetic checker controls only: no actual GPUI run or executed production mutation."""
import copy
from decimal import Decimal, ROUND_HALF_UP, ROUND_HALF_DOWN
import importlib.util
import json
import shutil
import sys
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("nested_fitting_verify", ROOT / "diagnostics/nested_deferred_fitting/verify.py")
v = importlib.util.module_from_spec(spec); spec.loader.exec_module(v)

def corpus(): return v.load_json(ROOT / "diagnostics/nested_deferred_fitting/scenarios.json")

# Independent fixed baseline witnesses: A outer/nested, then B outer/nested.
BASE = {
 "exact-inside": [[224,168],[280,208],[224,168],[280,208]],
 "outer-only": [[216,160],[248,192],[8,8],[40,40]],
 "inner-only": [[48,52],[272,200],[48,52],[8,8]],
 "both-levels": [[216,160],[272,200],[8,8],[8,8]],
 "threshold-device-half": [[24,28],[25.6,34.4],[24.8,27.2],[25.6,34.4]],
 "signed-half-composed": [[24.8,27.2],[27.2,32.8],[23.2,28.8],[20.8,39.2]],
 "fit-created-half": [[224,168],[280,208],[0,0],[.8,0]],
 "window-local": [[216,160],[80,96],[216,160],[272,200]],
}
ORDERS = {"baseline": (["b","a"],["b.nested","a.nested"],["b","a","b.nested","a.nested"]),
 "child-lower": (["a","b"],["a.nested","b.nested"],["a.nested","b.nested","a","b"]),
 "all-equal": (["a","b"],["a.nested","b.nested"],["a","b","a.nested","b.nested"])}


def independent_geometry(case, stage, scale):
    """Test-only decimal construction, separate from Fraction checker implementation.

    Decimal half modes, independently authored flow coordinates, and explicit
    baseline witnesses exercise the checker; none are runtime observations.
    """
    d = lambda value: Decimal(str(value))
    scale=d(scale); margin=d(case["margin"])
    snap=lambda value:(d(value)*scale).quantize(Decimal(1),rounding=ROUND_HALF_DOWN)/scale
    rounding=lambda value:int(value.quantize(Decimal(1),rounding=ROUND_HALF_UP))
    origin=[40,32] if stage=="moved" else [24,20]
    O=[origin[0],origin[1]+8];height=12 if stage=="reference-height" else 8
    N=[O[0],O[1]+height]
    result={"$host":([0,0,320,240],[0,0]),"$ancestor":([*origin,272,192],[0,0]),"ordinary.reference":([*origin,12,8],[0,0]),"ordinary.before":([*origin,12,12],[0,0]),"ordinary.after":([origin[0]+8,origin[1]+8,12,12],[0,0])}
    for layer in case['layers']:
        prefix=layer['id']; outer=[]; nested=[]; offsets=[]; total=[]; inner_static=[]
        for axis,limit in enumerate((320,240)):
            wanted=d(O[axis])+d(layer['position'][axis])
            if wanted+d((96,72)[axis])>limit: wanted=d(limit-(96,72)[axis])-margin
            if wanted<0: wanted=margin
            offset=rounding(wanted-d(O[axis])); offsets.append(offset)
            outer.append(d(O[axis])+snap(offset)); static=d(N[axis])+snap(offset);inner_static.append(static)
            wanted=d(layer['nested_position'][axis])+(static if layer['nested_mode']=='Local' else 0)
            if wanted+d((40,32)[axis])>limit:wanted=d(limit-(40,32)[axis])-margin
            if wanted<0:wanted=margin
            absolute_offset=offset+rounding(wanted-static);total.append(absolute_offset)
            nested.append(d(N[axis])+snap(absolute_offset))
        for suffix in ('anchor','deferred'):result[prefix+'.'+suffix]=([*O,96,72],[0,0])
        result[prefix+'.root']=([*outer,96,72],offsets)
        result[prefix+'.reference']=([*outer,12,height],offsets)
        result[prefix+'.before']=([*outer,12,12],offsets)
        result[prefix+'.after']=([outer[0]+16,outer[1]+8,12,12],offsets)
        for suffix in ('anchor','deferred'):result[prefix+'.nested.'+suffix]=([*inner_static,40,32],offsets)
        result[prefix+'.nested.root']=([*nested,40,32],total)
    return {name:([float(value) for value in bounds],offset)for name,(bounds,offset)in result.items()}


def synthetic_trace(inputs=None):
    inputs=copy.deepcopy(corpus() if inputs is None else inputs);observations=[]
    for case in inputs['cases']:
        events=[];frame=0
        def emit(event,operation):events.append({'sequence':len(events),'operation':operation,'frame':frame,'event':event})
        operations=[('initial',{'action':'open_window'},2),('scale1',{'action':'set_scale_factor','scale_factor':1},1),('scale1.25',{'action':'set_scale_factor','scale_factor':1.25},1.25),('child-lower',{'action':'set_priorities','priorities':[2,0,3,1]},1.25),('all-equal',{'action':'set_priorities','priorities':[1,1,1,1]},1.25),('moved',{'action':'restore_priorities_and_move_ancestor','delta':[16,12]},1.25),('reference-height',{'action':'restore_ancestor_and_set_nested_reference_height','height':12},1.25),('restored',{'action':'restore_original_state'},1.25)]
        for stage,action,scale in operations:
            emit({'type':'operation_start','input':action},stage);frame+=1
            emit({'type':'frame_start','scale_factor':scale,'window_size':[320,240],'client_inset':None},stage)
            geometry=independent_geometry(case,stage,scale)
            first,second,paint=ORDERS.get(stage,ORDERS['baseline'])
            priorities=[2,0,3,1] if stage=='child-lower' else [1,1,1,1] if stage=='all-equal' else [2,3,1,3]
            def callback(phase,node):
                group='ordinary';priority=None
                if node.startswith(('a.','b.')):
                    nested='.nested.'in node;group=node[0]+('.nested' if nested else '');priority=priorities[(0 if node[0]=='a'else 2)+int(nested)]
                event={'type':phase,'node':node,'group':group,'priority':priority}
                if phase.startswith(('prepaint','paint')):
                    event.update(bounds=geometry[node][0],content_mask=[0,0,320,240])
                    if phase.startswith('prepaint'):event['element_offset']=geometry[node][1]
                emit(copy.deepcopy(event),stage)
            def visit(phase,node,body=None):
                callback(phase,node)
                if body:body()
                callback(phase+'_end',node)
            def subtree(phase,prefix):
                def children():
                    if not prefix.endswith('.nested'):
                        visit(phase,prefix+'.before');visit(phase,prefix+'.reference')
                        visit(phase,prefix+'.nested.deferred',(lambda:subtree(phase,prefix+'.nested')) if phase=='request_layout'else None)
                        visit(phase,prefix+'.after')
                visit(phase,prefix+'.anchor',lambda:visit(phase,prefix+'.root',children))
            for phase in ('request_layout','prepaint','paint'):
                def ancestor():
                    visit(phase,'ordinary.before');visit(phase,'ordinary.reference')
                    for prefix in ('a','b'):visit(phase,prefix+'.deferred',(lambda prefix=prefix:subtree(phase,prefix)) if phase=='request_layout'else None)
                    visit(phase,'ordinary.after')
                visit(phase,'$host',lambda:visit(phase,'$ancestor',ancestor))
                for prefix in(first+second if phase=='prepaint'else paint if phase=='paint'else[]):subtree(phase,prefix)
            emit({'type':'operation_end','scale_factor':scale},stage)
        observations.append({'id':case['id'],'events':events})
    return {'schema_version':1,'layer':v.LAYER,'fixture':'font-free-two-level-nested-deferred-fitting-rounding','text_system':'NoopTextSystem; no text used','upstream_revision':v.UPSTREAM,'run_token':'synthetic-checker-only-0001','input':inputs,'cases':observations},inputs


def single(family='signed-half-composed'):
    inputs=corpus();inputs['cases']=[next(case for case in inputs['cases']if case['id']==family)];return synthetic_trace(inputs)


def synthetic_bundle(directory):
    raw, inputs = synthetic_trace()
    profile = v.load_json(ROOT / "diagnostics/nested_deferred_fitting/profile.json")
    files = {"raw.json": json.dumps(raw).encode(), "raw.stdout": json.dumps(raw).encode(), "raw.stderr": b"", "scenarios.json": (ROOT / "diagnostics/nested_deferred_fitting/scenarios.json").read_bytes(),
        "probe": b"\x7fELFsynthetic-checker-only", "rustc.stdout": b"rustc 1.98.1 synthetic only\n", "cargo.stdout": b"cargo 1.98.1 synthetic only\n", "rustc.stderr": b"", "cargo.stderr": b"", "build.stdout": b"", "build.stderr": b""}
    files["toolchain.txt"] = files["rustc.stdout"] + files["cargo.stdout"]
    files.update({v.retained_path(p): (ROOT / p).read_bytes() for p in v.RETAIN + list(profile["frozen_original"]["sha256"])})
    files.update({"upstream/" + p: b"synthetic upstream source only" for p in v.UPSTREAM_RETAIN})
    files["build-Cargo.toml"] = files[v.retained_path("adapters/nested_deferred_fitting_rust/Cargo.toml")].replace(b'"../../../zed-source/crates/gpui"', b'"/synthetic-upstream/crates/gpui"')
    files["build-Cargo.lock"] = files[v.retained_path("adapters/nested_deferred_fitting_rust/Cargo.lock")]
    build = ["cargo", "+1.98.1", "build", "--locked", "--manifest-path", str(directory.parent / ("nested-deferred-fitting-build-" + raw["run_token"]) / "adapter/Cargo.toml")]
    execute = [str(directory / "probe"), str(directory / "scenarios.json"), raw["run_token"]]
    environment = {"CARGO_BUILD_JOBS": "2", "CARGO_INCREMENTAL": "0", "DISPLAY": None, "WAYLAND_DISPLAY": None}
    sha = lambda name: v.hashlib.sha256(files[name]).hexdigest()
    plan = {"schema_version": 1, "layer": v.LAYER, "run_token": raw["run_token"], "build_command": build, "execution_command": execute,
        "environment": environment, "input_sha256": sha("scenarios.json"), "lock_sha256": sha(v.retained_path("adapters/nested_deferred_fitting_rust/Cargo.lock")),
        "build_manifest_sha256": sha("build-Cargo.toml"), "toolchain_sha256": sha("toolchain.txt")}
    files["build-plan.json"] = json.dumps(plan).encode()
    for name, content in files.items():
        path = directory / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(content)
    identity = {"commit": "a" * 40, "tree": "b" * 40, "clean": True}
    upstream = {"commit": v.UPSTREAM, "tree": v.UPSTREAM_TREE, "clean": True}
    run = lambda cmd: {"command": cmd, "returncode": 0, "timed_out": False, "resource_floor_breached": False}
    manifest = {"schema_version": 1, "layer": v.LAYER, "suite": identity, "suite_after": identity.copy(), "upstream": upstream,
        "upstream_after": upstream.copy(), "upstream_source_path": "/synthetic-upstream", "run_token": raw["run_token"], "environment": environment,
        "disk_floor_bytes": 1024**3 + 32*1024**2, "disk_start": {"/tmp": 2*1024**3}, "disk_end": {"/tmp": 2*1024**3},
        "build": run(build), "execution": run(execute), "rustc": run(["rustc", "+1.98.1", "--version", "--verbose"]), "cargo": run(["cargo", "+1.98.1", "--version", "--verbose"]),
        "files": {name: {"sha256": v.digest(directory / name), "size": len(content)} for name, content in files.items()}}
    (directory / "manifest.json").write_text(json.dumps(manifest))
    return manifest


class NestedFittingContracts(unittest.TestCase):
    def test_frozen_693_baseline_blobs_modes_and_exact_inputs(self):
        inputs=corpus();v.validate_scenarios(inputs);self.assertEqual(len(inputs['cases']),8)
        profile=v.load_json(ROOT/'diagnostics/nested_deferred_fitting/profile.json')
        self.assertEqual(profile['input_sha256'],v.digest(ROOT/'diagnostics/nested_deferred_fitting/scenarios.json'))
        self.assertEqual(profile['geometry_allowance_logical_px'],2**-10);self.assertEqual(profile['physical_grid_allowance_px'],2**-10)
        self.assertEqual(profile['order_and_ids_allowance'],0)
        for name,sha in profile['baseline_tracked_sha256'].items():self.assertEqual(v.digest(ROOT/name),sha,name)
        entries={}
        for row in subprocess.check_output(['git','ls-tree','-r','-z',v.SUITE_BASE],cwd=ROOT).split(b'\0'):
            if not row:continue
            meta,path=row.split(b'\t',1);mode,kind,oid=meta.decode().split();self.assertEqual(kind,'blob');entries[path.decode()]={'mode':mode,'blob':oid}
        self.assertEqual(len(entries),693);self.assertEqual(profile['baseline_git_entries'],entries)
        for name in v.RETAIN:self.assertTrue((ROOT/name).is_file(),name)

    def test_explicit_baseline_rational_witnesses_and_signed_ties(self):
        for case in corpus()['cases']:
            model,_=v.derived_geometry(case,'scale1.25',1.25)
            actual=[model[node][0][:2]for node in('a.root','a.nested.root','b.root','b.nested.root')]
            self.assertEqual(actual,BASE[case['id']],case['id'])
            for stage,scale in [('initial',2),('scale1',1),('scale1.25',1.25),('moved',1.25),('reference-height',1.25)]:
                model,_=v.derived_geometry(case,stage,scale);self.assertEqual(model,independent_geometry(case,stage,scale),(case['id'],stage))
        for n,expected in[(.5,1),(-.5,-1),(1.5,2),(-1.5,-2),(.25,0),(-.25,0)]:self.assertEqual(v.logical_round(n),expected)
        self.assertEqual(float(v.device_snap(2,1.25)),1.6);self.assertEqual(float(v.device_snap(-2,1.25)),-1.6)
        self.assertEqual(float(v.device_snap(3,1.25)),3.2)
        self.assertNotEqual(v.device_snap(3,1.25),v.device_snap(1,1.25)+v.device_snap(2,1.25))

    def test_transition_reference_movement_and_window_control(self):
        byid={c['id']:c for c in corpus()['cases']}
        base,_=v.derived_geometry(byid['threshold-device-half'],'scale1.25',1.25)
        moved,_=v.derived_geometry(byid['threshold-device-half'],'moved',1.25)
        reference,_=v.derived_geometry(byid['threshold-device-half'],'reference-height',1.25)
        v.vector(moved['a.nested.root'][0],[41.6,46.4,40,32],'explicit moved witness',0)
        v.vector(reference['a.nested.root'][0],[25.6,38.4,40,32],'explicit +4 reference witness',0)
        self.assertEqual(base['a.nested.root'][1],reference['a.nested.root'][1])
        for stage in('scale1.25','moved','reference-height'):
            geometry,_=v.derived_geometry(byid['window-local'],stage,1.25)
            self.assertEqual(geometry['a.nested.root'][0],[80,96,40,32]);self.assertEqual(geometry['b.nested.root'][0],[272,200,40,32])
        # Fitting is strict and never rerun after rounding; an inside target can end below margin8.
        geometry,_=v.derived_geometry(byid['inner-only'],'reference-height',1.25)
        self.assertEqual(geometry['b.nested.root'][0],[8,4,40,32])

    def test_all_synthetic_frames_and_priority_only_geometry(self):
        raw,inputs=synthetic_trace();result=v.verify_observations(raw,inputs)
        self.assertEqual(result['case_count'],8);self.assertEqual(result['observed_frame_count'],64)
        for case in result['cases']:
            frames={op['id']:op['frames'][0]for op in case['operations']}
            self.assertEqual(frames['initial']['scale_factor'],2)
            for stage in('child-lower','all-equal'):
                for node,event in frames['scale1.25']['observed_prepaint'].items():
                    for field in('bounds','element_offset','content_mask'):self.assertEqual(event[field],frames[stage]['observed_prepaint'][node][field])
            self.assertEqual(frames['child-lower']['checker_derivation_not_observation']['global_stable_paint_registry'],['a.nested','b.nested','a','b'])
            self.assertEqual(frames['all-equal']['checker_derivation_not_observation']['global_stable_paint_registry'],['a','b','a.nested','b.nested'])
            self.assertEqual(len(frames['scale1.25']['observed_paintable_box_projection']),13)

    def test_all_observed_redraws_are_retained_without_fixed_count(self):
        raw, inputs = single(); entries = raw["cases"][0]["events"]
        start = next(i for i, entry in enumerate(entries) if entry["operation"] == "scale1" and entry["event"]["type"] == "frame_start")
        end = next(i for i in range(start, len(entries)) if entries[i]["event"]["type"] == "operation_end")
        repeated = copy.deepcopy(entries[start:end]); entries[end:end] = repeated
        frame = 0
        for sequence, entry in enumerate(entries):
            if entry["event"]["type"] == "frame_start": frame += 1
            entry["sequence"] = sequence; entry["frame"] = frame
        result = v.verify_observations(raw, inputs)
        self.assertEqual(result["observed_frame_count"], 9)
        self.assertEqual(len(result["cases"][0]["operations"][1]["frames"]), 2)

    def test_checker_rejects_each_fitting_rounding_and_reference_defect(self):
        controls=[('outer-only','scale1.25','a.root','bounds',[224,168,96,72]),
          ('inner-only','scale1.25','a.nested.root','bounds',[280,208,40,32]),
          ('exact-inside','scale1.25','a.root','bounds',[216,160,96,72]),
          ('signed-half-composed','scale1.25','a.nested.root','bounds',[26.4,33.6,40,32]),
          ('signed-half-composed','scale1.25','a.root','element_offset',[0,0]),
          ('threshold-device-half','scale1.25','a.nested.root','bounds',[26.4,33.6,40,32]),
          ('signed-half-composed','scale1.25','a.nested.root','element_offset',[2,-2]),
          ('signed-half-composed','scale1.25','a.nested.root','element_offset',[4,-4]),
          ('window-local','scale1.25','a.nested.root','bounds',[272,200,40,32]),
          ('threshold-device-half','reference-height','a.nested.root','bounds',[25.6,34.4,40,32]),
          ('fit-created-half','scale1.25','b.nested.root','bounds',[.5,.5,40,32])]
        for family,stage,node,field,value in controls:
            raw,inputs=single(family)
            for entry in raw['cases'][0]['events']:
                e=entry['event']
                if entry['operation']==stage and e.get('node')==node and field in e:e[field]=value[:]
            with self.subTest(family=family,field=field,value=value),self.assertRaises(ValueError):v.verify_observations(raw,inputs)

    def test_checker_rejects_order_round_mask_frame_group_and_session_shape(self):
        for change in('order','round','mask','frame','group','priority','operation','unknown','missing-return','raw-pin'):
            raw,inputs=single();events=raw['cases'][0]['events']
            event=next(e for e in events if e['operation']=='scale1.25'and e['event']['type']=='prepaint'and e['event']['node']=='a.nested.root')
            if change=='order':event['event']['node']='b.nested.root'
            if change=='round':events[:]=[e for e in events if not(e['operation']=='scale1.25'and e['event']['type'].startswith('prepaint')and e['event'].get('node')=='a.nested.anchor')]
            if change=='mask':event['event']['content_mask']=[0,0,319,240]
            if change=='frame':event['frame']+=1
            if change=='group':event['event']['group']='a'
            if change=='priority':event['event']['priority']=0
            if change=='operation':event['operation']='moved'
            if change=='unknown':event['event']['predicted_bounds']=[]
            if change=='missing-return':events.remove(next(e for e in events if e['operation']=='scale1.25'and e['event']['type']=='paint_end'))
            if change=='raw-pin':raw['upstream_revision']='0'*40
            for i,e in enumerate(events):e['sequence']=i
            with self.subTest(change=change),self.assertRaises(ValueError):v.verify_observations(raw,inputs)

    def test_numeric_budgets_are_distinct_and_small(self):
        epsilon=2**-10
        v.vector([100+epsilon],[100],'logical bound')
        with self.assertRaises(ValueError):v.vector([100+2*epsilon],[100],'logical bound')
        v.physical_grid([.8,0,40,32],1.25)
        with self.assertRaises(ValueError):v.physical_grid([.801,0,40,32],1.25)
        self.assertEqual(.8/epsilon,819.2);self.assertEqual(1/epsilon,1024)
        raw,inputs=single();event=next(e['event']for e in raw['cases'][0]['events']if e['event']['type']=='prepaint'and e['event']['node']=='a.nested.root')
        event['element_offset'][0]+=epsilon
        with self.assertRaisesRegex(ValueError,'logical offset'):v.verify_observations(raw,inputs)

    def test_rejects_unqualified_inputs(self):
        for change in('mode','size','margin','flow','priority','extra','nonfinite'):
            inputs=corpus();case=inputs['cases'][0]
            if change=='mode':case['layers'][0]['nested_mode']='Window'
            if change=='size':case['nested_size'][0]=40.25
            if change=='margin':case['margin']=7
            if change=='flow':case['reference_size'][1]=0
            if change=='priority':case['layers'][0]['priority']=True
            if change=='extra':case['offset']=[1,1]
            if change=='nonfinite':case['layers'][0]['position'][0]=float('nan')
            with self.subTest(change=change),self.assertRaises(ValueError):v.validate_scenarios(inputs)

    def test_observer_keeps_fitting_and_rounding_in_upstream_only(self):
        source=(ROOT/'adapters/nested_deferred_fitting_rust/src/main.rs').read_text()
        for forbidden in('sort_by','.sort(','.round(','.ceil(','.floor(','pixel_snap(','derived_','simulate_click','on_mouse','.cached('):self.assertNotIn(forbidden,source)
        for required in('self.inner.request_layout','prepaint_end','paint_end','window.element_offset()','window.content_mask()','ordinary.reference','.block()','reference_height','AnchoredPositionMode::Window','.snap_to_window_with_margin(px(margin))'):self.assertIn(required,source)
        self.assertNotIn('element_offset()',source[source.index('    fn paint('):source.index('fn observed')])
        runner=(ROOT/'diagnostics/nested_deferred_fitting/run.py').read_text();self.assertIn('DISK_FLOOR = 1024**3 + 32 * 1024**2',runner)

    def test_manifest_integrity_and_non_source_bound_label(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "_build/evidence"; out.mkdir(parents=True)
            synthetic_bundle(out); report = v.verify_bundle(out)
            self.assertFalse(report["source_bound"])
            self.assertIn("authenticity unqualified", report["inspection_scope"])
            (out / "raw.stdout").write_bytes(b"corruption")
            with self.assertRaisesRegex(ValueError, "changed evidence"): v.verify_bundle(out)

    def test_complete_passing_bundle_result_json_save_load_recompute_equality(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "_build/evidence"; out.mkdir(parents=True)
            synthetic_bundle(out)
            original = v.verify_bundle(out)
            # No tuple/list coercion, projection filtering, or semantic-only comparison.
            path = out / "verification.json"
            path.write_text(json.dumps(original, indent=2, allow_nan=False) + "\n")
            loaded = v.load_json(path)
            self.assertEqual(original, loaded)
            self.assertEqual(original, v.verify_bundle(out))
            self.assertEqual(loaded, v.verify_bundle(out))
            self.assertEqual(original["observed_frame_count"], 64)
            self.assertEqual(original["case_count"], 8)
            for case in loaded["cases"]:
                for operation in case["operations"]:
                    for frame in operation["frames"]:
                        self.assertEqual(len(frame["observed_paintable_box_projection"]), 13)

    def test_complete_failing_bundle_result_json_save_load_recompute_equality(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "_build/evidence"; out.mkdir(parents=True)
            manifest = synthetic_bundle(out)
            raw = v.load_json(out / "raw.json")
            case = next(case for case in raw["cases"] if case["id"] == "signed-half-composed")
            for entry in case["events"]:
                event = entry["event"]
                if entry["operation"] == "scale1.25" and event.get("node") == "a.nested.root" and "element_offset" in event:
                    event["element_offset"] = [2, -2]
            encoded = json.dumps(raw, allow_nan=False).encode()
            for relative in ("raw.json", "raw.stdout"):
                (out / relative).write_bytes(encoded)
                manifest["files"][relative] = {"sha256": v.digest(out / relative), "size": len(encoded)}
            (out / "manifest.json").write_text(json.dumps(manifest, allow_nan=False))
            self.assertEqual(raw, v.load_json(out / "raw.json"))

            def failure_result():
                try:
                    v.verify_bundle(out)
                except ValueError as caught:
                    # The runner's complete retained verification-failure.json shape.
                    return {"type": type(caught).__name__, "error": str(caught)}
                self.fail("intentionally corrupted synthetic transcript was accepted")

            original = failure_result()
            self.assertEqual(original["type"], "ValueError")
            self.assertIn("logical offset", original["error"])
            path = out / "verification-failure.json"
            path.write_text(json.dumps(original, indent=2, allow_nan=False) + "\n")
            loaded = v.load_json(path)
            self.assertEqual(original, loaded)
            self.assertEqual(original, failure_result())
            self.assertEqual(loaded, failure_result())

    def test_rejects_rehashed_original_stdout_token_commands_and_budget(self):
        for mutation in ("stdout", "token", "command", "build", "budget", "physical-budget", "logical-rule", "device-rule", "composition-rule", "lock", "toolchain", "floor"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                out = Path(temp) / "_build/evidence"; out.mkdir(parents=True); manifest = synthetic_bundle(out)
                changed = None
                if mutation == "stdout": changed = "raw.stdout"; (out / changed).write_bytes(b"{}");
                if mutation == "token": manifest["run_token"] = "different-run-token-0000"
                if mutation == "command": manifest["execution"]["command"][0] = "/other/probe"
                if mutation == "build": manifest["build"]["command"].remove("--locked")
                if mutation == "budget":
                    changed = v.retained_path("diagnostics/nested_deferred_fitting/profile.json")
                    profile = v.load_json(out / changed); profile["geometry_allowance_logical_px"] = 1
                    (out / changed).write_text(json.dumps(profile))
                if mutation in ("physical-budget", "logical-rule", "device-rule", "composition-rule"):
                    changed = v.retained_path("diagnostics/nested_deferred_fitting/profile.json")
                    profile = v.load_json(out / changed)
                    if mutation == "physical-budget": profile["physical_grid_allowance_px"] = 1
                    else: profile["rounding_contract"][{"logical-rule":"logical","device-rule":"device","composition-rule":"composition"}[mutation]] = "forged rule"
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
            relative = "adapters/nested_deferred_fitting_rust/src/main.rs"; path = out / v.retained_path(relative)
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
        spec = importlib.util.spec_from_file_location("nested_deferred_fitting_run", ROOT / "diagnostics/nested_deferred_fitting/run.py")
        runner = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"verify": v}): spec.loader.exec_module(runner)
        for failure in ("build", "raw"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary)/"suite"; upstream=Path(temporary)/"upstream"
                profile=v.load_json(ROOT/"diagnostics/nested_deferred_fitting/profile.json")
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
                        binary=Path(environment["CARGO_TARGET_DIR"])/"debug/gpui-nested-deferred-fitting-diagnostic"
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

    def test_source_scope_excludes_any_baseline_or_unowned_change(self):
        allowed = "\n".join("A\t" + name for name in v.RETAIN)
        with patch.object(v.subprocess, "check_output", side_effect=[v.SUITE_BASE_TREE + "\n", allowed]):
            v.validate_baseline_source(ROOT, "a" * 40)
        for changed in (allowed + "\nM\tdiagnostics/deferred_priority/verify.py", allowed + "\nA\tnew-unowned.py", allowed.replace("A\t" + v.RETAIN[0], "M\t" + v.RETAIN[0]), ""):
            with self.subTest(changed=changed), patch.object(v.subprocess, "check_output", side_effect=[v.SUITE_BASE_TREE, changed]), self.assertRaises(ValueError):
                v.validate_baseline_source(ROOT, "a" * 40)
        with patch.object(v.subprocess, "check_output", return_value="0" * 40), self.assertRaisesRegex(ValueError, "base tree"):
            v.validate_baseline_source(ROOT, "a" * 40)


if __name__ == "__main__": unittest.main()
