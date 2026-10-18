// SYNTHETIC UNIT INPUTS ONLY. No PNG capture, compiler, browser or runtime evidence.
import {COLORS,makeProfile,sha256} from './drag-drop-comparator.mjs';
const WHITE=[255,255,255,255],BLACK=[0,0,0,255];
export const syntheticGeometry={sources:[{x:192,y:168,width:128,height:128},{x:336,y:168,width:128,height:128},{x:480,y:168,width:128,height:128}],target:{x:144,y:356,width:512,height:128}};
function rect(image,r,color) {
  for(let y=r.y;y<r.y+r.height;y++)for(let x=r.x;x<r.x+r.width;x++)image.data.set(color,4*(y*800+x));
}
function ring(image,r,color,width) {
  for(const edge of [{...r,height:width},{...r,y:r.y+r.height-width,height:width},{...r,width},{...r,x:r.x+r.width-width,width}])rect(image,edge,color);
}
export function syntheticFrame(state) {
  const image={width:800,height:600,data:new Uint8Array(800*600*4)};rect(image,{x:0,y:0,width:800,height:600},WHITE);
  for(let index=0;index<3;index++) {
    const r=syntheticGeometry.sources[index],hover=state.active===null&&state.pointer.x>=r.x&&state.pointer.x<r.x+128&&state.pointer.y>=r.y&&state.pointer.y<r.y+128;
    if(hover)rect(image,r,COLORS[index].map((v,i)=>i===3?255:Math.round(v*.2+255*.8)));
    ring(image,r,COLORS[index],2);
  }
  if(state.target!==null)rect(image,syntheticGeometry.target,COLORS[state.target].map((v,i)=>i===3?255:Math.round(v*.5+255*.5)));
  ring(image,syntheticGeometry.target,state.target===null?BLACK:COLORS[state.target],3);
  if(state.active!==null) {
    const color=COLORS[state.active],r={x:state.pointer.x-60,y:state.pointer.y-25,width:120,height:50};
    for(let y=r.y;y<r.y+r.height;y++)for(let x=r.x;x<r.x+r.width;x++) {
      const offset=4*(y*800+x);for(let channel=0;channel<3;channel++)image.data[offset+channel]=Math.round(color[channel]*.5+image.data[offset+channel]*.5);
    }
  }
  return image;
}
export function syntheticInput(profile) {
  const events=[],mouse_events=[],operations=[];let time=0;
  for(const operation of profile.operations) {
    const pointer=operation.expected.map(event=>({...event,trusted:true,target:'CANVAS',time:++time,defaultPrevented:true,shiftKey:false,ctrlKey:false,altKey:false,metaKey:false}));
    const mouse={...operation.mouse_expected,trusted:true,target:'CANVAS',time:++time,defaultPrevented:false};
    operations.push({...structuredClone(operation),input_method:'CDP.Input.dispatchMouseEvent',input_acknowledged:true,status:'delivered',post_delivery_animation_frames:2,events:pointer,mouse_events:[mouse]});
    events.push(...pointer);mouse_events.push(mouse);
  }
  return {operations,events,mouse_events,startup_events:[],startup_mouse_events:[],operation_start:0,mouse_operation_start:0,captures:structuredClone(profile.captures)};
}
export function syntheticPixels() {
  const profile=makeProfile(syntheticGeometry),report=syntheticInput(profile),images={},stableImages={};
  for(const [name,state] of Object.entries(profile.captures)) {
    images[name]=syntheticFrame(state);stableImages[name]={...images[name],data:images[name].data.slice()};
    Object.assign(report.captures[name],{rgba_sha256:sha256(images[name].data),stability_rgba_sha256:sha256(stableImages[name].data)});
  }
  return {report,retained:{images,stableImages},profile};
}
