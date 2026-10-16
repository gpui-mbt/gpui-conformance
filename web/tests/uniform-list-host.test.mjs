import assert from 'node:assert/strict';
import test from 'node:test';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {sha256} from './uniform-list-comparator.mjs';
import {HTML_ENTRYPOINTS,SUITE_INPUTS} from './uniform-list-runtime-evidence.mjs';

// Execute the unchanged shared host routing with only its import boundary mocked.
// This exercises packaging/route contracts; it is not browser/WASM evidence.
async function route(example) {
  const source=readFileSync(new URL('../rust/host.mjs',import.meta.url),'utf8'),imports=[],complete=[],errors=[];
  const error={hidden:true,textContent:''},html={dataset:{}},document={documentElement:html,getElementById:()=>error,querySelector:()=>({})};
  const code=source.replace("import { createHostTiming } from '../load-timing.mjs';",'').replace('await import(modules[example])','await load(modules[example])');
  await vm.runInNewContext(`(async()=>{${code}})()`,{URL,location:{href:'http://127.0.0.1/rust/?example='+example},crossOriginIsolated:true,document,
    createHostTiming:()=>({complete:(...values)=>complete.push(values),fail:()=>{}}),
    load:async path=>{imports.push(path);return {default:async()=>{}};},console:{error:error=>errors.push(error.message)},performance:{now:()=>0}});
  return {imports,complete,errors,html,error,document};
}
test('Rust-only route imports uniform_list binding and marks canvas initialization without claiming paint',async()=>{
  const result=await route('uniform_list');assert.deepEqual(result.imports,['./uniform_list.js']);assert.deepEqual(result.errors,[]);
  assert.equal(result.html.dataset.runtimeStatus,'initialized');
  assert.deepEqual(Array.from(result.complete[0][0]),['./uniform_list.js','./uniform_list_bg.wasm']);
  assert.equal(result.document.title,'uniform_list · gpui.rs');
});
test('unknown Rust route fails before importing any generated code',async()=>{
  const result=await route('uniform_list_other');assert.deepEqual(result.imports,[]);assert.equal(result.html.dataset.runtimeStatus,'failed');
  assert.match(result.error.textContent,/not bundled/);
});
test('exact HTML and static-site preparer are retained while catalog has no list candidate',()=>{
  const html=readFileSync(new URL('../rust/index.html',import.meta.url));assert.equal(sha256(html),HTML_ENTRYPOINTS.rust.sha256);
  assert.match(html.toString(),/<script type="module" src="\.\/host.mjs"><\/script>/);
  assert(SUITE_INPUTS.includes('web/scripts/prepare_uniform_list_site.py'));
  const catalog=JSON.parse(readFileSync(new URL('../examples.json',import.meta.url)));
  assert(!catalog.examples.some(example=>example.id==='uniform_list'));
  const candidate=readFileSync(new URL('../moonbit/site/host.mjs',import.meta.url),'utf8');assert(!candidate.includes('uniform_list'));
});
