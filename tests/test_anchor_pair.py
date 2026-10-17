"""Self-contained synthetic checker tests; these are not engine execution evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'diagnostics/anchor_pair'))
import compare
import run_controls
import run_mutants
spec = importlib.util.spec_from_file_location('anchor_synthetic_helper', ROOT / 'tests/test_anchor_diagnostic.py')
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def synthetic_pair():
    rust, corpus = helper.synthetic_checker_input()
    corpus['cases'][0]['id'] = rust['cases'][0]['id'] = 'oversized-popup'
    def observation(case):
        nodes = compare.topology(case)
        bounds = {'$host': [0, 0, 640, 480], '$parent_position': [0, 0, 0, 0],
            'parent': [80, 80, 160, 120], 'button': [80, 80, 120, 65],
            'anchor_popup0': [80, 145, 80, 24], 'popup0': [220, 180, 80, 24],
            '$sibling_position': [0, 0, 0, 0], 'sibling': [220, 180, 80, 24]}
        events, frame = [], 0
        for operation, value in compare.operations(case):
            def emit(event): events.append(dict(sequence=len(events), frame=frame, operation=operation, event=event))
            emit(dict(type='operation_start', input=value))
            scale = 2 if operation == 'initial' else case['scale_factor']
            if value['action'] != 'click':
                frame += 1
                emit(dict(type='frame_start', scale_factor=scale, window_size=case['window']))
                for kind in ('request_start', 'request_end', 'prepaint_start'): emit(dict(type=kind))
                emit(dict(type='prepaint_end', overflow=False))
                for name, node in nodes.items():
                    emit(dict(type='node', node=name, id=node['id'], parent=node['parent'], bounds=bounds[name],
                              pointer_events=node['interactive'], focusable=node['interactive']))
                def scene(kind, name, rectangle): emit(dict(type='scene',kind=kind,node=name,bounds=rectangle))
                scene('clip_push', '$host', bounds['$host'])
                scene('quad', 'button', bounds['button']); scene('quad', 'sibling', bounds['sibling'])
                scene('clip_push', 'anchor_popup0', bounds['$host'])
                scene('quad', 'popup0', bounds['popup0']); scene('clip_pop', 'anchor_popup0', None)
                scene('clip_pop', '$host', None)
                for side, position in [('right', [641, 240]), ('bottom', [320, 481])]:
                    emit(dict(type='viewport_hit', side=side, position=position, target=None))
                emit(dict(type='frame_end', scale_factor=scale, window_size=case['window']))
            else:
                target = 'popup0' if case['popups'][0]['interactive'] else 'sibling'
                path = compare.lineage(target, nodes)
                for action in ('down', 'up'):
                    emit(dict(type='route',action=action,position=value['position'],hit_test=target,target=target,
                        capture=path[::-1],bubble=path,callback_capture=path[::-1],callback_bubble=path,
                        focused_target=target,focused_capture=path[::-1],focused_bubble=path))
            emit(dict(type='operation_end', scale_factor=scale))
        return dict(id=case['id'], events=events)
    extension = compare.extension_input(corpus)
    raw = dict(schema_version=1,layer=compare.CANDIDATE_LAYER,fixture='font-free-bounded-anchor',
        input=corpus,run_token='synthetic-checker-only-0001',cases=[observation(corpus['cases'][0])],
        candidate_only=dict(kind='interactive-oversized-viewport-contract',source_case_id='oversized-popup',
                            input=extension,observation=observation(extension)))
    return rust, raw, corpus


def synthetic_fractional_rust():
    """Synthetic lifecycle data solely for extension-validator regression tests."""
    import math
    import fractional_viewport
    template, _ = helper.synthetic_checker_input(interactive=True)
    inputs = fractional_viewport.corpus()
    raw = copy.deepcopy(template)
    raw['input'], raw['cases'] = inputs, []
    for case in inputs['cases']:
        events = []
        for source in template['cases'][0]['events']:
            if source['operation'] not in ('initial', 'configured'): continue
            entry = copy.deepcopy(source); event = entry['event']
            if event.get('node') == 'sibling': continue
            if 'node' in event: event['node'] = event['node'].replace('popup0', 'popup')
            scale = 2 if entry['operation'] == 'initial' else case['scale_factor']
            if 'scale_factor' in event: event['scale_factor'] = scale
            if 'window_size' in event: event['window_size'] = case['window']
            if event['type'] == 'operation_start' and entry['operation'] == 'configured': event['input']['scale_factor'] = scale
            if 'bounds' in event:
                button_height = math.ceil(65 * scale - .5) / scale
                geometry = {'$host': [0, 0, math.ceil(160.5 * scale - .5) / scale, 120],
                    'parent': [0, 0, 80, 80], 'button': [0, 0, 120, button_height],
                    'deferred_popup': [0, button_height, 320, 240],
                    'anchor_popup': [0, button_height, 320, 240], 'popup': [0, 0, 320, 240]}
                event['bounds'] = geometry[event['node']]
            if 'content_mask' in event: event['content_mask'] = [0, 0, *case['window']]
            entry['sequence'] = len(events); events.append(entry)
        for hit in case['hits']:
            def emit(event): events.append(dict(sequence=len(events),frame=2,operation=hit['id'],event=event))
            emit(dict(type='operation_start',input=dict(action='click',position=hit['position'])))
            if hit['id'] == 'inside-logical-viewport':
                for event in [dict(type='mouse_down',node='popup',position=hit['position'],contexts=['AnchorRoot','AnchorParent','Leaf_popup']),
                    dict(type='click',node='popup',detail=dict(kind='mouse',down=hit['position'],up=hit['position']),contexts=['AnchorRoot','AnchorParent','Leaf_popup'])]: emit(event)
            emit(dict(type='operation_end',scale_factor=case['scale_factor']))
        raw['cases'].append(dict(id=case['id'],events=events))
    return raw, inputs


class AnchorPairTests(unittest.TestCase):
    def setUp(self): self.rust, self.raw, self.corpus = synthetic_pair()
    def test_synthetic_pair_passes(self):
        result = compare.compare_observations(self.rust, self.raw, self.corpus)
        self.assertTrue(result['passed'])
        self.assertEqual(result['counts']['compared_operations'], 3)
        self.assertEqual(result['counts']['paired_clicks'], 1)
    def test_synthetic_corruptions_rejected(self):
        # The shared fixed-corpus control names target popup; the synthetic helper uses popup0.
        for name, change in run_controls.corruptions():
            if name == 'background-popup-interactive': continue
            altered = copy.deepcopy(self.raw)
            change(altered)
            with self.subTest(name=name):
                try: result = compare.compare_observations(self.rust, altered, self.corpus)
                except (ValueError, KeyError, TypeError, IndexError): continue
                self.assertFalse(result['passed'])
    def test_strict_json(self):
        for text in ['{"x":1,"x":2}', '[NaN]', '[Infinity]', '[-Infinity]']:
            with self.subTest(text=text), self.assertRaises(ValueError): compare.load_json(text)
    def test_boolean_sequence_rejected(self):
        self.raw['cases'][0]['events'][0]['sequence'] = False
        with self.assertRaises(ValueError): compare.verify_candidate(self.raw, self.corpus)
    def test_unknown_event_field_rejected(self):
        self.raw['cases'][0]['events'][0]['event']['unexpected'] = 1
        with self.assertRaises(ValueError): compare.verify_candidate(self.raw, self.corpus)
    def test_boolean_scale_rejected(self):
        run_controls.first(self.raw, 'frame_start')['scale_factor'] = True
        with self.assertRaises(ValueError): compare.verify_candidate(self.raw, self.corpus)
    def test_intermediate_frame_checked(self):
        run_controls.first(self.raw, 'node')['bounds'][0] = 9999
        with self.assertRaises(ValueError): compare.compare_observations(self.rust, self.raw, self.corpus)
    def test_extension_failure_separately_classified(self):
        event = next(e['event'] for e in self.raw['candidate_only']['observation']['events'] if e['event']['type'] == 'viewport_hit')
        event['target'] = 'popup0'
        with self.assertRaises(compare.CandidateOnlyContractError): compare.compare_observations(self.rust, self.raw, self.corpus)
    def test_extension_cannot_change_paired_input(self):
        self.raw['candidate_only']['input']['window'][0] = 320
        with self.assertRaises(ValueError): compare.verify_candidate(self.raw, self.corpus)
    def test_operation_loss_rejected(self):
        self.raw['cases'][0]['events'].pop()
        with self.assertRaises(ValueError): compare.verify_candidate(self.raw, self.corpus)
    def test_route_callback_loss_rejected(self):
        run_controls.first(self.raw, 'route')['callback_capture'] = []
        with self.assertRaises(ValueError): compare.verify_candidate(self.raw, self.corpus)
    def test_mutant_classification(self):
        good = dict(returncode=0,timed_out=False)
        self.assertEqual(run_mutants.classify(good,good,{'passed':False}), 'executed-semantic-rejection')
        self.assertEqual(run_mutants.classify(good,good,candidate_only_error='mask'), 'executed-candidate-only-contract-rejection')
        for build, execution, kwargs in [(dict(returncode=1,timed_out=False),None,{}),
                (good,None,{}),(good,dict(returncode=1,timed_out=False),{}),
                (good,dict(returncode=0,timed_out=True),{}),(good,good,{'transport_error':'JSON'})]:
            outcome=run_mutants.classify(build,execution,**kwargs)
            self.assertNotIn(outcome, ['executed-semantic-rejection','executed-candidate-only-contract-rejection'])
            with self.assertRaises(ValueError): compare.validate_mutation_outcomes([dict(outcome=outcome,scope='rust-paired-semantics')])
    def test_candidate_only_is_not_paired_kill(self):
        with self.assertRaises(ValueError): compare.validate_mutation_outcomes([dict(outcome='executed-candidate-only-contract-rejection',scope='rust-paired-semantics')])
    def test_mutation_transport_token(self):
        import tempfile
        with tempfile.TemporaryDirectory() as path:
            file=Path(path)/'raw.json';file.write_text(json.dumps(self.raw))
            with self.assertRaises(ValueError): run_mutants.decode_transport(file,'different-token',self.corpus)


class FractionalViewportTests(unittest.TestCase):
    def setUp(self):
        import fractional_viewport
        self.extension = fractional_viewport
        self.raw, self.inputs = synthetic_fractional_rust()
    def test_separate_synthetic_fractional_raw(self):
        result=self.extension.verify_rust(self.raw,self.inputs)
        self.assertEqual(len(result['cases']),2)
        self.assertEqual(sum(len(c['operations']) for c in result['cases']),8)
    def test_rounded_root_is_not_logical_mask(self):
        for entry in self.raw['cases'][0]['events']:
            if entry['operation']=='configured' and entry['event']['type']=='prepaint': entry['event']['content_mask'][2]=160
        with self.assertRaisesRegex(ValueError,'logical viewport mask'): self.extension.verify_rust(self.raw,self.inputs)
    def test_missing_inside_callbacks_rejected(self):
        events=self.raw['cases'][0]['events'];events[:]=[e for e in events if e['event']['type'] not in ('mouse_down','click')]
        for i,e in enumerate(events):e['sequence']=i
        with self.assertRaisesRegex(ValueError,'callback'): self.extension.verify_rust(self.raw,self.inputs)
    def test_lifecycle_loss_rejected(self):
        self.raw['cases'][0]['events'].pop(5)
        for i,e in enumerate(self.raw['cases'][0]['events']):e['sequence']=i
        with self.assertRaises(ValueError): self.extension.verify_rust(self.raw,self.inputs)
    def test_wrong_root_geometry_rejected(self):
        for entry in self.raw['cases'][0]['events']:
            if entry['event'].get('node')=='$host' and 'bounds' in entry['event']:entry['event']['bounds'][2]=150
        with self.assertRaises(ValueError): self.extension.verify_rust(self.raw,self.inputs)
    def test_logical_mask_route_survives_rounded_root_undershoot(self):
        case=self.inputs['cases'][0];nodes=compare.topology(case)
        path=compare.lineage('popup',nodes);point=[160.25,40]
        event=dict(type='route',action='down',position=point,hit_test='popup',target='popup',capture=path[::-1],bubble=path,
            callback_capture=path[::-1],callback_bubble=path,focused_target='popup',focused_capture=path[::-1],focused_bubble=path)
        frame=dict(painted_leaves=['button','popup'],bounds={'$host':[0,0,160,120],'button':[0,0,120,65],'popup':[0,0,320,240]},logical_viewport=[0,0,160.5,120])
        self.assertEqual(compare.verify_route(event,'down',point,nodes,frame)['target'],'popup')
        frame['logical_viewport']=[0,0,160,120]
        with self.assertRaises(ValueError):compare.verify_route(event,'down',point,nodes,frame)
    def test_fractional_kill_cannot_replace_ordinary_kill(self):
        with self.assertRaises(ValueError):compare.validate_mutation_outcomes([dict(scope='rust-paired-semantics',outcome='executed-fractional-viewport-semantic-rejection')])
    def test_separate_corpus_does_not_mutate_frozen_input(self):
        original=(ROOT/'diagnostics/anchor/scenarios.json').read_bytes()
        self.extension.corpus()['cases'][0]['window'][0]=999
        self.assertEqual((ROOT/'diagnostics/anchor/scenarios.json').read_bytes(),original)
        self.assertEqual(self.extension.corpus()['cases'][0]['window'][0],160.5)


class NativeRetentionTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from run import MODULE
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.stage=Path(self.temporary.name)/'source';self.stage.mkdir();(self.stage/'moon.mod').write_text(MODULE)
        self.dependencies={'primitives':[], 'scene':['primitives'], 'layout':['primitives'],
            'element':['layout','primitives','scene'], 'probe':['element','env','json','layout','primitives','scene']}
        self.filenames={p:('main' if p=='probe' else 'anchored' if p=='element' else p)+'.mbt' for p in self.dependencies}
        for package,deps in self.dependencies.items():
            directory=self.stage/package;directory.mkdir();(directory/self.filenames[package]).write_text('// synthetic checker input only')
            imports=['"'+('moonbitlang/core/' if d in ('env','json') else 'f4ah6o/gpui/')+d+'",' for d in deps]
            (directory/'moon.pkg').write_text(('import { '+ ' '.join(imports)+' }' if imports else '')+('\noptions("is-main": true)' if package=='probe' else ''))
    def tools(self): return {'moonc':{'path':'/tools/moonc'},'cc':{'path':'/usr/bin/cc'},'ar':{'path':'/usr/bin/ar'}}
    def plans(self):
        prefix='./_build/native/debug/build/';std='$MOON_HOME/lib/core/_build/native/release/bundle/'
        order=('primitives','layout','scene','element','probe');commands=[]
        for p in order:
            imports=[]
            for name in sorted(self.dependencies[p]+['prelude']):
                path=(std+name+'/'+name+'.mi' if name in ('prelude','env','json') else prefix+name+'/'+name+'.mi')
                imports+=['-i',path+':'+name]
            command=['moonc','build-package','./'+p+'/'+self.filenames[p],'-w','@a','-o',prefix+p+'/'+p+'.core',
                '-pkg','f4ah6o/gpui/'+p,'-pkg-type','executable' if p=='probe' else 'library','-std-path',std[:-1]]+imports+[
                '-pkg-sources','f4ah6o/gpui/'+p+':./'+p,'-target','native','-g','-O0','-workspace-path','.','-all-pkgs',prefix+'all_pkgs.json']
            commands.append(command)
        command=['moonc','link-core',std+'abort/abort.core',std+'core.core']+[prefix+p+'/'+p+'.core' for p in order]+[
            '-main','f4ah6o/gpui/probe','-o',prefix+'probe/__moonbit_link_core__/probe.o','-pkg-config-path','./probe/moon.pkg']
        for p in order:command+=['-pkg-sources','f4ah6o/gpui/'+p+':./'+p]
        commands.append(command+['-pkg-sources','moonbitlang/core:$MOON_HOME/lib/core','-target','x86_64-unknown-linux-gnu','-g','-O0'])
        runtime=('utf','sync_io','runtime','env','backtrace');archive=prefix+'libruntime-04d24968c494e3bb.a'
        for r in runtime:commands.append(['/usr/bin/cc','-o',prefix+'runtime-'+r+'.o','-I$MOON_HOME/include','-g','-c','-fwrapv','-fno-strict-aliasing','-O2','-DMOONBIT_ALLOW_STACKTRACE','-DMOONBIT_ALLOCATOR=MOONBIT_ALLOCATOR_MIMALLOC','$MOON_HOME/lib/runtime/'+r+'.c'])
        commands.append(['/usr/bin/ar','-r','-c','-s',archive]+[prefix+'runtime-'+r+'.o' for r in sorted(runtime)])
        commands.append(['/usr/bin/cc','-o',prefix+'probe/probe.exe','$MOON_HOME/lib/libmoonbitrun.o',prefix+'probe/__moonbit_link_core__/probe.o',archive,'-lm','$MOON_HOME/lib/libbacktrace.a'])
        import shlex
        return '\n'.join(shlex.join(c) for c in commands)
    def test_direct_native_environment_is_bound(self):
        from run import require_native_environment
        env=dict(CC='/usr/bin/cc',MOON_CC=None,MOON_HOME='/tools',MOONBIT_NEW_NATIVE=None)
        require_native_environment(env,self.tools())
        for change in ({'MOONBIT_NEW_NATIVE':'0'},{'MOONBIT_NEW_NATIVE':'unknown'},{'MOON_CC':'/wrong/compiler'}):
            with self.assertRaises(ValueError):require_native_environment(dict(env,**change),self.tools())
    def test_actual_object_pipeline_is_bound(self):
        from run import native_build_plan
        result=native_build_plan(self.plans(),self.tools(),self.stage)
        self.assertEqual(result['backend'],'direct-native-object')
        self.assertIn('probe/__moonbit_link_core__/probe.o',result['required_generated'])
        for old,new in [('probe/__moonbit_link_core__/probe.o','probe/probe.c'),('x86_64-unknown-linux-gnu','native'),
                ('/usr/bin/cc','/wrong/cc'),(' -g -O0',' -g'),('runtime-runtime.o','wrong-runtime.o'),('runtime/runtime.c','runtime/utf.c')]:
            with self.subTest(old=old),self.assertRaises(ValueError):native_build_plan(self.plans().replace(old,new),self.tools(),self.stage)
    def test_unretained_source_conflicting_mode_and_header_rejected(self):
        from run import native_build_plan
        changes=[('./element/anchored.mbt','/tmp/unretained-source.mbt'),
            ('-target native -g -O0','-target native -g -O0 -O2'),
            ("'-I$MOON_HOME/include' -g -c", "'-I$MOON_HOME/include' -include /tmp/unretained-header.h -g -c"),
            ('-workspace-path .','-workspace-path /tmp'),('f4ah6o/gpui/element:./element','f4ah6o/gpui/element:/tmp'),
            ('-std-path', '-unknown-option'),(' -lm ', ' -lm -lunknown ')]
        for old,new in changes:
            self.assertIn(old,self.plans())
            with self.subTest(old=old),self.assertRaises(ValueError):native_build_plan(self.plans().replace(old,new),self.tools(),self.stage)
    def test_missing_staged_source_and_changed_imports_rejected(self):
        from run import native_build_plan
        file=self.stage/'element/anchored.mbt';file.rename(file.with_name('replaced.mbt'))
        with self.assertRaises(ValueError):native_build_plan(self.plans(),self.tools(),self.stage)
        file.with_name('replaced.mbt').rename(file)
        (self.stage/'element/moon.pkg').write_text('import { "moonbitlang/core/unknown", }')
        with self.assertRaises(ValueError):native_build_plan(self.plans(),self.tools(),self.stage)
    def test_unsupported_package_metadata_rejected(self):
        from run import native_build_plan
        file=self.stage/'primitives/moon.pkg';original=file.read_text()
        for extra in ['options("compile-flags": ["-O2"])','import { "external/unknown", }',
                      'import { "external/unknown", } for "test"','import {} for "unknown"']:
            file.write_text(original+'\n'+extra)
            with self.subTest(extra=extra),self.assertRaises(ValueError):native_build_plan(self.plans(),self.tools(),self.stage)
        file.write_text(original)
    def test_missing_and_swapped_generated_objects_rejected(self):
        from run import retain_native_generated,native_generated_inventory,native_build_plan
        source=Path(self.temporary.name)/'build';out=Path(self.temporary.name)/'retained';source.mkdir()
        plan=native_build_plan(self.plans(),self.tools(),self.stage)
        with self.assertRaises(ValueError):retain_native_generated(source,out,plan)
        for name in plan['required_generated']:
            file=source/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_text('synthetic non-executable checker fixture '+name)
        retained=retain_native_generated(source,out,plan)
        self.assertEqual(native_generated_inventory(out,plan),retained)
        for name in ['probe/__moonbit_link_core__/probe.o','runtime-runtime.o','libruntime-04d24968c494e3bb.a']:
            file=out/name;original=file.read_bytes();file.write_bytes(b'swapped synthetic input')
            with self.assertRaises(ValueError):compare.require(native_generated_inventory(out,plan)==retained,'swapped generated input')
            file.write_bytes(original);file.unlink()
            with self.assertRaises(ValueError):native_generated_inventory(out,plan)
            file.write_bytes(original)
    def test_baseline_changes_trigger_pair_workflow(self):
        workflow=(ROOT/'.github/workflows/anchor-pair.yml').read_text()
        for path in ['adapters/anchor_rust/**','diagnostics/anchor/**','tests/test_anchor_diagnostic.py','.github/workflows/anchor-diagnostic.yml']:
            self.assertIn("- '"+path+"'",workflow)


if __name__ == '__main__': unittest.main()
