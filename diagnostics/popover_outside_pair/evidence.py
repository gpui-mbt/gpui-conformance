"""Reopen the complete pair bundle against external source and CI identities.
Tool/sysroot hashes and compiler records require corroborating original CI logs;
this verifier does not claim cryptographic proof of execution.
"""
import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shlex
from run_rust import (ORACLE,ORACLE_TREE,CORE,CORE_TREE,UPSTREAM,UPSTREAM_TREE,FLOOR,
    ORACLE_PATHS,UPSTREAM_PATHS,STAGED_PATHS,UNSET,digest,git,inventory,load,require,
    safe_file,validate_source,rust_build_graph,staged_inventory)

ADDITIONS = {'adapters/popover_outside_moonbit/main.mbt','adapters/popover_outside_moonbit/moon.pkg',
    *('diagnostics/popover_outside_pair/'+p for p in ['profile.json','run.py','compare.py','evidence.py',
       'run_rust.py','run_controls.py','README.md']),
    'tests/test_outside_pointer_pair.py','.github/workflows/popover-outside-pair.yml'}


def entries(source,commit):
    result={}
    for row in git(source,'ls-tree','-rz',commit).split(b'\0'):
        if row:
            metadata,path=row.split(b'\t',1);result[path.decode()]=metadata.decode()
    return result


def validate_pair(pair,oracle,commit,tree):
    require(re.fullmatch('[0-9a-f]{40}',commit) and re.fullmatch('[0-9a-f]{40}',tree),'exact pair identity')
    validate_source(pair,commit,tree);validate_source(oracle,ORACLE,ORACLE_TREE)
    require(git(pair,'rev-parse',ORACLE+'^{tree}').decode().strip()==ORACLE_TREE,'oracle lineage object')
    git(pair,'merge-base','--is-ancestor',ORACLE,commit)
    before,after=entries(oracle,ORACLE),entries(pair,commit)
    require(len(before)==734 and all(after.get(p)==v for p,v in before.items()),'734 baseline files changed')
    require(set(after)-set(before)==ADDITIONS,'exact owned pair additions')
    require(all(after[p].startswith('100644 blob ') for p in ADDITIONS),'pair file modes')
    require(sum(len(git(pair,'show',commit+':'+p)) for p in ADDITIONS)<=2*1024**2,'source cap')


def check_inventory(directory,manifest):
    safe_file(directory,'manifest.json')
    require(manifest['files']==inventory(directory),'whole-bundle inventory changed')


def process_ok(record,command,cwd=None):
    require(record['command']==command,'command binding')
    if cwd is not None:require(record['cwd']==str(cwd),'process cwd')
    require(type(record['returncode']) is int and record['returncode']==0 and 'spawn_error' not in record,'process exit')
    require(record['timed_out'] is False and record['resource_floor_breached'] is False,'stopped process')
    require(type(record['pid']) is int and record['pid']>0,'process pid')
    times=[datetime.fromisoformat(record[k]) for k in ('started_at','finished_at')]
    require(all(t.tzinfo is not None for t in times) and times[0]<=times[1],'process timestamps')
    samples=record['disk_samples']
    require(type(samples) is list and samples and all(set(s)=={'workspace','tmp'} and
            all(type(v) is int and v>=FLOOR for v in s.values()) for s in samples),'resource samples/floor')
    return times


def ordered(intervals):require(all(a[1]<=b[0] for a,b in zip(intervals,intervals[1:])),'process chronology')

def source_bytes(directory,prefix,source,commit,paths):
    for p in paths:
        require(safe_file(directory,prefix+p).read_bytes()==git(source,'show',commit+':'+p),'source bytes: '+prefix+p)


def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);result=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result);return result


def hash_metadata(info):
    require(set(info)=={'sha256','size'} and re.fullmatch('[0-9a-f]{64}',info['sha256']) and
            type(info['size']) is int and info['size']>0,'typed hash metadata')


