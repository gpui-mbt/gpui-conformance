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
