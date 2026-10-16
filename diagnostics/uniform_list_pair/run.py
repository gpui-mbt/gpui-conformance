#!/usr/bin/env python3
"""Compile a small native production-core probe; retain a self-contained raw pair."""
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
from compare import ROOT, baseline, compare_observations, require

PACKAGES = ('element', 'layout', 'primitives', 'scene')
MODULE = 'name = "f4ah6o/gpui"\nversion = "0.0.0"\n'
SUITE_FILES = (
    'adapters/uniform_list_moonbit/main.mbt', 'adapters/uniform_list_moonbit/moon.pkg',
    'diagnostics/uniform_list_pair/compare.py', 'diagnostics/uniform_list_pair/run.py',
    'diagnostics/uniform_list_pair/verify.py', 'diagnostics/uniform_list_pair/README.md',
    'diagnostics/uniform_list_pair/approved_baseline.json', 'tests/test_uniform_list_pair.py',
)

EXTRA_SUITE_FILES = ('diagnostics/uniform_list_pair/profile.json',
    'diagnostics/uniform_list_pair/run_controls.py', 'diagnostics/uniform_list_pair/run_mutants.py',
    'diagnostics/uniform_list_pair/mutations.json', 'diagnostics/uniform_list_pair/range_guard_test.mbt',
    'diagnostics/uniform_list_pair/run_range_guard.py', '.github/workflows/uniform-list-diagnostic.yml',
    'diagnostics/uniform_list/verify.py')
ALL_SUITE_FILES = SUITE_FILES + EXTRA_SUITE_FILES
OMITTED_BUILD_CACHES = ('build-source/_build/.moon_db', 'build-source/_build/.moon-lock')

def suite_retained_path(relative):
    return 'suite/workflows/uniform-list-diagnostic.yml' if relative.startswith('.github/') else 'suite/' + relative


def now(): return datetime.now(timezone.utc).isoformat()

def command(args, cwd=None): return subprocess.check_output(args, cwd=cwd, text=True).strip()

def identity(path):
    return {'commit': command(['git', 'rev-parse', 'HEAD'], path),
            'tree': command(['git', 'rev-parse', 'HEAD^{tree}'], path),
            'clean': not command(['git', 'status', '--porcelain', '--untracked-files=all'], path)}

def production_file(relative):
    p = Path(relative)
    return p.parts[0] in PACKAGES and len(p.parts) == 2 and (p.name == 'moon.pkg' or
        (p.suffix == '.mbt' and not p.name.endswith(('_test.mbt', '_wbtest.mbt'))))

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

def validate_approved_baseline(directory, suite_source, upstream_source):
    pin = json.loads((ROOT / 'diagnostics/uniform_list_pair/approved_baseline.json').read_text())
    for relative, digest in pin['files'].items():
        require(baseline.digest(directory / relative) == digest, 'not approved actual baseline: ' + relative)
    result = baseline.verify_bundle(directory, pin['suite_commit'], pin['suite_tree'], suite_source, upstream_source)
    require(result['source_bound'], 'baseline not independently source-bound')
    return pin

