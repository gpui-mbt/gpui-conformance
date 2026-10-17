#!/usr/bin/env python3
"""Compile exact production packages and retain the complete native semantic pair."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import time
import shlex
import subprocess
import uuid
from compare import load_json, ROOT, LAYER, baseline, compare_observations, require, require_semantic_match, policy, mutation_descriptors

PACKAGES = ('element', 'layout', 'primitives', 'scene')
# Published API context only; the actual compiler consumes retained generated .mi.
CORE_API_FILES = ('element/pkg.generated.mbti', 'scene/pkg.generated.mbti')
MODULE = 'name = "f4ah6o/gpui"\nversion = "0.0.0"\n'
NEW_SUITE_FILES = ('adapters/nested_deferred_moonbit/main.mbt', 'adapters/nested_deferred_moonbit/moon.pkg',
    'diagnostics/nested_deferred_pair/compare.py', 'diagnostics/nested_deferred_pair/run.py',
    'diagnostics/nested_deferred_pair/verify.py', 'diagnostics/nested_deferred_pair/profile.json',
    'diagnostics/nested_deferred_pair/actual-rust-projection.json', 'diagnostics/nested_deferred_pair/comparison-policy.json', 'diagnostics/nested_deferred_pair/control-policy.json', 'diagnostics/nested_deferred_pair/README.md', 'diagnostics/nested_deferred_pair/raw.schema.json',
    'diagnostics/nested_deferred_pair/regressions.py', 'diagnostics/nested_deferred_pair/observer_compatibility.json', 'diagnostics/nested_deferred_pair/run_mutants.py',
    'diagnostics/nested_deferred_pair/mutations.json', 'diagnostics/nested_deferred_pair/run_controls.py',
    'diagnostics/nested_deferred_pair/verify_mutants.py', 'tests/test_nested_deferred_pair.py',
    '.github/workflows/nested-deferred-native-pair.yml')
# Exact inventory, including every unchanged verifier/helper the new suite calls.
SUITE_FILES = NEW_SUITE_FILES + tuple(load_json((ROOT / 'diagnostics/nested_deferred_pair/profile.json').read_text())['approved_fixture_sha256'])
OMITTED_BUILD_CACHES = ('build-source/_build/.moon_db', 'build-source/_build/.moon-lock',
    'regressions/build-source/_build/.moon_db', 'regressions/build-source/_build/.moon-lock',
    'margin-regression/build-source/_build/.moon_db', 'margin-regression/build-source/_build/.moon-lock',
    'flat-regression/build-source/_build/.moon_db', 'flat-regression/build-source/_build/.moon-lock')
POLICY_FILES = ('diagnostics/nested_deferred_pair/profile.json', 'diagnostics/nested_deferred_pair/compare.py',
    'diagnostics/nested_deferred_pair/raw.schema.json', 'diagnostics/nested_deferred_pair/mutations.json',
    'diagnostics/nested_deferred_pair/observer_compatibility.json', 'diagnostics/nested_deferred_pair/actual-rust-projection.json', 'diagnostics/nested_deferred_pair/comparison-policy.json', 'diagnostics/nested_deferred_pair/control-policy.json')
TOOLCHAIN_ROOTS = ('lib/core/_build/native/release/bundle', 'include', 'lib/runtime', 'lib/libmoonbitrun.o', 'lib/libbacktrace.a')


NATIVE_BACKEND = 'direct-native-object'
BUILD_PREFIX = './_build/native/debug/build/'


def require_native_environment(environment, tools):
    require(environment.get('MOONBIT_NEW_NATIVE') in (None, '1'), 'unknown or changed native backend environment')
    require(environment.get('CC') == tools['cc']['path'] and environment.get('MOON_CC') is None, 'native compiler environment binding')
    require(isinstance(environment.get('MOON_HOME'), str) and Path(environment['MOON_HOME']).is_absolute(), 'native toolchain home')


def staged_package_inputs(source):
    """Read the exact bounded projection, including supported package metadata."""
    require(source.is_dir() and (source / 'moon.mod').read_text() == MODULE, 'native staged module identity')
    result = {}
    for package in (*PACKAGES, 'probe'):
        directory = source / package
        require(directory.is_dir() and not directory.is_symlink(), 'native staged package directory')
        files = sorted(directory.iterdir())
        require(all(p.is_file() and not p.is_symlink() and (p.name == 'moon.pkg' or
                    p.suffix == '.mbt' and not p.name.endswith(('_test.mbt', '_wbtest.mbt'))) for p in files), 'unexpected staged package input')
        sources = ['./' + str(p.relative_to(source)) for p in files if p.suffix == '.mbt']
        require(sources and (package != 'probe' or sources == ['./probe/main.mbt']), 'complete staged package sources')
        metadata = (directory / 'moon.pkg').read_text()
        imports = ['moonbitlang/core/prelude']
        pattern = r'import\s*\{([^}]*)\}(?:\s*for\s*"([^"]+)")?'
        for block in re.finditer(pattern, metadata):
            names = re.findall(r'"([^"]+)"', block[1])
            require(not re.sub(r'"[^"]+"|[\s,]', '', block[1]), 'unsupported package import syntax')
            if block[2] is None: imports.extend(names)
            else:
                require(block[2] == 'test', 'unsupported package import mode')
                require(all(name in ('moonbitlang/core/double','moonbitlang/core/quickcheck') or name in {'f4ah6o/gpui/' + p for p in PACKAGES} for name in names), 'unsupported test-only package import')
        remainder = re.sub(pattern, '', metadata).strip()
        require(remainder == ('options("is-main": true)' if package == 'probe' else ''), 'unsupported native package metadata')
        aliases = {}
        for name in imports:
            alias = name.rsplit('/', 1)[-1]
            require(alias not in aliases, 'duplicate package import alias')
            if name.startswith('f4ah6o/gpui/'):
                require(alias in PACKAGES and name == 'f4ah6o/gpui/' + alias, 'unretained production package import')
                path = BUILD_PREFIX + alias + '/' + alias + '.mi'
            else:
                require(name in ('moonbitlang/core/prelude','moonbitlang/core/json','moonbitlang/core/env','moonbitlang/core/math'), 'unsupported runtime package import')
                path = '$MOON_HOME/lib/core/_build/native/release/bundle/' + alias + '/' + alias + '.mi'
            aliases[alias] = path + ':' + alias
        result[package] = {'sources': sources, 'imports': [aliases[a] for a in sorted(aliases)]}
    return result


def native_build_plan(text, tools, source):
    """Bind the actual direct-native pipeline; unknown modes fail closed."""
    staged = staged_package_inputs(source)
    commands = [shlex.split(line) for line in text.splitlines() if line.strip()]
    required, external, packages, links, runtime, archives, final = set(), set(), [], [], [], [], []
    def value(command, flag):
        require(command.count(flag) == 1 and command.index(flag) + 1 < len(command), 'native plan flag: ' + flag)
        return command[command.index(flag) + 1]
    def generated(path):
        require(path.startswith(BUILD_PREFIX), 'native generated path root')
        relative = path[len(BUILD_PREFIX):]
        require(relative and '..' not in Path(relative).parts, 'unsafe generated input')
        required.add(relative)
        return relative
    for command in commands:
        program = command[0]
        if program in ('moonc', tools['moonc']['path'], tools['moonc'].get('command_path')):
            require(len(command) > 1 and command[1] in ('build-package', 'link-core'), 'unexpected native compiler action')
            output = generated(value(command, '-o'))
            require('-g' in command and '-O0' in command, 'native debug unoptimized mode')
            if command[1] == 'build-package':
                package = value(command, '-pkg').removeprefix('f4ah6o/gpui/')
                require(package in (*PACKAGES, 'probe') and output == package + '/' + package + '.core' and value(command, '-target') == 'native', 'native production package output')
                expected = [program, 'build-package'] + staged[package]['sources'] + ['-w', '@a', '-o', BUILD_PREFIX + output,
                    '-pkg', 'f4ah6o/gpui/' + package, '-pkg-type', 'executable' if package == 'probe' else 'library',
                    '-std-path', '$MOON_HOME/lib/core/_build/native/release/bundle']
                for imported in staged[package]['imports']: expected.extend(['-i', imported])
                expected.extend(['-pkg-sources', 'f4ah6o/gpui/' + package + ':./' + package, '-target', 'native', '-g', '-O0',
                                 '-workspace-path', '.', '-all-pkgs', BUILD_PREFIX + 'all_pkgs.json'])
                require(command == expected, 'exact staged production source/compiler argv: ' + package)
                required.add(package + '/' + package + '.mi'); packages.append(package)
            else:
                require(value(command, '-target') in ('x86_64-unknown-linux-gnu', 'aarch64-unknown-linux-gnu') and
                        output == 'probe/__moonbit_link_core__/probe.o' and value(command, '-main') == 'f4ah6o/gpui/probe', 'direct-native linked object/backend')
                order = ('primitives','layout','scene','element','probe')
                expected = [program, 'link-core', '$MOON_HOME/lib/core/_build/native/release/bundle/abort/abort.core',
                    '$MOON_HOME/lib/core/_build/native/release/bundle/core.core']
                expected.extend(BUILD_PREFIX + name + '/' + name + '.core' for name in order)
                expected.extend(['-main','f4ah6o/gpui/probe','-o',BUILD_PREFIX + output,'-pkg-config-path','./probe/moon.pkg'])
                for name in order: expected.extend(['-pkg-sources','f4ah6o/gpui/' + name + ':./' + name])
                expected.extend(['-pkg-sources','moonbitlang/core:$MOON_HOME/lib/core','-target','x86_64-unknown-linux-gnu','-g','-O0'])
                require(command == expected, 'exact supported direct-native linker argv')
                links.append(command)
        elif program in (tools['cc']['path'], tools['cc'].get('command_path')):
            output = generated(value(command, '-o'))
            if '-c' in command:
                require(output.startswith('runtime-') and output.endswith('.o'), 'native runtime compile output')
                require([arg for arg in command if arg.endswith('.c')] == ['$MOON_HOME/lib/runtime/' + output[len('runtime-'):-2] + '.c'], 'native runtime source/output binding')
                expected = [program,'-o',BUILD_PREFIX + output,'-I$MOON_HOME/include','-g','-c','-fwrapv','-fno-strict-aliasing','-O2',
                    '-DMOONBIT_ALLOW_STACKTRACE','-DMOONBIT_ALLOCATOR=MOONBIT_ALLOCATOR_MIMALLOC',
                    '$MOON_HOME/lib/runtime/' + output[len('runtime-'):-2] + '.c']
                require(command == expected, 'exact supported native runtime compile argv')
                runtime.append(output)
            else:
                require(output == 'probe/probe.exe', 'native final ELF output')
                final.append(command)
        elif program in (tools['ar']['path'], tools['ar'].get('command_path')):
            outputs = [arg for arg in command[1:] if arg.startswith(BUILD_PREFIX) and arg.endswith('.a')]
            require(len(outputs) == 1 and command[1:4] == ['-r', '-c', '-s'], 'native runtime archive command')
            archives.append((generated(outputs[0]), command))
        else:
            require(False, 'unknown native build-plan program: ' + program)
        for argument in command[1:]:
            path = argument.split(':', 1)[0] if argument.startswith((BUILD_PREFIX, '$MOON_HOME/')) else argument
            if path.startswith(BUILD_PREFIX): generated(path)
            elif path.startswith('$MOON_HOME/') and Path(path).suffix in ('.core', '.mi', '.o', '.a', '.c'):
                relative = path[len('$MOON_HOME/'):]
                require('..' not in Path(relative).parts, 'unsafe native toolchain input')
                external.add(relative)
    require(sorted(packages) == sorted((*PACKAGES, 'probe')) and len(links) == len(final) == len(archives) == 1, 'complete native package/link pipeline')
    require(set(runtime) == {'runtime-' + name + '.o' for name in ('utf','sync_io','runtime','env','backtrace')}, 'complete native runtime compilation')
    require(len(runtime) == 5, 'exact runtime compile count')
    archive, archive_command = archives[0]
    require(re.fullmatch(r'libruntime-[0-9a-f]{16}\.a', archive), 'native archive identity')
    require(archive_command == [archive_command[0],'-r','-c','-s',BUILD_PREFIX + archive] + [BUILD_PREFIX + name for name in sorted(runtime)], 'exact supported archive argv')
    require(final[0] == [final[0][0],'-o',BUILD_PREFIX + 'probe/probe.exe','$MOON_HOME/lib/libmoonbitrun.o',
            BUILD_PREFIX + 'probe/__moonbit_link_core__/probe.o',BUILD_PREFIX + archive,'-lm','$MOON_HOME/lib/libbacktrace.a'], 'exact supported native final linker argv')
    require({arg[len(BUILD_PREFIX):] for arg in archive_command if arg.startswith(BUILD_PREFIX) and arg.endswith('.o')} == set(runtime), 'runtime archive inputs')
    require(BUILD_PREFIX + 'probe/__moonbit_link_core__/probe.o' in final[0] and BUILD_PREFIX + archive in final[0] and
            '$MOON_HOME/lib/libmoonbitrun.o' in final[0] and '$MOON_HOME/lib/libbacktrace.a' in final[0], 'final native link inputs')
    require({arg for arg in final[0] if arg.endswith(('.o', '.a'))} == {BUILD_PREFIX + 'probe/__moonbit_link_core__/probe.o', BUILD_PREFIX + archive, '$MOON_HOME/lib/libmoonbitrun.o', '$MOON_HOME/lib/libbacktrace.a'}, 'unexpected final native object/archive input')
    expected_cores = {BUILD_PREFIX + package + '/' + package + '.core' for package in (*PACKAGES, 'probe')}
    expected_cores |= {'$MOON_HOME/lib/core/_build/native/release/bundle/' + name for name in ('abort/abort.core','core.core')}
    require({arg for arg in links[0] if arg.endswith('.core')} == expected_cores, 'linked production/runtime core inputs')
    return {'backend': NATIVE_BACKEND, 'commands': commands, 'required_generated': sorted(required), 'required_toolchain': sorted(external)}


def native_generated_inventory(source, plan):
    files = {}
    for path in sorted(source.rglob('*')):
        require(not path.is_symlink() and path.resolve().is_relative_to(source.resolve()), 'unsafe generated native artifact')
        if path.is_file(): files[str(path.relative_to(source))] = {'sha256': baseline.digest(path), 'size': path.stat().st_size}
    require(set(plan['required_generated']) <= set(files), 'missing planned generated native inputs/outputs')
    require(all(files[name]['size'] > 0 for name in plan['required_generated']), 'empty planned generated artifact')
    return files


def retain_native_generated(source, destination, plan):
    files = native_generated_inventory(source, plan)
    shutil.copytree(source, destination)
    require(native_generated_inventory(destination, plan) == files, 'generated copy differs from actual build')
    return files


def retained_path(relative):
    return 'suite/workflows/' + Path(relative).name if relative.startswith('.github/') else 'suite/' + relative


def now(): return datetime.now(timezone.utc).isoformat()


def command(args, cwd=None): return subprocess.check_output(args, cwd=cwd, text=True).strip()


def identity(path):
    return {'commit': command(['git', 'rev-parse', 'HEAD'], path),
            'tree': command(['git', 'rev-parse', 'HEAD^{tree}'], path),
            'clean': not command(['git', 'status', '--porcelain', '--untracked-files=all'], path)}


def production_file(relative):
    path = Path(relative)
    return len(path.parts) == 2 and path.parts[0] in PACKAGES and (path.name == 'moon.pkg' or
        path.suffix == '.mbt' and not path.name.endswith(('_test.mbt', '_wbtest.mbt')))


def production_paths(core):
    return sorted(str(p.relative_to(core)) for package in PACKAGES for p in (core / package).iterdir()
                  if p.is_file() and production_file(str(p.relative_to(core))))



def selected_production_paths(core, commit):
    paths = command(['git', 'ls-tree', '-r', '--name-only', commit], core).splitlines()
    require(len(paths) == len(set(paths)), 'duplicate selected Git source path')
    selected = sorted(p for p in paths if production_file(p))
    require(selected and all(package + '/moon.pkg' in selected for package in PACKAGES), 'complete selected production packages')
    return selected


def source_preflight(core, commit):
    """Before staging or compiling, bind every production input to selected Git."""
    selected = selected_production_paths(core, commit)
    require(production_paths(core) == selected, 'filesystem/selected production source inventory')
    for relative in (*selected, *CORE_API_FILES, 'moon.mod'):
        path = core / relative
        require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(core.resolve()), 'unsafe selected core input: ' + relative)
        blob = subprocess.check_output(['git', 'show', commit + ':' + relative], cwd=core)
        require(path.read_bytes() == blob, 'preexecution core Git blob: ' + relative)
    return selected


def verify_core_api(directory, manifest, core_source, core_commit):
    api = directory / 'core-api'
    names = sorted(str(p.relative_to(api)) for p in api.rglob('*') if p.is_file())
    require(manifest.get('core_api_context') == {'role': 'noncompiled-published-api-context', 'files': list(CORE_API_FILES)}, 'core API context inventory')
    require(names == sorted(CORE_API_FILES), 'complete retained API context')
    for relative in CORE_API_FILES:
        path = baseline.strict_file(api, relative)
        require(not path.is_symlink() and path.read_bytes() == subprocess.check_output(
            ['git', 'show', core_commit + ':' + relative], cwd=core_source), 'core API Git blob: ' + relative)


DISK_FLOOR = 1024 ** 3
PROCESS_RESERVE = 64 * 1024 ** 2


def capacity_snapshot(path):
    return {str(Path(p).resolve()): shutil.disk_usage(p).free for p in (path, Path('/tmp'))}


def require_capacity(path, reserve=PROCESS_RESERVE):
    snapshot=capacity_snapshot(path)
    require(all(value > DISK_FLOOR + reserve for value in snapshot.values()),
            'strict 1GiB floor plus predeclared process/evidence reserve; preserve evidence')
    return snapshot


def execute(args, cwd, out, stem, environment, timeout=120):
    started=now(); before=require_capacity(out);minimum=dict(before)
    with (out/(stem+'.stdout')).open('wb') as stdout,(out/(stem+'.stderr')).open('wb') as stderr:
        process=subprocess.Popen(args,cwd=cwd,env=environment,stdout=stdout,stderr=stderr,start_new_session=True)
        deadline=time.monotonic()+timeout;timed_out=False;resource_floor_stop=False
        while process.poll() is None:
            snapshot=capacity_snapshot(out)
            minimum={name:min(value,minimum[name]) for name,value in snapshot.items()}
            resource_floor_stop=any(value <= DISK_FLOOR + PROCESS_RESERVE//2 for value in snapshot.values())
            timed_out=time.monotonic()>=deadline
            if resource_floor_stop or timed_out:
                try: os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError: pass
                break
            time.sleep(0.1)
        code=process.wait()
    after=capacity_snapshot(out);minimum={name:min(value,minimum[name]) for name,value in after.items()}
    return {'command':args,'cwd':str(cwd),'started_at':started,'finished_at':now(),
        'pid':process.pid,'returncode':code,'timed_out':timed_out,'resource_floor_stop':resource_floor_stop,
        'resource_guard':{'strict_floor_bytes':DISK_FLOOR,'process_reserve_bytes':PROCESS_RESERVE,
            'before_free_bytes':before,'minimum_observed_free_bytes':minimum,'after_free_bytes':after}}


def verify_process_guard(record):
    guard=record['resource_guard']
    require(record['resource_floor_stop'] is False and guard['strict_floor_bytes']==DISK_FLOOR and
        guard['process_reserve_bytes']==PROCESS_RESERVE,'process resource guard identity/stop')
    before,minimum,after=(guard[name] for name in ('before_free_bytes','minimum_observed_free_bytes','after_free_bytes'))
    require(set(before)==set(minimum)==set(after) and len(before) in (1,2),'process resource paths')
    require(all(type(value) is int and value > DISK_FLOOR for values in (before,minimum,after) for value in values.values()),'strict process disk floor')
    require(all(before[name]>DISK_FLOOR+PROCESS_RESERVE and minimum[name]<=min(before[name],after[name]) for name in before),'process reserved/minimum capacity')




def git_tree_entries(source, commit):
    """Read complete mode/type/blob identities, not a selected-path allowlist."""
    raw = subprocess.check_output(['git', 'ls-tree', '-rz', '--full-tree', commit], cwd=source)
    entries = {}
    for record in raw.split(b'\0'):
        if not record:
            continue
        metadata, name = record.split(b'\t', 1)
        mode, kind, oid = metadata.decode('ascii').split()
        relative = name.decode('utf-8')
        require(relative not in entries, 'duplicate Git source entry')
        entries[relative] = {'mode': mode, 'type': kind, 'oid': oid}
    return entries


def validate_source_lineage(pair_source, pair_commit, oracle_source, oracle_commit):
    """Bind two distinct selected suites while preserving the frozen oracle gate."""
    profile = load_json((ROOT / 'diagnostics/nested_deferred_pair/profile.json').read_text())
    for selected in (pair_commit, oracle_commit):
        require(isinstance(selected, str) and re.fullmatch('[0-9a-f]{40}', selected), 'exact selected suite commit required')
    require(oracle_commit == profile['suite_base_public_commit'], 'exact pinned oracle suite commit required')
    require(pair_commit != oracle_commit, 'distinct pair and oracle suite commits required')
    oracle_tree = command(['git', 'rev-parse', oracle_commit + '^{tree}'], oracle_source)
    require(oracle_tree == profile['suite_base_tree'], 'exact pinned oracle suite tree required')
    # This deliberately needs the historical e576 object. Never bypass or widen
    # the unchanged oracle's eleven-addition preflight for pair-owned paths.
    baseline.validate_baseline_source(oracle_source, oracle_commit)
    require(command(['git', 'rev-parse', oracle_commit + '^{tree}'], pair_source) == oracle_tree,
            'pair source must contain the exact oracle Git object')
    subprocess.check_call(['git', 'merge-base', '--is-ancestor', oracle_commit, pair_commit], cwd=pair_source)
    original = git_tree_entries(oracle_source, oracle_commit)
    selected = git_tree_entries(pair_source, pair_commit)
    require(len(original) == 674, 'complete 674-entry oracle source inventory')
    require(all(selected.get(path) == entry for path, entry in original.items()), 'changed or missing baseline Git source entry')
    require(set(selected) - set(original) == set(NEW_SUITE_FILES), 'exact nineteen owned pair additions required')
    require(all(selected[path]['type'] == 'blob' and selected[path]['mode'] == '100644' for path in NEW_SUITE_FILES),
            'regular nonexecutable pair source additions required')
    return {'oracle_suite': {'commit': oracle_commit, 'tree': oracle_tree},
            'pair_suite': {'commit': pair_commit, 'tree': command(['git', 'rev-parse', pair_commit + '^{tree}'], pair_source)},
            'historical_oracle_base': {'commit': baseline.SUITE_BASE, 'tree': baseline.SUITE_BASE_TREE},
            'baseline_entries': original, 'pair_additions': sorted(NEW_SUITE_FILES)}


def regression_source_context(parent, pair_source, oracle_source, oracle_commit):
    """Every wrapper independently reopens the parent's explicit source lineage."""
    lineage = validate_source_lineage(pair_source, parent['suite']['commit'], oracle_source, oracle_commit)
    require(parent['source_lineage'] == lineage, 'regression parent source lineage differs')
    require(parent['suite']['tree'] == lineage['pair_suite']['tree'], 'regression selected pair tree differs')
    return lineage


