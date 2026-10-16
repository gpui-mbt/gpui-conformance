// Compare two independently executed profiles only after verifying their
// retained complete screenshots. This is behavior evidence, not pixel parity.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFile,writeFile} from 'node:fs/promises';
import {resolve,join,basename} from 'node:path';
import {spawnSync} from 'node:child_process';
import {compareScrollableBehavior,validateScrollablePixels} from './scrollable-pair-comparator.mjs';

const directory=resolve(process.argv[2]||'_build/browser-example-evidence');
const dpr=Number(process.argv.find(arg=>arg.startsWith('--dpr='))?.slice(6)||1);
const report={status:'failed',scope:'actual independent Rust/MoonBit screenshot-derived scroll behavior'};
try {
  const decoderVersion=spawnSync('python3',['-c','import PIL; print(PIL.__version__)'],{encoding:'utf8'});
  if(decoderVersion.error)throw decoderVersion.error;
  assert.equal(decoderVersion.status,0,`Pillow is required: ${decoderVersion.stderr}`);
  report.png_decoder={implementation:'Pillow',version:decoderVersion.stdout.trim()};
  report.decoded_pixel_validation={};
  const sides=[];
  for(const runtime of ['rust','moonbit']) {
    const bytes=await readFile(join(directory,`scrollable-${runtime}-result-dpr${dpr}.json`));
    const result=JSON.parse(bytes);
    const images={};
    for(const [name,capture] of Object.entries(result.captures)) {
      assert.equal(basename(capture.file),capture.file,'Capture must be a local retained file');
      const png=await readFile(join(directory,capture.file));
      assert.equal(createHash('sha256').update(png).digest('hex'),capture.png_sha256,'Retained screenshot hash');
      assert.equal(png.subarray(0,8).toString('hex'),'89504e470d0a1a0a','PNG signature');
      assert.equal(png.subarray(12,16).toString('ascii'),'IHDR','PNG dimensions header');
      assert.deepEqual([png.readUInt32BE(16),png.readUInt32BE(20)],[500*dpr,500*dpr],'Full unscaled capture dimensions');
      // Decode the retained PNG, not the report's claimed pixel hash. Pillow
      // is pinned by CI and also used by the existing screenshot comparators.
      const decoded=spawnSync('python3',['-c',
        'from PIL import Image; import sys; im=Image.open(sys.argv[1]); im.load(); sys.stdout.buffer.write(im.convert("RGBA").tobytes())',
        join(directory,capture.file)],{maxBuffer:500*500*dpr*dpr*4+4096});
      if(decoded.error)throw decoded.error;
      assert.equal(decoded.status,0,`Decode retained PNG: ${decoded.stderr?.toString()}`);
      assert.equal(decoded.stdout.length,500*500*dpr*dpr*4,'Complete decoded RGBA required');
      images[name]={width:500*dpr,height:500*dpr,data:new Uint8Array(decoded.stdout)};
    }
    report.decoded_pixel_validation[runtime]=validateScrollablePixels(result,images);
    sides.push(result);
    report[`${runtime}_result_sha256`]=createHash('sha256').update(bytes).digest('hex');
  }
  Object.assign(report,compareScrollableBehavior(...sides));
  report.retained_screenshots='all PNG bytes, decoded RGBA and pixel predicates verified; no cropping, replacement or resampling';
  console.log('PASS: actual Rust/MoonBit nested-scroll behavior agrees within the recorded browser profile. Full-pixel and native parity remain UNVERIFIED.');
} catch(error) {report.failure=error.stack;throw error;}
finally {
  await writeFile(join(directory,`scrollable-pair-result-dpr${dpr}.json`),JSON.stringify(report,null,2)+'\n');
}
