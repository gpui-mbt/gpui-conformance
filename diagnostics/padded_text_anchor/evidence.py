"""Reopen source-bound Rust evidence; original CI logs remain required.
Source hashes and self-reported process records are not cryptographic execution proof.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import importlib.util
_spec=importlib.util.spec_from_file_location('padded_anchor_execution_helpers',Path(__file__).with_name('run.py'))
_run=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_run)
for _name in ('PROFILE','UPSTREAM','UPSTREAM_TREE','FLOOR','FIXTURE_PATHS','RUNNER_PATHS',
              'UPSTREAM_PATHS','STAGED_PATHS','UNSET','digest','git','inventory','load','require',
              'safe_file','validate_source','validate_suite','rust_build_graph','staged_inventory',
              'load_profile','module','json_same'):
    globals()[_name]=getattr(_run,_name)

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



def verify_execution(directory,fixture_source,upstream_source,runner_source,profile,expected,root):
    directory=Path(directory);root=Path(root)
    require(root.is_absolute() and '..' not in root.parts and root.parent.name=='_build','recorded evidence root')
    record=load(safe_file(directory,'manifest.json'));check_inventory(directory,record)
    require(type(record['schema_version']) is int and record['schema_version']==1 and record['status']=='executed','successful Rust status')
    token=record['run_token']
    require(isinstance(token,str) and re.fullmatch('[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}',token),'UUID run token')
    require(record['source_unchanged'] is True and json_same(record['profile'],profile),'immutable profile/source')
    require(record['runner']=={'commit':expected['commit'],'tree':expected['tree']},'external runner identity')
    require(record['session']=={'GITHUB_REPOSITORY':expected['repository'],'GITHUB_RUN_ID':expected['run_id'],
        'GITHUB_RUN_ATTEMPT':expected['run_attempt'],'GITHUB_SHA':expected['commit'],'GITHUB_JOB':'actual-padded-text-anchor'},'external CI session')
    required={'probe','toolchain-inputs.json','trace-shape.json'}|{'fixture/'+p for p in FIXTURE_PATHS}|{'runner/'+p for p in RUNNER_PATHS}|{'upstream/'+p for p in UPSTREAM_PATHS}|{'staged/'+p for p in STAGED_PATHS}
    stems=['resolve-rustc','resolve-cargo','rustc','cargo','sysroot','target-libdir','build','raw']
    required|={stem+'.'+suffix for stem in stems for suffix in ('stdout','stderr')}
    require(set(record['files'])==required,'exact successful evidence inventory')
    source_bytes(directory,'fixture/',fixture_source,profile['fixture_commit'],FIXTURE_PATHS)
    source_bytes(directory,'runner/',runner_source,expected['commit'],RUNNER_PATHS)
    source_bytes(directory,'upstream/',upstream_source,UPSTREAM,UPSTREAM_PATHS)
    require(record['execution_root']==str(root),'recorded execution root')
    build=Path(record['build_root']);stage=build/'adapter';cwd=root.parent.parent
    require(build==root.parent/('padded-anchor-build-'+token),'build root token binding')
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
    return {'status':'source_and_session_bound','execution_authenticated':False,
            'requires_original_ci_log_review':True,'fixture_commit':profile['fixture_commit'],
            'runner_commit':expected['commit'],'variant_count':len(raw['variants']),
            'observed_numeric_goldens':None,'attachment_reference_hypothesis_confirmed':None,
            'font_parity':False,'unchanged_example_parity':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence',type=Path)
    for name in ('runner-source','fixture-source','upstream-source'):
        parser.add_argument('--'+name,type=Path,required=True)
    for name in ('runner-commit','runner-tree','repository','run-id','run-attempt','recorded-execution-root'):
        parser.add_argument('--'+name,required=True)
    args=parser.parse_args()
    profile=load_profile(args.runner_source/'diagnostics/padded_text_anchor/execution_profile.json')
    require(args.repository=='gpui-mbt/gpui-conformance' and re.fullmatch('[1-9][0-9]*',args.run_id) and re.fullmatch('[1-9][0-9]*',args.run_attempt),'external repository/session identifiers')
    validate_suite(args.runner_source,args.fixture_source,profile,args.runner_commit,args.runner_tree)
    validate_source(args.upstream_source,UPSTREAM,UPSTREAM_TREE)
    expected={'commit':args.runner_commit,'tree':args.runner_tree,'repository':args.repository,'run_id':args.run_id,'run_attempt':args.run_attempt}
    print(json.dumps(verify_execution(args.evidence,args.fixture_source,args.upstream_source,args.runner_source,profile,expected,Path(args.recorded_execution_root)),indent=2))


if __name__=='__main__':main()
