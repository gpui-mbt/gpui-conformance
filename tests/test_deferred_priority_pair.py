"""Synthetic checker tests only. No engine execution or actual pair claim."""
import copy
import importlib.util
import json
from pathlib import Path
import shlex
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
PAIR=ROOT/'diagnostics/deferred_priority_pair'

def load_module(name,path,imports=None):
    spec=importlib.util.spec_from_file_location(name,path); module=importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules,imports or {}): spec.loader.exec_module(module)
    return module

compare=load_module('deferred_pair_compare_tests',PAIR/'compare.py')
runner=load_module('deferred_pair_runner_tests',PAIR/'run.py',{'compare':compare})
verifier=load_module('deferred_pair_verify_tests',PAIR/'verify.py',{'compare':compare,'run':runner})
mutants=load_module('deferred_pair_mutants_tests',PAIR/'run_mutants.py',{'compare':compare,'run':runner,'verify':verifier})
helper=load_module('deferred_pair_synthetic_oracle',ROOT/'tests/test_deferred_priority_diagnostic.py')


def synthetic_pair(family=None):
    """Synthetic geometry copies the independent authored Rust test fixture."""
    rust,corpus=helper.single(family) if family else helper.synthetic_trace()
    candidates=[]
    for case,original in zip(corpus['cases'],rust['cases']):
        events=[]; frame=0; last_nodes=None; order=None
        for operation,action,stage,scale,is_input in compare.baseline.operation_plan(case):
            def emit(e): events.append({'sequence':len(events),'operation':operation,'frame':frame,'event':copy.deepcopy(e)})
            emit({'type':'operation_start','input':action})
            if not is_input:
                frame+=1; emit({'type':'frame_start','scale_factor':scale,'window_size':case['window']})
                for kind in ('request_start','request_end','prepaint_start'): emit({'type':kind})
                emit({'type':'prepaint_end','overflow':True})
                raw_bounds={e['event']['node']:e['event']['bounds'] for e in original['events'] if e['operation']==operation and e['event']['type']=='prepaint'}
                nodes={}
                for name,node in compare.topology(case,stage).items():
                    config=compare.baseline.interaction_for(case,name)
                    # Extra helper geometry has no Rust correspondence and no parity claim.
                    e={'type':'node','node':name,**node,'bounds':raw_bounds.get(name,[0,0,0,0]),'pointer_events':bool(config and config['listener']!='none'),'focusable':False}
                    nodes[name]=e;emit(e)
                order=['ordinary.before','ordinary.after']+[p+'.'+s for p in helper.ORDERS[case['id'].split('-scale')[0]][['base','updated','removed','restored'].index(stage)] for s in ('root','first','second')]
                emit({'type':'scene','kind':'clip_push','node':'$host','id':nodes['$host']['id'],'bounds':[0,0,*case['window']]})
                for name in order: emit({'type':'scene','kind':'quad','node':name,'id':nodes[name]['id'],'bounds':nodes[name]['bounds']})
                emit({'type':'scene','kind':'clip_pop','node':'$host','id':nodes['$host']['id'],'bounds':None})
                emit({'type':'frame_end','scale_factor':scale,'window_size':case['window']});last_nodes=nodes
            else:
                target=next(n for n in reversed(order) if last_nodes[n]['pointer_events']);bubble=[];node=target
                while node is not None: bubble.append(node);node=last_nodes[node]['parent']
                capture=list(reversed(bubble))
                for action_name in ('down','up'):
                    emit({'type':'route','action':action_name,'position':case['probe_position'],'hit_test':target,'target':target,'capture':capture,'bubble':bubble,'callback_capture':capture,'callback_bubble':bubble,
                          'callbacks':[{'node':n,'id':last_nodes[n]['id'],'phase':p} for p,path in [('capture',capture),('bubble',bubble)] for n in path]})
            emit({'type':'operation_end','scale_factor':scale})
        candidates.append({'id':case['id'],'events':events})
    return rust,{'schema_version':1,'layer':compare.CANDIDATE_LAYER,'fixture':'font-free-flat-deferred-priority','input':copy.deepcopy(corpus),'run_token':'synthetic-checker-only-0001','cases':candidates},corpus


def entries(raw,kind=None,operation=None):
    return [e for e in raw['cases'][0]['events'] if (kind is None or e['event']['type']==kind) and (operation is None or e['operation']==operation)]

def renumber(raw):
    for case in raw['cases']:
        for i,e in enumerate(case['events']): e['sequence']=i


