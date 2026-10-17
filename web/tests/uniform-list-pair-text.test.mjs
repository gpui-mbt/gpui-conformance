import test from 'node:test';
import assert from 'node:assert/strict';
import {measureUniformListInputs} from '../moonbit/site/uniform-list-text.mjs';
function fixture(){
  let saved;
  const context={font:'initial',textRendering:'auto',fontKerning:'auto',calls:[],
    save(){saved={font:this.font,textRendering:this.textRendering,fontKerning:this.fontKerning};},
    restore(){Object.assign(this,saved);},
    measureText(text){this.calls.push({text,rendering:this.textRendering,kerning:this.fontKerning});return {width:text.length*7.3};}};
  const metadata={id:'uniform_list',font_family:'IBM Plex Sans',font_size:16,runs:Array.from({length:50},(_,i)=>({text:`Item ${i+1}`}))};
  return {context,metadata};
}
test('unhinted source ASCII widths/prefixes/glyph metrics are explicit host inputs',()=>{
  const {context,metadata}=fixture();const inputs=measureUniformListInputs(context,metadata);
  assert.equal(inputs.widths.length,50);assert.equal(inputs.widths[0],6*7.3);assert.equal(inputs.widths[49],7*7.3);
  assert.deepEqual(inputs.prefixes[0],[0,7.3,14.6,21.9,29.2,36.5,43.8]);
  assert.equal(inputs.advances[0].length,6);assert(context.calls.every(c=>c.rendering==='geometricPrecision'&&c.kerning==='normal'));
  assert.equal(inputs.shaping_mode,'geometricPrecision');assert.equal(inputs.raster_mode,'auto');
  assert.equal(context.textRendering,'auto');assert.equal(context.font,'initial');
  assert(!('origins' in inputs)&&!('rows' in inputs)&&!('offset' in inputs));
});
test('unsupported labels and invalid glyph metrics fail and restore raster state',()=>{
  const f=fixture();f.metadata.runs[3].text='different';assert.throws(()=>measureUniformListInputs(f.context,f.metadata));
  assert.equal(f.context.textRendering,'auto');const g=fixture();g.context.measureText=()=>({width:Infinity});
  assert.throws(()=>measureUniformListInputs(g.context,g.metadata));assert.equal(g.context.textRendering,'auto');
});
