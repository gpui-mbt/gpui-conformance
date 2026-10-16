import assert from 'node:assert/strict';

// The real Chromium DOM is used with the compiled MoonBit TextField. These
// programmatic events must not be reported as a live Japanese IME test.
export async function checkInputIme(page, moon) {
  const canvas=moon.locator('canvas');
  const editor=moon.locator('textarea[data-gpui-input="true"]');
  const state=()=>moon.locator('html').evaluate(()=>globalThis.gpuiExample.input);
  const reset=async()=>{
    await canvas.click({position:{x:270,y:15}});
    assert.equal((await state()).text,'');
    assert.equal(await editor.evaluate(el=>document.activeElement===el),true,
      'Reset must preserve the trusted click-to-focus path from PR #42');
  };
  const compose=(preedit,final,{escape=false}={})=>editor.evaluate((el,args)=>{
    el.dispatchEvent(new CompositionEvent('compositionstart',{bubbles:true,data:''}));
    el.dispatchEvent(new CompositionEvent('compositionupdate',{bubbles:true,data:args.preedit}));
    if (args.escape) el.dispatchEvent(new KeyboardEvent('keydown',{
      bubbles:true,cancelable:true,key:'Escape',keyCode:27,isComposing:true,
    }));
    el.dispatchEvent(new CompositionEvent('compositionend',{bubbles:true,data:args.final}));
  },{preedit,final,escape});
  const before=(data,{cancelable=true,inputType='insertText',applyNative=false}={})=>
    editor.evaluate((el,args)=>{
      const event=new InputEvent('beforeinput',{
        bubbles:true,cancelable:args.cancelable,inputType:args.inputType,data:args.data,
      });
      el.dispatchEvent(event);
      // Synthetic events do not automatically mutate DOM. Explicitly mimic
      // only the browser edit that preventDefault cannot block.
      if (args.applyNative && !event.defaultPrevented) {
        el.value=args.data;
        el.dispatchEvent(new InputEvent('input',{
          bubbles:true,inputType:args.inputType,data:args.data,
        }));
      }
      return {cancelable:event.cancelable,prevented:event.defaultPrevented,value:el.value};
    },{data,cancelable,inputType,applyNative});
  const observed={};

  await reset();
  await compose('にほん','日本');
  assert.equal((await state()).text,'日本','compositionend must commit through MoonBit once');
  const unavoidable=await before('日本',{cancelable:false,applyNative:true});
  assert.equal(unavoidable.cancelable,false);
  assert.equal(unavoidable.prevented,false);
  assert.equal(unavoidable.value,'','Non-cancelable duplicate must be cleared from transport');
  assert.equal((await state()).text,'日本','Replayed non-cancelable final must not insert twice');
  observed.noncancelableFinal=await state();

  await page.keyboard.type('!');
  assert.equal((await state()).text,'日本!','Next trusted keystroke must not be swallowed');
  await page.keyboard.press('Control+z');
  assert.equal((await state()).text,'日本');
  await page.keyboard.press('Control+z');
  assert.equal((await state()).text,'','IME commit must retain one TextField undo entry');

  await reset();
  await compose('にほん','日本');
  const canceled=await before('日本',{inputType:'insertFromComposition'});
  assert.equal(canceled.prevented,true);
  assert.equal((await state()).text,'日本');
  const repeated=await before('日本');
  assert.equal(repeated.prevented,true);
  assert.equal((await state()).text,'日本日本',
    'After canceled duplicate, the next same-data edit must still be accepted');
  observed.cancelableFinal=await state();

  await reset();
  await compose('にほん','日本');
  await editor.evaluate(el=>{
    el.value='日本';
    el.dispatchEvent(new InputEvent('input',{
      bubbles:true,inputType:'insertFromComposition',data:'日本',
    }));
  });
  assert.equal((await state()).text,'日本','Input-only replay must be suppressed');

  await reset();
  await compose('にほん','日本');
  await before('!');
  assert.equal((await state()).text,'日本!','Immediate different beforeinput must be accepted');

  await reset();
  await compose('にほん','日本');
  const nativeOrdinary=await before('!',{cancelable:false,applyNative:true});
  assert.equal(nativeOrdinary.prevented,false);
  assert.equal((await state()).text,'日本!',
    'A non-cancelable regular character must arrive from input fallback just once');
  observed.noncancelableOrdinary=await state();

  await reset();
  await compose('かな','かな',{escape:true});
  assert.equal((await state()).text,'','Escape must cancel the composition');
  await page.keyboard.type('X');
  assert.equal((await state()).text,'X');

  await reset();
  await compose('かな','');
  assert.equal((await state()).text,'','Ambiguous empty finalization must cancel');
  await page.keyboard.type('Y');
  assert.equal((await state()).text,'Y');

  const result={
    checked:['commit once','non-cancelable final beforeinput + native input',
      'trusted following key + separate undo entries','cancelable duplicate + same-data next edit',
      'input-only replay','immediate distinct character','non-cancelable ordinary character',
      'Escape and empty cancellation','trusted Reset click maintains focus'],
    observation:'synthetic Chromium events + compiled MoonBit TextField; NOT live Japanese IME',
    states:observed,
  };
  await reset();
  return result;
}
