#!/usr/bin/env python3
"""Source-bound, batched full-rectangle reverse-spacing differential.

Batches bound the OS environment payload; they never filter or normalize cases.
Every input, raw process stream, and source/executable identity is retained.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
from datetime import datetime, timezone
from run_flex_basis import ROOT, compare, require, sha, source_identity, validate, validate_build, validate_control_mode


def chunks(cases, size):
    for i in range(0, len(cases), size):
        yield cases[i:i + size]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('rust-exe', 'moon-exe', 'upstream-source', 'moonbit-source', 'build-manifest', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--scenarios', type=Path, default=ROOT/'reverse_rounding_scenarios.json')
    p.add_argument('--pins', type=Path, default=ROOT/'reverse_rounding_pins.json')
    p.add_argument('--batch-size', type=int, default=64)
    p.add_argument('--negative-control', action='store_true')
    p.add_argument('--capability-control', action='store_true')
    a = p.parse_args()
    require(1 <= a.batch_size <= 64, 'Batch size must be between 1 and 64')
    corpus = json.loads(a.scenarios.read_text()); validate(corpus)
    sources = {name:source_identity(path) for name,path in [('upstream',a.upstream_source),('moonbit',a.moonbit_source),('suite',ROOT)]}
    build = json.loads(a.build_manifest.read_text())
    exes = {'upstream':a.rust_exe, 'moonbit':a.moon_exe}
    validate_build(build, sources, exes, a.pins)
    validate_control_mode(build, corpus, a.capability_control)
    out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    (out/'scenarios.json').write_bytes(a.scenarios.read_bytes())
    evidence = {'started_at':datetime.now(timezone.utc).isoformat(),'sources':sources,'build_manifest':build,
                'build_manifest_sha256':sha(a.build_manifest),'pins_sha256':sha(a.pins),'scenarios_sha256':sha(a.scenarios),
                'negative_control':a.negative_control,'capability_control':a.capability_control,'batches':[],
                'scope':'Complete root/container/child rectangles; no geometry projection or tolerance change; headless only'}
    observed = {name:{'implementation':name,'cases':[]} for name in exes}
    for index, batch in enumerate(chunks(corpus['cases'], a.batch_size)):
        d = out/f'batch-{index:03d}'; d.mkdir()
        request = {**corpus, 'cases':batch}
        payload = json.dumps(request)
        require(len(payload.encode()) < 100000, 'Oversized batch; reduce batch size')
        (d/'scenarios.json').write_text(json.dumps(request,indent=2)+'\n')
        env = os.environ.copy(); env.update(GPUI_SCENARIOS=payload, GPUI_FIXED_ROOT_CONTROL='0', GPUI_NEGATIVE_CONTROL=str(int(a.negative_control)))
        record = {'directory':d.name,'scenarios_sha256':sha(d/'scenarios.json'),'case_ids':[c['id'] for c in batch],'runs':{}}
        for name, exe in exes.items():
            require(sha(exe) == build['executables'][name]['sha256'], 'Executable changed before run')
            proc = subprocess.run([str(exe.resolve())], env=env, capture_output=True, timeout=90)
            require(sha(exe) == build['executables'][name]['sha256'], 'Executable changed during run')
            (d/(name+'.stdout')).write_bytes(proc.stdout); (d/(name+'.stderr')).write_bytes(proc.stderr)
            record['runs'][name] = {'returncode':proc.returncode,'executable_sha256':sha(exe),'stdout_sha256':sha(d/(name+'.stdout')),'stderr_sha256':sha(d/(name+'.stderr'))}
            require(proc.returncode == 0, name+' failed; see '+str(d))
            lines = [x.removeprefix('GPUI_CONFORMANCE ') for x in proc.stdout.decode().splitlines() if x.startswith('GPUI_CONFORMANCE ')]
            require(len(lines) == 1, 'Expected one process observation')
            result = json.loads(lines[0]); require(result['implementation'] == name)
            require([x['id'] for x in result['cases']] == record['case_ids'], 'Missing, reordered or added process observations')
            observed[name]['cases'].extend(result['cases'])
        evidence['batches'].append(record)
        (out/'manifest.json').write_text(json.dumps(evidence,indent=2)+'\n')
    result = compare(corpus, observed['upstream'], observed['moonbit'])
    (out/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    require(sources == {name:source_identity(path) for name,path in [('upstream',a.upstream_source),('moonbit',a.moonbit_source),('suite',ROOT)]}, 'Sources changed during execution')
    evidence['finished_at'] = datetime.now(timezone.utc).isoformat(); evidence['summary'] = result['summary']
    (out/'manifest.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps(result['summary']))
    actual = {c['id'] for c in result['cases'] if c['status'] == 'mismatch'}
    expected = {c['id'] for c in corpus['cases'] if c['expected_capability_mismatch']}
    if a.negative_control: return int(len(actual) != len(corpus['cases']))
    if a.capability_control: return int(actual != expected)
    return int(bool(actual))


if __name__ == '__main__': raise SystemExit(main())
