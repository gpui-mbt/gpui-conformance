import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {readGridViewport,measureGridInputs,readGridFrame} from '../moonbit/site/grid-layout-host.mjs';

// Synthetic host fixtures exercise transport only, not compiled MoonBit or Rust.
function fixture() {
  const calls=[],measurements=[];
  const runtime={
    grid_layout_metadata:()=>JSON.stringify({id:'grid_layout',width:500,height:500,font_family:'IBM Plex Sans',font_size:16}),
    grid_layout_content:(width,height,scale)=>{
      calls.push(['content',width,height,scale]);
      if (![399,400,401,500].includes(width)||height!==500||scale!==1)
        return JSON.stringify({ok:false,error:'unsupported_viewport_profile'});
      return JSON.stringify({ok:true,runs:[`Header — ${width}px`,'Table of contents','Content','AD :(','Footer'].map(text=>({text,font_size:16})),layout_passes:1,query_callbacks:1});
    },
    grid_layout_frame:(width,height,prefixes,scale)=>{
      calls.push(['frame',width,height,prefixes,scale]);
      return JSON.stringify({ok:true,conformance:'unverified',grid_layout:{frame_layout_passes:1,frame_query_callbacks:1},snapshot:{}});
    },
  };
  const context={measureText:text=>{measurements.push(text);return {width:Array.from(text).length*8};}};
  return {runtime,context,calls,measurements};
}

test('viewport adapter transports actual finite dimensions without a breakpoint or clamping',()=>{
  for(const width of [16,399,400,401,500,650.25])
    assert.deepEqual(readGridViewport({innerWidth:width,innerHeight:713}),{width,height:713});
  for(const width of [0,-1,NaN,Infinity,'500']) assert.throws(()=>readGridViewport({innerWidth:width,innerHeight:500}));
  const source=readFileSync(new URL('../moonbit/site/grid-layout-host.mjs',import.meta.url),'utf8');
  assert(!/\b400\b|Math\.(min|max|floor|ceil|round)|grid_cols|with_span/.test(source.replace('normal 400 16px','normal weight 16px')));
});

test('shaping prefixes preserve source Unicode and exact content from compiled export',()=>{
  const f=fixture(),result=measureGridInputs(f.runtime,f.context,399,500,1);
  assert.equal(result.content.runs[0].text,'Header — 399px');
  assert.deepEqual(result.prefixes[0],[0,8,16,24,32,40,48,56,64,72,80,88,96,104,112]);
  assert(f.measurements.includes('Header —'));
  assert.equal(f.context.font,'normal 400 16px "IBM Plex Sans"');
  assert.deepEqual(f.calls,[['content',399,500,1]]);
});

test('each presentable frame calls preflight and frame once and reports both actual passes',()=>{
  const f=fixture();
  for(const width of [500,399,400,401,500]) {
    const result=readGridFrame(f.runtime,f.context,{innerWidth:width,innerHeight:500},1);
    assert.equal(result.width,width);assert.equal(result.height,500);
    assert.equal(result.frame.grid_layout.host_layout_passes,2);
    assert.equal(result.frame.conformance,'unverified');
    const [content,frame]=f.calls.slice(-2);
    assert.deepEqual(content,['content',width,500,1]);
    assert.equal(frame[0],'frame');assert.equal(frame[1],width);assert.equal(frame[2],500);assert.equal(frame[4],1);
    assert.deepEqual(frame[3],result.prefixes);
  }
  assert.equal(f.calls.length,10);
});

test('unsupported viewport and invalid runtime content fail without inventing a candidate frame',()=>{
  const f=fixture();assert.throws(()=>readGridFrame(f.runtime,f.context,{innerWidth:650,innerHeight:500},1),/unsupported_viewport_profile/);
  assert.deepEqual(f.calls,[['content',650,500,1]]);
  for(const content of [{ok:false,error:'failed'},{ok:true,runs:[]},{ok:true,runs:Array(5).fill({text:1,font_size:16})},
    {ok:true,runs:Array(5).fill({text:'text',font_size:17})}]) {
    assert.throws(()=>measureGridInputs({grid_layout_content:()=>JSON.stringify(content)},f.context,500,500,1));
  }
  const bad=fixture();bad.runtime.grid_layout_frame=()=>JSON.stringify({ok:false,error:'invalid_metrics'});
  assert.throws(()=>readGridFrame(bad.runtime,bad.context,{innerWidth:500,innerHeight:500},1),/invalid_metrics/);
});

