import test from 'node:test';
import assert from 'node:assert/strict';
import {createDynamicFontHost, FONT_URL, SAMPLE, WAITING, DOWNLOADING, LOADED} from '../moonbit/site/dynamic-font-host.mjs';

function harness(fetchFont) {
  const changes = [];
  const registered = [];
  let faceCalls = 0;
  class FakeFontFace {
    constructor(family, bytes) {
      faceCalls++;
      assert.equal(family, 'Noto Sans Devanagari');
      assert(bytes instanceof ArrayBuffer);
    }
    async load() { return this; }
  }
  const host = createDynamicFontHost({
    fetchFont, FontFaceType: FakeFontFace,
    fonts: {add(face) { registered.push(face); }},
    onChange: next => changes.push(next),
  });
  return {host, changes, registered, get faceCalls() {return faceCalls;}};
}

test('only the known missing Devanagari range triggers an attempt', async () => {
  let count = 0;
  const h = harness(async () => {count++;throw Error('offline');});
  assert.deepEqual(h.host.state, {phase:'waiting', message:WAITING, attempts:0});
  assert.equal(await h.host.start('Hello 😀 world'), false);
  assert.equal(count, 0);
  assert.equal(await h.host.start(SAMPLE), true);
  assert.equal(count, 1);
  assert.equal(h.host.state.phase, 'failed');
  assert.equal(h.host.state.attempts, 1);
  assert.equal(await h.host.start(SAMPLE), false);
  assert.equal(count, 1);
  assert.equal(h.changes[0].message, DOWNLOADING);
  assert.match(h.host.state.message, /Reload to retry/);
});

test('HTTP 503 and empty bodies are failures without adding a font', async () => {
  for (const response of [
    {ok:false,status:503,arrayBuffer:async()=>new ArrayBuffer(1)},
    {ok:true,status:200,arrayBuffer:async()=>new ArrayBuffer(0)},
  ]) {
    let observed;
    const h = harness(async (url, options) => {
      observed = {url, options}; return response;
    });
    assert.equal(await h.host.start(), true);
    assert.deepEqual(observed, {url:FONT_URL,options:{mode:'cors', credentials:'omit'}});
    assert.equal(h.host.state.phase,'failed');
    assert.equal(h.registered.length,0);
    assert.equal(h.faceCalls,0);
  }
});

test('font face registration advances exactly once and rejects repeated probes', async () => {
  let count=0;
  const h=harness(async()=>{
    count++;
    return {ok:true,status:200,arrayBuffer:async()=>new Uint8Array([1,2,3]).buffer};
  });
  assert.equal(await h.host.start(SAMPLE),true);
  assert.deepEqual(h.changes.map(s=>s.phase),['downloading','loaded']);
  assert.deepEqual(h.host.state,{phase:'loaded',message:LOADED,attempts:1});
  assert.equal(h.registered.length,1);
  assert.equal(h.faceCalls,1);
  assert.equal(await h.host.start(SAMPLE),false);
  assert.equal(count,1);
});

test('a pending download cannot be started again by multiple glyph probes',async()=>{
  let unblock;
  let count=0;
  const h=harness(async()=>{count++;return await new Promise(resolve=>{unblock=resolve;});});
  const pending=h.host.start(SAMPLE);
  assert.equal(h.host.state.phase,'downloading');
  assert.equal(await h.host.start(SAMPLE),false);
  unblock({ok:true,status:200,arrayBuffer:async()=>new Uint8Array([4]).buffer});
  await pending;
  assert.equal(count,1);
  assert.equal(h.host.state.phase,'loaded');
});

test('font decode/registration failure is shown without reattempt',async()=>{
  let count=0;
  class InvalidFont {async load(){throw Error('invalid OpenType font');}}
  const h=createDynamicFontHost({
    fetchFont:async()=>{count++;return {ok:true,status:200,arrayBuffer:async()=>new Uint8Array([1]).buffer};},
    FontFaceType:InvalidFont,fonts:{add(){throw Error('must not register');}},onChange:()=>{},
  });
  await h.start();
  assert.equal(h.state.phase,'failed');
  assert.match(h.state.message,/invalid OpenType font/);
  await h.start();
  assert.equal(count,1);
});
