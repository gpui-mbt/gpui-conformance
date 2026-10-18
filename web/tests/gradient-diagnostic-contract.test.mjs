import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateProfile,samples,sha256,validatePinnedSources,SOURCE_REGISTRY_SHA256} from './gradient-diagnostic-contract.mjs';
const profile=JSON.parse(readFileSync(new URL('../gradient-diagnostic/profile.json',import.meta.url)));
test('bounded exact synthetic profile with boundary and explicit polygon probes',()=>{
 validateProfile(profile);assert.equal(profile.cases.filter(c=>c.kind==='unequal').length,2);assert.equal(profile.cases.filter(c=>c.kind==='transparent').length,2);
 assert.deepEqual(profile.polygon.vertices_relative,[[0,80],[80,30],[81,30],[161,80]]);assert.deepEqual(profile.polygon.clip_relative,[0,45,161,35]);
 for(const space of ['Srgb','Oklab']){const cases=profile.cases.filter(c=>c.color_space===space);assert(cases.some(c=>c.stops[0]<0&&c.stops[1]>1));assert(cases.some(c=>c.stops[0]>c.stops[1]));}
});
test('samples preserve exact boundary pixel centers without expected color branch',()=>{
 const rgba=Buffer.alloc(1000*900*4);const data=samples(rgba,profile);
 for(const c of data.filter(c=>c.id.endsWith('equal-stops'))){assert.deepEqual(c.points.map(p=>p.x),[c.bounds[0]+79,c.bounds[0]+80,c.bounds[0]+81]);assert.equal(c.points[1].fragment_center[0],c.bounds[0]+80.5);}
 assert.equal(data.length,36);const changed=Buffer.from(rgba);changed[0]=1;assert.notEqual(sha256(changed),sha256(rgba));
});
test('mutated profile identity, dimensions and center construction fail closed',()=>{
 for(const mutate of [p=>p.original_example=true,p=>p.viewport.dpr=2,p=>p.cases.pop(),p=>p.cases.find(c=>c.id.endsWith('equal-stops')).bounds[2]=160]){const p=structuredClone(profile);mutate(p);assert.throws(()=>validateProfile(p));}
});

test('frozen source registry rejects changed source facts even with updated local hashes',()=>{
 const bytes=readFileSync(new URL('../gradient-diagnostic/upstream-sources.json',import.meta.url));assert.equal(sha256(bytes),SOURCE_REGISTRY_SHA256);
 const registry=JSON.parse(bytes);registry.sources[0].sha256='0'.repeat(64);
 assert.throws(()=>validatePinnedSources(new Map([['upstream-sources.json',Buffer.from(JSON.stringify(registry))]])));
 assert.throws(()=>validatePinnedSources(new Map([['upstream-sources.json',bytes],['upstream-source/'+JSON.parse(bytes).sources[0].path,Buffer.from('altered shader source')]])));
});