def verify_rust(directory,oracle_source,upstream_source,token,root):
    record=load(safe_file(directory,'manifest.json'));check_inventory(directory,record)
    require(type(record['schema_version']) is int and record['schema_version']==2 and record['status']=='executed','Rust status')
    require(record['run_token']==token and record['source_unchanged'] is True,'Rust session/source')
    require(record['oracle']=={'commit':ORACLE,'tree':ORACLE_TREE} and
            record['upstream']=={'commit':UPSTREAM,'tree':UPSTREAM_TREE},'Rust identities')
    required={'probe','toolchain-inputs.json'}|{'oracle/'+p for p in ORACLE_PATHS}|{'upstream/'+p for p in UPSTREAM_PATHS}|{'staged/'+p for p in STAGED_PATHS}
    stems=['resolve-rustc','resolve-cargo','rustc','cargo','sysroot','target-libdir','build','raw']
    required|={stem+'.'+suffix for stem in stems for suffix in ('stdout','stderr')}
    require(set(record['files'])==required,'Rust successful files')
    source_bytes(directory,'oracle/',oracle_source,ORACLE,ORACLE_PATHS)
    source_bytes(directory,'upstream/',upstream_source,UPSTREAM,UPSTREAM_PATHS)
    require(record['execution_root']==str(root),'Rust execution root')
    build=Path(record['build_root']);stage=build/'adapter';cwd=root.parent.parent.parent
    require(build==root.parent.parent/('popover-rust-build-'+token),'Rust build root')
    upstream=Path(record['upstream_source_path'])
    require(upstream.is_absolute() and '..' not in upstream.parts,'upstream build path')
    require(record['staged_inputs']==staged_inventory(directory/'staged'),'staged input inventory')
    original=safe_file(directory,'oracle/adapters/popover_outside_rust/Cargo.toml').read_text()
    placeholder='"../../../zed-source/crates/gpui"'
    require(original.count(placeholder)==1,'Cargo placeholder')
    require(safe_file(directory,'staged/Cargo.toml').read_text()==original.replace(placeholder,json.dumps(str(upstream/'crates/gpui'))),'actual staged manifest relocation')
    for p in ('Cargo.lock','src/main.rs'):
        require(safe_file(directory,'staged/'+p).read_bytes()==safe_file(directory,'oracle/adapters/popover_outside_rust/'+p).read_bytes(),'actual staged source/lock')
    require(set(record['tools'])=={'rustc','cargo'},'Rust selected tools')
    intervals=[]
    for tool in ('rustc','cargo'):
        key='resolve-'+tool
        intervals.append(process_ok(record[key],['rustup','which','--toolchain','1.98.1',tool],cwd))
        info=record['tools'][tool]
        require(set(info)=={'path','sha256','size'},'Rust tool metadata')
        hash_metadata({k:info[k] for k in ('sha256','size')})
        require(Path(info['path']).is_absolute() and '..' not in Path(info['path']).parts and
                safe_file(directory,key+'.stdout').read_text().strip()==info['path'],'resolved Rust tool binding')
        require(safe_file(directory,key+'.stderr').stat().st_size==0,'Rust resolution stderr')
    env={'CARGO_BUILD_JOBS':'2','CARGO_INCREMENTAL':'0','CARGO_HOME':str(build/'cargo-home'),
         'CARGO_TARGET_DIR':str(build/'target'),'RUSTUP_TOOLCHAIN':'1.98.1','RUSTC':record['tools']['rustc']['path']}
    require(record['environment']==env,'Rust environment')
    removed=record['unset_environment']
    require(type(removed) is list and removed==sorted(set(removed)) and set(UNSET)<=set(removed) and
            all(isinstance(k,str) and re.fullmatch('[A-Z0-9_]+',k) for k in removed),'Rust removed overrides')
    for tool in ('rustc','cargo'):
        intervals.append(process_ok(record[tool],[record['tools'][tool]['path'],'--version','--verbose'],cwd))
        require(safe_file(directory,tool+'.stdout').read_text().startswith(tool+' 1.98.1 '),'Rust version')
        require(safe_file(directory,tool+'.stderr').stat().st_size==0,'Rust version stderr')
    for query in ('sysroot','target-libdir'):
        intervals.append(process_ok(record[query],[record['tools']['rustc']['path'],'--print',query],cwd))
        require(safe_file(directory,query+'.stderr').stat().st_size==0,'Rust query stderr')
    inputs=record['toolchain_inputs']
    require(load(safe_file(directory,'toolchain-inputs.json'))==inputs,'Rust toolchain sidecar')
    require(set(inputs)=={'sysroot','target_libdir','files','aliases'},'Rust toolchain fields')
    sysroot,target=Path(inputs['sysroot']),Path(inputs['target_libdir'])
    host_lines=[l.removeprefix('host: ') for l in safe_file(directory,'rustc.stdout').read_text().splitlines() if l.startswith('host: ')]
    require(len(host_lines)==1 and re.fullmatch('[A-Za-z0-9_-]+',host_lines[0]),'rustc host')
    require(sysroot.is_absolute() and '..' not in sysroot.parts and target==sysroot/'lib/rustlib'/host_lines[0]/'lib','Rust target standard library root')
    require(safe_file(directory,'sysroot.stdout').read_text().strip()==str(sysroot) and
            safe_file(directory,'target-libdir.stdout').read_text().strip()==str(target),'Rust compiler library queries')
    for tool in ('rustc','cargo'):require(record['tools'][tool]['path']==str(sysroot/'bin'/tool),'selected toolchain distribution')
    require(type(inputs['files']) is dict and 0<len(inputs['files'])<=1024 and any(p.endswith('.rlib') for p in inputs['files']),'bounded stdlib inventory')
    for p,info in inputs['files'].items():
        require(Path(p).is_relative_to(sysroot) and '..' not in Path(p).parts,'Rust stdlib input path')
        hash_metadata(info)
    require(type(inputs['aliases']) is dict and len(inputs['aliases'])<=1024,'Rust library aliases')
    for alias,resolved in inputs['aliases'].items():
        require(Path(alias).parent in (sysroot/'lib',target) and '..' not in Path(alias).parts and resolved in inputs['files'],'Rust library alias binding')
    command=[record['tools']['cargo']['path'],'build','--locked','-vv','--message-format=json-render-diagnostics','--manifest-path',str(stage/'Cargo.toml')]
    intervals.append(process_ok(record['build'],command,cwd))
    graph=rust_build_graph(record,safe_file(directory,'build.stdout').read_text(),safe_file(directory,'build.stderr').read_text())
    require(record['graph']==graph,'Cargo graph record')
    probe=safe_file(directory,'probe')
    require(record['executable']=={'path':graph['artifact']['executable'],'sha256':digest(probe),'size':probe.stat().st_size},'Cargo emitted executable bytes')
    with probe.open('rb') as stream:require(stream.read(4)==b'\x7fELF','Rust ELF')
    intervals.append(process_ok(record['execution'],[str(root/'probe'),str(root/'oracle/diagnostics/popover_outside/scenarios.json'),token],cwd))
    ordered(intervals)
    require(safe_file(directory,'raw.stderr').stat().st_size==0,'Rust runtime stderr')
    raw=load(safe_file(directory,'raw.stdout'));fixture=load(safe_file(directory,'oracle/diagnostics/popover_outside/scenarios.json'))
    require(raw['run_token']==token,'Rust raw token')
    module(Path(oracle_source)/'diagnostics/popover_outside/verify.py','frozen_popover').verify(raw,fixture)
    return raw,fixture,record


