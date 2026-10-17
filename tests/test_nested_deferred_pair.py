"""Synthetic checker tests only. No actual engine execution or parity claim."""
import copy
import ast
import inspect
import importlib.util
import json
import os
import subprocess
import shutil
import re
from pathlib import Path
import shlex
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
PAIR=ROOT/'diagnostics/nested_deferred_pair'
def load_module(name,path,imports=None):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules,imports or {}):spec.loader.exec_module(module)
    return module
compare=load_module('nested_pair_compare_tests',PAIR/'compare.py')
runner=load_module('nested_pair_runner_tests',PAIR/'run.py',{'compare':compare})
verifier=load_module('nested_pair_verify_tests',PAIR/'verify.py',{'compare':compare,'run':runner})
mutants=load_module('nested_pair_mutants_tests',PAIR/'run_mutants.py',{'compare':compare,'run':runner,'verify':verifier})
helper=load_module('nested_pair_synthetic_oracle',ROOT/'tests/test_nested_deferred_diagnostic.py')

def renumber(raw):
    for case in raw['cases']:
        for i,e in enumerate(case['events']):e['sequence']=i

def synthetic_pair(family=None):
    rust,corpus=helper.single(family) if family else helper.synthetic_trace()
    # The approved actual observer records two base frames. Add the same authored
    # synthetic frame twice only in this checker fixture, never production output.
    for case in rust['cases']:
        events=case['events'];base=[e for e in events if e['operation']=='base'];index=events.index(base[-1])
        copied=copy.deepcopy(base[1:-1]);frame=base[-1]['frame']
        for e in events[index:]:e['frame']+=1
        for e in copied:e['frame']=frame+1
        events[index:index]=copied
    renumber(rust)
    candidates=[]
    for case,original in zip(corpus['cases'],rust['cases']):
        events=[];frame=0
        for operation,action,stage,scale in compare.baseline.operation_plan(case):
            def emit(e):events.append({'sequence':len(events),'operation':operation,'frame':frame,'event':copy.deepcopy(e)})
            emit({'type':'operation_start','input':action});frame+=1
            emit({'type':'frame_start','scale_factor':scale,'window_size':case['window']})
            for kind in ('request_start','request_end','prepaint_start'):emit({'type':kind})
            emit({'type':'prepaint_end','overflow':True})
            raw_bounds={e['event']['node']:e['event']['bounds'] for e in original['events'] if e['operation']==operation and e['event']['type']=='prepaint'}
            nodes={}
            for name,node in compare.topology(case,stage).items():
                e={'type':'node','node':name,**node,'bounds':raw_bounds.get(name,[0,0,0,0]),'pointer_events':False,'focusable':False}
                nodes[name]=e;emit(e)
            family=case['id'].split('-scale')[0]
            groups=helper.ORDERS[family][{'updated':1,'removed':2}.get(stage,0)][2].split()
            order=['ordinary.before','ordinary.after']+[p+'.'+s for p in groups for s in (('root',) if p.endswith('.nested') else ('root','before','after'))]
            emit({'type':'scene','kind':'clip_push','node':'$host','id':nodes['$host']['id'],'bounds':[0,0,*case['window']]})
            for name in order:emit({'type':'scene','kind':'quad','node':name,'id':nodes[name]['id'],'bounds':nodes[name]['bounds']})
            emit({'type':'scene','kind':'clip_pop','node':'$host','id':nodes['$host']['id'],'bounds':None})
            emit({'type':'frame_end','scale_factor':scale,'window_size':case['window']})
            emit({'type':'operation_end','scale_factor':scale})
        candidates.append({'id':case['id'],'events':events})
    return rust,{'schema_version':1,'layer':compare.CANDIDATE_LAYER,'fixture':'font-free-two-level-nested-deferred','input':copy.deepcopy(corpus),'run_token':'synthetic-checker-only-0001','cases':candidates},corpus

def entries(raw,kind=None,operation=None):
    return [e for e in raw['cases'][0]['events'] if (kind is None or e['event']['type']==kind) and (operation is None or e['operation']==operation)]

