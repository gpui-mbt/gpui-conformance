"""Fail-closed retained process/build provenance for the bounded opacity pair."""
import argparse
import shlex
from datetime import datetime
from pathlib import Path
from support import digest, inventory, load, require, safe_file, staged_inventory, rust_build_graph, verify_git_proof
from compare import compare
from candidate import require_success
from run_controls import MUTATIONS

HERE=Path(__file__).resolve().parent

def verify_runtime_tools(out, toolchain):
    require(set(toolchain)=={'moon','moonc','node'},'complete candidate compiler/runtime')
    for name,tool in toolchain.items():
        require(digest(safe_file(out,'tools/'+name))==tool['sha256'],'missing/tampered compiler/runtime')


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



def verify(out):
    out=Path(out);m=load(safe_file(out,'manifest.json'));profile=load(HERE/'profile.json')
    require(profile['status']=='bound','unbound profile')
    require(m['profile']==profile,'stale candidate/profile')
    require(m['status'] in ('executed','executed_strict_mismatch') and m['source_unchanged'] is True,'unfinished execution')
    require(m['suite']['commit']==m['session']['GITHUB_SHA'],'suite/session identity')
    files=inventory(out)
    # Verification is generated after the manifest inventory, and is not an input.
    files.pop('verification.json',None)
    require(files==m['files'],'retained files changed or missing')
    for p in profile['files']:
        require(digest(safe_file(out,'suite/'+p))==digest(HERE.parents[1]/p),'stale fixture/checker source')
    require(digest(out/'suite/diagnostics/element_opacity_pair/policy.json')==profile['policy_sha256'],'frozen source policy')
    require(digest(out/'suite/diagnostics/element_opacity_pair/scenarios.json')==profile['scenarios_sha256'],'frozen corpus')
    policy=load(out/'suite/diagnostics/element_opacity_pair/policy.json')
    import hashlib
    def blob(path):
        b=path.read_bytes();return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
    for p,sha in policy['source_blobs'].items(): require(blob(safe_file(out,'upstream/'+p))==sha,'upstream source blob')
    r=load(out/'rust/manifest.json');c=load(out/'candidate/manifest.json')
    original=Path(m['execution_root']);require(original.is_absolute(),'execution root')
    for name,record in [('rust',r),('candidate',c)]:
        require(record==m[name] and record['status']=='executed','build/run manifest identity')
        for kind in ('build','execution'):
            process=record[kind];require_success(process,name+' '+kind)
            require(type(process['pid']) is int and process['pid']>0 and process['started_at']<=process['finished_at'],'process identity/timing')
            for suffix in ('stdout','stderr'):safe_file(out,name+'/'+('raw' if kind=='execution' else 'build')+'.'+suffix)
        require(record['build']['finished_at']<=record['execution']['started_at'],'build before execution')
    require(r['execution']['pid']!=c['execution']['pid'],'distinct child executions')
    require(r['run_token']==m['tokens']['rust'],'Rust challenge binding')
    require(c['environment']['GPUI_RUN_TOKEN']==m['tokens']['candidate'],'MoonBit challenge binding')
    require(r['execution']['command']==[str(original/'rust/probe')],'actual retained Rust program')
    require(r['executable']=={'sha256':digest(out/'rust/probe'),'size':(out/'rust/probe').stat().st_size},'Rust executable bytes')
    upstream=Path(r['upstream_source_path']);require(upstream.is_absolute(),'Rust upstream source path')
    original_manifest=(out/'suite/adapters/element_opacity_rust/Cargo.toml').read_text()
    placeholder='"../../../zed-source/crates/gpui"'
    require(original_manifest.count(placeholder)==1,'single reviewed dependency placeholder')
    import json
    expected_manifest=original_manifest.replace(placeholder,json.dumps(str(upstream/'crates/gpui')))
    require((out/'rust/staged/Cargo.toml').read_text()==expected_manifest,'exact GPUI dependency relocation')
    expected_build_root=original.parent/('opacity-rust-build-'+m['tokens']['rust'])
    require(r['build_root']==str(expected_build_root),'Rust isolated build root')
    require(r['build']['command']==[r['tools']['cargo']['path'],'build','--locked','-vv','--message-format=json-render-diagnostics','--manifest-path',str(expected_build_root/'adapter/Cargo.toml')],'Rust build command')
    require(r['build']['cwd']==r['execution']['cwd']==str(original.parent.parent),'Rust build/runtime cwd')
    gpui_artifacts=[]
    for line in (out/'rust/build.stdout').read_text().splitlines():
        if line.startswith('{'):
            message=json.loads(line)
            if message.get('reason')=='compiler-artifact' and message.get('target',{}).get('name')=='gpui':gpui_artifacts.append(message)
    require(len(gpui_artifacts)==1 and gpui_artifacts[0]['manifest_path']==str(upstream/'crates/gpui/Cargo.toml') and gpui_artifacts[0]['target']['src_path']==str(upstream/'crates/gpui/src/gpui.rs'),'actual pinned GPUI Cargo artifact source')
    graph=rust_build_graph(r,(out/'rust/build.stdout').read_text(),(out/'rust/build.stderr').read_text())
    require(graph==r['graph'],'actual compiler artifact graph')
    for path in ('Cargo.lock','src/main.rs'):
        require(digest(out/'rust/staged'/path)==digest(out/'suite/adapters/element_opacity_rust'/path),'Rust source binding')
    require(c['execution']['command']==[c['toolchain']['node']['resolved_path'],str(original/'candidate/probe.js')],'Node runtime command')
    expected_build=[c['toolchain']['moon']['resolved_path'],'build','--target','js','--debug']
    require(c['build']['command']==expected_build and c['build_plan']['command']==expected_build+['--dry-run'],'MoonBit actual build commands')
    require(c['build']['cwd']==c['build_plan']['cwd']==c['execution']['cwd']==str(original/'candidate/build-source'),'MoonBit compiler/runtime cwd')
    require_success(c['build_plan'],'MoonBit build plan')
    verify_js_plan(out/'candidate',c,c['inputs'])
    require(c['executable']=={'sha256':digest(out/'candidate/probe.js'),'size':(out/'candidate/probe.js').stat().st_size},'MoonBit executable bytes')
    require(digest(out/'candidate/build-source/_build/js/debug/build/probe/probe.js')==digest(out/'candidate/probe.js'),'MoonBit emitted artifact')
    verify_runtime_tools(out/'candidate',c['toolchain'])
    verify_git_proof(out/'core-source-proof',profile['core_commit'],profile['core_tree'],
        {meta['path']:meta['blob'] for meta in c['inputs'].values() if meta['origin']=='core'})
    for path,meta in c['inputs'].items():
        source=safe_file(out,'candidate/build-source/'+path)
        require(digest(source)==meta['sha256'] and blob(source)==meta['blob'],'compiled source provenance')
        if meta['origin']=='pair':require(digest(source)==digest(out/'suite'/meta['path']),'adapter compiler input binding')
    require(any(p.endswith('.core') for p in c['files'] if p.startswith('toolchain-inputs/js-bundle/')),'retained MoonBit stdlib')
    require([row['name'] for row in m['controls']]==list(MUTATIONS),'complete executed negative controls')
    for row in m['controls']:
        root=out/'controls'/row['name'];record=load(safe_file(root,'manifest.json'))
        require(record==row['manifest'] and record['status']=='executed','actual negative execution manifest')
        for kind in ('build','execution'): require_success(record[kind],'negative '+kind)
        require(record['shared_toolchain']=='candidate','control runtime identity')
        require(record['inputs']==c['inputs'],'control must retain identical input inventory')
        require(record['environment']['MOON_HOME']==c['environment']['MOON_HOME'],'shared control standard library root')
        require(set(record['toolchain'])==set(c['toolchain']),'shared control tool inventory')
        for tool,metadata in record['toolchain'].items():
            require({k:v for k,v in metadata.items() if k!='version'}=={k:v for k,v in c['toolchain'][tool].items() if k!='version'},'shared compiler/runtime metadata')
            require_success(metadata['version'],'control tool version')
            require((root/(tool+'-version.stdout')).read_bytes()==(out/'candidate'/(tool+'-version.stdout')).read_bytes(),'shared tool version output')
        require(record['execution']['command']==[c['toolchain']['node']['resolved_path'],str(original/'controls'/row['name']/'probe.js')],'control Node execution command')
        require(record['build_plan']['cwd']==str(original/'controls'/row['name']/'build-source'),'control build-plan cwd')
        require_success(record['build_plan'],'control build plan')
        previous=None
        for phase in ('build_plan','build','execution'):
            process=record[phase]
            start,end=(datetime.fromisoformat(process[k]) for k in ('started_at','finished_at'))
            require(type(process['pid']) is int and process['pid']>0 and start.tzinfo is not None and end.tzinfo is not None and start<=end,'control process identity/chronology')
            require(previous is None or previous<=start,'control process sequence')
            previous=end
        for target,meta in record['inputs'].items():
            if target!='probe/main.mbt':
                source=safe_file(root,'build-source/'+target)
                require(digest(source)==meta['sha256'] and blob(source)==meta['blob'],'additional unapproved control source mutation')

        require(record['build']['command']==expected_build and record['build_plan']['command']==expected_build+['--dry-run'],'control compiler commands')
        require(record['build']['cwd']==record['execution']['cwd']==str(original/'controls'/row['name']/'build-source'),'control compiler/runtime cwd')
        verify_js_plan(root,record,record['inputs'],shared=out/'candidate')
        require(record['executable']['sha256']==digest(safe_file(root,'probe.js'))==digest(safe_file(root,'build-source/_build/js/debug/build/probe/probe.js')),'negative executable linkage')
        mutation=record['mutation'];old,new=MUTATIONS[row['name']]
        original_source=(out/'suite/adapters/element_opacity_moonbit/main.mbt').read_text()
        require(original_source.count(old)==1 and (root/'build-source/probe/main.mbt').read_text()==original_source.replace(old,new),'actual negative compiler source')
        require(mutation['before_sha256']==digest(out/'suite/adapters/element_opacity_moonbit/main.mbt') and mutation['after_sha256']==digest(root/'build-source/probe/main.mbt'),'mutation hashes')
        raw=load(root/'raw.stdout')
        require(raw['run_token']==row['token']==record['environment']['GPUI_RUN_TOKEN'] and raw['input']==load(HERE/'scenarios.json'),'negative challenge/input')
        try:
            negative=compare(load(out/'rust/raw.stdout'),raw,load(HERE/'scenarios.json'),{'rust':m['tokens']['rust'],'candidate':row['token']})
        except ValueError as error:
            require(str(error) in ('source opacity policy','raw/projected alpha binding','intrinsic alpha preserved'),'negative semantic rejection')
            negative={'strict_match':False,'semantic_rejection':str(error)}
        require(negative==row['comparison'] and negative['strict_match'] is False,'negative recomputation')
    report=compare(load(out/'rust/raw.stdout'),load(out/'candidate/raw.stdout'),load(HERE/'scenarios.json'),m['tokens'])
    require(report==load(out/'comparison.json'),'comparison recomputation')
    return {'schema_version':1,'execution_verified':True,'strict_match':report['strict_match'],'case_count':report['case_count'],
            'qualification':'bounded headless scene alpha/layout/mouse events; no pixels or full example port'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);args=p.parse_args()
    print(__import__('json').dumps(verify(args.output),indent=2))