class SyntheticDeferredPairTests(unittest.TestCase):
    def setUp(self): self.rust,self.raw,self.inputs=synthetic_pair('ascending')

    def test_full_fixture_and_explicit_nonparity(self):
        rust,raw,inputs=synthetic_pair(); result=compare.compare_observations(rust,raw,inputs)
        self.assertTrue(result['passed']);self.assertFalse(result['input_parity_established']);self.assertFalse(result['lifecycle_callback_parity_established'])
        self.assertEqual(result['counts'],{'cases':16,'rust_frames':80,'candidate_frames':80,'compared_operations':144,'rust_mouse_down_callbacks':484,'candidate_input_operations':64})
        self.assertEqual(len(result['cases']),16)
        op=result['cases'][0]['operations'][2]
        self.assertEqual(len(op['rust_actual_mouse_down_callbacks']),11)
        self.assertEqual(len(op['candidate_actual_routes']),2)
        self.assertFalse(op['input_parity_established'])

    def test_source_policy_frozen_before_candidate(self):
        p=compare.policy();self.assertEqual(p['order_and_ids_allowance'],0)
        self.assertEqual(p['geometry_allowance_logical_px'],2**-10)
        self.assertIn('every raw frame',p['operation_policy'])
        self.assertEqual(p['approved_actual_rust_review_sha256'],'55f7683818d82eea95376837121c26b7f964ab0fbfafef250ff1bc237d7c7273')

    def test_order_is_semantic_mismatch_not_fabricated_callback_equality(self):
        quads=[e for e in entries(self.raw,'scene','initial') if e['event']['kind']=='quad']
        quads[2]['event'],quads[5]['event']=quads[5]['event'],quads[2]['event']
        result=compare.compare_observations(self.rust,self.raw,self.inputs)
        self.assertFalse(result['passed']); self.assertEqual(result['mismatches'][0]['field'],'paint_order')
        with self.assertRaises(ValueError): compare.require_semantic_match(result)

    def test_each_box_geometry_compared(self):
        for name in compare.box_names(self.inputs['cases'][0],'base'):
            raw=copy.deepcopy(self.raw)
            for e in entries(raw,operation='initial'):
                if e['event'].get('node')==name and (e['event']['type']=='node' or e['event'].get('kind')=='quad'): e['event']['bounds'][0]+=1
            result=compare.compare_observations(self.rust,raw,self.inputs)
            with self.subTest(node=name): self.assertFalse(result['passed']);self.assertIn('bounds/'+name,[m['field'] for m in result['mismatches']])

    def test_all_frame_structure_and_raw_ids_retained(self):
        for operation in ('initial','base','updated','removed','restored'):
            for field,value in [('id','9999'),('parent','wrong'),('bounds',[float('nan'),0,0,0]),('pointer_events',True)]:
                raw=copy.deepcopy(self.raw);entries(raw,'node',operation)[0]['event'][field]=value
                with self.subTest(operation=operation,field=field),self.assertRaises(ValueError): compare.verify_candidate(raw,self.inputs)

    def test_scene_id_geometry_balance_and_exact_boxes(self):
        for field,value in [('id','999'),('bounds',[1,2,3,4]),('node','$attachments')]:
            raw=copy.deepcopy(self.raw);quad=next(e['event'] for e in entries(raw,'scene','initial') if e['event']['kind']=='quad');quad[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):compare.verify_candidate(raw,self.inputs)
        raw=copy.deepcopy(self.raw);entries(raw,'scene','initial')[-1]['event']['node']='a.anchor'
        with self.assertRaises(ValueError):compare.verify_candidate(raw,self.inputs)

    def test_extra_redraw_validated_without_pairing_counts(self):
        events=self.raw['cases'][0]['events'];base=[e for e in events if e['operation']=='base'];frame=base[-1]['frame']
        copied=copy.deepcopy(base[1:-1]);index=events.index(base[-1])
        for e in events[index:]:e['frame']+=1
        for e in copied:e['frame']=frame+1
        events[index:index]=copied;renumber(self.raw)
        result=compare.compare_observations(self.rust,self.raw,self.inputs)
        self.assertTrue(result['passed']);self.assertEqual(result['counts']['candidate_frames'],6)
        # A malformed earlier frame cannot be hidden by its later good redraw.
        entries(self.raw,'node','base')[0]['event']['bounds'][0]=float('inf')
        with self.assertRaises(ValueError):compare.verify_candidate(self.raw,self.inputs)

    def test_scene_masks_are_compared_not_silently_ignored(self):
        entries(self.raw,'scene','initial')[0]['event']['bounds'][2]=160
        result=compare.compare_observations(self.rust,self.raw,self.inputs)
        self.assertFalse(result['passed']);self.assertTrue(any(m['field'].startswith('effective_mask/') for m in result['mismatches']))

    def test_missing_observed_clip_is_null_and_fails_paired_masks(self):
        raw=copy.deepcopy(self.raw)
        raw['cases'][0]['events'][:]=[e for e in raw['cases'][0]['events'] if not (e['operation']=='base' and e['event']['type']=='scene' and e['event']['kind'].startswith('clip_'))]
        renumber(raw)
        decoded=compare.verify_candidate(raw,self.inputs)
        frame=decoded[0]['operations'][1]['frames'][0]
        self.assertTrue(all(m['derived_intersection'] is None and m['observed_clip_stack']==[] for m in frame['effective_masks'].values()))
        result=compare.compare_observations(self.rust,raw,self.inputs)
        self.assertFalse(result['passed'])
        self.assertTrue(any(m['field'].startswith('effective_mask/') and m['candidate'] is None for m in result['mismatches']))
        self.assertFalse(result['input_parity_established'])
        self.assertTrue(compare.compare_observations(self.rust,self.raw,self.inputs)['passed'])

    def test_actual_nested_clip_intersection_is_checked(self):
        raw=copy.deepcopy(self.raw);events=raw['cases'][0]['events'];scenes=entries(raw,'scene','initial')
        node=compare.topology(self.inputs['cases'][0],'base')['a.anchor'];start=copy.deepcopy(scenes[0]);end=copy.deepcopy(scenes[-1])
        start['event'].update(node='a.anchor',id=node['id'],bounds=[40,40,120,100])
        end['event'].update(node='a.anchor',id=node['id'])
        events.insert(events.index(scenes[0])+1,start);events.insert(events.index(scenes[-1]),end);renumber(raw)
        result=compare.compare_observations(self.rust,raw,self.inputs)
        self.assertFalse(result['passed']);self.assertTrue(any(m['candidate']==[40,40,120,100] for m in result['mismatches']))
        end['event'].update(node='$host',id=compare.topology(self.inputs['cases'][0],'base')['$host']['id'])
        with self.assertRaisesRegex(ValueError,'clip balance'):compare.verify_candidate(raw,self.inputs)

    def test_input_routes_cannot_be_omitted_or_fabricated(self):
        for field,value in [('target','ordinary.before'),('hit_test',None),('capture',[]),('bubble',[]),('callback_capture',[]),('callback_bubble',[]),('callbacks',[])]:
            raw=copy.deepcopy(self.raw);entries(raw,'route','base.input')[0]['event'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):compare.verify_candidate(raw,self.inputs)
        self.assertEqual(len(entries(self.raw,'route')),8)

    def test_transparent_and_occluding_stopping_are_still_input_diagnostics(self):
        for family,count in [('transparent-top',8),('occluding-top',1),('stopping-top',1)]:
            rust,raw,inputs=synthetic_pair(family);result=compare.compare_observations(rust,raw,inputs);op=result['cases'][0]['operations'][2]
            self.assertTrue(result['passed']);self.assertEqual(len(op['rust_actual_mouse_down_callbacks']),count);self.assertFalse(op['input_parity_established'])
            self.assertEqual(op['candidate_actual_routes'][0]['target'],'b.second' if family=='transparent-top' else 'c.second')

    def test_strict_transport_input_and_session(self):
        for field,value in [('layer','wrong'),('fixture','wrong'),('schema_version',2),('run_token','short'),('cases',[])]:
            raw=copy.deepcopy(self.raw);raw[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):compare.decode_transport(raw,self.raw['run_token'],self.inputs)
        for text in ('{"x":1,"x":2}','[NaN]','[Infinity]','{} {}'):
            with self.assertRaises(ValueError):compare.load_json(text)

    def test_lifecycle_labels_may_not_be_added_to_candidate_nodes(self):
        raw=copy.deepcopy(self.raw);entries(raw,'node','initial')[0]['event']['callback']='paint'
        with self.assertRaises(ValueError):compare.verify_candidate(raw,self.inputs)

    def test_restore_ids_are_stable_after_removal(self):
        verified=compare.verify_candidate(self.raw,self.inputs)[0]['operations'];initial=verified[0]['frames'][0]['nodes'];restored=verified[7]['frames'][0]['nodes']
        self.assertEqual({k:v['id'] for k,v in initial.items()},{k:v['id'] for k,v in restored.items()})
        self.assertNotIn('a.root',verified[5]['frames'][0]['nodes'])

    def test_frozen_oracle_and_reference_files_unchanged(self):
        profile=json.loads((PAIR/'profile.json').read_text())
        self.assertTrue(set(compare.baseline.RETAIN)<=set(profile['approved_fixture_sha256']))
        for name,sha in profile['approved_fixture_sha256'].items(): self.assertEqual(compare.baseline.digest(ROOT/name),sha,name)
        self.assertEqual(len(runner.SUITE_FILES),len(set(runner.SUITE_FILES)))
        for name in runner.SUITE_FILES:self.assertTrue((ROOT/name).is_file(),name)
        self.assertEqual(profile['margin_regression'],{'cases':88,'compared_operations':176})

    def test_adapter_only_observes_real_apis(self):
        text=(ROOT/'adapters/deferred_priority_moonbit/main.mbt').read_text()
        for value in ('attachment.deferred(priority=priority)','frame.paint().commands()','command.id()','node.bounds()','tree.hit_test(point)','tree.dispatch_input(event)','tree.dispatch_input_with(event','context.current_target()'):
            self.assertIn(value,text)
        for value in ('.sort(','.sort_by(','.round(','.floor(','.ceil(','derived_lifecycle','observed_paint_order'):
            self.assertNotIn(value,text)
        self.assertNotIn('"type", @json.to_json("paint")',text)

    def test_successful_transport_required_for_semantic_control(self):
        good={'returncode':0,'timed_out':False}; bad={'returncode':1,'timed_out':False}
        descriptor=json.loads((PAIR/'control-policy.json').read_text())[0]; mismatch={'passed':False,'mismatches':descriptor['required_witnesses']}
        self.assertEqual(mutants.classify(good,good,mismatch,descriptor=descriptor),'executed-paired-deferred-priority-rejection')
        for build,execution,kwargs in [(bad,good,{}),(good,bad,{}),(good,None,{}),(good,good,{'transport_error':'bad'}),(good,good,{'validation_error':'bad'})]:
            self.assertNotEqual(mutants.classify(build,execution,mismatch,descriptor=descriptor,**kwargs),'executed-paired-deferred-priority-rejection')
        self.assertEqual(mutants.classify(good,good,{'passed':True},descriptor=descriptor),'survived')

    def test_exact_frozen_control_descriptors_and_all_witnesses(self):
        descriptors=compare.mutation_descriptors()
        self.assertEqual([d['name'] for d in descriptors],compare.policy()['production_controls'])
        good={'returncode':0,'timed_out':False}
        for descriptor in descriptors:
            comparison={'passed':False,'mismatches':copy.deepcopy(descriptor['required_witnesses'])}
            self.assertEqual(mutants.classify(good,good,comparison,descriptor=descriptor),'executed-paired-deferred-priority-rejection')
            comparison['mismatches'].pop()
            self.assertEqual(mutants.classify(good,good,comparison,descriptor=descriptor),'executed-unrelated-rejection-not-deferred-priority-kill')
        outcomes=[{'mutation':d['name'],'outcome':'executed-paired-deferred-priority-rejection'} for d in descriptors]
        compare.validate_mutation_outcomes(outcomes)
        with self.assertRaises(ValueError):compare.validate_mutation_outcomes(outcomes[::-1])

    def test_policy_and_control_drift_stop_before_compiler(self):
        argv=['run.py','--core-source','/unused-core','--core-commit','a'*40,'--baseline','/unused-rust',
              '--regression-baseline','/unused-anchor','--margin-baseline','/unused-margin',
              '--baseline-suite-commit','b'*40,'--upstream-source','/unused-upstream','--output','/unused-output']
        real_digest=compare.baseline.digest
        for filename in ('comparison-policy.json','control-policy.json'):
            def digest(path): return '0'*64 if Path(path).name==filename else real_digest(path)
            with self.subTest(filename=filename),patch.object(sys,'argv',argv),patch.object(compare.baseline,'digest',side_effect=digest), \
                 patch.object(runner,'validate_baseline') as baseline_gate,patch.object(runner,'execute') as compiler:
                with self.assertRaisesRegex(ValueError,'policy changed'):runner.main()
                baseline_gate.assert_not_called();compiler.assert_not_called()
        with patch.object(sys,'argv',argv),patch.object(runner,'validate_baseline',side_effect=RuntimeError('after unchanged policy')) as baseline_gate, \
             patch.object(runner,'execute') as compiler:
            with self.assertRaisesRegex(RuntimeError,'after unchanged policy'):runner.main()
            baseline_gate.assert_called_once();compiler.assert_not_called()

    def test_all_regressions_gate_each_control(self):
        source=(PAIR/'run_mutants.py').read_text();self.assertIn("reopened['margin_regression']['passed']",source)
        self.assertIn("reopened['regressions']['passed']",source)
        self.assertIn("margin_regression=margin_regression",(PAIR/'verify.py').read_text())

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



if __name__ == "__main__": unittest.main()
