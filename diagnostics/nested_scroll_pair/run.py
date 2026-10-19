#!/usr/bin/env python3
"""Execute the font-free nested-scroll pair against exact clean source commits."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PACKAGES = ('primitives', 'layout', 'scene', 'element')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load(path):
    return json.loads(path.read_text(), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(path):
    return {str(p.relative_to(path)): digest(p) for p in sorted(path.rglob('*')) if p.is_file()}


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def identity(path, pin):
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=path, text=True).strip()
    require(git('rev-parse', 'HEAD') == pin, 'source revision differs: ' + str(path))
    require(not git('status', '--porcelain', '--untracked-files=all'), 'source is dirty: ' + str(path))
    return {'commit': pin, 'tree': git('rev-parse', 'HEAD^{tree}')}


def validate_fixture(fixture):
    require(set(fixture) == {'schema_version', 'points', 'cases'} and type(fixture['schema_version']) is int and fixture['schema_version'] == 1, 'fixture schema')
    require(isinstance(fixture['points'], list) and fixture['points'], 'fixture points')
    require(isinstance(fixture['cases'], list) and fixture['cases'], 'fixture cases')
    names = set()
    for row in fixture['points']:
        require(isinstance(row, list) and len(row) == 2, 'point shape')
        require(all(type(x) in (int, float) and math.isfinite(x) for x in row), 'finite point')
    for case in fixture['cases']:
        require(set(case) == {'id', 'layout', 'device_scale', 'wheels'}, 'case schema')
        require(type(case['device_scale']) in (int, float) and case['device_scale'] in (1, 2), 'supported device scale')
        require(case['layout'] in ('vertical', 'horizontal', 'both'), 'case layout')
        require(isinstance(case['id'], str) and case['id'] and case['id'] not in names, 'unique case id')
        names.add(case['id'])
        require(isinstance(case['wheels'], list) and case['wheels'], 'wheel list')
        for row in case['wheels']:
            require(isinstance(row, list) and len(row) == 4, 'wheel shape')
            require(all(type(x) in (int, float) and math.isfinite(x) for x in row), 'finite wheel')


def validate_observation(raw, fixture, backend):
    require(set(raw) == {'schema_version', 'backend', 'input', 'cases'}, 'observation schema')
    require(type(raw['schema_version']) is int and raw['schema_version'] == 1 and raw['backend'] == backend and raw['input'] == fixture, 'observation identity/input')
    require(len(raw['cases']) == len(fixture['cases']), 'case count')
    for actual, case in zip(raw['cases'], fixture['cases']):
        require(set(actual) == {'id', 'device_scale', 'frames'} and actual['id'] == case['id'], 'ordered case identity')
        require(type(actual['device_scale']) in (int, float) and actual['device_scale'] == case['device_scale'], 'observed device scale')
        require(len(actual['frames']) == len(case['wheels']) + 1, 'frame count')
        for frame in actual['frames']:
            require(set(frame) == {'offsets', 'maximums', 'bounds', 'targets'}, 'frame schema')
            for key in ('offsets', 'maximums'):
                require(len(frame[key]) == 2 and all(len(row) == 2 for row in frame[key]), 'scroll state shape')
                require(all(type(x) in (int, float) and math.isfinite(x) for row in frame[key] for x in row), 'finite scroll state')
            require(len(frame['bounds']) == 5, 'bounds count')
            for node, ident in zip(frame['bounds'], range(2, 7)):
                require(len(node) == 2 and type(node[0]) is int and node[0] == ident and len(node[1]) == 4, 'bounds identity/shape')
                require(all(type(x) in (int, float) and math.isfinite(x) for x in node[1]), 'finite bounds')
            require(len(frame['targets']) == len(fixture['points']), 'target count')
            require(all(x is None or type(x) is int and 2 <= x <= 6 for x in frame['targets']), 'target identity')


def compare(rust, moon, fixture):
    validate_fixture(fixture)
    validate_observation(rust, fixture, 'rust-gpui')
    validate_observation(moon, fixture, 'moonbit')
    differences = []
    for r, m in zip(rust['cases'], moon['cases']):
        for index, (rf, mf) in enumerate(zip(r['frames'], m['frames'])):
            for field in rf:
                if rf[field] != mf[field]:
                    differences.append({'case': r['id'], 'frame': index, 'field': field, 'rust': rf[field], 'moonbit': mf[field]})
    return {'status': 'pass' if not differences else 'mismatch', 'cases': len(fixture['cases']),
            'frames': sum(len(c['wheels']) + 1 for c in fixture['cases']), 'differences': differences,
            'scope': 'headless nested scroll offsets, maxima, geometry and hit targets; no native or pixel claim'}


def execute(args, cwd, env, out, name, timeout=120):
    start = datetime.now(timezone.utc).isoformat()
    with (out / (name + '.stdout')).open('wb') as stdout, (out / (name + '.stderr')).open('wb') as stderr:
        process = subprocess.Popen(args, cwd=cwd, env=env, stdout=stdout, stderr=stderr)
        timed_out = False
        try:
            code = process.wait(timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            code = process.wait()
    return {'command': args, 'cwd': str(cwd), 'started_at': start, 'returncode': code, 'timed_out': timed_out}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('upstream-source', 'core-source', 'output'):
        parser.add_argument('--' + key, type=Path, required=True)
    parser.add_argument('--cargo-target-dir', type=Path, help='Optional compilation cache; Cargo still builds the retained source')
    parser.add_argument('--online', action='store_true')
    args = parser.parse_args()
    upstream, core, out = args.upstream_source.resolve(), args.core_source.resolve(), args.output.resolve()
    pins = load(HERE / 'pins.json')
    fixture = load(HERE / 'scenarios.json')
    validate_fixture(fixture)
    sources = {'upstream': identity(upstream, pins['upstream']), 'core': identity(core, pins['core'])}
    require(not out.exists(), 'fresh output required')
    out.mkdir(parents=True)
    save(out / 'scenarios.json', fixture)
    rust = out / 'rust-source'
    shutil.copytree(ROOT / 'adapters/nested_scroll_rust', rust)
    lock = (ROOT / 'adapters/grid_layout_rust/Cargo.lock').read_text()
    require(lock.count('name = \"gpui-grid-layout-diagnostic\"') == 1, 'shared lock package identity')
    (rust / 'Cargo.lock').write_text(lock.replace('name = \"gpui-grid-layout-diagnostic\"', 'name = \"gpui-nested-scroll-diagnostic\"'))
    manifest = rust / 'Cargo.toml'
    manifest.write_text(manifest.read_text().replace('"../../../zed-source/crates/gpui"', json.dumps(str(upstream / 'crates/gpui'))))
    moon = out / 'moon-source'
    moon.mkdir()
    (moon / 'moon.mod').write_text('name = "f4ah6o/gpui"\nversion = "0.0.0"\n')
    for package in PACKAGES:
        (moon / package).mkdir()
        for path in (core / package).iterdir():
            if path.name == 'moon.pkg' or path.suffix == '.mbt' and not path.name.endswith(('_test.mbt', '_wbtest.mbt')):
                shutil.copy2(path, moon / package / path.name)
    shutil.copytree(ROOT / 'adapters/nested_scroll_moonbit', moon / 'probe')
    source_files = {'rust': inventory(rust), 'moon': inventory(moon)}
    env = os.environ.copy()
    env['SCROLL_SCENARIOS'] = json.dumps(fixture)
    target = args.cargo_target_dir.resolve() if args.cargo_target_dir else out / 'rust-target'
    env['CARGO_TARGET_DIR'] = str(target)
    suite_sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    suite = identity(ROOT, suite_sha)
    suite_files = ['adapters/grid_layout_rust/Cargo.lock'] + [str(p.relative_to(ROOT)) for folder in ('adapters/nested_scroll_rust', 'adapters/nested_scroll_moonbit', 'diagnostics/nested_scroll_pair') for p in sorted((ROOT / folder).rglob('*')) if p.is_file() and '__pycache__' not in p.parts] + ['tests/test_nested_scroll_pair.py']
    for relative in suite_files:
        destination = out / 'suite-source' / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    record = {'status': 'started', 'suite': suite, 'suite_files': inventory(out / 'suite-source'),
              'sources': sources, 'source_files': source_files, 'runs': {}}
    try:
        for name, command, cwd, timeout in [
            ('rust-version', ['rustc', '+1.98.1', '--version'], ROOT, 30),
            ('moon-version', ['moon', 'version', '--all'], ROOT, 30),
            ('node-version', ['node', '--version'], ROOT, 30),
            ('rust-build', ['cargo', '+1.98.1', 'build', '--locked'] + ([] if args.online else ['--offline']) + ['--manifest-path', str(manifest)], ROOT, 2100),
            ('moon-build', ['moon', 'build', '--target', 'js', '--deny-warn', 'probe'], moon, 120),
        ]:
            record['runs'][name] = execute(command, cwd, env, out, name, timeout)
            require(record['runs'][name]['returncode'] == 0, name + ' failed; see retained stderr')
        shutil.copy2(target / 'debug/gpui-nested-scroll-diagnostic', out / 'rust-probe')
        shutil.copy2(moon / '_build/js/debug/build/probe/probe.js', out / 'moon-probe.js')
        record['artifacts'] = {p: digest(out / p) for p in ('rust-probe', 'moon-probe.js')}
        for name, command in [('rust', [str(out / 'rust-probe')]), ('moon', ['node', str(out / 'moon-probe.js')])]:
            record['runs'][name] = execute(command, ROOT, env, out, name)
            require(record['runs'][name]['returncode'] == 0, name + ' execution failed')
        report = compare(load(out / 'rust.stdout'), load(out / 'moon.stdout'), fixture)
        save(out / 'comparison.json', report)
        require(inventory(rust) == source_files['rust'], 'Rust staged source drift')
        require(all(digest(moon / p) == sha for p, sha in source_files['moon'].items()), 'MoonBit staged source drift')
        for name, path in [('upstream', upstream), ('core', core)]:
            require(identity(path, pins[name]) == sources[name], 'source changed')
        require(identity(ROOT, suite_sha) == suite, 'suite changed')
        record['status'] = report['status']
        print(json.dumps(report))
    except Exception:
        record['status'] = 'failed'
        raise
    finally:
        record['files'] = {p.name: digest(p) for p in out.iterdir() if p.is_file()}
        save(out / 'manifest.json', record)
    return 0 if record['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
