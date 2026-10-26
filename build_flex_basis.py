#!/usr/bin/env python3
"""Prepare/build source-pinned flex-basis adapters without implicit build fallbacks.

Use locked Cargo (offline unless --online), verified read-only dependencies, or a
verified adapter binary. Uncommitted sources require explicit consent and are
copied from recorded file-byte snapshots, never from git archive HEAD.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
from build_flex_justify import cached_rust
from run_flex_basis import (ROOT, DEFAULT_PINS, POINTS_CONTROL, PERCENT_CONTROL, SPACING_CONTROL, CONTROL_KINDS, INTRINSIC_PERCENT_CONTROL, PERCENT_PARSER_CONTROLS,
                            basis_parser_identity, control_kind, require, sha, source_identity, validate_pins)


def snapshot_source(source, destination):
    destination.mkdir(parents=True, exist_ok=False)
    for relative,digest in source['files'].items():
        src=Path(source['path'])/relative
        require(sha(src)==digest, 'Source changed before snapshot: '+relative)
        target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src,target)
        require(sha(target)==digest, 'Copied source differs: '+relative)


def disable_flex_basis(moon, kind=POINTS_CONTROL):
    """Mutate the production resolver only; preserve its validation and adapter."""
    path = moon/('layout/tree.mbt' if kind == INTRINSIC_PERCENT_CONTROL else 'layout/layout.mbt')
    before = path.read_text()
    function = ('fn intrinsic_percent_contribution(' if kind == INTRINSIC_PERCENT_CONTROL else
                'fn device_distributed_starts(' if kind == SPACING_CONTROL else 'fn FlexItem::resolved_flex_basis(')
    start = before.index(function)
    end = before.index('\n}\n', start) + 3
    original = before[start:end]
    # Preserve validation and self use so --deny-warn remains meaningful.
    require(kind in CONTROL_KINDS, 'Unknown production basis mutation')
    if kind == INTRINSIC_PERCENT_CONTROL:
        needle, replacement = 'Some(value) => Ok(value)', 'Some(_) => Ok(0.0)'
    elif kind == SPACING_CONTROL:
        needle = 'if sizes.length() <= 1 ||'
        replacement = 'if sizes.length() >= 0 ||'
    elif kind == PERCENT_CONTROL:
        needle = 'Ok(Some(resolved)) => Ok(resolved)'
        replacement = 'Ok(Some(_)) => Ok(fallback)'
        require(original.count('Ok(resolved)') == 1, 'Production percent result must be unique')
    else:
        needle, replacement = 'Ok(value)', 'Ok(fallback)'
    require(original.count(needle) == 1, 'Production basis resolver changed')
    mutated = original.replace(needle, replacement)
    before_hash = sha(path)
    path.write_text(before[:start] + mutated + before[end:])
    return {'kind': kind, 'file': str(path.relative_to(moon)),
            'original_sha256': before_hash, 'mutated_sha256': sha(path),
            'original_function': original, 'mutated_function': mutated}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('upstream-source','moonbit-source','output'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--pins',type=Path,default=DEFAULT_PINS,help='Exact source profile, including capability control kind')
    p.add_argument('--control-kind',choices=CONTROL_KINDS,help='If supplied, must match the selected pins')
    p.add_argument('--rust-dependency-cache',type=Path,help='Verify and reuse exact-pin Cargo dependencies read-only, without a Cargo fallback')
    p.add_argument('--online',action='store_true',help='Permit dependency downloads for an explicitly selected full locked Cargo build')
    p.add_argument('--allow-dirty-worktree',action='store_true',help='Snapshot actual uncommitted MoonBit/suite source bytes and mark them honestly')
    p.add_argument('--execute-build',action='store_true',help='Explicitly execute prepared commands; omission writes plan only')
    p.add_argument('--reuse-rust-build',type=Path,help='Reuse verified adapter binary from a prior build manifest, without recompilation or a dependency-cache requirement')
    p.add_argument('--disable-flex-basis',action='store_true',help='Compile the production resolver mutation classified by the selected pins')
    p.add_argument('--build-timeout',type=int,default=1800,help='Per-command timeout in seconds; failed builds never trigger an alternate build mode')
    a=p.parse_args()
    require(a.build_timeout>0, 'Build timeout must be positive')
    require(not a.online or not (a.rust_dependency_cache or a.reuse_rust_build), '--online applies only to full locked Cargo builds')
    sources={name:source_identity(path) for name,path in [('upstream',a.upstream_source),('moonbit',a.moonbit_source),('suite',ROOT)]}
    pins=validate_pins(sources,a.pins)
    kind=control_kind(pins)
    require(a.control_kind is None or a.control_kind==kind, 'Requested control kind differs from selected pins')
    require(a.allow_dirty_worktree or not any(s['dirty'] for s in sources.values()), 'Uncommitted inputs require --allow-dirty-worktree')
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    rust=out/'rust';shutil.copytree(ROOT/'adapters/flex_basis/rust',rust)
    manifest=rust/'Cargo.toml'
    manifest.write_text(manifest.read_text().replace('"../../../zed-source/crates/gpui"',json.dumps(str(a.upstream_source.resolve()/'crates/gpui'))))
    lock_hash=sha(rust/'Cargo.lock')
    moon=out/'moon';snapshot_source(sources['moonbit'],moon)
    shutil.copytree(ROOT/'adapters/flex_basis/moonbit',moon/'conformance_probe')
    parser=basis_parser_identity(kind)
    if kind in PERCENT_PARSER_CONTROLS:
        shutil.copy2(ROOT/parser['source_path'],moon/'conformance_probe/basis.mbt')
    require(sha(moon/'conformance_probe/basis.mbt')==parser['sha256'], 'Prepared basis parser differs from selected profile')
    mutation=disable_flex_basis(moon,kind) if a.disable_flex_basis else None
    adapter_hashes={str(path.relative_to(ROOT/'adapters/flex_basis/rust')):sha(path) for path in sorted((ROOT/'adapters/flex_basis/rust').rglob('*')) if path.is_file()}
    deps=None;dependency_inputs=[];reuse=None;commands=[]
    if a.reuse_rust_build:
        previous=json.loads(a.reuse_rust_build.read_text())
        require(previous['rust_adapter_sha256']==adapter_hashes, 'Changed Rust adapter cannot reuse binary')
        for key in ('revision','tree','source_sha256'):
            require(previous['sources']['upstream'][key]==sources['upstream'][key], 'Reused upstream source differs')
        require(not previous['sources']['upstream']['dirty'], 'Reused upstream source was dirty')
        version=subprocess.check_output(['rustc','+1.98.1','--version'],text=True).strip()
        require(previous['toolchains']['rust']==version, 'Reused adapter compiler mismatch')
        rust_exe=Path(previous['executables']['upstream']['path'])
        require(sha(rust_exe)==previous['executables']['upstream']['sha256'], 'Reused upstream executable changed')
        reuse={'manifest_path':str(a.reuse_rust_build.resolve()),'manifest_sha256':sha(a.reuse_rust_build),'manifest':previous}
        mode='verified-binary-reuse'
    elif a.rust_dependency_cache:
        rust_exe,rust_command,deps,dependency_inputs=cached_rust(rust,sources['upstream'],a.rust_dependency_cache.resolve(),out)
        commands.append(('rust',rust_command,ROOT))
        mode='verified-dependency-reuse'
    else:
        rust_exe=rust/'target/debug/gpui-conformance-probe'
        rust_command=['cargo','+1.98.1','build','--locked','--manifest-path',str(manifest),'--target-dir',str(rust/'target')]
        if not a.online:
            rust_command.append('--offline')
        commands.append(('rust',rust_command,ROOT))
        mode='locked-cargo-online' if a.online else 'locked-cargo-offline'
    commands.append(('moon',['moon','build','--target','native','--deny-warn','conformance_probe'],moon))
    plan={'scope':'headless TestWindow and snapshot geometry only; no desktop/pixel parity', 'pins_sha256':sha(a.pins),
          'control_kind':kind,'basis_parser':parser,'sources':sources,'disable_flex_basis':a.disable_flex_basis,'mutation':mutation,
          'rust_adapter_sha256':adapter_hashes,'rust_lockfile_sha256':lock_hash,'rust_build_mode':mode,
          'rust_dependencies':deps,'reused_rust':reuse,
          'commands':[{'name':name,'command':command,'cwd':str(cwd)} for name,command,cwd in commands]}
    (out/'build-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    if not a.execute_build:
        print(json.dumps({'status':'prepared_only','plan':str(out/'build-plan.json'),'commands':plan['commands']},indent=2));return
    for row in plan['commands']:
        name=row['name']
        with (out/(name+'-build.stdout')).open('wb') as stdout,(out/(name+'-build.stderr')).open('wb') as stderr:
            proc=subprocess.run(row['command'],cwd=row['cwd'],stdout=stdout,stderr=stderr,timeout=a.build_timeout)
        row.update(returncode=proc.returncode,stdout_sha256=sha(out/(name+'-build.stdout')),stderr_sha256=sha(out/(name+'-build.stderr')))
        (out/'build-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
        require(proc.returncode==0, name+' build failed; retained '+str(out/(name+'-build.stderr')))
    if deps is not None:
        debug=a.rust_dependency_cache.resolve()/'rust/target/debug'
        require(all(deps['dependency_sha256'][str(path.relative_to(debug))]==sha(path) for path in dependency_inputs), 'Read-only Rust dependency changed')
    require(sha(rust/'Cargo.lock')==lock_hash, 'Locked Cargo input changed')
    require(sources=={name:source_identity(path) for name,path in [('upstream',a.upstream_source),('moonbit',a.moonbit_source),('suite',ROOT)]}, 'Input sources changed during build')
    exes={'upstream':rust_exe,'moonbit':moon/'_build/native/debug/build/conformance_probe/conformance_probe.exe'}
    plan['executables']={name:{'path':str(path),'sha256':sha(path)} for name,path in exes.items()}
    plan['toolchains']={tool:subprocess.check_output(command,text=True).strip() for tool,command in [('rust',['rustc','+1.98.1','--version']),('moon',['moon','version'])]}
    (out/'build-manifest.json').write_text(json.dumps(plan,indent=2)+'\n')
    print(json.dumps({'executables':plan['executables'],'manifest':str(out/'build-manifest.json')},indent=2))

if __name__=='__main__':main()
