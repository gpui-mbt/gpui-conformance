import test from 'node:test';
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {readGridFrame} from '../moonbit/site/grid-layout-host.mjs';
import {validateFrame,drawFrame} from '../moonbit/site/render.mjs';

// Optional actual compiled ESM check. Generic source-only runs explicitly skip
// it; a separately built runtime is required. No mock can substitute for it.
const runtimePath=process.env.GPUI_GRID_LAYOUT_RUNTIME;

// Exercise the actual host painter, including its DPR admission contract.
// Canvas calls do not establish browser pixel or Rust parity.
function assertPaints(frame,width,height,scale) {
  let draws=0;
  const context=new Proxy({}, {get:(_object,key)=>key==='measureText'
    ? ()=>({fontBoundingBoxAscent:16,fontBoundingBoxDescent:4})
    : ()=>{draws++;}});
  drawFrame(context,frame,{width,height,font_family:'IBM Plex Sans'},scale);
  assert(draws>0);
}
test('actual compiled candidate exports retain query bounds thresholds spans and resize restoration',
  {skip:!runtimePath},async()=>{
    const runtime=await import(pathToFileURL(runtimePath));
    const metadata=JSON.parse(runtime.grid_layout_metadata());
    assert.equal(metadata.id,'grid_layout');assert.equal(metadata.conformance,'unverified');
    assert.deepEqual(metadata.viewport_profile,{widths:[399,400,401,500],height:500,device_scale:1});
    const context={measureText:text=>({width:Array.from(text).length*8})};
    const results=[];
    const expected={
      399:[[0,0,399,48],[0,52,399,80],[0,136,399,228],[0,368,399,80],[0,452,399,48]],
      400:[[0,0,400,97],[0,101,77,224],[81,101,238,298],[323,101,77,298],[0,403,400,97]],
      401:[[0,0,401,97],[0,101,77,224],[81,101,239,298],[324,101,77,298],[0,403,401,97]],
      500:[[0,0,500,97],[0,101,97,224],[101,101,298,298],[403,101,97,298],[0,403,500,97]],
    };
    for(const width of [500,399,400,401,500,399,400,500]) {
      const result=readGridFrame(runtime,context,{innerWidth:width,innerHeight:500},1);
      const frame=result.frame,grid=frame.grid_layout;validateFrame(frame);
      assert.deepEqual(grid.query_size,{width,height:500});assert.equal(grid.mode,width===399?'stack':'grid');
      assert.equal(grid.comparison_profile_match,true);assert.equal(grid.frame_query_callbacks,1);assert.equal(grid.frame_layout_passes,1);assert.equal(grid.host_layout_passes,2);
      assert.equal(result.content.query_callbacks,1);assert.equal(result.content.layout_passes,1);
      assert.deepEqual(grid.blocks.map(block=>Object.values(block.bounds)),expected[width]);
      assert.deepEqual(grid.blocks.map(block=>block.name),['header','toc','content','ad','footer']);
      assert.deepEqual(frame.shadows,[{id:2,kind:'shadow_lg'}]);
      assert.equal(frame.decorations.length,5);
      assert(frame.decorations.every(d=>d.radius===6&&d.border==='#ffffff'&&d.border_width===1&&d.border_style==='dashed'));
      const texts=frame.snapshot.items.filter(item=>item.kind==='text_run');
      assert.equal(texts[0].text,`Header — ${width}px`);
      assert.deepEqual(texts[0].text_origin,{x:1,y:1});
      assert.deepEqual(texts.map(item=>item.text),width===399
        ? [`Header — ${width}px`,'Table of contents','Content','AD :(','Footer']
        : [`Header — ${width}px`,'Table of ','contents','Content','AD :(','Footer']);
      // Exercise the actual SceneSnapshot through the real Canvas adapter with
      // a drawing recorder. This does not observe browser or GPU pixels.
      let draws=0;
      const paintContext=new Proxy({}, {get:(_object,key)=>key==='measureText'
        ? ()=>({fontBoundingBoxAscent:16,fontBoundingBoxDescent:4})
        : ()=>{draws++;}});
      drawFrame(paintContext,frame,{...metadata,width,height:500},1);assert(draws>0);
      results.push(frame);
    }
    assert.deepEqual(results[0],results.at(-1),'Same-size fresh requests restore deterministic candidate output');
    for(const [width,height,scale] of [[16,32,.25],[16.01,32.01,.25],[16384,32,1],[8192,4096.49,1],[800,600,2],[320,240,1.25],[16,32,1],[399.5,713,1.25],[500,501,1],[500,500,2],[1920,1080,2],[4096,8192,1],[500,500,.25],[500,500,4]]) {
      const result=readGridFrame(runtime,context,{innerWidth:width,innerHeight:height},scale);
      validateFrame(result.frame);assertPaints(result.frame,width,height,scale);
      assert.equal(result.frame.grid_layout.comparison_profile_match,false);
      assert.equal(result.frame.conformance,'unverified');
      assert.equal(result.frame.grid_layout.mode,result.frame.grid_layout.query_size.width<400?'stack':'grid');
      assert.equal(result.width,width);assert.equal(result.height,height);
    }
    for(const [width,height,scale] of [[1,1,.5],[.1,.1,8],[15.99,500,1],[500,31.99,1],[0,500,1],[-1,500,1],[NaN,500,1],[Infinity,500,1],[500,0,1],[500,NaN,1],[500,Infinity,1],[500,500,0],[500,500,NaN],[500,500,Infinity],[1,1,.25],[500,500,.249],[800,600,4.01],[800,600,5],[500,500,8],[500,500,4.01],[16385,500,1],[8192.25,100,2],[8193,100,2],[8192,8192,1],[8192,4096.5,1]]) {
      assert.equal(JSON.parse(runtime.grid_layout_content(width,height,scale)).error,'invalid_live_viewport');
      assert.equal(JSON.parse(runtime.grid_layout_frame(width,height,[],scale)).error,'invalid_live_viewport');
    }
    assert.equal(JSON.parse(runtime.grid_layout_frame(500,500,[],1)).error,'invalid_metrics');
  });


test('compiled live viewport matrix preserves valid paint and rejects backing-store overflows',
  {skip:!runtimePath},async()=>{
    const runtime=await import(pathToFileURL(runtimePath));
    const context={measureText:text=>({width:Array.from(text).length*8})};
    let accepted=0,rejected=0;
    for(const width of [16,17,32,320,398,399,399.5,400,401,800,1920])
      for(const height of [32,33,40,48,100,240,500,713])
        for(const scale of [.25,.3,.5,1,1.25,1.5,2,3,4]) {
          if(Math.round(width*scale)*Math.round(height*scale)>33554432) {
            assert.equal(JSON.parse(runtime.grid_layout_content(width,height,scale)).error,'invalid_live_viewport');
            rejected++;continue;
          }
          const {frame}=readGridFrame(runtime,context,{innerWidth:width,innerHeight:height},scale);
          validateFrame(frame);assertPaints(frame,width,height,scale);assert.equal(frame.conformance,'unverified');accepted++;
        }
    assert.equal(accepted,792);assert.equal(rejected,0);
  });
