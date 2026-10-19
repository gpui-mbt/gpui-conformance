// Prepared content is private and immutable: callers receive only an opaque token.
// Decode before drawFrame, never fetch/derive ancestry/fit images during painting.
const prepared = new WeakMap();
const digestPattern = /^[0-9a-f]{64}$/;
const exact = (value, keys) => value && Object.keys(value).sort().join(',') === keys.sort().join(',');
const rect = b => b && [b.x,b.y,b.width,b.height].every(Number.isFinite) && b.width >= 0 && b.height >= 0;
const maxPixels = 4194304, maxBytes = 16777216;

export function validateImageResources(snapshot) {
  const resources = snapshot.resources ?? [];
  if (!Array.isArray(resources) || resources.length > 32) throw new Error('Invalid image resource table');
  const byId = new Map(); let pixels = 0;
  for (const r of resources) {
    if (!exact(r,['id','kind','content_identity','pixel_width','pixel_height','frame_count']) ||
        r.kind !== 'image' || !Number.isSafeInteger(r.id) || r.id < 0 || byId.has(r.id) ||
        !digestPattern.test(r.content_identity) || ![r.pixel_width,r.pixel_height,r.frame_count].every(n=>Number.isSafeInteger(n)&&n>0) ||
        r.pixel_width > 4096 || r.pixel_height > 4096 || r.frame_count !== 1 ||
        (pixels += r.pixel_width*r.pixel_height*r.frame_count) > maxPixels) throw new Error('Invalid image resource descriptor');
    byId.set(r.id,r);
  }
  for (const item of snapshot.items) if (item.kind === 'image') {
    const r = byId.get(item.resource_id), t = item.transform;
    if (!r || item.frame_index !== 0 || !rect(item.image_bounds) || !t ||
        !['a','b','c','d','tx','ty'].every((k,i)=>t[k] === [1,0,0,1,0,0][i]))
      throw new Error('Missing image resource or unsupported image geometry');
  }
  return byId;
}

export async function prepareImageResources(descriptors, encodedById) {
  const byId = new Map([...validateImageResources({resources:descriptors,items:[]})].map(([id,r])=>[id,Object.freeze({...r})]));
  if (!(encodedById instanceof Map) || encodedById.size !== byId.size) throw new Error('Image bytes/table mismatch');
  const ready = new Map(); let total = 0;
  try {
    for (const [id,r] of byId) {
      const input = encodedById.get(id);
      if (!(input instanceof Uint8Array) || input.byteLength < 8 || (total += input.byteLength) > maxBytes)
        throw new Error('Missing or oversized image bytes');
      const bytes = input.slice();
      // This first bounded path admits only static PNG. No implicit GIF frame zero.
      if (![137,80,78,71,13,10,26,10].every((v,i)=>bytes[i]===v)) throw new Error('Expected static PNG bytes');
      validateStaticPng(bytes,r);
      const hash = [...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(v=>v.toString(16).padStart(2,'0')).join('');
      if (hash !== r.content_identity) throw new Error('Image content identity mismatch');
      const bitmap = await createImageBitmap(new Blob([bytes],{type:'image/png'}), {premultiplyAlpha:'default',colorSpaceConversion:'default'});
      if (bitmap.width !== r.pixel_width || bitmap.height !== r.pixel_height) {bitmap.close();throw new Error('Decoded image dimensions mismatch');}
      ready.set(id,{descriptor:Object.freeze({...r}),frames:Object.freeze([bitmap])});
    }
  } catch (error) {for (const value of ready.values()) for (const bitmap of value.frames) bitmap.close();throw error;}
  const token = Object.freeze({}); prepared.set(token,ready); return token;
}

export function resolveImageResources(snapshot, token) {
  const byId = validateImageResources(snapshot), ready = prepared.get(token), result = new Map();
  for (const [id,r] of byId) {
    const value = ready?.get(id);
    if (!value || Object.keys(r).some(k=>r[k]!==value.descriptor[k])) throw new Error('Image resource was not prepared or changed');
    if (value.frames.some(bitmap=>bitmap.width!==r.pixel_width || bitmap.height!==r.pixel_height)) throw new Error('Prepared image is closed or invalid');
    result.set(id,value.frames);
  }
  return (context,item) => {
    const bitmap=result.get(item.resource_id)?.[item.frame_index];
    if(!bitmap)throw new Error('Unresolved image item');
    const b=item.bounds;context.drawImage(bitmap,b.x,b.y,b.width,b.height);
  };
}

// Validate chunk boundaries and dimensions before the decoder allocates pixels.
function validateStaticPng(bytes,r) {
  const view=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);
  let offset=8, first=true, ended=false;
  while(offset+12<=bytes.length) {
    const length=view.getUint32(offset), type=String.fromCharCode(...bytes.subarray(offset+4,offset+8));
    if(length>bytes.length-offset-12) throw new Error('Truncated PNG chunk');
    if(first && (type!=='IHDR'||length!==13||view.getUint32(offset+8)!==r.pixel_width||view.getUint32(offset+12)!==r.pixel_height)) throw new Error('PNG header dimensions mismatch');
    if(type==='acTL'||type==='fcTL'||type==='fdAT') throw new Error('Animated PNG unsupported');
    first=false; offset+=length+12;
    if(type==='IEND') {if(length!==0||offset!==bytes.length)throw new Error('Invalid PNG end');ended=true;break;}
  }
  if(!ended)throw new Error('Incomplete PNG');
}
