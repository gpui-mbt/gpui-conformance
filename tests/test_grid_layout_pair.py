"""Synthetic checker inputs only. These tests do not execute either engine."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pair = load('grid_pair_compare', 'diagnostics/grid_layout_pair/compare.py')
helpers = load('grid_checker_helpers', 'tests/test_grid_layout_diagnostic.py')
with patch.dict(sys.modules, {'compare': pair}):
    runner = load('grid_pair_run', 'diagnostics/grid_layout_pair/run.py')
    with patch.dict(sys.modules, {'run': runner}):
        verifier = load('grid_pair_verify', 'diagnostics/grid_layout_pair/verify.py')
        with patch.dict(sys.modules, {'verify': verifier}):
            mutants = load('grid_pair_mutants', 'diagnostics/grid_layout_pair/run_mutants.py')


def synthetic_pair():
    """Translate a manually authored checker fixture, never engine observations."""
    rust, corpus, witnesses = helpers.synthetic_checker_input()
    case = corpus['cases'][0]
    events, frame = [], 0
    geometry = witnesses['cases'][case['id']]['bounds']
    topology = pair.topology(case)
    def emit(event, operation):
        events.append({'sequence': len(events), 'operation': operation, 'frame': frame, 'event': event})
    for operation, input_value in pair.operations(case):
        emit({'type': 'operation_start', 'input': input_value}, operation)
        scale = 2 if operation == 'initial' else 1
        if operation in ('initial', 'configured'):
            frame += 1
            emit({'type': 'frame_start', 'scale_factor': scale, 'window_size': [640, 640]}, operation)
            emit({'type': 'request_start'}, operation)
            emit({'type': 'request_end', 'callback_count': 0}, operation)
            emit({'type': 'prepaint_start'}, operation)
            emit({'type': 'callback', 'node': 'query', 'size': [100, 60]}, operation)
            emit({'type': 'prepaint_end', 'callback_count': 1, 'overflow': False}, operation)
            for name, node in topology.items():
                emit({'type': 'node', 'node': name, 'id': node['numeric_id'], 'parent': node['parent'], 'bounds': geometry[name]}, operation)
            emit({'type': 'scene', 'kind': 'quad', 'node': 'leaf', 'bounds': geometry['leaf']}, operation)
            emit({'type': 'frame_end', 'scale_factor': scale, 'window_size': [640, 640]}, operation)
        else:
            for action in ('down', 'up'):
                emit({'type': 'route', 'action': action, 'position': [21, 31], 'target': 'leaf',
                      'capture': ['$host', 'grid', 'query', 'leaf'], 'bubble': ['leaf', 'query', 'grid', '$host']}, operation)
        emit({'type': 'operation_end', 'scale_factor': scale}, operation)
    candidate = {'schema_version': 1, 'layer': pair.CANDIDATE_LAYER, 'fixture': 'font-free-bounded-grid',
        'run_token': 'synthetic-candidate-checker-0001', 'input': copy.deepcopy(corpus),
        'cases': [{'id': case['id'], 'status': 'observed', 'events': events}]}
    return rust, candidate, corpus, witnesses


def event(candidate, kind, operation='initial'):
    return next(e['event'] for e in candidate['cases'][0]['events'] if e['operation'] == operation and e['event']['type'] == kind)


class GridPairContracts(unittest.TestCase):
    def test_synthetic_pair_claim_and_both_scales(self):
        result = pair.compare_observations(*synthetic_pair())
        self.assertTrue(result['passed'])
        self.assertEqual(result['counts'], {'supported_cases': 1, 'unsupported_cases': 0, 'rust_frames': 2, 'candidate_frames': 2, 'compared_operations': 3})
        ops = result['cases'][0]['operations']
        self.assertEqual([op['scale_factor'] for op in ops], [2, 1, 1])
        self.assertEqual(ops[2]['compared_candidate_frame'], 2)
        self.assertIn('no unchanged-example', result['claim'])

    def test_candidate_lifecycle_callback_and_topology_corruptions(self):
        mutations = [
            lambda c: event(c, 'request_end').update(callback_count=1),
            lambda c: event(c, 'callback').update(size=[640, 640]),
            lambda c: event(c, 'callback').update(node='leaf'),
            lambda c: event(c, 'prepaint_end').update(callback_count=0),
            lambda c: event(c, 'node').update(parent='grid'),
            lambda c: event(c, 'node').update(id='999'),
            lambda c: event(c, 'scene').update(kind='clip_push'),
            lambda c: event(c, 'scene').update(bounds=[20, 30, 11, 7]),
            lambda c: event(c, 'frame_start').update(scale_factor=1),
            lambda c: event(c, 'frame_end').update(window_size=[600, 640]),
            lambda c: event(c, 'route', 'inside').update(capture=['leaf']),
            lambda c: event(c, 'route', 'inside').update(position=[22, 31]),
            lambda c: c['cases'][0]['events'][4].update(frame=9),
            lambda c: c['cases'][0]['events'][4].update(operation='configured'),
            lambda c: c['cases'][0]['events'][4].update(sequence=99),
        ]
        for index, mutate in enumerate(mutations):
            rust, candidate, corpus, witnesses = synthetic_pair()
            mutate(candidate)
            with self.subTest(index=index), self.assertRaises(ValueError): pair.compare_observations(rust, candidate, corpus, witnesses)

    def test_early_missing_duplicate_and_extra_callback_rejected(self):
        for mutation in ('early', 'missing', 'duplicate', 'trailing'):
            rust, candidate, corpus, witnesses = synthetic_pair()
            events = candidate['cases'][0]['events']
            index = next(i for i, e in enumerate(events) if e['event']['type'] == 'callback')
            if mutation == 'early': events.insert(3, events.pop(index))
            if mutation == 'missing': events.pop(index)
            if mutation == 'duplicate': events.insert(index, copy.deepcopy(events[index]))
            if mutation == 'trailing': events.append(copy.deepcopy(events[-1]))
            helpers.resequence(events)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): pair.compare_observations(rust, candidate, corpus, witnesses)

    def test_geometry_corruption_just_beyond_f32_serialization_tolerance(self):
        pair.vector([10 + pair.TOLERANCE / 2], [10], 'within serialization tolerance')
        with self.assertRaises(ValueError): pair.vector([10 + pair.TOLERANCE + .000001], [10], 'beyond serialization tolerance')
        rust, candidate, corpus, witnesses = synthetic_pair()
        geometry = event(candidate, 'scene')['bounds'].copy()
        geometry[2] += pair.TOLERANCE + .000001
        event(candidate, 'scene')['bounds'] = geometry
        with self.assertRaisesRegex(ValueError, 'scene/tree bounds'):
            pair.compare_observations(rust, candidate, corpus, witnesses)

    def test_numeric_domain_is_enforced_without_widening_tolerance(self):
        pair.bounded_geometry([1024, -1024], 'domain boundary')
        with self.assertRaises(ValueError): pair.bounded_geometry([1024.000001, 0], 'over boundary')
        with self.assertRaises(ValueError): pair.bounded_geometry([1000, 0, 25, 1], 'far edge outside', rectangle=True)
        rust, candidate, corpus, witnesses = synthetic_pair()
        event(candidate, 'node')['bounds'] = [0, 0, 1025, 640]
        with self.assertRaisesRegex(ValueError, 'numeric comparison domain'):
            pair.compare_observations(rust, candidate, corpus, witnesses)

    def test_semantic_mismatch_is_retained_not_smoothed_or_relabelled(self):
        rust, candidate, corpus, witnesses = synthetic_pair()
        # Internally consistent scene/tree geometry can still disagree with Rust.
        for entry in candidate['cases'][0]['events']:
            item = entry['event']
            if item['type'] in ('node', 'scene') and item.get('node') == 'leaf': item['bounds'] = [20, 30, 11, 7]
        result = pair.compare_observations(rust, candidate, corpus, witnesses)
        self.assertFalse(result['passed'])
        self.assertEqual(result['mismatches'][0]['field'], 'bounds/leaf')
        self.assertEqual(result['mismatches'][0]['rust'], [20, 30, 10, 7])
        self.assertEqual(result['mismatches'][0]['candidate'], [20, 30, 11, 7])
        with self.assertRaises(ValueError): pair.require_semantic_match(result)

    def test_consistent_wrong_route_compares_with_actual_rust_click(self):
        rust, candidate, corpus, witnesses = synthetic_pair()
        for entry in candidate['cases'][0]['events']:
            item = entry['event']
            if item['type'] == 'route': item.update(target='query', capture=['$host', 'grid', 'query'], bubble=['query', 'grid', '$host'])
        result = pair.compare_observations(rust, candidate, corpus, witnesses)
        self.assertFalse(result['passed'])
        self.assertEqual(result['mismatches'][-1]['field'], 'click_vs_leaf_route_targets')

    def test_all_frames_validated_but_redraw_counts_need_not_match(self):
        rust, candidate, corpus, witnesses = synthetic_pair()
        events = candidate['cases'][0]['events']
        start = next(i for i, e in enumerate(events) if e['operation'] == 'configured') + 1
        end = next(i for i, e in enumerate(events) if e['operation'] == 'configured' and e['event']['type'] == 'operation_end')
        extra = copy.deepcopy(events[start:end])
        for e in extra: e['frame'] = 3
        for e in events[end:]: e['frame'] = 3
        events[end:end] = extra
        helpers.resequence(events)
        result = pair.compare_observations(rust, candidate, corpus, witnesses)
        self.assertTrue(result['passed'])
        self.assertEqual(result['counts']['candidate_frames'], 3)
        self.assertEqual(result['counts']['rust_frames'], 2)
        self.assertEqual(result['cases'][0]['operations'][1]['compared_candidate_frame'], 3)
        # An invalid earlier frame cannot be hidden by a valid final frame.
        event(candidate, 'request_end', 'configured')['callback_count'] = 1
        with self.assertRaises(ValueError): pair.compare_observations(rust, candidate, corpus, witnesses)

    def test_rust_topology_checked_beyond_balanced_lifecycle(self):
        rust, candidate, corpus, witnesses = synthetic_pair()
        # The baseline validator checks each lifecycle and balanced nesting;
        # pair adds declared parentage, rather than claiming construction logs.
        events = rust['cases'][0]['events']
        a = next(i for i, e in enumerate(events) if e['event'] == {'type': 'request_layout', 'node': 'query'})
        block = events[a:a + 2]
        del events[a:a + 2]
        b = next(i for i, e in enumerate(events) if e['event'] == {'type': 'request_layout_end', 'node': 'grid'}) + 1
        events[b:b] = block
        helpers.resequence(events)
        pair.baseline.verify_observations(rust, corpus, witnesses)
        with self.assertRaisesRegex(ValueError, 'parent/topology'): pair.compare_observations(rust, candidate, corpus, witnesses)

    def test_named_unsupported_is_never_silent_success(self):
        rust, candidate, corpus, witnesses = synthetic_pair()
        case = copy.deepcopy(corpus['cases'][0]); case['id'] = 'explicit-collision'
        corpus['cases'].append(case)
        rust['input'] = copy.deepcopy(corpus)
        rust_case = copy.deepcopy(rust['cases'][0]); rust_case['id'] = case['id']; rust['cases'].append(rust_case)
        candidate['input'] = copy.deepcopy(corpus)
        candidate['cases'].append({'id': 'explicit-collision', 'status': 'unsupported', 'reason': 'explicit-grid-line-placement', 'events': []})
        result = pair.compare_observations(rust, candidate, corpus, witnesses)
        self.assertEqual(result['counts']['unsupported_cases'], 1)
        self.assertEqual(result['cases'][1]['status'], 'unsupported')
        candidate['cases'][1]['reason'] = 'covered'
        with self.assertRaises(ValueError): pair.compare_observations(rust, candidate, corpus, witnesses)

    def test_production_adapter_delegates_without_reconstructed_layout(self):
        source = (ROOT / 'adapters/grid_layout_moonbit/main.mbt').read_text()
        for text in ('request_layout_with_device_scale', 'requested.prepaint()', 'painted.tree().nodes()',
                     'painted.paint().commands()', 'tree.dispatch_input(event)', 'with_query_root_size',
                     'probe.render(scenario, 2)', 'explicit-collision'):
            self.assertIn(text, source)
        for text in ('with_layout_bounds', 'expected_bounds', 'witnesses.json', 'track_width', 'floor(', 'ceil(', 'rust-baseline'):
            self.assertNotIn(text, source)

    def test_frozen_baseline_profile_and_exact_candidate_pin(self):
        profile = json.loads((ROOT / 'diagnostics/grid_layout_pair/profile.json').read_text())
        self.assertEqual(len(profile['candidate_commit']), 40)
        self.assertEqual(len(profile['candidate_tree']), 40)
        self.assertEqual(profile['supported_cases'], 12)
        self.assertEqual(profile['unsupported_cases'], pair.UNSUPPORTED)
        self.assertEqual(set(profile['approved_fixture_sha256']), set(pair.baseline.RETAIN))
        for path, digest in profile['approved_fixture_sha256'].items(): self.assertEqual(pair.baseline.digest(ROOT / path), digest)

    def test_mutations_must_execute_and_fail_semantics_not_build_crash_or_timeout(self):
        ok = {'returncode': 0, 'timed_out': False}
        bad = {'returncode': 1, 'timed_out': False}
        timeout = {'returncode': -9, 'timed_out': True}
        self.assertEqual(mutants.classify(ok, ok, {'passed': False}), 'executed-semantic-rejection')
        self.assertEqual(mutants.classify(ok, ok, validation_error='allocated size'), 'executed-semantic-rejection')
        for build, execution, comparison in ((bad, None, None), (ok, bad, None), (ok, timeout, None), (ok, ok, {'passed': True})):
            outcome = mutants.classify(build, execution, comparison)
            with self.assertRaises(ValueError): pair.validate_mutation_outcomes([{'outcome': outcome}])
        mutations = json.loads((ROOT / 'diagnostics/grid_layout_pair/mutations.json').read_text())
        self.assertGreaterEqual(len(mutations), 6)
        self.assertEqual(len({m['name'] for m in mutations}), len(mutations))
        self.assertTrue(all(m['path'].startswith(('element/', 'layout/')) for m in mutations))

    def test_inventory_keeps_nested_manifests_and_rejects_missing_source_pins(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / 'rust-baseline').mkdir()
            (root / 'manifest.json').write_text('{}')
            (root / 'rust-baseline/manifest.json').write_text('{}')
            self.assertIn('rust-baseline/manifest.json', runner.inventory(root))
            self.assertNotIn('manifest.json', runner.inventory(root))
        with self.assertRaises(ValueError): runner.validate_baseline(ROOT, ROOT, ROOT, None)

    def test_pair_bundle_relocation_source_binary_argv_and_corruption_guards(self):
        rust, candidate, corpus, witnesses = synthetic_pair()
        profile = json.loads((ROOT / 'diagnostics/grid_layout_pair/profile.json').read_text())
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            old_root = Path('/recorded-source/_build/original-pair')
            files = {'candidate-probe': b'\x7fELFsynthetic-checker-only',
                'candidate-raw.json': json.dumps(candidate).encode(), 'candidate.stderr': b'',
                'build.stdout': b'', 'build.stderr': b'', 'build-plan.stdout': b'', 'build-plan.stderr': b'',
                'scenarios.json': json.dumps(corpus).encode(), 'toolchain.txt': b'synthetic checker toolchain',
                'original-core-moon.mod': b'name = "synthetic-core"', 'build-source/moon.mod': runner.MODULE.encode(),
                'build-source/element/fake.mbt': b'// synthetic checker source',
                'toolchain-inputs/include/fake.h': b'// synthetic checker toolchain input',
                'rust-baseline/raw.json': json.dumps(rust).encode(),
                'rust-baseline/scenarios.json': json.dumps(corpus).encode(),
                'rust-baseline/retained/diagnostics/grid_layout/witnesses.json': json.dumps(witnesses).encode()}
            files.update({runner.retained_path(path): (ROOT / path).read_bytes() for path in runner.SUITE_FILES})
            for name in ('main.mbt', 'moon.pkg'): files['build-source/probe/' + name] = files['suite/adapters/grid_layout_moonbit/' + name]
            files['build-source/_build/native/debug/build/probe/probe.exe'] = files['candidate-probe']
            for path, content in files.items():
                destination = directory / path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content)
            core = {'commit': profile['candidate_commit'], 'tree': profile['candidate_tree'], 'clean': True}
            suite = {'commit': 'a' * 40, 'tree': 'b' * 40, 'clean': True}
            approved = {'recorded_execution_root': '/recorded-source/_build/original-rust', 'source_bound': True}
            phase = {'returncode': 0, 'timed_out': False, 'cwd': str(old_root / 'build-source')}
            manifest = {'schema_version': 1, 'layer': pair.LAYER, 'qualification': 'exact-clean-source-pair',
                'review_or_publication_claim': False, 'requested_core_commit': core['commit'],
                'recorded_execution_root': str(old_root), 'core': core, 'core_after': core,
                'suite': suite, 'suite_after': suite, 'baseline': approved,
                'core_inputs': ['element/fake.mbt'], 'toolchain_inputs': ['include/fake.h'],
                'tool_binaries': {'moon': {'path': '/toolchain/moon'}},
                'run_token': candidate['run_token'],
                'input_environment': {'GPUI_RUN_TOKEN': candidate['run_token'], 'GPUI_SCENARIOS_sha256': pair.baseline.digest(directory / 'scenarios.json')},
                'build': dict(phase, command=['/toolchain/moon', 'build', '--target', 'native', '--deny-warn', '--verbose', 'probe']),
                'build_plan': dict(phase, command=['/toolchain/moon', 'build', '--target', 'native', '--deny-warn', '--dry-run', '--verbose', 'probe']),
                'execution': dict(phase, command=[str(old_root / 'candidate-probe')]), 'files': runner.inventory(directory)}
            path = directory / 'manifest.json'
            path.write_text(json.dumps(manifest))
            def git(arguments, cwd=None, text=False):
                if arguments[1] == 'rev-parse': return (core['tree'] if str(cwd) == 'synthetic-core' else suite['tree']) + '\n'
                if arguments[1] == 'ls-tree': return 'element/fake.mbt\n'
                relative = arguments[2].split(':', 1)[1]
                if str(cwd) == 'synthetic-core': return files['original-core-moon.mod' if relative == 'moon.mod' else 'build-source/' + relative]
                return files[runner.retained_path(relative)]
            def inspect(): return verifier.verify(directory, ROOT, ROOT, Path('synthetic-core'), suite['commit'], core['commit'])
            with patch.object(verifier, 'validate_baseline', return_value=approved), patch.object(verifier.subprocess, 'check_output', side_effect=git):
                self.assertTrue(inspect()['candidate_source_bound'])
                self.assertTrue(inspect()['passed'])
                for mutate in (
                    lambda m: m.update(run_token='wrong-token'),
                    lambda m: m.update(recorded_execution_root='relative/pair'),
                    lambda m: m['execution'].update(command=['/bin/true']),
                    lambda m: m['build'].update(command=['moon', 'build']),
                    lambda m: m['build_plan'].update(cwd='/wrong/build-source'),
                    lambda m: m['execution'].update(returncode=2),
                    lambda m: m['build'].update(timed_out=True),
                    lambda m: m['files'].pop('candidate-probe'),
                    lambda m: m['core'].update(clean=False),
                ):
                    changed = copy.deepcopy(manifest); mutate(changed); path.write_text(json.dumps(changed))
                    with self.assertRaises(ValueError): inspect()
                path.write_text(json.dumps(manifest))
                hidden = directory / 'build-source/probe/extra.mbt'; hidden.write_text('// unlisted compiled input')
                with self.assertRaisesRegex(ValueError, 'unexpected compiled source'): inspect()
                hidden.unlink()
                source = directory / 'build-source/element/fake.mbt'
                source.write_bytes(b'// changed and rehashed engine source')
                changed = copy.deepcopy(manifest)
                changed['files']['build-source/element/fake.mbt'] = {'sha256': pair.baseline.digest(source), 'size': source.stat().st_size}
                path.write_text(json.dumps(changed))
                with self.assertRaisesRegex(ValueError, 'core Git blob'): inspect()
                source.write_bytes(files['build-source/element/fake.mbt'])
                path.write_text(json.dumps(manifest))
                (directory / 'candidate-probe').write_bytes(b'changed binary')
                with self.assertRaisesRegex(ValueError, 'changed evidence'): inspect()

    def test_ci_is_failure_preserving_and_separates_controls(self):
        source = (ROOT / '.github/workflows/grid-layout-pair.yml').read_text()
        for text in ('if: always()', 'run_mutants.py', 'run_controls.py', 'verify.py', '--core-commit', '--suite-commit'):
            self.assertIn(text, source)
        for text in ('continue-on-error: true', 'rmtree', 'rm -rf', '--allow-unqualified'):
            self.assertNotIn(text, source)
        self.assertEqual(runner.retained_path('.github/workflows/grid-layout-pair.yml'), 'suite/workflows/grid-layout-pair.yml')


if __name__ == '__main__': unittest.main()
