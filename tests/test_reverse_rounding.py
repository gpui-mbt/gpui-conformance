"""Synthetic coverage and full-rectangle/batch contracts, not parity evidence."""
import copy
import json
import unittest
import run_flex_basis as r
from run_reverse_rounding import chunks

class ReverseRoundingTests(unittest.TestCase):
    def setUp(self): self.corpus=json.loads((r.ROOT/'reverse_rounding_scenarios.json').read_text())
    def test_coverage(self):
        r.validate(self.corpus)
        self.assertEqual(len(self.corpus['cases']),1297)
        for key,values in [('direction',{'row','column','row_reverse','column_reverse'}),('wrap',{'nowrap','wrap','wrap_reverse'}),('justify',{'space-around','space-between','space-evenly'}),('device_scale_factor',{1,1.5,2})]:
            self.assertEqual({c[key] for c in self.corpus['cases']},values)
        self.assertEqual({len(c['children']) for c in self.corpus['cases']},{2,3,4,5})
        self.assertTrue(any(c['id']=='round-original-intrinsic-fractional' for c in self.corpus['cases']))
    def test_batches_preserve_every_case_and_order(self):
        batches=list(chunks(self.corpus['cases'],64))
        self.assertTrue(all(len(b)<=64 for b in batches))
        self.assertEqual([c for b in batches for c in b],self.corpus['cases'])
    def test_all_five_children_observed(self):
        source=(r.ROOT/'adapters/flex_basis/rust/src/main.rs').read_text()
        self.assertIn('let selectors = ["a", "b", "c", "d", "e", "f", "g"];',source)
        c=next(c for c in self.corpus['cases'] if len(c['children'])==5)
        corpus={**self.corpus,'cases':[c]}; viewport=[0,0,c['width'],c['height']]
        a={'implementation':'upstream','cases':[{'id':c['id'],'status':'observed','layer':'headless-layout','observation':{'bounds':[viewport]+[[0,0,1,1]]*5,'test_window_viewport':viewport,'device_scale_factor':c['device_scale_factor']}}]}
        b=copy.deepcopy(a);b['implementation']='moonbit';o=b['cases'][0]['observation'];o.pop('test_window_viewport');o.update(physical_viewport=viewport,snapshot_viewport=viewport)
        self.assertEqual(r.compare(corpus,a,b)['summary']['pass'],1)
        for index in range(6):
            changed=copy.deepcopy(b);changed['cases'][0]['observation']['bounds'][index][0]+=1
            self.assertEqual(r.compare(corpus,a,changed)['summary']['mismatch'],1)
        o['bounds'].pop()
        with self.assertRaises(ValueError):r.compare(corpus,a,b)
    def test_eight_children_rejected(self):
        c=copy.deepcopy(self.corpus);c['cases'][0]['children']=[[1,1]]*8
        with self.assertRaises(ValueError):r.validate(c)

if __name__=='__main__':unittest.main()

