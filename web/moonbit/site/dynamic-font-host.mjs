// Browser Canvas cannot surface GPUI/Cosmic Text's missing-glyph subscription.
// This fixed Devanagari probe is a host approximation, not a conformance oracle.
export const FONT_URL = 'https://fonts.gstatic.com/s/notosansdevanagari/v30/TuGoUUFzXI5FBtUq5a8bjKYTZjtRU6Sgv3NaV_SNmI0b8QQCQmHn6B2OHjbL_08AlXQly-A.ttf';
export const SAMPLE = 'नमस्ते 😀 दुनिया 👨‍👩‍👧‍👦 नमस्ते ❤️';
export const WAITING = 'Waiting for a missing Devanagari glyph…';
export const DOWNLOADING = 'Downloading Noto Sans Devanagari (219 KB)…';
export const LOADED = 'Font loaded. The same text is now shaped by Cosmic Text.';

export function createDynamicFontHost({fetchFont, FontFaceType, fonts, onChange}) {
  let phase = 'waiting';
  let message = WAITING;
  let attempts = 0;
  const state = () => ({phase, message, attempts});
  const change = (next, text) => {
    phase = next;
    message = text;
    onChange(state());
  };
  async function start(sample = SAMPLE) {
    if (attempts !== 0 || !/[\u0900-\u097f]/u.test(sample)) return false;
    attempts += 1;
    change('downloading', DOWNLOADING);
    try {
      const response = await fetchFont(FONT_URL, {mode:'cors', credentials:'omit'});
      if (!response.ok) throw new Error('Font request failed: HTTP ' + response.status);
      const bytes = await response.arrayBuffer();
      if (!bytes.byteLength) throw new Error('Font response was empty');
      const face = await new FontFaceType('Noto Sans Devanagari', bytes).load();
      fonts.add(face);
      change('loaded', LOADED);
    } catch (error) {
      change('failed', 'Font loading failed: ' + (error?.message || String(error)) + '. Reload to retry.');
    }
    return true;
  }
  return {start, get state() { return state(); }};
}
