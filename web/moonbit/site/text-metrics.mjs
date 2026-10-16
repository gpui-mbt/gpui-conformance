// Font measurement and grapheme segmentation are explicit browser host inputs.
// The MoonBit port, not this adapter, chooses wrap points and elided text.
export function measureWrapperInputs(context, metadata) {
  if (typeof Intl.Segmenter !== 'function') throw new Error('Grapheme segmentation is unavailable');
  if (!Array.isArray(metadata.runs) || metadata.runs.length !== 9) throw new Error('Expected the upstream text_wrapper runs');
  const segmenter = new Intl.Segmenter('und', {granularity: 'grapheme'});
  const graphemes = [], advances = [], prefixes = [];
  context.save();
  try {
    for (const run of metadata.runs) {
      if (typeof run.text !== 'string' || ![16,20].includes(run.font_size)) throw new Error('Invalid text_wrapper font input');
      context.font = `normal 400 ${run.font_size}px "${metadata.font_family}"`;
      const segments = Array.from(segmenter.segment(run.text), item => item.segment);
      graphemes.push(segments);
      advances.push(segments.map(text => context.measureText(text).width));
      let prefix = '';
      prefixes.push([0, ...segments.map(text => {
        prefix += text;
        return context.measureText(prefix).width;
      })]);
    }
    const ellipsisWidths = [16,20].map(size => {
      context.font = `normal 400 ${size}px "${metadata.font_family}"`;
      return context.measureText('…').width;
    });
    if ([...advances.flat(), ...prefixes.flat(), ...ellipsisWidths].some(width => !Number.isFinite(width) || width < 0)) throw new Error('Invalid browser text metrics');
    return {graphemes, advances, prefixes, ellipsisWidths};
  } finally { context.restore(); }
}