class SyntheticNestedPairTests(unittest.TestCase):
    def setUp(self):self.rust,self.raw,self.inputs=synthetic_pair('increasing')
    def test_full_fixture_and_explicit_nonparity(self):
        rust,raw,inputs=synthetic_pair();r=compare.compare_observations(rust,raw,inputs)
        self.assertTrue(r['passed']);self.assertEqual(r['counts'],{'cases':8,'rust_frames':56,'candidate_frames':48,'compared_operations':48,'compared_frame_pairs':56})
        for k in ('input_parity_established','lifecycle_callback_parity_established','redraw_count_parity_established'):self.assertFalse(r[k])
    def test_source_policy_and_actual_projection_frozen_before_candidate(self):
        p=compare.policy();self.assertEqual(p['geometry_allowance_logical_px'],0);self.assertEqual(p['physical_grid_allowance_px'],0)
        self.assertEqual(p['approved_actual_rust_review_sha256'],'9e119d29b94ae2d92751138fa4232732275761f37a8cabd8f0dfcb032a80b748')
        frozen=compare.load_json((PAIR/'actual-rust-projection.json').read_text());self.assertEqual(sum(len(c['frames']) for c in frozen['cases']),56)
        self.assertEqual(frozen['candidate_ids']['a.nested.root'],'16')
    def test_order_is_semantic_mismatch(self):
        q=[e for e in entries(self.raw,'scene','initial') if e['event']['kind']=='quad'];q[2]['event'],q[5]['event']=q[5]['event'],q[2]['event']
        result=compare.compare_observations(self.rust,self.raw,self.inputs);self.assertFalse(result['passed']);self.assertEqual(result['mismatches'][0]['field'],'paint_order')
    def test_each_box_geometry_compared_exactly(self):
        for name in compare.box_names(self.inputs['cases'][0],'base'):
            raw=copy.deepcopy(self.raw)
            for e in entries(raw,operation='initial'):
                if e['event'].get('node')==name and (e['event']['type']=='node' or e['event'].get('kind')=='quad'):e['event']['bounds'][0]+=4
            result=compare.compare_observations(self.rust,raw,self.inputs)
            with self.subTest(node=name):self.assertIn('bounds/'+name,[m['field'] for m in result['mismatches']])
    def test_subgrid_epsilon_rejected_not_tolerated(self):
        entries(self.raw,'node','initial')[0]['event']['bounds'][0]+=2**-12
        with self.assertRaisesRegex(ValueError,'exact physical grid'):compare.verify_candidate(self.raw,self.inputs)
    def test_all_frame_structure_and_ids_retained(self):
        for op in ('initial','base','updated','removed','restored','moved'):
            for field,value in [('id','9999'),('parent','wrong'),('bounds',[float('nan'),0,0,0]),('pointer_events',True)]:
                raw=copy.deepcopy(self.raw);entries(raw,'node',op)[0]['event'][field]=value
                with self.subTest(op=op,field=field),self.assertRaises(ValueError):compare.verify_candidate(raw,self.inputs)
    def test_scene_id_bounds_balance_and_box_domain(self):
        for field,value in [('id','999'),('bounds',[1,2,3,4]),('node','$attachments')]:
            raw=copy.deepcopy(self.raw);q=next(e['event'] for e in entries(raw,'scene','initial') if e['event']['kind']=='quad');q[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):compare.verify_candidate(raw,self.inputs)
        entries(self.raw,'scene','initial')[-1]['event']['node']='a.anchor'
        with self.assertRaises(ValueError):compare.verify_candidate(self.raw,self.inputs)
    def test_every_earlier_candidate_frame_compared(self):
        events=self.raw['cases'][0]['events'];base=[e for e in events if e['operation']=='base'];i=events.index(base[-1]);frame=base[-1]['frame'];copyframe=copy.deepcopy(base[1:-1])
        for e in events[i:]:e['frame']+=1
        for e in copyframe:e['frame']=frame+1
        events[i:i]=copyframe;renumber(self.raw)
        self.assertTrue(compare.compare_observations(self.rust,self.raw,self.inputs)['passed'])
        for e in base:
            if e['event'].get('node')=='a.nested.root' and (e['event']['type']=='node' or e['event'].get('kind')=='quad'):e['event']['bounds'][0]+=4
        self.assertFalse(compare.compare_observations(self.rust,self.raw,self.inputs)['passed'])
    def test_both_actual_base_frames_are_retained_and_exact(self):
        verified=compare.baseline.verify_observations(self.rust,self.inputs);self.assertEqual(len(verified['cases'][0]['operations'][1]['frames']),2)
        for e in self.rust['cases'][0]['events']:
            if e['frame']==2 and e['event']['type'] in ('prepaint','prepaint_end','paint','paint_end') and e['event']['node']=='a.nested.root':e['event']['bounds'][0]+=2**-12
        with self.assertRaisesRegex(ValueError,'fresh actual Rust'):compare.compare_observations(self.rust,self.raw,self.inputs)
    def test_missing_observed_mask_is_null_and_semantic_mismatch(self):
        e=self.raw['cases'][0]['events'];e[:]=[x for x in e if x['event'].get('kind') not in ('clip_push','clip_pop')];renumber(self.raw)
        r=compare.compare_observations(self.rust,self.raw,self.inputs);self.assertFalse(r['passed']);self.assertIn('effective_mask/a.nested.root',[m['field'] for m in r['mismatches']])
    def test_actual_clip_intersection_and_no_clipping_claim(self):
        q=entries(self.raw,'scene','initial');q[0]['event']['bounds']=[0,0,316,240]
        r=compare.compare_observations(self.rust,self.raw,self.inputs);self.assertFalse(r['passed'])
        self.assertIn('nontrivial nested clipping',compare.policy()['scope_exclusions'])
    def test_bootstrap_scale_not_reused_from_configured_scale(self):
        for e in entries(self.raw,operation='initial'):
            if 'scale_factor' in e['event']:e['event']['scale_factor']=1
        with self.assertRaises(ValueError):compare.compare_observations(self.rust,self.raw,self.inputs)
    def test_transport_input_session_and_duplicate_keys(self):
        with self.assertRaises(ValueError):compare.decode_transport(self.raw,'wrong-token-0000000000',self.inputs)
        with self.assertRaises(ValueError):compare.load_json('{"x":1,"x":2}')
        self.raw['input']['cases'][0]['window'][0]=123
        with self.assertRaises(ValueError):compare.decode_transport(self.raw,self.raw['run_token'],self.inputs)
    def test_no_fabricated_lifecycle_or_input_events(self):
        entries(self.raw,'node','base')[0]['event']['lifecycle_callback']='paint'
        with self.assertRaises(ValueError):compare.verify_candidate(self.raw,self.inputs)
    def test_removal_restore_stable_ids_and_movement(self):
        verified=compare.verify_candidate(self.raw,self.inputs)[0]['operations'];removed=verified[3]['frames'][0]['nodes'];restored=verified[4]['frames'][0]['nodes'];moved=verified[5]['frames'][0]['nodes']
        self.assertNotIn('a.nested.root',removed);self.assertEqual(restored['a.nested.root']['id'],moved['a.nested.root']['id']);self.assertEqual(restored['a.nested.root']['bounds'],[80,68,40,32]);self.assertEqual(moved['a.nested.root']['bounds'],[96,80,40,32])
    def test_all_frozen_sources_and_public_pins_unchanged(self):
        p=compare.load_json((PAIR/'profile.json').read_text())
        for name,sha in p['approved_fixture_sha256'].items():
            with self.subTest(name=name):self.assertEqual(compare.baseline.digest(ROOT/name),sha)
        self.assertIn(p['candidate_pin_status'],('pending-independent-core-review-and-publication','published-exact-commit-tree'))
    def test_adapter_uses_genuine_layout_and_command_apis(self):
        s=(ROOT/'adapters/nested_deferred_moonbit/main.mbt').read_text()
        for token in ('request_layout_with_device_scale','requested.prepaint()','frame.tree().nodes()','frame.paint().commands()','command.id()','@element.Local'):
            self.assertIn(token,s)
        self.assertNotIn('derive_schedule',s);self.assertNotIn('.sort(',s)
    def test_three_exact_predeclared_production_controls(self):
        descriptors=compare.mutation_descriptors()
        self.assertEqual([d['name'] for d in descriptors],['structural-dfs-ties','parent-contiguous-scheduling','lost-outer-local-offset'])
        self.assertEqual([d['path'] for d in descriptors],['element/deferred.mbt','element/deferred.mbt','element/anchored.mbt'])
        self.assertTrue(all(d['old']!=d['new'] and len(d['required_witnesses'])==2 for d in descriptors))
        self.assertEqual(descriptors[2]['old'],'let absolute = match inherited.translated(relative)')
        self.assertEqual(descriptors[2]['new'],'let absolute = match zero.translated(relative)')
    def test_all_four_regressions_gate_controls(self):
        for file in ('run_mutants.py','verify_mutants.py'):
            s=(PAIR/file).read_text();self.assertIn("['regressions']['passed']",s);self.assertIn("['margin_regression']['passed']",s);self.assertIn("['flat_regression']['passed']",s)
    def test_controls_require_success_and_all_semantic_witnesses(self):
        desc=compare.load_json((PAIR/'control-policy.json').read_text())[0];ok={'returncode':0,'timed_out':False};bad={'returncode':1,'timed_out':False}
        match={'passed':False,'mismatches':copy.deepcopy(desc['required_witnesses'])}
        self.assertEqual(mutants.classify(ok,ok,match,descriptor=desc),'executed-paired-nested-deferred-rejection')
        for kwargs in ({'build':bad,'execution':ok},{'build':ok,'execution':bad},{'build':ok,'execution':ok,'transport_error':'bad'}, {'build':ok,'execution':ok,'validation_error':'bad'}):
            self.assertNotEqual(mutants.classify(comparison=match,descriptor=desc,**kwargs),'executed-paired-nested-deferred-rejection')
        match['mismatches'].pop();self.assertNotEqual(mutants.classify(ok,ok,match,descriptor=desc),'executed-paired-nested-deferred-rejection')

