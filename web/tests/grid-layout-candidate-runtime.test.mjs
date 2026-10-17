import test from 'node:test';
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {readGridFrame} from '../moonbit/site/grid-layout-host.mjs';
import {validateFrame,drawFrame} from '../moonbit/site/render.mjs';

// Optional actual compiled ESM check. Generic source-only runs explicitly skip
// it; a separately built runtime is required. No mock can substitute for it.
const runtimePath=process.env.GPUI_GRID_LAYOUT_RUNTIME;
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
      assert.equal(grid.frame_query_callbacks,1);assert.equal(grid.frame_layout_passes,1);assert.equal(grid.host_layout_passes,2);
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
    for(const [width,height,scale] of [[16,500,1],[398,500,1],[402,500,1],[500,501,1],[500,500,2]]) {
      assert.equal(JSON.parse(runtime.grid_layout_content(width,height,scale)).error,'unsupported_viewport_profile');
      assert.equal(JSON.parse(runtime.grid_layout_frame(width,height,[],scale)).error,'unsupported_viewport_profile');
    }
    assert.equal(JSON.parse(runtime.grid_layout_frame(500,500,[],1)).error,'invalid_metrics');
  });
