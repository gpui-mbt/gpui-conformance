"""Synthetic source/comparator tests only; never actual runtime evidence."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('image_compare',ROOT/'diagnostics/image_resource_pair/compare.py')
compare=importlib.util.module_from_spec(spec);spec.loader.exec_module(compare)

def synthetic_pair():
    rust={'backend':'actual-rust-gpui-test-platform','run_token':'synthetic-test-only','cases':[]}
    core={'backend':'actual-moonbit-core','run_token':'synthetic-test-only','cases':[]}
    for name in ['original_png_nested','original_png_clipped','portrait_contain','painter_order']:
        width=20 if name=='original_png_clipped' else 32
        rects=[[25,0,50,100]] if name=='portrait_contain' else [[0,0,32,32],[width,0,32,32]]
        opacities=[1] if name=='portrait_contain' else [.25,1]
        def rect(b):return dict(zip(['x','y','width','height'],b))
        clips=[[0,0,100,100]] if name=='portrait_contain' else [[0,0,width,32],[0,0,160,120]]
        items=[{'kind':'image','bounds':rect(b),'image_bounds':rect([0,0,100,100] if name=='portrait_contain' else b),'opacity':o,'clip_chain_id':i+1} for i,(b,o) in enumerate(zip(rects,opacities))]
        snapshot={'viewport':rect([0,0,160,120]),'items':items,'clip_chains':[{'id':i+1,'rects':[rect(c)]} for i,c in enumerate(clips)]}
        rust['cases'].append({'case':name,'viewport':[160,120],'sprites':[{'bounds':b,'opacity':o,'content_mask':c} for b,o,c in zip(rects,opacities,clips)]})
        core['cases'].append({'case':name,'frame':{'snapshot':snapshot}})
    return rust,core

class SourceTests(unittest.TestCase):
    def test_original_asset_identity(self):
        b=(ROOT/'assets/app-icon.png').read_bytes()
        self.assertEqual(len(b),168173)
        self.assertEqual(hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest(),'08b6d8afa0d1088e50f1e9697e01407c9c623f6d')
        self.assertEqual(hashlib.sha256(b).hexdigest(),'77453d98d46494b3b34b94aa863b686ea299e0190030a5c7ca5377b238332522')
    def test_geometry_asset_identity(self):
        self.assertEqual(hashlib.sha256((ROOT/'assets/portrait.png').read_bytes()).hexdigest(),'5ee1c4f5612fcc49c0bf14d1a4b774f9ba7ae4249ceec93869c9f9ba68493f0f')
    def test_comparator_positive_synthetic(self):
        self.assertEqual(compare.compare(*synthetic_pair())['status'],'passed-numerical-sprite-proof')
    def test_comparator_rejects_bad_runtime_shapes(self):
        mutations=[lambda c:c['cases'][0]['frame']['snapshot']['items'].pop(),
            lambda c:c['cases'][0]['frame']['snapshot']['items'][0].update(opacity=.0625),
            lambda c:c['cases'][0]['frame']['snapshot']['items'][0].update(opacity=1),
            lambda c:c['cases'][2]['frame']['snapshot']['items'][0]['bounds'].update(x=0,width=100),
            lambda c:c['cases'][1]['frame']['snapshot']['clip_chains'][0]['rects'][0].update(width=32),
            lambda c:c.update(run_token='wrong')]
        for mutate in mutations:
            r,c=synthetic_pair();mutate(c)
            with self.assertRaises(AssertionError):compare.compare(r,c)
    def test_actual_viewport_is_required(self):
        r,c=synthetic_pair();r['cases'][0]['viewport']=[1920,1080]
        with self.assertRaises(AssertionError):compare.compare(r,c)
    def test_profile_fail_closed_until_exact_pin(self):
        p=json.loads((ROOT/'diagnostics/image_resource_pair/profile.json').read_text())
        if p['status']=='bound':
            self.assertRegex(p['core_commit'],r'^[0-9a-f]{40}$');self.assertRegex(p['core_tree'],r'^[0-9a-f]{40}$')
        else:self.assertIsNone(p['core_commit']);self.assertIsNone(p['core_tree'])

if __name__=='__main__':unittest.main()
