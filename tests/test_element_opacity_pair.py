"""Synthetic contract unit tests only. These never assert real framework execution."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'diagnostics/element_opacity_pair'))
import compare
import evidence
import support

class ContractTests(unittest.TestCase):
    def setUp(self):
        self.fixture=compare.load(ROOT/'diagnostics/element_opacity_pair/scenarios.json')
        self.tokens={'rust':'rust-synthetic-unit-test','candidate':'moon-synthetic-unit-test'}
    def traces(self):
        traces=[]
        colors={v:k for k,v in compare.COLORS.items()}
        for backend,key in [('rust-gpui','rust'),('moonbit-core','candidate')]:
            trace={'schema_version':1,'backend':backend,'run_token':self.tokens[key],'input':copy.deepcopy(self.fixture),'cases':[]}
            if key=='rust':trace['upstream_revision']=compare.UPSTREAM
            for case in self.fixture['cases']:
                ids=[2,3,4,5]+([7] if case['nested'] else [])
                order=[2,5,3,4,7] if case['nested'] else [2,5,3,4] if case['deferred'] else [2,3,4,5]
                alpha=compare.expected_alpha(case)
                quads=[{'bounds':[0,0,20,20],'clip':[0,0,240,180],'rgba':list(colors[i])+[alpha[i]]} for i in order if i in alpha]
                row={'id':case['id'],'bounds':[{'id':i,'bounds':[0,0,20,20]} for i in ids],'target':4,'quads':quads}
                if key=='candidate':
                    row['raw_alpha']=[{'id':i,'alpha':case['alpha']/255 if i==4 else 1,'opacity':alpha.get(i,0)/(case['alpha']/255 if i==4 else 1)} for i in order]
                trace['cases'].append(row)
            traces.append(trace)
        return traces
    def test_synthetic_projection(self):
        self.assertTrue(compare.compare(*self.traces(),self.fixture,self.tokens)['strict_match'])
    def test_omitted_parent_multiplication(self):
        r,c=self.traces();c['cases'][2]['quads'][1]['rgba'][3]*=2
        with self.assertRaisesRegex(ValueError,'source opacity'):compare.compare(r,c,self.fixture,self.tokens)
    def test_doubled_parent_multiplication(self):
        r,c=self.traces();c['cases'][2]['quads'][1]['rgba'][3]*=.5
        with self.assertRaisesRegex(ValueError,'source opacity'):compare.compare(r,c,self.fixture,self.tokens)
    def test_overwrite_parent_with_local(self):
        r,c=self.traces();c['cases'][2]['quads'][2]['rgba'][3]=.5
        with self.assertRaises(ValueError):compare.compare(r,c,self.fixture,self.tokens)
    def test_sibling_scope_leak(self):
        r,c=self.traces();c['cases'][2]['quads'][-1]['rgba'][3]=.5
        with self.assertRaises(ValueError):compare.compare(r,c,self.fixture,self.tokens)
    def test_missing_nested_layer(self):
        r,c=self.traces();c['cases'][-1]['quads'].pop()
        with self.assertRaises(ValueError):compare.compare(r,c,self.fixture,self.tokens)
    def test_deferred_must_not_inherit_parent(self):
        r,c=self.traces();c['cases'][-2]['quads'][2]['rgba'][3]*=.5
        with self.assertRaises(ValueError):compare.compare(r,c,self.fixture,self.tokens)
    def test_zero_still_receives_input(self):
        r,c=self.traces();c['cases'][5]['target']=None
        with self.assertRaises(ValueError):compare.compare(r,c,self.fixture,self.tokens)
    def test_geometry_difference(self):
        r,c=self.traces();c['cases'][0]['bounds'][0]['bounds'][2]+=1
        self.assertFalse(compare.compare(r,c,self.fixture,self.tokens)['strict_match'])
    def test_clip_difference(self):
        r,c=self.traces();c['cases'][6]['quads'][1]['clip'][2]-=1
        self.assertFalse(compare.compare(r,c,self.fixture,self.tokens)['strict_match'])
    def test_raw_alpha_cannot_hide_double_application(self):
        r,c=self.traces();c['cases'][4]['raw_alpha'][2]['opacity']*=.5
        with self.assertRaisesRegex(ValueError,'raw/projected'):compare.compare(r,c,self.fixture,self.tokens)
    def test_stale_capture_challenge(self):
        r,c=self.traces();c['run_token']='old-token'
        with self.assertRaisesRegex(ValueError,'run token'):compare.compare(r,c,self.fixture,self.tokens)
    def test_stale_rust_source(self):
        r,c=self.traces();r['upstream_revision']='0'*40
        with self.assertRaisesRegex(ValueError,'Rust revision'):compare.compare(r,c,self.fixture,self.tokens)
    def test_shared_output_cannot_claim_two_executions(self):
        with self.assertRaises(ValueError):compare.compare(*self.traces(),self.fixture,{'rust':'same','candidate':'same'})
    def test_missing_runtime_is_not_execution(self):
        with tempfile.TemporaryDirectory() as path:
            Path(path,'raw.json').write_text(json.dumps(self.traces()))
            with self.assertRaises(ValueError):evidence.verify(Path(path))
    def test_missing_node_runtime_bytes(self):
        with tempfile.TemporaryDirectory() as path:
            root=Path(path);(root/'tools').mkdir();tools={}
            for name in ('moon','moonc','node'):
                (root/'tools'/name).write_bytes(b'synthetic-'+name.encode())
                tools[name]={'sha256':support.digest(root/'tools'/name)}
            evidence.verify_runtime_tools(root,tools)
            (root/'tools/node').unlink()
            with self.assertRaisesRegex(ValueError,'missing file'):evidence.verify_runtime_tools(root,tools)
    def test_committed_source_proof_rejects_stale_blob(self):
        with tempfile.TemporaryDirectory() as path:
            root=Path(path);blob=support.object_id('blob',b'source')
            tree=b'100644 main.mbt\0'+bytes.fromhex(blob)
            tree_id=support.object_id('tree',tree);(root/tree_id).write_bytes(tree)
            commit=('tree '+tree_id+'\n\nsynthetic commit\n').encode()
            commit_id=support.object_id('commit',commit);(root/commit_id).write_bytes(commit)
            support.verify_git_proof(root,commit_id,tree_id,{'main.mbt':blob})
            with self.assertRaisesRegex(ValueError,'committed tree'):
                support.verify_git_proof(root,commit_id,tree_id,{'main.mbt':'0'*40})
    def test_disjoint_quad_reordering_allowed(self):
        r,c=self.traces()
        for trace in (r,c):
            trace['cases'][0]['quads'][-1]['bounds']=[100,0,20,20]
        c['cases'][0]['quads'].insert(0,c['cases'][0]['quads'].pop())
        self.assertTrue(compare.compare(r,c,self.fixture,self.tokens)['strict_match'])
    def test_overlapping_quad_reordering_rejected(self):
        r,c=self.traces();c['cases'][0]['quads'].reverse()
        self.assertFalse(compare.compare(r,c,self.fixture,self.tokens)['strict_match'])
    def test_unbound_profile_fails_closed(self):
        profile=compare.load(ROOT/'diagnostics/element_opacity_pair/profile.json')
        if profile['status']=='draft_unbound':
            with tempfile.TemporaryDirectory() as path:
                Path(path,'manifest.json').write_text('{}')
                with self.assertRaisesRegex(ValueError,'unbound'):evidence.verify(Path(path))

if __name__=='__main__':unittest.main()