async function route(width=500) {
  const f=fixture(),events=new Map(),draws=[],imports=[],timing=[];
  const canvas={style:{},setAttribute(){},getContext:()=>f.context},error={hidden:true};
  const document={getElementById:id=>id==='canvas'?canvas:error,documentElement:{dataset:{}},fonts:{add(){},ready:Promise.resolve()}};
  const window={innerWidth:width,innerHeight:500,addEventListener:(name,callback)=>events.set(name,callback)};
  const source=readFileSync(new URL('../moonbit/site/host.mjs',import.meta.url),'utf8')
    .replace(/^import .*;\n/gm,'').replace('await import(modules[example])','await load(modules[example])');
  const sandbox={URL,location:{href:'http://127.0.0.1/moonbit/?example=grid_layout'},window,document,devicePixelRatio:1,
    FontFace:class {async load(){return this;}},readGridFrame,
    drawFrame:(_context,frame,metadata,scale)=>draws.push({frame,metadata:{...metadata},scale}),
    load:async path=>{imports.push(path);return f.runtime;},
    createHostTiming:()=>({complete:(...args)=>timing.push(['complete',...args]),fail:()=>timing.push(['fail'])})};
  await vm.runInNewContext(`(async()=>{${source}})()`,sandbox);
  return {...f,window,events,draws,imports,timing,sandbox,canvas,error,document};
}

test('shared host imports real candidate route and updates Canvas size on actual resize events',async()=>{
  const f=await route();assert.deepEqual(f.imports,['./grid_layout.mjs']);
  for(const width of [399,400,401,500]) {f.window.innerWidth=width;f.events.get('resize')();}
  assert.deepEqual(f.draws.map(draw=>draw.metadata.width),[500,399,400,401,500]);
  assert(f.draws.every(draw=>draw.metadata.height===500&&draw.scale===1));
  assert.equal(f.canvas.width,500);assert.equal(f.canvas.height,500);assert.equal(f.canvas.style.width,'500px');
  assert.equal(f.document.documentElement.dataset.runtimeStatus,'ready');
  assert.equal(f.sandbox.gpuiExample.frame.grid_layout.host_layout_passes,2);
});

test('unsupported resize clears stale success and same document recovers, including initial rejection',async()=>{
  for(const initial of [500,650]) {
    const f=await route(initial);
    f.window.innerWidth=650;f.events.get('resize')();
    assert.equal(f.canvas.hidden,true);assert.equal(f.error.hidden,false);
    assert.equal(f.sandbox.gpuiExample,undefined);assert.equal(f.document.documentElement.dataset.runtimeStatus,'failed');
    assert.match(f.error.textContent,/Supported profile/);
    f.window.innerWidth=399;f.events.get('resize')();
    assert.equal(f.canvas.hidden,false);assert.equal(f.error.hidden,true);assert.equal(f.canvas.width,399);
    assert.equal(f.document.documentElement.dataset.runtimeStatus,'ready');assert(f.sandbox.gpuiExample);
  }
});

test('live candidate registration remains distinct from immutable Rust-only catalog and generic builder',()=>{
  const live=JSON.parse(readFileSync(new URL('../examples.json',import.meta.url)));
  const frozen=JSON.parse(readFileSync(new URL('./fixtures/grid-layout-rust-only-catalog-b0781104.json',import.meta.url)));
  const candidate=live.examples.find(entry=>entry.id==='grid_layout');
  assert.equal(candidate.moonbit,'implemented');assert.equal(candidate.source_blob,'51f9b13e41fb7913c653d716da3e8ce05a96109d');
  assert.equal(candidate.candidate_source,'web/moonbit/grid_layout/grid_layout.mbt');
  assert(!frozen.examples.some(entry=>entry.id==='grid_layout'));
  assert.match(candidate.implementation_note,/two host layout passes/);
  assert.match(candidate.implementation_note,/remain unverified/);
  const builder=readFileSync(new URL('../scripts/build_moonbit.py',import.meta.url),'utf8');
  assert(builder.includes('example.get("moonbit") == "implemented"'));
  assert(builder.includes('shutil.copytree(WEB / "moonbit" / name, candidate / package)'));
});
