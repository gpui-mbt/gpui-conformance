import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,mkdtempSync,writeFileSync,rmSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {INPUTS,ROOT,committedSuite,assertSuite,assertInputs,binding,assertBindings,assertRuntime} from './gradient-diagnostic-provenance.mjs';
import {sha256} from './gradient-diagnostic-contract.mjs';
const suite={commit:'a'.repeat(40),tree:'b'.repeat(40),files:new Map(INPUTS.suite_inputs.map(p=>[p,readFileSync(ROOT+'/'+p)]))};
function fixture(){
 const m={suite_commit:suite.commit,suite_tree:suite.tree,suite_inputs:Object.fromEntries([...suite.files].map(([p,b])=>[p,sha256(b)]))};
 const assets=new Map(Object.entries(INPUTS.fixed_inputs).map(([p,source])=>[p,suite.files.get(source)]));
 const records=INPUTS.suite_inputs.map(suite_path=>({suite_path}));return {m,assets,records};
}
test('complete committed input contract accepts exact source bytes',()=>{const {m,assets,records}=fixture();assertInputs(records,assets,suite,m);});
test('omitted, extra and duplicate review inputs fail independently',()=>{
 for(const mutate of [r=>r.pop(),r=>r.push({suite_path:'unreviewed.js'}),r=>{r[1]=r[0];},r=>r.splice(0)]){const {m,assets,records}=fixture();mutate(records);assert.throws(()=>assertInputs(records,assets,suite,m));}
});
test('stale suite commit/tree, source hashes and rehashed alternate host fail independently',()=>{
 for(const key of ['suite_commit','suite_tree']){const {m}=fixture();m[key]='0'.repeat(40);assert.throws(()=>assertSuite(m,suite));}
 {const {m}=fixture();m.suite_inputs[INPUTS.suite_inputs[0]]='0'.repeat(64);assert.throws(()=>assertSuite(m,suite));}
 {const {m,assets,records}=fixture();assets.set('host.mjs',Buffer.from('alternate host'));m.files={'host.mjs':sha256(assets.get('host.mjs'))};assert.throws(()=>assertInputs(records,assets,suite,m));}
});
function capture(){const {m}=fixture();const r={session:'12345678-1234-4234-8234-123456789abc',document_id:'12345678-1234-4234-8234-123456789abd',url:'http://127.0.0.1:1234/',manifest:{sha256:'c'.repeat(64)}};
 const b=binding(r,m);r.observed_document={document_id:r.document_id,url:r.url,width:1000,height:900,dpr:1};r.responses=[{ordinal:1,url:r.url,binding:{...b,response_ordinal:1,url:r.url}}];r.screenshots=[1,2].map(ordinal=>({file:'frame-'+ordinal+'.png',ordinal,binding:{...b,capture_ordinal:ordinal}}));r.stable=r.screenshots.map(f=>f.file);r.raw_rgba={binding:b};return {r,m};}
test('session/document/response/capture binding accepts complete identity',()=>{const {r,m}=capture();assertBindings(r,m);});
test('malformed/swapped sessions, responses, routes and duplicate captures rejected',()=>{
 for(const mutate of [r=>r.session='not a UUID',r=>r.responses[0].binding.session='12345678-1234-4234-8234-123456789abe',r=>r.responses[0].binding.url+='elsewhere',r=>r.responses.push(r.responses[0]),r=>r.screenshots.push(r.screenshots[0]),r=>r.screenshots[0].binding.document_id='12345678-1234-4234-8234-123456789abe',r=>r.observed_document.width=999,r=>r.stable[1]=r.stable[0]]){const {r,m}=capture();mutate(r);assert.throws(()=>assertBindings(r,m));}
});
// Tiny structurally valid test module; explicitly not a compiled GPUI runtime.
const leb=n=>{const b=[];do{let x=n&127;n>>>=7;b.push(x|(n?128:0));}while(n);return b;};
const section=(id,b)=>[id,...leb(b.length),...b];const str=s=>[...leb(s.length),...Buffer.from(s)];
const wasm=Buffer.from([0,97,115,109,1,0,0,0,...section(1,[1,96,0,0]),...section(3,[1,0]),...section(5,[1,0,1]),...section(7,[2,...str('memory'),2,0,...str('__wbindgen_start'),0,0]),...section(10,[1,2,0,11])]);
test('structural runtime gate rejects invalid/template-only bytes, wrong exports/loader and missing worker',()=>{
 const loader=Buffer.from('gradient_diagnostic_bg.wasm __wbg_init __wbindgen_start');const assets=new Map([['gradient_diagnostic_bg.wasm',wasm],['gradient_diagnostic.js',loader]]);const responses=[{url:'blob:http://127.0.0.1:1234/test',type:'script'}];assertRuntime(assets,responses);
 assert.throws(()=>assertRuntime(assets,[]));
 for(const invalid of [Buffer.from('template only'),Buffer.from([0,97,115,109,1,0,0,0])]){const a=new Map(assets);a.set('gradient_diagnostic_bg.wasm',invalid);assert.throws(()=>assertRuntime(a,responses));}
 const a=new Map(assets);a.set('gradient_diagnostic.js',Buffer.from('unlinked loader'));assert.throws(()=>assertRuntime(a,responses));
});
test('dirty staged source is rejected before committed input lookup',()=>{
 const root=mkdtempSync('/tmp/gradient-dirty-source-');try{execFileSync('git',['init','-q'],{cwd:root});writeFileSync(root+'/tracked','dirty');execFileSync('git',['add','tracked'],{cwd:root});assert.throws(()=>committedSuite(root),/Dirty tracked suite source/);}finally{rmSync(root,{recursive:true,force:true});}
});
