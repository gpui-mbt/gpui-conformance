// Filesystem corruption controls only, never runtime capture evidence.
import assert from 'node:assert/strict';
import test from 'node:test';
import {mkdtemp,writeFile,symlink,link,mkdir,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {strictLocalReader} from './anchor-runtime-evidence.mjs';
import {sha256} from './anchor-comparator.mjs';
test('strict retained reader rejects path traversal, symlink/hardlink aliases, wrong digest, empty/oversized/non-file records',async()=>{
  const root=await mkdtemp(join(tmpdir(),'anchor-reader-'));try {
    const bytes=Buffer.from('synthetic retained-file check'),digest=sha256(bytes),read=await strictLocalReader(root);
    await writeFile(join(root,'valid.bin'),bytes);assert.deepEqual(await read('valid.bin',digest),bytes);
    for(const filename of ['../valid.bin','a/b.bin','a\\b.bin','.','..','CON.bin','space name.bin'])await assert.rejects(()=>read(filename,digest));
    await assert.rejects(()=>read('valid.bin','0'.repeat(64)));await assert.rejects(()=>read('valid.bin',digest,1));
    await symlink('valid.bin',join(root,'alias.bin'));await assert.rejects(()=>read('alias.bin',digest));
    await writeFile(join(root,'hard-source.bin'),bytes);await link(join(root,'hard-source.bin'),join(root,'hard-alias.bin'));
    await assert.rejects(()=>read('hard-source.bin',digest));await assert.rejects(()=>read('hard-alias.bin',digest));
    await writeFile(join(root,'empty.bin'),'');await assert.rejects(()=>read('empty.bin',sha256(Buffer.alloc(0))));
    await mkdir(join(root,'directory'));await assert.rejects(()=>read('directory',digest));
    await assert.rejects(()=>read('missing.bin',digest));
  } finally {await rm(root,{recursive:true,force:true});}
});
