#!/usr/bin/env python3
"""Comparator fault injection into copies of an actual original oracle PNG.
These checks never claim a mutated PNG is an independently rendered runtime.
Compiled source controls are captured separately by pattern-pair-browser.mjs.
Set PATTERN_RUST_PNG to a retained unchanged-Rust original browser screenshot.
"""
import importlib.util, json, os, unittest
from pathlib import Path
from PIL import Image
spec=importlib.util.spec_from_file_location('pattern_compare',Path(__file__).with_name('pattern-compare.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class ContractTests(unittest.TestCase):
    def test_frozen_source_contract(self):
        c=json.loads(m.CONTRACT.read_text())
        self.assertEqual(c['upstream']['source_blob'],'7d2e98d16e24dc23dc307296a3b35c18e624d9e3')
        self.assertEqual([r['height'] for r in c['rows']],[18]*4+[56]*3+[26])
        self.assertEqual([r['interval'] for r in c['rows'][:4]],[4.5,4.5,4.5,9])
        self.assertEqual(set(c['controls']),{'wrong_interval','wrong_phase','wrong_color','missing_row','missing_runtime'})
    def test_missing_runtime_blank_canvas_fails(self):
        blank=Image.new('RGBA',(600,600),'white')
        with self.assertRaisesRegex(AssertionError,'four connected blue source borders'):m.compare(blank,blank)

@unittest.skipUnless(os.environ.get('PATTERN_RUST_PNG'),'requires actual retained Rust browser PNG; no synthetic reference')
class ActualOracleMutationTests(unittest.TestCase):
    def setUp(self):
        self.oracle=Image.open(os.environ['PATTERN_RUST_PNG']).convert('RGBA');self.regions=dict(m.regions(m.blue_boxes(self.oracle)))
    def reject(self,image,region):
        with self.assertRaisesRegex(AssertionError,region):m.compare(self.oracle,image)
    def test_actual_blue_stripes_are_not_closed_borders(self):
        diagnostics={};boxes=m.blue_boxes(self.oracle,diagnostics)
        self.assertEqual(len(boxes),4)
        self.assertTrue(all(c['closed_perimeter'] for c in diagnostics['largest_components'] if c['bounds'] in boxes))
        self.assertTrue(any(not c['closed_perimeter'] and c['bounds'][2]-c['bounds'][0]>=50 and c['bounds'][3]-c['bounds'][1]>=30 for c in diagnostics['largest_components']))
    def test_unchanged_actual_oracle_self_check(self):m.compare(self.oracle,self.oracle.copy())
    def test_wrong_interval(self):
        candidate=self.oracle.copy();x,y,w,h=self.regions['red4'];sx,sy,_,_=self.regions['red3']
        candidate.paste(self.oracle.crop((sx,sy,sx+w,sy+h)),(x,y));self.reject(candidate,'red4')
    def test_wrong_phase(self):
        candidate=self.oracle.copy();x,y,w,h=self.regions['red2']
        row=self.oracle.crop((x,y,x+w,y+h));candidate.paste(row.crop((0,0,w-2,h)),(x+2,y));candidate.paste(row.crop((w-2,0,w,h)),(x,y));self.reject(candidate,'red2')
    def test_wrong_color(self):
        candidate=self.oracle.copy();x,y,w,h=self.regions['red1']
        for yy in range(y,y+h):
            for xx in range(x,x+w):
                r,g,b,a=candidate.getpixel((xx,yy))
                if r>200 and g<50 and b<50:candidate.putpixel((xx,yy),(0,255,0,a))
        self.reject(candidate,'red1')
    def test_missing_row(self):
        candidate=self.oracle.copy();x,y,w,h=self.regions['short_yellow'];candidate.paste((214,235,214,255),(x,y,x+w,y+h));self.reject(candidate,'short_yellow')
    def test_wrong_green_alpha(self):
        candidate=self.oracle.copy();x,y,w,h=self.regions['large_red']
        for yy in range(y,y+h):
            for xx in range(x,x+w):
                r,g,b,a=candidate.getpixel((xx,yy))
                if g>230 and r>200 and b>200:candidate.putpixel((xx,yy),(255,255,255,a))
        self.reject(candidate,'large_red')
if __name__=='__main__':unittest.main(verbosity=2)
