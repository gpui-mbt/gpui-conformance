// Canvas exports only: no composited-page screenshot or DOM-notice pixel claim.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
export const digest=bytes=>createHash('sha256').update(bytes).digest('hex');
export function captureIdentity(state) {
  const {width,height,scale,status,canvas,canvasBounds,canvasHidden,errorHidden,noticeHidden,metadata,hostScale,frame,document_id}=state;
  return {width,height,scale,status,canvas,canvasBounds,canvasHidden,errorHidden,noticeHidden,metadata,hostScale,frame,document_id};
}
export function decodeLiveCanvas(png) {
  const decoded=spawnSync('python3',[fileURLToPath(new URL('../scripts/decode_anchor_live_png.py',import.meta.url))],
    {input:png,maxBuffer:33554432*4+8});
  assert.equal(decoded.status,0,`Independent live PNG decoder: ${decoded.stderr}`);
  assert(decoded.stdout.length>=8);
  return {width:decoded.stdout.readUInt32BE(0),height:decoded.stdout.readUInt32BE(4),rgba:decoded.stdout.subarray(8)};
}
export function verifyCanvasCapture({before,after,expected,png,rgba,samples=[]}) {
  const identity=captureIdentity(before);
  assert.deepEqual(captureIdentity(after),identity,'Viewport/DPR/frame/hover changed during capture');
  assert.deepEqual(identity,captureIdentity(expected),'Capture is stale relative to the requested live state');
  assert.equal(identity.status,'ready');assert.equal(identity.canvasHidden,false);assert.equal(identity.errorHidden,true);
  assert.equal(identity.width,identity.metadata.width);assert.equal(identity.height,identity.metadata.height);
  assert.equal(identity.scale,identity.hostScale);assert.equal(identity.frame.snapshot.scale,identity.scale);
  const dimensions=[Math.round(identity.width*identity.scale),Math.round(identity.height*identity.scale)];
  assert.deepEqual(identity.canvas,dimensions);
  const decoded=decodeLiveCanvas(png);
  assert.deepEqual([decoded.width,decoded.height],dimensions,'Decoded Canvas PNG dimensions disagree with live backing store');
  assert.equal(rgba.length,dimensions[0]*dimensions[1]*4,'Independent live Canvas buffer length');
  assert(decoded.rgba.equals(rgba),'Decoded PNG differs from independently read live Canvas RGBA; stale same-size capture');
  for(const sample of samples) {
    const x=Math.floor(sample.x*identity.scale),y=Math.floor(sample.y*identity.scale);
    assert(x>=0&&x<decoded.width&&y>=0&&y<decoded.height,'Pixel probe must be inside actual backing store');
    const offset=(y*decoded.width+x)*4;
    assert.deepEqual(Array.from(decoded.rgba.subarray(offset,offset+4)),sample.rgba,`Decoded PNG sample ${sample.kind}`);
  }
  return {kind:'canvas_export',composited_page_screenshot:false,width:decoded.width,height:decoded.height,
    png_sha256:digest(png),rgba_sha256:digest(rgba),rgba_bytes:rgba.length,identity_sha256:digest(JSON.stringify(identity)),samples};
}

// This function executes wholly within the candidate iframe in one synchronous
// JS task. No viewport changes, pointer events, redraws or screenshot APIs occur.
export function exportLiveCanvas() {
  const read=()=>{
    const canvas=document.querySelector('canvas'),error=document.getElementById('error');
    const example=globalThis.gpuiExample,rect=canvas.getBoundingClientRect();
    return structuredClone({width:innerWidth,height:innerHeight,scale:devicePixelRatio,status:document.documentElement.dataset.runtimeStatus,
      canvas:[canvas.width,canvas.height],canvasBounds:{x:rect.x,y:rect.y,width:rect.width,height:rect.height},
      canvasHidden:canvas.hidden,errorHidden:error.hidden,noticeHidden:document.getElementById('anchor-live-notice').hidden,
      metadata:example?.metadata,hostScale:example?.scale,frame:example?.frame,document_id:globalThis.anchorLiveProbe.document_id});
  };
  const before=read(),canvas=document.querySelector('canvas');
  const png=canvas.toDataURL('image/png');
  const pixels=canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data;
  const parts=[];for(let i=0;i<pixels.length;i+=32768)parts.push(String.fromCharCode(...pixels.subarray(i,i+32768)));
  const rgba=btoa(parts.join(''));
  return {before,after:read(),png,rgba};
}