def validate_baseline(directory, suite_source, upstream_source, suite_commit, recorded_execution_root=None):
    profile = load_json((ROOT / 'diagnostics/nested_deferred_pair/profile.json').read_text())
    require(isinstance(suite_commit, str) and re.fullmatch('[0-9a-f]{40}', suite_commit), 'independently selected exact baseline suite commit required')
    tree = command(['git', 'rev-parse', suite_commit + '^{tree}'], suite_source)
    result = baseline.verify_bundle(directory, suite_commit, tree, suite_source, upstream_source, recorded_execution_root=recorded_execution_root)
    require(result['source_bound'], 'Rust baseline must be independently source-bound')
    for relative in baseline.RETAIN:
        expected = profile['approved_fixture_sha256'][relative]
        require(baseline.digest(directory / baseline.retained_path(relative)) == expected, 'baseline fixture changed: ' + relative)
    return {'suite_commit': suite_commit, 'suite_tree': tree, 'manifest_sha256': baseline.digest(directory / 'manifest.json'),
            'raw_sha256': baseline.digest(directory / 'raw.json'), 'source_bound': True,
            'recorded_execution_root': str(Path(recorded_execution_root).resolve() if recorded_execution_root is not None else directory.resolve())}


def inventory(directory):
    return {str(path.relative_to(directory)): {'sha256': baseline.digest(path), 'size': path.stat().st_size}
            for path in sorted(directory.rglob('*')) if path.is_file()
            and str(path.relative_to(directory)) not in OMITTED_BUILD_CACHES and path.relative_to(directory) != Path('manifest.json')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core-source', type=Path, required=True)
    parser.add_argument('--core-commit', required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--regression-baseline', type=Path, required=True)
    parser.add_argument('--margin-baseline', type=Path, required=True)
    parser.add_argument('--flat-baseline', type=Path, required=True)
    parser.add_argument('--flat-baseline-recorded-execution-root', type=Path)
    parser.add_argument('--margin-baseline-recorded-execution-root', type=Path)
    parser.add_argument('--regression-baseline-recorded-execution-root', type=Path)
    parser.add_argument('--baseline-suite-source', type=Path, default=ROOT)
    parser.add_argument('--baseline-suite-commit', required=True)
    parser.add_argument('--baseline-recorded-execution-root', type=Path)
    parser.add_argument('--upstream-source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    policy()
    mutation_descriptors()
    core, original = args.core_source.resolve(), args.baseline.resolve()
    profile = load_json((ROOT / 'diagnostics/nested_deferred_pair/profile.json').read_text())
    core_before, suite_before = identity(core), identity(ROOT)
    require(core_before['clean'] and suite_before['clean'], 'exact clean sources required')
    require(args.core_commit == profile['candidate_commit'] == core_before['commit'] and core_before['tree'] == profile['candidate_tree'], 'candidate public commit/tree pin')
    require(profile['candidate_pin_status'] == 'published-exact-commit-tree', 'candidate publication pin still pending')
    oracle_before = identity(args.baseline_suite_source)
    require(oracle_before['clean'] and oracle_before['commit'] == args.baseline_suite_commit, 'exact clean oracle checkout required')
    lineage = validate_source_lineage(ROOT, suite_before['commit'], args.baseline_suite_source, args.baseline_suite_commit)
    require(oracle_before['tree'] == lineage['oracle_suite']['tree'], 'oracle checkout tree')
    approved = validate_baseline(original, args.baseline_suite_source, args.upstream_source, args.baseline_suite_commit,
                                 args.baseline_recorded_execution_root)
    inputs = source_preflight(core, args.core_commit)
    resource_budget = require_capacity(ROOT, 2 * 1024**3)
    require(shutil.disk_usage(ROOT).free >= 3 * 1024**3, 'Need 2GiB execution/evidence budget plus strict 1GiB floor; preserve evidence and run heavy pair in CI')
    for relative, expected in profile['approved_fixture_sha256'].items():
        require(baseline.digest(ROOT / relative) == expected, 'frozen source changed: ' + relative)
    out = args.output.resolve()
    require(out.is_relative_to(ROOT / '_build'), 'output must be a new ignored _build directory')
    out.mkdir(parents=True, exist_ok=False)
    stage = out / 'build-source'
    stage.mkdir()
    (stage / 'moon.mod').write_text(MODULE)
    shutil.copy2(core / 'moon.mod', out / 'original-core-moon.mod')
    for relative in CORE_API_FILES:
        destination = out / 'core-api' / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(core / relative, destination)
    for relative in inputs:
        destination = stage / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(core / relative, destination)
    shutil.copytree(ROOT / 'adapters/nested_deferred_moonbit', stage / 'probe')
    for relative in SUITE_FILES:
        destination = out / retained_path(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    shutil.copytree(original, out / 'rust-baseline')
    shutil.copy2(original / 'scenarios.json', out / 'scenarios.json')
    environment = os.environ.copy()
    token = str(uuid.uuid4())
    environment['GPUI_SCENARIOS'] = (out / 'scenarios.json').read_text()
    environment['GPUI_RUN_TOKEN'] = token
    moon = shutil.which('moon')
    require(moon is not None, 'MoonBit toolchain missing')
    moon = str(Path(moon).resolve())
    (out / 'toolchain.txt').write_text(command([moon, 'version', '--all']) + '\n' + command(['cc', '--version']) + '\n' + command(['ar', '--version']) + '\n')
    tools = {}
    for name in ('moon', 'moonc', 'cc', 'ar'):
        require(shutil.which(name) is not None, 'missing compiler: ' + name)
        path = Path(shutil.which(name)).resolve()
        destination = out / 'tool-binaries' / name
        destination.parent.mkdir(exist_ok=True)
        shutil.copy2(path, destination)
        tools[name] = {'path': str(path), 'command_path': shutil.which(name), 'sha256': baseline.digest(path), 'retained': 'tool-binaries/' + name}
    moon_home = Path(environment['MOON_HOME']).resolve()
    environment['CC'] = tools['cc']['path']
    require_native_environment(environment, tools)
    environment['MOON_HOME'] = str(moon_home)
    toolchain_inputs = []
    for relative in TOOLCHAIN_ROOTS:
        source = moon_home / relative
        for path in (sorted(source.rglob('*')) if source.is_dir() else [source]):
            if path.is_file():
                name = str(path.relative_to(moon_home))
                destination = out / 'toolchain-inputs' / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
                toolchain_inputs.append(name)
    require(toolchain_inputs, 'native toolchain input inventory missing')
    manifest = {'schema_version': 1, 'layer': LAYER, 'run_token': token, 'qualification': 'exact-clean-source-pair',
        'review_or_publication_claim': False, 'requested_core_commit': args.core_commit, 'recorded_execution_root': str(out),
        'core': core_before, 'suite': suite_before, 'oracle_suite': oracle_before,
        'source_lineage': lineage, 'baseline': approved, 'core_inputs': inputs,
        'core_api_context': {'role': 'noncompiled-published-api-context', 'files': list(CORE_API_FILES)},
        'preexecution_contract_sha256': {p: baseline.digest(ROOT / p) for p in POLICY_FILES},
        'toolchain_inputs': sorted(toolchain_inputs), 'toolchain_home': str(moon_home),
        'input_environment': {'GPUI_RUN_TOKEN': token, 'GPUI_SCENARIOS_sha256': baseline.digest(out / 'scenarios.json'),
                              'CC': environment['CC'], 'MOON_CC': environment.get('MOON_CC'), 'MOONBIT_NEW_NATIVE': environment.get('MOONBIT_NEW_NATIVE'), 'MOON_HOME': environment['MOON_HOME']},
        'tool_binaries': tools, 'platform': {'system': platform.system(), 'machine': platform.machine()},
        'resource_budget': {'strict_floor_bytes':DISK_FLOOR,'pair_reserve_bytes':2*1024**3,'before_free_bytes':resource_budget},
        'started_at': now(), 'omitted_non_input_build_caches': list(OMITTED_BUILD_CACHES), 'files': {}}
    manifest['build_plan'] = execute([moon, 'build', '--target', 'native', '--deny-warn', '--dry-run', '--verbose', 'probe'], stage, out, 'build-plan', environment)
    require(manifest['build_plan']['returncode'] == 0 and not manifest['build_plan']['timed_out'], 'build plan failed; logs retained')
    manifest['native_build_plan'] = native_build_plan((out / 'build-plan.stdout').read_text(), tools, stage)
    require(set(manifest['native_build_plan']['required_toolchain']) <= set(toolchain_inputs), 'unretained planned native toolchain input')
    manifest['build'] = execute([moon, 'build', '--target', 'native', '--deny-warn', '--verbose', 'probe'], stage, out, 'build', environment)
    if manifest['build']['returncode'] == 0:
        manifest['generated_build_inputs'] = native_generated_inventory(stage / '_build/native/debug/build', manifest['native_build_plan'])
        shutil.copy2(stage / '_build/native/debug/build/probe/probe.exe', out / 'candidate-probe')
        manifest['execution'] = execute([str(out / 'candidate-probe')], stage, out, 'candidate', environment)
        (out / 'candidate.stdout').rename(out / 'candidate-raw.json')
    manifest['core_after'], manifest['suite_after'] = identity(core), identity(ROOT)
    manifest['tool_binaries_after'] = {name: baseline.digest(Path(item['path'])) for name, item in tools.items()}
    manifest['tool_commands_after'] = {name: baseline.digest(Path(item['command_path'])) for name, item in tools.items()}
    manifest['toolchain_inputs_after'] = {name: baseline.digest(moon_home / name) for name in toolchain_inputs}
    if manifest.get('execution', {}).get('returncode') == 0:
        try:
            comparison = compare_observations(load_json((original / 'raw.json').read_text()),
                load_json((out / 'candidate-raw.json').read_text()), load_json((out / 'scenarios.json').read_text()))
            (out / 'comparison.json').write_text(json.dumps(comparison, indent=2) + '\n')
        except (ValueError, KeyError, TypeError, IndexError) as error:
            (out / 'comparison-failure.json').write_text(json.dumps({'error': str(error), 'type': type(error).__name__}, indent=2) + '\n')
    if (out / 'comparison.json').is_file() and comparison['passed']:
        from regressions import execute_regressions
        try:
            manifest['regressions'] = execute_regressions(out, environment, args.regression_baseline.resolve(),
                {'pair_suite_source': ROOT, 'suite_source': args.baseline_suite_source, 'upstream_source': args.upstream_source,
                 'suite_commit': args.baseline_suite_commit,
                 'recorded_execution_root': args.regression_baseline_recorded_execution_root,
                 'pair_manifest': manifest})
            from regressions import execute_margin_regression
            manifest['margin_regression'] = execute_margin_regression(out, environment, args.margin_baseline.resolve(),
                {'pair_suite_source': ROOT, 'suite_source': args.baseline_suite_source, 'upstream_source': args.upstream_source,
                 'suite_commit': args.baseline_suite_commit,
                 'recorded_execution_root': args.margin_baseline_recorded_execution_root, 'pair_manifest': manifest})
            from regressions import execute_flat_regression
            manifest['flat_regression'] = execute_flat_regression(out, environment, args.flat_baseline.resolve(),
                {'pair_suite_source': ROOT, 'suite_source': args.baseline_suite_source, 'upstream_source': args.upstream_source,
                 'suite_commit': args.baseline_suite_commit,
                 'recorded_execution_root': args.flat_baseline_recorded_execution_root, 'pair_manifest': manifest})
        except (ValueError, TypeError, KeyError, IndexError, OSError) as error:
            manifest['regression_failure'] = {'error': str(error), 'type': type(error).__name__}
    # The extension is part of this execution interval: bind source and tools
    # again after both binaries have finished, not merely after the first corpus.
    manifest['core_after'], manifest['suite_after'] = identity(core), identity(ROOT)
    manifest['tool_binaries_after'] = {name: baseline.digest(Path(item['path'])) for name, item in tools.items()}
    manifest['tool_commands_after'] = {name: baseline.digest(Path(item['command_path'])) for name, item in tools.items()}
    manifest['toolchain_inputs_after'] = {name: baseline.digest(moon_home / name) for name in toolchain_inputs}
    manifest['oracle_suite_after'] = identity(args.baseline_suite_source)
    require(manifest['oracle_suite_after'] == oracle_before, 'oracle source identity changed; evidence retained')
    require(validate_source_lineage(ROOT, suite_before['commit'], args.baseline_suite_source, args.baseline_suite_commit) == lineage, 'source lineage changed')
    manifest['finished_at'] = now()
    manifest['files'] = inventory(out)
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    require(manifest['core_after'] == core_before and manifest['suite_after'] == suite_before, 'source identity changed; evidence retained')
    require(all(manifest['tool_binaries_after'][name] == manifest['tool_commands_after'][name] == item['sha256'] for name, item in tools.items()), 'compiler changed during run')
    require(all(manifest['toolchain_inputs_after'][name] == baseline.digest(out / 'toolchain-inputs' / name) for name in toolchain_inputs), 'runtime inputs changed during run')
    require(manifest['build']['returncode'] == 0, 'candidate build failed; evidence retained')
    require(manifest.get('execution', {}).get('returncode') == 0, 'candidate execution failed; evidence retained')
    require((out / 'comparison.json').is_file(), 'candidate trace invalid; evidence retained')
    require_semantic_match(comparison)
    require('regressions' in manifest and manifest['regressions']['passed'], 'original/fractional regression pair failed; evidence retained')
    require(manifest.get('margin_regression', {}).get('passed'), 'same-core margin regression failed; evidence retained')
    require(manifest.get('flat_regression', {}).get('passed'), 'same-core flat-priority regression failed; evidence retained')
    print(json.dumps({'evidence': str(out), 'qualification': manifest['qualification'], 'counts': comparison['counts']}))


if __name__ == '__main__': main()
