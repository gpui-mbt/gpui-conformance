#!/usr/bin/env python3
"""Independently recompute every executed mutation outcome from copied artifacts."""
from __future__ import annotations
import argparse
import difflib
import hashlib
import json
from pathlib import Path
from compare import baseline, load_json, require, require_semantic_match, compare_observations, validate_mutation_outcomes, CandidateOnlyContractError
from fractional_viewport import corpus as extension_corpus, compare_extension
from run import inventory, native_build_plan, native_generated_inventory
from run_mutants import classify, decode_transport
from verify import verify


def verify_mutants(directory, evidence, ordinary):
    require_semantic_match(ordinary)
    require_semantic_match(ordinary['fractional_viewport'])
    directory, evidence = Path(directory).resolve(), Path(evidence).resolve()
    parent = load_json((evidence / 'manifest.json').read_text())
    summary = load_json((directory / 'results.json').read_text())
    require(summary['evidence_kind'] == 'executed-production-engine-mutations', 'mutation evidence kind')
    require(summary['baseline_manifest_sha256'] == baseline.digest(evidence / 'manifest.json'), 'mutation ordinary-pair binding')
    descriptors = load_json((evidence / 'suite/diagnostics/anchor_pair/mutations.json').read_text())
    require((directory / 'mutations.json').read_bytes() == (evidence / 'suite/diagnostics/anchor_pair/mutations.json').read_bytes(), 'exact retained mutation definitions')
    require((directory / 'run_mutants.py').read_bytes() == (evidence / 'suite/diagnostics/anchor_pair/run_mutants.py').read_bytes(), 'exact retained mutation runner')
    require([r['mutation'] for r in summary['mutations']] == [m['name'] for m in descriptors], 'exact mutation coverage/order')
    original_inputs = {str(p.relative_to(evidence / 'build-source')): baseline.digest(p)
        for p in (evidence / 'build-source').rglob('*') if p.is_file() and '_build' not in p.relative_to(evidence / 'build-source').parts}
    rust = load_json((evidence / 'rust-baseline/raw.json').read_text())
    inputs = load_json((evidence / 'scenarios.json').read_text())
    fractional_rust = load_json((evidence / 'fractional-viewport/rust-raw.json').read_text())
    results = []
    for descriptor, saved in zip(descriptors, summary['mutations']):
        name, relative = descriptor['name'], descriptor['path']
        require(Path(name).name == name and '..' not in Path(relative).parts and not Path(relative).is_absolute(), 'safe mutation target')
        folder = directory / name
        record = load_json((folder / 'manifest.json').read_text())
        require(record == saved, 'summary and per-mutation manifest disagree')
        require(inventory(folder) == record['files'], 'complete unchanged mutation evidence')
        for path in folder.rglob('*'):
            require(not path.is_symlink() and path.resolve().is_relative_to(folder), 'unsafe mutation evidence path')
        require(record['evidence_kind'] == 'executed-production-engine-mutation' and record['path'] == relative and
                record['scope'] == descriptor['scope'] and record['intended_predicate'] == descriptor['predicate'], 'mutation identity/scope')
        require(record['core_commit'] == parent['core']['commit'] and record['baseline_manifest_sha256'] == summary['baseline_manifest_sha256'], 'mutation exact ordinary source')
        source = (evidence / 'build-source' / relative).read_text()
        require(source.count(descriptor['old']) == 1, 'mutation source anchor exactly once')
        changed = source.replace(descriptor['old'], descriptor['new'])
        require((folder / 'mutated-source.mbt').read_text() == changed, 'exact single production mutation')
        patch = ''.join(difflib.unified_diff(source.splitlines(True), changed.splitlines(True), fromfile='a/' + relative, tofile='b/' + relative))
        require((folder / 'mutation.diff').read_text() == patch, 'exact mutation diff')
        require(record['original_sha256'] == baseline.digest(evidence / 'build-source' / relative) and
                record['mutated_sha256'] == baseline.digest(folder / 'mutated-source.mbt'), 'mutation source hashes')
        expected_inputs = dict(original_inputs, **{relative: hashlib.sha256(changed.encode()).hexdigest()})
        require(load_json((folder / 'source-input-hashes.json').read_text()) == record['source_inputs_after'] == expected_inputs, 'isolated complete source inputs')
        require(record['scenarios_sha256'] == baseline.digest(evidence / 'scenarios.json'), 'unchanged ordinary corpus')
        require(record['tool_binaries'] == parent['tool_binaries'] and record['toolchain_home'] == parent['toolchain_home'], 'same native compiler/runtime')
        require(record['tool_binaries_after'] == record['tool_commands_after'] == parent['tool_binaries_after'] and record['toolchain_inputs_after'] == parent['toolchain_inputs_after'], 'mutant compiler/runtime stability')
        root = Path(summary['recorded_execution_root'])
        require(root.is_absolute() and '..' not in root.parts and record['recorded_execution_root'] == str(root), 'recorded mutant execution root')
        work = root / 'reused-build-source'
        moon = parent['tool_binaries']['moon']['path']
        for phase, flags in [('build_plan', ['--dry-run']), ('build', [])]:
            command = [moon, 'build', '--target', 'native', '--deny-warn'] + flags + ['--verbose', 'probe']
            require(record[phase]['command'] == command and record[phase]['cwd'] == str(work), 'exact mutant native build command')
        require((folder / 'candidate-probe').read_bytes().startswith(b'\x7fELF'), 'executed native ELF required')
        plan = native_build_plan((folder / 'build-plan.stdout').read_text(), record['tool_binaries'])
        require(plan == record['native_build_plan'] == parent['native_build_plan'], 'same qualified actual native pipeline')
        require(native_generated_inventory(folder / 'generated', plan) == record['generated_build_inputs'], 'actual generated native inputs changed or missing')
        require((folder / 'generated/probe/probe.exe').read_bytes() == (folder / 'candidate-probe').read_bytes(), 'generated/actually executed ELF mismatch')
        require(record['native_environment'] == {key: parent['input_environment'][key] for key in ('CC','MOON_CC','MOON_HOME','MOONBIT_NEW_NATIVE')}, 'mutant native environment differs from ordinary pair')
        def inspect(stem, phase, token, corpus, comparison_fn, rust_raw, saved_name):
            execution = record[phase]
            require(execution['command'] == [str(root / name / 'candidate-probe')] and execution['cwd'] == str(work), 'exact mutated ELF invocation')
            comparison, error, transport, candidate_only = None, None, None, None
            if execution['returncode'] == 0 and not execution['timed_out']:
                try:
                    require((folder / (stem + '.stderr')).stat().st_size == 0, 'mutant stderr')
                    raw = decode_transport(folder / (stem + '.stdout'), token, corpus)
                except (ValueError, TypeError, KeyError, IndexError, UnicodeError) as failure: transport = str(failure)
                else:
                    try:
                        comparison = comparison_fn(rust_raw, raw, corpus)
                    except CandidateOnlyContractError as failure: candidate_only = str(failure)
                    except (ValueError, TypeError, KeyError, IndexError) as failure: error = str(failure)
            if comparison is not None:
                require(load_json((folder / saved_name).read_text()) == comparison, 'mutant saved/recomputed comparison')
            return classify(record['build'], execution, comparison, error, transport, candidate_only)
        outcome = inspect('candidate', 'execution', record['run_token'], inputs, compare_observations, rust, 'comparison.json')
        fractional = inspect('fractional-candidate', 'fractional_execution', record['fractional_token'], extension_corpus(), compare_extension, fractional_rust, 'fractional-comparison.json')
        require(fractional == record['fractional_outcome'], 'fractional mutation outcome mismatch')
        if descriptor['scope'] == 'fractional-viewport-rust-pair':
            require(record['ordinary_outcome'] == outcome, 'ordinary control must pass before fractional rejection')
            outcome = 'executed-fractional-viewport-semantic-rejection' if outcome == 'survived' and fractional == 'executed-semantic-rejection' else 'fractional-control-did-not-isolate-viewport-semantics'
        if record['build_plan']['returncode'] != 0 or record['build_plan']['timed_out']:
            outcome = 'build-plan-rejection-not-semantic-kill'
        require(outcome == record['outcome'], 'recomputed executed mutation outcome')
        results.append({'mutation': name, 'scope': descriptor['scope'], 'outcome': outcome})
    validate_mutation_outcomes(results)
    return {'ordinary_pair_source_bound': True, 'mutations': results,
            'rust_paired_semantic_kills': sum(r['scope'] == 'rust-paired-semantics' for r in results),
            'separate_fractional_viewport_kills': sum(r['scope'] == 'fractional-viewport-rust-pair' for r in results),
            'compiler_or_transport_failure_kills': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('evidence', 'mutants', 'suite-source', 'upstream-source', 'core-source'): parser.add_argument('--' + name, type=Path, required=True)
    for name in ('suite-commit', 'core-commit'): parser.add_argument('--' + name, required=True)
    parser.add_argument('--baseline-suite-commit')
    args = parser.parse_args()
    ordinary = verify(args.evidence, args.suite_source, args.upstream_source, args.core_source, args.suite_commit, args.core_commit, args.baseline_suite_commit)
    print(json.dumps(verify_mutants(args.mutants, args.evidence, ordinary), indent=2))


if __name__ == '__main__': main()
