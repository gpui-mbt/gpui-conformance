import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {webcrypto} from 'node:crypto';
import {prepareImageResources} from '../moonbit/site/image-resources.mjs';
import {drawFrame,validateFrame,drawCoreRasterFrame} from '../moonbit/site/render.mjs';
if (!globalThis.crypto) globalThis.crypto=webcrypto;
const resource={id:1,kind:'image',content_identity:'77453d98d46494b3b34b94aa863b686ea299e0190030a5c7ca5377b238332522',pixel_width:512,pixel_height:512,frame_count:1};
const identity={a:1,b:0,c:0,d:1,tx:0,ty:0};
const image={id:2,kind:'image',resource_id:1,frame_index:0,bounds:{x:25,y:0,width:50,height:100},image_bounds:{x:0,y:0,width:100,height:100},transform:identity,opacity:.25,clip_chain_id:1};
const quad={id:1,kind:'quad',bounds:{x:0,y:0,width:100,height:100},color:{red:255,green:0,blue:0,alpha:255},opacity:1};
const frame=()=>({ok:true,conformance:'unverified',decorations:[],snapshot:{schema_version:1,resources:[{...resource}],items:structuredClone([quad,image,{...quad,id:3}]),clip_chains:[{id:1,rects:[{x:10,y:10,width:70,height:70}]}]}});
const bytes=new Uint8Array(await readFile(new URL('../../assets/app-icon.png',import.meta.url)));
const bitmap=Object.freeze({width:512,height:512,close(){}});
globalThis.createImageBitmap=async()=>bitmap;
const prepared=await prepareImageResources([resource],new Map([[1,bytes]]));
function context(){const calls=[],state={globalAlpha:1};return {calls,proxy:new Proxy(state,{get:(o,k)=>k in o?o[k]:(...args)=>calls.push([k,...args,k==='drawImage'||k==='fill'?o.globalAlpha:null]),set:(o,k,v)=>(o[k]=v,true)})};}

test('real asset prepared, image stays in painter order and uses core bounds, crop, clip, alpha',()=>{
 const c=context();drawFrame(c.proxy,frame(),{width:100,height:100},1,prepared);
 assert.deepEqual(c.calls.filter(c=>['fill','drawImage'].includes(c[0])).map(c=>[c[0],c.at(-1)]),[['fill',1],['drawImage',.25],['fill',1]]);
 assert.deepEqual(c.calls.find(c=>c[0]==='drawImage').slice(1,-1),[bitmap,25,0,50,100]);
 assert.ok(c.calls.some(c=>c[0]==='rect'&&c.slice(1,5).join(',')==='10,10,70,70'));
 assert.ok(c.calls.some(c=>c[0]==='rect'&&c.slice(1,5).join(',')==='0,0,100,100'));
});
test('missing, changed, invalid or unprepared resource fails before any destination method',()=>{
 const mutations=[f=>f.snapshot.resources=[],f=>f.snapshot.resources[0].content_identity='0'.repeat(64),f=>f.snapshot.items[1].frame_index=1,f=>f.snapshot.items[1].transform={...identity,tx:1},f=>f.snapshot.items[1].image_bounds.width=-1,f=>f.snapshot.resources.push({...resource})];
 for(const mutate of mutations){const f=frame();mutate(f);const c=context();assert.throws(()=>drawFrame(c.proxy,f,{width:100,height:100},1,prepared));assert.equal(c.calls.length,0);}
 const c=context();assert.throws(()=>drawFrame(c.proxy,frame(),{width:100,height:100},1,{}));assert.equal(c.calls.length,0);
});
test('preparation rejects content substitution and dimensions before decoding',async()=>{
 let decodes=0;globalThis.createImageBitmap=async()=>{decodes++;return bitmap;};
 await assert.rejects(prepareImageResources([{...resource,content_identity:'0'.repeat(64)}],new Map([[1,bytes]])),/identity/);
 await assert.rejects(prepareImageResources([{...resource,pixel_width:256}],new Map([[1,bytes]])),/dimensions/);
 assert.equal(decodes,0);
});
test('host does not admit unsupported image animation or arbitrary resources',()=>{
 const f=frame();f.snapshot.resources[0].frame_count=2;assert.throws(()=>validateFrame(f));
});

test('externally closed bitmap fails preflight before clear or earlier quad',async()=>{
 let live=true;
 const closable={get width(){return live?512:0;},get height(){return live?512:0;},close(){live=false;}};
 globalThis.createImageBitmap=async()=>closable;
 const token=await prepareImageResources([resource],new Map([[1,bytes]]));
 const first=context();drawFrame(first.proxy,frame(),{width:100,height:100},1,token);
 // Even a host that intercepted a prior draw cannot bypass the next preflight.
 first.calls.find(c=>c[0]==='drawImage')[1].close();
 const second=context();assert.throws(()=>drawFrame(second.proxy,frame(),{width:100,height:100},1,token),/closed|invalid/);
 assert.equal(second.calls.length,0);
});

test('core raster transport rejects image resources before clear or allocation',()=>{
 const f={ok:true,conformance:'unverified',decorations:[],raster_transport:'ordered_core_webgl2_linear_straight_v1',snapshot:{schema_version:1,viewport:{x:0,y:0,width:100,height:100},scale:1,resources:[resource],items:[quad]},operations:[{kind:'legacy',index:0}]};
 const c=context();let allocations=0;
 assert.throws(()=>drawCoreRasterFrame(c.proxy,f,{width:100,height:100},1,()=>{allocations++;throw Error('unexpected');}),/resources unsupported/);
 assert.equal(c.calls.length,0);assert.equal(allocations,0);
});
