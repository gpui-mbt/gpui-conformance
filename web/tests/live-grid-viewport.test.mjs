import assert from 'node:assert/strict';
import test from 'node:test';
import {gridPaneSize} from '../live-grid-viewport.mjs';
test('desktop uses equal integer widths and remaining screen height',()=>{
 assert.deepEqual(gridPaneSize({widths:[678.5,679],viewportHeight:1000,top:300,headerHeights:[50,52],stacked:false,padding:40}),{width:678,height:608});
});
test('stacked panes share screen height and include both headers and gap',()=>{
 assert.deepEqual(gridPaneSize({widths:[356,356],viewportHeight:844,top:300,headerHeights:[70,70],stacked:true,gap:8,padding:32}),{width:356,height:182});
});
test('small landscape screens retain usable panes with page scrolling',()=>{
 assert.deepEqual(gridPaneSize({widths:[370,370],viewportHeight:390,top:330,headerHeights:[50,50],stacked:false,padding:32}),{width:370,height:160});
});

test('observer updates both iframe dimensions and teardown cancels pending work',async()=>{
 const {fitLiveGrid}=await import('../live-grid-viewport.mjs');
 let callback,queued,resize,disconnected=false,cancelled=false,active=false;
 const containers=[{clientWidth:600,style:{}},{clientWidth:601,style:{}}];
 const frames=containers.map(parentElement=>({parentElement,style:{}}));
 const heads=[0,1].map(()=>({getBoundingClientRect:()=>({height:48})}));
 const panes={querySelectorAll:()=>heads,getBoundingClientRect:()=>({top:200})};
 const win={innerHeight:900,getComputedStyle:()=>({rowGap:'16',paddingTop:'20',paddingBottom:'20'}),matchMedia:()=>({matches:false}),
  ResizeObserver:class{constructor(cb){callback=cb;}observe(){}disconnect(){disconnected=true;}},
  addEventListener:(type,cb)=>{resize=cb;},removeEventListener:(type,cb)=>assert.equal(cb,resize),
  requestAnimationFrame:cb=>{queued=cb;return 1;},cancelAnimationFrame:()=>{cancelled=true;}};
 const doc={body:{classList:{add:()=>{active=true;},remove:()=>{active=false;}}},querySelector:()=>panes,getElementById:id=>id==='notice'?{}:frames[id==='rust-frame'?0:1]};
 const stop=fitLiveGrid({windowObject:win,documentObject:doc});
 assert(active);assert.deepEqual(frames.map(f=>f.style),[{width:'600px',height:'610px'},{width:'600px',height:'610px'}]);
 containers[0].clientWidth=333;callback();queued();assert(frames.every(f=>f.style.width==='333px'));
 resize();stop();assert(disconnected&&cancelled&&!active);
});
