#!/usr/bin/env python3
"""Prepare/build bounded flex-basis adapters using existing read-only Rust dependencies.

No full Cargo build fallback exists. Uncommitted sources require explicit consent
and are copied from their recorded file-byte snapshot, never from git archive HEAD.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
from build_flex_justify import cached_rust
from run_flex_basis import ROOT, require, sha, source_identity, validate_pins


def snapshot_source(source, destination):
    destination.mkdir(parents=True, exist_ok=False)
    for relative,digest in source['files'].items():
        src=Path(source['path'])/relative
        require(sha(src)==digest, 'Source changed before snapshot: '+relative)
        target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src,target)
        require(sha(target)==digest, 'Copied source differs: '+relative)


def disable_flex_basis(moon):
    """Mutate the production resolver only; preserve its validation and adapter."""
    path = moon/'layout/layout.mbt'
    before = path.read_text()
    start = before.index('fn FlexItem::resolved_flex_basis(')
    end = before.index('\n}\n', start) + 3
    original = before[start:end]
    # Preserve validation and self use so --deny-warn remains meaningful.
    require(original.count('Ok(value)') == 1, 'Production basis resolver changed')
    mutated = original.replace('Ok(value)', 'Ok(fallback)')
    before_hash = sha(path)
    path.write_text(before[:start] + mutated + before[end:])
    return {'kind': 'production-points-resolve-as-auto', 'file': 'layout/layout.mbt',
            'original_sha256': before_hash, 'mutated_sha256': sha(path),
            'original_function': original, 'mutated_function': mutated}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('upstream-source','moonbit-source','output','rust-dependency-cache'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--allow-dirty-worktree',action='store_true',help='Snapshot actual uncommitted MoonBit/suite source bytes and mark them honestly')
    p.add_argument('--execute-build',action='store_true',help='Explicitly execute prepared commands; omission writes plan only')
    p.add_argument('--reuse-rust-build',type=Path,help='Reuse verified flex-basis adapter binary from a prior build manifest, without recompilation or copying')
    p.add_argument('--disable-flex-basis',action='store_true',help='Compile explicitly labeled production resolver mutation')
    a=p.parse_args()
    sources={name:source_identity(path) for name,path in [('upstream',a.upstream_source),('moonbit',a.moonbit_source),('suite',ROOT)]}
    validate_pins(sources)
    require(a.allow_dirty_worktree or not any(s['dirty'] for s in sources.values()), 'Uncommitted inputs require --allow-dirty-worktree')
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    rust=out/'rust';shutil.copytree(ROOT/'adapters/flex_basis/rust',rust)
    manifest=rust/'Cargo.toml'
    manifest.write_text(manifest.read_text().replace('"../../../zed-source/crates/gpui"',json.dumps(str(a.upstream_source.resolve()/'crates/gpui'))))
    moon=out/'moon';snapshot_source(sources['moonbit'],moon)
    shutil.copytree(ROOT/'adapters/flex_basis/moonbit',moon/'conformance_probe')
    mutation = None
    if a.disable_flex_basis:
        mutation = disable_flex_basis(moon)
    rust_exe,rust_command,deps,dependency_inputs=cached_rust(rust,sources['upstream'],a.rust_dependency_cache.resolve(),out)
    adapter_hashes={str(path.relative_to(ROOT/'adapters/flex_basis/rust')):sha(path) for path in sorted((ROOT/'adapters/flex_basis/rust').rglob('*')) if path.is_file()}
    commands=[('rust',rust_command,ROOT)]
    reuse=None
    if a.reuse_rust_build:
        previous=json.loads(a.reuse_rust_build.read_text())
        require(previous['rust_adapter_sha256']==adapter_hashes, 'Changed Rust adapter cannot reuse binary')
        for key in ('revision','tree','source_sha256'):
            require(previous['sources']['upstream'][key]==sources['upstream'][key], 'Reused upstream source differs')
        rust_exe=Path(previous['executables']['upstream']['path'])
        require(sha(rust_exe)==previous['executables']['upstream']['sha256'], 'Reused upstream executable changed')
        reuse={'manifest_path':str(a.reuse_rust_build.resolve()),'manifest_sha256':sha(a.reuse_rust_build),'manifest':previous}
        commands=[]
    commands.append(('moon',['moon','build','--target','native','--deny-warn','conformance_probe'],moon))
    plan={'scope':'headless TestWindow and snapshot geometry only; no desktop/pixel parity', 'pins_sha256':sha(ROOT/'flex_basis_pins.json'),
          'sources':sources,'disable_flex_basis':a.disable_flex_basis,'mutation':mutation,'rust_adapter_sha256':adapter_hashes,'rust_dependencies':deps,'reused_rust':reuse,
          'commands':[{'name':name,'command':command,'cwd':str(cwd)} for name,command,cwd in commands]}
    (out/'build-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    if not a.execute_build:
        print(json.dumps({'status':'prepared_only','plan':str(out/'build-plan.json'),'commands':plan['commands']},indent=2));return
    for row in plan['commands']:
        name=row['name']
        with (out/(name+'-build.stdout')).open('wb') as stdout,(out/(name+'-build.stderr')).open('wb') as stderr:
            proc=subprocess.run(row['command'],cwd=row['cwd'],stdout=stdout,stderr=stderr,timeout=600)
        row.update(returncode=proc.returncode,stdout_sha256=sha(out/(name+'-build.stdout')),stderr_sha256=sha(out/(name+'-build.stderr')))
        (out/'build-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
        require(proc.returncode==0, name+' build failed; retained '+str(out/(name+'-build.stderr')))
    debug=a.rust_dependency_cache.resolve()/'rust/target/debug'
    require(all(deps['dependency_sha256'][str(path.relative_to(debug))]==sha(path) for path in dependency_inputs), 'Read-only Rust dependency changed')
    require(sources=={name:source_identity(path) for name,path in [('upstream',a.upstream_source),('moonbit',a.moonbit_source),('suite',ROOT)]}, 'Input sources changed during build')
    exes={'upstream':rust_exe,'moonbit':moon/'_build/native/debug/build/conformance_probe/conformance_probe.exe'}
    plan['executables']={name:{'path':str(path),'sha256':sha(path)} for name,path in exes.items()}
    plan['toolchains']={tool:subprocess.check_output(command,text=True).strip() for tool,command in [('rust',['rustc','+1.98.1','--version']),('moon',['moon','version'])]}
    (out/'build-manifest.json').write_text(json.dumps(plan,indent=2)+'\n')
    print(json.dumps({'executables':plan['executables'],'manifest':str(out/'build-manifest.json')},indent=2))

if __name__=='__main__':main()
