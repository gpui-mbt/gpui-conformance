#!/usr/bin/env python3
"""Build only the compiled grid_layout candidate, separate from frozen Rust evidence.

An explicit --local-core-override permits dirty development source. Its manifest
is unqualified and the actual pair verifier rejects it. No guessed public pin.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import difflib
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
from build_moonbit import WEB, run, check_candidate_source, check_source

PROFILE = WEB / 'pairs/grid_layout.json'
CORE_DIRS = ('element', 'layout', 'primitives', 'scene')


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources(root: Path) -> dict[str, str]:
    paths = [root / 'moon.mod', root / 'script/macos_text_prebuild.py']
    for name in CORE_DIRS:
        paths.extend(sorted((root / name).rglob('*.mbt')))
        paths.append(root / name / 'moon.pkg')
    return {str(p.relative_to(root)): digest(p) for p in paths}


def mutate_source(source: str, mutation: dict) -> str:
    if source.count(mutation['find']) != mutation['occurrences']:
        raise ValueError('Exact source mutation anchor count changed')
    return source.replace(mutation['find'], mutation['replace'])


def build(core: Path, upstream: Path, out: Path, local_override: bool = False, control: str | None = None) -> None:
    profile = json.loads(PROFILE.read_text())
    if out.exists():
        raise ValueError('Output exists; use a fresh directory')
    if shutil.disk_usage(out.parent if out.parent.exists() else WEB.parent).free < 1024**3:
        raise ValueError('At least 1 GiB free space is required before building')
    if control is not None and control not in profile['executed_controls']:
        raise ValueError('Unknown executed control')
    actual = {'repository': profile['candidate']['repository'],
              'revision': run(['git', 'rev-parse', 'HEAD'], core, True),
              'tree': run(['git', 'rev-parse', 'HEAD^{tree}'], core, True)}
    dirty = bool(run(['git', 'status', '--porcelain', '--untracked-files=all'], core, True))
    suite_dirty = bool(run(['git', 'status', '--porcelain', '--untracked-files=no'], WEB.parent, True))
    if not local_override:
        check_candidate_source(core, profile['candidate'])
        if dirty or suite_dirty:
            raise ValueError('Qualified build requires clean committed core and suite')
        suite_paths = [PROFILE, Path(__file__).resolve(), *sorted((WEB / 'moonbit/site').rglob('*')),
                       *sorted((WEB / 'moonbit/grid_layout').iterdir())]
        for path in suite_paths:
            if path.is_file():
                run(['git', 'ls-files', '--error-unmatch', str(path.relative_to(WEB.parent))], WEB.parent, True)
    check_source(upstream, profile['upstream']['revision'])
    if run(['git', 'rev-parse', 'HEAD^{tree}'], upstream, True) != profile['upstream']['tree']:
        raise ValueError('Upstream tree mismatch')
    source = upstream / profile['upstream']['source']
    if digest(source) != profile['upstream']['source_sha256']:
        raise ValueError('Unchanged source bytes mismatch')
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='grid-pair-build-', dir=out.parent) as work:
        work = Path(work)
        candidate = work / 'candidate'
        candidate.mkdir()
        if local_override:
            shutil.copy2(core / 'moon.mod', candidate / 'moon.mod')
            (candidate / 'script').mkdir()
            shutil.copy2(core / 'script/macos_text_prebuild.py', candidate / 'script/macos_text_prebuild.py')
            for name in CORE_DIRS:
                shutil.copytree(core / name, candidate / name)
        else:
            archive = subprocess.run(['git', 'archive', 'HEAD'], cwd=core, check=True, stdout=subprocess.PIPE).stdout
            with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
                tar.extractall(candidate, filter='data')
        core_sources = sources(candidate)
        package = 'examples/conformance_grid_layout'
        shutil.copytree(WEB / 'moonbit/grid_layout', candidate / package)
        mutation = None
        if control:
            mutation = profile['executed_controls'][control]
            original = (candidate / package / 'grid_layout.mbt').read_text()
            changed = mutate_source(original, mutation)
            (candidate / package / 'grid_layout.mbt').write_text(changed)
        compiler = run(['moon', 'version', '--all'], candidate, True)
        commands = [['moon', 'test', package, '--target', 'js', '--deny-warn'],
                    ['moon', 'build', package, '--target', 'js', '--release', '--deny-warn']]
        if control:
            commands = commands[1:]  # Original assertions intentionally reject faults; compile the fault itself.
        logs = []
        for command in commands:
            p = subprocess.run(command, cwd=candidate, text=True, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT)
            logs.append({'command': command, 'returncode': p.returncode, 'output': p.stdout})
            print(p.stdout, end='')
            if p.returncode:
                raise ValueError('Compiled candidate test/build failed')
        runtime = candidate / '_build/js/release/build' / package / 'conformance_grid_layout.js'
        stage = work / 'site'
        shutil.copytree(WEB / 'moonbit/site', stage / 'moonbit')
        shutil.copy2(WEB / 'load-timing.mjs', stage / 'load-timing.mjs')
        shutil.copy2(runtime, stage / 'moonbit/grid_layout.mjs')
        font = upstream / 'assets/fonts/ibm-plex-sans/IBMPlexSans-Regular.ttf'
        shutil.copy2(font, stage / 'moonbit/IBMPlexSans-Regular.ttf')
        shutil.copy2(font.parent / 'license.txt', stage / 'moonbit/font-license.txt')
        (stage / 'inputs').mkdir()
        shutil.copy2(source, stage / 'inputs/grid_layout.rs')
        shutil.copy2(PROFILE, stage / 'inputs/profile.json')
        shutil.copy2(WEB / 'examples.json', stage / 'inputs/current-catalog.json')
        for path in core_sources:
            target = stage / 'inputs/core' / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(candidate / path, target)
        for path in sorted((candidate / package).iterdir()):
            if path.is_file() and path.suffix != '.mbti':
                shutil.copy2(path, stage / 'inputs' / path.name)
        (stage / 'inputs/build-log.json').write_text(json.dumps(logs, indent=2) + '\n')
        control_source = None
        if control:
            original_bytes = (WEB / 'moonbit/grid_layout/grid_layout.mbt').read_bytes()
            mutated_bytes = (stage / 'inputs/grid_layout.mbt').read_bytes()
            (stage / 'inputs/unmutated-grid_layout.mbt').write_bytes(original_bytes)
            patch = ''.join(difflib.unified_diff(original_bytes.decode().splitlines(True),
                mutated_bytes.decode().splitlines(True), fromfile='original/grid_layout.mbt',
                tofile='compiled-control/grid_layout.mbt'))
            (stage / 'inputs/source-mutation.patch').write_text(patch)
            control_source = {'original_sha256': hashlib.sha256(original_bytes).hexdigest(),
                              'mutated_sha256': hashlib.sha256(mutated_bytes).hexdigest(),
                              'patch_file': 'inputs/source-mutation.patch',
                              'patch_sha256': digest(stage / 'inputs/source-mutation.patch')}

        manifest = {
            'schema': 1, 'site_kind': 'grid_layout_compiled_candidate', 'profile': profile,
            'qualification': 'unqualified_local_override' if local_override else 'pinned_clean_source',
            'candidate': actual, 'candidate_tracked_or_untracked_dirty': dirty,
            'lab_revision': run(['git', 'rev-parse', 'HEAD'], WEB.parent, True),
            'lab_tree': run(['git', 'rev-parse', 'HEAD^{tree}'], WEB.parent, True),
            'lab_tracked_dirty': suite_dirty, 'compiler': compiler,
            'completed_at_utc': datetime.now(timezone.utc).isoformat(),
            'commands': commands, 'unit_tests': 'not_run_for_executed_mutant' if control else 'passed',
            'executed_control': control, 'mutation': mutation, 'control_source': control_source, 'implemented': ['grid_layout'],
            'font_contract': 'Exact IBM Plex Sans bytes; Canvas shaping proxy; no text or full-image parity claim',
            'core_source_sha256': core_sources,
            'files': {str(p.relative_to(stage)): digest(p) for p in sorted(stage.rglob('*')) if p.is_file()},
            'comparison': 'not_run', 'conformance': 'not_claimed',
        }
        (stage / 'build-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        if not local_override:
            check_candidate_source(core, profile['candidate'])
        check_source(upstream, profile['upstream']['revision'])
        shutil.copytree(stage, out)
    print(f'Compiled grid_layout candidate: {out}; {manifest["qualification"]}; no browser comparison claimed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--gpui-source', type=Path, required=True)
    parser.add_argument('--upstream-source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--local-core-override', action='store_true')
    parser.add_argument('--control', choices=['wrong_gap', 'wrong_color'])
    args = parser.parse_args()
    try:
        build(args.gpui_source.resolve(), args.upstream_source.resolve(), args.out.resolve(), args.local_core_override, args.control)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'Grid-layout candidate build failed: {error}\n')
