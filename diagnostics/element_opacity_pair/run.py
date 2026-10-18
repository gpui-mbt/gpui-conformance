"""Actual pinned GPUI/MoonBit build and execution. No workflow or deploy changes."""
import argparse
import os
from pathlib import Path
import shutil
import uuid
from support import *
from candidate import compile_candidate, require_success, blobs, production_paths
from compare import compare, validate_fixture

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def identity(path):
    return {'commit':git(path,'rev-parse','HEAD').decode().strip(),
            'tree':git(path,'rev-parse','HEAD^{tree}').decode().strip()}

def rust(pair,upstream,out,token,fixture):
    out.mkdir();build=pair/'_build'/('opacity-rust-build-'+token);stage=build/'adapter';build.mkdir()
    shutil.copytree(pair/'adapters/element_opacity_rust',stage)
    original=(stage/'Cargo.toml').read_text();placeholder='"../../../zed-source/crates/gpui"'
    require(original.count(placeholder)==1,'Cargo path placeholder')
    (stage/'Cargo.toml').write_text(original.replace(placeholder,json.dumps(str(upstream/'crates/gpui'))))
    snapshot_source(stage,out/'staged',STAGED_PATHS)
    record={'schema_version':1,'status':'preflight','run_token':token,'build_root':str(build),'upstream_source_path':str(upstream),'tools':{},'started_at':now()}
    env=os.environ.copy()
    for k in list(env):
        if k in UNSET or k.startswith(('CARGO_','RUSTC','RUSTDOC','RUST_')):env.pop(k,None)
    try:
        for name in ('rustc','cargo'):
            resolved=execute(['rustup','which','--toolchain','1.98.1',name],out,'resolve-'+name,env,cwd=pair)
            require_success(resolved,'installed Rust tool')
            path=Path((out/('resolve-'+name+'.stdout')).read_text().strip()).resolve()
            require(path.is_file(),'Rust executable')
            record['tools'][name]={'path':str(path),'sha256':digest(path),'size':path.stat().st_size}
        env.update({'CARGO_BUILD_JOBS':'2','CARGO_INCREMENTAL':'0','CARGO_HOME':str(build/'cargo-home'),
                    'CARGO_TARGET_DIR':str(build/'target'),'RUSTUP_TOOLCHAIN':'1.98.1','RUSTC':record['tools']['rustc']['path'],
                    'GPUI_SCENARIOS':json.dumps(fixture,separators=(',',':')),'GPUI_RUN_TOKEN':token})
        record['environment']={k:env[k] for k in ('CARGO_BUILD_JOBS','CARGO_INCREMENTAL','CARGO_HOME','CARGO_TARGET_DIR','RUSTUP_TOOLCHAIN','RUSTC','GPUI_SCENARIOS','GPUI_RUN_TOKEN')}
        for name in ('rustc','cargo'):
            record[name]=execute([record['tools'][name]['path'],'--version','--verbose'],out,name,env,cwd=pair)
            require_success(record[name],'Rust version')
            require((out/(name+'.stdout')).read_text().startswith(name+' 1.98.1 '),'Rust version pin')
        for query in ('sysroot','target-libdir'):
            require_success(execute([record['tools']['rustc']['path'],'--print',query],out,query,env,cwd=pair),'Rust sysroot')
        record['toolchain_inputs']=toolchain_inventory((out/'sysroot.stdout').read_text().strip(),(out/'target-libdir.stdout').read_text().strip())
        record['status']='build_failed'
        record['build']=execute([record['tools']['cargo']['path'],'build','--locked','-vv','--message-format=json-render-diagnostics',
            '--manifest-path',str(stage/'Cargo.toml')],out,'build',env,timeout=2100,cwd=pair)
        require_success(record['build'],'Rust compile')
        require(staged_inventory(stage)==staged_inventory(out/'staged'),'compiler source drift')
        record['graph']=rust_build_graph(record,(out/'build.stdout').read_text(),(out/'build.stderr').read_text())
        executable=Path(record['graph']['artifact']['executable']);shutil.copy2(executable,out/'probe')
        record['executable']={'sha256':digest(out/'probe'),'size':(out/'probe').stat().st_size}
        record['status']='execution_failed'
        record['execution']=execute([str(out/'probe')],out,'raw',env,cwd=pair)
        require_success(record['execution'],'Rust execution')
        require(digest(executable)==digest(out/'probe')==record['executable']['sha256'],'runtime artifact drift')
        for t in record['tools'].values():require(digest(t['path'])==t['sha256'],'tool drift')
        record['status']='executed'
    finally:
        record['finished_at']=now();record['files']=inventory(out);save(out/'manifest.json',record)
    return record

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core-source','upstream-source','output'):p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args();core=args.core_source.resolve();upstream=args.upstream_source.resolve();out=args.output.resolve()
    profile=load(HERE/'profile.json');policy=load(HERE/'policy.json');fixture=load(HERE/'scenarios.json')
    validate_fixture(fixture)
    require(profile['status']=='bound' and re.fullmatch('[0-9a-f]{40}',profile['core_commit'] or '') and re.fullmatch('[0-9a-f]{40}',profile['core_tree'] or ''),'unbound candidate cannot execute')
    require(profile['policy_sha256']==digest(HERE/'policy.json') and profile['scenarios_sha256']==digest(HERE/'scenarios.json'),'frozen policy/corpus')
    require(policy['upstream_revision']==UPSTREAM,'upstream policy pin')
    require(out.parent==ROOT/'_build' and not out.exists(),'fresh bounded output')
    require(os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_OS')=='Linux','actual Linux CI session required')
    suite=identity(ROOT);require(os.environ.get('GITHUB_SHA')==suite['commit'],'CI suite commit binding')
    validate_source(ROOT,**{'commit':suite['commit'],'tree':suite['tree']})
    validate_source(core,profile['core_commit'],profile['core_tree']);validate_source(upstream,UPSTREAM,UPSTREAM_TREE)
    for path,sha in policy['source_blobs'].items(): require(blobs(upstream)[path]==sha,'pinned upstream source')
    require(min(shutil.disk_usage(ROOT).free,shutil.disk_usage('/tmp').free)>=9*1024**3,'9GiB initial build headroom')
    out.mkdir(parents=True);tokens={k:str(uuid.uuid4()) for k in ('rust','candidate')}
    manifest={'schema_version':1,'status':'preflight','started_at':now(),'tokens':tokens,'suite':suite,'profile':profile,
              'source_unchanged':False,'execution_root':str(out),'session':{k:os.environ[k] for k in ('GITHUB_REPOSITORY','GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT','GITHUB_SHA','GITHUB_JOB')}}
    try:
        snapshot_source(ROOT,out/'suite',profile['files'])
        snapshot_source(upstream,out/'upstream',list(policy['source_blobs']))
        snapshot_git_proof(core,out/'core-source-proof',profile['core_commit'],production_paths(core))
        manifest['rust']=rust(ROOT,upstream,out/'rust',tokens['rust'],fixture)
        manifest['candidate']=compile_candidate(ROOT,core,out/'candidate',fixture,tokens['candidate'])
        report=compare(load(out/'rust/raw.stdout'),load(out/'candidate/raw.stdout'),fixture,tokens)
        save(out/'comparison.json',report)
        from run_controls import run_controls
        manifest['controls']=run_controls(ROOT,core,out,fixture,load(out/'rust/raw.stdout'),tokens['rust'])
        validate_source(ROOT,suite['commit'],suite['tree']);validate_source(core,profile['core_commit'],profile['core_tree']);validate_source(upstream,UPSTREAM,UPSTREAM_TREE)
        manifest['source_unchanged']=True;manifest['status']='executed' if report['strict_match'] else 'executed_strict_mismatch'
    finally:
        manifest['finished_at']=now();manifest['files']=inventory(out);save(out/'manifest.json',manifest)
    from evidence import verify
    verification=verify(out);save(out/'verification.json',verification)
    require(verification['strict_match'],'actual pair differs')

if __name__=='__main__':main()