def verify_js_plan(out,candidate,inputs,shared=None):
    """Bind every source, generated interface/core, and retained runtime input."""
    shared=Path(shared) if shared is not None else Path(out)
    prefix='_build/js/debug/build/';standard='$MOON_HOME/lib/core/_build/js/release/bundle'
    home=candidate['environment']['MOON_HOME'];packages={str(Path(p).parent) for p in inputs if p.endswith('.mbt')}
    compiled,linked,generated=set(),[],set()
    def value(command,flag):
        require(command.count(flag)==1 and command.index(flag)+1<len(command),'compiler flag: '+flag)
        return command[command.index(flag)+1]
    def normalize(arg):
        if arg.startswith(home+'/'):return '$MOON_HOME'+arg[len(home):]
        return arg[2:] if arg.startswith('./') else arg
    def retained(path):
        path=normalize(path);require('..' not in Path(path).parts,'unsafe compiler graph path')
        if path.startswith(prefix):
            generated.add(path);file=safe_file(out,'build-source/'+path)
        elif path.startswith(standard+'/'):file=safe_file(shared,'toolchain-inputs/js-bundle/'+path[len(standard)+1:])
        else:raise ValueError('unretained compiler graph input: '+path)
        require(file.stat().st_size>0,'empty compiler graph input');return path
    commands=[shlex.split(line) for line in safe_file(out,'build-plan.stdout').read_text().splitlines() if line.strip()]
    for command in commands:
        require(command[0] in ('moonc',candidate['toolchain']['moonc']['command_path'],candidate['toolchain']['moonc']['resolved_path']),'compiler program')
        require(len(command)>1 and command[1] in ('build-package','link-core'),'compiler action')
        require(value(command,'-target')=='js' and '-g' in command and '-O0' in command,'JS debug target')
        output=normalize(value(command,'-o'))
        if command[1]=='build-package':
            package=value(command,'-pkg').removeprefix('f4ah6o/gpui/')
            require(package in packages and package not in compiled,'package coverage')
            actual=sorted(normalize(a) for a in command if a.endswith('.mbt'))
            expected=sorted(p for p in inputs if p.endswith('.mbt') and str(Path(p).parent)==package)
            require(actual==expected,'exact compiler source inputs')
            require(output==prefix+package+'/'+Path(package).name+'.core','compiler output')
            require(value(command,'-pkg-type')==('executable' if package=='probe' else 'library'),'package type')
            require(normalize(value(command,'-std-path'))==standard,'standard library root')
            retained(output[:-5]+'.mi');compiled.add(package)
        else:
            require(output==prefix+'probe/probe.js' and value(command,'-main')=='f4ah6o/gpui/probe','JS main/output')
            linked.append(command)
        retained(output)
        for index,arg in enumerate(command):
            if arg=='-i':retained(command[index+1].split(':',1)[0])
            if normalize(arg).endswith(('.core','.mi')):retained(arg)
            if arg=='-all-pkgs':retained(command[index+1])
    require(compiled==packages and len(linked)==1,'complete JS graph')
    cores=[normalize(arg) for arg in linked[0] if arg.endswith('.core')]
    require(len(cores)==len(set(cores)),'duplicate linked input')
    expected={prefix+p+'/'+Path(p).name+'.core' for p in packages}
    require({p for p in cores if p.startswith(prefix)}==expected,'linked production inputs')
    external=set(cores)-expected
    require(external and all(p.startswith(standard+'/') for p in external),'linked standard inputs')
    return {'commands':commands,'required_generated':sorted(generated)}


