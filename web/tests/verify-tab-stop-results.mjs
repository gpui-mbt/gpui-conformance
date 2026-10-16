// Re-read retained bytes; never certify report-provided checks or geometry.
import assert from 'node:assert/strict';
import {readFile,writeFile,realpath,stat} from 'node:fs/promises';
import {resolve,join,sep,basename} from 'node:path';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {TAB_STOP,sha256,assertProvenance,provenanceNegativeControls,decodePng,sourceGeometry,
  validateTraversal,validateClicks,validateOperations,traversalNegativeControls,assertCurrentTabStopBuild} from './tab-stop-comparator.mjs';
const evidence=await realpath(resolve(process.argv[2]||'_build/tab-stop-oracle-evidence'));
const verification={status:'failed',runtime:'rust',candidate:'not_implemented',comparison:'not_run',conformance:'not_claimed'};
async function local(file,max=16*1024*1024) {
  assert.equal(file,basename(file),'Retained evidence must be a direct local filename');
  const path=await realpath(join(evidence,file));assert(path.startsWith(evidence+sep),'Evidence symlinks must remain inside the evidence directory');
  const info=await stat(path);assert(info.isFile()&&info.size>0&&info.size<=max,'Bounded nonempty evidence file');
  return readFile(path);
}
try {
  const reportBytes=await local('tab-stop-rust-result-dpr1.json'),result=JSON.parse(reportBytes);
  verification.discovery_sha256=sha256(reportBytes);
  assert.equal(result.status,'rust_discovery_captured');assert.equal(result.runtime,'rust');assert.equal(result.mode,'discovery');
  assert.equal(result.candidate,'not_implemented');assert.equal(result.comparison,'not_run');assert.equal(result.conformance,'not_claimed');
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
  verification.current_checkout=assertCurrentTabStopBuild(result,{
    revision:git(['rev-parse','HEAD']),
    trackedDirty:git(['status','--porcelain','--untracked-files=no'])!=='',
    catalogBytes:await readFile(resolve('web/examples.json')),
  });
  const decoder=await local('tab-stop-png-decoder.py');assert.equal(sha256(decoder),result.decoder.sha256);
  assert.equal(sha256(decoder),sha256(await readFile(new URL('../scripts/decode_oracle_png.py',import.meta.url))),'Decoder source must match this lab checkout');
  const expectedRuntime=['load-timing.mjs','rust/host.mjs','rust/tab_stop.js','rust/tab_stop_bg.wasm'];
  assert.deepEqual([...new Set(result.runtime_responses.map(entry=>entry.path))].sort(),expectedRuntime);
  let wasm;
  for(const response of result.runtime_responses) {
    assert.equal(response.status,200);assert.equal(new URL(response.url).pathname,'/gpui-conformance/'+response.path);
    const bytes=await local(response.file,64*1024*1024);assert.equal(sha256(bytes),response.sha256);
    const expected=response.path==='load-timing.mjs'?build.moonbit_host_files_sha256[response.path]:build.rust.files[response.path.slice(5)];
    assert.equal(response.sha256,expected,'Actually served executable bytes must match the build manifest');
    assert(result.served_requests.some(entry=>entry.status===200&&entry.url==='/gpui-conformance/'+response.path&&entry.sha256===expected),'Server must independently record the same served bytes');
    if(response.path==='rust/tab_stop_bg.wasm')wasm=bytes;
  }
  assert.deepEqual(result.support_files.map(entry=>entry.path).sort(),[
    'rust/unchanged-source/tab_stop.rs','rust/packaging-Cargo.toml',...Object.values(build.rust.embedded_fonts).map(font=>'rust/'+font.file)].sort());
  for(const entry of result.support_files) {
    const bytes=await local(entry.file);assert.equal(sha256(bytes),entry.sha256);assert.equal(entry.sha256,build.rust.files[entry.path.slice(5)]);
    if(entry.path.endsWith('.rs')) {
      assert.equal(entry.sha256,TAB_STOP.sourceSha256);
      assert.equal(createHash('sha1').update(Buffer.from(`blob ${bytes.length}\0`)).update(bytes).digest('hex'),TAB_STOP.sourceBlob);
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
  const geometry=sourceGeometry(images);verification.traversal=validateTraversal(images,geometry);
  verification.clicks=validateClicks(images,geometry);verification.delivery=validateOperations(result,geometry);
  verification.negative_controls=traversalNegativeControls(images,geometry);
  verification.capture_integrity=captureIntegrity;verification.geometry=geometry;
  verification.status='rust_source_profile_verified';
  verification.unverified=['MoonBit counterpart/comparison','native parity','exact message OCR/text/full-image parity',
    'other browsers/GPUs/viewports/DPRs','touch/IME','group-container direct focus anchors'];
  console.log('VERIFIED: actual unchanged Rust source-profile ordering, non-stops, click listeners, trusted delivery and independently decoded stable PNGs. No MoonBit/native conformance claim.');
}catch(error){verification.failure=error.stack;throw error;}
finally {await writeFile(join(evidence,'tab-stop-rust-verification-dpr1.json'),JSON.stringify(verification,null,2)+'\n');}
