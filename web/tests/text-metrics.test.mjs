import test from 'node:test';
import assert from 'node:assert/strict';
import { measureWrapperInputs } from '../moonbit/site/text-metrics.mjs';

function fixture(text = 'A e\u0301 👩‍💻 中') {
  return {font_family:'IBM Plex Sans', runs:Array.from({length:9}, (_,i) => ({text, font_size:i < 3 ? 16 : 20}))};
}
function context(measure = text => text.length * 2) {
  return {font:'', saves:0, restores:0, save(){this.saves++;}, restore(){this.restores++;}, measureText(text){return {width:measure(text)};}};
}
test('host supplies measured grapheme and whole-prefix inputs, never line breaks', () => {
  const ctx = context();
  const result = measureWrapperInputs(ctx, fixture());
  assert.deepEqual(result.graphemes[0], ['A',' ','e\u0301',' ','👩‍💻',' ','中']);
  assert.equal(result.prefixes[0].length,result.graphemes[0].length + 1);
  assert.equal(result.prefixes[0][0],0);
  assert.equal(result.prefixes[0].at(-1),fixture().runs[0].text.length * 2);
  assert.deepEqual(result.ellipsisWidths,[2,2]);
  assert.deepEqual(Object.keys(result),['graphemes','advances','prefixes','ellipsisWidths']);
  assert.deepEqual([ctx.saves,ctx.restores],[1,1]);
});
test('host preserves empty/Unicode input and passes distinct shaping measurements', () => {
  const empty = measureWrapperInputs(context(),fixture(''));
  assert.deepEqual(empty.graphemes[0],[]); assert.deepEqual(empty.prefixes[0],[0]);
  const shaped = measureWrapperInputs(context(text => text === 'AV' ? 3 : text.length * 2),fixture('AV'));
  assert.deepEqual(shaped.advances[0],[2,2]);
  assert.deepEqual(shaped.prefixes[0],[0,2,3]);
});
test('invalid host metrics or metadata fail before runtime layout and restore context', () => {
  for (const invalid of [NaN,Infinity,-1]) {
    const ctx=context(() => invalid);
    assert.throws(() => measureWrapperInputs(ctx,fixture()),/Invalid browser text metrics/);
    assert.equal(ctx.restores,1);
  }
  const metadata=fixture(); metadata.runs[4].font_size=0;
  const ctx=context();
  assert.throws(() => measureWrapperInputs(ctx,metadata),/Invalid text_wrapper font input/);
  assert.equal(ctx.restores,1);
  assert.throws(() => measureWrapperInputs(context(),{runs:[]}),/Expected/);
});

test('typography supplies per-font whole-prefix measurements for all eighteen specimens', async () => {
  const {measureTypographyInputs} = await import('../moonbit/site/text-metrics.mjs');
  const phrase = 'The quick brown fox jumps over the lazy dog';
  const metadata = {font_family:'Zed Mono', runs:[
    {id:20,text:'.ZedMono',font_size:16,style:'normal',weight:400},
    {id:500,text:'👩‍💻',font_size:24,style:'normal',weight:400},
    ...Array.from({length:18},(_,i)=>({id:900+i,text:phrase,font_size:10+i,style:'normal',weight:400})),
  ]};
  const ctx = context();
  ctx.measureText = function(text) {
    const size = Number(this.font.match(/(\d+)px/)[1]);
    return {width:text.length * size * (this.font.includes('Changed') ? 0.75 : 0.5)};
  };
  const first = measureTypographyInputs(ctx, metadata);
  assert.deepEqual(Object.keys(first),['widths','prefixes']);
  assert.equal(first.widths.length,20);
  assert.equal(first.prefixes.length,18);
  for(let i=0;i<18;i++) {
    assert.equal(first.prefixes[i].length,phrase.length+1);
    assert.equal(first.prefixes[i][0],0);
    assert.equal(first.prefixes[i][1],(10+i)*0.5);
    assert.equal(first.prefixes[i].at(-1),first.widths[2+i]);
  }
  metadata.font_family='Changed';
  const changed = measureTypographyInputs(ctx,metadata);
  assert.equal(changed.prefixes[17].at(-1),first.prefixes[17].at(-1)*1.5);
  assert.deepEqual([ctx.saves,ctx.restores],[2,2]);
  const bad = context(()=>NaN);
  assert.throws(()=>measureTypographyInputs(bad,metadata),/Invalid browser text metrics/);
  assert.equal(bad.restores,1);
});
