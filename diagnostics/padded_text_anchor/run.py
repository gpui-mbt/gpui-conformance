"""Dedicated Rust-only observer runner, derived from PR70's compiler binding.
Draft profiles cannot execute. No caller-supplied source identity overrides.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import signal
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
PROFILE = Path(__file__).with_name('execution_profile.json')
UPSTREAM = '5a5fbe79917971a4d52a96b6ddb04da198a5012e'
UPSTREAM_TREE = '990fb995914d51a546b20e5cf0382dafc105c299'
FLOOR = 1024**3 + 32*1024**2
FIXTURE_PATHS = [
    'adapters/padded_text_anchor_rust/Cargo.toml',
    'adapters/padded_text_anchor_rust/Cargo.lock',
    'adapters/padded_text_anchor_rust/src/main.rs',
    'diagnostics/padded_text_anchor/README.md',
    'diagnostics/padded_text_anchor/scenarios.json',
    'diagnostics/padded_text_anchor/verify.py',
    'tests/test_padded_text_anchor.py',
]
RUNNER_PATHS = [
    'diagnostics/padded_text_anchor/run.py',
    'diagnostics/padded_text_anchor/evidence.py',
    'diagnostics/padded_text_anchor/execution_profile.json',
    'tests/test_padded_anchor_evidence.py',
    '.github/workflows/padded-text-anchor.yml',
]
UPSTREAM_PATHS = ['Cargo.toml','Cargo.lock','rust-toolchain.toml','crates/gpui/Cargo.toml',
    'crates/gpui/examples/popover.rs','crates/gpui/examples/example_support/fonts.rs',
    'crates/gpui/src/elements/anchored.rs','crates/gpui/src/elements/deferred.rs',
    'crates/gpui/src/elements/div.rs','crates/gpui/src/elements/text.rs',
    'crates/gpui/src/window.rs','crates/gpui/src/platform.rs','crates/gpui/src/platform/test/platform.rs',
    'crates/gpui/src/app/test_context.rs','crates/gpui/src/platform/test/window.rs',
    'crates/gpui/src/style.rs','crates/gpui/src/taffy.rs','crates/gpui/src/text_system.rs']
STAGED_PATHS = ['Cargo.toml','Cargo.lock','src/main.rs']
UNSET = ['DISPLAY','WAYLAND_DISPLAY','RUSTFLAGS','CARGO_ENCODED_RUSTFLAGS','RUSTDOCFLAGS',
         'RUSTC_WRAPPER','RUSTC_WORKSPACE_WRAPPER','CARGO_BUILD_TARGET','RUSTC','RUSTDOC']

def require(ok, message):
    if not ok: raise ValueError(message)


def load(path):
    def pairs(items):
        result = {}
        for key,value in items:
            require(key not in result,'duplicate JSON key')
            result[key] = value
        return result
    def invalid(value): raise ValueError('nonfinite JSON: '+value)
    return json.loads(Path(path).read_text(),object_pairs_hook=pairs,parse_constant=invalid)


def json_same(left,right):
    """Strict recursively typed evidence metadata equality (bool is not int)."""
    if type(left) is not type(right):return False
    if type(left) is dict:return left.keys()==right.keys() and all(json_same(left[k],right[k]) for k in left)
    if type(left) is list:return len(left)==len(right) and all(json_same(a,b) for a,b in zip(left,right))
    return type(left) in (str,int,float,bool,type(None)) and left==right


def save(path,value): Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def now(): return datetime.now(timezone.utc).isoformat()


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''): result.update(chunk)
    return result.hexdigest()


def git(source,*args): return subprocess.check_output(['git','-C',str(source),*args])


def validate_source(source,commit,tree):
    require(git(source,'rev-parse','HEAD').decode().strip()==commit,'checkout identity')
    require(git(source,'rev-parse','HEAD^{tree}').decode().strip()==tree,'tree identity')
    require(not git(source,'status','--porcelain','--untracked-files=all').strip(),'dirty source')


def safe_file(root,relative):
    require(isinstance(relative,str),'path type')
    path = PurePosixPath(relative)
    require(str(path)==relative and path.parts and not path.is_absolute() and '..' not in path.parts,'unsafe path')
    current = Path(root)
    require(not current.is_symlink(),'symlink root')
    for part in path.parts:
        current /= part
        require(not current.is_symlink(),'symlink evidence')
    require(current.is_file(),'missing file: '+relative)
    return current


def inventory(out):
    result = {}
    require(not Path(out).is_symlink(),'symlink root')
    for path in sorted(Path(out).rglob('*')):
        require(not path.is_symlink(),'symlink evidence')
        require(path.is_file() or path.is_dir(),'nonregular evidence entry')
        if path.is_file() and path != Path(out)/'manifest.json':
            relative = path.relative_to(out).as_posix()
            safe_file(out,relative)
            result[relative] = {'sha256':digest(path),'size':path.stat().st_size}
    return result


def snapshot_source(source,destination,paths):
    for relative in paths:
        src = safe_file(source,relative)
        dst = Path(destination)/relative
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src,dst)


def execute(command,out,stem,environment,timeout=120,cwd=None):
    require(cwd is not None,'explicit cwd required')
    out = Path(out)
    started,begin = now(),time.monotonic()
    samples = [{'workspace':shutil.disk_usage(cwd).free,'tmp':shutil.disk_usage('/tmp').free}]
    require(min(samples[0].values())>=FLOOR,'disk floor before process')
    base = {'command':list(map(str,command)),'cwd':str(Path(cwd).resolve()),'started_at':started}
    with (out/(stem+'.stdout')).open('xb') as stdout,(out/(stem+'.stderr')).open('xb') as stderr:
        try:
            process = subprocess.Popen(command,cwd=cwd,env=environment,stdout=stdout,stderr=stderr,start_new_session=True)
        except OSError as error:
            return dict(base,finished_at=now(),returncode=None,timed_out=False,resource_floor_breached=False,
                        disk_samples=samples,pid=None,spawn_error={'type':type(error).__name__,'message':str(error)})
        timed_out = breached = False
        while process.poll() is None:
            sample = {'workspace':shutil.disk_usage(cwd).free,'tmp':shutil.disk_usage('/tmp').free}
            samples.append(sample)
            timed_out = time.monotonic()-begin>timeout
            breached = min(sample.values())<FLOOR
            if timed_out or breached:
                os.killpg(process.pid,signal.SIGKILL)
                break
            time.sleep(.5)
        code = process.wait()
    return dict(base,finished_at=now(),returncode=code,timed_out=timed_out,
                resource_floor_breached=breached,disk_samples=samples,pid=process.pid)


def staged_inventory(stage):
    require({p.relative_to(stage).as_posix() for p in Path(stage).rglob('*') if p.is_file() or p.is_symlink()}==set(STAGED_PATHS),'exact staged compiler source files')
    return inventory(stage)


def toolchain_inventory(sysroot,target_libdir):
    sysroot,target = Path(sysroot),Path(target_libdir)
    require(sysroot.is_absolute() and target.is_relative_to(sysroot),'Rust sysroot/target path')
    files,aliases = {},{}
    # Retain bounded hash metadata, not another copy of the Rust distribution.
    for directory in (sysroot/'lib',target):
        require(directory.is_dir(),'Rust library directory missing')
        for path in sorted(directory.iterdir()):
            if path.is_file():
                resolved=path.resolve()
                require(resolved.is_relative_to(sysroot) and resolved.is_file(),'Rust library escapes selected sysroot')
                if resolved!=path:aliases[str(path)]=str(resolved)
                files[str(resolved)]={'sha256':digest(resolved),'size':resolved.stat().st_size}
    require(0<len(files)<=1024 and any(p.endswith('.rlib') for p in files),'Rust standard library inventory')
    return {'sysroot':str(sysroot),'target_libdir':str(target),'files':files,'aliases':aliases}


def rust_build_graph(record,stdout,stderr):
    """Reconstruct the selected Cargo artifact and its actual verbose rustc argv."""
    stage = Path(record['build_root'])/'adapter'
    target = Path(record['build_root'])/'target'
    # Cargo -vv deliberately interleaves prefixed build-script directives with
    # its JSON stream. Recognize only the observed protocol, never arbitrary text.
    messages,script_lines = [],[]
    script_pattern = re.compile(r'\[([A-Za-z0-9_-]+) ([0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?)\] cargo::?(rerun-if-changed|rerun-if-env-changed|rustc-check-cfg|rustc-cfg|rustc-env)=(.+)')
    def pairs(items):
        value={}
        for key,item in items:
            require(key not in value,'duplicate Cargo JSON key')
            value[key]=item
        return value
    def invalid(value):raise ValueError('nonfinite Cargo JSON: '+value)
    for line in stdout.splitlines():
        if not line.strip():continue
        matched=script_pattern.fullmatch(line)
        if matched:
            script_lines.append((line,matched.groups()))
        else:
            message=json.loads(line,object_pairs_hook=pairs,parse_constant=invalid)
            require(type(message) is dict and message.get('reason') in
                    ('compiler-artifact','compiler-message','build-script-executed','build-finished'),
                    'unknown Cargo JSON record')
            messages.append(message)
    scripts=[m for m in messages if m.get('reason')=='build-script-executed']
    classified=[]
    for line,(name,version,directive,value) in script_lines:
        matching=[m for m in scripts if m['package_id'].endswith('#'+name+'@'+version) or
                  m['package_id'].endswith('/'+name+'#'+version)]
        require(len(matching)==1,'build-script prefix lacks unique Cargo package record')
        script=matching[0]
        if directive=='rustc-cfg':require(value in script['cfgs'],'build-script cfg differs from Cargo JSON')
        if directive=='rustc-env':
            require('=' in value and value.split('=',1) in script['env'],'build-script env differs from Cargo JSON')
        if directive=='rerun-if-env-changed':require(re.fullmatch('[A-Za-z_][A-Za-z0-9_]*',value),'build-script environment name')
        if directive=='rustc-check-cfg':require(value.startswith('cfg(') and value.endswith(')'),'build-script check-cfg')
        classified.append({'line':line,'package_id':script['package_id'],'directive':directive,'value':value})
    selected = [m for m in messages if m.get('reason')=='compiler-artifact' and
                m.get('target',{}).get('name')=='gpui-padded-text-anchor-diagnostic' and
                m.get('target',{}).get('kind')==['bin']]
    require(len(selected)==1,'one fresh Cargo probe artifact')
    artifact = selected[0]
    require(artifact['fresh'] is False and artifact['target']['src_path']==str(stage/'src/main.rs'),'Cargo staged source/freshness')
    executable = str(target/'debug/gpui-padded-text-anchor-diagnostic')
    require(artifact['executable']==executable and executable in artifact['filenames'],'Cargo executable linkage')
    require(artifact['profile']['test'] is False and artifact['profile']['opt_level']=='0' and
            artifact['profile']['debug_assertions'] is True,'Cargo debug profile')
    finished = [m for m in messages if m.get('reason')=='build-finished']
    require(len(finished)==1 and set(finished[0])=={'reason','success'} and
            finished[0]['success'] is True, 'Cargo completion schema/boolean success')
    commands = []
    for line in stderr.splitlines():
        match = re.search(r'Running `(.*)`\s*$',line)
        if match:
            command = shlex.split(match.group(1))
            if '--crate-name' in command and command[command.index('--crate-name')+1]=='gpui_padded_text_anchor_diagnostic':
                commands.append(command)
    require(len(commands)==1,'one actual probe compiler invocation')
    command = commands[0]
    compiler = record['tools']['rustc']['path']
    require(command.count(compiler)==1,'resolved rustc invocation')
    index = command.index(compiler)
    assignments = command[:index]
    require(all('=' in item for item in assignments),'unexpected compiler prefix')
    env = dict(item.split('=',1) for item in assignments)
    require(env.get('CARGO_MANIFEST_DIR')==str(stage),'verbose Cargo manifest binding')
    args = command[index+1:]
    def value(flag):
        require(args.count(flag)==1 and args.index(flag)+1<len(args),'compiler flag '+flag)
        return args[args.index(flag)+1]
    sources=[arg for arg in args if arg.endswith('.rs')]
    require(len(sources)==1,'one actual compiler source')
    source=Path(sources[0])
    require('..' not in source.parts and (source if source.is_absolute() else stage/source)==stage/'src/main.rs','actual compiler source')
    require(value('--crate-type')=='bin' and value('--out-dir')==str(target/'debug/deps'),'actual compiler output')
    require('--emit=dep-info,link' in args or ('--emit' in args and value('--emit')=='dep-info,link'),'actual compiler emits link')
    return {'artifact':artifact,'compiler_command':command,'build_script_output':classified}



def load_profile(path=PROFILE, require_bound=True):
    profile = load(path)
    keys = {'schema_version','status','fixture_commit','fixture_tree',
            'integration_baseline_commit','integration_baseline_tree',
            'upstream_commit','upstream_tree','fixture_files',
            'estimated_artifact_zip_limit','estimated_artifact_extraction_limit'}
    require(set(profile)==keys and type(profile['schema_version']) is int and profile['schema_version']==1, 'profile schema')
    require(profile['upstream_commit']==UPSTREAM and profile['upstream_tree']==UPSTREAM_TREE, 'upstream pin')
    require(set(profile['fixture_files'])==set(FIXTURE_PATHS), 'seven fixture paths')
    for metadata in profile['fixture_files'].values():
        require(set(metadata)=={'sha256','size'} and isinstance(metadata['sha256'],str) and
                re.fullmatch('[0-9a-f]{64}',metadata['sha256']) and type(metadata['size']) is int and metadata['size']>0, 'fixture hash metadata')
    require(sum(m['size'] for m in profile['fixture_files'].values())<=2*1024**2,'fixture source cap')
    require(type(profile['estimated_artifact_zip_limit']) is int and profile['estimated_artifact_zip_limit']==12*1024**2 and
            type(profile['estimated_artifact_extraction_limit']) is int and profile['estimated_artifact_extraction_limit']==48*1024**2,'artifact policy')
    identity_keys = ('fixture_commit','fixture_tree','integration_baseline_commit','integration_baseline_tree')
    if profile['status']=='draft_unbound' and not require_bound:
        require(all(profile[k] is None for k in identity_keys),'draft identity placeholders')
    else:
        require(profile['status']=='bound' and all(isinstance(profile[k],str) and re.fullmatch('[0-9a-f]{40}',profile[k]) for k in identity_keys), 'unbound profile cannot execute or publish')
        require(profile['fixture_commit']!=profile['integration_baseline_commit'], 'fixture source is distinct from integration baseline')
    return profile


def entries(source, commit):
    result = {}
    for row in git(source,'ls-tree','-rz',commit).split(b'\0'):
        if row:
            metadata,path=row.split(b'\t',1)
            result[path.decode()]=metadata.decode()
    return result


def validate_suite(source,fixture,profile,commit,tree):
    require(re.fullmatch('[0-9a-f]{40}',commit) and re.fullmatch('[0-9a-f]{40}',tree),'exact runner identity')
    validate_source(source,commit,tree)
    validate_source(fixture,profile['fixture_commit'],profile['fixture_tree'])
    baseline=profile['integration_baseline_commit']
    require(git(source,'rev-parse',baseline+'^{tree}').decode().strip()==profile['integration_baseline_tree'],'integration baseline tree')
    git(source,'merge-base','--is-ancestor',baseline,commit)
    before,after=entries(source,baseline),entries(source,commit)
    require(all(after.get(path)==blob for path,blob in before.items()),'historical baseline mode/blob changed')
    owned=set(FIXTURE_PATHS)|set(RUNNER_PATHS)
    require(not set(RUNNER_PATHS)&set(before),'runner paths must be new')
    require(set(after)-set(before)==owned-set(before),'exact authorized additions')
    require(all(after[p].startswith('100644 blob ') for p in owned),'owned regular-file modes')
    require(sum(len(git(source,'show',commit+':'+p)) for p in owned)<=2*1024**2,'total source cap')
    require(sum(len(git(source,'show',commit+':'+p)) for p in RUNNER_PATHS)<=512*1024,'runner source cap')
    for path,metadata in profile['fixture_files'].items():
        pinned=git(fixture,'show',profile['fixture_commit']+':'+path)
        require(hashlib.sha256(pinned).hexdigest()==metadata['sha256'] and len(pinned)==metadata['size'],'reviewed fixture hash')
        require(safe_file(fixture,path).read_bytes()==pinned and safe_file(source,path).read_bytes()==pinned,'immutable fixture source bytes')
    require(json_same(load(safe_file(source,'diagnostics/padded_text_anchor/execution_profile.json')),profile),'profile checkout binding')


def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture-source',type=Path,required=True)
    parser.add_argument('--upstream-source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    profile=load_profile()  # Drafts stop before creating evidence or invoking tools.
    fixture,upstream,out=map(lambda p:p.resolve(),(args.fixture_source,args.upstream_source,args.output))
    require(out.parent==ROOT/'_build','fresh evidence directly under ignored _build')
    require(min(shutil.disk_usage(ROOT).free,shutil.disk_usage('/tmp').free)>=FLOOR,'disk floor before writes')
    out.mkdir(parents=True,exist_ok=False)
    token=str(uuid.uuid4());build=ROOT/'_build'/('padded-anchor-build-'+token);stage=build/'adapter'
    record={'schema_version':1,'status':'preflight','run_token':token,'execution_root':str(out),
            'build_root':str(build),'upstream_source_path':str(upstream),'fixture_source_path':str(fixture),
            'profile':profile,'tools':{},'source_unchanged':False,'started_at':now()}
    failure=None
    try:
        require(os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_OS')=='Linux' and
                os.environ.get('GITHUB_JOB')=='actual-padded-text-anchor','dedicated CI required')
        commit=git(ROOT,'rev-parse','HEAD').decode().strip();tree=git(ROOT,'rev-parse','HEAD^{tree}').decode().strip()
        record['runner']={'commit':commit,'tree':tree}
        record['session']={k:os.environ[k] for k in ('GITHUB_REPOSITORY','GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT','GITHUB_SHA','GITHUB_JOB')}
        require(record['session']['GITHUB_SHA']==commit,'CI runner commit binding')
        validate_suite(ROOT,fixture,profile,commit,tree);validate_source(upstream,UPSTREAM,UPSTREAM_TREE)
        require(min(shutil.disk_usage(ROOT).free,shutil.disk_usage('/tmp').free)>=9*1024**3,'9GiB build headroom')
        snapshot_source(fixture,out/'fixture',FIXTURE_PATHS)
        snapshot_source(ROOT,out/'runner',RUNNER_PATHS)
        snapshot_source(upstream,out/'upstream',UPSTREAM_PATHS)
        build.mkdir(exist_ok=False)
        shutil.copytree(fixture/'adapters/padded_text_anchor_rust',stage)
        original=(stage/'Cargo.toml').read_text();placeholder='"../../../zed-source/crates/gpui"'
        require(original.count(placeholder)==1,'Cargo manifest placeholder')
        (stage/'Cargo.toml').write_text(original.replace(placeholder,json.dumps(str(upstream/'crates/gpui'))))
        snapshot_source(stage,out/'staged',STAGED_PATHS)
        record['staged_inputs']=staged_inventory(out/'staged')
        env=os.environ.copy()
        removed=sorted(set(UNSET)|{k for k in env if k.startswith(('CARGO_','RUSTC','RUSTDOC','RUST_'))})
        for key in removed:env.pop(key,None)
        record['unset_environment']=removed
        for tool in ('rustc','cargo'):
            key='resolve-'+tool
            record[key]=execute(['rustup','which','--toolchain','1.98.1',tool],out,key,env,cwd=ROOT)
            require(record[key]['returncode']==0,'Rust tool resolution')
            path=Path((out/(key+'.stdout')).read_text().strip())
            require(path.is_absolute() and path.is_file() and path==path.resolve(),'resolved tool path')
            record['tools'][tool]={'path':str(path),'sha256':digest(path),'size':path.stat().st_size}
        record['environment']={'CARGO_BUILD_JOBS':'2','CARGO_INCREMENTAL':'0','CARGO_HOME':str(build/'cargo-home'),
            'CARGO_TARGET_DIR':str(build/'target'),'RUSTUP_TOOLCHAIN':'1.98.1','RUSTC':record['tools']['rustc']['path']}
        env.update(record['environment'])
        for tool in ('rustc','cargo'):
            record['status']=tool+'_failed'
            record[tool]=execute([record['tools'][tool]['path'],'--version','--verbose'],out,tool,env,cwd=ROOT)
            require(record[tool]['returncode']==0 and (out/(tool+'.stdout')).read_text().startswith(tool+' 1.98.1 '),'Rust version')
        for query in ('sysroot','target-libdir'):
            record[query]=execute([record['tools']['rustc']['path'],'--print',query],out,query,env,cwd=ROOT)
            require(record[query]['returncode']==0,'Rust library query')
        record['toolchain_inputs']=toolchain_inventory((out/'sysroot.stdout').read_text().strip(),(out/'target-libdir.stdout').read_text().strip())
        save(out/'toolchain-inputs.json',record['toolchain_inputs'])
        record['status']='build_failed'
        require(staged_inventory(stage)==record['staged_inputs'],'staged source before build')
        record['build']=execute([record['tools']['cargo']['path'],'build','--locked','-vv',
            '--message-format=json-render-diagnostics','--manifest-path',str(stage/'Cargo.toml')],out,'build',env,timeout=2100,cwd=ROOT)
        require(staged_inventory(stage)==record['staged_inputs'],'staged source drift')
        require(record['build']['returncode']==0,'Rust build failed; original logs retained')
        record['graph']=rust_build_graph(record,(out/'build.stdout').read_text(),(out/'build.stderr').read_text())
        executable=Path(record['graph']['artifact']['executable'])
        record['executable']={'path':str(executable),'sha256':digest(executable),'size':executable.stat().st_size}
        shutil.copy2(executable,out/'probe')
        require(digest(out/'probe')==record['executable']['sha256'],'copied executable differs')
        record['status']='runtime_failed'
        record['execution']=execute([str(out/'probe'),str(out/'fixture/diagnostics/padded_text_anchor/scenarios.json'),token],out,'raw',env,cwd=ROOT)
        require(record['execution']['returncode']==0,'Rust execution failed; original logs retained')
        require(digest(out/'probe')==record['executable']['sha256'] and digest(executable)==record['executable']['sha256'],'executable drift')
        require(staged_inventory(stage)==record['staged_inputs'],'staged source drift after runtime')
        for info in record['tools'].values():require(digest(info['path'])==info['sha256'],'Rust tool drift')
        require(toolchain_inventory(record['toolchain_inputs']['sysroot'],record['toolchain_inputs']['target_libdir'])==record['toolchain_inputs'],'Rust library drift')
        record['status']='trace_validation_failed'
        checker=module(fixture/'diagnostics/padded_text_anchor/verify.py','padded_fixture_checker')
        raw=load(out/'raw.stdout');require(raw['run_token']==token,'raw run token')
        report=checker.verify(raw,load(out/'fixture/diagnostics/padded_text_anchor/scenarios.json'))
        save(out/'trace-shape.json',report)
        require(report['execution_authenticated'] is False and report['attachment_reference_hypothesis_confirmed'] is None,'no inferred provenance/golden')
        record['status']='executed'
    except Exception as error:
        failure=error
        save(out/'failure.json',{'stage':record['status'],'type':type(error).__name__,'message':str(error)})
    finally:
        try:
            if 'runner' in record:
                validate_suite(ROOT,fixture,profile,record['runner']['commit'],record['runner']['tree'])
                validate_source(upstream,UPSTREAM,UPSTREAM_TREE)
                record['source_unchanged']=True
        except Exception as error:
            record['source_check_error']=str(error)
            if failure is None:failure=error
        record['finished_at']=now()
        record['files']=inventory(out);save(out/'manifest.json',record)
    if failure is not None:raise failure
    print(json.dumps({'status':'executed','evidence':str(out),'execution_authenticated':False}))


if __name__=='__main__':main()
