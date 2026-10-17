#!/usr/bin/env python3
"""Execute real isolated production mutations, separate from checker corruptions."""
from __future__ import annotations
import argparse
import difflib
import json
import os
from pathlib import Path
import shutil
import uuid
from compare import ROOT, baseline, compare_observations, require, require_semantic_match, validate_mutation_outcomes
from run import execute, inventory
from verify import verify


def classify(build, execution, comparison=None, validation_error=None):
    if build['returncode'] != 0: return 'compile-rejection-not-executed'
    if execution['timed_out']: return 'executed-timeout-not-semantic-kill'
    if execution['returncode'] != 0: return 'executed-runtime-rejection-not-semantic-kill'
    if validation_error is not None or comparison is not None and not comparison['passed']: return 'executed-semantic-rejection'
    return 'survived'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--core-source', type=Path, required=True)
    parser.add_argument('--suite-source', type=Path, default=ROOT)
    parser.add_argument('--core-commit', required=True)
    parser.add_argument('--suite-commit', required=True)
    parser.add_argument('--upstream-source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    evidence = args.evidence.resolve()
    clean_pair = verify(evidence, args.suite_source, args.upstream_source, args.core_source, args.suite_commit, args.core_commit)
    require_semantic_match(clean_pair)  # A pre-existing mismatch cannot kill a mutant.
    out = args.output.resolve()
    require(out.is_relative_to(ROOT / '_build'), 'output must be a new ignored _build directory')
    out.mkdir(parents=True, exist_ok=False)
    work = out / 'reused-build-source'
    shutil.copytree(evidence / 'build-source', work, ignore=shutil.ignore_patterns('_build'))
    shutil.copy2(ROOT / 'diagnostics/grid_layout_pair/mutations.json', out / 'mutations.json')
    shutil.copy2(Path(__file__), out / 'run_mutants.py')
    mutations = json.loads((out / 'mutations.json').read_text())
    rust = json.loads((evidence / 'rust-baseline/raw.json').read_text())
    corpus = json.loads((evidence / 'scenarios.json').read_text())
    witnesses = json.loads((evidence / 'rust-baseline/retained/diagnostics/grid_layout/witnesses.json').read_text())
    results = []
    for mutation in mutations:
        name, relative, old, new = (mutation[key] for key in ('name', 'path', 'old', 'new'))
        require(shutil.disk_usage(out).free >= 1100 * 1024**2, 'Preserve >=1GiB free; stop without deleting evidence')
        directory = out / name
        directory.mkdir()
        source = (evidence / 'build-source' / relative).read_text()
        require(source.count(old) == 1, name + ': mutation must match exactly once')
        changed = source.replace(old, new)
        (work / relative).write_text(changed)
        (directory / 'mutated-source.mbt').write_text(changed)
        (directory / 'mutation.diff').write_text(''.join(difflib.unified_diff(source.splitlines(True), changed.splitlines(True), fromfile='a/' + relative, tofile='b/' + relative)))
        (directory / 'source-input-hashes.json').write_text(json.dumps({str(p.relative_to(work)): baseline.digest(p) for p in work.rglob('*') if p.is_file() and '_build' not in p.relative_to(work).parts}, indent=2) + '\n')
        environment = os.environ.copy()
        token = str(uuid.uuid4())
        environment.update(GPUI_SCENARIOS=(evidence / 'scenarios.json').read_text(), GPUI_RUN_TOKEN=token)
        record = {'mutation': name, 'path': relative, 'run_token': token, 'core_commit': args.core_commit,
            'evidence_kind': 'executed-production-engine-mutation', 'intended_predicate': mutation['predicate'],
            'baseline_manifest_sha256': baseline.digest(evidence / 'manifest.json'),
            'original_sha256': baseline.digest(evidence / 'build-source' / relative),
            'mutated_sha256': baseline.digest(directory / 'mutated-source.mbt'),
            'scenarios_sha256': baseline.digest(evidence / 'scenarios.json')}
        record['build'] = execute([shutil.which('moon'), 'build', '--target', 'native', '--deny-warn', '--verbose', 'probe'], work, directory, 'build', environment)
        comparison, error = None, None
        if record['build']['returncode'] == 0:
            shutil.copy2(work / '_build/native/debug/build/probe/probe.exe', directory / 'candidate-probe')
            record['execution'] = execute([str(directory / 'candidate-probe')], work, directory, 'candidate', environment, timeout=60)
            if record['execution']['returncode'] == 0 and not record['execution']['timed_out']:
                raw = json.loads((directory / 'candidate.stdout').read_text())
                require(raw['run_token'] == token, 'mutant cross-run trace')
                try:
                    comparison = compare_observations(rust, raw, corpus, witnesses)
                    (directory / 'comparison.json').write_text(json.dumps(comparison, indent=2) + '\n')
                except (ValueError, KeyError, TypeError, IndexError) as rejection:
                    error = str(rejection)
                    record['semantic_rejection'] = error
        record['outcome'] = classify(record['build'], record.get('execution'), comparison, error)
        record['files'] = inventory(directory)
        (directory / 'manifest.json').write_text(json.dumps(record, indent=2) + '\n')
        results.append(record)
        (out / 'results.json').write_text(json.dumps({'evidence_kind': 'executed-production-engine-mutations', 'baseline_manifest_sha256': baseline.digest(evidence / 'manifest.json'), 'mutations': results}, indent=2) + '\n')
        (work / relative).write_text(source)  # Restore isolated mutation input only.
        print(name + ': ' + record['outcome'], flush=True)
    validate_mutation_outcomes(results)


if __name__ == '__main__': main()
