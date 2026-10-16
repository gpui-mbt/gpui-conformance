// Re-read retained bytes; never certify report-provided checks or geometry.
import assert from 'node:assert/strict';
import {readFile,writeFile,realpath,stat} from 'node:fs/promises';
import {resolve,join,sep,basename} from 'node:path';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {DRAG_DROP,sha256,assertProvenance,provenanceNegativeControls,decodePng,discoverGeometry,
  validateProfile,validateOperations,profileNegativeControls,assertCurrentBuild,PROFILE_REVISION,SOURCE_CONSTRAINTS} from './drag-drop-comparator.mjs';
const evidence=await realpath(resolve(process.argv[2]||'_build/drag-drop-oracle-evidence'));
const verification={status:'failed',runtime:'rust',candidate:'not_implemented',comparison:'not_run',conformance:'not_claimed'};
async function local(file,max=16*1024*1024) {
  assert.equal(file,basename(file),'Retained evidence must be a direct local filename');
  const path=await realpath(join(evidence,file));assert(path.startsWith(evidence+sep),'Evidence symlinks must remain inside the evidence directory');
  const info=await stat(path);assert(info.isFile()&&info.size>0&&info.size<=max,'Bounded nonempty evidence file');
  return readFile(path);
}
try {
  const reportBytes=await local('drag-drop-rust-result-dpr1.json'),result=JSON.parse(reportBytes);
  verification.discovery_sha256=sha256(reportBytes);
  assert.equal(result.status,'rust_discovery_captured');assert.equal(result.runtime,'rust');assert.equal(result.mode,'discovery');
  assert.equal(result.profile_revision,PROFILE_REVISION,'Historical failed profiles retain their original labels');
  assert.equal(result.candidate,'not_implemented');assert.equal(result.comparison,'not_run');assert.equal(result.conformance,'not_claimed');
  assert.deepEqual(result.source_constraints,SOURCE_CONSTRAINTS);
  assert.deepEqual(result.profile,{width:800,height:600,dpr:1});assert.deepEqual(result.errors,[]);
  const buildBytes=await local(result.build_evidence.file),catalogBytes=await local(result.catalog_evidence.file);
  assert.equal(sha256(buildBytes),result.build_evidence.sha256);assert.equal(sha256(catalogBytes),result.catalog_evidence.sha256);
  const build=JSON.parse(buildBytes),catalog=JSON.parse(catalogBytes);assert.deepEqual(result.build,build);assert.deepEqual(result.catalog,catalog);
  verification.source=assertProvenance(build,catalog);verification.provenance_negative_controls=provenanceNegativeControls(build,catalog);
  assert.deepEqual(result.source,verification.source);
  const git=args=>{
    const value=spawnSync('git',args,{encoding:'utf8',timeout:10000,maxBuffer:1024*1024});
    if(value.error)throw value.error;
    assert.equal(value.status,0,`Current checkout provenance: ${value.stderr?.slice(0,2048)}`);
    return value.stdout.trim();
  };
  verification.current_checkout=assertCurrentBuild(result,{
    revision:git(['rev-parse','HEAD']),tree:git(['rev-parse','HEAD^{tree}']),
    trackedDirty:git(['status','--porcelain','--untracked-files=no'])!=='',
    catalogBytes:await readFile(resolve('web/examples.json')),
  });
  const decoder=await local('drag-drop-png-decoder.py');assert.equal(sha256(decoder),result.decoder.sha256);
  assert.equal(sha256(decoder),sha256(await readFile(new URL('../scripts/decode_drag_drop_png.py',import.meta.url))),'Decoder source must match this lab checkout');
  assert.deepEqual(result.canvas,{bounds:{x:0,y:0,width:800,height:600},backing:{width:800,height:600}});
  assert.equal(result.environment?.playwright,'1.56.1');assert.equal(result.environment?.platform,'linux');
  assert.match(result.environment?.browser||'',/^\d+\.\d+\.\d+\.\d+$/);
  assert.equal(result.decoder.name,'Pillow');assert.equal(result.decoder.version,'12.0.0');
  assert.equal(build.rust.files['host.mjs'],sha256(await readFile(new URL('../rust/host.mjs',import.meta.url))),'Served source-only host matches actual checkout');
  const expectedRuntime=['load-timing.mjs','rust/host.mjs','rust/drag_drop.js','rust/drag_drop_bg.wasm'].sort();
  assert.deepEqual([...new Set(result.runtime_responses.map(entry=>entry.path))].sort(),expectedRuntime);
  let wasm;
  for(const response of result.runtime_responses) {
    assert.equal(response.status,200);assert.equal(new URL(response.url).pathname,'/gpui-conformance/'+response.path);
    const bytes=await local(response.file,64*1024*1024);assert.equal(sha256(bytes),response.sha256);
    const expected=response.path==='load-timing.mjs'?build.moonbit_host_files_sha256[response.path]:build.rust.files[response.path.slice(5)];
    assert.equal(response.sha256,expected,'Actually served executable bytes must match the build manifest');
    assert(result.served_requests.some(entry=>entry.status===200&&entry.url==='/gpui-conformance/'+response.path&&entry.sha256===expected),'Server must independently record the same served bytes');
    if(response.path==='rust/drag_drop_bg.wasm')wasm=bytes;
  }
  assert.deepEqual(result.support_files.map(entry=>entry.path).sort(),[
    'rust/unchanged-source/drag_drop.rs','rust/packaging-Cargo.toml',...Object.values(build.rust.embedded_fonts).map(font=>'rust/'+font.file)].sort());
  for(const entry of result.support_files) {
    const bytes=await local(entry.file);assert.equal(sha256(bytes),entry.sha256);assert.equal(entry.sha256,build.rust.files[entry.path.slice(5)]);
    if(entry.path.endsWith('.rs')) {
      assert.equal(entry.sha256,DRAG_DROP.sourceSha256);
      assert.equal(createHash('sha1').update(Buffer.from(`blob ${bytes.length}\0`)).update(bytes).digest('hex'),DRAG_DROP.sourceBlob);
    }else if(entry.path.endsWith('.ttf'))assert(wasm.includes(bytes),'Actual served WASM must contain each complete pinned embedded font input');
  }
  const images={},captureIntegrity={},used=new Set();
  for(const [name,capture] of Object.entries(result.captures)) {
    assert(capture.stable&&capture.file!==capture.stability_file,'Two distinct screenshot sample files required');
    assert(capture.attempts.length>=2);assert.equal(capture.attempts.at(-1).file,capture.file);assert.equal(capture.attempts.at(-2).file,capture.stability_file);
    for(const attempt of capture.attempts) {
      assert(!used.has(attempt.file),'Original attempt files must not be reused across captures');used.add(attempt.file);
      const bytes=await local(attempt.file,8*1024*1024);assert.equal(sha256(bytes),attempt.png_sha256);
      const image=decodePng(bytes);assert.equal(sha256(image.data),attempt.rgba_sha256);assert.equal(image.width,attempt.width);assert.equal(image.height,attempt.height);
      if(attempt.file===capture.file)images[name]=image;
    }
    const a=decodePng(await local(capture.file)),b=decodePng(await local(capture.stability_file));
    assert.equal(sha256(a.data),sha256(b.data),'Two independent original PNGs must decode to identical complete RGBA');
    assert.equal(capture.rgba_sha256,sha256(a.data));assert.equal(capture.stability_rgba_sha256,sha256(b.data));
    assert.equal(capture.png_sha256,sha256(await local(capture.file)));assert.equal(capture.stability_png_sha256,sha256(await local(capture.stability_file)));
    captureIntegrity[name]={rgba_sha256:sha256(a.data),samples:2,width:a.width,height:a.height};
  }
  // Recompute, rather than import, all observed geometry from actual PNGs.
  const geometry=discoverGeometry(images.initial);verification.profile=validateProfile(images,geometry);
  verification.delivery=validateOperations(result,geometry);verification.negative_controls=profileNegativeControls(images,geometry,result);
  verification.capture_integrity=captureIntegrity;verification.geometry=geometry;
  verification.status='rust_source_profile_verified';
  verification.unverified=['MoonBit counterpart/comparison','native parity','exact message OCR/text/full-image parity',
    'other browsers/GPUs/viewports/DPRs','native/global capture, touch and OS drag','foreign payloads, rejecting predicates and nested/overlapping targets','actual internal activation grip (visible offsets cancel)'];
  console.log('VERIFIED: actual unchanged Rust drag activation, typed drop, hover/preview/cleanup paint, trusted independent delivery and independently decoded stable PNGs. No MoonBit/native conformance claim.');
}catch(error){verification.failure=error.stack;throw error;}
finally {
  const bytes=JSON.stringify(verification,null,2)+'\n';
  try{await writeFile(join(evidence,'drag-drop-rust-verification-dpr1.json'),bytes,{flag:'wx'});}
  catch(error){if(error.code!=='EEXIST')throw error;await writeFile(join(evidence,`drag-drop-rust-verification-recheck-${Date.now()}.json`),bytes,{flag:'wx'});}
}