def verify_candidate(directory,record,core_source,pair_source,token,root,fixture,relative='candidate',mutation=None):
    out=Path(directory)/relative;candidate=load(safe_file(out,'manifest.json'))
    require(type(candidate['schema_version']) is int and candidate['schema_version']==1 and candidate['status']=='executed','candidate status')
    require((candidate['mutation'] is None)==(mutation is None),'candidate mutation mode')
    if mutation is None:
        require(record['candidate']==candidate and candidate['shared_toolchain'] is None,'ordinary candidate sidecar/shared mode')
        check_inventory(out,candidate);shared=out
    else:
        actual=inventory(out);require('comparison.json' in actual,'control comparison missing');actual.pop('comparison.json')
        require(candidate['files']==actual and candidate['shared_toolchain']=='candidate','control inventory/shared mode')
        shared=Path(directory)/'candidate'
        require(not (out/'tools').exists() and not (out/'toolchain-inputs').exists(),'controls must use immutable shared inputs')
        # Derive the location from the known bundle root, never a manifest path.
        ordinary=load(safe_file(shared,'manifest.json'));check_inventory(shared,ordinary)
        for tool in ('moon','moonc','node'):
            require({k:v for k,v in candidate['toolchain'][tool].items() if k!='version'}==
                    {k:v for k,v in ordinary['toolchain'][tool].items() if k!='version'},'shared compiler identity')
        require(candidate['environment']['MOON_HOME']==ordinary['environment']['MOON_HOME'],'shared compiler home')
    require(candidate['execution_root']==str(root/relative),'candidate root')
    source=root/relative/'build-source';module_text='name = "f4ah6o/gpui"\nversion = "0.0.0"\n'
    require(candidate['module']==module_text and safe_file(out,'build-source/moon.mod').read_text()==module_text,'candidate module')
    mutation_spec=None
    if mutation is not None:
        controls=module(Path(pair_source)/'diagnostics/popover_outside_pair/run_controls.py','checked_controls')
        require(mutation in controls.NAMES,'control name');mutation_spec=controls.replacements(mutation)
    changed=False
    def check_input(path,data):
        nonlocal changed
        expected=data
        if mutation_spec is not None and path==mutation_spec[0]:
            before,after=mutation_spec[1:];text=data.decode();require(text.count(before)==1,'mutation site')
            expected=text.replace(before,after,1).encode();changed=True
            descriptor=dict(name=mutation,path=path,before=before,after=after,original_sha256=hashlib.sha256(data).hexdigest(),
                mutated_sha256=hashlib.sha256(expected).hexdigest(),kind='production-dispatch' if path.startswith('element/') else 'production-api-adapter-misuse')
            require(candidate['mutation']==descriptor,'source mutation descriptor')
        require(safe_file(out,'build-source/'+path).read_bytes()==expected,'candidate source: '+path)
    expected={};packages={'primitives','layout','scene','element','controls/button'}
    for path,metadata in entries(core_source,CORE).items():
        name=Path(path)
        if str(name.parent) in packages and (name.name=='moon.pkg' or name.suffix=='.mbt' and not name.name.endswith(('_test.mbt','_wbtest.mbt'))):
            require(metadata.startswith('100644 blob '),'core source mode')
            data=git(core_source,'show',CORE+':'+path)
            expected[path]={'origin':'core','path':path,'sha256':hashlib.sha256(data).hexdigest(),'blob':metadata.split()[2]}
            check_input(path,data)
    for name in ('main.mbt','moon.pkg'):
        path='adapters/popover_outside_moonbit/'+name;commit=record['sources']['pair']['commit']
        data=git(pair_source,'show',commit+':'+path)
        expected['probe/'+name]={'origin':'pair','path':path,'sha256':hashlib.sha256(data).hexdigest(),
            'blob':git(pair_source,'rev-parse',commit+':'+path).decode().strip()}
        check_input('probe/'+name,data)
    require((mutation is not None)==changed and candidate['inputs']==expected,'exact candidate inputs/transformation')
    actual={p.relative_to(out/'build-source').as_posix() for p in (out/'build-source').rglob('*') if p.is_file() and '_build' not in p.relative_to(out/'build-source').parts}
    require(actual==set(expected)|{'moon.mod'},'unrecorded compiler source inputs')
    env=candidate['environment']
    require(set(env)=={'MOON_HOME','GPUI_SCENARIOS','GPUI_RUN_TOKEN','NODE_OPTIONS','NODE_PATH'},'candidate environment fields')
    require(Path(env['MOON_HOME']).is_absolute() and env['GPUI_SCENARIOS']==json.dumps(fixture,separators=(',',':')) and
            env['GPUI_RUN_TOKEN']==token and env['NODE_OPTIONS'] is None and env['NODE_PATH'] is None,'candidate environment')
    require(set(candidate['toolchain'])=={'moon','moonc','node'},'candidate tool set')
    intervals=[]
    for tool in ('moon','moonc','node'):
        info=candidate['toolchain'][tool]
        require(set(info)=={'command_path','resolved_path','sha256','version'},'tool metadata')
        require(Path(info['command_path']).is_absolute() and Path(info['resolved_path']).is_absolute(),'tool paths')
        require(digest(safe_file(shared,'tools/'+tool))==info['sha256'],'retained compiler bytes')
        intervals.append(process_ok(info['version'],[info['resolved_path'],'--version'],source))
        require(safe_file(out,tool+'-version.stdout').stat().st_size>0,'tool version output');safe_file(out,tool+'-version.stderr')
    bundle=shared/'toolchain-inputs/js-bundle'
    require(bundle.is_dir() and any(p.is_file() for p in bundle.rglob('*')),'shared standard library missing')
    command=[candidate['toolchain']['moon']['resolved_path'],'build','--target','js','--debug']
    intervals.append(process_ok(candidate['build_plan'],command+['--dry-run'],source))
    intervals.append(process_ok(candidate['build'],command,source))
    intervals.append(process_ok(candidate['execution'],[candidate['toolchain']['node']['resolved_path'],str(root/relative/'probe.js')],source));ordered(intervals)
    verify_js_plan(out,candidate,expected,shared)
    require(safe_file(out,'probe.js').read_bytes()==safe_file(out,'build-source/_build/js/debug/build/probe/probe.js').read_bytes(),'executed JS differs from compiler output')
    for stem in ('build-plan','build','raw'):
        safe_file(out,stem+'.stdout');safe_file(out,stem+'.stderr')
    require(safe_file(out,'raw.stderr').stat().st_size==0,'candidate runtime stderr')
    raw=load(safe_file(out,'raw.stdout'));require(raw['run_token']==token and raw['input']==fixture,'candidate raw input/session')
    return raw,candidate


