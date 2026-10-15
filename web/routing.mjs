export function selectExample(catalog, id) {
  const example = catalog.examples.find(entry => entry.id === id);
  if (!example) throw new Error(`Unknown upstream example: ${id}`);
  return example;
}

export function rustExampleUrl(base, example) {
  if (!base.trim()) return null;
  const url = new URL(base);
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) throw new Error('Rust gallery URL must be HTTP(S) without credentials');
  if (url.search || url.hash) throw new Error('Supply the gallery base URL, not an example URL or query');
  if (!url.pathname.endsWith('/')) url.pathname += '/';
  return new URL(example.rust_route, url).href;
}

export function moonbitExampleUrl(base, example) {
  if (example.moonbit !== 'implemented') return null;
  const url = new URL('./moonbit/', base);
  url.searchParams.set('example', example.id);
  return url.href;
}
