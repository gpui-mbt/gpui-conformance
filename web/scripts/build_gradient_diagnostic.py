#!/usr/bin/env python3
"""Build synthetic probes against immutable upstream renderer; CI execution only."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
from build_rust import prepare_gallery, TOOLCHAIN, WEB
from build_moonbit import check_source, run

REVISION = '5a5fbe79917971a4d52a96b6ddb04da198a5012e'
NAME = 'gradient_diagnostic'
SOURCE_REGISTRY_SHA256 = '95d6e03ef3ba1be0fa56ce91516073a2954a30d70a83974f58e62f158dbf8a99'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def prepare_diagnostic(source, gallery):
    packaging = prepare_gallery(source, gallery, [])
    shutil.copy2(WEB / 'gradient-diagnostic/main.rs', gallery / 'gradient_diagnostic.rs')
    manifest = gallery / 'Cargo.toml'
    manifest.write_text(manifest.read_text() + '\n[[bin]]\nname = "gradient_diagnostic"\npath = "gradient_diagnostic.rs"\n')
    return {**packaging, 'kind': 'synthetic diagnostic in relocated standalone upstream package',
            'manifest_sha256': digest(manifest), 'diagnostic_source_sha256': digest(gallery / 'gradient_diagnostic.rs'),
            'upstream_files_modified': False, 'original_example': False}

def committed_suite():
    if run(['git', 'status', '--porcelain', '--untracked-files=no'], WEB.parent, True):
        raise ValueError('Dirty tracked suite source')
    registry = json.loads((WEB / 'gradient-diagnostic/provenance-inputs.json').read_text())
    files = {}
    for path in registry['suite_inputs']:
        raw = subprocess.run(['git', 'show', 'HEAD:' + path], cwd=WEB.parent, check=True, stdout=subprocess.PIPE).stdout
        if raw != (WEB.parent / path).read_bytes():
            raise ValueError('Uncommitted suite input: ' + path)
        files[path] = hashlib.sha256(raw).hexdigest()
    return {'commit': run(['git', 'rev-parse', 'HEAD'], WEB.parent, True),
            'tree': run(['git', 'rev-parse', 'HEAD^{tree}'], WEB.parent, True), 'files': files}

def build(upstream, site, target):
    if site.exists():
        raise ValueError('Diagnostic site must be a fresh directory')
    check_source(upstream, REVISION)
    suite = committed_suite()
    if shutil.disk_usage('/tmp').free < 1024 ** 3:
        raise ValueError('Less than 1 GiB temporary free space')
    with tempfile.TemporaryDirectory(prefix='gradient-diagnostic-', dir='/tmp') as work:
        work = Path(work)
        source = work / 'source'; source.mkdir()
        archive = subprocess.run(['git', 'archive', REVISION], cwd=upstream, check=True, stdout=subprocess.PIPE).stdout
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(source, filter='data')
        gallery = work / 'gallery'
        packaging = prepare_diagnostic(source, gallery)
        command = ['cargo', f'+{TOOLCHAIN}', 'build', '--locked', '--release', '--config', 'profile.release.codegen-units=1',
                   '--target', 'wasm32-unknown-unknown', '--bin', NAME, '--target-dir', str(target)]
        run(command, gallery)
        output = work / 'output'; output.mkdir()
        run(['wasm-bindgen', '--target', 'web', '--out-dir', str(output), '--out-name', NAME,
             str(target / 'wasm32-unknown-unknown/release/gradient_diagnostic.wasm')], gallery)
        for name in ['index.html', 'host.mjs', 'profile.json', 'main.rs', 'README.md', 'upstream-sources.json', 'provenance-inputs.json']:
            shutil.copy2(WEB / 'gradient-diagnostic' / name, output / name)
        shutil.copy2(gallery / 'Cargo.toml', output / 'packaging-Cargo.toml')
        shutil.copy2(gallery / 'Cargo.lock', output / 'Cargo.lock')
        shutil.copy2(source / 'LICENSE-APACHE', output / 'LICENSE-APACHE')
        # Preserve exact shader and CPU input bytes separately from synthetic source.
        registry_path = WEB / 'gradient-diagnostic/upstream-sources.json'
        if digest(registry_path) != SOURCE_REGISTRY_SHA256:
            raise ValueError('Frozen upstream source registry changed')
        registry = json.loads(registry_path.read_text())
        for record in registry['sources']:
            relative = record['path']
            if digest(source / relative) != record['sha256']:
                raise ValueError('Pinned upstream source bytes changed: ' + relative)
            dest = output / 'upstream-source' / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / relative, dest)
        manifest = {'schema_version': 1, 'kind': 'synthetic_rust_gpu_diagnostic_only', 'original_example': False,
                    'candidate': 'not_implemented', 'conformance': 'not_claimed', 'upstream_revision': REVISION,
                    'upstream_tree': run(['git', 'rev-parse', REVISION + '^{tree}'], upstream, True),
                    'suite_tree': suite['tree'], 'suite_commit': suite['commit'], 'suite_inputs': suite['files'],
                    'packaging': packaging, 'toolchain': run(['rustc', f'+{TOOLCHAIN}', '--version'], gallery, True),
                    'bindings': run(['wasm-bindgen', '--version'], gallery, True),
                    'files': {str(p.relative_to(output)): digest(p) for p in sorted(output.rglob('*')) if p.is_file()}}
        (output / 'build-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        check_source(upstream, REVISION)
        if committed_suite() != suite:
            raise ValueError('Suite changed during build')
        shutil.copytree(output, site)

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--upstream-source', required=True, type=Path)
    p.add_argument('--site', type=Path, default=Path('/tmp/gradient-diagnostic-site'))
    p.add_argument('--target-dir', type=Path, default=Path('/tmp/gradient-diagnostic-target'))
    a = p.parse_args()
    build(a.upstream_source.resolve(), a.site.resolve(), a.target_dir.resolve())
