"""Synthetic tests for bounded flex-basis evidence; not runtime qualification."""
import copy
import json
import unittest
from unittest.mock import patch
import run_flex_basis as r

class FlexBasisTests(unittest.TestCase):
    def setUp(self):
        self.corpus=json.loads((r.ROOT/'flex_basis_scenarios.json').read_text())
    def observations(self,implementation):
        cases=[]
        for c in self.corpus['cases']:
            rect=[0,0,c['width'],c['height']]
            observation={'bounds':[rect.copy()]+[[0,0,1,1] for _ in c['children']], 'device_scale_factor':c['device_scale_factor']}
            if implementation=='upstream': observation['test_window_viewport']=rect.copy()
            else: observation.update(physical_viewport=rect.copy(),snapshot_viewport=rect.copy())
            cases.append(dict(id=c['id'],layer='headless-layout',status='observed',observation=observation))
        return dict(implementation=implementation,cases=cases)
    def test_coverage_and_ci(self):
        r.validate(self.corpus)
        cases=self.corpus['cases']
        self.assertEqual(len(cases),120)
        self.assertEqual(sum(c['expected_capability_mismatch'] for c in cases),108)
        for direction in ('row','column','row_reverse','column_reverse'):
            for scale in (1,1.5,2):
                self.assertEqual(sum(c['direction']==direction and c['device_scale_factor']==scale for c in cases),10)
        self.assertIn("python3 -m unittest discover -s tests -p 'test_flex_basis.py' -v",(r.ROOT/'.github/workflows/harness.yml').read_text())
    def test_identical_full_bounds_pass(self):
        self.assertEqual(r.compare(self.corpus,self.observations('upstream'),self.observations('moonbit'))['summary'],{'total':120,'pass':120,'mismatch':0})
    def test_every_root_and_child_coordinate_compared(self):
        for node in range(4):
            for coordinate in range(4):
                a,b=self.observations('upstream'),self.observations('moonbit')
                b['cases'][0]['observation']['bounds'][node][coordinate]+=1
                result=r.compare(self.corpus,a,b)
                self.assertEqual(result['summary']['mismatch'],1)
                self.assertEqual(result['cases'][0]['differences'][0]['path'],f'bounds[{node}][{coordinate}]')
    def test_exact_moonbit_viewport_and_observed_scale(self):
        for key in ('physical_viewport','snapshot_viewport','device_scale_factor'):
            a,b=self.observations('upstream'),self.observations('moonbit')
            if key=='device_scale_factor': b['cases'][0]['observation'][key]=2
            else: b['cases'][0]['observation'][key][2]+=1e-10
            with self.assertRaises(ValueError): r.compare(self.corpus,a,b)
    def test_missing_extra_reordered_or_projected_rejected(self):
        for operation in ('missing','extra','reorder','projection','status','layer','implementation'):
            a,b=self.observations('upstream'),self.observations('moonbit')
            if operation=='missing': b['cases'].pop()
            elif operation=='extra': b['cases'].append(copy.deepcopy(b['cases'][0]))
            elif operation=='reorder': b['cases'][0],b['cases'][1]=b['cases'][1],b['cases'][0]
            elif operation=='projection': b['cases'][0]['observation']['line_origins']=[]
            elif operation=='implementation': b[operation]='upstream'
            else: b['cases'][0][operation]='invalid'
            with self.subTest(operation=operation),self.assertRaises(ValueError): r.compare(self.corpus,a,b)
    def test_invalid_basis_and_corpus(self):
        for value in ([],[None],[-1,0,0],[float('nan'),0,0],[float('inf'),0,0],[True,0,0],[{'percent':0.5},0,0],['content',0,0]):
            c=copy.deepcopy(self.corpus);c['cases'][0]['flex_basis']=value
            with self.subTest(value=value),self.assertRaises(ValueError): r.validate(c)
        for key,value in [('device_scale_factor',True),('width',-1),('layout_observation','children-only'),('expected_capability_mismatch',1)]:
            c=copy.deepcopy(self.corpus);c['cases'][0][key]=value
            with self.assertRaises(ValueError):r.validate(c)
    def test_bad_numeric_coordinate_and_size(self):
        for value,coordinate in [(True,0),(float('nan'),0),(float('inf'),0),(-1,2),(-1,3)]:
            a,b=self.observations('upstream'),self.observations('moonbit')
            b['cases'][0]['observation']['bounds'][0][coordinate]=value
            with self.assertRaises(ValueError):r.compare(self.corpus,a,b)
    def test_build_source_bytes_remain_bound(self):
        source={name:dict(revision='r',tree='t',source_sha256='s',files={'a':'hash'}) for name in ('upstream','moonbit','suite')}
        build={'sources':copy.deepcopy(source),'pins_sha256':r.sha(r.ROOT/'flex_basis_pins.json'),'executables':{}}
        for name in source:
            changed=copy.deepcopy(source);changed[name]['source_sha256']='changed'
            with patch.object(r,'validate_pins'),self.assertRaisesRegex(ValueError,'source_sha256'):r.validate_build(build,changed,{})
    def test_observers_use_real_basis_and_production_api(self):
        rust=(r.ROOT/'adapters/flex_basis/rust/src/main.rs').read_text()
        moon=(r.ROOT/'adapters/flex_basis/moonbit/main.mbt').read_text()
        self.assertIn('child.flex_basis(px(basis as f32))',rust)
        self.assertIn('item.with_flex_basis(',moon)
        self.assertIn('@layout.FlexBasis::points',moon)
        self.assertNotIn('GPUI_DISABLE_FLEX_BASIS',moon)


