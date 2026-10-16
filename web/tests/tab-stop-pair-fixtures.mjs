// SYNTHETIC UNIT INPUTS ONLY. No PNG, compiler, browser or runtime evidence.
import {sha256,frameGeometry,makeProfile} from './tab-stop-comparator.mjs';
export function fixtureFrame(focus=null,message='initial',hover=false) {
  const image={width:800,height:600,data:new Uint8Array(1920000)},boxes={};
  const paint=(x,y,width,height,color)=>{for(let yy=y;yy<y+height;yy++)for(let xx=x;xx<x+width;xx++)image.data.set(color,4*(yy*800+xx));};
  paint(0,0,800,600,[255,255,255,255]);
  const heights=[33,33,34,33,33];
  if(focus==='item0'){heights[0]++;heights[2]--;}if(focus==='item1'){heights[1]++;heights[2]--;}if(focus==='item4'){heights[4]++;heights[2]--;}
  let y=54;
  const ring=(box,width,color)=>{
    paint(box.x,box.y,box.width,width,color);paint(box.x,box.y+box.height-width,box.width,width,color);
    paint(box.x,box.y,width,box.height,color);paint(box.x+box.width-width,box.y,width,box.height,color);
  };
  for(let index=0;index<5;index++) {
    const name='item'+index,box={x:16,y,width:768,height:heights[index]};boxes[name]=box;
    if(hover&&focus===name)paint(16,y,768,heights[index],[230,230,230,255]);
    ring(box,1,index===3?[153,153,153,255]:[0,0,0,255]);y+=heights[index]+12;
  }
  const widths=focus==='el1'?[380,376]:focus==='el2'?[376,380]:[378,378];
  boxes.el1={x:16,y,width:widths[0],height:40};boxes.el2={x:28+widths[0],y,width:widths[1],height:40};
  for(const name of ['el1','el2']){const b=boxes[name];paint(b.x,b.y,b.width,b.height,[0,0,0,255]);}y+=52;
  for(let group=1;group<=2;group++){for(let child=1;child<=3;child++){const b={x:16,y:y+40*(child-1),width:768,height:40};boxes[`group${group}_child${child}`]=b;paint(b.x,b.y,b.width,b.height,[0,0,0,255]);}y+=132;}
  if(focus&&focus!=='item3')ring(boxes[focus],3,[0,0,255,255]);
  const token={initial:1,forward:2,reverse:3,el1:4,el2:5}[message];
  for(let x=20;x<200+7*token;x+=7)paint(x,20+token,3,9,[0,0,0,255]);return image;
}
export function syntheticPixels() {
  const images={},frames={};let plan=makeProfile();
  const hovered=new Set(['click_item0','click_item1','click_item2','click_item4','edge_card_hover','edge_card_down','edge_card_click']);
  while(true) {
    for(const [name,spec] of Object.entries(plan.captures))if(!images[name]){images[name]=fixtureFrame(spec.focus,spec.message,hovered.has(name));frames[name]=frameGeometry(images[name]);}
    if(plan.complete)break;plan=makeProfile(frames);
  }
  let time=0;
  const operations=plan.operations.map(operation=>({name:operation.name,expected:structuredClone(operation.expected),status:'delivered',
    events:operation.expected.map(event=>({...event,trusted:true,target:event.type.startsWith('key')?'TEXTAREA':'CANVAS',defaultPrevented:true,time:++time}))}));
  const report={operations,startup_events:[],operation_start:0,events:operations.flatMap(operation=>operation.events),captures:{}};
  const stableImages={};for(const [name,image] of Object.entries(images)) {
    stableImages[name]={...image,data:image.data.slice()};report.captures[name]={after_operation:plan.captures[name].after_operation,
      rgba_sha256:sha256(image.data),stability_rgba_sha256:sha256(stableImages[name].data)};
  }
  return {report,retained:{images,stableImages},plan};
}
