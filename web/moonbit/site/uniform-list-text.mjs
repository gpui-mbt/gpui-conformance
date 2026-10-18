// Bounded ASCII-only host shaping inputs. Source5a CosmicTextSystem shapes with
// Hinting::Disabled (crates/gpui_wgpu/src/cosmic_text_system.rs:758), then rasterizes
// individual glyphs with Swash hint(true) (:530). Canvas auto rounds advances;
// geometricPrecision supplies unhinted shaping metrics, but must not become the
// raster mode. MoonBit derives glyph origins; JS never positions list rows.
export function measureUniformListInputs(context,metadata) {
  if(metadata?.id!=='uniform_list'||metadata.font_family!=='IBM Plex Sans'||metadata.font_size!==16||
    !Array.isArray(metadata.runs)||metadata.runs.length!==50)throw new Error('Invalid uniform-list typography metadata');
  const widths=[],prefixes=[],advances=[];
  context.save();
  try {
    context.font='normal 400 16px "IBM Plex Sans"';
    context.textRendering='geometricPrecision';context.fontKerning='normal';
    if(context.textRendering!=='geometricPrecision')throw new Error('Unhinted Canvas shaping is unavailable');
    for(const [index,run] of metadata.runs.entries()) {
      if(run.text!==`Item ${index+1}`)throw new Error('Only source ASCII Item labels are supported');
      let prefix='';const values=[0],chars=Array.from(run.text);
      const glyphs=chars.map(char=>context.measureText(char).width);
      for(const char of chars){prefix+=char;values.push(context.measureText(prefix).width);}
      if([...values,...glyphs].some(x=>!Number.isFinite(x)||x<0))throw new Error('Invalid unhinted shaping input');
      widths.push(values.at(-1));prefixes.push(values);advances.push(glyphs);
    }
    return {widths,prefixes,advances,shaping_mode:'geometricPrecision',raster_mode:'auto',kerning:'normal',
      limitation:'Source ASCII Item1..50 only; no general complex-text equivalence'};
  } finally {context.restore();}
}
