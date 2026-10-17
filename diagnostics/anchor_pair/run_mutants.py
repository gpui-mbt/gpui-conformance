#!/usr/bin/env python3
"""Build/run isolated production mutations only after a source-bound pair passes."""
from __future__ import annotations
import argparse
import difflib
import json
import os
from pathlib import Path
import shutil
import uuid
from compare import load_json, ROOT, CANDIDATE_LAYER, CandidateOnlyContractError, baseline, compare_observations, validate_schema, require, require_semantic_match, validate_mutation_outcomes
from run import execute, inventory, native_build_plan, retain_native_generated
from verify import verify


def classify(build, execution, comparison=None, validation_error=None, transport_error=None, candidate_only_error=None):
    if build['returncode'] != 0 or build['timed_out']: return 'compile-rejection-not-executed'
    if execution is None: return 'execution-missing-not-semantic-kill'
    if execution['timed_out']: return 'executed-timeout-not-semantic-kill'
    if execution['returncode'] != 0: return 'executed-runtime-rejection-not-semantic-kill'
    if transport_error is not None: return 'executed-transport-rejection-not-semantic-kill'
    if candidate_only_error is not None: return 'executed-candidate-only-contract-rejection'
    if validation_error is not None or comparison is not None and not comparison['passed']: return 'executed-semantic-rejection'
    return 'survived'


def decode_transport(path, token, corpus):
    raw = load_json(path.read_text())
    require(isinstance(raw, dict) and raw.get('schema_version') == 1 and raw.get('layer') == CANDIDATE_LAYER and
            raw.get('fixture') == 'font-free-bounded-anchor' and raw.get('run_token') == token and raw.get('input') == corpus,
            'mutant transport identity/input/token')
    require(isinstance(raw.get('cases'), list) and [c.get('id') for c in raw['cases']] == [c['id'] for c in corpus['cases']],
            'mutant transport case coverage')
    validate_schema(raw, ROOT / 'diagnostics/anchor_pair/raw.schema.json')
    return raw


