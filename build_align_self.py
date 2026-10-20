#!/usr/bin/env python3
"""Build actual bounded align-self probes without modifying either source checkout."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

from run_align_self import ROOT, identity, sha, require, validate_pins


def cached_rust(rust, upstream, cache, out):
    """Reuse read-only exact-pin Cargo dependencies when disk prevents copying them."""
    source_manifest = cache / 'build-manifest.json'
    previous = json.loads(source_manifest.read_text())
    for key in ('revision', 'tree'):
        require(previous['sources']['upstream'][key] == upstream[key], 'Cached dependency source pin mismatch')
    require(not previous['sources']['upstream']['dirty'], 'Dirty cached dependency source')
    version = subprocess.check_output(['rustc', '+1.98.1', '--version'], text=True).strip()
    require(previous['toolchains']['rust'] == version, 'Cached dependency compiler mismatch')
    require(sha(rust/'Cargo.lock') == sha(cache/'rust/Cargo.lock'), 'Cached dependency lockfile mismatch')
    debug = cache/'rust/target/debug'
    def unique(pattern):
        paths = sorted((debug/'deps').glob(pattern))
        require(len(paths) == 1, 'Expected one cached '+pattern)
        return paths[0]
    executable = out/'gpui-conformance-probe'
    command = ['rustc', '+1.98.1', '--edition=2024', '--crate-name', 'gpui_conformance_probe',
               str(rust/'src/main.rs'), '-L', 'dependency='+str(debug/'deps'),
               '--extern', 'gpui='+str(unique('libgpui-*.rlib')),
               '--extern', 'serde_json='+str(unique('libserde_json-*.rlib')),
               '-C', 'debuginfo=0', '-o', str(executable)]
    for path in sorted((debug/'build').glob('*/out')):
        command += ['-L', 'native='+str(path)]
    inputs = sorted(set((debug/'deps').glob('*.rlib')) | set((debug/'deps').glob('*.rmeta')) | set((debug/'deps').glob('*.so')) |
                    set((debug/'build').glob('*/out/**/*.a')) | set((debug/'build').glob('*/out/**/*.o')))
    require(inputs, 'Empty dependency cache')
    hashes = {str(path.relative_to(debug)): sha(path) for path in inputs}
    evidence = {'mode': 'read-only exact-pin Cargo dependency reuse; new adapter compile/link',
                'manifest_sha256': sha(source_manifest), 'manifest': previous,
                'cache': str(cache), 'dependency_sha256': hashes}
    return executable, command, evidence, inputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('upstream-source', 'moonbit-source', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--disable-align-self', action='store_true', help='Compile the explicit capability-negative mutant')
    parser.add_argument('--rust-dependency-cache', type=Path, help='Prior compatible build directory, read-only; provenance and dependency hashes are retained')
    args = parser.parse_args()
    sources = {name: identity(path) for name, path in [('upstream', args.upstream_source), ('moonbit', args.moonbit_source), ('suite', ROOT)]}
    validate_pins(sources)
    require(not any(value['dirty'] for value in sources.values()), 'Commit tracked input changes before building')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    rust = out/'rust'
    shutil.copytree(ROOT/'adapters/align_self/rust', rust)
    manifest = rust/'Cargo.toml'
    manifest.write_text(manifest.read_text().replace('"../../../zed-source/crates/gpui"', json.dumps(str(args.upstream_source.resolve()/'crates/gpui'))))
    moon = out/'moon'
    moon.mkdir()
    archive = subprocess.check_output(['git', '-C', str(args.moonbit_source), 'archive', 'HEAD'])
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(moon, filter='data')
    mutation = None
    if args.disable_align_self:
        file = moon/'layout/layout.mbt'
        before = file.read_text()
        original = '  match self.align_self {'
        require(before.count(original) == 1, 'Capability mutation point must be unique')
        # Both arms inherit. The explicit discarded value avoids an unused-field
        # warning while removing every override through the production resolver.
        replacement = '  let inherited_only = match self.align_self { _ => AlignSelf::Auto }\n  match inherited_only {'
        file.write_text(before.replace(original, replacement))
        mutation = {'kind': 'disable_align_self', 'file': 'layout/layout.mbt',
                    'original_sha256': hashlib.sha256(before.encode()).hexdigest(), 'mutated_sha256': sha(file),
                    'change': 'effective per-item alignment always inherits the container'}
    shutil.copytree(ROOT/'adapters/align_self/moonbit', moon/'conformance_probe')
    dependency_evidence = None
    dependency_inputs = []
    if args.rust_dependency_cache:
        rust_exe, rust_command, dependency_evidence, dependency_inputs = cached_rust(rust, sources['upstream'], args.rust_dependency_cache.resolve(), out)
    else:
        rust_exe = rust/'target/debug/gpui-conformance-probe'
        rust_command = ['cargo', '+1.98.1', 'build', '--locked', '--offline', '--manifest-path', str(manifest)]
    commands = [('rust', rust_command, ROOT), ('moon', ['moon', 'build', '--target', 'native', '--deny-warn', 'conformance_probe'], moon)]
    command_evidence = []
    for name, command, cwd in commands:
        with (out/(name+'-build.stdout')).open('wb') as stdout, (out/(name+'-build.stderr')).open('wb') as stderr:
            process = subprocess.run(command, cwd=cwd, stdout=stdout, stderr=stderr, timeout=600)
        command_evidence.append({'name': name, 'command': command, 'cwd': str(cwd), 'returncode': process.returncode,
                                 'stdout_sha256': sha(out/(name+'-build.stdout')), 'stderr_sha256': sha(out/(name+'-build.stderr'))})
        require(process.returncode == 0, name+' build failed; retained stderr: '+str(out/(name+'-build.stderr')))
    if dependency_evidence:
        debug = args.rust_dependency_cache.resolve()/'rust/target/debug'
        require(all(dependency_evidence['dependency_sha256'][str(path.relative_to(debug))] == sha(path) for path in dependency_inputs), 'Read-only dependency cache changed during build')
    require(sources == {name: identity(path) for name, path in [('upstream', args.upstream_source), ('moonbit', args.moonbit_source), ('suite', ROOT)]}, 'Input sources changed during build')
    exes = {'upstream': rust_exe, 'moonbit': moon/'_build/native/debug/build/conformance_probe/conformance_probe.exe'}
    evidence = {'pins_sha256': sha(ROOT/'align_self_pins.json'), 'sources': sources, 'mutation': mutation,
                'commands': command_evidence, 'rust_dependencies': dependency_evidence,
                'executables': {name: {'path': str(path), 'sha256': sha(path)} for name, path in exes.items()},
                'toolchains': {tool: subprocess.check_output(command, text=True).strip() for tool, command in [('rust', ['rustc', '+1.98.1', '--version']), ('moon', ['moon', 'version'])]}}
    (out/'build-manifest.json').write_text(json.dumps(evidence, indent=2)+'\n')
    print(json.dumps({'executables': evidence['executables'], 'mutation': mutation}, indent=2))


if __name__ == '__main__':
    main()
