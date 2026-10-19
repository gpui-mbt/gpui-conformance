// The paired lab already shows this warning above both runtimes. Only that
// verified, visible warning can replace the child's canvas-covering duplicate.
export function hasVisibleParentGridQualification(w) {
  try {
    const p = w.parent;
    if (p === w || p.location.origin !== w.location.origin) return false;
    const d = p.document, moon = d.getElementById('moon-frame'), rust = d.getElementById('rust-frame');
    if (moon !== w.frameElement || !rust || !d.body.classList.contains('live-grid')) return false;
    for (const frame of [moon, rust]) {
      const url = new URL(frame.src, p.location.href);
      if (url.origin !== w.location.origin || url.searchParams.get('example') !== 'grid_layout') return false;
    }
    const notice = d.getElementById('notice');
    if (!notice || !notice.isConnected || !notice.textContent.includes('Strict comparison remains limited to 399/400/401/500 × 500 at DPR1; other sizes are unverified.')) return false;
    if (![...notice.getClientRects()].some(rect => rect.width > 0 && rect.height > 0)) return false;
    for (let node = notice; node; node = node.parentElement) {
      const style = p.getComputedStyle(node);
      if (node.hidden || node.getAttribute('aria-hidden') === 'true' || style.display === 'none' || style.visibility !== 'visible' || Number(style.opacity) === 0) return false;
    }
    return true;
  } catch { return false; } // Cross-origin and unrelated embeds keep their warning.
}

export function watchGridQualificationNotice(w, notice) {
  let required = false, stopped = false;
  const refresh = () => { if (stopped) return; notice.hidden = !required || hasVisibleParentGridQualification(w); };
  let observer;
  try {
    if (w.parent !== w && w.parent.location.origin === w.location.origin) {
      observer = new w.MutationObserver(refresh);
      observer.observe(w.parent.document.documentElement, {subtree:true, childList:true, characterData:true, attributes:true, attributeFilter:['hidden','style','class','aria-hidden','src']});
      w.parent.addEventListener('resize', refresh);
    }
  } catch { /* Standalone fallback remains visible when required. */ }
  return {
    setRequired(value) { required = value; refresh(); },
    stop() { stopped = true; observer?.disconnect(); try { w.parent.removeEventListener('resize', refresh); } catch {} },
  };
}