class ResourceAndRegressionGuards(unittest.TestCase):
    def test_strict_reserved_capacity_and_snapshot(self):
        with patch.object(runner,'capacity_snapshot',return_value={'/tmp':runner.DISK_FLOOR+runner.PROCESS_RESERVE}):
            with self.assertRaises(ValueError):runner.require_capacity(Path('/tmp'))
        with patch.object(runner,'capacity_snapshot',return_value={'/tmp':runner.DISK_FLOOR+runner.PROCESS_RESERVE+1}):
            self.assertEqual(runner.require_capacity(Path('/tmp'))['/tmp'],runner.DISK_FLOOR+runner.PROCESS_RESERVE+1)
    def test_rehashed_resource_guard_must_remain_above_floor(self):
        n=runner.DISK_FLOOR+runner.PROCESS_RESERVE+1
        record={'resource_floor_stop':False,'resource_guard':{'strict_floor_bytes':runner.DISK_FLOOR,'process_reserve_bytes':runner.PROCESS_RESERVE,
            'before_free_bytes':{'/tmp':n},'minimum_observed_free_bytes':{'/tmp':n-1},'after_free_bytes':{'/tmp':n}}}
        runner.verify_process_guard(record)
        for changed in ('stop','floor','minimum'):
            r=copy.deepcopy(record)
            if changed=='stop':r['resource_floor_stop']=True
            elif changed=='floor':r['resource_guard']['strict_floor_bytes']=0
            else:r['resource_guard']['minimum_observed_free_bytes']['/tmp']=runner.DISK_FLOOR
            with self.subTest(changed=changed),self.assertRaises(ValueError):runner.verify_process_guard(r)
    def test_resource_stops_are_not_semantic_kills(self):
        desc=compare.load_json((PAIR/'control-policy.json').read_text())[0];match={'passed':False,'mismatches':desc['required_witnesses']}
        good={'returncode':0,'timed_out':False};stopped={**good,'resource_floor_stop':True}
        for build,execution in ((stopped,good),(good,stopped)):
            self.assertNotEqual(mutants.classify(build,execution,match,descriptor=desc),'executed-paired-nested-deferred-rejection')
    def test_policy_control_and_public_pin_fail_before_execution(self):
        with patch.object(compare.baseline,'digest',return_value='0'*64):
            with self.assertRaisesRegex(ValueError,'pre-candidate comparison'):compare.policy()
            with self.assertRaisesRegex(ValueError,'pre-candidate control'):compare.mutation_descriptors()
        args=['run.py','--core-source','/tmp/nonexistent-core','--core-commit','0'*40,
            '--baseline','/tmp/no-baseline','--regression-baseline','/tmp/no-original',
            '--margin-baseline','/tmp/no-margin','--flat-baseline','/tmp/no-flat',
            '--baseline-suite-commit','1'*40,'--upstream-source','/tmp/no-upstream','--output',str(ROOT/'_build/no-execution')]
        with patch.object(sys,'argv',args),patch.object(runner,'mutation_descriptors',return_value=[]),\
             patch.object(runner,'validate_baseline',return_value={'source_bound':True}),\
             patch.object(runner,'identity',return_value={'commit':'1'*40,'tree':'2'*40,'clean':True}),\
             patch.object(runner,'execute') as execute:
            with self.assertRaisesRegex(ValueError,'candidate public commit/tree pin'):runner.main()
            execute.assert_not_called()
    def test_flat_regression_uses_frozen_comparator_without_old_public_pin(self):
        module=load_module('nested_flat_regression_modules',PAIR/'regressions.py')
        with module.flat_modules() as old:
            self.assertEqual(old.compare.LAYER,'supplemental-flat-deferred-priority-native-pair')
            self.assertEqual(old.native.LAYER,compare.LAYER)
            self.assertIn('nested_deferred_pair',str(old.native.__file__))
            self.assertIn('deferred_priority_pair',str(old.compare.__file__))
        with self.assertRaises(ValueError):module._flat_counts({'passed':True,'counts':{'cases':15,'compared_operations':144}})