def validate_baseline(directory, suite_source, upstream_source, fresh_suite_commit=None):
    if fresh_suite_commit is None:
        return validate_approved_baseline(directory, suite_source, upstream_source)
    require(len(fresh_suite_commit) == 40, 'exact fresh baseline suite commit required')
    profile = json.loads((ROOT / 'diagnostics/uniform_list_pair/profile.json').read_text())
    tree = command(['git', 'rev-parse', fresh_suite_commit + '^{tree}'], suite_source)
    baseline.verify_bundle(directory, fresh_suite_commit, tree, suite_source, upstream_source)
    # New actual run is allowed only for byte-identical approved fixture/build/input/schema/verifier.
    for relative, expected in profile['approved_fixture_sha256'].items():
        require(baseline.digest(directory / baseline.retained_path(relative)) == expected,
                'fresh baseline changed approved fixture: ' + relative)
    manifest = json.loads((directory / 'manifest.json').read_text())
    require(manifest['upstream']['commit'] == profile['upstream_commit']
            and manifest['upstream']['tree'] == profile['upstream_tree'], 'fresh upstream pin')
    return {'mode': 'fresh-source-bound', 'suite_commit': fresh_suite_commit, 'suite_tree': tree,
            'upstream_commit': profile['upstream_commit'], 'upstream_tree': profile['upstream_tree'],
            'approved_fixture_profile_sha256': baseline.digest(ROOT / 'diagnostics/uniform_list_pair/profile.json'),
            'files': {name: baseline.digest(directory / name) for name in ('manifest.json', 'raw.json', 'scenarios.json', 'probe')}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core-source', type=Path, required=True)
    parser.add_argument('--core-commit', help='Exact externally selected clean core commit')
    parser.add_argument('--allow-unqualified-checkout', action='store_true', help='Explicit dirty/local provisional observation only')
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--fresh-baseline-suite-commit', help='Explicit exact current CI suite commit for a newly executed unchanged Rust fixture')
    parser.add_argument('--baseline-suite-source', type=Path, default=ROOT)
    parser.add_argument('--upstream-source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    core, original = args.core_source.resolve(), args.baseline.resolve()
    pin = validate_baseline(original, args.baseline_suite_source, args.upstream_source, args.fresh_baseline_suite_commit)
    core_before, suite_before = identity(core), identity(ROOT)
    if args.fresh_baseline_suite_commit is not None:
        require(args.fresh_baseline_suite_commit == suite_before['commit'], 'fresh pair must execute at the same exact suite checkout')
    profile = json.loads((ROOT / 'diagnostics/uniform_list_pair/profile.json').read_text())
    if args.core_commit is None and not args.allow_unqualified_checkout:
        args.core_commit = profile['candidate_commit']
        require(core_before['tree'] == profile['candidate_tree'], 'public candidate tree mismatch')
    if not args.allow_unqualified_checkout:
        require(args.core_commit and len(args.core_commit) == 40, 'explicit exact core pin required')
        require(core_before['commit'] == args.core_commit and core_before['clean'] and suite_before['clean'], 'clean exact sources required')
    require(args.core_commit is None or core_before['commit'] == args.core_commit, 'core commit mismatch')
    if args.core_commit == profile['candidate_commit']:
        require(core_before['tree'] == profile['candidate_tree'], 'public candidate tree mismatch')
    require(shutil.disk_usage(ROOT).free >= 1024**3, 'Preserve at least1GiB free; no cache/evidence cleanup allowed')
    out = args.output.resolve()
    require(out.is_relative_to(ROOT / '_build'), 'output must be a new directory under ignored _build')
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
    shutil.copytree(ROOT / 'adapters/uniform_list_moonbit', stage / 'probe')
    for relative in ALL_SUITE_FILES:
        destination = out / suite_retained_path(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    shutil.copytree(original, out / 'rust-baseline')
    shutil.copy2(original / 'scenarios.json', out / 'scenarios.json')
    environment = os.environ.copy()
    token = str(uuid.uuid4())
    environment['GPUI_SCENARIOS'] = (out / 'scenarios.json').read_text()
    environment['GPUI_RUN_TOKEN'] = token
    moon = shutil.which('moon')
    require(moon is not None, 'MoonBit toolchain not found')
    toolchain = command([moon, 'version', '--all']) + '\n' + command(['cc', '--version']) + '\n'
    (out / 'toolchain.txt').write_text(toolchain)
    tools = {}
    for name in ('moon', 'moonc', 'cc'):
        path = Path(shutil.which(name)).resolve()
        tools[name] = {'path': str(path), 'sha256': baseline.digest(path)}
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
    manifest = {'schema_version': 2, 'layer': 'compiled-uniform-list-pair', 'run_token': token,
        'qualification': 'unqualified-checkout' if args.allow_unqualified_checkout else 'exact-clean-local-source-pair',
        'review_or_publication_claim': False, 'requested_core_commit': args.core_commit,
        'core': core_before, 'suite': suite_before, 'core_source_path': str(core),
        'baseline_mode': 'fresh-source-bound' if args.fresh_baseline_suite_commit else 'approved-retained',
        'core_inputs': inputs, 'toolchain_inputs': toolchain_inputs, 'toolchain_home': str(moon_home),
        'input_environment': {'GPUI_RUN_TOKEN': token, 'GPUI_SCENARIOS_sha256': baseline.digest(out / 'scenarios.json')}, 'approved_baseline': pin, 'tool_binaries': tools,
        'platform': {'system': platform.system(), 'machine': platform.machine()},
        'started_at': now(), 'omitted_non_input_build_caches': list(OMITTED_BUILD_CACHES), 'files': {}}
    manifest['build_plan'] = execute([moon, 'build', '--target', 'native', '--deny-warn', '--dry-run', '--verbose', 'probe'], stage, out, 'build-plan', environment)
    manifest['build'] = execute([moon, 'build', '--target', 'native', '--deny-warn', '--verbose', 'probe'], stage, out, 'build', environment)
    if manifest['build']['returncode'] == 0:
        shutil.copy2(stage / '_build/native/debug/build/probe/probe.exe', out / 'candidate-probe')
        manifest['execution'] = execute([str(out / 'candidate-probe')], stage, out, 'candidate', environment)
        (out / 'candidate.stdout').rename(out / 'candidate-raw.json')
    manifest['core_after'], manifest['suite_after'] = identity(core), identity(ROOT)
    require(manifest['core_after'] == core_before and manifest['suite_after'] == suite_before, 'source identity changed during build')
    for relative in inputs:
        require((stage / relative).read_bytes() == (core / relative).read_bytes(), 'source bytes changed during build: ' + relative)
    if manifest.get('execution', {}).get('returncode') == 0:
        try:
            comparison = compare_observations(json.loads((original / 'raw.json').read_text()),
                json.loads((out / 'candidate-raw.json').read_text()), json.loads((out / 'scenarios.json').read_text()))
            (out / 'comparison.json').write_text(json.dumps(comparison, indent=2) + '\n')
        except (ValueError, KeyError, TypeError, IndexError) as error:
            (out / 'comparison-failure.json').write_text(json.dumps({'error': str(error)}, indent=2) + '\n')
    manifest['finished_at'] = now()
    for path in sorted(out.rglob('*')):
        if path.is_file() and str(path.relative_to(out)) not in manifest['omitted_non_input_build_caches']:
            require(not any(part.startswith('.') for part in path.relative_to(out).parts), 'unexpected hidden artifact input: ' + str(path.relative_to(out)))
            manifest['files'][str(path.relative_to(out))] = {'sha256': baseline.digest(path), 'size': path.stat().st_size}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    require(manifest['build']['returncode'] == 0, 'candidate build failed; evidence retained')
    require(manifest.get('execution', {}).get('returncode') == 0, 'candidate execution failed; evidence retained')
    require((out / 'comparison.json').is_file(), 'pair differs; raw evidence retained')
    print(json.dumps({'evidence': str(out), 'qualification': manifest['qualification'], 'counts': comparison['counts']}))

if __name__ == '__main__': main()
