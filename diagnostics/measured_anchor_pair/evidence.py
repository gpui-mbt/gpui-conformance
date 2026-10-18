"""Independently reopen source, compiler graph, session and semantic evidence.
JSON/hashes are not cryptographic execution proof; original CI logs are required.
"""
import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shlex
from run_rust import (UPSTREAM,UPSTREAM_TREE,FLOOR,FIXTURE_PATHS,UPSTREAM_PATHS,STAGED_PATHS,UNSET,
    digest,git,inventory,json_same,load,require,safe_file,validate_source,rust_build_graph,staged_inventory,module)
from run import ADDITIONS,PACKAGES,SPEC_SHA256,entries,load_profile,validate_pair

def check_inventory(directory,manifest):
    safe_file(directory,'manifest.json')
    require(json_same(manifest['files'],inventory(directory)),'whole-bundle inventory changed')


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


def hash_metadata(info):
    require(set(info)=={'sha256','size'} and re.fullmatch('[0-9a-f]{64}',info['sha256']) and
            type(info['size']) is int and info['size']>0,'typed hash metadata')



def verify_rust(directory,fixture_source,upstream_source,runner_source,profile,expected,root):
    directory=Path(directory);root=Path(root)
    require(root.is_absolute() and '..' not in root.parts and root.parent.parent.name=='_build','recorded evidence root')
    record=load(safe_file(directory,'manifest.json'));check_inventory(directory,record)
    require(type(record['schema_version']) is int and record['schema_version']==1 and record['status']=='executed','successful Rust status')
    token=record['run_token']
    require(isinstance(token,str) and re.fullmatch('[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}',token),'UUID run token')
    require(record['source_unchanged'] is True and json_same(record['profile'],profile),'immutable profile/source')
    require(record['runner']=={'commit':expected['commit'],'tree':expected['tree']},'external runner identity')
    require(record['session']=={'GITHUB_REPOSITORY':expected['repository'],'GITHUB_RUN_ID':expected['run_id'],
        'GITHUB_RUN_ATTEMPT':expected['run_attempt'],'GITHUB_SHA':expected['commit'],'GITHUB_JOB':'actual-measured-anchor-pair'},'external CI session')
    required={'probe','toolchain-inputs.json','trace-shape.json'}|{'fixture/'+p for p in FIXTURE_PATHS}|{'runner/'+p for p in profile['additions']}|{'upstream/'+p for p in UPSTREAM_PATHS}|{'staged/'+p for p in STAGED_PATHS}
    stems=['resolve-rustc','resolve-cargo','rustc','cargo','sysroot','target-libdir','build','raw']
    required|={stem+'.'+suffix for stem in stems for suffix in ('stdout','stderr')}
    require(set(record['files'])==required,'exact successful evidence inventory')
    source_bytes(directory,'fixture/',fixture_source,profile['fixture_commit'],FIXTURE_PATHS)
    source_bytes(directory,'runner/',runner_source,expected['commit'],profile['additions'])
    source_bytes(directory,'upstream/',upstream_source,UPSTREAM,UPSTREAM_PATHS)
    require(record['execution_root']==str(root),'recorded execution root')
    build=Path(record['build_root']);stage=build/'adapter';cwd=root.parent.parent.parent
    require(build==root.parent.parent/('measured-anchor-rust-build-'+token),'build root token binding')
    upstream=Path(record['upstream_source_path']);fixture=Path(record['fixture_source_path'])
    require(all(p.is_absolute() and '..' not in p.parts for p in (upstream,fixture)),'recorded source roots')
    require(json_same(record['staged_inputs'],staged_inventory(directory/'staged')),'staged inventory')
    original=safe_file(directory,'fixture/adapters/padded_text_anchor_rust/Cargo.toml').read_text()
    placeholder='"../../../zed-source/crates/gpui"'
    require(original.count(placeholder)==1,'Cargo placeholder')
    require(safe_file(directory,'staged/Cargo.toml').read_text()==original.replace(placeholder,json.dumps(str(upstream/'crates/gpui'))),'single permitted manifest relocation')
    for p in ('Cargo.lock','src/main.rs'):
        require(safe_file(directory,'staged/'+p).read_bytes()==safe_file(directory,'fixture/adapters/padded_text_anchor_rust/'+p).read_bytes(),'staged source/lock unchanged')
    require(set(record['tools'])=={'rustc','cargo'},'selected Rust tools')
    intervals=[]
    for tool in ('rustc','cargo'):
        key='resolve-'+tool
        intervals.append(process_ok(record[key],['rustup','which','--toolchain','1.98.1',tool],cwd))
        info=record['tools'][tool]
        require(set(info)=={'path','sha256','size'},'Rust tool fields')
        hash_metadata({k:info[k] for k in ('sha256','size')})
        require(Path(info['path']).is_absolute() and '..' not in Path(info['path']).parts and safe_file(directory,key+'.stdout').read_text().strip()==info['path'],'resolved tool path')
        require(safe_file(directory,key+'.stderr').stat().st_size==0,'resolution stderr')
    environment={'CARGO_BUILD_JOBS':'2','CARGO_INCREMENTAL':'0','CARGO_HOME':str(build/'cargo-home'),
        'CARGO_TARGET_DIR':str(build/'target'),'RUSTUP_TOOLCHAIN':'1.98.1','RUSTC':record['tools']['rustc']['path']}
    require(record['environment']==environment,'recorded compiler environment')
    removed=record['unset_environment']
    require(type(removed) is list and all(isinstance(k,str) and re.fullmatch('[A-Z0-9_]+',k) for k in removed) and removed==sorted(set(removed)) and set(UNSET)<=set(removed),'removed compiler overrides')
    for tool in ('rustc','cargo'):
        intervals.append(process_ok(record[tool],[record['tools'][tool]['path'],'--version','--verbose'],cwd))
        require(safe_file(directory,tool+'.stdout').read_text().startswith(tool+' 1.98.1 '),'Rust tool version')
        require(safe_file(directory,tool+'.stderr').stat().st_size==0,'tool version stderr')
    for query in ('sysroot','target-libdir'):
        intervals.append(process_ok(record[query],[record['tools']['rustc']['path'],'--print',query],cwd))
        require(safe_file(directory,query+'.stderr').stat().st_size==0,'Rust query stderr')
    inputs=record['toolchain_inputs']
    require(json_same(load(safe_file(directory,'toolchain-inputs.json')),inputs),'toolchain sidecar')
    require(set(inputs)=={'sysroot','target_libdir','files','aliases'},'toolchain fields')
    sysroot,target=Path(inputs['sysroot']),Path(inputs['target_libdir'])
    host_lines=[l.removeprefix('host: ') for l in safe_file(directory,'rustc.stdout').read_text().splitlines() if l.startswith('host: ')]
    require(len(host_lines)==1 and re.fullmatch('[A-Za-z0-9_-]+',host_lines[0]),'rustc host')
    require(sysroot.is_absolute() and '..' not in sysroot.parts and target==sysroot/'lib/rustlib'/host_lines[0]/'lib','Rust target library path')
    require(safe_file(directory,'sysroot.stdout').read_text().strip()==str(sysroot) and safe_file(directory,'target-libdir.stdout').read_text().strip()==str(target),'library query binding')
    for tool in ('rustc','cargo'):require(record['tools'][tool]['path']==str(sysroot/'bin'/tool),'one Rust distribution')
    require(type(inputs['files']) is dict and 0<len(inputs['files'])<=1024 and any(p.endswith('.rlib') for p in inputs['files']),'bounded stdlib metadata')
    for p,info in inputs['files'].items():
        require(Path(p).is_relative_to(sysroot) and '..' not in Path(p).parts,'stdlib safe path')
        hash_metadata(info)
    require(type(inputs['aliases']) is dict and len(inputs['aliases'])<=1024,'bounded stdlib aliases')
    for alias,resolved in inputs['aliases'].items():
        require(Path(alias).parent in (sysroot/'lib',target) and '..' not in Path(alias).parts and resolved in inputs['files'],'stdlib alias binding')
    command=[record['tools']['cargo']['path'],'build','--locked','-vv','--message-format=json-render-diagnostics','--manifest-path',str(stage/'Cargo.toml')]
    intervals.append(process_ok(record['build'],command,cwd))
    graph=rust_build_graph(record,safe_file(directory,'build.stdout').read_text(),safe_file(directory,'build.stderr').read_text())
    require(json_same(record['graph'],graph),'independently reconstructed Cargo graph')
    probe=safe_file(directory,'probe')
    require(record['executable']=={'path':graph['artifact']['executable'],'sha256':digest(probe),'size':probe.stat().st_size},'emitted/executed executable binding')
    with probe.open('rb') as stream:require(stream.read(4)==b'\x7fELF','Rust ELF')
    intervals.append(process_ok(record['execution'],[str(root/'probe'),str(root/'fixture/diagnostics/padded_text_anchor/scenarios.json'),token],cwd))
    ordered(intervals)
    lifetime=[datetime.fromisoformat(record[k]) for k in ('started_at','finished_at')]
    require(all(t.tzinfo is not None for t in lifetime) and lifetime[0]<=intervals[0][0] and intervals[-1][1]<=lifetime[1],'overall process chronology')
    require(safe_file(directory,'raw.stderr').stat().st_size==0,'runtime stderr')
    raw=load(safe_file(directory,'raw.stdout'));fixture_input=load(safe_file(directory,'fixture/diagnostics/padded_text_anchor/scenarios.json'))
    require(raw['run_token']==token,'raw token')
    checker=module(Path(fixture_source)/'diagnostics/padded_text_anchor/verify.py','frozen_padded_checker')
    report=checker.verify(raw,fixture_input)
    require(json_same(load(safe_file(directory,'trace-shape.json')),report),'recomputed trace report')
    require(report['execution_authenticated'] is False and report['observed_numeric_goldens'] is None and report['attachment_reference_hypothesis_confirmed'] is None and report['font_parity'] is False and report['unchanged_example_parity'] is False,'honest shape report')
    return raw,fixture_input,record


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
        controls=module(Path(pair_source)/'diagnostics/measured_anchor_pair/run_controls.py','checked_controls')
        require(mutation in controls.NAMES,'control name');mutation_spec=controls.replacements(mutation)
    changed=False
    def check_input(path,data):
        nonlocal changed
        expected=data
        if mutation_spec is not None and path==mutation_spec[0]:
            before,after=mutation_spec[1:];text=data.decode();require(text.count(before)==1,'mutation site')
            expected=text.replace(before,after,1).encode();changed=True
            descriptor=dict(name=mutation,path=path,before=before,after=after,original_sha256=hashlib.sha256(data).hexdigest(),
                mutated_sha256=hashlib.sha256(expected).hexdigest(),kind='production-layout' if path.startswith('element/') else 'production-api-adapter-misuse')
            require(candidate['mutation']==descriptor,'source mutation descriptor')
        require(safe_file(out,'build-source/'+path).read_bytes()==expected,'candidate source: '+path)
    expected={};packages=set(PACKAGES)
    for path,metadata in entries(core_source,record['profile']['core_commit']).items():
        name=Path(path)
        if str(name.parent) in packages and (name.name=='moon.pkg' or name.suffix=='.mbt' and not name.name.endswith(('_test.mbt','_wbtest.mbt'))):
            require(metadata.startswith('100644 blob '),'core source mode')
            data=git(core_source,'show',record['profile']['core_commit']+':'+path)
            expected[path]={'origin':'core','path':path,'sha256':hashlib.sha256(data).hexdigest(),'blob':metadata.split()[2]}
            check_input(path,data)
    for name in ('main.mbt','noop_metrics.mbt','moon.pkg'):
        path='adapters/measured_anchor_moonbit/'+name;commit=record['sources']['pair']['commit']
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
        intervals.append(process_ok(info['version'],[info['resolved_path'],'-v' if tool=='moonc' else '--version'],source))
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
    require(candidate['executable']=={'sha256':digest(safe_file(out,'probe.js')),'size':safe_file(out,'probe.js').stat().st_size},'executable hash binding')
    raw=load(safe_file(out,'raw.stdout'));require(raw['run_token']==token and raw['input']==fixture,'candidate raw input/session')
    return raw,candidate


