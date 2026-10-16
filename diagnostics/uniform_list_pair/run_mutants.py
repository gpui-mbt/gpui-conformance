#!/usr/bin/env python3
"""Execute isolated production mutations, retaining native binaries and raw failures."""
from __future__ import annotations
import argparse
import difflib
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import uuid
from compare import ROOT, baseline, compare_observations, require, validate_mutation_outcomes
from run import now
from verify import verify


def execute(command, cwd, directory, stem, environment, timeout=120):
    def limit(): resource.setrlimit(resource.RLIMIT_AS, (768 * 1024**2, 768 * 1024**2))
    started = now()
    with (directory / (stem + '.stdout')).open('wb') as stdout, (directory / (stem + '.stderr')).open('wb') as stderr:
        process = subprocess.Popen(command, cwd=cwd, env=environment, stdout=stdout, stderr=stderr, preexec_fn=limit)
        timed_out = False
        try: code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            code = process.wait()
    return {'command': command, 'cwd': str(cwd), 'started_at': started, 'finished_at': now(),
            'pid': process.pid, 'returncode': code, 'timed_out': timed_out, 'address_space_limit_bytes': 768 * 1024**2}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--core-source', type=Path, required=True)
    parser.add_argument('--suite-source', type=Path, default=ROOT)
    parser.add_argument('--core-commit', required=True)
    parser.add_argument('--suite-commit', required=True)
    parser.add_argument('--fresh-baseline-suite-commit')
    parser.add_argument('--upstream-source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    evidence = args.evidence.resolve()
    verified = verify(evidence, args.suite_source, args.upstream_source, args.core_source, args.suite_commit, args.core_commit, args.fresh_baseline_suite_commit)
    require(verified['candidate_source_bound'], 'baseline candidate must be exact source bound')
    out = args.output.resolve()
    require(out.is_relative_to(ROOT / '_build'), 'output must be under _build')
    out.mkdir(parents=True, exist_ok=False)
    work = out / 'reused-build-source'
    shutil.copytree(evidence / 'build-source', work, ignore=shutil.ignore_patterns('_build'))
    mutations_path = ROOT / 'diagnostics/uniform_list_pair/mutations.json'
    shutil.copy2(mutations_path, out / 'mutations.json')
    shutil.copy2(Path(__file__), out / 'run_mutants.py')
    mutations = json.loads(mutations_path.read_text())
    rust = json.loads((evidence / 'rust-baseline/raw.json').read_text())
    scenarios = json.loads((evidence / 'scenarios.json').read_text())
    results = []
    for name, relative, old, new in mutations:
        require(shutil.disk_usage(out).free >= 1100 * 1024**2, 'Preserve >=1GiB headroom; stop without cleanup')
        directory = out / name
        directory.mkdir()
        source = (evidence / 'build-source' / relative).read_text()
        require(source.count(old) == 1, name + ': mutation must match exactly once')
        changed = source.replace(old, new)
        (work / relative).write_text(changed)
        (directory / 'mutated-source.mbt').write_text(changed)
        (directory / 'mutation.diff').write_text(''.join(difflib.unified_diff(source.splitlines(True), changed.splitlines(True), fromfile='a/' + relative, tofile='b/' + relative)))
        inputs = {str(p.relative_to(work)): baseline.digest(p) for p in work.rglob('*') if p.is_file() and '_build' not in p.relative_to(work).parts}
        (directory / 'source-input-hashes.json').write_text(json.dumps(inputs, indent=2) + '\n')
        environment = os.environ.copy()
        token = str(uuid.uuid4())
        environment['GPUI_SCENARIOS'] = (evidence / 'scenarios.json').read_text()
        environment['GPUI_RUN_TOKEN'] = token
        record = {'mutation': name, 'path': relative, 'run_token': token, 'core_commit': args.core_commit,
                  'baseline_manifest_sha256': baseline.digest(evidence / 'manifest.json'),
                  'original_sha256': baseline.digest(evidence / 'build-source' / relative),
                  'mutated_sha256': baseline.digest(directory / 'mutated-source.mbt'),
                  'original_scenarios_sha256': baseline.digest(evidence / 'scenarios.json')}
        record['build'] = execute([shutil.which('moon'), 'build', '--target', 'native', '--deny-warn', '--verbose', 'probe'], work, directory, 'build', environment)
        if record['build']['returncode'] == 0:
            shutil.copy2(work / '_build/native/debug/build/probe/probe.exe', directory / 'candidate-probe')
            record['execution'] = execute([str(directory / 'candidate-probe')], work, directory, 'candidate', environment, timeout=60)
            if record['execution']['returncode'] == 0:
                try:
                    raw = json.loads((directory / 'candidate.stdout').read_text())
                    require(raw['run_token'] == token, 'cross-run mutant trace')
                    result = compare_observations(rust, raw, scenarios)
                    record['outcome'] = 'survived'
                    (directory / 'comparison.json').write_text(json.dumps(result, indent=2) + '\n')
                except (ValueError, KeyError, TypeError, IndexError) as error:
                    record['outcome'] = 'executed-semantic-rejection'
                    record['rejection'] = str(error)
            else:
                record['outcome'] = 'executed-runtime-rejection' if not record['execution']['timed_out'] else 'executed-timeout'
        else: record['outcome'] = 'compile-rejection-not-executed'
        record['files'] = {str(p.relative_to(directory)): {'sha256': baseline.digest(p), 'size': p.stat().st_size} for p in directory.rglob('*') if p.is_file()}
        (directory / 'manifest.json').write_text(json.dumps(record, indent=2) + '\n')
        results.append(record)
        (out / 'results.json').write_text(json.dumps({'baseline_evidence': str(evidence), 'baseline_manifest_sha256': baseline.digest(evidence / 'manifest.json'), 'mutations': results}, indent=2) + '\n')
        # Restore only the isolated scratch input, never source or baseline evidence.
        (work / relative).write_text(source)
        print(name + ': ' + record['outcome'] + ('; ' + record['rejection'] if 'rejection' in record else ''), flush=True)
    validate_mutation_outcomes(results)

if __name__ == '__main__': main()
