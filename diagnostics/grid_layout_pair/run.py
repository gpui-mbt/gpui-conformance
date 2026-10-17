#!/usr/bin/env python3
"""Compile exact production packages and retain the complete native semantic pair."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import uuid
from compare import ROOT, LAYER, baseline, compare_observations, require, require_semantic_match

PACKAGES = ('element', 'layout', 'primitives', 'scene')
MODULE = 'name = "f4ah6o/gpui"\nversion = "0.0.0"\n'
SUITE_FILES = ('adapters/grid_layout_moonbit/main.mbt', 'adapters/grid_layout_moonbit/moon.pkg',
    'diagnostics/grid_layout_pair/compare.py', 'diagnostics/grid_layout_pair/run.py',
    'diagnostics/grid_layout_pair/verify.py', 'diagnostics/grid_layout_pair/profile.json',
    'diagnostics/grid_layout_pair/README.md', 'diagnostics/grid_layout_pair/run_mutants.py',
    'diagnostics/grid_layout_pair/mutations.json', 'diagnostics/grid_layout_pair/run_controls.py',
    'tests/test_grid_layout_pair.py', '.github/workflows/grid-layout-pair.yml')
OMITTED_BUILD_CACHES = ('build-source/_build/.moon_db', 'build-source/_build/.moon-lock')


def retained_path(relative):
    return 'suite/workflows/grid-layout-pair.yml' if relative.startswith('.github/') else 'suite/' + relative


def now(): return datetime.now(timezone.utc).isoformat()


def command(args, cwd=None): return subprocess.check_output(args, cwd=cwd, text=True).strip()


def identity(path):
    return {'commit': command(['git', 'rev-parse', 'HEAD'], path),
            'tree': command(['git', 'rev-parse', 'HEAD^{tree}'], path),
            'clean': not command(['git', 'status', '--porcelain', '--untracked-files=all'], path)}


def production_file(relative):
    path = Path(relative)
    return len(path.parts) == 2 and path.parts[0] in PACKAGES and (path.name == 'moon.pkg' or
        path.suffix == '.mbt' and not path.name.endswith(('_test.mbt', '_wbtest.mbt')))


def production_paths(core):
    return sorted(str(p.relative_to(core)) for package in PACKAGES for p in (core / package).iterdir()
                  if p.is_file() and production_file(str(p.relative_to(core))))


def execute(args, cwd, out, stem, environment, timeout=120):
    started = now()
    with (out / (stem + '.stdout')).open('wb') as stdout, (out / (stem + '.stderr')).open('wb') as stderr:
        process = subprocess.Popen(args, cwd=cwd, env=environment, stdout=stdout, stderr=stderr)
        timed_out = False
        try: code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            code = process.wait()
    return {'command': args, 'cwd': str(cwd), 'started_at': started, 'finished_at': now(),
            'pid': process.pid, 'returncode': code, 'timed_out': timed_out}


def validate_baseline(directory, suite_source, upstream_source, suite_commit, recorded_execution_root=None):
    profile = json.loads((ROOT / 'diagnostics/grid_layout_pair/profile.json').read_text())
    require(isinstance(suite_commit, str) and len(suite_commit) == 40, 'independently selected exact baseline suite commit required')
    tree = command(['git', 'rev-parse', suite_commit + '^{tree}'], suite_source)
    result = baseline.verify_bundle(directory, suite_commit, tree, suite_source, upstream_source, recorded_execution_root=recorded_execution_root)
    require(result['source_bound'], 'Rust baseline must be independently source-bound')
    for relative, expected in profile['approved_fixture_sha256'].items():
        require(baseline.digest(directory / baseline.retained_path(relative)) == expected, 'baseline fixture changed: ' + relative)
    return {'suite_commit': suite_commit, 'suite_tree': tree, 'manifest_sha256': baseline.digest(directory / 'manifest.json'),
            'raw_sha256': baseline.digest(directory / 'raw.json'), 'source_bound': True,
            'recorded_execution_root': str(Path(recorded_execution_root).resolve() if recorded_execution_root is not None else directory.resolve())}


def inventory(directory):
    return {str(path.relative_to(directory)): {'sha256': baseline.digest(path), 'size': path.stat().st_size}
            for path in sorted(directory.rglob('*')) if path.is_file()
            and str(path.relative_to(directory)) not in OMITTED_BUILD_CACHES and path.relative_to(directory) != Path('manifest.json')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core-source', type=Path, required=True)
    parser.add_argument('--core-commit', required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--baseline-suite-source', type=Path, default=ROOT)
    parser.add_argument('--baseline-suite-commit', required=True)
    parser.add_argument('--upstream-source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    core, original = args.core_source.resolve(), args.baseline.resolve()
    profile = json.loads((ROOT / 'diagnostics/grid_layout_pair/profile.json').read_text())
    approved = validate_baseline(original, args.baseline_suite_source, args.upstream_source, args.baseline_suite_commit)
    core_before, suite_before = identity(core), identity(ROOT)
    require(core_before['clean'] and suite_before['clean'], 'exact clean sources required')
    require(args.core_commit == profile['candidate_commit'] == core_before['commit'] and core_before['tree'] == profile['candidate_tree'], 'candidate public commit/tree pin')
    require(args.baseline_suite_commit == suite_before['commit'], 'fresh baseline and pair must use same suite commit')
    require(shutil.disk_usage(ROOT).free >= 2 * 1024**3, 'Need 2GiB headroom; preserve evidence and run heavy pair in CI')
    out = args.output.resolve()
    require(out.is_relative_to(ROOT / '_build'), 'output must be a new ignored _build directory')
    out.mkdir(parents=True, exist_ok=False)
    stage = out / 'build-source'
    stage.mkdir()
    (stage / 'moon.mod').write_text(MODULE)
    shutil.copy2(core / 'moon.mod', out / 'original-core-moon.mod')
    inputs = production_paths(core)
    for relative in inputs:
        destination = stage / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(core / relative, destination)
    shutil.copytree(ROOT / 'adapters/grid_layout_moonbit', stage / 'probe')
    for relative in SUITE_FILES:
        destination = out / retained_path(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    shutil.copytree(original, out / 'rust-baseline')
    shutil.copy2(original / 'scenarios.json', out / 'scenarios.json')
    environment = os.environ.copy()
    token = str(uuid.uuid4())
    environment['GPUI_SCENARIOS'] = (out / 'scenarios.json').read_text()
    environment['GPUI_RUN_TOKEN'] = token
    moon = shutil.which('moon')
    require(moon is not None, 'MoonBit toolchain missing')
    moon = str(Path(moon).resolve())
    (out / 'toolchain.txt').write_text(command([moon, 'version', '--all']) + '\n' + command(['cc', '--version']) + '\n')
    tools = {name: {'path': str(Path(shutil.which(name)).resolve()), 'sha256': baseline.digest(Path(shutil.which(name)).resolve())} for name in ('moon', 'moonc', 'cc')}
    moon_home = Path(environment['MOON_HOME']).resolve()
    toolchain_inputs = []
    for relative in ('lib/core/_build/native/release/bundle', 'include', 'lib/runtime', 'lib/libmoonbitrun.o', 'lib/libbacktrace.a'):
        source = moon_home / relative
        for path in (sorted(source.rglob('*')) if source.is_dir() else [source]):
            if path.is_file():
                name = str(path.relative_to(moon_home))
                destination = out / 'toolchain-inputs' / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
                toolchain_inputs.append(name)
    require(toolchain_inputs, 'native toolchain input inventory missing')
    manifest = {'schema_version': 1, 'layer': LAYER, 'run_token': token, 'qualification': 'exact-clean-source-pair',
        'review_or_publication_claim': False, 'requested_core_commit': args.core_commit, 'recorded_execution_root': str(out),
        'core': core_before, 'suite': suite_before, 'baseline': approved, 'core_inputs': inputs,
        'toolchain_inputs': toolchain_inputs, 'toolchain_home': str(moon_home),
        'input_environment': {'GPUI_RUN_TOKEN': token, 'GPUI_SCENARIOS_sha256': baseline.digest(out / 'scenarios.json')},
        'tool_binaries': tools, 'platform': {'system': platform.system(), 'machine': platform.machine()},
        'started_at': now(), 'omitted_non_input_build_caches': list(OMITTED_BUILD_CACHES), 'files': {}}
    manifest['build_plan'] = execute([moon, 'build', '--target', 'native', '--deny-warn', '--dry-run', '--verbose', 'probe'], stage, out, 'build-plan', environment)
    manifest['build'] = execute([moon, 'build', '--target', 'native', '--deny-warn', '--verbose', 'probe'], stage, out, 'build', environment)
    if manifest['build']['returncode'] == 0:
        shutil.copy2(stage / '_build/native/debug/build/probe/probe.exe', out / 'candidate-probe')
        manifest['execution'] = execute([str(out / 'candidate-probe')], stage, out, 'candidate', environment)
        (out / 'candidate.stdout').rename(out / 'candidate-raw.json')
    manifest['core_after'], manifest['suite_after'] = identity(core), identity(ROOT)
    if manifest.get('execution', {}).get('returncode') == 0:
        try:
            comparison = compare_observations(json.loads((original / 'raw.json').read_text()),
                json.loads((out / 'candidate-raw.json').read_text()), json.loads((out / 'scenarios.json').read_text()),
                json.loads((original / 'retained/diagnostics/grid_layout/witnesses.json').read_text()))
            (out / 'comparison.json').write_text(json.dumps(comparison, indent=2) + '\n')
        except (ValueError, KeyError, TypeError, IndexError) as error:
            (out / 'comparison-failure.json').write_text(json.dumps({'error': str(error), 'type': type(error).__name__}, indent=2) + '\n')
    manifest['finished_at'] = now()
    manifest['files'] = inventory(out)
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    require(manifest['core_after'] == core_before and manifest['suite_after'] == suite_before, 'source identity changed; evidence retained')
    require(manifest['build']['returncode'] == 0, 'candidate build failed; evidence retained')
    require(manifest.get('execution', {}).get('returncode') == 0, 'candidate execution failed; evidence retained')
    require((out / 'comparison.json').is_file(), 'candidate trace invalid; evidence retained')
    require_semantic_match(comparison)
    print(json.dumps({'evidence': str(out), 'qualification': manifest['qualification'], 'counts': comparison['counts']}))


if __name__ == '__main__': main()
