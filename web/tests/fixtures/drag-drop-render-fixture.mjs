// Synthetic source-derived command fixtures, never original Rust/browser pixels.
export const metadata={width:800,height:600,font_family:'IBM Plex Sans'};
export const blue={red:0,green:0,blue:255,alpha:255};
export const white={red:255,green:255,blue:255,alpha:255};
export const clear={red:0,green:0,blue:0,alpha:0};
export const quad=(id,bounds,color=blue,opacity=1)=>({id,kind:'quad',bounds,color,opacity});
export const label=(id,bounds,text='Item 0',color=white,font_size=12)=>
  ({id,kind:'text',bounds,text,color,font_size,opacity:1});

export function previewFrame() {
  return {ok:true,conformance:'unverified',snapshot:{schema_version:1,items:[
    quad(100,{x:200,y:200,width:120,height:50},blue,.5),
    label(101,{x:242,y:215,width:36,height:19}),
  ]},decorations:[],shadows:[{id:100,kind:'shadow_md',element_opacity:1}]};
}

export function adjacentPreviews() {
  const frame=previewFrame();
  frame.snapshot.items.push(
    quad(200,{x:200,y:250,width:120,height:50},blue,.5),
    label(201,{x:242,y:265,width:36,height:19},'Item 1'));
  frame.shadows.push({id:200,kind:'shadow_md',element_opacity:1});
  return frame;
}

export function borderedPreview() {
  const frame=previewFrame();
  frame.snapshot.items.unshift(
    quad(1,{x:144,y:188,width:512,height:128},blue,.5),
    label(2,{x:350,y:239,width:100,height:26},'Drop items here',{red:51,green:51,blue:51,alpha:255},16),
    quad(3,{x:144,y:188,width:512,height:128},clear));
  frame.decorations.push({id:3,radius:0,border:'#0000ff',border_width:3,border_style:'solid'});
  return frame;
}

export const isShadow=state=>state.kind==='fill'&&state.shadowBlur>0;

export function recorder({failFill=false}={}) {
  const calls=[],states=[],stack=[];
  let path=[];
  const initial={globalAlpha:.23,shadowColor:'transparent',shadowBlur:0,shadowOffsetX:0,shadowOffsetY:0,lineWidth:7};
  const state={...initial};
  const context=new Proxy(state,{
    get:(object,key)=>(...args)=>{
      calls.push([key,...args]);
      if(key==='save')stack.push({...object});
      else if(key==='restore'){
        const old=stack.pop();
        if(!old)throw new Error('Unbalanced restore');
        for(const name of Object.keys(object))delete object[name];
        Object.assign(object,old);
      } else if(key==='measureText')return {actualBoundingBoxAscent:9,actualBoundingBoxDescent:3};
      else if(key==='beginPath')path=[];
      else if(['rect','roundRect'].includes(key))path.push([key,...args]);
      else if(key==='clip')object.clips=[...(object.clips||[]),...path];
      else if(['fill','stroke','fillText'].includes(key)){
        states.push({kind:key,...object,args,path:path.map(part=>[...part])});
        if(key==='fill'&&failFill)throw new Error('Synthetic Canvas paint failure');
      }
    },
    set:(object,key,value)=>{calls.push(['set',key,value]);object[key]=value;return true;},
  });
  return {context,calls,states,state,initial,stack};
}
