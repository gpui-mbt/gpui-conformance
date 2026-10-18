"""Source/checker tests only. Synthetic rows are never Rust execution evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('padded_verify', ROOT/'diagnostics/padded_text_anchor/verify.py')
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)
FIXTURE = verify.load(verify.FIXTURE)
ADDITIONS = {'adapters/padded_text_anchor_rust/Cargo.toml','adapters/padded_text_anchor_rust/Cargo.lock','adapters/padded_text_anchor_rust/src/main.rs','diagnostics/padded_text_anchor/README.md','diagnostics/padded_text_anchor/scenarios.json','diagnostics/padded_text_anchor/verify.py','tests/test_padded_text_anchor.py'}

def synthetic():
    raw = dict(schema_version=1,layer='source-derived-padded-text-anchor',upstream_revision=verify.UPSTREAM,
               text_backend='upstream-NoopTextSystem',run_token='synthetic-not-executed',input=copy.deepcopy(FIXTURE),variants=[])
    for variant in FIXTURE['variants']:
        events=[]
        for frame,step in enumerate(FIXTURE['steps'],1):
            def add(event):
                events.append(dict(sequence=len(events),operation=step['id'],frame=frame,event=event))
            add(dict(type='operation_start',**{k:step[k] for k in ('viewport','scale','nested_open')}))
            add(dict(type='frame_start',viewport=step['viewport'],scale=step['scale']))
            nodes=verify.BASE_NODES | (verify.CHILD_NODES if step['nested_open'] else set())
            for node in sorted(nodes):
                if node.endswith('_text'):
                    add(dict(type='text_inputs',node=node,font_family='synthetic',font_size=10,rem_size=10,line_height=15,units_per_em=1000,ascent=10,descent=-2,em_advance=6))
            for node in sorted(nodes):add(dict(type='prepaint',node=node,bounds=[10,20,30,40]))
            hits={'primary','secondary'} | ({'child'} if step['nested_open'] else {'parent'})
            for node in sorted(hits):add(dict(type='hitbox',node=node,bounds=[10,20,30,40],content_mask=[0,0,900,700]))
            for node in ['host','primary','primary_text']:
                add(dict(type='paint',node=node,bounds=[10,20,30,40]))
            add(dict(type='host_paint_return'))
            for node in sorted(nodes-{'host','primary','primary_text'}):add(dict(type='paint',node=node,bounds=[10,20,30,40]))
            add(dict(type='operation_end'))
        raw['variants'].append(dict(variant=variant,events=events))
    return raw

class PaddedTextAnchorTests(unittest.TestCase):
    def test_synthetic_is_never_evidence(self):
        report=verify.verify(json.loads(json.dumps(synthetic())))
        self.assertEqual(report['status'],'trace_shape_valid')
        self.assertFalse(report['execution_authenticated'])
        self.assertIsNone(report['observed_numeric_goldens'])
        self.assertIsNone(report['attachment_reference_hypothesis_confirmed'])
        self.assertFalse(report['font_parity'])
        self.assertFalse(report['unchanged_example_parity'])

    def test_mutated_traces_rejected(self):
        for kind in ['sequence','scale','bounds','hitbox','font','missing_text','duplicate_paint','order','operation','backend','input','bool_sequence']:
            raw=synthetic(); events=raw['variants'][0]['events']
            def first(k):return next(r['event'] for r in events if r['event']['type']==k)
            if kind=='sequence':events[0]['sequence']=99
            if kind=='bool_sequence':events[0]['sequence']=False
            if kind=='scale':first('frame_start')['scale']=9
            if kind=='bounds':first('prepaint')['bounds']=[1,2,-1,4]
            if kind=='hitbox':first('hitbox')['bounds'][0]=99
            if kind=='font':first('text_inputs')['em_advance']=0
            if kind=='missing_text':first('text_inputs')['type']='host_paint_return'
            if kind=='duplicate_paint':first('paint')['node']='parent'
            if kind=='order':
                a=next(i for i,r in enumerate(events) if r['event']['type']=='paint')
                b=next(i for i,r in enumerate(events) if r['event']['type']=='prepaint' and r['event']['node']=='host')
                events[a]['event'],events[b]['event']=events[b]['event'],events[a]['event']
            if kind=='operation':events[-1]['operation']='wrong'
            if kind=='backend':raw['text_backend']='real-fonts'
            if kind=='input':raw['input']['steps'][0]['scale']=42
            with self.subTest(kind=kind),self.assertRaises(ValueError):verify.verify(json.loads(json.dumps(raw)))

    def test_typed_metadata_negative_controls(self):
        cases = [
            ('schema', lambda r: r.__setitem__('schema_version', True)),
            ('input_schema_bool', lambda r: r['input'].__setitem__('schema_version', True)),
            ('input_schema_float', lambda r: r['input'].__setitem__('schema_version', 1.0)),
            ('input_scale', lambda r: r['input']['steps'][0].__setitem__('scale', True)),
            ('input_nested', lambda r: r['input']['steps'][0].__setitem__('nested_open', 0)),
        ]
        for event_type in ('frame_start', 'operation_start'):
            def mutate_scale(raw, kind=event_type):
                next(r['event'] for r in raw['variants'][0]['events'] if r['event']['type']==kind)['scale']=True
            cases.append((event_type+'_scale', mutate_scale))
        def mutate_nested(raw):
            raw['variants'][0]['events'][0]['event']['nested_open']=0
        cases.append(('operation_nested',mutate_nested))
        for name, mutate in cases:
            raw=synthetic(); mutate(raw)
            for roundtrip in (False,True):
                candidate=json.loads(json.dumps(raw)) if roundtrip else raw
                with self.subTest(name=name,roundtrip=roundtrip),self.assertRaises(ValueError):
                    verify.verify(candidate)
        # Viewports in this fixture are >1. A recursive comparator unit control
        # specifically protects bool/zero and bool/one aliases in nested arrays.
        for left,right in [([False],[0]),({'x':[True]},{'x':[1]}),([1], [True]),(True,1), (False,0)]:
            self.assertFalse(verify.json_equal(left,right))
            self.assertFalse(verify.json_equal(json.loads(json.dumps(left)),json.loads(json.dumps(right))))

    def test_numeric_geometry_equivalence_is_allowed(self):
        raw=synthetic()
        raw['input']['steps'][0]['scale']=1.0
        for row in raw['variants'][0]['events']:
            if row['event']['type'] in ('frame_start','operation_start'):
                row['event']['scale']=float(row['event']['scale'])
                row['event']['viewport']=[float(v) for v in row['event']['viewport']]
        self.assertEqual(verify.verify(json.loads(json.dumps(raw)))['status'],'trace_shape_valid')
        for invalid in (float('nan'),float('inf'),float('-inf')):
            self.assertFalse(verify.json_equal(invalid,invalid))

    def test_nonfinite_duplicate_and_boolean_rectangles(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'raw.json'
            for content in ['{"a":1,"a":2}','{"a":NaN}','{"a":Infinity}']:
                path.write_text(content)
                with self.assertRaises(ValueError):verify.load(path)
        self.assertFalse(verify.rectangle([False,0,1,1]))

    def test_fixture_coverage(self):
        self.assertEqual(FIXTURE['variants'],['example_branch','asymmetric_fractional'])
        self.assertEqual({s['scale'] for s in FIXTURE['steps']},{1,1.25,1.5,2})
        self.assertEqual(len({s['id'] for s in FIXTURE['steps']}),len(FIXTURE['steps']))
        for i in range(0,len(FIXTURE['steps']),2):
            a,b=FIXTURE['steps'][i:i+2]
            self.assertFalse(a['nested_open']);self.assertTrue(b['nested_open'])
            self.assertEqual(a['viewport'],b['viewport'])

    def test_source_delimiters(self):
        # Lexical balance only, explicitly not a Rust parser/type checker.
        import re
        source=(ROOT/'adapters/padded_text_anchor_rust/src/main.rs').read_text()
        source=re.sub(r'"(?:\\.|[^"\\])*"|//[^\n]*', '', source, flags=re.S)
        stack=[]
        for char in source:
            if char in '([{':stack.append(char)
            elif char in ')]}':
                self.assertTrue(stack)
                self.assertEqual('([{'.index(stack.pop()), ')]}'.index(char))
        self.assertFalse(stack)

    def test_source_uses_real_text_and_layout(self):
        source=(ROOT/'adapters/padded_text_anchor_rust/src/main.rs').read_text()
        for text in ['Open Popover','Child Popover','This is first level Popover,','This is second level Popover with nested deferred!','Click outside to close.']:
            self.assertIn(text,source)
        for call in ['.px_3().py_1()', '.mt_2()', '.w_96().gap_3()', '.border_1().text_sm()',
                     'TestAppContext::single()', 'cx.simulate_resize(', 'cx.simulate_scale_factor_change(',
                     'text.resolve_font(', 'text.em_advance(', 'hitbox.bounds', 'hitbox.content_mask.bounds']:
            self.assertIn(call,source)
        self.assertNotIn('.position(',source)
        self.assertNotIn('.child(div().w(',source)
        self.assertIn('NoopTextSystem',source)
        self.assertIn('asymmetric_fractional',source)

    def test_lock_manifest_root_only_rename(self):
        import tomllib
        manifest=tomllib.loads((ROOT/'adapters/padded_text_anchor_rust/Cargo.toml').read_text())
        lock=tomllib.loads((ROOT/'adapters/padded_text_anchor_rust/Cargo.lock').read_text())
        name=manifest['package']['name']
        self.assertEqual(name,'gpui-padded-text-anchor-diagnostic')
        self.assertEqual(sum(p['name']==name for p in lock['package']),1)
        self.assertEqual(manifest['dependencies']['gpui']['features'],['test-support'])

    def test_seven_paths_budget_and_baseline(self):
        self.assertEqual(len(ADDITIONS),7)
        self.assertLessEqual(sum((ROOT/p).stat().st_size for p in ADDITIONS),2*1024**2)
        readme=(ROOT/'diagnostics/padded_text_anchor/README.md').read_text()
        for identity in [verify.BASELINE,verify.BASELINE_TREE,verify.UPSTREAM]:self.assertIn(identity,readme)
        self.assertIn('uncompiled and unexecuted',readme)

if __name__=='__main__':unittest.main()
