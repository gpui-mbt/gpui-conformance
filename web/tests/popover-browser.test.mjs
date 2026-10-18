// Offline oracle/contract tests only. These do not execute either runtime,
// Playwright, OCR, or establish browser conformance.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {profiles,limits,parseTsv,phraseBox,visibleState,ObservationUnavailable} from './popover-browser.mjs';
const header='level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext';
const row=(text,i=1,conf=95,line=1)=>`5\t1\t1\t1\t${line}\t${i}\t${10+i*40}\t30\t35\t20\t${conf}\t${text}`;
const words=text=>parseTsv([header,...text.split(' ').map((w,i)=>row(w,i))].join('\n'));
test('profiles are bounded declared and narrower fractional smoke, never arbitrary viewport coverage',()=>{
  assert.deepEqual(profiles,[{width:800,height:600,dpr:1,kind:'declared-source-profile'},
    {width:480,height:600,dpr:1.25,kind:'narrow-fractional-smoke'}]);
  assert(limits.captures<=160);assert(limits.events<=128);assert(limits.ocrBytes<=4*1024*1024);
  assert(limits.ocrMs<=8000);assert(limits.runMs<=120000);
});
test('TSV only admits finite confident word observations',()=>{
  const data=[header,row('Open'),row('Popover',2),row('noise',3,10),row('invalid').replace('\t50\t30','\tNaN\t30'),'bad\trow'].join('\n');
  assert.deepEqual(parseTsv(data).map(w=>w.text),['Open','Popover']);
});
test('OCR target distinguishes Open from Opened and accounts for screenshot DPR',()=>{
  const observed=words('Opened Popover Open Popover');
  assert.deepEqual(phraseBox(observed,'Open Popover',1.25),{x:102,y:32,width:60,height:16});
  assert.throws(()=>phraseBox(words('Opened Popover'),'Open Popover'),ObservationUnavailable);
  assert.throws(()=>phraseBox(words('Open Popover Open Popover'),'Open Popover'),ObservationUnavailable);
});
test('OCR target cannot bridge lines or low-confidence words',()=>{
  assert.throws(()=>phraseBox(parseTsv([header,row('Open',1),row('Popover',2,95,2)].join('\n')),'Open Popover'),ObservationUnavailable);
  assert.throws(()=>phraseBox(parseTsv([header,row('Open',1),row('Popover',2,39)].join('\n')),'Open Popover'),ObservationUnavailable);
});
test('fail closed on missing required positive labels rather than qualifying absent text',()=>{
  for(const [text,parent,child] of [['',false,false],['Popover',false,false],['Popover',true,false],['first level Popover',true,true]])
    assert.throws(()=>visibleState(words(text),{blueBorder:0},parent,child),ObservationUnavailable);
});
test('observed child blue border and popup labels must agree with every expected state',()=>{
  visibleState(words('default opened Popover'),{blueBorder:0},false,false);
  visibleState(words('first level Popover'),{blueBorder:0},true,false);
  visibleState(words('first level Popover second level Popover'),{blueBorder:50},true,true);
  assert.throws(()=>visibleState(words('default opened Popover first level'),{blueBorder:0},false,false),/remains visible/);
  assert.throws(()=>visibleState(words('first level Popover second level'),{blueBorder:0},true,false),/remains visible/);
  assert.throws(()=>visibleState(words('first level Popover second level'),{blueBorder:0},true,true),/border ink/);
  assert.throws(()=>visibleState(words('first level Popover'),{blueBorder:50},true,false),/border ink/);
});
test('main existing workflow entrypoint invokes independent qualification before overall pass',()=>{
  const harness=readFileSync(new URL('./candidate-browser.mjs',import.meta.url),'utf8');
  assert.match(harness,/import \{ checkPopoverPair \} from '\.\/popover-browser\.mjs'/);
  assert(harness.indexOf('report.popover = await checkPopoverPair')<harness.indexOf("report.overall = 'passed'"));
});
test('harness retains originals, errors and trusted pointer evidence without runtime mutation',()=>{
  const source=readFileSync(new URL('./popover-browser.mjs',import.meta.url),'utf8');
  assert.doesNotMatch(source,/dispatchEvent|new (?:Mouse|Pointer|Keyboard)Event|wasmBindings\.|runtime\.|\.popover_pointer\(|\.popover_frame\(/);
  assert.match(source,/derived_from:`\$\{side\} actual screenshot OCR`/);
  assert.match(source,/ocr\.stderr\|\|''/);assert.match(source,/ocr\.stdout\|\|''/);
  assert.match(source,/events:await p\.evaluate\(\(\)=>popoverQualificationEvents\)/);
  for(const stage of ['initial','parent','child','child-dismissed','parent-dismissed','child-outside-release'])
    assert(source.includes(`observe('${stage}'`));
  assert.match(source,/\.mouse\.down\(\{button:'right'\}\)/);
  assert.match(source,/\.mouse\.up\(\{button:'right'\}\)/);
  assert.match(source,/events\.every\(e=>e\.trusted\)/);
  assert.match(source,/observation_unavailable/);
});
