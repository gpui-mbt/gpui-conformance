"""Build actual MoonBit production packages with retained compiler/runtime inputs."""
import os
from pathlib import Path
import shutil
from support import *
PACKAGES=['primitives','layout','scene','element']
MODULE='name = "f4ah6o/gpui"\nversion = "0.0.0"\n'
def entries(source,revision):
    result={}
    for row in git(source,'ls-tree','-rz',revision).split(b'\0'):
        if row:
            metadata,path=row.split(b'\t',1);result[path.decode()]=metadata.decode()
    return result


def blobs(source,revision='HEAD'):
    return {p:v.split()[2] for p,v in entries(source,revision).items()}


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
        inputs += [('probe/'+name,pair,'adapters/element_opacity_moonbit/'+name,'pair',
                    pair_blobs['adapters/element_opacity_moonbit/'+name]) for name in ('main.mbt','moon.pkg')]
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