class MutationTests(unittest.TestCase):
    def test_production_mutation_preserves_validation_and_only_changes_resolver(self):
        import tempfile
        from pathlib import Path
        from build_flex_basis import disable_flex_basis
        fixture='prefix\nfn FlexItem::resolved_flex_basis(\n self : FlexItem,\n fallback : Double,\n) -> Result[Double, LayoutError] {\n match self.flex_basis {\n Auto => Ok(fallback)\n Points(value) => if value < 0.0 { Err(NegativeValue) } else { Ok(value) }\n }\n}\nsuffix\n'
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'layout').mkdir();p=root/'layout/layout.mbt';p.write_text(fixture)
            mutation=disable_flex_basis(root)
            self.assertEqual(p.read_text(),fixture.replace('Ok(value)','Ok(fallback)'))
            self.assertNotEqual(mutation['original_sha256'],mutation['mutated_sha256'])
            with self.assertRaises(ValueError):disable_flex_basis(root)

    def test_control_classification_and_mutation_are_bound(self):
        source={name:dict(revision='r',tree='t',source_sha256='s',files={'layout/layout.mbt':'original'}) for name in ('upstream','moonbit','suite')}
        build={'sources':copy.deepcopy(source),'pins_sha256':'pins','executables':{},'disable_flex_basis':False,'mutation':None}
        with patch.object(r,'validate_pins'),patch.object(r,'sha',return_value='pins'):
            r.validate_build(build,source,{})
            for invalid in (None,0,'false'):
                changed=copy.deepcopy(build);changed['disable_flex_basis']=invalid
                with self.assertRaises(ValueError):r.validate_build(changed,source,{})
            changed=copy.deepcopy(build);changed['disable_flex_basis']=True
            with self.assertRaises(ValueError):r.validate_build(changed,source,{})
            changed['mutation']={'kind':'production-points-resolve-as-auto','file':'layout/layout.mbt','original_sha256':'original','mutated_sha256':'mutated'}
            r.validate_build(changed,source,{})
            for key,value in [('kind','adapter'),('file','conformance_probe/main.mbt'),('original_sha256','other'),('mutated_sha256','original')]:
                invalid=copy.deepcopy(changed);invalid['mutation'][key]=value
                with self.assertRaises(ValueError):r.validate_build(invalid,source,{})
            changed['disable_flex_basis']=False
            with self.assertRaises(ValueError):r.validate_build(changed,source,{})

if __name__=='__main__':unittest.main()