def verify_bundle(directory,*,pair_source,oracle_source,core_source,upstream_source,pair_commit,pair_tree,
                  repository,run_id,run_attempt,recorded_execution_root):
    directory=Path(directory);record=load(safe_file(directory,'manifest.json'))
    expected={'pair':{'commit':pair_commit,'tree':pair_tree},'oracle':{'commit':ORACLE,'tree':ORACLE_TREE},
              'core':{'commit':CORE,'tree':CORE_TREE},'upstream':{'commit':UPSTREAM,'tree':UPSTREAM_TREE}}
    require(record['sources']==expected,'external source identities')
    validate_pair(pair_source,oracle_source,pair_commit,pair_tree)
    validate_source(core_source,CORE,CORE_TREE);validate_source(upstream_source,UPSTREAM,UPSTREAM_TREE)
    require(record['session']=={'repository':repository,'run_id':run_id,'run_attempt':run_attempt,'sha':pair_commit,'job':'actual-popover-outside-pair'},'external CI session')
    require(re.fullmatch('[0-9]+',run_id) and re.fullmatch('[1-9][0-9]*',run_attempt),'session shape')
    require(type(record['schema_version']) is int and record['schema_version']==1 and record['status']=='executed' and record['source_unchanged'] is True,'pair status')
    token=record['run_token'];require(isinstance(token,str) and re.fullmatch('[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}',token),'token shape')
    root=Path(recorded_execution_root);require(root.is_absolute() and '..' not in root.parts and str(root)==record['execution_root'],'execution root')
    check_inventory(directory,record)
    require(sum(v['size'] for v in record['files'].values())<=512*1024**2,'evidence expansion ceiling')
    require({p.name for p in directory.iterdir()}=={'manifest.json','pair','rust','candidate','controls','comparison.json','controls.json'},'bundle top-level entries')
    require(set(inventory(directory/'pair'))==ADDITIONS,'pair snapshot inventory')
    source_bytes(directory,'pair/',pair_source,pair_commit,ADDITIONS)
    raw,fixture,rust=verify_rust(directory/'rust',oracle_source,upstream_source,token,root/'rust')
    require(record['rust']==rust,'Rust manifest sidecar')
    candidate,candidate_manifest=verify_candidate(directory,record,core_source,pair_source,token,root,fixture)
    comparator=module(Path(pair_source)/'diagnostics/popover_outside_pair/compare.py','pair_comparator')
    result=comparator.compare(raw,candidate,oracle_source,fixture,token)
    require(load(safe_file(directory,'comparison.json'))==result and result['status']=='match','ordinary comparison')
    controls_module=module(Path(pair_source)/'diagnostics/popover_outside_pair/run_controls.py','pair_controls')
    start,finish=[datetime.fromisoformat(record[k]) for k in ('started_at','finished_at')]
    require(start.tzinfo is not None and finish.tzinfo is not None and start<=finish,'bundle timestamps')
    rust_start=datetime.fromisoformat(rust['resolve-rustc']['started_at']);rust_end=datetime.fromisoformat(rust['execution']['finished_at'])
    candidate_start=datetime.fromisoformat(candidate_manifest['toolchain']['moon']['version']['started_at'])
    previous_end=datetime.fromisoformat(candidate_manifest['execution']['finished_at'])
    require(start<=rust_start<=rust_end<=candidate_start<=previous_end<=finish,'pair chronology')
    controls=[]
    for name in controls_module.NAMES:
        control,manifest=verify_candidate(directory,record,core_source,pair_source,token,root,fixture,relative='controls/'+name,mutation=name)
        control_start=datetime.fromisoformat(manifest['toolchain']['moon']['version']['started_at'])
        control_end=datetime.fromisoformat(manifest['execution']['finished_at'])
        require(previous_end<=control_start<=control_end<=finish,'control chronology');previous_end=control_end
        compared=comparator.compare(raw,control,oracle_source,fixture,token)
        require(compared['status']=='semantic_mismatch' and compared['differences'],'control survived')
        require(load(safe_file(directory,'controls/'+name+'/comparison.json'))==compared,'control comparison sidecar')
        controls.append(dict(name=name,status='semantic_rejection',build_returncode=0,execution_returncode=0,
            differing_operations=[row['operation'] for row in compared['differences']]))
    require(record['controls']==controls and load(safe_file(directory,'controls.json'))==controls,'control outcomes')
    require({p.name for p in (directory/'controls').iterdir()}==set(controls_module.NAMES),'control directories')
    return {'execution_authenticated':False,'run_attestation':{'status':'external_git_and_ci_session_bound',
        'sources':expected,'repository':repository,'run_id':run_id,'run_attempt':run_attempt,
        'limitation':'Corroborate compiler/process/toolchain hash records with original CI logs and artifact provenance; JSON is not execution proof.'},'comparison':result}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path)
    for name in ('pair-source','oracle-source','core-source','upstream-source','pair-commit','pair-tree','repository','run-id','run-attempt','recorded-execution-root'):
        parser.add_argument('--'+name,required=True)
    print(json.dumps(verify_bundle(**vars(parser.parse_args())),indent=2))


if __name__=='__main__':main()
