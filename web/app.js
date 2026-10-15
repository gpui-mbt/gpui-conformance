import { selectExample, rustExampleUrl, moonbitExampleUrl } from './routing.mjs';
const $ = id => document.getElementById(id);
const query = new URL(location.href).searchParams;
try {
  const response = await fetch('./examples.json');
  if (!response.ok) throw new Error(`Catalog HTTP ${response.status}`);
  const catalog = await response.json();
  for (const example of catalog.examples) {
    const option = document.createElement('option'); option.value = example.id;
    option.textContent = `${example.title}${example.moonbit === 'implemented' ? '' : ' — MoonBit not implemented'}`;
    $('fixture').append(option);
  }
  const requested = query.get('example') || 'hello_world';
  $('fixture').value = selectExample(catalog, requested).id;
  $('rust-url').value = query.get('rust') || '';
  $('pins').textContent = `Upstream ${catalog.upstream.revision} · Candidate ${catalog.moonbit.revision}`;
  function clearFrames() {
    for (const side of ['rust', 'moon']) { $(side + '-frame').removeAttribute('src'); $(side + '-frame').hidden = true; $(side + '-empty').hidden = false; }
  }
  function load() {
    // Clear the old pair first; a missing port must never leave a stale, mismatched application visible.
    clearFrames();
    try {
      const example = selectExample(catalog, $('fixture').value);
      $('rust-source').href = `https://github.com/${catalog.upstream.repository}/blob/${catalog.upstream.revision}/${example.source}`;
      $('moon-source').hidden = example.moonbit !== 'implemented';
      $('moon-source').href = 'https://github.com/gpui-mbt/gpui-conformance/blob/feat/browser-side-by-side-lab/web/moonbit/hello_world/hello_world.mbt';
      const moon = moonbitExampleUrl(location.href, example);
      if (!moon) {
        $('notice').textContent = `${example.title}: MoonBit port not implemented. Neither runtime is substituted.`;
        $('rust-empty').textContent = 'Select an implemented pair to compare.';
        return;
      }
      const rust = rustExampleUrl($('rust-url').value, example);
      $('moon-frame').src = moon; $('moon-frame').hidden = false; $('moon-empty').hidden = true;
      if (rust) { $('rust-frame').src = rust; $('rust-frame').hidden = false; $('rust-empty').hidden = true; }
      else $('rust-empty').textContent = 'Rust WASM is not bundled. Enter the base URL of the upstream gallery; the matching route is selected automatically.';
      const next = new URL(location.href); next.search = '';
      next.searchParams.set('example', example.id);
      if ($('rust-url').value.trim()) next.searchParams.set('rust', $('rust-url').value.trim());
      history.replaceState(null, '', next);
      $('notice').textContent = `${example.title} · fixed ${example.width} × ${example.height} logical pixels · ${rust ? 'Both URLs requested; Rust rendering not verified.' : 'MoonBit port requested; Rust URL not configured.'} The upstream example has no interactive controls.`;
    } catch (error) { $('notice').textContent = error.message; }
  }
  $('settings').addEventListener('submit', event => { event.preventDefault(); load(); });
  $('fixture').addEventListener('change', load);
  load();
} catch (error) { $('notice').textContent = `Unable to load examples: ${error.message}`; }
