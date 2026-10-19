#!/usr/bin/env python3
"""Build standalone reverse-flow probes from pinned upstream and clean core."""
import argparse
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

from run_reverse_flow import ROOT, identity, sha, require, validate_pins


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--upstream-source', type=Path, required=True)
    p.add_argument('--moonbit-source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--disable-reversal', action='store_true', help='Compile an explicit capability-negative mutant')
    args = p.parse_args()
    sources = {name: identity(path) for name, path in [('upstream', args.upstream_source), ('moonbit', args.moonbit_source), ('suite', ROOT)]}
    validate_pins(sources)
    require(not any(value['dirty'] for value in sources.values()), 'Commit tracked input changes before building')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    rust = out/'rust'
    shutil.copytree(ROOT/'adapters/reverse_flow/rust', rust, dirs_exist_ok=True)
    manifest = rust/'Cargo.toml'
    manifest.write_text(manifest.read_text().replace('"../../../zed-source/crates/gpui"', json.dumps(str(args.upstream_source.resolve()/'crates/gpui'))))
    moon = out/'moon'
    moon.mkdir(exist_ok=False)
    archive = subprocess.check_output(['git', '-C', str(args.moonbit_source), 'archive', 'HEAD'])
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(moon, filter='data')
    mutation = None
    if args.disable_reversal:
        file = moon/'layout/layout.mbt'
        before = file.read_text()
        original = 'self is RowReverse || self is ColumnReverse'
        require(before.count(original) == 1)
        file.write_text(before.replace(original, 'match self { Row | Column | RowReverse | ColumnReverse => false }'))
        mutation = {'file': 'layout/layout.mbt', 'original_sha256': __import__('hashlib').sha256(before.encode()).hexdigest(),
                    'mutated_sha256': sha(file), 'change': 'FlowDirection::is_reverse always returns false'}
    shutil.copytree(ROOT/'adapters/reverse_flow/moonbit', moon/'conformance_probe')
    commands = [('rust', ['cargo', '+1.98.1', 'build', '--locked', '--offline', '--manifest-path', str(manifest)], ROOT),
                ('moon', ['moon', 'build', '--target', 'native', '--deny-warn', 'conformance_probe'], moon)]
    for name, cmd, cwd in commands:
        with (out/(name+'-build.stdout')).open('wb') as stdout, (out/(name+'-build.stderr')).open('wb') as stderr:
            subprocess.run(cmd, cwd=cwd, stdout=stdout, stderr=stderr, timeout=600, check=True)
    exes = {'upstream': rust/'target/debug/gpui-conformance-probe', 'moonbit': moon/'_build/native/debug/build/conformance_probe/conformance_probe.exe'}
    evidence = {'pins_sha256': sha(ROOT/'reverse_flow_pins.json'), 'sources': sources, 'mutation': mutation, 'executables': {name: {'path': str(path), 'sha256': sha(path)} for name, path in exes.items()},
                'toolchains': {tool: subprocess.check_output(cmd, text=True).strip() for tool, cmd in [('rust', ['rustc', '+1.98.1', '--version']), ('moon', ['moon', 'version'])]}}
    (out/'build-manifest.json').write_text(json.dumps(evidence, indent=2)+'\n')
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
