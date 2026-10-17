"""Dedicated fresh actual Rust / production MoonBit pairing, CI only."""
import argparse
import json
import os
from pathlib import Path
import shutil
import uuid

from run_rust import (CORE, CORE_TREE, ORACLE, ORACLE_TREE, UPSTREAM, UPSTREAM_TREE,
    digest, execute, git, inventory, load, now, require, run_rust, save,
    snapshot_source, validate_source)
from compare import compare

HERE = Path(__file__).resolve().parent
PAIR = HERE.parents[1]
PACKAGES = ['primitives', 'layout', 'scene', 'element', 'controls/button']
MODULE = 'name = "f4ah6o/gpui"\nversion = "0.0.0"\n'
ADDITIONS = [
    'adapters/popover_outside_moonbit/main.mbt', 'adapters/popover_outside_moonbit/moon.pkg',
    *['diagnostics/popover_outside_pair/'+name for name in
      ('profile.json','run.py','run_rust.py','compare.py','run_controls.py','evidence.py','README.md')],
    'tests/test_outside_pointer_pair.py', '.github/workflows/popover-outside-pair.yml']


def blobs(source, revision='HEAD'):
    result = {}
    for row in git(source, 'ls-tree', '-rz', revision).split(b'\0'):
        if not row: continue
        metadata, path = row.split(b'\t',1)
        mode, kind, blob = metadata.decode().split()
        require(kind=='blob','source tree entry must be a blob')
        result[path.decode()] = blob
    return result


def validate_pair(pair, oracle):
    baseline, current = blobs(oracle), blobs(pair)
    require(len(baseline)==734,'oracle source count')
    for source in (oracle,pair):
        entries={row.split(b'\t',1)[1].decode():row.split(b'\t',1)[0] for row in git(source,'ls-tree','-rz','HEAD').split(b'\0') if row}
        require(all(entries[path].startswith(b'100644 blob ') for path in baseline),'baseline source mode changed')
    require(all(entries[path].startswith(b'100644 blob ') for path in ADDITIONS if path in entries),'pair source mode')
    require(all(current.get(path)==sha for path,sha in baseline.items()),'original source changed')
    require(set(current)-set(baseline)==set(ADDITIONS),'pair additions')
    require(not git(pair,'status','--porcelain','--untracked-files=all').strip(),'dirty pair source')
    git(pair,'merge-base','--is-ancestor',ORACLE,'HEAD')
    return {'commit':git(pair,'rev-parse','HEAD').decode().strip(),
            'tree':git(pair,'rev-parse','HEAD^{tree}').decode().strip()}


def production_paths(core):
    return sorted(path for path in blobs(core) if
        str(Path(path).parent) in PACKAGES and
        (path.endswith('/moon.pkg') or (path.endswith('.mbt') and
         not path.endswith(('_test.mbt','_wbtest.mbt')))))


def require_selected_source(source, original):
    require(git(source,'ls-tree','HEAD','--',original).startswith(b'100644 blob '), 'selected input must be regular source')
    require(not (Path(source)/original).is_symlink(),'selected input symlink')


def version_command(name, resolved_path):
    require(name in ('moon','moonc','node'),'known tool version command')
    return [str(resolved_path), '-v' if name=='moonc' else '--version']


def require_success(record, label):
    require(type(record.get('returncode')) is int and record['returncode']==0 and
            record.get('timed_out') is False and record.get('resource_floor_breached') is False, label)


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
        inputs += [('probe/'+name,pair,'adapters/popover_outside_moonbit/'+name,'pair',
                    pair_blobs['adapters/popover_outside_moonbit/'+name]) for name in ('main.mbt','moon.pkg')]
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
        manifest['status']='executed'
    finally:
        manifest['finished_at']=now()
        manifest['files']=inventory(out)
        save(out/'manifest.json',manifest)
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('core-source','oracle-source','upstream-source','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    pair=PAIR.resolve();core=args.core_source.resolve();oracle=args.oracle_source.resolve();upstream=args.upstream_source.resolve()
    out=args.output.resolve()
    require(out.parent==pair/'_build' and not out.exists(),'fresh ignored output directory')
    require(os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('GITHUB_JOB')=='actual-popover-outside-pair','dedicated CI required')
    validate_source(core,CORE,CORE_TREE);validate_source(oracle,ORACLE,ORACLE_TREE);validate_source(upstream,UPSTREAM,UPSTREAM_TREE)
    pair_identity=validate_pair(pair,oracle)
    require(os.environ['GITHUB_SHA']==pair_identity['commit'],'CI pair source')
    out.mkdir(parents=True)
    token=str(uuid.uuid4())
    manifest={'schema_version':1,'status':'preflight','run_token':token,'execution_root':str(out),
        'started_at':now(),'sources':{'pair':pair_identity,'core':{'commit':CORE,'tree':CORE_TREE},
        'oracle':{'commit':ORACLE,'tree':ORACLE_TREE},'upstream':{'commit':UPSTREAM,'tree':UPSTREAM_TREE}},
        'session':{'repository':os.environ['GITHUB_REPOSITORY'],'run_id':os.environ['GITHUB_RUN_ID'],
        'run_attempt':os.environ['GITHUB_RUN_ATTEMPT'],'sha':os.environ['GITHUB_SHA'],'job':os.environ['GITHUB_JOB']},
        'source_unchanged':False}
    try:
        snapshot_source(pair,out/'pair',ADDITIONS)
        fixture=load(oracle/'diagnostics/popover_outside/scenarios.json')
        manifest['rust']=run_rust(pair,oracle,upstream,out/'rust',token)
        manifest['candidate']=compile_candidate(pair,core,out/'candidate',fixture,token)
        rust=load(out/'rust/raw.stdout')
        report=compare(rust,load(out/'candidate/raw.stdout'),oracle,fixture,token)
        save(out/'comparison.json',report)
        require(report['status']=='match','ordinary semantic mismatch')
        from run_controls import run_controls
        manifest['controls']=run_controls(pair,core,oracle,out,fixture,token,rust)
        validate_source(core,CORE,CORE_TREE);validate_source(oracle,ORACLE,ORACLE_TREE);validate_source(upstream,UPSTREAM,UPSTREAM_TREE)
        require(validate_pair(pair,oracle)==pair_identity,'pair source drift')
        manifest['source_unchanged']=True
        require(sum(x['size'] for x in inventory(out).values())<=512*1024**2,'512MiB evidence expansion ceiling')
        manifest['status']='executed'
    finally:
        manifest['finished_at']=now();manifest['files']=inventory(out)
        save(out/'manifest.json',manifest)


if __name__=='__main__':main()