def verify_bundle(directory,*,pair_source,fixture_source,core_source,upstream_source,pair_commit,pair_tree,
                  repository,run_id,run_attempt,recorded_execution_root):
    directory=Path(directory);record=load(safe_file(directory,'manifest.json'))
    profile=load_profile(Path(pair_source)/'diagnostics/measured_anchor_pair/profile.json')
    expected={'pair':{'commit':pair_commit,'tree':pair_tree},
        'fixture':{'commit':profile['fixture_commit'],'tree':profile['fixture_tree']},
        'baseline':{'commit':profile['integration_baseline_commit'],'tree':profile['integration_baseline_tree']},
        'core':{'commit':profile['core_commit'],'tree':profile['core_tree']},'upstream':{'commit':UPSTREAM,'tree':UPSTREAM_TREE}}
    require(json_same(record['profile'],profile) and json_same(record['sources'],expected),'external source/profile identities')
    validate_pair(pair_source,fixture_source,profile,pair_commit,pair_tree)
    validate_source(core_source,profile['core_commit'],profile['core_tree']);validate_source(upstream_source,UPSTREAM,UPSTREAM_TREE)
    require(repository=='gpui-mbt/gpui-conformance' and re.fullmatch('[1-9][0-9]*',run_id) and re.fullmatch('[1-9][0-9]*',run_attempt),'external session')
    session={'GITHUB_REPOSITORY':repository,'GITHUB_RUN_ID':run_id,'GITHUB_RUN_ATTEMPT':run_attempt,'GITHUB_SHA':pair_commit,'GITHUB_JOB':'actual-measured-anchor-pair'}
    require(record['session']==session,'external Actions identity; no historical spoof')
    require(type(record['schema_version']) is int and record['schema_version']==1 and record['status'] in ('executed','executed_strict_mismatch') and record['source_unchanged'] is True,'completed evidence status')
    token=record['run_token'];require(isinstance(token,str) and re.fullmatch('[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}',token),'fresh UUID token')
    root=Path(recorded_execution_root);require(root.is_absolute() and '..' not in root.parts and str(root)==record['execution_root'],'recorded execution root')
    require(record['comparison_spec_sha256']==SPEC_SHA256,'preexecution frozen spec')
    check_inventory(directory,record)
    require(sum(v['size'] for v in record['files'].values())<=profile['evidence_expansion_cap'],'evidence cap')
    require({p.name for p in directory.iterdir()}=={'manifest.json','pair','rust','candidate','controls','comparison.json','controls.json'},'exact bundle roots')
    require(set(inventory(directory/'pair'))==set(ADDITIONS),'pair source inventory')
    source_bytes(directory,'pair/',pair_source,pair_commit,ADDITIONS)
    rust_expected={'commit':pair_commit,'tree':pair_tree,'repository':repository,'run_id':run_id,'run_attempt':run_attempt}
    raw,fixture,rust=verify_rust(directory/'rust',fixture_source,upstream_source,pair_source,profile,rust_expected,root/'rust')
    require(record['rust']==rust and rust['run_token']==token,'Rust sidecar/session')
    candidate,candidate_manifest=verify_candidate(directory,record,core_source,pair_source,token,root,fixture)
    comparator=module(Path(pair_source)/'diagnostics/measured_anchor_pair/compare.py','paired_comparator')
    result=comparator.compare(raw,candidate,fixture,token)
    require(json_same(load(safe_file(directory,'comparison.json')),result),'recomputed strict comparison')
    require(record['strict_match'] is result['strict_match'] and record['status']==('executed' if result['strict_match'] else 'executed_strict_mismatch'),'strict failure preservation')
    controls_module=module(Path(pair_source)/'diagnostics/measured_anchor_pair/run_controls.py','paired_controls')
    start,finish=[datetime.fromisoformat(record[k]) for k in ('started_at','finished_at')]
    require(start.tzinfo is not None and finish.tzinfo is not None and start<=finish,'bundle chronology')
    rust_start=datetime.fromisoformat(rust['resolve-rustc']['started_at']);rust_end=datetime.fromisoformat(rust['execution']['finished_at'])
    candidate_start=datetime.fromisoformat(candidate_manifest['toolchain']['moon']['version']['started_at']);previous_end=datetime.fromisoformat(candidate_manifest['execution']['finished_at'])
    require(start<=rust_start<=rust_end<=candidate_start<=previous_end<=finish,'Rust then core chronology')
    outcomes=[]
    for name in controls_module.NAMES:
        control,manifest=verify_candidate(directory,record,core_source,pair_source,token,root,fixture,relative='controls/'+name,mutation=name)
        first=datetime.fromisoformat(manifest['toolchain']['moon']['version']['started_at']);last=datetime.fromisoformat(manifest['execution']['finished_at'])
        require(previous_end<=first<=last<=finish,'control chronology');previous_end=last
        compared=comparator.compare(raw,control,fixture,token)
        require(json_same(load(safe_file(directory,'controls/'+name+'/comparison.json')),compared),'control comparison')
        outcome=comparator.evaluate_control(name,result,compared,candidate,control,fixture,
            execution={'build_returncode':manifest['build']['returncode'],'execution_returncode':manifest['execution']['returncode']})
        require(outcome.get('killed') is True,'compiled control-specific additional violation required')
        outcomes.append(outcome)
    require(json_same(record['controls'],outcomes) and json_same(load(safe_file(directory,'controls.json')),outcomes),'recomputed control witnesses')
    require({p.name for p in (directory/'controls').iterdir()}==set(controls_module.NAMES),'exact control coverage')
    return {'execution_authenticated':False,'run_attestation':{'status':'external_git_and_ci_session_bound','sources':expected,
        'repository':repository,'run_id':run_id,'run_attempt':run_attempt,
        'limitation':'Review original CI logs and original artifact provenance. Self-reported process records are not cryptographic execution proof.'},
        'strict_match':result['strict_match'],'comparison':result,'controls':outcomes}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path)
    for name in ('pair-source','fixture-source','core-source','upstream-source','pair-commit','pair-tree','repository','run-id','run-attempt','recorded-execution-root'):
        parser.add_argument('--'+name,required=True)
    print(json.dumps(verify_bundle(**vars(parser.parse_args())),indent=2))


if __name__=='__main__':main()
