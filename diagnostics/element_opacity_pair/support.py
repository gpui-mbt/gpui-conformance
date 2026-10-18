"""Fresh paired Rust observer; compiler-binding helpers retained from merged PR71.
No historical GITHUB session or runner identity is substituted.
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
PROFILE = Path(__file__).with_name('profile.json')
UPSTREAM = '5a5fbe79917971a4d52a96b6ddb04da198a5012e'
UPSTREAM_TREE = '990fb995914d51a546b20e5cf0382dafc105c299'
FLOOR = 1024**3 + 32*1024**2
FIXTURE_PATHS = [
    'adapters/element_opacity_rust/Cargo.toml',
    'adapters/element_opacity_rust/Cargo.lock',
    'adapters/element_opacity_rust/src/main.rs',
    'diagnostics/padded_text_anchor/README.md',
    'diagnostics/padded_text_anchor/scenarios.json',
    'diagnostics/padded_text_anchor/verify.py',
    'tests/test_padded_text_anchor.py',
]
UPSTREAM_PATHS = ['Cargo.toml','Cargo.lock','rust-toolchain.toml','crates/gpui/Cargo.toml',
    'crates/gpui/examples/popover.rs','crates/gpui/examples/example_support/fonts.rs',
    'crates/gpui/src/elements/anchored.rs','crates/gpui/src/elements/deferred.rs',
    'crates/gpui/src/elements/div.rs','crates/gpui/src/elements/text.rs',
    'crates/gpui/src/window.rs','crates/gpui/src/platform.rs','crates/gpui/src/platform/test/platform.rs',
    'crates/gpui/src/app/test_context.rs','crates/gpui/src/platform/test/window.rs',
    'crates/gpui/src/style.rs','crates/gpui/src/taffy.rs','crates/gpui/src/text_system.rs',
    'crates/gpui/src/text_system/line_layout.rs','crates/gpui/src/text_system/line_wrapper.rs',
    'crates/gpui/src/geometry.rs','crates/gpui/src/util.rs']
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
                m.get('target',{}).get('name')=='gpui-element-opacity-diagnostic' and
                m.get('target',{}).get('kind')==['bin']]
    require(len(selected)==1,'one fresh Cargo probe artifact')
    artifact = selected[0]
    require(artifact['fresh'] is False and artifact['target']['src_path']==str(stage/'src/main.rs'),'Cargo staged source/freshness')
    executable = str(target/'debug/gpui-element-opacity-diagnostic')
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
            if '--crate-name' in command and command[command.index('--crate-name')+1]=='gpui_element_opacity_diagnostic':
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



def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result



def object_id(kind, data):
    return hashlib.sha1(kind.encode()+b' '+str(len(data)).encode()+b'\0'+data).hexdigest()

def tree_entries(data):
    result={};offset=0
    while offset<len(data):
        space=data.index(b' ',offset);zero=data.index(b'\0',space)
        mode=data[offset:space].decode();name=data[space+1:zero].decode()
        require(name not in result and name not in ('.','..') and '/' not in name,'Git tree path')
        require(zero+21<=len(data),'short Git tree hash')
        result[name]=(mode,data[zero+1:zero+21].hex());offset=zero+21
    return result

def snapshot_git_proof(source,destination,commit,paths):
    """Retain only the commit and ancestor tree objects for selected inputs."""
    destination=Path(destination);destination.mkdir()
    commit_bytes=git(source,'cat-file','commit',commit)
    require(object_id('commit',commit_bytes)==commit,'commit object')
    (destination/commit).write_bytes(commit_bytes)
    root=commit_bytes.splitlines()[0].decode().removeprefix('tree ')
    retained={commit}
    for path in paths:
        tree=root
        for part in PurePosixPath(path).parts:
            raw=git(source,'cat-file','tree',tree)
            require(len(raw)<=1024**2 and object_id('tree',raw)==tree,'bounded tree object')
            if tree not in retained:(destination/tree).write_bytes(raw);retained.add(tree)
            mode,tree=tree_entries(raw)[part]
            if part!=PurePosixPath(path).parts[-1]:require(mode=='40000','source tree mode')
    require(sum(p.stat().st_size for p in destination.iterdir())<=16*1024**2,'proof size cap')

def verify_git_proof(proof,commit,tree,paths):
    raw=safe_file(proof,commit).read_bytes()
    require(object_id('commit',raw)==commit and raw.splitlines()[0]==('tree '+tree).encode(),'commit/tree provenance')
    for path,expected_blob in paths.items():
        current=tree;parts=PurePosixPath(path).parts
        require(parts and str(PurePosixPath(path))==path and '..' not in parts and not path.startswith('/'),'proof path')
        for index,part in enumerate(parts):
            raw=safe_file(proof,current).read_bytes()
            require(object_id('tree',raw)==current,'tree object provenance')
            require(part in tree_entries(raw),'missing source tree entry')
            mode,current=tree_entries(raw)[part]
            require(mode==('100644' if index==len(parts)-1 else '40000'),'regular compiler source mode')
        require(current==expected_blob,'source input differs from committed tree')
