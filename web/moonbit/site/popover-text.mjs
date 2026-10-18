// Source-specific shaping input only. MoonBit owns wrapping and all geometry.
export const popoverRuns = [
  ['Opened Popover',16], ['Open Popover',16],
  ['Here is an example text rendered, to ensure the Popover will float above this contents.',16],
  ['Child Popover',14],
  ['This is a default opened Popover, we can use deferred to render it in a floating layer.',14],
  ['This is first level Popover, we can use deferred to render it in a floating layer.\nClick outside to close.',14],
  ['This is second level Popover with nested deferred!',14],
];
export async function loadPopoverFont({FontFaceType,fonts}) {
  const face = new FontFaceType('IBM Plex Sans','url(./IBMPlexSans-Regular.ttf)');
  const loaded = await face.load();
  if (loaded.status !== 'loaded') throw new Error('Bundled popover font failed to load');
  fonts.add(loaded);
  await fonts.ready;
  if (!fonts.check('16px "IBM Plex Sans"') || !fonts.check('14px "IBM Plex Sans"'))
    throw new Error('Bundled popover font is unavailable');
  return loaded;
}
export function measurePopoverInputs(context,metadata) {
  if(metadata?.id!=='popover'||metadata.font_family!=='IBM Plex Sans'||
     !Array.isArray(metadata.runs)||metadata.runs.length!==popoverRuns.length)
    throw new Error('Invalid popover typography metadata');
  const prefixes=[];
  context.save();
  try {
    context.textRendering='geometricPrecision';context.fontKerning='normal';
    if(context.textRendering!=='geometricPrecision')throw new Error('Unhinted Canvas shaping is unavailable');
    for(const [index,run] of metadata.runs.entries()) {
      const [text,size]=popoverRuns[index];
      if(run.text!==text||run.font_size!==size)throw new Error('Unexpected popover source text/style');
      context.font=`normal 400 ${size}px "IBM Plex Sans"`;
      for(const segment of text.split('\n')) {
        let prefix='';const values=[0];
        for(const character of segment) {
          prefix+=character;
          const width=context.measureText(prefix).width;
          if(!Number.isFinite(width)||width<=values.at(-1)||width>16384)
            throw new Error('Invalid popover prefix metric');
          values.push(width);
        }
        prefixes.push(values);
      }
    }
    return prefixes;
  }finally{context.restore();}
}
