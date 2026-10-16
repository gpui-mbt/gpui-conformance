#!/usr/bin/env python3
"""Execute the fractional boundary unit regression; never claim a Rust pair."""
import argparse
import difflib
import json
import os
from pathlib import Path
import shutil
from compare import ROOT, baseline, require
from run_mutants import execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    evidence, out = args.evidence.resolve(), args.output.resolve()
    require(shutil.disk_usage(ROOT).free >= 1050 * 1024**2, 'preserve1GiB headroom')
    require(out.is_relative_to(ROOT / '_build'), 'output must be under _build')
    out.mkdir(parents=True, exist_ok=False)
    work = out / 'source'
    shutil.copytree(evidence / 'build-source', work, ignore=shutil.ignore_patterns('_build'))
    fixture = ROOT / 'diagnostics/uniform_list_pair/range_guard_test.mbt'
    shutil.copy2(fixture, work / 'element/pair_boundary_test.mbt')
    shutil.copy2(Path(__file__), out / 'run_range_guard.py')
    (out / 'source-input-hashes.json').write_text(json.dumps({str(p.relative_to(work)): baseline.digest(p) for p in work.rglob('*') if p.is_file()}, indent=2) + '\n')
    command = [shutil.which('moon'), 'test', 'element/pair_boundary_test.mbt', '--target', 'native', '--deny-warn', '--warn-list=-29']
    report = {'kind': 'executed-core-unit-regression-not-upstream-equivalence', 'core': json.loads((evidence / 'manifest.json').read_text())['core'],
              'baseline_manifest_sha256': baseline.digest(evidence / 'manifest.json'), 'fixture_sha256': baseline.digest(fixture)}
    report['baseline'] = execute(command, work, out, 'baseline', os.environ.copy())
    executable = work / '_build/native/debug/test/element/element.blackbox_test.exe'
    if report['baseline']['returncode'] == 0: shutil.copy2(executable, out / 'baseline-test-probe')
    path = work / 'element/uniform_list.mbt'
    original = path.read_text()
    old = 'else if value >= count.to_double() {\n    count\n  }'
    new = 'else if value >= count.to_double() {\n    value.to_int()\n  }'
    require(original.count(old) == 1, 'unique range clamp mutation')
    mutated = original.replace(old, new)
    path.write_text(mutated)
    (out / 'mutation.diff').write_text(''.join(difflib.unified_diff(original.splitlines(True), mutated.splitlines(True), fromfile='a/element/uniform_list.mbt', tofile='b/element/uniform_list.mbt')))
    report['mutated_source_sha256'] = baseline.digest(path)
    report['mutant'] = execute(command, work, out, 'mutant', os.environ.copy())
    if executable.exists(): shutil.copy2(executable, out / 'mutant-test-probe')
    report['baseline_passed'] = report['baseline']['returncode'] == 0
    log = (out / 'mutant.stdout').read_text() + (out / 'mutant.stderr').read_text()
    report['compiled_and_executed_rejection'] = report['mutant']['returncode'] != 0 and ('Total tests: 1' in log and 'failed: 1' in log or 'Active test at executable exit:' in log and 'pair fractional endpoint regression' in log)
    report['files'] = {str(p.relative_to(out)): {'sha256': baseline.digest(p), 'size': p.stat().st_size} for p in out.rglob('*') if p.is_file() and p.name not in ('.moon_db', '.moon-lock')}
    (out / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    require(report['baseline_passed'] and report['compiled_and_executed_rejection'], 'unit mutation not proved killed')
    print(json.dumps({'kind': report['kind'], 'baseline_passed': True, 'compiled_and_executed_rejection': True}))

if __name__ == '__main__': main()
