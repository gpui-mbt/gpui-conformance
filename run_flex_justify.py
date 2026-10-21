#!/usr/bin/env python3
"""Token-free, process-backed flex-relative-justify full-bounds differential.

Adapters are bounded copies of the existing reverse-flow corpus adapters. Builds must be
performed explicitly before this runner; executable hashes and source identity
are retained alongside stdout/stderr. No native window or screenshot claim.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent


def require(condition, message="invalid flex-relative-justify evidence"):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(path):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(path), *args], text=True).strip()
    return {'path': str(path.resolve()), 'revision': git('rev-parse', 'HEAD'),
            'tree': git('rev-parse', 'HEAD^{tree}'), 'dirty': bool(git('status', '--porcelain', '--untracked-files=no'))}


def numeric(value, *, nullable=False):
    return (nullable and value is None) or (type(value) in (int, float) and math.isfinite(value) and value >= 0)


def validate(corpus):
    require(type(corpus) is dict and corpus.get('schema_version') == 1 and corpus.get('cases'))
    require(type(corpus['cases']) is list)
    ids = set()
    for case in corpus['cases']:
        require(type(case) is dict and type(case.get('id')) is str and case['id'] and case['id'] not in ids)
        ids.add(case['id'])
        require(case.get('kind') == 'layout' and case.get('layer') == 'headless-layout')
        require(case.get('direction') in ('row', 'column', 'row_reverse', 'column_reverse'))
        require(all(numeric(case.get(k)) and 0 < case[k] <= 4096 for k in ('width', 'height')))
        require(case.get('layout_observation', 'bounds') == 'bounds')
        require(type(case.get('device_scale_factor')) in (int, float) and case['device_scale_factor'] == 2)
        children = case.get('children')
        require(type(children) is list and 1 <= len(children) <= 3)
        require(all(type(child) is list and len(child) == 2 and all(numeric(v, nullable=True) for v in child) for child in children))
        require(case.get('align') in ('start', 'center', 'end', 'stretch'))
        require(case.get('justify') in ('start', 'center', 'end', 'space-between', 'space-around', 'space-evenly', 'flex_start', 'flex_end'))
        require(case.get('wrap', 'nowrap') in ('nowrap', 'wrap', 'wrap_reverse'))
        require(case.get('align_content', 'stretch') in ('start', 'center', 'end', 'stretch', 'space-between', 'space-around', 'space-evenly'))
        overrides = case.get('align_self')
        require(type(overrides) is list and len(overrides) == len(children))
        require(all(value in ('auto', 'start', 'center', 'end', 'stretch', 'flex_start', 'flex_end') for value in overrides))
        require(numeric(case.get('gap')))
        for key in ('gap_x', 'gap_y'):
            require(key not in case or numeric(case[key]))
        if 'padding' in case:
            require(type(case['padding']) is list and len(case['padding']) == 4 and all(numeric(v) for v in case['padding']))
        for key in ('grow', 'shrink', 'min_main', 'max_main', 'min_cross', 'max_cross'):
            if key in case:
                require(type(case[key]) is list and len(case[key]) == len(children))
                require(all(numeric(v, nullable=key.startswith('max')) for v in case[key]))
        for axis in ('main', 'cross'):
            for minimum, maximum in zip(case.get('min_'+axis, [0]*len(children)), case.get('max_'+axis, [None]*len(children))):
                require(maximum is None or minimum <= maximum)


def compare(corpus, rust, moon):
    validate(corpus)
    require(rust.get("implementation") == "upstream")
    require(moon.get("implementation") == "moonbit")
    rows = []
    require(len(rust['cases']) == len(moon['cases']) == len(corpus['cases']))
    for expected, a, b in zip(corpus['cases'], rust['cases'], moon['cases']):
        require(a['id'] == b['id'] == expected['id'])
        require(a['status'] == b['status'] == 'observed')
        require(a['layer'] == b['layer'] == 'headless-layout')
        require(type(a.get('observation')) is dict and type(b.get('observation')) is dict)
        require(set(a['observation']) == set(b['observation']) == {'bounds'})
        ab, bb = a['observation']['bounds'], b['observation']['bounds']
        require(type(ab) is list and type(bb) is list)
        require(len(ab) == len(bb) == len(expected['children']) + 1)
        differences = []
        for i, (ar, br) in enumerate(zip(ab, bb)):
            require(len(ar) == len(br) == 4)
            for j, (x, y) in enumerate(zip(ar, br)):
                require(type(x) in (int, float) and type(y) in (int, float))
                require(math.isfinite(x) and math.isfinite(y))
                require(j < 2 or (x >= 0 and y >= 0))
                if abs(x-y) > 1e-5:
                    differences.append({'path': f'bounds[{i}][{j}]', 'upstream': x, 'moonbit': y})
        rows.append({'id': a['id'], 'status': 'mismatch' if differences else 'pass', 'differences': differences})
    return {'summary': {'total': len(rows), 'pass': sum(r['status'] == 'pass' for r in rows),
                        'mismatch': sum(r['status'] == 'mismatch' for r in rows)}, 'cases': rows}


def validate_pins(sources):
    pins = json.loads((ROOT/'flex_justify_pins.json').read_text())
    require(pins['schema_version'] == 1, 'Unknown flex-relative-justify pin schema')
    for name in ('upstream', 'moonbit'):
        for key in ('revision', 'tree'):
            require(sources[name][key] == pins[name][key], f'{name} {key} differs from flex-relative-justify pin')


def validate_build(build, sources, executables):
    validate_pins(sources)
    validate_pins(build['sources'])
    for name in ('upstream', 'moonbit', 'suite'):
        for key in ('revision', 'tree'):
            require(build['sources'][name][key] == sources[name][key], 'Build/source '+key+' mismatch')
        require(not build['sources'][name]['dirty'], 'Dirty build input source')
        require(not sources[name]['dirty'], 'Dirty input source')
    require(len({sha(exe) for exe in executables.values()}) == len(executables), 'Implementations must use distinct executable bytes')
    for name, exe in executables.items():
        require(build['executables'][name]['sha256'] == sha(exe), 'Executable hash mismatch')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for arg in ('rust-exe', 'moon-exe', 'upstream-source', 'moonbit-source', 'output'):
        p.add_argument('--'+arg, type=Path, required=True)
    p.add_argument('--scenarios', type=Path, default=ROOT/'flex_justify_scenarios.json')
    p.add_argument('--negative-control', action='store_true')
    p.add_argument('--build-manifest', type=Path, required=True)
    args = p.parse_args()
    corpus = json.loads(args.scenarios.read_text())
    validate(corpus)
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    (out/'scenarios.json').write_bytes(args.scenarios.read_bytes())
    env = os.environ.copy()
    env['GPUI_SCENARIOS'] = json.dumps(corpus)
    env['GPUI_NEGATIVE_CONTROL'] = '1' if args.negative_control else '0'
    sources = {'upstream': identity(args.upstream_source), 'moonbit': identity(args.moonbit_source), 'suite': identity(ROOT)}
    build = json.loads(args.build_manifest.read_text())
    require(build['pins_sha256'] == sha(ROOT/'flex_justify_pins.json'), 'Build pins hash mismatch')
    require(build.get('mutation') is None or build['mutation'].get('kind') == 'disable_flex_justify', 'Unknown capability mutation')
    validate_build(build, sources, {'upstream': args.rust_exe, 'moonbit': args.moon_exe})
    manifest = {'pins_sha256': sha(ROOT/'flex_justify_pins.json'), 'build_manifest_sha256': sha(args.build_manifest), 'build_manifest': build, 'started_at': datetime.now(timezone.utc).isoformat(), 'sources': sources,
                'scenarios_sha256': sha(args.scenarios), 'negative_control': args.negative_control,
                'tolerance': 1e-5, 'projection': 'complete root and source-order child bounds', 'runs': {}}
    observed = {}
    for name, exe in [('upstream', args.rust_exe), ('moonbit', args.moon_exe)]:
        exe = exe.resolve()
        proc = subprocess.run([str(exe)], env=env, capture_output=True, timeout=60)
        stdout, stderr = out/(name+'.stdout'), out/(name+'.stderr')
        stdout.write_bytes(proc.stdout)
        stderr.write_bytes(proc.stderr)
        manifest['runs'][name] = {'executable': str(exe), 'sha256': sha(exe), 'returncode': proc.returncode,
                                  'stdout_sha256': sha(stdout), 'stderr_sha256': sha(stderr)}
        require(proc.returncode == 0, proc.stderr.decode())
        lines = [line.removeprefix('GPUI_CONFORMANCE ') for line in proc.stdout.decode().splitlines() if line.startswith('GPUI_CONFORMANCE ')]
        require(len(lines) == 1)
        observed[name] = json.loads(lines[0])
    after = {'upstream': identity(args.upstream_source), 'moonbit': identity(args.moonbit_source), 'suite': identity(ROOT)}
    require(after == sources, 'Input sources changed during execution')
    result = compare(corpus, observed['upstream'], observed['moonbit'])
    manifest['finished_at'] = datetime.now(timezone.utc).isoformat()
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    (out/'comparison.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result['summary']))
    return int(result['summary']['mismatch'] != 0)


if __name__ == '__main__':
    raise SystemExit(main())
