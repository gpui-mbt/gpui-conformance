export function selectExample(catalog, id) {
  const example = catalog.examples.find(entry => entry.id === id);
  if (!example) throw new Error(`Unknown upstream example: ${id}`);
  return example;
}

export function rustExampleUrl(base, example) {
  if (example.moonbit !== 'implemented') return null;
  const url = new URL('./rust/', base);
  url.searchParams.set('example', example.id);
  return url.href;
}

export function moonbitExampleUrl(base, example) {
  if (example.moonbit !== 'implemented') return null;
  const url = new URL('./moonbit/', base);
  url.searchParams.set('example', example.id);
  return url.href;
}