class SpacingMutationTests(unittest.TestCase):
    def test_exact_production_fallback_mutation(self):
        import tempfile
        from pathlib import Path
        from build_flex_basis import disable_flex_basis
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'layout').mkdir()
            source='fn device_distributed_starts(\n  sizes : Array[Double],\n) -> Array[Double]? {\n  if sizes.length() <= 1 || false { return None }\n  Some(sizes)\n}\n'
            f=root/'layout/layout.mbt';f.write_text(source)
            evidence=disable_flex_basis(root,r.SPACING_CONTROL)
            self.assertEqual(f.read_text(),source.replace('if sizes.length() <= 1 ||','if sizes.length() >= 0 ||'))
            self.assertNotEqual(evidence['original_sha256'],evidence['mutated_sha256'])
            self.assertEqual(evidence['kind'],r.SPACING_CONTROL)
    def test_observed_regression_control_ids_retained(self):
        c=json.loads((r.ROOT/'reverse_rounding_scenarios.json').read_text())
        self.assertEqual(c['capability_control'],r.SPACING_CONTROL)
        self.assertEqual(sum(x['expected_capability_mismatch'] for x in c['cases']),35)
    def test_manifest_binds_entire_fallback_mutation(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from build_flex_basis import disable_flex_basis
        source_text='prefix\nfn device_distributed_starts(\n  sizes : Array[Double],\n) -> Array[Double]? {\n  if sizes.length() <= 1 || false { return None }\n  Some(sizes)\n}\nsuffix\n'
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source';mutant=root/'mutant'
            for path in (source,mutant):
                (path/'layout').mkdir(parents=True);(path/'layout/layout.mbt').write_text(source_text)
            pins=root/'pins.json';pins.write_text(json.dumps({'schema_version':1,'capability_control':r.SPACING_CONTROL}))
            sources={name:{'revision':'r','tree':'t','source_sha256':'s','files':{'layout/layout.mbt':r.sha(source/'layout/layout.mbt')},'path':str(source)} for name in ('upstream','moonbit','suite')}
            mutation=disable_flex_basis(mutant,r.SPACING_CONTROL)
            manifest={'sources':copy.deepcopy(sources),'pins_sha256':r.sha(pins),'control_kind':r.SPACING_CONTROL,'basis_parser':r.basis_parser_identity(r.SPACING_CONTROL),'disable_flex_basis':True,'mutation':mutation,'executables':{}}
            with patch.object(r,'validate_pins'):
                r.validate_build(manifest,sources,{},pins)
                for key,value in [('kind',r.POINTS_CONTROL),('file','conformance_probe/main.mbt'),('original_sha256','changed'),('mutated_sha256','changed'),('original_function','wrong'),('mutated_function','return None')]:
                    changed=copy.deepcopy(manifest);changed['mutation'][key]=value
                    with self.subTest(key=key),self.assertRaises(ValueError):r.validate_build(changed,sources,{},pins)
                changed=copy.deepcopy(manifest);changed['disable_flex_basis']=False
                with self.assertRaises(ValueError):r.validate_build(changed,sources,{},pins)
    def test_spacing_profile_rejects_other_mutation_classification(self):
        c=json.loads((r.ROOT/'reverse_rounding_scenarios.json').read_text())
        for kind in (r.POINTS_CONTROL,r.PERCENT_CONTROL):
            with self.assertRaises(ValueError):r.validate_control_mode({'control_kind':kind,'disable_flex_basis':True},c,True)
        r.validate_control_mode({'control_kind':r.SPACING_CONTROL,'disable_flex_basis':True},c,True)

class PercentPreservationTests(unittest.TestCase):
    def test_percent_review_regressions_remain_explicit(self):
        corpus=json.loads((r.ROOT/'reverse_rounding_percent_preservation_scenarios.json').read_text())
        r.validate(corpus)
        self.assertEqual(len(corpus['cases']),11)
        self.assertEqual(corpus['capability_control'],r.PERCENT_CONTROL)
        for case in corpus['cases']:
            self.assertFalse(case['expected_capability_mismatch'])
            self.assertTrue(any(isinstance(b,dict) and 'percent' in b for b in case['flex_basis']))

    def test_review_scale_125_is_accepted_without_tolerance_change(self):
        corpus=json.loads((r.ROOT/'reverse_rounding_percent_preservation_scenarios.json').read_text())
        self.assertTrue(any(c['device_scale_factor']==1.25 for c in corpus['cases']))
        r.validate(corpus)
        bad=copy.deepcopy(corpus);bad['cases'][0]['device_scale_factor']=1.3
        with self.assertRaises(ValueError):r.validate(bad)

class FarEdgePreservationTests(unittest.TestCase):
    def test_seven_child_review_case_is_not_truncated(self):
        corpus=json.loads((r.ROOT/'reverse_rounding_far_edge_scenarios.json').read_text())
        r.validate(corpus)
        c=corpus['cases'][0]
        self.assertEqual(len(c['children']),7)
        self.assertEqual(c['children'],[[3,10],[5,10],[20,10],[10,10],[0,10],[10,10],[1,10]])
        self.assertEqual(c['width'],84)
        self.assertEqual(c['padding'],[0,0,0,2])
        self.assertFalse(c['expected_capability_mismatch'])

class NestedOriginPreservationTests(unittest.TestCase):
    def test_offset_wrapper_is_bounded_and_preserves_rect_count(self):
        corpus=json.loads((r.ROOT/'reverse_rounding_nested_origin_scenarios.json').read_text())
        r.validate(corpus)
        c=corpus['cases'][0]
        self.assertEqual((c['width'],c['parent_offset_x']),(189,47))
        self.assertEqual(c['children'],[[12,10],[20,10],[49,10]])
        bad=copy.deepcopy(corpus);bad['cases'][0]['intrinsic_parent']=True
        with self.assertRaises(ValueError):r.validate(bad)