def source_hashes(work):
    return {str(p.relative_to(work)): baseline.digest(p) for p in sorted(work.rglob('*'))
            if p.is_file() and '_build' not in p.relative_to(work).parts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--core-source', type=Path, required=True)
    parser.add_argument('--suite-source', type=Path, default=ROOT)
    parser.add_argument('--core-commit', required=True)
    parser.add_argument('--suite-commit', required=True)
    parser.add_argument('--upstream-source', type=Path, required=True)
    parser.add_argument('--baseline-suite-commit')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    evidence = args.evidence.resolve()
    clean_pair = verify(evidence, args.suite_source, args.upstream_source, args.core_source, args.suite_commit,
                        args.core_commit, args.baseline_suite_commit)
    require_semantic_match(clean_pair)  # A pre-existing mismatch cannot kill a mutant.
    original = load_json((evidence / 'manifest.json').read_text())
    tools = original['tool_binaries']
    moon_home = Path(original['toolchain_home'])
    for name, tool in tools.items():
        require(baseline.digest(Path(tool['path'])) == tool['sha256'], 'mutant compiler differs from ordinary pair: ' + name)
    for name in original['toolchain_inputs']:
        require(baseline.digest(moon_home / name) == original['toolchain_inputs_after'][name], 'mutant runtime differs from ordinary pair')
    out = args.output.resolve()
    require(out.is_relative_to(ROOT / '_build'), 'output must be a new ignored _build directory')
    out.mkdir(parents=True, exist_ok=False)
    work = out / 'reused-build-source'
    shutil.copytree(evidence / 'build-source', work, ignore=shutil.ignore_patterns('_build'))
    shutil.copy2(ROOT / 'diagnostics/anchor_pair/mutations.json', out / 'mutations.json')
    shutil.copy2(Path(__file__), out / 'run_mutants.py')
    mutations = load_json((out / 'mutations.json').read_text())
    rust = load_json((evidence / 'rust-baseline/raw.json').read_text())
    corpus = load_json((evidence / 'scenarios.json').read_text())
    originals = source_hashes(work)
    results = []
    for mutation in mutations:
        name, relative, old, new = (mutation[key] for key in ('name', 'path', 'old', 'new'))
        require(shutil.disk_usage(out).free >= 1100 * 1024**2, 'Preserve >=1GiB free; stop without deleting evidence')
        require(source_hashes(work) == originals, 'mutations must be isolated, starting from identical production source')
        directory = out / name
        directory.mkdir()
        source = (evidence / 'build-source' / relative).read_text()
        require(source.count(old) == 1, name + ': mutation must match exactly once')
        changed = source.replace(old, new)
        (work / relative).write_text(changed)
        (directory / 'mutated-source.mbt').write_text(changed)
        (directory / 'mutation.diff').write_text(''.join(difflib.unified_diff(source.splitlines(True), changed.splitlines(True), fromfile='a/' + relative, tofile='b/' + relative)))
        before = source_hashes(work)
        (directory / 'source-input-hashes.json').write_text(json.dumps(before, indent=2) + '\n')
        environment = os.environ.copy()
        token = str(uuid.uuid4())
        environment.update(GPUI_SCENARIOS=(evidence / 'scenarios.json').read_text(), GPUI_RUN_TOKEN=token,
                           CC=tools['cc']['path'], MOON_HOME=str(moon_home))
        environment.pop('MOON_CC', None)
        if original['input_environment']['MOONBIT_NEW_NATIVE'] is None: environment.pop('MOONBIT_NEW_NATIVE', None)
        else: environment['MOONBIT_NEW_NATIVE'] = original['input_environment']['MOONBIT_NEW_NATIVE']
        record = {'mutation': name, 'path': relative, 'run_token': token, 'core_commit': args.core_commit,
            'scope': mutation['scope'],
            'evidence_kind': 'executed-production-engine-mutation', 'intended_predicate': mutation['predicate'],
            'recorded_execution_root': str(out), 'native_environment': {key: environment.get(key) for key in ('CC','MOON_CC','MOON_HOME','MOONBIT_NEW_NATIVE')}, 'tool_binaries': tools, 'toolchain_home': str(moon_home),
            'baseline_manifest_sha256': baseline.digest(evidence / 'manifest.json'),
            'original_sha256': baseline.digest(evidence / 'build-source' / relative),
            'mutated_sha256': baseline.digest(directory / 'mutated-source.mbt'),
            'scenarios_sha256': baseline.digest(evidence / 'scenarios.json')}
        record['build_plan'] = execute([tools['moon']['path'], 'build', '--target', 'native', '--deny-warn', '--dry-run', '--verbose', 'probe'], work, directory, 'build-plan', environment)
        record['native_build_plan'] = native_build_plan((directory / 'build-plan.stdout').read_text(), tools)
        require(record['native_build_plan'] == original['native_build_plan'], 'mutant native pipeline differs from ordinary pair')
        record['build'] = execute([tools['moon']['path'], 'build', '--target', 'native', '--deny-warn', '--verbose', 'probe'], work, directory, 'build', environment)
        comparison, error, transport_error, candidate_only_error = None, None, None, None
        if record['build']['returncode'] == 0 and not record['build']['timed_out']:
            shutil.copy2(work / '_build/native/debug/build/probe/probe.exe', directory / 'candidate-probe')
            record['generated_build_inputs'] = retain_native_generated(work / '_build/native/debug/build', directory / 'generated', record['native_build_plan'])
            record['execution'] = execute([str(directory / 'candidate-probe')], work, directory, 'candidate', environment, timeout=60)
            if record['execution']['returncode'] == 0 and not record['execution']['timed_out']:
                try:
                    require((directory / 'candidate.stderr').stat().st_size == 0, 'mutant stderr is not empty')
                    raw = decode_transport(directory / 'candidate.stdout', token, corpus)
                except (ValueError, KeyError, TypeError, IndexError, UnicodeError) as failure:
                    transport_error = str(failure)
                    record['transport_rejection'] = transport_error
                else:
                    try:
                        comparison = compare_observations(rust, raw, corpus)
                        (directory / 'comparison.json').write_text(json.dumps(comparison, indent=2) + '\n')
                    except CandidateOnlyContractError as rejection:
                        candidate_only_error = str(rejection)
                        record['candidate_only_contract_rejection'] = candidate_only_error
                    except (ValueError, KeyError, TypeError, IndexError) as rejection:
                        error = str(rejection)
                        record['semantic_rejection'] = error
        if record.get('execution', {}).get('returncode') == 0 and not record['execution']['timed_out']:
            from fractional_viewport import corpus as extension_corpus, compare_extension
            ext_inputs = extension_corpus()
            ext_token = str(uuid.uuid4())
            ext_environment = environment.copy()
            ext_environment.update(GPUI_SCENARIOS=json.dumps(ext_inputs), GPUI_RUN_TOKEN=ext_token)
            record['fractional_token'] = ext_token
            record['fractional_execution'] = execute([str(directory / 'candidate-probe')], work, directory, 'fractional-candidate', ext_environment, timeout=60)
            ext_comparison, ext_error, ext_transport = None, None, None
            if record['fractional_execution']['returncode'] == 0 and not record['fractional_execution']['timed_out']:
                try:
                    require((directory / 'fractional-candidate.stderr').stat().st_size == 0, 'fractional mutant stderr')
                    ext_raw = decode_transport(directory / 'fractional-candidate.stdout', ext_token, ext_inputs)
                except (ValueError, KeyError, TypeError, IndexError, UnicodeError) as failure:
                    ext_transport = str(failure)
                    record['fractional_transport_rejection'] = ext_transport
                else:
                    try:
                        ext_comparison = compare_extension(load_json((evidence / 'fractional-viewport/rust-raw.json').read_text()), ext_raw, ext_inputs)
                        (directory / 'fractional-comparison.json').write_text(json.dumps(ext_comparison, indent=2) + '\n')
                    except (ValueError, KeyError, TypeError, IndexError) as failure:
                        ext_error = str(failure)
                        record['fractional_semantic_rejection'] = ext_error
            record['fractional_outcome'] = classify(record['build'], record['fractional_execution'], ext_comparison, ext_error, ext_transport)
        record['tool_binaries_after'] = {name: baseline.digest(Path(tool['path'])) for name, tool in tools.items()}
        record['tool_commands_after'] = {name: baseline.digest(Path(tool['command_path'])) for name, tool in tools.items()}
        record['toolchain_inputs_after'] = {name: baseline.digest(moon_home / name) for name in original['toolchain_inputs']}
        require(record['tool_binaries_after'] == record['tool_commands_after'] == original['tool_binaries_after'] and
                record['toolchain_inputs_after'] == original['toolchain_inputs_after'], 'mutant compiler/runtime changed during execution')
        record['source_inputs_after'] = source_hashes(work)
        require(record['source_inputs_after'] == before, 'mutant source changed during build/run')
        record['outcome'] = classify(record['build'], record.get('execution'), comparison, error, transport_error, candidate_only_error)
        if mutation['scope'] == 'fractional-viewport-rust-pair':
            ordinary_outcome = record['outcome']
            record['ordinary_outcome'] = ordinary_outcome
            record['outcome'] = ('executed-fractional-viewport-semantic-rejection'
                if ordinary_outcome == 'survived' and record.get('fractional_outcome') == 'executed-semantic-rejection'
                else 'fractional-control-did-not-isolate-viewport-semantics')
        if record['build_plan']['returncode'] != 0 or record['build_plan']['timed_out']:
            record['outcome'] = 'build-plan-rejection-not-semantic-kill'
        record['files'] = inventory(directory)
        (directory / 'manifest.json').write_text(json.dumps(record, indent=2) + '\n')
        results.append(record)
        (out / 'results.json').write_text(json.dumps({'evidence_kind': 'executed-production-engine-mutations',
            'recorded_execution_root': str(out), 'baseline_manifest_sha256': baseline.digest(evidence / 'manifest.json'),
            'mutations': results}, indent=2) + '\n')
        (work / relative).write_text(source)  # Restore only this isolated mutation input.
        print(name + ': ' + record['outcome'], flush=True)
    validate_mutation_outcomes(results)


if __name__ == '__main__': main()
