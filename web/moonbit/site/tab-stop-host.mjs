import {createFocusVisibleHost} from './focus-visible-host.mjs';

// Export-name adapter only. Reuse the verified browser transport unchanged;
// compiled MoonBit owns traversal, geometry, owners, gestures and messages.
export function createTabStopHost({runtime,...options}) {
  const forwarded={};
  for(const name of ['pointer','leave','key','wheel']) {
    const method=runtime?.[`tab_stop_${name}`];
    if(typeof method!=='function')throw new Error(`Missing tab-stop transport method ${name}`);
    forwarded[`focus_visible_${name}`]=(...args)=>method(...args);
  }
  return createFocusVisibleHost({...options,runtime:forwarded});
}
