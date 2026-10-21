"""Synthetic contract tests only: these never claim framework execution."""
import copy
import json
import unittest
from unittest.mock import patch
import run_root_box as r
import attest_root_box_build as attester

class RootBoxTests(unittest.TestCase):
    def setUp(self):
        self.corpus=json.loads((r.ROOT/'root_box_scenarios.json').read_text())
    def observed(self,implementation):
        cases=[]
        for c in self.corpus['cases']:
            rect=[0,0,c['width'],c['height']]
            observation={'bounds':[rect.copy()]+[[0,0,1,1] for _ in c['children']],'device_scale_factor':c['device_scale_factor']}
            if implementation=='upstream':observation['test_window_viewport']=rect.copy()
            else:observation.update(physical_viewport=rect.copy(),snapshot_viewport=rect.copy())
            cases.append(dict(id=c['id'],layer='headless-layout',status='observed',observation=observation))
        return dict(implementation=implementation,cases=cases)
    def test_coverage(self):
        r.validate(self.corpus)
        cases=self.corpus['cases']
        self.assertEqual(len(cases),132)
        workflow=(r.ROOT/'.github/workflows/harness.yml').read_text()
        self.assertEqual(workflow.count("python3 -m unittest discover -s tests -p 'test_root_box.py' -v"),1)
        self.assertEqual(sum(c['expected_fixed_mismatch'] for c in cases),54)
        self.assertEqual(sum(not c['children'] for c in cases),57)
        for scale in (1,1.5,2):
            for profile in ('padding','border','combined'):
                for axis in ('width','height'):
                    for relation in ('narrow','equal','wide'):
                        self.assertEqual(sum(c['device_scale_factor']==scale and c['inset_profile']==profile and c['threshold_axis']==axis and c['threshold_relation']==relation for c in cases),2)
        self.assertEqual({c['direction'] for c in cases},{'row','column','row_reverse','column_reverse'})
    def test_thresholds_are_actual_snapped_inset_minima(self):
        for c in self.corpus['cases']:
            if c['inset_profile'] not in ('padding','border','combined'):continue
            scale=c['device_scale_factor']
            # Non-tie fractional inputs make threshold intent independent of ties.
            for v in c['padding']+c['border']:
                self.assertNotAlmostEqual(v*scale%1,0.5)
            p=[round(v*scale)/scale for v in c['padding']]
            b=[max(1/scale,round(v*scale)/scale) if v else 0 for v in c['border']]
            axis=c['threshold_axis'];indices=(1,3) if axis=='width' else (0,2)
            threshold=sum(p[i]+b[i] for i in indices)
            expected=threshold+{'narrow':-1,'equal':0,'wide':1}[c['threshold_relation']]/scale
            self.assertAlmostEqual(c[axis],expected)
    def test_identical_full_bounds_pass(self):
        self.assertEqual(r.compare(self.corpus,self.observed('upstream'),self.observed('moonbit'))['summary'],{'total':132,'pass':132,'mismatch':0})
    def test_all_root_and_child_coordinates_compared(self):
        for node in (0,1):
            for coordinate in range(4):
                a,b=self.observed('upstream'),self.observed('moonbit')
                b['cases'][0]['observation']['bounds'][node][coordinate]+=1
                result=r.compare(self.corpus,a,b)
                self.assertEqual(result['summary']['mismatch'],1)
                self.assertEqual(result['cases'][0]['differences'][0]['path'],f'bounds[{node}][{coordinate}]')
    def test_physical_viewport_is_exact_not_tolerance(self):
        for key in ('physical_viewport','snapshot_viewport'):
            a,b=self.observed('upstream'),self.observed('moonbit')
            b['cases'][0]['observation'][key][2]+=1e-10
            with self.assertRaisesRegex(ValueError,'exact'):r.compare(self.corpus,a,b)
    def test_legacy_control_does_not_claim_exact_physical_viewport(self):
        a,b=self.observed('upstream'),self.observed('moonbit')
        b['cases'][0]['observation']['snapshot_viewport'][2]+=1
        r.compare(self.corpus,a,b,fixed_root=True)
    def test_testwindow_viewport_and_scale_validated(self):
        for key in ('test_window_viewport','device_scale_factor'):
            a,b=self.observed('upstream'),self.observed('moonbit')
            if key=='test_window_viewport':a['cases'][0]['observation'][key][2]+=1
            else:a['cases'][0]['observation'][key]=2
            with self.assertRaises(ValueError):r.compare(self.corpus,a,b)
    def test_bad_numeric_coordinate_or_size(self):
        for value,coordinate in [(True,0),(float('nan'),0),(float('inf'),0),(-1,2),(-1,3)]:
            a,b=self.observed('upstream'),self.observed('moonbit')
            b['cases'][0]['observation']['bounds'][0][coordinate]=value
            with self.assertRaises(ValueError):r.compare(self.corpus,a,b)
    def test_missing_extra_reordered_or_projected_observation_rejected(self):
        for operation in ('missing','extra','reorder','projection','status','layer','implementation'):
            a,b=self.observed('upstream'),self.observed('moonbit')
            if operation=='missing':b['cases'].pop()
            elif operation=='extra':b['cases'].append(copy.deepcopy(b['cases'][0]))
            elif operation=='reorder':b['cases'][0],b['cases'][1]=b['cases'][1],b['cases'][0]
            elif operation=='projection':b['cases'][0]['observation']['line_origins']=[]
            elif operation=='implementation':b[operation]='upstream'
            else:b['cases'][0][operation]='invalid'
            with self.subTest(operation=operation),self.assertRaises(ValueError):r.compare(self.corpus,a,b)
    def test_bad_corpus_values(self):
        for key,value in [('device_scale_factor',True),('device_scale_factor',3),('width',-1),('height',float('nan')),('padding',[1]),('border',[0,0,0,-1]),('align_self',[]),('children',[[True,1]]),('expected_fixed_mismatch',1),('layout_observation','children-only')]:
            corpus=copy.deepcopy(self.corpus);corpus['cases'][0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):r.validate(corpus)
    def test_build_rejects_changed_source_bytes_even_same_head(self):
        base={name:dict(revision='r',tree='t',source_sha256='s',files={'a':'hash'}) for name in ('upstream','moonbit','suite')}
        build={'sources':copy.deepcopy(base),'pins_sha256':r.sha(r.ROOT/'root_box_pins.json'),'executables':{}}
        for name in base:
            changed=copy.deepcopy(base);changed[name]['source_sha256']='changed'
            with patch.object(r,'validate_pins'),self.assertRaisesRegex(ValueError,'source_sha256'):r.validate_build(build,changed,{})
    def test_reuse_rejects_adapter_change_but_allows_recorded_corpus_change(self):
        base={name:dict(revision='r',tree='t',source_sha256='s',files={'a':'hash'}) for name in ('upstream','moonbit','suite')}
        base['suite']['files']={'adapters/root_box/moonbit/main.mbt':'same','root_box_scenarios.json':'old'}
        changed=copy.deepcopy(base);changed['suite']['files']['root_box_scenarios.json']='new'
        with patch.object(attester,'validate_pins'):
            self.assertEqual(attester.verify_source_equivalence(base,changed),['root_box_scenarios.json'])
            changed['suite']['files']['.github/workflows/harness.yml']='wired'
            self.assertEqual(attester.verify_source_equivalence(base,changed),['.github/workflows/harness.yml','root_box_scenarios.json'])
            unrelated=copy.deepcopy(changed)
            unrelated['suite']['files']['.github/workflows/other.yml']='not-authorized'
            with self.assertRaisesRegex(ValueError,'compiled or unrelated'):attester.verify_source_equivalence(base,unrelated)
            changed['suite']['files']['adapters/root_box/moonbit/main.mbt']='new'
            with self.assertRaisesRegex(ValueError,'compiled or unrelated'):attester.verify_source_equivalence(base,changed)
    def test_reuse_rejects_core_change(self):
        base={name:dict(revision='r',tree='t',source_sha256='s',files={'a':'hash'}) for name in ('upstream','moonbit','suite')}
        changed=copy.deepcopy(base);changed['moonbit']['source_sha256']='changed'
        with patch.object(attester,'validate_pins'),self.assertRaisesRegex(ValueError,'Compiled moonbit'):attester.verify_source_equivalence(base,changed)
    def test_finite_zero_viewport_is_valid_input(self):
        self.corpus['cases'][0]['width']=0
        r.validate(self.corpus)

if __name__=='__main__':unittest.main()
