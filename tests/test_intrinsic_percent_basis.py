"""Synthetic schema/comparison contracts, not actual GPUI parity evidence."""
import copy
import json
import unittest
import tempfile
from pathlib import Path
import build_flex_basis as b
from unittest.mock import patch
import run_flex_basis as r

class IntrinsicPercentBasisTests(unittest.TestCase):
    def setUp(self):
        self.corpus=json.loads((r.ROOT/'intrinsic_percent_basis_scenarios.json').read_text())
    def test_shared_production_branch_mutation(self):
        fixture = """prefix
fn intrinsic_percent_contribution(
  item : FlexItem,
  preferred : Double?,
  has_children : Bool,
) -> Result[Double, TreeLayoutError] {
  match preferred {
    Some(value) => Ok(value)
    None => if has_children { Err(UnsupportedIntrinsicFlexBasis) } else { Ok(0.0) }
  }
}
suffix
"""
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'layout').mkdir();path=root/'layout/tree.mbt';path.write_text(fixture)
            mutation=b.disable_flex_basis(root,r.INTRINSIC_PERCENT_CONTROL)
            self.assertEqual(mutation['file'],'layout/tree.mbt')
            self.assertEqual(path.read_text(),fixture.replace('Some(value) => Ok(value)','Some(_) => Ok(0.0)'))
            self.assertNotEqual(mutation['original_sha256'],mutation['mutated_sha256'])
            with self.assertRaises(ValueError):b.disable_flex_basis(root,r.INTRINSIC_PERCENT_CONTROL)
    def test_mutation_manifest_is_bound_to_full_source(self):
        fixture='fn intrinsic_percent_contribution(\n) {\n  Some(value) => Ok(value)\n}\n'
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source';mutant=root/'mutant'
            for directory in (source,mutant):
                (directory/'layout').mkdir(parents=True);(directory/'layout/tree.mbt').write_text(fixture)
            pins=root/'pins.json';pins.write_text(json.dumps({'schema_version':1,'capability_control':r.INTRINSIC_PERCENT_CONTROL}))
            sources={name:{'revision':'r','tree':'t','source_sha256':'s','files':{'layout/tree.mbt':r.sha(source/'layout/tree.mbt')},'path':str(source)} for name in ('upstream','moonbit','suite')}
            mutation=b.disable_flex_basis(mutant,r.INTRINSIC_PERCENT_CONTROL)
            manifest={'sources':copy.deepcopy(sources),'pins_sha256':r.sha(pins),'control_kind':r.INTRINSIC_PERCENT_CONTROL,
                      'basis_parser':r.basis_parser_identity(r.INTRINSIC_PERCENT_CONTROL),'disable_flex_basis':True,'mutation':mutation,'executables':{}}
            with patch.object(r,'validate_pins'):
                r.validate_build(manifest,sources,{},pins)
                for key,value in [('kind',r.PERCENT_CONTROL),('file','layout/layout.mbt'),('original_sha256','changed'),
                                  ('mutated_sha256','changed'),('original_function','wrong'),('mutated_function','ignored')]:
                    changed=copy.deepcopy(manifest);changed['mutation'][key]=value
                    with self.subTest(key=key),self.assertRaises(ValueError):r.validate_build(changed,sources,{},pins)
    def test_parser_is_percent_without_adapter_changes(self):
        identity=r.basis_parser_identity(r.INTRINSIC_PERCENT_CONTROL)
        self.assertEqual(identity['source_path'],'adapters/percent_basis/moonbit/basis.mbt')
        self.assertEqual(identity['sha256'],r.basis_parser_identity(r.PERCENT_CONTROL)['sha256'])
    def test_exact_pins_and_mutation_expectations(self):
        path=r.ROOT/'intrinsic_percent_basis_pins.json';pins=json.loads(path.read_text())
        self.assertEqual(pins['capability_control'],r.INTRINSIC_PERCENT_CONTROL)
        self.assertEqual(pins['upstream']['revision'],'5a5fbe79917971a4d52a96b6ddb04da198a5012e')
        sources={name:{**pins[name],'dirty':False} for name in ('upstream','moonbit')}
        r.validate_pins(sources,path)
        for name in sources:
            for key in ('revision','tree'):
                self.assertRegex(pins[name][key],r'^[0-9a-f]{40}$')
                changed=copy.deepcopy(sources);changed[name][key]='0'*40
                with self.assertRaises(ValueError):r.validate_pins(changed,path)
        self.assertEqual(sum(c['expected_capability_mismatch'] for c in self.corpus['cases']),84)
    def test_coverage(self):
        r.validate(self.corpus)
        self.assertEqual(len(self.corpus['cases']),144)
        for direction in ('row','row_reverse','column','column_reverse'):
            for scale in (1,1.5,2):
                rows=[c for c in self.corpus['cases'] if c['direction']==direction and c['device_scale_factor']==scale]
                self.assertEqual(len(rows),12)
                self.assertTrue(all(len(c['children'])==3 for c in rows))
        self.assertTrue(all('expected_bounds' not in c for c in self.corpus['cases']))
    def test_explicit_profile_required(self):
        for profile in (None,'intrinsic_basis','unknown'):
            c=copy.deepcopy(self.corpus)
            if profile is None: del c['profile']
            else: c['profile']=profile
            with self.subTest(profile=profile),self.assertRaises(ValueError):r.validate(c)
    def test_old_profile_restrictions_retained(self):
        c=json.loads((r.ROOT/'intrinsic_basis_scenarios.json').read_text())
        r.validate(c)
        c['capability_control']=r.PERCENT_CONTROL
        with self.assertRaises(ValueError):r.validate(c)
    def test_reject_out_of_scope(self):
        for key,value in [('intrinsic_parent',False),('intrinsic_parent',1),('wrap','wrap'),
                          ('grow',[0,1,0]),('shrink',[0,0,1]),('container_cross',None),
                          ('parent_offset_x',1),('children',[[{'percent':.5},10],[20,12],[30,8]]),
                          ('flex_basis',[{'content':1},None,None])]:
            c=copy.deepcopy(self.corpus);c['cases'][0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):r.validate(c)
        c=copy.deepcopy(self.corpus);c['capability_control']=r.POINTS_CONTROL
        with self.assertRaises(ValueError):r.validate(c)
    def observations(self,implementation):
        rows=[]
        for c in self.corpus['cases']:
            viewport=[0,0,c['width'],c['height']]
            obs={'bounds':[viewport.copy()]+[[0,0,1,1] for _ in range(4)],'device_scale_factor':c['device_scale_factor']}
            if implementation=='upstream':obs['test_window_viewport']=viewport.copy()
            else:obs.update(physical_viewport=viewport.copy(),snapshot_viewport=viewport.copy())
            rows.append(dict(id=c['id'],status='observed',layer='headless-layout',observation=obs))
        return dict(implementation=implementation,cases=rows)
    def test_every_rectangle_coordinate_compared(self):
        for node in range(5):
            for axis in range(4):
                a,b=self.observations('upstream'),self.observations('moonbit')
                b['cases'][0]['observation']['bounds'][node][axis]+=1
                result=r.compare(self.corpus,a,b)
                self.assertEqual(result['summary']['mismatch'],1)
                self.assertEqual(result['cases'][0]['differences'][0]['path'],f'bounds[{node}][{axis}]')
    def test_viewport_and_scale_are_exact(self):
        for key in ('physical_viewport','snapshot_viewport'):
            a,b=self.observations('upstream'),self.observations('moonbit')
            b['cases'][0]['observation'][key][2]+=1e-8
            with self.assertRaises(ValueError):r.compare(self.corpus,a,b)
        a,b=self.observations('upstream'),self.observations('moonbit')
        b['cases'][0]['observation']['device_scale_factor']=2
        with self.assertRaises(ValueError):r.compare(self.corpus,a,b)

if __name__=='__main__': unittest.main()
