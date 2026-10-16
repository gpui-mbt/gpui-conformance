import test from 'node:test';
import assert from 'node:assert/strict';
import {drawFrame,validateFrame} from '../moonbit/site/render.mjs';

const frame=()=>({ok:true,conformance:'unverified',snapshot:{schema_version:1,items:[
  {id:1,kind:'quad',bounds:{x:32,y:208,width:736,height:64},color:{red:37,green:99,blue:235,alpha:255}},
  {id:2,kind:'text',bounds:{x:32,y:32,width:300,height:39},font_size:24,text:'CSS focus-visible Demo',color:{red:17,green:24,blue:39,alpha:255}},
]},decorations:[{id:1,radius:6,border:'#10b981',border_width:4,border_style:'solid'}],
text_styles:[{id:2,weight:700,style:'normal',decoration:'none'}]});

test('focus borders and bold700 remain explicit validated host extensions',()=>{
  assert.doesNotThrow(()=>validateFrame(frame()));
  for(const width of [0,2,5,-1,NaN,Infinity,'4',null]) {
    const value=frame();value.decorations[0].border_width=width;
    assert.throws(()=>validateFrame(value),/decoration/);
  }
  for(const mutation of [value=>{value.decorations[0].border_style='dashed';},
    value=>{value.snapshot.items[0].bounds.height=7;},
    value=>{value.decorations[0].radius=33;},
    value=>{value.decorations[0].id=2;},
    value=>{value.text_styles[0].weight=600;}]) {
    const value=frame();mutation(value);assert.throws(()=>validateFrame(value));
  }
});

test('solid focus border centerline is inset2px with inner radius4px',()=>{
  const paths=[],strokes=[],fonts=[],target={};
  const context=new Proxy(target,{
    get:(object,key)=>key==='roundRect'? (...args)=>paths.push(args):
      key==='stroke'?()=>strokes.push({width:object.lineWidth,color:object.strokeStyle}):
      key==='measureText'?()=>({actualBoundingBoxAscent:18,actualBoundingBoxDescent:5}):()=>{},
    set:(object,key,value)=>{object[key]=value;if(key==='font')fonts.push(value);return true;},
  });
  drawFrame(context,frame(),{width:800,height:600,font_family:'IBM Plex Sans'},1);
  assert.deepEqual(paths,[[32,208,736,64,6],[34,210,732,60,4]]);
  assert.deepEqual(strokes,[{width:4,color:'#10b981'}]);
  assert(fonts.some(font=>font.includes('700 24px')));
});

test('existing1px dashed borders still validate and invalid focus strokes draw nothing',()=>{
  const old=frame();old.decorations[0].border_width=1;old.decorations[0].border_style='dashed';
  assert.doesNotThrow(()=>validateFrame(old));
  const invalid=frame();invalid.decorations[0].border_width=8;
  let calls=0;
  assert.throws(()=>drawFrame(new Proxy({}, {get:()=>()=>calls++}),invalid,{width:800,height:600},1));
  assert.equal(calls,0);
});
