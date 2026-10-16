import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {randomUUID} from 'node:crypto';
import {candidateProvenance,assertCandidateRuntime,evidenceFilename} from './uniform-list-pair-evidence.mjs';
import {EMBEDDED_FONTS,sha256,UNIFORM_LIST} from './uniform-list-comparator.mjs';
function provenance(){
  const bytes=readFileSync(new URL('../pairs/uniform_list.json',import.meta.url)),profile=JSON.parse(bytes);
  const files=Object.fromEntries(['moonbit/uniform_list.mjs','moonbit/host.mjs','moonbit/render.mjs','inputs/uniform_list.mbt','inputs/moon.pkg'].map(path=>[path,'a'.repeat(64)]));
  Object.assign(files,{'inputs/uniform_list.rs':UNIFORM_LIST.sourceSha256,'inputs/profile.json':sha256(bytes),
    'moonbit/IBMPlexSans-Regular.ttf':EMBEDDED_FONTS['assets/fonts/ibm-plex-sans/IBMPlexSans-Regular.ttf']});
  return {schema:1,site_kind:'uniform_list_compiled_candidate',qualification:'pinned_clean_source',candidate_tracked_or_untracked_dirty:false,
    lab_tracked_dirty:false,profile,candidate:profile.candidate,implemented:['uniform_list'],files,compiler:'moon synthetic test fixture',
    unit_tests:'passed',completed_at_utc:'2026-10-16T21:40:00Z',comparison:'not_run',conformance:'not_claimed',
    commands:[['moon','test','examples/conformance_uniform_list','--target','js','--deny-warn'],
      ['moon','build','examples/conformance_uniform_list','--target','js','--release','--deny-warn']]};
}
test('synthetic provenance follows exact public profile and rejects override/dirty/source/font/core changes',()=>{
  const build=provenance();candidateProvenance(build);
  for(const mutate of [x=>x.qualification='unqualified_local_override',x=>x.candidate_tracked_or_untracked_dirty=true,
    x=>x.lab_tracked_dirty=true,x=>x.profile.upstream.revision='0'.repeat(40),
    x=>x.candidate={...x.candidate,revision:'0'.repeat(40)},x=>x.files['moonbit/IBMPlexSans-Regular.ttf']='0'.repeat(64),
    x=>x.files['inputs/uniform_list.rs']='0'.repeat(64),x=>x.files['inputs/profile.json']='0'.repeat(64)]) {
    const changed=structuredClone(build);mutate(changed);assert.throws(()=>candidateProvenance(changed));
  }
});
function responses(){
  const session=randomUUID(),report={capture_session:session,build:{files:{}},runtime_responses:[],served_requests:[],requests:[]},assets={},retained={};
  for(const path of ['moonbit/index.html','moonbit/host.mjs','moonbit/uniform_list.mjs','moonbit/render.mjs','moonbit/uniform-list-host.mjs','moonbit/uniform-list-text.mjs','moonbit/IBMPlexSans-Regular.ttf','load-timing.mjs']) {
    const bytes=Buffer.from('synthetic '+path),response_id=report.requests.length+1;
    const url='http://127.0.0.1:12123/gpui-conformance/'+(path==='moonbit/index.html'?'moonbit/?example=uniform_list':path);
    const resource_type=path.endsWith('.html')?'document':path.endsWith('.ttf')?'font':'script';const digest=sha256(bytes);
    report.build.files[path]=digest;assets[path]=bytes;retained[response_id]=bytes;
    report.runtime_responses.push({path,url,response_id,resource_type,status:200,binding:{runtime:'moonbit',session},sha256:digest,bytes:bytes.length,file:evidenceFilename('moonbit','asset',url,response_id)});
    report.requests.push({url,response_id,resource_type,status:200});report.served_requests.push({url:new URL(url).pathname+new URL(url).search,status:200,sha256:digest});
  }
  return {report,assets,retained};
}
test('actual-byte contract rejects omitted, corrupt, cross-session, external and unexpected responses',()=>{
  const f=responses();assertCandidateRuntime(f.report,f.assets,f.retained);
  for(const mutate of [r=>r.runtime_responses.pop(),r=>r.runtime_responses[0].binding.session=randomUUID(),
    r=>r.runtime_responses[1].sha256='0'.repeat(64),r=>r.runtime_responses[1].url='https://evil.invalid/a.mjs',
    r=>r.runtime_responses[1].url='blob:http://127.0.0.1:12123/a',r=>r.served_requests=[],
    r=>r.requests.push({url:'http://127.0.0.1:12123/evil.mjs',response_id:99,status:200,resource_type:'script'})]) {
    const changed=structuredClone(f.report);mutate(changed);assert.throws(()=>assertCandidateRuntime(changed,f.assets,f.retained));
  }
  assert.throws(()=>assertCandidateRuntime(f.report,f.assets,{...f.retained,2:Buffer.from('corrupted actual bytes')}));
});
