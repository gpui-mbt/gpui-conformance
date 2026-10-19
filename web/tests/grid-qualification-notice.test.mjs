import test from 'node:test';
import assert from 'node:assert/strict';
import {hasVisibleParentGridQualification,watchGridQualificationNotice} from '../moonbit/site/grid-qualification-notice.mjs';
function fixture() {
 const warning={textContent:'Strict comparison remains limited to 399/400/401/500 × 500 at DPR1; other sizes are unverified.',isConnected:true,getClientRects:()=>[{width:300,height:40}],getAttribute:()=>null,parentElement:null};
 const moon={src:'https://example.test/moonbit/?example=grid_layout'},rust={src:'https://example.test/rust/?example=grid_layout'};
 const elements={'notice':warning,'moon-frame':moon,'rust-frame':rust};let mutation,resize;
 const parent={location:{origin:'https://example.test',href:'https://example.test/?example=grid_layout'},document:{getElementById:id=>elements[id],body:{classList:{contains:()=>true}},documentElement:{}},getComputedStyle:n=>({display:'block',visibility:'visible',opacity:'1',...n.style}),addEventListener:(e,f)=>resize=f,removeEventListener:()=>resize=null};
 const w={parent,location:parent.location,frameElement:moon,MutationObserver:class {constructor(f){mutation=f} observe(){} disconnect(){mutation=null}}};
 return {w,warning,elements,mutation:()=>mutation(),resize:()=>resize(),callbacks:()=>({mutation,resize})};
}
test('only the same-origin grid pair with visible complete qualification replaces the duplicate',()=>{
 const f=fixture();assert(hasVisibleParentGridQualification(f.w));
 for(const mutate of [f=>f.w.frameElement={},f=>f.elements['rust-frame']=null,f=>f.elements['rust-frame'].src='https://elsewhere.test/?example=grid_layout',f=>f.elements['moon-frame'].src='https://example.test/?example=gradient',f=>f.warning.textContent='Live viewport',f=>f.warning.isConnected=false,f=>f.warning.getClientRects=()=>[],f=>f.warning.getClientRects=()=>[{width:0,height:40}],f=>f.warning.getClientRects=()=>[{width:300,height:0}],f=>f.warning.hidden=true,f=>f.warning.style={display:'none'},f=>f.warning.style={visibility:'hidden'},f=>f.warning.style={opacity:'0'},f=>f.warning.getAttribute=()=> 'true',f=>f.warning.parentElement={hidden:true,getAttribute:()=>null},f=>f.w.parent=f.w,f=>Object.defineProperty(f.w.parent,'document',{get(){throw Error('cross origin')}})]){const f=fixture();mutate(f);assert.equal(hasVisibleParentGridQualification(f.w),false);}
});
test('parent removal, hiding and text changes immediately restore required child warning',()=>{
 const f=fixture(),notice={hidden:true},controller=watchGridQualificationNotice(f.w,notice);
 controller.setRequired(true);assert.equal(notice.hidden,true);
 f.warning.hidden=true;f.mutation();assert.equal(notice.hidden,false);
 f.warning.hidden=false;f.mutation();assert.equal(notice.hidden,true);
 const warning=f.elements.notice;delete f.elements.notice;f.mutation();assert.equal(notice.hidden,false);
 f.elements.notice=warning;f.mutation();assert.equal(notice.hidden,true);
 warning.style={visibility:'hidden'};f.resize();assert.equal(notice.hidden,false);
 warning.style={};warning.textContent='';f.mutation();assert.equal(notice.hidden,false);
 controller.setRequired(false);assert.equal(notice.hidden,true);controller.stop();
});
test('standalone and cross-origin hosts preserve required warning and qualified/error state hides it',()=>{
 for(const mode of ['standalone','cross-origin']){const f=fixture();if(mode==='standalone')f.w.parent=f.w;else Object.defineProperty(f.w.parent,'location',{get(){throw Error('cross origin')}});const notice={},c=watchGridQualificationNotice(f.w,notice);c.setRequired(true);assert.equal(notice.hidden,false);c.setRequired(false);assert.equal(notice.hidden,true);c.stop();}
});

test('stopped parent callbacks stay inert and a fresh watcher can restore after page return',()=>{
 const f=fixture(),notice={hidden:true},old=watchGridQualificationNotice(f.w,notice);old.setRequired(true);
 const queued=f.callbacks();old.stop();assert.deepEqual(f.callbacks(),{mutation:null,resize:null});
 f.warning.hidden=true;queued.mutation();queued.resize();assert.equal(notice.hidden,true);
 const current=watchGridQualificationNotice(f.w,notice);current.setRequired(true);assert.equal(notice.hidden,false);
 f.warning.hidden=false;f.mutation();assert.equal(notice.hidden,true);current.stop();
});
