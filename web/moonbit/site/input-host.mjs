// Browser-only transport. The compiled MoonBit TextField owns every transaction;
// no DOM textarea value or JS shadow document is authoritative.
export function createInputHost({runtime, canvas, render, onError = error => console.error(error)}) {
  const editor = document.createElement('textarea');
  editor.setAttribute('aria-label', 'GPUI text input');
  editor.setAttribute('autocomplete', 'off');
  editor.setAttribute('autocorrect', 'off');
  editor.setAttribute('spellcheck', 'false');
  editor.dataset.gpuiInput = 'true';
  Object.assign(editor.style, {position:'fixed', left:'8px', top:'38px', width:'1px',
    height:'1px', opacity:'0', zIndex:'-1', padding:'0', border:'0'});
  canvas.parentElement.append(editor);
  let hostComposing = false;
  let cancellation = false;
  let suppressFinalInput = false;
  let finalCompositionText = '';
  let activePointer = null;
  const events = [];
  const record = (type, extra = {}) => {
    events.push({type, ...extra});
    if (events.length > 200) events.shift();
  };
  const mutate = (fn, detail) => {
    try {
      if (fn() === false) {
        record('rejected', {detail});
        return false;
      }
      render();
      return true;
    } catch (error) {
      onError(error);
      return false;
    }
  };
  const readState = () => ({
    text:runtime.input_text(),
    anchor:runtime.input_anchor(),
    head:runtime.input_head(),
    markedStart:runtime.input_marked_start(),
    markedEnd:runtime.input_marked_end(),
    composing:runtime.input_composing(),
    canUndo:runtime.input_can_undo(),
    canRedo:runtime.input_can_redo(),
    hostComposing,
    selecting:runtime.input_selecting(),
    scrollOffset:runtime.input_scroll_offset(),
  });
  const endPointer = (reason) => {
    if (activePointer === null) return;
    const pointerId = activePointer;
    activePointer = null;
    // Clear ownership before release: lostpointercapture may be dispatched
    // synchronously by a host and must not end a newer gesture.
    mutate(() => {runtime.input_pointer_end(); return true;}, reason);
    if (canvas.hasPointerCapture(pointerId)) canvas.releasePointerCapture(pointerId);
    record(reason, {pointerId});
  };
  const api = {editor, events, readState, reset() {
    endPointer('pointer-reset');
    hostComposing = false; cancellation = false; suppressFinalInput = false; finalCompositionText = '';
    mutate(() => {runtime.input_reset(); return true;}, 'reset');
    record('reset');
  }};
  editor.addEventListener('compositionstart', event => {
    endPointer('pointer-composition');
    hostComposing = true; cancellation = false;
    suppressFinalInput = false; finalCompositionText = '';
    record('compositionstart', {trusted:event.isTrusted});
  });
  editor.addEventListener('compositionupdate', event => {
    if (!hostComposing) return;
    const preedit = event.data || '';
    // DOM composition selection is not uniformly exposed. The current browser
    // end-caret is a host choice; the MoonBit value model validates UTF-16.
    mutate(() => runtime.input_preedit(preedit, preedit.length, preedit.length), 'preedit');
    record('compositionupdate', {preedit, trusted:event.isTrusted});
  });
  editor.addEventListener('compositionend', event => {
    if (!hostComposing) return;
    hostComposing = false;
    // Empty compositionend is ambiguous across IMEs; cancel rather than delete
    // an originally selected range without an explicit committed payload.
    const committed = !cancellation && Boolean(event.data);
    mutate(() => runtime.input_finish(event.data || '', committed), 'compositionend');
    record('compositionend', {data:event.data, committed, trusted:event.isTrusted});
    cancellation = false;
    suppressFinalInput = committed;
    finalCompositionText = committed ? event.data : '';
    editor.value = '';
  });
  editor.addEventListener('keydown', event => {
    if (hostComposing || event.isComposing || event.key === 'Process' || event.keyCode === 229) {
      if (event.key === 'Escape') {
        cancellation = true;
        record('ime-cancel-request', {trusted:event.isTrusted});
      }
      return;
    }
    // A later trusted keyboard event starts a new edit, not a duplicate IME
    // finalization; do not drop its first inserted character.
    suppressFinalInput = false;
    finalCompositionText = '';
    const platform = event.ctrlKey || event.metaKey;
    const shortcut = platform && ['a','z','y'].includes(event.key.toLowerCase());
    const nav = ['ArrowLeft','ArrowRight','Home','End','Backspace','Delete'].includes(event.key);
    if (shortcut || nav) {
      event.preventDefault();
      mutate(() => runtime.input_key(event.key, event.shiftKey, event.ctrlKey, event.metaKey), 'keydown');
      record('keydown', {key:event.key, shift:event.shiftKey, trusted:event.isTrusted});
    }
  });
  editor.addEventListener('beforeinput', event => {
    if (hostComposing || event.isComposing || event.inputType === 'insertCompositionText') return;
    if (suppressFinalInput) {
      const duplicate = (event.inputType === 'insertFromComposition' ||
        event.inputType === 'insertText') && event.data === finalCompositionText;
      suppressFinalInput = false;
      finalCompositionText = '';
      if (duplicate) { event.preventDefault(); return; }
    }
    if (event.inputType === 'insertText' && event.data != null) {
      event.preventDefault();
      mutate(() => runtime.input_insert(event.data), 'insertText');
      record('insertText', {text:event.data, trusted:event.isTrusted});
    }
  });
  editor.addEventListener('input', event => {
    // beforeinput may not be cancellable on some hosts; only an unhandled
    // browser value may be forwarded, and is immediately cleared.
    if (hostComposing || event.isComposing) return;
    if (suppressFinalInput && editor.value === finalCompositionText) {
      suppressFinalInput = false; finalCompositionText = ''; editor.value = ''; return;
    }
    suppressFinalInput = false; finalCompositionText = '';
    if (editor.value) {
      const data = editor.value;
      editor.value = '';
      mutate(() => runtime.input_insert(data), 'input-fallback');
      record('input-fallback', {trusted:event.isTrusted});
    }
  });
  editor.addEventListener('copy', event => {
    const selection = runtime.input_copy();
    if (!selection || !event.clipboardData) return;
    event.clipboardData.setData('text/plain', selection);
    event.preventDefault();
    record('copy', {length:selection.length, trusted:event.isTrusted});
  });
  editor.addEventListener('cut', event => {
    const selection = runtime.input_copy();
    if (!selection || !event.clipboardData) return;
    event.clipboardData.setData('text/plain', selection);
    event.preventDefault();
    mutate(() => runtime.input_cut(), 'cut');
    record('cut', {length:selection.length, trusted:event.isTrusted});
  });
  editor.addEventListener('paste', event => {
    if (!event.clipboardData || hostComposing) return;
    const value = event.clipboardData.getData('text/plain').replace(/[\r\n]/g, ' ');
    event.preventDefault();
    mutate(() => runtime.input_insert(value), 'paste');
    record('paste', {text:value, trusted:event.isTrusted});
  });
  const coordinates = event => {
    const rect = canvas.getBoundingClientRect();
    if (!(rect.width > 0 && rect.height > 0)) return null;
    const x = (event.clientX-rect.left)*300/rect.width;
    const y = (event.clientY-rect.top)*300/rect.height;
    return Number.isFinite(x) && Number.isFinite(y) ? {x,y} : null;
  };
  canvas.style.touchAction = 'none';
  canvas.addEventListener('pointerdown', event => {
    if (event.button !== 0 || !event.isPrimary || activePointer !== null) return;
    const point = coordinates(event);
    if (!point) return;
    const {x,y} = point;
    const reset = x >= 244 && x <= 294 && y >= 2 && y <= 28;
    if (reset) api.reset();
    else if (!mutate(() => runtime.input_pointer(x,y,event.shiftKey), 'pointer')) return;
    // Cancel the following native mouse-focus action before focusing the
    // transport textarea. Otherwise a trusted field click blurs it to BODY.
    event.preventDefault();
    editor.focus({preventScroll:true});
    if (!reset) {
      activePointer = event.pointerId;
      try { canvas.setPointerCapture(activePointer); }
      catch { endPointer('pointer-capture-failed'); }
    }
    record('pointer', {x,y,pointerId:event.pointerId,shift:event.shiftKey,trusted:event.isTrusted});
  });
  canvas.addEventListener('pointermove', event => {
    if (event.pointerId !== activePointer) return;
    if (!(event.buttons & 1)) { endPointer('pointer-buttons-released'); return; }
    const point = coordinates(event);
    if (!point) return;
    event.preventDefault();
    mutate(() => runtime.input_pointer_move(point.x,point.y), 'pointermove');
    record('pointermove', {...point,pointerId:event.pointerId,trusted:event.isTrusted});
  });
  canvas.addEventListener('pointerup', event => {
    if (event.pointerId !== activePointer) return;
    const point = coordinates(event);
    if (point) mutate(() => runtime.input_pointer_move(point.x,point.y), 'pointerup');
    endPointer('pointerup');
  });
  canvas.addEventListener('pointercancel', event => {
    if (event.pointerId === activePointer) endPointer('pointercancel');
  });
  canvas.addEventListener('lostpointercapture', event => {
    if (event.pointerId === activePointer) endPointer('lostpointercapture');
  });
  window.addEventListener('blur', () => endPointer('pointer-window-blur'));
  window.addEventListener('pagehide', () => endPointer('pointer-pagehide'));
  editor.addEventListener('blur', () => {
    endPointer('pointer-blur');
    if (hostComposing) {
      hostComposing = false;
      cancellation = true;
      mutate(() => runtime.input_finish('', false), 'blur-cancel');
      record('blur-cancel');
    }
  });
  editor.focus({preventScroll:true});
  return api;
}
