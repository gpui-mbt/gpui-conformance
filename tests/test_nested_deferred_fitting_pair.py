"""Source and synthetic checker tests only; never native execution/parity evidence."""
import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
PAIR=ROOT/'diagnostics/nested_deferred_fitting_pair'
def module(name,path,imports=None):
    spec=importlib.util.spec_from_file_location(name,path); result=importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules,imports or {}): spec.loader.exec_module(result)
    return result
compare=module('fitting_pair_compare',PAIR/'compare.py')
runner=module('fitting_pair_runner',PAIR/'run.py',{'compare':compare})
verifier=module('fitting_pair_verifier',PAIR/'verify.py',{'compare':compare,'run':runner})
mutants=module('fitting_pair_mutants',PAIR/'run_mutants.py',{'compare':compare,'run':runner,'verify':verifier})
regressions=module('fitting_pair_regressions',PAIR/'regressions.py')
helper=module('fitting_pair_test_oracle',ROOT/'tests/test_nested_deferred_fitting_diagnostic.py')


def synthetic_pair(family='signed-half-composed'):
    rust,corpus=helper.single(family) if family else helper.synthetic_trace()
    # Match reviewed redraw shape only in test fixtures; not observations.
    for observed in rust['cases']:
        original=observed['events'];events=[];frame=0
        for op in [x[0] for x in compare.baseline.operation_plan(corpus['cases'][0])]:
            group=[e for e in original if e['operation']==op]
            def add(e):
                e=copy.deepcopy(e);e['sequence']=len(events);e['frame']=frame;events.append(e)
            add(group[0])
            for _ in range(2 if op in ('scale1','scale1.25') else 1):
                frame+=1
                for e in group[1:-1]:add(e)
            add(group[-1])
        observed['events']=events
    candidates=[]
    for case,original in zip(corpus['cases'],rust['cases']):
        events=[];frame=0
        for operation,action,stage,scale in compare.baseline.operation_plan(case):
            def emit(e):events.append({'sequence':len(events),'operation':operation,'frame':frame,'event':copy.deepcopy(e)})
            emit({'type':'operation_start','input':action});frame+=1
            emit({'type':'frame_start','scale_factor':scale,'window_size':case['window']})
            for kind in ('request_start','request_end','prepaint_start'):emit({'type':kind})
            emit({'type':'prepaint_end','overflow':True})
            geometry=helper.independent_geometry(case,stage,scale);nodes={}
            for name,node in compare.topology(case,stage).items():
                if name in geometry:bounds=geometry[name][0]
                elif name=='$ancestor_position':bounds=[0,0,0,0]
                elif name.startswith('$'):bounds=[*geometry['$ancestor'][0][:2],0,0]
                else:bounds=[*geometry[name[0]+'.root'][0][:2],0,0]
                e={'type':'node','node':name,**node,'bounds':bounds,'pointer_events':False,'focusable':False};nodes[name]=e;emit(e)
            emit({'type':'scene','kind':'clip_push','node':'$host','id':'1','bounds':[0,0,*case['window']]})
            first_frame=next(e['frame'] for e in original['events'] if e['operation']==operation and e['event']['type']=='frame_start')
            for entry in original['events']:
                e=entry['event'];name=e.get('node')
                if entry['frame']==first_frame and e['type']=='paint' and compare.baseline.is_box(name):emit({'type':'scene','kind':'quad','node':name,'id':nodes[name]['id'],'bounds':nodes[name]['bounds']})
            emit({'type':'scene','kind':'clip_pop','node':'$host','id':'1','bounds':None})
            emit({'type':'frame_end','scale_factor':scale,'window_size':case['window']});emit({'type':'operation_end','scale_factor':scale})
        candidates.append({'id':case['id'],'events':events})
    return rust,{'schema_version':1,'layer':compare.CANDIDATE_LAYER,'fixture':'font-free-two-level-nested-deferred-fitting-rounding','input':corpus,'run_token':'synthetic-fitting-pair-only-0001','cases':candidates},corpus


def evaluate(rust,candidate,corpus):
    # Decimal synthetic geometry is not the exact actual f32 oracle projection.
    # Freeze remains enforced in production; this bypass exists ONLY in tests.
    with patch.object(compare,'verify_rust_freeze',return_value=None):return compare.compare_observations(rust,candidate,corpus)


def alter_box(candidate,name,operation='initial',delta=4):
    for e in candidate['cases'][0]['events']:
        v=e['event']
        if e['operation']==operation and v.get('node')==name and (v['type']=='node' or v.get('kind')=='quad'):v['bounds'][0]+=delta


