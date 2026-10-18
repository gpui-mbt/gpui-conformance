"""Fresh source-bound actual Rust/core pairing. Unbound profiles cannot execute."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import uuid
from run_rust import (UPSTREAM,UPSTREAM_TREE,FIXTURE_PATHS,digest,execute,git,inventory,
    json_same,load,now,require,run_rust,safe_file,save,snapshot_source,validate_source)

HERE=Path(__file__).resolve().parent
PAIR=HERE.parents[1]
PROFILE=HERE/'profile.json'
SPEC_SHA256='dba66cc5599a99e4f74e58ea7bec0eff089e08bb42da663bf6ef1050cdc551eb'
PACKAGES=['primitives','layout','scene','element']
MODULE='name = "f4ah6o/gpui"\nversion = "0.0.0"\n'
ADDITIONS=[
    *['adapters/measured_anchor_moonbit/'+p for p in ('main.mbt','noop_metrics.mbt','moon.pkg')],
    *['diagnostics/measured_anchor_pair/'+p for p in ('comparison_spec.json','profile.json','run.py','run_rust.py','compare.py','run_controls.py','evidence.py','README.md')],
    'tests/test_measured_anchor_pair.py','tests/test_measured_anchor_metrics.py',
    '.github/workflows/measured-anchor-pair.yml']


def load_profile(path=PROFILE,require_bound=True):
    p=load(path)
    require(type(p.get('schema_version')) is int and p['schema_version']==1,'profile schema')
    require(p['additions']==ADDITIONS and p['core_packages']==PACKAGES,'exact source paths')
    require(p['fixture_commit']=='4bf568614f9a5707855a441314eec8080adbc8a7' and p['fixture_tree']=='02f135a1b1dd34add72e200813a1bdcba6f7f5ef','immutable S fixture')
    require(p['integration_baseline_commit']=='1afff3fc1540657cd6060c7e7bb29be0030ad66e' and p['integration_baseline_tree']=='492373682d7af423e27833d3582ad43109dd5a4a','merged B baseline')
    require(p['upstream_commit']==UPSTREAM and p['upstream_tree']==UPSTREAM_TREE,'upstream identity')
    require(p['comparison_spec_sha256']==SPEC_SHA256,'frozen comparison identity')
    require(p['source_cap']==2*1024**2 and p['evidence_expansion_cap']==512*1024**2 and p['artifact_zip_cap']==128*1024**2,'resource ceilings')
    require(set(p['fixture_files'])==set(FIXTURE_PATHS),'immutable fixture inventory')
    if p['status']=='draft_unbound' and not require_bound:
        require(p['core_commit'] is None and p['core_tree'] is None,'unbound core identity')
    else:
        require(p['status']=='bound' and all(isinstance(p[k],str) and re.fullmatch('[0-9a-f]{40}',p[k]) for k in ('core_commit','core_tree')),'unbound profile cannot execute or publish')
    return p


def entries(source,revision):
    result={}
    for row in git(source,'ls-tree','-rz',revision).split(b'\0'):
        if row:
            metadata,path=row.split(b'\t',1);result[path.decode()]=metadata.decode()
    return result


def blobs(source,revision='HEAD'):
    return {p:v.split()[2] for p,v in entries(source,revision).items()}


def validate_pair(pair,fixture,profile,commit,tree):
    require(all(isinstance(v,str) and re.fullmatch('[0-9a-f]{40}',v) for v in (commit,tree)),'exact R identity')
    require(commit not in (profile['fixture_commit'],profile['integration_baseline_commit']),'S, B and R must be distinct')
    validate_source(pair,commit,tree);validate_source(fixture,profile['fixture_commit'],profile['fixture_tree'])
    baseline=profile['integration_baseline_commit']
    require(git(pair,'rev-parse',baseline+'^{tree}').decode().strip()==profile['integration_baseline_tree'],'B tree identity')
    git(pair,'merge-base','--is-ancestor',profile['fixture_commit'],baseline)
    git(pair,'merge-base','--is-ancestor',baseline,commit)
    before,after=entries(pair,baseline),entries(pair,commit)
    require(all(after.get(p)==v for p,v in before.items()),'existing baseline content/modes changed')
    require(set(after)-set(before)==set(ADDITIONS),'exact 14 additive source paths')
    require(all(after[p].startswith('100644 blob ') for p in ADDITIONS),'regular additive sources')
    require(sum(len(git(pair,'show',commit+':'+p)) for p in ADDITIONS)<=profile['source_cap'],'source cap')
    for p,meta in profile['fixture_files'].items():
        b=git(fixture,'show',profile['fixture_commit']+':'+p)
        require(meta=={'sha256':hashlib.sha256(b).hexdigest(),'size':len(b)},'fixture source pin')
        require(safe_file(fixture,p).read_bytes()==b==safe_file(pair,p).read_bytes(),'immutable fixture bytes')
    require(digest(safe_file(pair,'diagnostics/measured_anchor_pair/comparison_spec.json'))==SPEC_SHA256,'frozen specification bytes')
    require(json_same(load(safe_file(pair,'diagnostics/measured_anchor_pair/profile.json')),profile),'profile bytes')
    return {'commit':commit,'tree':tree}


def production_paths(core):
    return sorted(p for p in blobs(core) if str(Path(p).parent) in PACKAGES and
        (p.endswith('/moon.pkg') or (p.endswith('.mbt') and not p.endswith(('_test.mbt','_wbtest.mbt')))))


def require_selected_source(source,original):
    require(git(source,'ls-tree','HEAD','--',original).startswith(b'100644 blob '),'selected regular source')
    safe_file(source,original)


def version_command(name,resolved_path):
    require(name in ('moon','moonc','node'),'known tool')
    return [str(resolved_path),'-v' if name=='moonc' else '--version']


def require_success(record,label):
    require(type(record.get('returncode')) is int and record['returncode']==0 and record['timed_out'] is False and record['resource_floor_breached'] is False,label)


def compile_candidate(pair_source, core_source, out, fixture, token, mutation=None, shared_toolchain=None):
    pair,core,out = map(lambda p:Path(p).resolve(),(pair_source,core_source,out))
    out.mkdir(parents=True,exist_ok=False)
    stage = out/'build-source'
    stage.mkdir()
    manifest = {'schema_version':1,'status':'preflight','execution_root':str(out),
        'module':MODULE,'inputs':{},'mutation':mutation,'shared_toolchain':shared_toolchain,
        'toolchain':{},'environment':{},'started_at':now()}
    try:
        core_blobs,pair_blobs = blobs(core),blobs(pair)
        inputs = [(path,core,path,'core',core_blobs[path]) for path in production_paths(core)]
        inputs += [('probe/'+name,pair,'adapters/measured_anchor_moonbit/'+name,'pair',
                    pair_blobs['adapters/measured_anchor_moonbit/'+name]) for name in ('main.mbt','noop_metrics.mbt','moon.pkg')]
        for target,source,original,origin,blob in inputs:
            require_selected_source(source,original)
            path = stage/target
            path.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source/original,path)
            manifest['inputs'][target] = {'origin':origin,'path':original,'sha256':digest(path),'blob':blob}
        (stage/'moon.mod').write_text(MODULE)
        if mutation is not None:
            from run_controls import apply_mutation
            manifest['mutation']=apply_mutation(stage,mutation)
        require(shared_toolchain in (None,'candidate'),'shared toolchain reference')
        shared = out
        if shared_toolchain is not None:
            require(out.parent.name=='controls','fixed shared toolchain location')
            shared = out.parents[1]/'candidate'
            require(shared.is_dir() and not shared.is_symlink(),'ordinary candidate toolchain')
        else:
            (out/'tools').mkdir()
            (out/'toolchain-inputs/js-bundle').mkdir(parents=True)
        env = os.environ.copy()
        for key in ('NODE_OPTIONS','NODE_PATH'):
            env.pop(key,None)
        moon = shutil.which('moon');moonc = shutil.which('moonc');node = shutil.which('node')
        require(all((moon,moonc,node)),'installed MoonBit and Node toolchains required')
        moon_home = str(Path(moon).resolve().parent.parent)
        require(Path(moon_home,'lib','core').is_dir(),'MoonBit standard library root')
        manifest['environment'] = {'MOON_HOME':moon_home,'GPUI_SCENARIOS':json.dumps(fixture,separators=(',',':')),
            'GPUI_RUN_TOKEN':token,'NODE_OPTIONS':None,'NODE_PATH':None}
        env.update({k:v for k,v in manifest['environment'].items() if v is not None})
        for name,command in (('moon',moon),('moonc',moonc),('node',node)):
            path = Path(command).resolve()
            if shared_toolchain is None:
                shutil.copy2(path,out/'tools'/name)
            require(digest(shared/'tools'/name)==digest(path),'tool hash binding')
            version = execute(version_command(name,path),out,name+'-version',env,cwd=stage)
            manifest['toolchain'][name] = {'command_path':command,'resolved_path':str(path),
                'sha256':digest(path),'version':version}
            require_success(version,name+' version')
        for path in sorted(Path(moon_home,'lib','core','_build','js','release','bundle').rglob('*')):
            if not path.is_file() or path.suffix not in ('.core','.mi'): continue
            relative = path.relative_to(Path(moon_home,'lib','core','_build','js','release','bundle'))
            if shared_toolchain is None:
                dest = out/'toolchain-inputs/js-bundle'/relative
                dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(path,dest)
            require(digest(path)==digest(shared/'toolchain-inputs/js-bundle'/relative),'standard library hash')
        require(any((shared/'toolchain-inputs/js-bundle').rglob('*.core')),'standard library inputs')
        manifest['status']='build_plan_failed'
        command = [str(Path(moon).resolve()),'build','--target','js','--debug']
        manifest['build_plan']=execute(command+['--dry-run'],out,'build-plan',env,cwd=stage)
        require_success(manifest['build_plan'],'candidate build plan')
        manifest['status']='build_failed'
        manifest['build']=execute(command,out,'build',env,timeout=300,cwd=stage)
        require_success(manifest['build'],'candidate build')
        for name,tool in manifest['toolchain'].items():
            require(digest(tool['resolved_path'])==tool['sha256']==digest(shared/'tools'/name),'toolchain changed')
        for path in (shared/'toolchain-inputs/js-bundle').rglob('*'):
            if path.is_file():
                require(digest(path)==digest(Path(moon_home,'lib','core','_build','js','release','bundle')/path.relative_to(shared/'toolchain-inputs/js-bundle')),'stdlib changed')
        shutil.copy2(stage/'_build/js/debug/build/probe/probe.js',out/'probe.js')
        manifest['status']='execution_failed'
        manifest['execution']=execute([str(Path(node).resolve()),str(out/'probe.js')],out,'raw',env,cwd=stage)
        require_success(manifest['execution'],'candidate execution')
        manifest['executable']={'sha256':digest(out/'probe.js'),'size':(out/'probe.js').stat().st_size}
        require(digest(stage/'_build/js/debug/build/probe/probe.js')==manifest['executable']['sha256'],'emitted executable binding')
        manifest['status']='executed'
    finally:
        manifest['finished_at']=now()
        manifest['files']=inventory(out)
        save(out/'manifest.json',manifest)
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('core-source','fixture-source','upstream-source','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    profile=load_profile() # Fail closed before creating files or resolving tools.
    pair=PAIR.resolve();core=args.core_source.resolve();fixture_source=args.fixture_source.resolve();upstream=args.upstream_source.resolve();out=args.output.resolve()
    require(out.parent==pair/'_build' and not out.exists(),'fresh ignored output')
    require(os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_OS')=='Linux' and os.environ.get('GITHUB_JOB')=='actual-measured-anchor-pair','dedicated real CI session')
    commit=git(pair,'rev-parse','HEAD').decode().strip();tree=git(pair,'rev-parse','HEAD^{tree}').decode().strip()
    identity=validate_pair(pair,fixture_source,profile,commit,tree)
    require(os.environ['GITHUB_SHA']==commit,'current R/session identity')
    validate_source(core,profile['core_commit'],profile['core_tree']);validate_source(upstream,UPSTREAM,UPSTREAM_TREE)
    for path,blob in profile['metrics_source_blobs'].items():
        require(blobs(upstream)[path]==blob,'pinned text metric source')
    out.mkdir(parents=True);token=str(uuid.uuid4())
    manifest={'schema_version':1,'status':'preflight','run_token':token,'execution_root':str(out),'started_at':now(),
        'profile':profile,'sources':{'pair':identity,'baseline':{'commit':profile['integration_baseline_commit'],'tree':profile['integration_baseline_tree']},
        'fixture':{'commit':profile['fixture_commit'],'tree':profile['fixture_tree']},'core':{'commit':profile['core_commit'],'tree':profile['core_tree']},'upstream':{'commit':UPSTREAM,'tree':UPSTREAM_TREE}},
        'session':{k:os.environ[k] for k in ('GITHUB_REPOSITORY','GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT','GITHUB_SHA','GITHUB_JOB')},'source_unchanged':False,
        'comparison_spec_sha256':digest(HERE/'comparison_spec.json')}
    try:
        snapshot_source(pair,out/'pair',ADDITIONS)
        fixture=load(fixture_source/'diagnostics/padded_text_anchor/scenarios.json')
        manifest['rust']=run_rust(pair,fixture_source,upstream,out/'rust',token,profile,identity)
        manifest['candidate']=compile_candidate(pair,core,out/'candidate',fixture,token)
        from compare import compare
        rust=load(out/'rust/raw.stdout');candidate=load(out/'candidate/raw.stdout')
        report=compare(rust,candidate,fixture,token);save(out/'comparison.json',report)
        # Run controls even if strict baseline parity fails. Red is never relabelled green.
        from run_controls import run_controls
        manifest['controls']=run_controls(pair,core,out,fixture,token,rust,candidate,report)
        validate_pair(pair,fixture_source,profile,commit,tree);validate_source(core,profile['core_commit'],profile['core_tree']);validate_source(upstream,UPSTREAM,UPSTREAM_TREE)
        manifest['source_unchanged']=True
        require(sum(x['size'] for x in inventory(out).values())<=profile['evidence_expansion_cap'],'evidence expansion ceiling')
        manifest['strict_match']=report['strict_match']
        manifest['status']='executed' if report['strict_match'] else 'executed_strict_mismatch'
    finally:
        manifest['finished_at']=now();manifest['files']=inventory(out);save(out/'manifest.json',manifest)
    require(manifest['strict_match'],'strict parity failed; complete evidence and controls retained')


if __name__=='__main__':main()
