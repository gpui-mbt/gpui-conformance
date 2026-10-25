"""Synthetic nested-profile evidence tests; not runtime qualification."""
import copy
import json
import unittest
import run_flex_basis as r

class IntrinsicBasisTests(unittest.TestCase):
    def setUp(self):
        self.corpus=json.loads((r.ROOT/'intrinsic_basis_scenarios.json').read_text())
    def observations(self,implementation):
        rows=[]
        for c in self.corpus['cases']:
            viewport=[0,0,c['width'],c['height']]
            o={'bounds':[viewport.copy()]+[[0,0,1,1] for _ in range(len(c['children'])+1)],
               'device_scale_factor':c['device_scale_factor']}
            if implementation=='upstream': o['test_window_viewport']=viewport.copy()
            else: o.update(physical_viewport=viewport.copy(),snapshot_viewport=viewport.copy())
            rows.append(dict(id=c['id'],layer='headless-layout',status='observed',observation=o))
        return dict(implementation=implementation,cases=rows)
    def test_coverage(self):
        r.validate(self.corpus)
        self.assertEqual(len(self.corpus['cases']),132)
        self.assertEqual(sum(c['expected_capability_mismatch'] for c in self.corpus['cases']),96)
        for direction in ['row','column','row_reverse','column_reverse']:
            for scale in [1,1.5,2]:
                cases=[c for c in self.corpus['cases'] if c['direction']==direction and c['device_scale_factor']==scale]
                self.assertEqual(len(cases),11)
                self.assertTrue(all(c['intrinsic_parent'] and c['grow']==[0]*3 and c['shrink']==[0]*3 for c in cases))
    def test_identical_full_rectangles(self):
        self.assertEqual(r.compare(self.corpus,self.observations('upstream'),self.observations('moonbit'))['summary'],
                         {'total':132,'pass':132,'mismatch':0})
    def test_outer_container_and_every_child_coordinate_compared(self):
        for node in range(5):
            for coordinate in range(4):
                a,b=self.observations('upstream'),self.observations('moonbit')
                b['cases'][0]['observation']['bounds'][node][coordinate]+=1
                result=r.compare(self.corpus,a,b)
                self.assertEqual(result['summary']['mismatch'],1)
                self.assertEqual(result['cases'][0]['differences'][0]['path'],f'bounds[{node}][{coordinate}]')
    def test_missing_container_not_projected_away(self):
        a,b=self.observations('upstream'),self.observations('moonbit')
        for record in (a,b):record['cases'][0]['observation']['bounds'].pop(1)
        with self.assertRaises(ValueError):r.compare(self.corpus,a,b)
    def test_unsupported_intrinsic_profiles_rejected(self):
        for key,value in [('intrinsic_parent',1),('container_cross',None),('container_cross',-1),
                          ('wrap','wrap'),('grow',[1,0,0]),('shrink',[0,1,0])]:
            c=copy.deepcopy(self.corpus);c['cases'][0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):r.validate(c)
        c=copy.deepcopy(self.corpus);c['capability_control']=r.PERCENT_CONTROL
        with self.assertRaises(ValueError):r.validate(c)
    def test_profile_not_synthetic_expected_geometry(self):
        for c in self.corpus['cases']:
            self.assertNotIn('expected_bounds',c)
        rust=(r.ROOT/'adapters/flex_basis/rust/src/main.rs').read_text()
        moon=(r.ROOT/'adapters/flex_basis/moonbit/main.mbt').read_text()
        self.assertIn('Some(Length::Auto)',rust)
        self.assertIn('outer.child(root)',rust)
        self.assertIn('nested.then_some("outer")',rust)
        self.assertIn('@layout.Dimension::auto()',moon)
        self.assertIn('@element.Element::new(item).with_children_style(style)',moon)
        self.assertIn('tree().nodes().map(node => bounds(node.bounds()))',moon)

if __name__=='__main__': unittest.main()
