// Committed source and observed transport identity, never semantic color validation.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {sha256} from './gradient-diagnostic-contract.mjs';
export const ROOT=fileURLToPath(new URL('../../',import.meta.url));
export const INPUTS=JSON.parse(readFileSync(new URL('../gradient-diagnostic/provenance-inputs.json',import.meta.url)));
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
export function committedSuite(root=ROOT) {
 const git=(...args)=>execFileSync('git',args,{cwd:root});
 assert.equal(git('status','--porcelain','--untracked-files=no').toString().trim(),'','Dirty tracked suite source');
 const commit=git('rev-parse','HEAD').toString().trim(),tree=git('rev-parse','HEAD^{tree}').toString().trim();
 const files=new Map();
 for(const path of INPUTS.suite_inputs){const bytes=git('show','HEAD:'+path);assert.equal(sha256(readFileSync(root+'/'+path)),sha256(bytes),'Uncommitted suite input '+path);files.set(path,bytes);}
 return {commit,tree,files};
}
export function assertSuite(manifest,suite) {
 assert.equal(manifest.suite_commit,suite.commit,'Exact committed suite HEAD');assert.equal(manifest.suite_tree,suite.tree,'Exact committed suite tree');
 assert.deepEqual(Object.keys(manifest.suite_inputs).sort(),INPUTS.suite_inputs.slice().sort(),'Complete built suite registry');
 for(const path of INPUTS.suite_inputs)assert.equal(manifest.suite_inputs[path],sha256(suite.files.get(path)),'Built source bytes '+path);
}
export function assertInputs(records,assets,suite,manifest) {
 const suiteRecords=records.filter(r=>r.suite_path);assert.equal(suiteRecords.length,INPUTS.suite_inputs.length,'Required suite input cardinality');
 assert.deepEqual(suiteRecords.map(r=>r.suite_path).sort(),INPUTS.suite_inputs.slice().sort(),'Required suite input set (no missing, extra or duplicate)');
 for(const record of records)assert(Boolean(record.path)!==Boolean(record.suite_path),'Exactly one input identity');
 for(const [output,path] of Object.entries(INPUTS.fixed_inputs))assert.equal(sha256(assets.get(output)),sha256(suite.files.get(path)),'Fixed committed input '+output);
 assertSuite(manifest,suite);
}
export function binding(result,manifest) {
 assert.match(result.session,UUID,'Capture session UUID');assert.match(result.document_id,UUID,'Document UUID');
 const url=new URL(result.url);assert.equal(url.protocol,'http:');assert.equal(url.hostname,'127.0.0.1');assert(Number(url.port)>0);assert.equal(url.pathname,'/');assert.equal(url.search,'');assert.equal(url.hash,'');assert.equal(url.username,'');assert.equal(url.password,'');
 return {session:result.session,document_id:result.document_id,route:result.url,viewport:{width:1000,height:900,dpr:1},suite_commit:manifest.suite_commit,suite_tree:manifest.suite_tree,build_sha256:result.manifest.sha256};
}
export function assertBindings(result,manifest) {
 const expected=binding(result,manifest);assert.deepEqual(result.observed_document,{document_id:result.document_id,url:result.url,width:1000,height:900,dpr:1});
 const seen=new Set();for(const response of result.responses){assert(Number.isSafeInteger(response.ordinal)&&response.ordinal>0);assert(!seen.has(response.ordinal),'Duplicate response ordinal');seen.add(response.ordinal);assert.deepEqual(response.binding,{...expected,response_ordinal:response.ordinal,url:response.url});}
 const files=new Set(),ordinals=new Set();for(const frame of result.screenshots){assert(!files.has(frame.file),'Duplicate capture record');files.add(frame.file);assert(Number.isSafeInteger(frame.ordinal)&&frame.ordinal>0);assert(!ordinals.has(frame.ordinal));ordinals.add(frame.ordinal);assert.deepEqual(frame.binding,{...expected,capture_ordinal:frame.ordinal});}
 assert.deepEqual(result.raw_rgba.binding,expected);assert.equal(result.stable.length,2);assert.notEqual(result.stable[0],result.stable[1]);for(const f of result.stable)assert(files.has(f));
}
export function assertRuntime(assets,responses) {
 const wasm=assets.get('gradient_diagnostic_bg.wasm');assert(WebAssembly.validate(wasm),'Structurally valid compiled WASM');
 const module=new WebAssembly.Module(wasm),exports=WebAssembly.Module.exports(module);assert(exports.some(x=>x.name==='memory'&&x.kind==='memory'));assert(exports.some(x=>x.name==='__wbindgen_start'&&x.kind==='function'),'Actual wasm-bindgen start');
 const loader=assets.get('gradient_diagnostic.js').toString();assert(loader.includes('gradient_diagnostic_bg.wasm'));assert(loader.includes('__wbindgen_start'));assert(loader.includes('__wbg_init'));
 assert(responses.some(r=>r.url.startsWith('blob:')&&r.type==='script'),'Actual generated worker response required');
}
