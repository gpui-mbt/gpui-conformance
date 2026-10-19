"""Run only after exact source review and binding to a published core commit."""
import argparse
import json
import shutil
import os
from pathlib import Path
import re
import uuid
from candidate import compile_candidate
from prepare_rust import prepare
from compare import compare
from support import execute, require, load, save, digest, inventory, git

ROOT=Path(__file__).resolve().parents[2]
def successful(record):
    require(record['returncode']==0 and not record['timed_out'] and not record['resource_floor_breached'],'actual process failed')
def run(core,upstream,out):
    core=core.resolve();upstream=upstream.resolve();out=out.resolve()
    p=load(Path(__file__).with_name('profile.json'))
    require(p['status']=='bound','source review and exact core pin required')
    require(all(re.fullmatch('[0-9a-f]{40}',p[k] or '') for k in ['core_commit','core_tree']),'exact core pin required')
    require(git(core,'rev-parse','HEAD').decode().strip()==p['core_commit'],'core commit')
    require(git(core,'rev-parse','HEAD^{tree}').decode().strip()==p['core_tree'],'core tree')
    require(not git(core,'status','--porcelain','--untracked-files=all').strip(),'pristine core')
    out.mkdir(parents=True,exist_ok=False);token=str(uuid.uuid4())
    result={'status':'running','run_token':token,'profile':p,'suite_commit':git(ROOT,'rev-parse','HEAD').decode().strip()}
    require(not git(ROOT,'status','--porcelain','--untracked-files=all').strip(),'pristine suite before output')
    try:
        compile_candidate(ROOT,core,out/'candidate',{},token)
        core_output=load(out/'candidate/raw.stdout')
        save(out/'core.json',core_output)
        prepare(upstream,ROOT/'adapters/image_resource_rust/observer.rs',out/'rust-source.json')
        env=os.environ.copy()
        for key in ['DISPLAY','WAYLAND_DISPLAY','RUSTFLAGS','CARGO_ENCODED_RUSTFLAGS','RUSTC_WRAPPER','RUSTC_WORKSPACE_WRAPPER','CARGO_BUILD_TARGET','RUSTC','RUSTDOC']:
            env.pop(key,None)
        require(digest(ROOT/'assets/portrait.png')=='5ee1c4f5612fcc49c0bf14d1a4b774f9ba7ae4249ceec93869c9f9ba68493f0f','exact portrait asset')
        env.update(GPUI_PORTRAIT_ASSET=str(ROOT/'assets/portrait.png'),GPUI_IMAGE_ASSET=str(upstream/'crates/gpui/examples/image/app-icon.png'),GPUI_RUN_TOKEN=token,
            GPUI_OBSERVATION_OUT=str(out/'rust.json'),CARGO_BUILD_JOBS='2',CARGO_PROFILE_DEV_DEBUG='0',CARGO_PROFILE_TEST_DEBUG='0')
        for tool in ['cargo','rustc']:
            result[tool+'_version']=execute([tool,'+1.98.1','--version','--verbose'],out,tool+'-version',env,cwd=upstream)
            successful(result[tool+'_version'])
        command=['cargo','+1.98.1','test','--locked','-p','gpui','--lib','--no-default-features','--features','test-support','--no-run','--message-format=json']
        result['rust_build']=execute(command,out,'rust-build',env,timeout=3600,cwd=upstream);successful(result['rust_build'])
        artifacts=[json.loads(line) for line in (out/'rust-build.stdout').read_text().splitlines() if line.startswith('{')]
        executables=[a['executable'] for a in artifacts if a.get('reason')=='compiler-artifact' and a.get('target',{}).get('name')=='gpui' and a.get('profile',{}).get('test') and a.get('executable')]
        require(len(executables)==1,'one actual Rust test executable')
        binary=Path(executables[0]).resolve();require(binary.is_relative_to(upstream),'Rust executable location')
        shutil.copy2(binary,out/'rust-observer')
        result['rust_executable']={'path':str(binary),'retained':'rust-observer','sha256':digest(binary),'size':binary.stat().st_size}
        result['rust_process']=execute([str(binary),'image_resource_conformance_observer::observe_image_resources','--nocapture'],out,'rust-test',env,timeout=120,cwd=upstream);successful(result['rust_process'])
        require('1 passed; 0 failed' in (out/'rust-test.stdout').read_text(),'exactly one actual observer test')
        require(digest(binary)==result['rust_executable']['sha256'],'unchanged Rust executable')
        result['numerical']=compare(load(out/'rust.json'),core_output)
        result['browser_process']=execute(['node',str(Path(__file__).with_name('capture.mjs')),str(ROOT),str(out/'core.json'),str(out/'browser')],out,'browser-capture',env,timeout=300,cwd=ROOT)
        successful(result['browser_process']);result['browser']=load(out/'browser/report.json')
        require(result['browser']['status']=='passed-bounded-browser-image-proof','browser acceptance')
        result['status']='passed-bounded-image-prerequisite';result['full_opacity_port']=False;result['full_pixel_parity']=False
    finally:
        result['files']=inventory(out);save(out/'report.json',result)
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--core-source',type=Path,required=True);p.add_argument('--upstream-source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.core_source,a.upstream_source,a.output)