class FittingPairTests(unittest.TestCase):
    def test_full_synthetic_coverage(self):
        r,c,i=synthetic_pair(None);result=evaluate(r,c,i)
        self.assertTrue(result['passed']);self.assertEqual(result['counts'],{'cases':8,'rust_frames':80,'candidate_frames':64,'compared_operations':64,'compared_frame_pairs':80})
        self.assertFalse(result['lifecycle_callback_parity_established']);self.assertFalse(result['input_parity_established'])

    def test_frozen_policy(self):
        p=compare.policy();self.assertEqual(compare.TOLERANCE,2**-10);self.assertEqual(compare.GRID_TOLERANCE,2**-10)
        self.assertEqual(len(p['mapped_boxes']),13);self.assertEqual(len(p['candidate_ids']),29)
        self.assertEqual(p['production_controls'],[d['name'] for d in compare.mutation_descriptors()])
        self.assertEqual(p['geometry_allowance_logical_px'],2**-10);self.assertEqual(p['physical_grid_allowance_px'],2**-10)

    def test_actual_projection_inventory(self):
        raw=json.loads((PAIR/'actual-rust-projection.json').read_text());self.assertEqual(len(raw['cases']),8)
        self.assertEqual(sum(len(c['frames']) for c in raw['cases']),80)
        for case in raw['cases']:
            self.assertEqual(len(case['frames']),10)
            for frame in case['frames']:
                self.assertEqual(len(frame['box_paint_entries']),13)
                self.assertEqual(set(e['candidate_node'] for e in frame['box_paint_entries']),set(compare.policy()['mapped_boxes']))
                self.assertTrue(all(e['content_mask']==[0,0,320,240] for e in frame['box_paint_entries']))

    def test_synthetic_never_qualifies_as_actual_freeze(self):
        r,c,i=synthetic_pair()
        with self.assertRaisesRegex(ValueError,'actual Rust box projection'):compare.compare_observations(r,c,i)

    def test_all_six_control_classifications(self):
        good={'returncode':0,'timed_out':False}
        for d in compare.mutation_descriptors():
            result={'passed':False,'mismatches':copy.deepcopy(d['required_witnesses'])}
            self.assertEqual(mutants.classify(good,good,result,descriptor=d),'executed-paired-nested-deferred-fitting-rejection')
            result['mismatches'].pop()
            self.assertNotEqual(mutants.classify(good,good,result,descriptor=d),'executed-paired-nested-deferred-fitting-rejection')
            for build,execution,error in [({'returncode':1,'timed_out':False},good,None),(good,{'returncode':1,'timed_out':False},None),(good,good,'invalid observation')]:
                self.assertNotEqual(mutants.classify(build,execution,{'passed':False,'mismatches':d['required_witnesses']},error,descriptor=d),'executed-paired-nested-deferred-fitting-rejection')

    def test_numeric_allowances_separate_and_absolute(self):
        self.assertTrue(compare.numeric_equal([10],[10+2**-10]))
        self.assertFalse(compare.numeric_equal([10],[10+2**-9]))
        self.assertFalse(compare.numeric_equal([1],[True]))
        self.assertFalse(compare.numeric_equal([0],[float('nan')]))
        compare.physical_grid([0,0,12+2**-12,8],2)
        with self.assertRaises(ValueError):compare.physical_grid([0,0,12+2**-10,8],2)

    def test_owner_top_fault_is_semantic_not_transport(self):
        r,c,i=synthetic_pair('exact-inside')
        for e in c['cases'][0]['events']:
            if e['event'].get('type')=='node' and e['event'].get('node')=='a.anchor':e['event']['bounds'][1]-=8
        result=evaluate(r,c,i);self.assertFalse(result['passed'])
        self.assertTrue(any(e['field']=='static_origin/a.anchor' for e in result['mismatches']))

    def test_box_geometry_mutation_rejected_semantically(self):
        r,c,i=synthetic_pair();alter_box(c,'a.nested.root')
        result=evaluate(r,c,i);self.assertFalse(result['passed']);self.assertTrue(any(e['field']=='bounds/a.nested.root' for e in result['mismatches']))

    def test_order_exact(self):
        r,c,i=synthetic_pair();events=c['cases'][0]['events'];positions=[n for n,e in enumerate(events) if e['operation']=='initial' and e['event'].get('kind')=='quad'];a,b=positions[-2:];events[a]['event'],events[b]['event']=events[b]['event'],events[a]['event']
        self.assertTrue(any(m['field']=='paint_order' for m in evaluate(r,c,i)['mismatches']))

    def test_mask_semantic(self):
        r,c,i=synthetic_pair()
        for e in c['cases'][0]['events']:
            if e['event'].get('kind')=='clip_push':e['event']['bounds'][2]-=4
        self.assertTrue(any(m['field'].startswith('effective_mask/') for m in evaluate(r,c,i)['mismatches']))

    def test_metadata_and_sequence_reject(self):
        for kind in ('boolean_input','sequence','session','reference_extent','identifier','extra_field'):
            r,c,i=synthetic_pair()
            if kind=='boolean_input':c['input']=copy.deepcopy(i);c['input']['cases'][0]['margin']=True
            if kind=='sequence':c['cases'][0]['events'][2]['sequence']=99
            if kind=='session':c['run_token']='x'
            if kind=='reference_extent':
                for e in c['cases'][0]['events']:
                    if e['event'].get('node')=='ordinary.reference' and e['event']['type']=='node':e['event']['bounds'][3]=0
            if kind=='identifier':
                next(e['event'] for e in c['cases'][0]['events'] if e['event']['type']=='node')['id']='999'
            if kind=='extra_field':c['extra']=1
            with self.subTest(kind=kind),self.assertRaises(ValueError):evaluate(r,c,i)

    def test_boolean_operation_aliases_reject(self):
        for operation,key,value in [('scale1','scale_factor',True),('child-lower','priorities',[2,False,3,True])]:
            r,c,inputs=synthetic_pair()
            event=next(e['event'] for e in c['cases'][0]['events'] if e['operation']==operation and e['event']['type']=='operation_start')
            event['input'][key]=value
            with self.assertRaisesRegex(ValueError,'operation start'):evaluate(r,c,inputs)

    def test_signed_mutant_geometry_is_structurally_valid(self):
        compare.physical_grid([-8,-8,40,32],2)
        with self.assertRaises(ValueError):compare.physical_grid([0,0,-1,32],2)

    def test_duplicate_json_and_nonfinite(self):
        for text in ('{"a":1,"a":2}','{"a":NaN}','{"a":Infinity}'):
            with self.assertRaises(ValueError):compare.load_json(text)

    def test_exact_additive_inventory_and_baseline(self):
        profile=json.loads((PAIR/'profile.json').read_text())
        self.assertEqual(len(runner.NEW_SUITE_FILES),19)
        for name in runner.NEW_SUITE_FILES:self.assertTrue((ROOT/name).is_file(),name)
        untracked=set(subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines())
        if untracked:
            self.assertEqual(untracked,set(runner.NEW_SUITE_FILES),'current source-only additions exact19')
        entries=runner.git_tree_entries(ROOT,profile['suite_base_public_commit']);self.assertEqual(len(entries),704)
        self.assertEqual(entries,profile['baseline_git_entries'])
        for name,v in entries.items():
            self.assertEqual(subprocess.check_output(['git','hash-object','--',name],cwd=ROOT,text=True).strip(),v['oid'],name)
        regressions.authenticate_legacy_helpers()

    def test_scoped_wrappers_and_no_old_top_level_pin(self):
        for context in (regressions.original_modules,regressions.margin_modules,regressions.flat_modules,regressions.nested_modules):
            with context() as old:self.assertEqual(old.native.ROOT,ROOT)
        source=(PAIR/'regressions.py').read_text()
        self.assertIn('diagnostics/nested_deferred/scenarios.json',source)
        self.assertIn("profile['legacy_suite_commit']",source)
        for name in ('run.py','verify.py','run_mutants.py','verify_mutants.py'):self.assertIn('nested_regression',(PAIR/name).read_text())

    def test_distinct_frozen_oracle_lineages(self):
        profile=json.loads((PAIR/'profile.json').read_text())
        compare.baseline.validate_baseline_source(ROOT,profile['suite_base_public_commit'])
        with regressions.nested_modules() as old:
            old.compare.baseline.validate_baseline_source(ROOT,profile['legacy_suite_commit'])
            with self.assertRaisesRegex(ValueError,'non-owned'):
                old.compare.baseline.validate_baseline_source(ROOT,profile['suite_base_public_commit'])
        workflow=(ROOT/'.github/workflows/nested-deferred-fitting-native-pair.yml').read_text()
        self.assertIn('--legacy-suite-source ../legacy-suite',workflow)
        self.assertIn('--baseline ../oracle-suite/_build/nested-deferred-fitting-baseline',workflow)
        self.assertIn('--nested-baseline ../legacy-suite/_build/nested-deferred-baseline',workflow)

    def test_python_source_parse(self):
        for path in PAIR.glob('*.py'):ast.parse(path.read_text())

    def test_selected_core_and_mutation_sites(self):
        selected=os.environ.get('GPUI_SELECTED_CORE_TEST_SOURCE')
        if not selected:self.skipTest('explicit exact selected-core checkout absent; no native claim')
        selected=Path(selected);profile=json.loads((PAIR/'profile.json').read_text())
        # Source byte verification only; no compiler or process execution.
        for entries in profile['selected_core_inventory'].values():
            for path,v in entries.items():self.assertEqual(compare.baseline.digest(selected/path),v['sha256'],path)
        for d in compare.mutation_descriptors():self.assertEqual((selected/d['path']).read_text().count(d['old']),1,d['name'])

if __name__=='__main__':unittest.main()
