#!/usr/bin/env python3
"""Reread retained source and raw pair against independently selected Git objects."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import subprocess
from compare import load_json, ROOT, LAYER, baseline, compare_observations, require, require_semantic_match
from run import MODULE, SUITE_FILES, POLICY_FILES, OMITTED_BUILD_CACHES, TOOLCHAIN_ROOTS, inventory, production_file, validate_baseline, retained_path, native_build_plan, native_generated_inventory, require_native_environment, selected_production_paths, CORE_API_FILES, verify_core_api, verify_process_guard, DISK_FLOOR, validate_source_lineage


def git_blob(source, commit, relative):
    return subprocess.check_output(['git', 'show', commit + ':' + relative], cwd=source)


def verify(directory, suite_source, upstream_source, core_source, suite_commit, core_commit, baseline_suite_commit=None):
    directory = Path(directory).resolve()
    manifest = load_json((directory / 'manifest.json').read_text())
    require(manifest['schema_version'] == 1 and manifest['layer'] == LAYER, 'manifest identity')
    require(manifest['qualification'] == 'exact-clean-source-pair' and manifest['review_or_publication_claim'] is False, 'qualification')
    require(manifest['core_after'] == manifest['core'] and manifest['suite_after'] == manifest['suite'], 'sources changed')
    profile = load_json((ROOT / 'diagnostics/nested_deferred_pair/profile.json').read_text())
    require(core_commit == profile['candidate_commit'] and manifest['core']['tree'] == profile['candidate_tree'], 'candidate public pin')
    require(manifest['requested_core_commit'] == core_commit, 'requested candidate pin')
    require(profile['candidate_pin_status'] == 'published-exact-commit-tree', 'candidate publication pin still pending')
    for relative, expected in profile['approved_fixture_sha256'].items():
        require(baseline.digest(directory / retained_path(relative)) == expected, 'frozen fixture changed: ' + relative)
    require(manifest['platform']['system'] == 'Linux', 'native Linux candidate required')
    budget=manifest['resource_budget']
    require(budget['strict_floor_bytes']==DISK_FLOOR and budget['pair_reserve_bytes']==2*1024**3 and
        all(v > 3*1024**3 for v in budget['before_free_bytes'].values()),'preexecution pair capacity budget')
    require(manifest['preexecution_contract_sha256'] == {p: baseline.digest(directory / retained_path(p)) for p in POLICY_FILES}, 'preexecution exact policy/checker/schema/control lock')
    require(manifest['omitted_non_input_build_caches'] == list(OMITTED_BUILD_CACHES), 'unexpected omitted evidence')
    required = {'candidate-probe', 'candidate-raw.json', 'candidate.stderr', 'build.stdout', 'build.stderr',
                'build-plan.stdout', 'build-plan.stderr', 'scenarios.json', 'toolchain.txt',
                'original-core-moon.mod', 'build-source/moon.mod', 'build-source/probe/main.mbt',
                'build-source/probe/moon.pkg', 'build-source/_build/native/debug/build/probe/probe.exe',
                'rust-baseline/raw.json', 'comparison.json', 'regressions/manifest.json', 'margin-regression/manifest.json', 'flat-regression/manifest.json'}
    required |= {retained_path(p) for p in SUITE_FILES}
    required |= {'build-source/' + p for p in manifest['core_inputs']}
    required |= {'core-api/' + p for p in CORE_API_FILES}
    require(manifest['toolchain_inputs'], 'missing native toolchain inventory')
    required |= {'toolchain-inputs/' + p for p in manifest['toolchain_inputs']}
    required |= {'tool-binaries/' + name for name in ('moon', 'moonc', 'cc', 'ar')}
    require(required <= set(manifest['files']), 'missing retained pair evidence')
    for relative, metadata in manifest['files'].items():
        path = baseline.strict_file(directory, relative)
        require(not Path(relative).is_absolute() and '..' not in Path(relative).parts and not path.is_symlink()
                and path.is_file() and path.resolve().is_relative_to(directory), 'unsafe evidence path')
        require(baseline.digest(path) == metadata['sha256'] and path.stat().st_size == metadata['size'], 'changed evidence: ' + relative)
    require(inventory(directory) == manifest['files'], 'inventory must cover every retained file')
    oracle_commit = baseline_suite_commit or profile['suite_base_public_commit']
    lineage = validate_source_lineage(suite_source, suite_commit, suite_source, oracle_commit)
    require(manifest['source_lineage'] == lineage, 'independently selected oracle/pair source lineage')
    require(manifest['oracle_suite'] == manifest['oracle_suite_after'] == dict(lineage['oracle_suite'], clean=True), 'unchanged clean pinned oracle suite')
    approved = validate_baseline(directory / 'rust-baseline', suite_source, upstream_source, oracle_commit,
        recorded_execution_root=manifest['baseline']['recorded_execution_root'])
    require(manifest['baseline'] == approved, 'Rust baseline binding')
    require((directory / 'scenarios.json').read_bytes() == (directory / 'rust-baseline/scenarios.json').read_bytes(), 'same executed corpus')
    require((directory / 'build-source/moon.mod').read_text() == MODULE, 'focused module projection')
    staged_inputs = {str(p.relative_to(directory / 'build-source')) for p in (directory / 'build-source').rglob('*') if p.is_file() and '_build' not in p.relative_to(directory / 'build-source').parts}
    require(staged_inputs == set(manifest['core_inputs']) | {'moon.mod', 'probe/main.mbt', 'probe/moon.pkg'}, 'unexpected compiled source input')
    for name in ('main.mbt', 'moon.pkg'):
        require((directory / 'build-source/probe' / name).read_bytes() == (directory / 'suite/adapters/nested_deferred_moonbit' / name).read_bytes(), 'executed adapter bytes')
    for phase in ('build_plan', 'build', 'execution'):
        verify_process_guard(manifest[phase])
        require(manifest[phase]['returncode'] == 0 and manifest[phase]['timed_out'] is False, phase + ' failed')
    recorded_root = Path(manifest['recorded_execution_root'])
    require(recorded_root.is_absolute() and str(recorded_root) == str(recorded_root.resolve()) and '..' not in recorded_root.parts, 'canonical pair execution root')
    moon = manifest['tool_binaries']['moon']['path']
    require(set(manifest['tool_binaries']) == set(manifest['tool_binaries_after']) == {'moon', 'moonc', 'cc', 'ar'}, 'compiler inventory')
    for name, tool in manifest['tool_binaries'].items():
        require(Path(tool['path']).is_absolute() and tool['retained'] == 'tool-binaries/' + name, 'compiler path binding')
        require(re.fullmatch('[0-9a-f]{64}', tool['sha256']) and
                Path(tool['command_path']).is_absolute() and baseline.digest(directory / tool['retained']) == tool['sha256'] == manifest['tool_binaries_after'][name] == manifest['tool_commands_after'][name], 'retained compiler identity')
    native_inputs = manifest['toolchain_inputs']
    require(native_inputs == sorted(set(native_inputs)) and set(native_inputs) == set(manifest['toolchain_inputs_after']), 'runtime inventory shape')
    require(all(any(p == root or p.startswith(root + '/') for root in TOOLCHAIN_ROOTS) for p in native_inputs), 'unexpected runtime input root')
    require(any(p.startswith('lib/core/_build/native/release/bundle/') for p in native_inputs) and
            any(p.startswith('include/') for p in native_inputs), 'core runtime bundles and headers required')
    require({str(p.relative_to(directory / 'toolchain-inputs')) for p in (directory / 'toolchain-inputs').rglob('*') if p.is_file()} == set(native_inputs), 'complete retained runtime inventory')
    for name in native_inputs:
        require(baseline.digest(directory / 'toolchain-inputs' / name) == manifest['toolchain_inputs_after'][name], 'runtime input changed during run')
    require(manifest['input_environment']['CC'] == manifest['tool_binaries']['cc']['path'] and
            manifest['input_environment']['MOON_CC'] is None and manifest['input_environment']['MOONBIT_NEW_NATIVE'] in (None, '1') and
            manifest['input_environment']['MOON_HOME'] == manifest['toolchain_home'] and Path(manifest['toolchain_home']).is_absolute(), 'compiler/runtime environment binding')
    require_native_environment(manifest['input_environment'], manifest['tool_binaries'])
    plan = native_build_plan((directory / 'build-plan.stdout').read_text(), manifest['tool_binaries'], directory / 'build-source')
    require(plan == manifest['native_build_plan'] and set(plan['required_toolchain']) <= set(native_inputs), 'qualified direct-native pipeline/toolchain inputs')
    require(native_generated_inventory(directory / 'build-source/_build/native/debug/build', plan) == manifest['generated_build_inputs'], 'complete actual generated native build inputs')
    require(manifest['build']['command'] == [moon, 'build', '--target', 'native', '--deny-warn', '--verbose', 'probe'], 'exact build command')
    require(manifest['build_plan']['command'] == [moon, 'build', '--target', 'native', '--deny-warn', '--dry-run', '--verbose', 'probe'], 'exact build plan command')
    require(all(manifest[phase]['cwd'] == str(recorded_root / 'build-source') for phase in ('build_plan', 'build')), 'exact build source directory')
    require(manifest['execution']['command'] == [str(recorded_root / 'candidate-probe')], 'exact executed binary')
    require(manifest['execution']['cwd'] == str(recorded_root / 'build-source'), 'execution directory')
    require((directory / 'candidate-probe').read_bytes().startswith(b'\x7fELF'), 'native ELF')
    require((directory / 'candidate-probe').read_bytes() == (directory / 'build-source/_build/native/debug/build/probe/probe.exe').read_bytes(), 'build/executed binary')
    require((directory / 'candidate.stderr').stat().st_size == 0, 'candidate stderr')
    raw = load_json((directory / 'candidate-raw.json').read_text())
    require(raw['run_token'] == manifest['run_token'] == manifest['input_environment']['GPUI_RUN_TOKEN'], 'cross-run trace')
    require(manifest['input_environment']['GPUI_SCENARIOS_sha256'] == baseline.digest(directory / 'scenarios.json'), 'executed input hash')
    for source, selected, identity in ((core_source, core_commit, manifest['core']), (suite_source, suite_commit, manifest['suite'])):
        require(identity['commit'] == selected and len(selected) == 40 and identity['clean'] is True, 'selected clean source')
        tree = subprocess.check_output(['git', 'rev-parse', selected + '^{tree}'], cwd=source, text=True).strip()
        require(tree == identity['tree'], 'independent Git tree')
    require(manifest['core_inputs'] == selected_production_paths(core_source, core_commit), 'complete production source inventory')
    verify_core_api(directory, manifest, core_source, core_commit)
    for relative in manifest['core_inputs']:
        require((directory / 'build-source' / relative).read_bytes() == git_blob(core_source, core_commit, relative), 'core Git blob: ' + relative)
    require((directory / 'original-core-moon.mod').read_bytes() == git_blob(core_source, core_commit, 'moon.mod'), 'original module')
    for relative in SUITE_FILES:
        retained = (directory / retained_path(relative)).read_bytes()
        require(retained == git_blob(suite_source, suite_commit, relative), 'suite Git blob: ' + relative)
        require(retained == (ROOT / relative).read_bytes(), 'executing suite source differs from retained selected commit: ' + relative)
    comparison = compare_observations(load_json((directory / 'rust-baseline/raw.json').read_text()), raw,
        load_json((directory / 'scenarios.json').read_text()))
    if (directory / 'comparison.json').exists():
        require(comparison == load_json((directory / 'comparison.json').read_text()), 'saved comparison differs from independently recomputed result')
    from regressions import verify_regressions
    regressions = verify_regressions(directory, manifest, suite_source, upstream_source, core_source, suite_commit, core_commit)
    require(regressions == manifest['regressions'] and regressions['passed'], 'original/fractional recomputed regressions')
    from regressions import verify_margin_regression
    margin_regression = verify_margin_regression(directory, manifest, suite_source, upstream_source, core_source, suite_commit, core_commit)
    require(margin_regression == manifest['margin_regression'] and margin_regression['passed'], 'same-core margin recomputed regression')
    from regressions import verify_flat_regression
    flat_regression = verify_flat_regression(directory, manifest, suite_source, upstream_source, core_source, suite_commit, core_commit)
    require(flat_regression == manifest['flat_regression'] and flat_regression['passed'], 'same-core flat-priority recomputed regression')
    require_semantic_match(comparison)
    return dict(comparison, candidate_source_bound=True, qualification=manifest['qualification'], regressions=regressions, margin_regression=margin_regression, flat_regression=flat_regression)



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    parser.add_argument('--suite-source', type=Path, required=True)
    parser.add_argument('--upstream-source', type=Path, required=True)
    parser.add_argument('--core-source', type=Path, required=True)
    parser.add_argument('--suite-commit', required=True)
    parser.add_argument('--core-commit', required=True)
    parser.add_argument('--baseline-suite-commit', help='Independent selected baseline commit if different from pair suite commit')
    args = parser.parse_args()
    result = verify(args.evidence, args.suite_source, args.upstream_source, args.core_source, args.suite_commit, args.core_commit, args.baseline_suite_commit)
    print(json.dumps(result, indent=2))
    require_semantic_match(result)


if __name__ == '__main__': main()
