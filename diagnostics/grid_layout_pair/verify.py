#!/usr/bin/env python3
"""Reread retained source and raw pair against independently selected Git objects."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
from compare import ROOT, LAYER, baseline, compare_observations, require, require_semantic_match
from run import MODULE, SUITE_FILES, production_file, validate_baseline, retained_path


def git_blob(source, commit, relative):
    return subprocess.check_output(['git', 'show', commit + ':' + relative], cwd=source)


def verify(directory, suite_source, upstream_source, core_source, suite_commit, core_commit):
    directory = Path(directory).resolve()
    manifest = json.loads((directory / 'manifest.json').read_text())
    require(manifest['schema_version'] == 1 and manifest['layer'] == LAYER, 'manifest identity')
    require(manifest['qualification'] == 'exact-clean-source-pair' and manifest['review_or_publication_claim'] is False, 'qualification')
    require(manifest['core_after'] == manifest['core'] and manifest['suite_after'] == manifest['suite'], 'sources changed')
    profile = json.loads((ROOT / 'diagnostics/grid_layout_pair/profile.json').read_text())
    require(core_commit == profile['candidate_commit'] and manifest['core']['tree'] == profile['candidate_tree'], 'candidate public pin')
    require(manifest['requested_core_commit'] == core_commit, 'requested candidate pin')
    required = {'candidate-probe', 'candidate-raw.json', 'candidate.stderr', 'build.stdout', 'build.stderr',
                'build-plan.stdout', 'build-plan.stderr', 'scenarios.json', 'toolchain.txt',
                'original-core-moon.mod', 'build-source/moon.mod', 'build-source/probe/main.mbt',
                'build-source/probe/moon.pkg', 'build-source/_build/native/debug/build/probe/probe.exe',
                'rust-baseline/raw.json'}
    required |= {retained_path(p) for p in SUITE_FILES}
    required |= {'build-source/' + p for p in manifest['core_inputs']}
    require(manifest['toolchain_inputs'], 'missing native toolchain inventory')
    required |= {'toolchain-inputs/' + p for p in manifest['toolchain_inputs']}
    require(required <= set(manifest['files']), 'missing retained pair evidence')
    for relative, metadata in manifest['files'].items():
        path = directory / relative
        require(not Path(relative).is_absolute() and '..' not in Path(relative).parts and not path.is_symlink()
                and path.is_file() and path.resolve().is_relative_to(directory), 'unsafe evidence path')
        require(baseline.digest(path) == metadata['sha256'] and path.stat().st_size == metadata['size'], 'changed evidence: ' + relative)
    approved = validate_baseline(directory / 'rust-baseline', suite_source, upstream_source, suite_commit,
        recorded_execution_root=manifest['baseline']['recorded_execution_root'])
    require(manifest['baseline'] == approved, 'Rust baseline binding')
    require((directory / 'scenarios.json').read_bytes() == (directory / 'rust-baseline/scenarios.json').read_bytes(), 'same executed corpus')
    require((directory / 'build-source/moon.mod').read_text() == MODULE, 'focused module projection')
    staged_inputs = {str(p.relative_to(directory / 'build-source')) for p in (directory / 'build-source').rglob('*') if p.is_file() and '_build' not in p.relative_to(directory / 'build-source').parts}
    require(staged_inputs == set(manifest['core_inputs']) | {'moon.mod', 'probe/main.mbt', 'probe/moon.pkg'}, 'unexpected compiled source input')
    for name in ('main.mbt', 'moon.pkg'):
        require((directory / 'build-source/probe' / name).read_bytes() == (directory / 'suite/adapters/grid_layout_moonbit' / name).read_bytes(), 'executed adapter bytes')
    for phase in ('build_plan', 'build', 'execution'):
        require(manifest[phase]['returncode'] == 0 and manifest[phase]['timed_out'] is False, phase + ' failed')
    recorded_root = Path(manifest['recorded_execution_root'])
    require(recorded_root.is_absolute() and str(recorded_root) == str(recorded_root.resolve()) and '..' not in recorded_root.parts, 'canonical pair execution root')
    moon = manifest['tool_binaries']['moon']['path']
    require(manifest['build']['command'] == [moon, 'build', '--target', 'native', '--deny-warn', '--verbose', 'probe'], 'exact build command')
    require(manifest['build_plan']['command'] == [moon, 'build', '--target', 'native', '--deny-warn', '--dry-run', '--verbose', 'probe'], 'exact build plan command')
    require(all(manifest[phase]['cwd'] == str(recorded_root / 'build-source') for phase in ('build_plan', 'build')), 'exact build source directory')
    require(manifest['execution']['command'] == [str(recorded_root / 'candidate-probe')], 'exact executed binary')
    require(manifest['execution']['cwd'] == str(recorded_root / 'build-source'), 'execution directory')
    require((directory / 'candidate-probe').read_bytes().startswith(b'\x7fELF'), 'native ELF')
    require((directory / 'candidate-probe').read_bytes() == (directory / 'build-source/_build/native/debug/build/probe/probe.exe').read_bytes(), 'build/executed binary')
    require((directory / 'candidate.stderr').stat().st_size == 0, 'candidate stderr')
    raw = json.loads((directory / 'candidate-raw.json').read_text())
    require(raw['run_token'] == manifest['run_token'] == manifest['input_environment']['GPUI_RUN_TOKEN'], 'cross-run trace')
    require(manifest['input_environment']['GPUI_SCENARIOS_sha256'] == baseline.digest(directory / 'scenarios.json'), 'executed input hash')
    for source, selected, identity in ((core_source, core_commit, manifest['core']), (suite_source, suite_commit, manifest['suite'])):
        require(identity['commit'] == selected and len(selected) == 40 and identity['clean'] is True, 'selected clean source')
        tree = subprocess.check_output(['git', 'rev-parse', selected + '^{tree}'], cwd=source, text=True).strip()
        require(tree == identity['tree'], 'independent Git tree')
    paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', core_commit], cwd=core_source, text=True).splitlines()
    require(manifest['core_inputs'] == sorted(p for p in paths if production_file(p)), 'complete production source inventory')
    for relative in manifest['core_inputs']:
        require((directory / 'build-source' / relative).read_bytes() == git_blob(core_source, core_commit, relative), 'core Git blob: ' + relative)
    require((directory / 'original-core-moon.mod').read_bytes() == git_blob(core_source, core_commit, 'moon.mod'), 'original module')
    for relative in SUITE_FILES:
        require((directory / retained_path(relative)).read_bytes() == git_blob(suite_source, suite_commit, relative), 'suite Git blob: ' + relative)
    comparison = compare_observations(json.loads((directory / 'rust-baseline/raw.json').read_text()), raw,
        json.loads((directory / 'scenarios.json').read_text()),
        json.loads((directory / 'rust-baseline/retained/diagnostics/grid_layout/witnesses.json').read_text()))
    if (directory / 'comparison.json').exists():
        require(comparison == json.loads((directory / 'comparison.json').read_text()), 'saved comparison differs from independently recomputed result')
    return dict(comparison, candidate_source_bound=True, qualification=manifest['qualification'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    parser.add_argument('--suite-source', type=Path, required=True)
    parser.add_argument('--upstream-source', type=Path, required=True)
    parser.add_argument('--core-source', type=Path, required=True)
    parser.add_argument('--suite-commit', required=True)
    parser.add_argument('--core-commit', required=True)
    args = parser.parse_args()
    result = verify(args.evidence, args.suite_source, args.upstream_source, args.core_source, args.suite_commit, args.core_commit)
    print(json.dumps(result, indent=2))
    require_semantic_match(result)


if __name__ == '__main__': main()
