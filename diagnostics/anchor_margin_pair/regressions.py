#!/usr/bin/env python3
"""Run the frozen anchor observers against the margin pair's exact native core.

This is a new, scoped provenance wrapper. It never changes the original pair's
published core pin, original observer code, corpus, schemas, or numeric policy, and never
calls the original public-pin runner or verifier entry points. The original
source-bound Rust verifier, semantic comparator and separate fractional-viewport
runner/verifier remain the authorities. Native provenance uses the same new
scoped build-plan helpers as the enclosing margin pair.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from types import SimpleNamespace
import uuid

ROOT = Path(__file__).resolve().parents[2]
LAYER = 'supplemental-same-core-anchor-regressions'
QUALIFICATION = 'same-source-bound-core-frozen-anchor-observers'
ORIGINAL_COUNTS = {'cases': 24, 'compared_operations': 53, 'paired_clicks': 5}
FRACTIONAL_COUNTS = {'cases': 2, 'compared_operations': 8, 'paired_clicks': 4}
DISK_FLOOR = 1024 ** 3
PROFILE = 'diagnostics/anchor_margin_pair/profile.json'


def require(condition, message):
    if not condition:
        raise ValueError(message)


@contextmanager
def original_modules():
    """Bind legacy absolute imports only for the duration of legacy calls.

    Loading by filename avoids accidentally importing the new same-named
    margin modules. Restoring even partially initialized aliases is essential:
    the enclosing margin runner and its controls continue after this scope.
    """
    names = ('compare', 'run', 'fractional_viewport', 'verify')
    missing = object()
    saved = {name: sys.modules.get(name, missing) for name in names}
    loaded = {}
    try:
        # The new scoped runner owns the native ABI contract for the new core.
        # Its supported imports may grow without touching frozen observers.
        for name in ('compare', 'run'):
            path = ROOT / 'diagnostics/anchor_margin_pair' / (name + '.py')
            spec = importlib.util.spec_from_file_location('_scoped_anchor_' + name, path)
            require(spec is not None and spec.loader is not None, 'cannot load scoped native helper: ' + name)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            if name == 'run':
                loaded['native'] = module
        for name in names:
            path = ROOT / 'diagnostics/anchor_pair' / (name + '.py')
            spec = importlib.util.spec_from_file_location('_frozen_anchor_' + name, path)
            require(spec is not None and spec.loader is not None, 'cannot load frozen observer: ' + name)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            loaded[name] = module
        yield SimpleNamespace(**loaded)
    finally:
        for name in names:
            if saved[name] is missing:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = saved[name]


def retained_path(relative):
    return 'suite/workflows/' + Path(relative).name if relative.startswith('.github/workflows/') else 'suite/' + relative


def git_blob(source, commit, relative):
    return subprocess.check_output(['git', 'show', commit + ':' + relative], cwd=source)


def _safe_tree(directory):
    directory = Path(directory)
    require(directory.is_dir() and not directory.is_symlink(), 'regression evidence directory')
    for path in directory.rglob('*'):
        require(not path.is_symlink() and path.resolve().is_relative_to(directory.resolve()), 'unsafe regression evidence path')
        require(path.is_dir() or path.is_file(), 'unsupported regression evidence entry')


def _source_inventory(stage, old):
    _safe_tree(stage)
    return {str(path.relative_to(stage)): old.compare.baseline.digest(path)
            for path in sorted(stage.rglob('*'))
            if path.is_file() and '_build' not in path.relative_to(stage).parts}


def _profile(pair, old, suite_source=None, suite_commit=None):
    path = pair / retained_path(PROFILE)
    require(path.read_bytes() == (ROOT / PROFILE).read_bytes(), 'regression scoped profile differs from executing verifier')
    if suite_source is not None:
        require(path.read_bytes() == git_blob(suite_source, suite_commit, PROFILE), 'regression scoped profile Git blob')
    profile = old.compare.load_json(path.read_text())
    require(profile['original_regression'] == ORIGINAL_COUNTS and profile['fractional_regression'] == FRACTIONAL_COUNTS,
            'regression immutable count policy')
    return profile


def _observer_binding(pair, profile, old, suite_source=None, suite_commit=None):
    """Bind every original fixture, including the modules executing this scope."""
    files = sorted(set(old.run.SUITE_FILES) | set(old.compare.baseline.RETAIN))
    require(len(files) == 26, 'complete frozen original observer inventory')
    result = {}
    for relative in files:
        retained = pair / retained_path(relative)
        expected = profile['approved_fixture_sha256'][relative]
        require(old.compare.baseline.digest(retained) == expected, 'changed frozen regression fixture: ' + relative)
        require(retained.read_bytes() == (ROOT / relative).read_bytes(), 'executing frozen observer differs: ' + relative)
        if suite_source is not None:
            require(retained.read_bytes() == git_blob(suite_source, suite_commit, relative), 'regression observer Git blob: ' + relative)
        result[relative] = expected
    return result


def _native_helper_binding(pair, old, suite_source=None, suite_commit=None):
    result = {}
    for name in ('compare.py', 'run.py', 'regressions.py'):
        relative = 'diagnostics/anchor_margin_pair/' + name
        retained = pair / retained_path(relative)
        require(retained.read_bytes() == (ROOT / relative).read_bytes(), 'executing scoped native helper differs: ' + relative)
        if suite_source is not None:
            require(retained.read_bytes() == git_blob(suite_source, suite_commit, relative), 'scoped native helper Git blob: ' + relative)
        result[relative] = old.compare.baseline.digest(retained)
    return result


COMPATIBILITY = 'diagnostics/anchor_margin_pair/observer_compatibility.json'


def derive_observer(source: bytes, descriptor: dict) -> bytes:
    """Only the approved exact one-site exhaustive abort arm may be staged."""
    import hashlib
    require(descriptor['schema_version'] == 1 and
            descriptor['kind'] == 'staging-only-frozen-observer-exhaustiveness-compatibility', 'observer compatibility identity')
    require(descriptor['source'] == 'adapters/anchor_moonbit/main.mbt' and descriptor['exact_occurrences'] == 1,
            'observer compatibility source/occurrence contract')
    require(descriptor['old'] == '@scene.ClipPop => "clip_pop" }' and
            descriptor['new'] == '@scene.ClipPop => "clip_pop"; @scene.Paint => abort("unexpected non-quad paint") }',
            'only explicit unsupported Paint abort is authorized')
    require(hashlib.sha256(source).hexdigest() == descriptor['frozen_source_sha256'], 'frozen observer source drift')
    old, new = descriptor['old'].encode(), descriptor['new'].encode()
    require(source.count(old) == 1, 'observer compatibility exact one-site match')
    result = source.replace(old, new)
    require(hashlib.sha256(result).hexdigest() == descriptor['derived_source_sha256'], 'derived observer source hash')
    return result


def _compatibility(pair, old, suite_source=None, suite_commit=None):
    path = pair / retained_path(COMPATIBILITY)
    require(path.read_bytes() == (ROOT / COMPATIBILITY).read_bytes(), 'compatibility descriptor differs from executing verifier')
    if suite_source is not None:
        require(path.read_bytes() == git_blob(suite_source, suite_commit, COMPATIBILITY), 'compatibility descriptor Git blob')
    descriptor = old.compare.load_json(path.read_text())
    source = (pair / 'suite/adapters/anchor_moonbit/main.mbt').read_bytes()
    derived = derive_observer(source, descriptor)
    return descriptor, derived


def _require_original_compile_rejection(directory, manifest):
    rejection = manifest['compatibility_original_build']
    require(rejection['returncode'] != 0 and rejection['timed_out'] is False, 'frozen original must exhibit actual exhaustiveness compile rejection')
    diagnostic = (directory / 'frozen-original-build.stderr').read_text()
    require('[0011]' in diagnostic and 'partial_match' in diagnostic and 'Paint' in diagnostic,
            'frozen original compile rejection must name missing Paint exhaustiveness')


def _projection(pair, directory, manifest, old):
    """The regression compiles the exact parent production projection."""
    stage = directory / 'build-source'
    core_inputs = manifest['core_inputs']
    require(core_inputs == sorted(set(core_inputs)) and core_inputs and
            all(old.run.production_file(p) for p in core_inputs), 'regression production input inventory')
    inputs = _source_inventory(stage, old)
    require(set(inputs) == set(core_inputs) | {'moon.mod', 'probe/main.mbt', 'probe/moon.pkg'}, 'unexpected regression compiled input')
    require((stage / 'moon.mod').read_text() == old.run.MODULE and
            (stage / 'moon.mod').read_bytes() == (pair / 'build-source/moon.mod').read_bytes(), 'same focused regression module')
    for relative in core_inputs:
        require((stage / relative).read_bytes() == (pair / 'build-source' / relative).read_bytes(), 'regression differs from margin core: ' + relative)
    descriptor, derived = _compatibility(pair, old)
    require((stage / 'probe/main.mbt').read_bytes() == derived, 'exact compatibility-derived observer bytes')
    require((stage / 'probe/moon.pkg').read_bytes() == (pair / 'suite/adapters/anchor_moonbit/moon.pkg').read_bytes(), 'frozen observer package metadata')
    old.native.staged_package_inputs(stage)
    return inputs


def _environment(environment, token, scenarios, old):
    return {'GPUI_RUN_TOKEN': token, 'GPUI_SCENARIOS_sha256': old.compare.baseline.digest(scenarios),
            **{name: environment.get(name) for name in ('CC', 'MOON_CC', 'MOONBIT_NEW_NATIVE', 'MOON_HOME', 'DISPLAY', 'WAYLAND_DISPLAY')}}


def _live_tool_hashes(manifest, old):
    digest = old.compare.baseline.digest
    return {'tool_binaries': {name: digest(Path(item['path'])) for name, item in manifest['tool_binaries'].items()},
            'tool_commands': {name: digest(Path(item['command_path'])) for name, item in manifest['tool_binaries'].items()},
            'toolchain_inputs': {name: digest(Path(manifest['toolchain_home']) / name) for name in manifest['toolchain_inputs']}}


def _tool_binding(pair, pair_manifest, manifest, old):
    """Native inputs are retained once by the enclosing artifact, never omitted."""
    digest = old.compare.baseline.digest
    for key in ('tool_binaries', 'toolchain_inputs', 'toolchain_home'):
        require(manifest[key] == pair_manifest[key], 'regression inherited toolchain differs: ' + key)
    tools = manifest['tool_binaries']
    _safe_tree(pair / 'tool-binaries')
    require({p.name for p in (pair / 'tool-binaries').iterdir()} == {'moon', 'moonc', 'cc', 'ar'}, 'regression complete retained compiler inventory')
    require(set(tools) == {'moon', 'moonc', 'cc', 'ar'}, 'regression compiler inventory')
    for name, item in tools.items():
        require(item['retained'] == 'tool-binaries/' + name and Path(item['path']).is_absolute() and
                Path(item['command_path']).is_absolute() and re.fullmatch('[0-9a-f]{64}', item['sha256']), 'regression compiler identity')
        require(digest(pair / item['retained']) == item['sha256'], 'regression retained compiler hash')
    native = manifest['toolchain_inputs']
    require(native and native == sorted(set(native)), 'regression runtime inventory shape')
    require(all(not Path(p).is_absolute() and '..' not in Path(p).parts and
                any(p == root or p.startswith(root + '/') for root in old.native.TOOLCHAIN_ROOTS) for p in native), 'regression runtime inventory roots')
    _safe_tree(pair / 'toolchain-inputs')
    actual = {str(p.relative_to(pair / 'toolchain-inputs')) for p in (pair / 'toolchain-inputs').rglob('*') if p.is_file()}
    require(actual == set(native), 'regression complete retained runtime input inventory')
    require(any(p.startswith('include/') for p in native) and
            any(p.startswith('lib/core/_build/native/release/bundle/') for p in native), 'regression runtime bundle/header inputs')
    expected = {'tool_binaries': {name: item['sha256'] for name, item in tools.items()},
                'tool_commands': {name: item['sha256'] for name, item in tools.items()},
                'toolchain_inputs': {name: digest(pair / 'toolchain-inputs' / name) for name in native}}
    require(manifest['tool_hashes_before'] == expected, 'regression actual build/runtime inputs changed before execution')
    if 'tool_hashes_after' in manifest:
        require(manifest['tool_hashes_after'] == expected, 'regression actual build/runtime inputs changed during execution')
    env = manifest['input_environment']
    old.native.require_native_environment(env, tools)
    require(env['MOON_HOME'] == manifest['toolchain_home'] and
            env['DISPLAY'] is None and env['WAYLAND_DISPLAY'] is None, 'regression native/headless environment')
    for name in ('CC', 'MOON_CC', 'MOONBIT_NEW_NATIVE', 'MOON_HOME'):
        require(env[name] == pair_manifest['input_environment'][name], 'regression differs from enclosing compiler environment')


def _require_counts(comparison, expected, old):
    old.compare.require_semantic_match(comparison)
    require({key: comparison['counts'][key] for key in expected} == expected, 'frozen regression coverage counts')


def _require_space(path, extra=0):
    require(shutil.disk_usage(path).free >= DISK_FLOOR + extra,
            'Need to preserve at least 1GiB free disk; retain evidence and run native regressions in CI')


def _require_success(manifest, phase):
    require(manifest[phase]['returncode'] == 0 and manifest[phase]['timed_out'] is False,
            'regression ' + phase + ' failed; evidence retained')


def execute_regressions(pair: Path, environment: dict, original_rust: Path, source_context: dict) -> dict:
    """Build the exact compatibility-derived original adapter and run both genuine regressions."""
    pair, original_rust = Path(pair).resolve(), Path(original_rust).resolve()
    parent = source_context['pair_manifest']
    require(parent['recorded_execution_root'] == str(pair), 'regression parent execution root')
    require(source_context['suite_commit'] == parent['suite']['commit'], 'regression Rust and pair must use same selected suite commit')
    with original_modules() as old:
        profile = _profile(pair, old)
        observer_hashes = _observer_binding(pair, profile, old)
        native_hashes = _native_helper_binding(pair, old)
        compatibility, derived_observer = _compatibility(pair, old)
        approved = old.verify.validate_baseline(original_rust, source_context['suite_source'], source_context['upstream_source'],
                                               source_context['suite_commit'], source_context.get('recorded_execution_root'))
        _safe_tree(original_rust)
        estimated_copy = sum(p.stat().st_size for p in original_rust.rglob('*') if p.is_file())
        estimated_copy += sum((pair / 'build-source' / p).stat().st_size for p in parent['core_inputs'])
        _require_space(pair, estimated_copy)
        directory = pair / 'regressions'
        directory.mkdir(exist_ok=False)
        token = str(uuid.uuid4())
        manifest = {'schema_version': 1, 'layer': LAYER, 'qualification': QUALIFICATION,
                    'recorded_execution_root': str(directory), 'run_token': token,
                    'core': deepcopy(parent['core']), 'suite': deepcopy(parent['suite']),
                    'requested_core_commit': parent['requested_core_commit'], 'core_inputs': list(parent['core_inputs']),
                    'observer_compatibility': compatibility,
                    'baseline': approved, 'observer_sha256': observer_hashes, 'native_helper_sha256': native_hashes,
                    'scoped_profile_sha256': old.compare.baseline.digest(pair / retained_path(PROFILE)),
                    'toolchain_evidence': 'enclosing-source-bound-pair',
                    'tool_binaries': deepcopy(parent['tool_binaries']), 'toolchain_inputs': list(parent['toolchain_inputs']),
                    'toolchain_home': parent['toolchain_home'], 'platform': deepcopy(parent['platform']),
                    'omitted_non_input_build_caches': list(old.run.OMITTED_BUILD_CACHES),
                    'started_at': old.run.now()}
        try:
            stage = directory / 'build-source'
            stage.mkdir()
            for relative in ['moon.mod', *manifest['core_inputs']]:
                destination = stage / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(pair / 'build-source' / relative, destination)
            (stage / 'probe').mkdir()
            for name in ('main.mbt', 'moon.pkg'):
                shutil.copy2(pair / 'suite/adapters/anchor_moonbit' / name, stage / 'probe' / name)
            shutil.copytree(original_rust, directory / 'rust-baseline')
            shutil.copy2(original_rust / 'scenarios.json', directory / 'scenarios.json')
            env = environment.copy()
            env.pop('DISPLAY', None)
            env.pop('WAYLAND_DISPLAY', None)
            env.update(GPUI_RUN_TOKEN=token, GPUI_SCENARIOS=(directory / 'scenarios.json').read_text())
            manifest['input_environment'] = _environment(env, token, directory / 'scenarios.json', old)
            manifest['tool_hashes_before'] = _live_tool_hashes(manifest, old)
            _tool_binding(pair, parent, manifest, old)
            _require_space(directory)
            moon = manifest['tool_binaries']['moon']['path']
            # Prove the original frozen source fails, then apply only the retained
            # deterministic abort-arm derivation. No frozen repository file changes.
            manifest['compatibility_original_source_inputs'] = _source_inventory(stage, old)
            manifest['compatibility_original_build'] = old.run.execute(
                [moon, 'build', '--target', 'native', '--deny-warn', '--verbose', 'probe'],
                stage, directory, 'frozen-original-build', env)
            _require_original_compile_rejection(directory, manifest)
            require(_source_inventory(stage, old) == manifest['compatibility_original_source_inputs'], 'frozen compile source changed')
            (stage / 'probe/main.mbt').write_bytes(derived_observer)
            manifest['source_inputs'] = _projection(pair, directory, manifest, old)
            manifest['build_plan'] = old.run.execute([moon, 'build', '--target', 'native', '--deny-warn', '--dry-run', '--verbose', 'probe'],
                                                      stage, directory, 'build-plan', env)
            _require_success(manifest, 'build_plan')
            manifest['native_build_plan'] = old.native.native_build_plan((directory / 'build-plan.stdout').read_text(), manifest['tool_binaries'], stage)
            require(set(manifest['native_build_plan']['required_toolchain']) <= set(manifest['toolchain_inputs']), 'unretained regression planned runtime input')
            manifest['build'] = old.run.execute([moon, 'build', '--target', 'native', '--deny-warn', '--verbose', 'probe'],
                                                 stage, directory, 'build', env)
            _require_success(manifest, 'build')
            _require_space(directory)
            manifest['generated_build_inputs'] = old.native.native_generated_inventory(stage / '_build/native/debug/build', manifest['native_build_plan'])
            shutil.copy2(stage / '_build/native/debug/build/probe/probe.exe', directory / 'candidate-probe')
            require((directory / 'candidate-probe').read_bytes().startswith(b'\x7fELF'), 'regression candidate must be native ELF')
            manifest['execution'] = old.run.execute([str(directory / 'candidate-probe')], stage, directory, 'candidate', env)
            (directory / 'candidate.stdout').rename(directory / 'candidate-raw.json')
            _require_success(manifest, 'execution')
            require((directory / 'candidate.stderr').stat().st_size == 0, 'regression candidate stderr')
            raw = old.compare.load_json((directory / 'candidate-raw.json').read_text())
            require(raw['run_token'] == token, 'regression candidate cross-run token')
            original = old.compare.compare_observations(old.compare.load_json((directory / 'rust-baseline/raw.json').read_text()), raw,
                                                       old.compare.load_json((directory / 'scenarios.json').read_text()))
            (directory / 'comparison.json').write_text(json.dumps(original, indent=2) + '\n')
            _require_counts(original, ORIGINAL_COUNTS, old)
            fractional = old.fractional_viewport.execute_extension(directory, env)
            _require_counts(fractional, FRACTIONAL_COUNTS, old)
            extension_manifest = old.compare.load_json((directory / 'fractional-viewport/manifest.json').read_text())
            manifest['fractional_environment'] = _environment(env, extension_manifest['run_token'], directory / 'fractional-viewport/scenarios.json', old)
            manifest['fractional_viewport'] = fractional
            manifest['result'] = {'original': original, 'fractional': fractional,
                                  'observer_compatibility': compatibility, 'passed': True}
            manifest['source_inputs_after'] = _projection(pair, directory, manifest, old)
            require(manifest['source_inputs_after'] == manifest['source_inputs'], 'regression source changed during execution')
            manifest['tool_hashes_after'] = _live_tool_hashes(manifest, old)
            _tool_binding(pair, parent, manifest, old)
            _require_space(directory)
            return manifest['result']
        except (ValueError, TypeError, KeyError, IndexError, OSError, subprocess.SubprocessError) as error:
            manifest['failure'] = {'type': type(error).__name__, 'error': str(error)}
            raise
        finally:
            manifest['finished_at'] = old.run.now()
            manifest['files'] = old.run.inventory(directory)
            (directory / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


def verify_regressions(pair: Path, pair_manifest: dict, suite_source: Path, upstream_source: Path,
                       core_source: Path, suite_commit: str, core_commit: str) -> dict:
    """Reopen copied evidence without executing either retained binary."""
    pair = Path(pair).resolve()
    directory = pair / 'regressions'
    _safe_tree(directory)
    with original_modules() as old:
        digest = old.compare.baseline.digest
        manifest = old.compare.load_json((directory / 'manifest.json').read_text())
        require(manifest['schema_version'] == 1 and manifest['layer'] == LAYER and manifest['qualification'] == QUALIFICATION,
                'regression manifest identity')
        require('failure' not in manifest and manifest['result']['passed'] is True, 'failed regression artifact')
        profile = _profile(pair, old, suite_source, suite_commit)
        compatibility, derived_observer = _compatibility(pair, old, suite_source, suite_commit)
        require(manifest['observer_compatibility'] == compatibility, 'recorded compatibility derivation')
        require(profile['candidate_pin_status'] == 'published-exact-commit-tree' and
                profile['candidate_commit'] == core_commit and profile['candidate_tree'] == pair_manifest['core']['tree'],
                'regression new scoped core pin')
        require(manifest['observer_sha256'] == _observer_binding(pair, profile, old, suite_source, suite_commit), 'regression complete observer hashes')
        require(manifest['native_helper_sha256'] == _native_helper_binding(pair, old, suite_source, suite_commit), 'regression scoped native helper hashes')
        require(manifest['scoped_profile_sha256'] == digest(pair / retained_path(PROFILE)), 'regression scoped profile hash')
        for key in ('core', 'suite', 'requested_core_commit', 'core_inputs', 'platform'):
            require(manifest[key] == pair_manifest[key], 'regression enclosing provenance differs: ' + key)
        require(manifest['platform']['system'] == 'Linux' and manifest['requested_core_commit'] == core_commit, 'regression native Linux/core identity')
        require(pair_manifest['core_after'] == manifest['core'] and pair_manifest['suite_after'] == manifest['suite'], 'regression enclosing sources changed')
        for source, selected, identity in ((core_source, core_commit, manifest['core']), (suite_source, suite_commit, manifest['suite'])):
            require(isinstance(selected, str) and re.fullmatch('[0-9a-f]{40}', selected) and
                    identity['commit'] == selected and identity['clean'] is True, 'regression independently selected clean source')
            tree = subprocess.check_output(['git', 'rev-parse', selected + '^{tree}'], cwd=source, text=True).strip()
            require(tree == identity['tree'], 'regression independently selected Git tree')
        paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', core_commit], cwd=core_source, text=True).splitlines()
        require(manifest['core_inputs'] == sorted(p for p in paths if old.run.production_file(p)), 'regression complete Git core projection')
        for relative in manifest['core_inputs']:
            require((directory / 'build-source' / relative).read_bytes() == git_blob(core_source, core_commit, relative), 'regression core Git blob: ' + relative)
        require((pair / 'original-core-moon.mod').read_bytes() == git_blob(core_source, core_commit, 'moon.mod'), 'regression original core module Git blob')
        require(manifest['source_inputs'] == manifest['source_inputs_after'] == _projection(pair, directory, manifest, old), 'regression source input hashes')
        original_inputs = dict(manifest['source_inputs'], **{'probe/main.mbt': compatibility['frozen_source_sha256']})
        require(manifest['compatibility_original_source_inputs'] == original_inputs, 'original failed-build source projection')
        _require_original_compile_rejection(directory, manifest)
        require(manifest['omitted_non_input_build_caches'] == list(old.run.OMITTED_BUILD_CACHES), 'regression unexpected omitted files')
        required = {'frozen-original-build.stdout', 'frozen-original-build.stderr', 'build-source/moon.mod', 'build-source/probe/main.mbt', 'build-source/probe/moon.pkg',
                    'build-source/_build/native/debug/build/probe/probe.exe', 'candidate-probe', 'candidate-raw.json',
                    'candidate.stderr', 'build-plan.stdout', 'build-plan.stderr', 'build.stdout', 'build.stderr',
                    'scenarios.json', 'comparison.json', 'rust-baseline/manifest.json', 'rust-baseline/raw.json',
                    'rust-baseline/probe', 'fractional-viewport/manifest.json', 'fractional-viewport/scenarios.json',
                    'fractional-viewport/rust-raw.json', 'fractional-viewport/rust.stderr',
                    'fractional-viewport/candidate-raw.json', 'fractional-viewport/candidate.stderr',
                    'fractional-viewport/comparison.json'}
        required |= {'build-source/' + p for p in manifest['core_inputs']}
        require(required <= set(manifest['files']), 'missing retained regression evidence')
        for relative, metadata in manifest['files'].items():
            path = directory / relative
            require(not Path(relative).is_absolute() and '..' not in Path(relative).parts and path.is_file() and
                    not path.is_symlink() and path.resolve().is_relative_to(directory), 'unsafe regression inventory path')
            require(metadata == {'sha256': digest(path), 'size': path.stat().st_size}, 'regression file changed: ' + relative)
        require(old.run.inventory(directory) == manifest['files'], 'regression inventory must cover every retained file')
        approved = old.verify.validate_baseline(directory / 'rust-baseline', suite_source, upstream_source, suite_commit,
                                                manifest['baseline']['recorded_execution_root'])
        require(approved == manifest['baseline'], 'regression freshly source-bound original Rust baseline')
        require((directory / 'scenarios.json').read_bytes() == (directory / 'rust-baseline/scenarios.json').read_bytes() ==
                (pair / 'suite/diagnostics/anchor/scenarios.json').read_bytes(), 'regression exact unchanged original corpus')
        require(manifest['toolchain_evidence'] == 'enclosing-source-bound-pair' and 'tool_hashes_after' in manifest, 'regression toolchain evidence interval')
        _tool_binding(pair, pair_manifest, manifest, old)
        require(manifest['tool_hashes_after']['tool_binaries'] == pair_manifest['tool_binaries_after'] and
                manifest['tool_hashes_after']['tool_commands'] == pair_manifest['tool_commands_after'] and
                manifest['tool_hashes_after']['toolchain_inputs'] == pair_manifest['toolchain_inputs_after'], 'regression final enclosing runtime identity')
        plan = old.native.native_build_plan((directory / 'build-plan.stdout').read_text(), manifest['tool_binaries'], directory / 'build-source')
        require(plan == manifest['native_build_plan'] and set(plan['required_toolchain']) <= set(manifest['toolchain_inputs']), 'regression exact native plan')
        generated = old.native.native_generated_inventory(directory / 'build-source/_build/native/debug/build', plan)
        require(generated == manifest['generated_build_inputs'], 'regression complete generated native artifacts')
        recorded = Path(pair_manifest['recorded_execution_root']) / 'regressions'
        require(recorded.is_absolute() and '..' not in recorded.parts and str(recorded) == str(recorded.resolve()) and
                manifest['recorded_execution_root'] == str(recorded), 'regression canonical recorded root')
        moon = manifest['tool_binaries']['moon']['path']
        commands = {'build_plan': [moon, 'build', '--target', 'native', '--deny-warn', '--dry-run', '--verbose', 'probe'],
                    'build': [moon, 'build', '--target', 'native', '--deny-warn', '--verbose', 'probe'],
                    'execution': [str(recorded / 'candidate-probe')]}
        require(manifest['compatibility_original_build']['command'] == commands['build'] and
                manifest['compatibility_original_build']['cwd'] == str(recorded / 'build-source'), 'exact frozen-original native compile command')
        for phase, command in commands.items():
            _require_success(manifest, phase)
            require(manifest[phase]['command'] == command and manifest[phase]['cwd'] == str(recorded / 'build-source'), 'regression exact native invocation: ' + phase)
        candidate = (directory / 'candidate-probe').read_bytes()
        require(candidate.startswith(b'\x7fELF') and candidate == (directory / 'build-source/_build/native/debug/build/probe/probe.exe').read_bytes(), 'regression actual generated/executed ELF')
        require((directory / 'candidate.stderr').stat().st_size == 0, 'regression candidate stderr')
        raw = old.compare.load_json((directory / 'candidate-raw.json').read_text())
        token = manifest['run_token']
        require(isinstance(token, str) and str(uuid.UUID(token)) == token and
                raw['run_token'] == token == manifest['input_environment']['GPUI_RUN_TOKEN'], 'regression input/raw run token')
        require(manifest['input_environment']['GPUI_SCENARIOS_sha256'] == digest(directory / 'scenarios.json'), 'regression executed input hash')
        original = old.compare.compare_observations(old.compare.load_json((directory / 'rust-baseline/raw.json').read_text()), raw,
                                                   old.compare.load_json((directory / 'scenarios.json').read_text()))
        require(original == old.compare.load_json((directory / 'comparison.json').read_text()), 'regression recomputed original comparison')
        _require_counts(original, ORIGINAL_COUNTS, old)
        fractional = old.fractional_viewport.verify_extension(directory, manifest)
        require(fractional == manifest['fractional_viewport'], 'regression recomputed fractional comparison')
        _require_counts(fractional, FRACTIONAL_COUNTS, old)
        extension = old.compare.load_json((directory / 'fractional-viewport/manifest.json').read_text())
        expected_env = dict(manifest['input_environment'], GPUI_RUN_TOKEN=extension['run_token'],
                            GPUI_SCENARIOS_sha256=digest(directory / 'fractional-viewport/scenarios.json'))
        require(manifest['fractional_environment'] == expected_env and str(uuid.UUID(extension['run_token'])) == extension['run_token'] and extension['run_token'] != token,
                'regression separate fractional input environment/token')
        result = {'original': original, 'fractional': fractional, 'observer_compatibility': compatibility, 'passed': True}
        require(result == manifest['result'], 'regression independently recomputed result')
        return result
