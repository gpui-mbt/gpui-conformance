import { selectExample, rustExampleUrl, moonbitExampleUrl } from './routing.mjs';
const $ = id => document.getElementById(id);
import { createLoadComparison } from './load-comparison.mjs';
const loadComparison = createLoadComparison({ frames: { rust: $('rust-frame'), moon: $('moon-frame') }, output: $('load-results') });
const query = new URL(location.href).searchParams;
try {
  const response = await fetch('./examples.json');
  if (!response.ok) throw new Error(`Catalog HTTP ${response.status}`);
  const catalog = await response.json();
  const buildResponse = await fetch('./build-manifest.json');
  if (!buildResponse.ok) throw new Error(`Build manifest HTTP ${buildResponse.status}`);
  const build = await buildResponse.json();
  for (const example of catalog.examples) {
    const option = document.createElement('option'); option.value = example.id;
    option.textContent = `${example.title}${example.moonbit === 'implemented' ? '' : ' — gpui.mbt not implemented'}`;
    $('fixture').append(option);
  }
  const requested = query.get('example') || 'hello_world';
  $('fixture').value = selectExample(catalog, requested).id;
  $('pins').textContent = `Upstream ${catalog.upstream.revision} · Candidate ${catalog.moonbit.revision}`;
  function clearFrames() {
    for (const side of ['rust', 'moon']) { $(side + '-frame').removeAttribute('src'); $(side + '-frame').hidden = true; $(side + '-empty').hidden = false; }
  }
  function load() {
    // Clear the old pair first; a missing port must never leave a stale, mismatched application visible.
    loadComparison.cancel();
    clearFrames();
    try {
      const example = selectExample(catalog, $('fixture').value);
      $('rust-source').href = `https://github.com/${catalog.upstream.repository}/blob/${catalog.upstream.revision}/${example.source}`;
      $('moon-source').hidden = example.moonbit !== 'implemented';
      $('moon-source').href = `https://github.com/gpui-mbt/gpui-conformance/blob/${build.lab_revision}/${example.candidate_source}`;
      for (const side of ['moon', 'rust']) {
        $(side + '-frame').style.width = `${example.width || 500}px`;
        $(side + '-frame').style.height = `${example.height || 500}px`;
        $(side + '-frame').parentElement.style.height = `${(example.height || 500) + 20}px`;
      }
      const moon = moonbitExampleUrl(location.href, example);
      if (!moon) {
        $('notice').textContent = `${example.title}: gpui.mbt not implemented. Neither runtime is substituted.`;
        $('rust-empty').textContent = 'Select an implemented pair to compare.';
        return;
      }
      const rust = build.rust_bundled ? rustExampleUrl(location.href, example) : null;
      loadComparison.start({ example: example.id, urls: { moon, rust } });
      $('moon-empty').hidden = true;
      if (rust) $('rust-empty').hidden = true;
      else $('rust-empty').textContent = 'Rust WASM has not been built in this artifact. Comparison is unavailable.';
      const next = new URL(location.href); next.search = '';
      next.searchParams.set('example', example.id);
      history.replaceState(null, '', next);
      $('notice').textContent = `${example.title} · fixed ${example.width} × ${example.height} logical pixels · ${rust ? 'Both compiled runtimes requested from this origin; rendering results are recorded by browser E2E.' : 'MoonBit port requested; Rust artifact missing.'} ${example.id === 'anchor' ? 'Hover the eight buttons independently in each pane. Supported viewport profile: 750 or 480 × 600 at DPR 1; paired conformance remains unverified.' : example.interactive ? 'Use the preset and Count Primes controls independently in each pane. CPU work timings are not render-startup benchmarks.' : 'The upstream example has no interactive controls.'}${rust && !crossOriginIsolated ? ' This host lacks the COOP/COEP headers required by Rust WASM.' : ''}`;
    } catch (error) { $('notice').textContent = error.message; }
  }
  $('settings').addEventListener('submit', event => { event.preventDefault(); load(); });
  $('fixture').addEventListener('change', load);
  load();
} catch (error) { $('notice').textContent = `Unable to load examples: ${error.message}`; }