class SelectedProductionSourceTests(unittest.TestCase):
    """Synthetic noncompiled filesystem/Git binding tests."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.core = Path(self.temp.name) / 'core'
        self.core.mkdir()
        self.blobs = {'moon.mod': b'synthetic module', 'element/pkg.generated.mbti': b'synthetic API context'}
        for package in runner.PACKAGES:
            self.blobs[package + '/moon.pkg'] = b''
            self.blobs[package + '/' + package + '.mbt'] = b'// synthetic production source'
        for name in ('container_query', 'layout_bounds', 'deferred'):
            self.blobs['element/' + name + '.mbt'] = b'// synthetic priority metadata source'
        for relative, value in self.blobs.items():
            path = self.core / relative; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(value)
        self.paths = sorted(p for p in self.blobs if runner.production_file(p))
        self.git = patch.object(runner, 'command', return_value='\n'.join(sorted(self.blobs)))
        self.git.start(); self.addCleanup(self.git.stop)
        self.blob = patch.object(runner.subprocess, 'check_output', side_effect=lambda args, **kw: self.blobs[args[-1].split(':', 1)[1]])
        self.blob.start(); self.addCleanup(self.blob.stop)

    def test_complete_dynamic_production_and_api_context(self):
        self.assertEqual(runner.source_preflight(self.core, 'a' * 40), self.paths)
        self.assertIn('element/container_query.mbt', self.paths)
        self.assertIn('element/layout_bounds.mbt', self.paths)
        self.assertNotIn('element/pkg.generated.mbti', self.paths)
        self.assertEqual(runner.CORE_API_FILES, ('element/pkg.generated.mbti',))

    def test_extra_missing_alternate_and_duplicate_sources_fail_preflight(self):
        extra = self.core / 'element/ignored-extra.mbt'; extra.write_text('// extra ignored source')
        with self.assertRaisesRegex(ValueError, 'source inventory'): runner.source_preflight(self.core, 'a' * 40)
        extra.unlink()
        path = self.core / 'element/container_query.mbt'; original = path.read_bytes(); path.unlink()
        with self.assertRaisesRegex(ValueError, 'source inventory'): runner.source_preflight(self.core, 'a' * 40)
        path.write_bytes(original + b'\n// alternate source')
        with self.assertRaisesRegex(ValueError, 'preexecution core Git blob'): runner.source_preflight(self.core, 'a' * 40)
        path.write_bytes(original)
        with patch.object(runner, 'command', return_value='\n'.join(sorted(self.blobs) + ['element/deferred.mbt'])):
            with self.assertRaisesRegex(ValueError, 'duplicate selected Git source'): runner.source_preflight(self.core, 'a' * 40)
        api = self.core / runner.CORE_API_FILES[0]; api.write_bytes(api.read_bytes() + b'\n// alternate API')
        with self.assertRaisesRegex(ValueError, 'preexecution core Git blob'): runner.source_preflight(self.core, 'a' * 40)

    def test_retained_api_rehashed_alternate_missing_extra_duplicate_reject(self):
        evidence = Path(self.temp.name) / 'evidence'; api = evidence / 'core-api'; target = api / runner.CORE_API_FILES[0]
        target.parent.mkdir(parents=True); target.write_bytes(self.blobs[runner.CORE_API_FILES[0]])
        manifest = {'core_api_context': {'role': 'noncompiled-published-api-context', 'files': list(runner.CORE_API_FILES)}}
        runner.verify_core_api(evidence, manifest, self.core, 'a' * 40)
        target.write_bytes(target.read_bytes() + b'\n// rehashed alternate bytes')
        with self.assertRaisesRegex(ValueError, 'core API Git blob'): runner.verify_core_api(evidence, manifest, self.core, 'a' * 40)
        target.unlink()
        with self.assertRaisesRegex(ValueError, 'complete retained API'): runner.verify_core_api(evidence, manifest, self.core, 'a' * 40)
        target.write_bytes(self.blobs[runner.CORE_API_FILES[0]])
        extra = api / 'extra.mbti'; extra.write_text('extra')
        with self.assertRaisesRegex(ValueError, 'complete retained API'): runner.verify_core_api(evidence, manifest, self.core, 'a' * 40)
        extra.unlink(); manifest['core_api_context']['files'].append(runner.CORE_API_FILES[0])
        with self.assertRaisesRegex(ValueError, 'core API context inventory'): runner.verify_core_api(evidence, manifest, self.core, 'a' * 40)


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





class ExactOraclePairLineageTests(unittest.TestCase):
    """Real Git-object preflights only; no compiler or oracle execution."""
    def setUp(self):
        self.pair_commit = runner.command(['git', 'rev-parse', 'HEAD'], ROOT)
        self.profile = compare.load_json((PAIR/'profile.json').read_text())
        self.oracle = self.profile['suite_base_public_commit']
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        subprocess.check_call(['git', 'init', '-q', str(self.repo)])
        self.environment = dict(os.environ, GIT_AUTHOR_NAME='Source lineage test', GIT_AUTHOR_EMAIL='lineage@example.invalid',
                                GIT_COMMITTER_NAME='Source lineage test', GIT_COMMITTER_EMAIL='lineage@example.invalid')

    def use_shared_objects(self):
        common = Path(runner.command(['git', 'rev-parse', '--git-common-dir'], ROOT))
        common = common if common.is_absolute() else ROOT/common
        (self.repo/'.git/objects/info/alternates').write_text(str(common.resolve()/'objects')+'\n')

    def git(self, *args, data=None):
        return subprocess.check_output(['git', *args], cwd=self.repo, input=data, env=self.environment).decode().strip()

    def changed_pair(self, relative=None, mode='100644', remove=False, unrelated=False):
        self.use_shared_objects()
        self.git('read-tree', self.pair_commit)
        if relative:
            if remove:
                self.git('update-index', '--force-remove', relative)
            else:
                oid = self.git('hash-object', '-w', '--stdin', data=b'synthetic source-lineage negative only\n')
                self.git('update-index', '--add', '--cacheinfo', mode+','+oid+','+relative)
        tree = self.git('write-tree')
        return self.git('commit-tree', tree, *([] if unrelated else ['-p', self.pair_commit]), data=b'isolated nonexecuted lineage fixture\n')

    def lineage(self, source=None, commit=None, oracle_source=None, oracle_commit=None):
        return runner.validate_source_lineage(source or ROOT, commit or self.pair_commit,
                                              oracle_source or ROOT, oracle_commit or self.oracle)

    def test_actual_pair_head_and_exact_oracle_objects_pass(self):
        result = self.lineage()
        self.assertEqual(result['oracle_suite'], {'commit':self.oracle,'tree':self.profile['suite_base_tree']})
        self.assertEqual(result['pair_suite']['commit'], self.pair_commit)
        self.assertEqual(len(result['baseline_entries']),674)
        self.assertEqual(set(result['pair_additions']),set(runner.NEW_SUITE_FILES))
        # Preserve the original failed boundary: the frozen oracle still rejects
        # pair HEAD and accepts only its separately selected original source.
        compare.baseline.validate_baseline_source(ROOT,self.oracle)
        with self.assertRaisesRegex(ValueError,'changed baseline or non-owned'):
            compare.baseline.validate_baseline_source(ROOT,self.pair_commit)

    def test_real_descendant_pair_preserves_all_oracle_entries(self):
        commit=self.changed_pair('diagnostics/nested_deferred_pair/README.md')
        self.assertEqual(self.lineage(self.repo,commit)['pair_suite']['commit'],commit)

    def test_alternate_or_same_suite_identity_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'exact pinned oracle'):
            self.lineage(oracle_commit=compare.baseline.SUITE_BASE)
        with self.assertRaisesRegex(ValueError,'distinct pair and oracle'):
            self.lineage(commit=self.oracle)
        with self.assertRaisesRegex(ValueError,'exact selected suite'):
            self.lineage(commit='HEAD')

    def test_changed_or_deleted_baseline_blob_is_rejected(self):
        for remove in (False,True):
            with self.subTest(remove=remove):
                commit=self.changed_pair('diagnostics/nested_deferred/scenarios.json',remove=remove)
                with self.assertRaisesRegex(ValueError,'baseline Git source entry'):
                    self.lineage(self.repo,commit)

    def test_changed_baseline_mode_is_rejected(self):
        self.use_shared_objects();self.git('read-tree',self.pair_commit)
        entry=runner.git_tree_entries(ROOT,self.oracle)['diagnostics/nested_deferred/scenarios.json']
        self.git('update-index','--cacheinfo','100755,'+entry['oid']+',diagnostics/nested_deferred/scenarios.json')
        commit=self.git('commit-tree',self.git('write-tree'),'-p',self.pair_commit,data=b'mode-only fixture\n')
        with self.assertRaisesRegex(ValueError,'baseline Git source entry'):self.lineage(self.repo,commit)

    def test_missing_or_extra_owned_addition_is_rejected(self):
        for path,remove in (('unrelated-new-file',False),('diagnostics/nested_deferred_pair/README.md',True)):
            with self.subTest(path=path):
                commit=self.changed_pair(path,remove=remove)
                with self.assertRaisesRegex(ValueError,'nineteen owned'):self.lineage(self.repo,commit)

    def test_pair_addition_mode_and_unrelated_history_rejected(self):
        commit=self.changed_pair('diagnostics/nested_deferred_pair/README.md',mode='100755')
        with self.assertRaisesRegex(ValueError,'regular nonexecutable'):self.lineage(self.repo,commit)
        commit=self.changed_pair(unrelated=True)
        with self.assertRaises(subprocess.CalledProcessError):self.lineage(self.repo,commit)

    def test_missing_actual_historical_objects_rejected(self):
        # Minimal source store has the exact selected commit/root-tree objects,
        # but genuinely lacks the e576 historical object needed by frozen code.
        for commit in (self.oracle,self.pair_commit):
            tree=runner.command(['git','rev-parse',commit+'^{tree}'],ROOT)
            for kind,oid in (('commit',commit),('tree',tree)):
                value=subprocess.check_output(['git','cat-file',kind,oid],cwd=ROOT)
                self.assertEqual(self.git('hash-object','-w','-t',kind,'--stdin',data=value),oid)
        with self.assertRaises(subprocess.CalledProcessError):
            self.lineage(oracle_source=self.repo)

    def test_missing_source_objects_and_wrong_tree_rejected(self):
        with self.assertRaises(subprocess.CalledProcessError):self.lineage(oracle_source=self.repo)
        with patch.object(runner,'load_json',return_value=dict(self.profile,suite_base_tree='0'*40)):
            with self.assertRaisesRegex(ValueError,'oracle suite tree'):self.lineage()

    def test_all_regression_wrappers_reopen_distinct_lineage_before_builds(self):
        module=load_module('nested_lineage_regressions',PAIR/'regressions.py')
        lineage=self.lineage();parent={'suite':dict(lineage['pair_suite'],clean=True),'source_lineage':lineage,
                                    'recorded_execution_root':str(self.repo.resolve())}
        context={'pair_manifest':parent,'pair_suite_source':ROOT,'suite_source':ROOT,'suite_commit':self.oracle}
        with patch.dict(sys.modules,{'run':runner}):
            self.assertEqual(module._execution_lineage(parent,context),lineage)
            self.assertEqual(module._verification_lineage(parent,ROOT,self.pair_commit),self.oracle)
            for execute,scope in ((module.execute_regressions,'original_modules'),
                                  (module.execute_margin_regression,'margin_modules'),
                                  (module.execute_flat_regression,'flat_modules')):
                with self.subTest(execute=execute.__name__),patch.object(module,scope) as legacy:
                    bad=dict(context,suite_commit=self.pair_commit)
                    with self.assertRaisesRegex(ValueError,'exact pinned oracle'):
                        execute(self.repo,{},self.repo,bad)
                    legacy.assert_not_called()
            bad=copy.deepcopy(parent);bad['source_lineage']['pair_suite']['commit']='0'*40
            with self.assertRaisesRegex(ValueError,'parent source lineage differs'):
                module._execution_lineage(bad,context)
            with self.assertRaisesRegex(ValueError,'independently selected regression pair'):
                module._verification_lineage(parent,ROOT,self.oracle)

    def test_wrong_or_dirty_oracle_checkout_stops_runner_before_execution(self):
        args=['run.py','--core-source','/tmp/nonexistent-core','--core-commit',self.profile['candidate_commit'],
            '--baseline','/tmp/no-baseline','--regression-baseline','/tmp/no-original',
            '--margin-baseline','/tmp/no-margin','--flat-baseline','/tmp/no-flat',
            '--baseline-suite-commit',self.oracle,'--baseline-suite-source',str(self.repo),
            '--upstream-source','/tmp/no-upstream','--output',str(ROOT/'_build/no-execution')]
        core={'commit':self.profile['candidate_commit'],'tree':self.profile['candidate_tree'],'clean':True}
        pair={'commit':self.pair_commit,'tree':runner.command(['git','rev-parse','HEAD^{tree}'],ROOT),'clean':True}
        for oracle in ({'commit':self.pair_commit,'tree':pair['tree'],'clean':True},
                       {'commit':self.oracle,'tree':self.profile['suite_base_tree'],'clean':False}):
            with self.subTest(oracle=oracle),patch.object(sys,'argv',args),\
                 patch.object(runner,'identity',side_effect=[core,pair,oracle]),\
                 patch.object(runner,'execute') as execute,patch.object(runner,'validate_baseline') as baseline_call:
                with self.assertRaisesRegex(ValueError,'exact clean oracle checkout'):runner.main()
                execute.assert_not_called();baseline_call.assert_not_called()

    def test_workflow_uses_full_history_isolated_oracle_for_all_four_observers(self):
        text=(ROOT/'.github/workflows/nested-deferred-native-pair.yml').read_text()
        self.assertEqual(text.count('fetch-depth: 0'),2)
        self.assertIn('ref: ${{ steps.pins.outputs.oracle }}',text)
        start=text.index('      - name: Compile and execute four unchanged actual Rust observers')
        end=text.index('      - name: Compile deferred pair',start)
        observer=text[start:end]
        self.assertIn('working-directory: oracle-suite',observer)
        for name in ('nested_deferred','anchor_margin','anchor','deferred_priority'):
            self.assertIn('python3 diagnostics/'+name+'/run.py',observer)
            self.assertIn('python3 diagnostics/'+name+'/verify.py',observer)
        self.assertIn('--baseline-suite-source ../oracle-suite',text[end:])
        self.assertIn("--baseline-suite-commit '${{ steps.pins.outputs.oracle }}'",text[end:])




class WorkflowLayoutIntegrationTests(unittest.TestCase):
    """Run unchanged source/path/inventory gates on synthetic, never executed bundles."""
    def test_all_four_frozen_preflights_at_actual_sibling_checkout_paths(self):
        upstream_origin=Path(os.environ.get('GPUI_LAYOUT_TEST_UPSTREAM_SOURCE', ROOT/'_build/upstream-source'))
        if not upstream_origin.is_dir():
            self.assertNotIn('GPUI_LAYOUT_TEST_UPSTREAM_SOURCE',os.environ,'Required CI layout source is missing')
            self.skipTest('Pinned upstream checkout required for source/path integration; dedicated CI supplies it')
        profile=compare.load_json((PAIR/'profile.json').read_text())
        self.assertEqual(runner.command(['git','rev-parse',profile['upstream_commit']+'^{tree}'],upstream_origin),profile['upstream_tree'])
        self.assertGreater(shutil.disk_usage(tempfile.gettempdir()).free,runner.DISK_FLOOR+64*1024**2)
        with tempfile.TemporaryDirectory(prefix='nested-pair-layout-') as temporary:
            workspace=Path(temporary).resolve();pair=workspace/'pair-suite';oracle=workspace/'oracle-suite'
            upstream=pair/'_build/upstream-source';core=pair/'_build/core-source'
            def sparse_checkout(origin,commit,destination,paths):
                destination.mkdir(parents=True,exist_ok=True)
                subprocess.check_call(['git','init','-q',str(destination)])
                common=Path(runner.command(['git','rev-parse','--git-common-dir'],origin))
                common=common if common.is_absolute() else origin/common
                (destination/'.git/objects/info/alternates').write_text(str(common.resolve()/'objects')+'\n')
                subprocess.check_call(['git','config','core.sparseCheckout','true'],cwd=destination)
                (destination/'.git/info/sparse-checkout').write_text(''.join('/'+p+'\n' for p in sorted(paths)))
                subprocess.check_call(['git','checkout','--detach','-q',commit],cwd=destination)
                self.assertTrue(runner.identity(destination)['clean'])
            head=runner.command(['git','rev-parse','HEAD'],ROOT)
            suite_paths=set(profile['approved_fixture_sha256'])|set(runner.NEW_SUITE_FILES)|{'.gitignore'}
            sparse_checkout(ROOT,head,pair,suite_paths)
            sparse_checkout(ROOT,profile['suite_base_public_commit'],oracle,suite_paths-set(runner.NEW_SUITE_FILES))
            helpers={name:load_module('layout_fixture_'+name,ROOT/('tests/test_'+name+'_diagnostic.py'))
                     for name in ('anchor','anchor_margin','deferred_priority','nested_deferred')}
            validators={name:getattr(h,'v',getattr(h,'verify',None)) for name,h in helpers.items()}
            upstream_paths=set().union(*(set(v.UPSTREAM_RETAIN) for v in validators.values()))
            sparse_checkout(upstream_origin,profile['upstream_commit'],upstream,upstream_paths)
            core.mkdir();(core/'source-path-placeholder').write_text('Layout only; no core build/source qualification.\n')
            lineage=runner.validate_source_lineage(pair,head,oracle,profile['suite_base_public_commit'])
            self.assertEqual(len(lineage['baseline_entries']),674)
            self.assertNotEqual(runner.identity(pair)['commit'],runner.identity(oracle)['commit'])
            class ObservationBoundaryReached(Exception):pass
            outcomes=[];peak_fixture_bytes=0
            labels={'anchor':'anchor-original-baseline','anchor_margin':'anchor-margin-baseline',
                    'deferred_priority':'flat-priority-baseline','nested_deferred':'nested-deferred-baseline'}
            for name,helper_module in helpers.items():
                validator=validators[name]
                body=ast.parse(inspect.getsource(validator.verify_bundle)).body[0].body
                boundary_index=next(i for i,node in enumerate(body) if isinstance(node,ast.Assign) and
                    isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Name) and node.value.func.id=='verify_observations')
                self.assertFalse(any(isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='require'
                    for statement in body[boundary_index+1:] for node in ast.walk(statement)), 'No provenance gate may follow observation sentinel')
                for old_layout in (False,True):
                    directory=(pair/'_build/oracle-suite/_build' if old_layout else oracle/'_build')/labels[name]
                    helper_module.synthetic_bundle(directory)
                    manifest=json.loads((directory/'manifest.json').read_text())
                    manifest['suite']=manifest['suite_after']=runner.identity(oracle)
                    manifest['upstream']=manifest['upstream_after']=runner.identity(upstream)
                    manifest['upstream_source_path']=str(upstream)
                    # Bind all real source/inventory gates. Anchor's synthetic
                    # fixture has a tiny corpus; the observation sentinel is
                    # after source/path gates, so retain the exact frozen corpus.
                    relative='diagnostics/'+name+'/scenarios.json'
                    for target in ('scenarios.json',validator.retained_path(relative)):
                        (directory/target).write_bytes((oracle/relative).read_bytes())
                    for relative in validator.UPSTREAM_RETAIN:
                        (directory/'upstream'/relative).write_bytes((upstream/relative).read_bytes())
                    cargo=directory/validator.retained_path('adapters/'+name+'_rust/Cargo.toml')
                    (directory/'build-Cargo.toml').write_text(cargo.read_text().replace('"../../../zed-source/crates/gpui"',json.dumps(str(upstream/'crates/gpui'))))
                    if (directory/'build-plan.json').exists():
                        plan=json.loads((directory/'build-plan.json').read_text())
                        plan['build_manifest_sha256']=validator.digest(directory/'build-Cargo.toml')
                        plan['input_sha256']=validator.digest(directory/'scenarios.json')
                        (directory/'build-plan.json').write_text(json.dumps(plan))
                    for relative in manifest['files']:
                        path=directory/relative;manifest['files'][relative]={'sha256':validator.digest(path),'size':path.stat().st_size}
                    (directory/'manifest.json').write_text(json.dumps(manifest))
                    args=(directory,profile['suite_base_public_commit'],profile['suite_base_tree'],oracle,upstream)
                    # Only final semantic observation is intercepted. The entire
                    # frozen source/history/inventory/command/path preflight runs.
                    with patch.object(validator,'verify_observations',side_effect=ObservationBoundaryReached) as boundary:
                        if old_layout:
                            with self.assertRaisesRegex(ValueError,'one ignored build root'):validator.verify_bundle(*args)
                            boundary.assert_not_called()
                            outcomes.append({'observer':name,'outcome':'old-double-build-rejected','recorded_execution_root':str(directory),'build_ancestors':2})
                        else:
                            with self.assertRaises(ObservationBoundaryReached):validator.verify_bundle(*args)
                            boundary.assert_called_once()
                            outcomes.append({'observer':name,'outcome':'reached observation boundary','recorded_execution_root':str(directory),'build_ancestors':1})
                    peak_fixture_bytes=max(peak_fixture_bytes,sum(p.stat().st_size for p in workspace.rglob('*') if p.is_file()))
                    self.assertLess(peak_fixture_bytes,32*1024**2)
                    if old_layout:
                        shutil.rmtree(directory) # only this test's regenerable negative fixture
            self.assertEqual(len(outcomes),8)
            self.assertTrue(runner.identity(pair)['clean']);self.assertTrue(runner.identity(oracle)['clean'])
            self.assertLess(sum(p.stat().st_size for p in workspace.rglob('*') if p.is_file()),32*1024**2)
            workflow_bindings=self._assert_workflow_paths(workspace,pair,oracle,upstream,core,labels)
            if os.environ.get('GPUI_LAYOUT_TEST_REPORT'):
                Path(os.environ['GPUI_LAYOUT_TEST_REPORT']).write_text(json.dumps({
                    'qualification':'synthetic source/path/inventory preflight only; no engine execution',
                    'outcomes':outcomes,'workflow_bindings':workflow_bindings,'source_lineage':lineage,'pair_clean':True,'oracle_clean':True,
                    'workspace':str(workspace),'peak_fixture_bytes':peak_fixture_bytes,'fixture_cleanup':'temporary regenerable fixtures removed after test',
                    'frozen_validator_sha256':{name:compare.baseline.digest(ROOT/('diagnostics/'+name+'/verify.py')) for name in helpers}},indent=2)+'\n')

    def _assert_workflow_paths(self,workspace,pair,oracle,upstream,core,labels):
        text=(ROOT/'.github/workflows/nested-deferred-native-pair.yml').read_text()
        self.assertIn('    defaults:\n      run:\n        working-directory: pair-suite\n',text)
        self.assertIn('          path: pair-suite\n',text);self.assertIn('          path: oracle-suite\n',text)
        for match in re.finditer(r'^          path: (.+)$',text,re.M):
            if match.group(1)=='|':continue
            target=workspace/match.group(1);self.assertTrue(target.resolve().is_relative_to(workspace));self.assertTrue(target.exists())
        self.assertNotIn('actions/cache',text) # no unexamined cache path/working-directory convention
        steps=re.split(r'^      - ',text,flags=re.M)[1:]
        bindings={};invocations=[];copy_paths=[];upload_paths=[]
        for step in steps:
            cwd=oracle if '        working-directory: oracle-suite' in step else pair
            if 'uses: actions/upload-artifact' in step:
                uploads=step.split('          path: |\n',1)[1].split('          include-hidden-files:',1)[0]
                expected={oracle/'_build'/v for v in labels.values()}|{pair/'_build'/v for v in
                    ('nested-deferred-pair-evidence','nested-deferred-mutants','nested-deferred-forensic-controls','nested-deferred-pair-logs')}
                actual={workspace/line.strip() for line in uploads.splitlines() if line.strip()}
                self.assertEqual(actual,expected);upload_paths=sorted(map(str,actual))
            if '        run: |' not in step:continue
            script=step.split('        run: |\n',1)[1]
            script=script.replace('\\\n',' ')
            script=script.replace('$GITHUB_WORKSPACE',str(workspace))
            script=re.sub(r'\$\{\{.*?\}\}', 'selected-exact-pin',script)
            script=script.replace('$(git rev-parse HEAD^{tree})','selected-tree').replace('$(git rev-parse HEAD)','selected-commit')
            for line in script.splitlines():
                line=line.strip()
                if line.startswith('cp -a '):
                    copied=shlex.split(line);source=(cwd/copied[2]).resolve();destination=(cwd/copied[3]).resolve()
                    expected_copy={'nested-deferred-pair-evidence':'nested-deferred-pair-copy','nested-deferred-mutants':'nested-deferred-mutants-copy'}
                    self.assertEqual(destination,source.parent/expected_copy[source.name]);self.assertTrue(source.is_relative_to(pair/'_build'))
                    self.assertEqual(sum(p.name=='_build' for p in destination.parents),1)
                    copy_paths.append({'cwd':str(cwd),'source':str(source),'destination':str(destination)})
                if not line.startswith('python3 diagnostics/'):continue
                argv=shlex.split(line);self.assertTrue((cwd/argv[1]).is_file(),argv[1])
                invocations.append({'cwd':str(cwd),'argv':argv})
                for flag in ('--core-source','--upstream-source','--baseline-suite-source','--suite-source',
                             '--baseline','--margin-baseline','--flat-baseline','--regression-baseline','--output','--evidence','--mutants'):
                    if flag not in argv:continue
                    target=(cwd/argv[argv.index(flag)+1]).resolve();bindings.setdefault(flag,set()).add(target)
                    if flag in ('--core-source','--upstream-source','--baseline-suite-source','--suite-source'):self.assertTrue(target.exists())
                    else:self.assertEqual(sum(p.name=='_build' for p in target.parents),1,str(target))
                if argv[1].endswith('/verify.py') and not argv[2].startswith('--'):
                    target=(cwd/argv[2]).resolve();self.assertEqual(sum(p.name=='_build' for p in target.parents),1)
                for token in argv:
                    if '/nested-deferred-pair-logs/' in token:self.assertTrue((cwd/Path(token)).resolve().is_relative_to(pair/'_build/nested-deferred-pair-logs'))
        self.assertEqual(bindings['--core-source'],{core});self.assertEqual(bindings['--upstream-source'],{upstream})
        self.assertEqual(bindings['--baseline-suite-source'],{oracle})
        self.assertEqual(bindings['--suite-source'],{pair,oracle})
        for flag,label in (('--baseline','nested-deferred-baseline'),('--margin-baseline','anchor-margin-baseline'),
                           ('--flat-baseline','flat-priority-baseline'),('--regression-baseline','anchor-original-baseline')):
            self.assertEqual(bindings[flag],{oracle/'_build'/label})
        expected_outputs={oracle/'_build'/v for v in labels.values()}|{pair/'_build'/v for v in
            ('nested-deferred-pair-evidence','nested-deferred-mutants','nested-deferred-forensic-controls')}
        self.assertEqual(bindings['--output'],expected_outputs)
        self.assertEqual(bindings['--mutants'],{pair/'_build/nested-deferred-mutants',pair/'_build/nested-deferred-mutants-copy'})
        self.assertEqual(bindings['--evidence'],{pair/'_build/nested-deferred-pair-evidence',pair/'_build/nested-deferred-pair-copy'})
        self.assertEqual(len(copy_paths),2)
        self.assertIn("Path('../oracle-suite')",text)
        return {'cli_paths':{key:sorted(map(str,values)) for key,values in bindings.items()},
                'invocations':invocations,'relocation_copies':copy_paths,'artifact_upload_paths':upload_paths,'cache_actions':[]}


if __name__ == "__main__": unittest.main()
