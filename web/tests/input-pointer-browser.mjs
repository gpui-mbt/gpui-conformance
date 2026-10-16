import assert from 'node:assert/strict';

// Runs against the real compiled MoonBit module in the selected input iframe.
// All focus entry uses trusted canvas clicks; never focus the hidden textarea.
export async function checkInputPointers(page, moon) {
  const canvas = moon.locator('canvas');
  const state = () => moon.locator('html').evaluate(() => gpuiExample.input);
  const selection = async () => { const s = await state(); return [s.anchor,s.head]; };
  const focused = () => moon.locator('html').evaluate(() =>
    document.activeElement?.matches('textarea[data-gpui-input="true"]'));
  const reset = async text => {
    await canvas.click({position:{x:270,y:15}});
    assert.equal(await focused(),true,'Reset must retain keyboard focus');
    assert.equal((await state()).text,'');
    if (text) await page.keyboard.insertText(text);
  };
  const point = async (x,y=50) => {
    const box=await canvas.boundingBox();
    return {x:box.x+x*box.width/300,y:box.y+y*box.height/300};
  };
  const move = async (x,y=50,steps=1) => {
    const p=await point(x,y); await page.mouse.move(p.x,p.y,{steps});
  };
  const down = async x => { await move(x); await page.mouse.down(); };
  const drag = async (from,to,y=50) => {
    await down(from); await move(to,y,5); await page.mouse.up();
    assert.equal((await state()).selecting,false);
  };
  const pointerId = () => canvas.evaluate(() =>
    gpuiExample.inputEvents.filter(e=>e.type==='pointer').at(-1).pointerId);

  await reset();
  await canvas.click({position:{x:12,y:50}});
  assert.equal(await focused(),true,'A normal trusted field click must focus the transport');
  await page.keyboard.type('abc');
  await canvas.click({position:{x:24,y:50}});
  assert.equal(await focused(),true,'The canvas default mousedown must not steal focus');
  await page.keyboard.type('X');
  assert.equal((await state()).text,'aXbc');
  assert.deepEqual(await selection(),[2,2]);
  await page.keyboard.press('ArrowLeft');
  await page.keyboard.press('Shift+ArrowRight');
  await page.keyboard.press('Control+c');
  await page.keyboard.press('Control+x');
  assert.equal((await state()).text,'abc');
  const clipboard=await moon.locator('html').evaluate(() =>
    gpuiExample.inputEvents.filter(e=>['copy','cut'].includes(e.type)));
  assert(clipboard.some(e=>e.type==='copy' && e.length===1 && e.trusted));
  assert(clipboard.some(e=>e.type==='cut' && e.length===1 && e.trusted));

  await reset('abcdef');
  for (const y of [35,70]) {
    await canvas.click({position:{x:36,y}});
    assert.deepEqual(await selection(),[2,2],'A plain click in field padding must stay collapsed');
    assert.equal(await focused(),true);
  }
  await drag(12,60);
  assert.deepEqual(await selection(),[0,4]);
  await drag(72,24);
  assert.deepEqual(await selection(),[5,1]);
  await page.keyboard.down('Shift');
  await canvas.click({position:{x:48,y:50}});
  assert.deepEqual(await selection(),[5,3],'Shift-click retains the directional anchor');
  await drag(36,12);
  await page.keyboard.up('Shift');
  assert.deepEqual(await selection(),[5,0],'Shift-drag retains the existing anchor');

  // Capture keeps the gesture alive beyond the field and iframe canvas.
  await down(12);
  const id=await pointerId();
  assert.equal(await canvas.evaluate((c,id)=>c.hasPointerCapture(id),id),true);
  await move(350,330,5);
  await page.mouse.up();
  assert.deepEqual(await selection(),[0,6]);
  assert.equal((await state()).selecting,false);
  assert.equal(await canvas.evaluate((c,id)=>c.hasPointerCapture(id),id),false);
  await move(24);
  assert.deepEqual(await selection(),[0,6],'Hover after outside release cannot extend selection');
  await drag(84,-30,50);
  assert.deepEqual(await selection(),[6,0]);

  // Cancellation is a deterministic DOM transport check. It is explicitly
  // separate from the trusted mouse paths above, not hardware-touch evidence.
  await down(12); await move(36);
  const cancelled=await selection();
  await canvas.evaluate((c,id)=>c.dispatchEvent(new PointerEvent('pointercancel',
    {bubbles:true,pointerId:id,isPrimary:true})),await pointerId());
  assert.equal((await state()).selecting,false);
  await move(72); await page.mouse.up();
  assert.deepEqual(await selection(),cancelled);

  await down(12); await move(48);
  const lost=await selection();
  await canvas.evaluate((c,id)=>c.releasePointerCapture(id),await pointerId());
  await move(60); // Chromium delivers lostpointercapture before this event.
  assert.equal((await state()).selecting,false);
  await page.mouse.up();
  assert.deepEqual(await selection(),lost);

  await down(12); await move(36);
  const blurred=await selection();
  await moon.locator('html').evaluate(() => document.activeElement.blur());
  assert.equal((await state()).selecting,false);
  await move(72); await page.mouse.up();
  assert.deepEqual(await selection(),blurred);
  await canvas.click({position:{x:48,y:50}});
  await page.keyboard.type('!');
  assert.equal((await state()).text,'abc!def','A new click works after cancellation and blur');

  await reset('a😀漢');
  await drag(24,36);
  assert.deepEqual(await selection(),[1,3],'Emoji selection must not split UTF-16 surrogate pairs');
  await page.keyboard.press('Control+x');
  assert.equal((await state()).text,'a漢');
  await page.keyboard.press('Control+z');
  assert.equal((await state()).text,'a😀漢');
  await drag(48,24);
  assert.deepEqual(await selection(),[4,1]);

  await reset('abcdefghijklmnopqrstuvwxyz0123456789');
  assert((await state()).scrollOffset>0);
  await drag(288,264);
  assert.deepEqual(await selection(),[36,34],'Scrolled text hit testing uses the current scroll offset');
  await page.keyboard.press('Control+x');
  assert.equal((await state()).text,'abcdefghijklmnopqrstuvwxyz01234567');

  await reset('abcdefghijklmnopqrstuvwxyz0123456789');
  await page.keyboard.press('Home');
  assert.equal((await state()).scrollOffset,0);
  await drag(12,600);
  assert.deepEqual(await selection(),[0,36],'Captured drag must reach text beyond the right viewport');
  assert((await state()).scrollOffset>0);
  await drag(288,-300);
  assert.deepEqual(await selection(),[36,0],'Captured drag must reach text beyond the left viewport');
  assert.equal((await state()).scrollOffset,0);
  await drag(48,48,120);
  assert.deepEqual(await selection(),[3,36],'Dragging below a single line selects to its end');
  await page.keyboard.press('Home');
  await drag(48,48,10);
  assert.deepEqual(await selection(),[3,0],'Dragging above a single line selects to its start');

  const events=await moon.locator('html').evaluate(() => [...gpuiExample.inputEvents]);
  assert(events.some(e=>e.type==='pointermove' && e.trusted));
  assert(events.some(e=>e.type==='pointercancel'));
  assert(events.some(e=>e.type==='lostpointercapture'));
  await reset();
  return {events,checked:['trusted click-to-type and Reset-to-type','caret placement and trusted copy/cut',
    'forward/backward/Shift drag selection','outside release and capture loss','synthetic pointer cancellation',
    'blur cleanup and subsequent click','supplementary Unicode boundaries','horizontally scrolled and offscreen selection','above/below-line endpoints']};
}
