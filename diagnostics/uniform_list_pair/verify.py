#!/usr/bin/env python3
"""Independently reread pair bytes and optionally bind them to exact Git objects."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
from compare import ROOT, baseline, compare_observations, equal, require
from run import MODULE, SUITE_FILES, ALL_SUITE_FILES, production_file, validate_baseline, suite_retained_path


def git_blob(source, commit, relative):
    return subprocess.check_output(['git', 'show', commit + ':' + relative], cwd=source)


def check_identity(source, identity):
    tree = subprocess.check_output(['git', 'rev-parse', identity['commit'] + '^{tree}'], cwd=source, text=True).strip()
    equal(tree, identity['tree'], 'independent Git tree')


def verify(directory, suite_source, upstream_source, core_source=None, suite_commit=None, core_commit=None, fresh_baseline_suite_commit=None):
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text())
    require(manifest['schema_version'] in (1, 2), 'manifest schema')
    suite_files = ALL_SUITE_FILES if manifest['schema_version'] == 2 else SUITE_FILES
    equal(manifest['layer'], 'compiled-uniform-list-pair', 'manifest layer')
    equal(manifest['review_or_publication_claim'], False, 'review/publication overclaim')
    require(manifest['qualification'] in ('unqualified-checkout', 'exact-clean-local-source-pair'), 'qualification')
    equal(manifest['core_after'], manifest['core'], 'core changed during run')
    equal(manifest['suite_after'], manifest['suite'], 'suite changed during run')
    required = {'candidate-probe', 'candidate-raw.json', 'candidate.stderr', 'build.stdout', 'build.stderr',
                'scenarios.json', 'toolchain.txt', 'original-core-moon.mod', 'build-source/moon.mod'}
    required |= {suite_retained_path(p) for p in suite_files}
    required |= {'build-source/' + p for p in manifest['core_inputs']}
    if 'toolchain_inputs' in manifest:
        required |= {'toolchain-inputs/' + p for p in manifest['toolchain_inputs']}
        required |= {'build-plan.stdout', 'build-plan.stderr'}
        require(manifest['toolchain_inputs'], 'missing toolchain inputs')
        equal(manifest['input_environment']['GPUI_RUN_TOKEN'], manifest['run_token'], 'environment run token')
        equal(manifest['input_environment']['GPUI_SCENARIOS_sha256'], baseline.digest(directory / 'scenarios.json'), 'environment input bytes')
    required |= {'build-source/probe/main.mbt', 'build-source/probe/moon.pkg'}
    require(required <= set(manifest['files']), 'missing retained evidence')
    for relative, metadata in manifest['files'].items():
        path = directory / relative
        require(not Path(relative).is_absolute() and '..' not in Path(relative).parts and not path.is_symlink()
                and path.is_file() and path.resolve().is_relative_to(directory.resolve()), 'unsafe evidence path')
        equal(baseline.digest(path), metadata['sha256'], 'retained hash ' + relative)
        equal(path.stat().st_size, metadata['size'], 'retained size ' + relative)
    require((manifest.get('baseline_mode', 'approved-retained') == 'fresh-source-bound') == (fresh_baseline_suite_commit is not None), 'explicit fresh baseline binding required')
    if fresh_baseline_suite_commit is not None:
        equal(fresh_baseline_suite_commit, suite_commit, 'fresh pair suite selection')
    pin = validate_baseline(directory / 'rust-baseline', suite_source, upstream_source, fresh_baseline_suite_commit)
    equal(manifest['approved_baseline'], pin, 'approved baseline binding')
    equal((directory / 'scenarios.json').read_bytes(), (directory / 'rust-baseline/scenarios.json').read_bytes(), 'executed input bytes')
    equal((directory / 'build-source/moon.mod').read_text(), MODULE, 'focused module projection')
    for filename in ('main.mbt', 'moon.pkg'):
        equal((directory / 'build-source/probe' / filename).read_bytes(),
              (directory / 'suite/adapters/uniform_list_moonbit' / filename).read_bytes(), 'adapter build bytes')
    for phase in ('build', 'execution'):
        equal(manifest[phase]['returncode'], 0, phase + ' failure')
        equal(manifest[phase]['timed_out'], False, phase + ' timeout')
    require('--target' in manifest['build']['command'] and 'native' in manifest['build']['command'] and '--deny-warn' in manifest['build']['command'], 'build target')
    require((directory / 'candidate-probe').read_bytes().startswith(b'\x7fELF'), 'native executable not retained')
    require((directory / 'candidate.stderr').stat().st_size == 0, 'candidate stderr')
    equal((directory / 'candidate-probe').read_bytes(),
          (directory / 'build-source/_build/native/debug/build/probe/probe.exe').read_bytes(), 'executed compiled output')
    raw = json.loads((directory / 'candidate-raw.json').read_text())
    equal(raw['run_token'], manifest['run_token'], 'cross-run candidate trace')
    source_bound = False
    if manifest['qualification'] == 'exact-clean-local-source-pair':
        require(core_source is not None and core_commit is not None and suite_commit is not None,
                'independently selected source paths and exact commits required')
        equal(manifest['core']['clean'], True, 'dirty core')
        equal(manifest['suite']['clean'], True, 'dirty suite')
        equal(manifest['core']['commit'], core_commit, 'selected core pin')
        equal(manifest['suite']['commit'], suite_commit, 'selected suite pin')
        equal(manifest['requested_core_commit'], core_commit, 'build core pin')
        check_identity(core_source, manifest['core'])
        check_identity(suite_source, manifest['suite'])
        paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', core_commit], cwd=core_source, text=True).splitlines()
        equal(manifest['core_inputs'], sorted(p for p in paths if production_file(p)), 'complete core source inventory')
        for relative in manifest['core_inputs']:
            equal((directory / 'build-source' / relative).read_bytes(), git_blob(core_source, core_commit, relative), 'core Git blob ' + relative)
        equal((directory / 'original-core-moon.mod').read_bytes(), git_blob(core_source, core_commit, 'moon.mod'), 'original core module')
        for relative in suite_files:
            equal((directory / suite_retained_path(relative)).read_bytes(), git_blob(suite_source, suite_commit, relative), 'suite Git blob ' + relative)
        source_bound = True
    result = compare_observations(json.loads((directory / 'rust-baseline/raw.json').read_text()), raw, json.loads((directory / 'scenarios.json').read_text()))
    result['candidate_source_bound'] = source_bound
    result['qualification'] = manifest['qualification']
    result['review_or_publication_claim'] = False
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    parser.add_argument('--suite-source', type=Path, required=True)
    parser.add_argument('--upstream-source', type=Path, required=True)
    parser.add_argument('--core-source', type=Path)
    parser.add_argument('--suite-commit')
    parser.add_argument('--core-commit')
    parser.add_argument('--fresh-baseline-suite-commit')
    args = parser.parse_args()
    print(json.dumps(verify(args.evidence, args.suite_source, args.upstream_source, args.core_source, args.suite_commit, args.core_commit, args.fresh_baseline_suite_commit), indent=2))

if __name__ == '__main__': main()
