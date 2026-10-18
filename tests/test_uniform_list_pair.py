"""Checker-only synthetic fixtures. None are engine evidence or expected Rust output."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest
import json
import tempfile
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'diagnostics/uniform_list_pair'))
from compare import (BEHAVIORAL_MUTATIONS, RUNTIME_CONTROL_MUTATIONS,
                     compare_observations, distinct_states, rust_frame,
                     validate_mutation_outcomes)
spec = importlib.util.spec_from_file_location('diagnostic_test_helpers', ROOT / 'tests/test_uniform_list_diagnostic.py')
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
pair_spec = importlib.util.spec_from_file_location('uniform_list_pair_runner', ROOT / 'diagnostics/uniform_list_pair/run.py')
pair_run = importlib.util.module_from_spec(pair_spec)
pair_spec.loader.exec_module(pair_run)


def synthetic_pair():
    rust, corpus = helpers.synthetic_checker_input()
    result, pending = [], None
    for original in rust['cases'][0]['events']:
        event = original['event']
        kind = event['type']
        if kind == 'operation_start': original['frame'] -= 1
        entry = copy.deepcopy(original)
        if kind == 'frame_start': pending = []
        if pending is not None: pending.append(original)
        if kind == 'constructed':
            index = event['item_id']
            entry['event'].update(row_id=str(1000 + 2 * index), inner_id=str(1001 + 2 * index))
        if kind == 'frame_start': entry['event']['logical_layout_scale'] = 1
        if kind == 'frame_end':
            normalized, _ = rust_frame(pending)
            def emit(value): result.append({'sequence': 0, 'operation': original['operation'], 'frame': original['frame'], 'event': value})
            emit({'type': 'node', 'id': '1', 'parent': None, 'bounds': [0, 0, 420, 420], 'factory_call': None})
            emit({'type': 'node', 'id': '2', 'parent': '1', 'bounds': [40, 50, 220, 52], 'factory_call': None})
            for row in normalized['rows']:
                identifier = str(1000 + 2 * row['item_id'] + (row['kind'] == 'inner'))
                emit({'type': 'node', 'id': identifier, 'parent': '2' if row['kind'] == 'row' else str(int(identifier) - 1),
                      'bounds': row['bounds'], 'factory_call': original['frame'] * 3})
            for identifier, box in [('1', [0, 0, 420, 420]), ('2', [40, 50, 220, 52])]:
                emit({'type': 'scene', 'kind': 'clip_push', 'id': identifier, 'bounds': box})
            for row in normalized['rows']:
                emit({'type': 'scene', 'kind': 'quad', 'id': str(1000 + 2 * row['item_id'] + (row['kind'] == 'inner')), 'bounds': row['bounds']})
            for identifier in ('2', '1'): emit({'type': 'scene', 'kind': 'clip_pop', 'id': identifier, 'bounds': None})
            entry['event'] = {'type': 'frame_end', 'state': normalized['state']}
            pending = None
        if kind == 'operation_end': entry['event'] = {'type': 'operation_end', 'configuration': event['configuration'], 'state': normalized['state']}
        if kind not in ('request_layout', 'prepaint'): result.append(entry)
    for i, entry in enumerate(result): entry['sequence'] = i
    candidate = {'schema_version': 1, 'layer': 'compiled-moonbit-uniform-list-semantics',
                 'fixture': 'font-free-nested-auto-height', 'logical_layout_scale': 1, 'platform_scale_claim': False,
                 'input': copy.deepcopy(corpus), 'run_token': 'synthetic-checker-only-not-observed',
                 'cases': [{'id': corpus['cases'][0]['id'], 'events': result}]}
    return rust, candidate, corpus


class PairContracts(unittest.TestCase):
    def test_behavioral_mutations_cannot_regress_to_runtime_failure(self):
        results = [{'mutation': name, 'outcome': 'executed-semantic-rejection'}
                   for name in sorted(BEHAVIORAL_MUTATIONS)]
        results += [{'mutation': name, 'outcome': 'executed-runtime-rejection'}
                    for name in sorted(RUNTIME_CONTROL_MUTATIONS)]
        validate_mutation_outcomes(results)
        self.assertEqual(len(BEHAVIORAL_MUTATIONS), 12)
        for index in range(len(results)):
            rejected = ['survived', 'executed-timeout', 'compile-rejection-not-executed']
            if results[index]['mutation'] in BEHAVIORAL_MUTATIONS:
                rejected.append('executed-runtime-rejection')
            for outcome in rejected:
                changed = copy.deepcopy(results)
                changed[index]['outcome'] = outcome
                with self.subTest(name=changed[index]['mutation'], outcome=outcome):
                    with self.assertRaises(ValueError): validate_mutation_outcomes(changed)
        for changed in (results[:-1], results + [results[0]],
                        results[:-1] + [{'mutation': 'unknown', 'outcome': 'executed-semantic-rejection'}]):
            with self.assertRaises(ValueError): validate_mutation_outcomes(changed)

    def test_synthetic_checker_pair(self):
        result = compare_observations(*synthetic_pair())
        self.assertEqual(result['counts']['compared_operations'], 1)
        self.assertEqual(result['numeric_tolerance'], 0)

    def test_corrupted_candidate_raw_rejected(self):
        changes = [
            ('factory', None, 'range', [1, 2]),
            ('constructed', None, 'row_id', '1002'),
            ('constructed', None, 'item_id', 99),
            ('node', '1000', 'bounds', [40, 50, 220, 27]),
            ('node', '1000', 'factory_call', 1),
            ('node', '1000', 'parent', '1'),
            ('node', '1001', 'bounds', [40, 50, 220, 25]),
            ('scene', '2', 'bounds', [0, 0, 420, 420]),
        ]
        for kind, identifier, key, value in changes:
            with self.subTest(kind=kind, key=key):
                rust, candidate, corpus = synthetic_pair()
                event = next(e['event'] for e in candidate['cases'][0]['events']
                             if e['operation'] != 'initial' and e['event']['type'] == kind
                             and (identifier is None or e['event'].get('id') == identifier))
                event[key] = value
                with self.assertRaises(ValueError): compare_observations(rust, candidate, corpus)

    def test_core_state_corruption_rejected(self):
        for key, value in [('offset', [0, 1]), ('max_offset', [0, 0]), ('content_size', [220, 52]),
                           ('measured_item_size', [220, 27]), ('visible_range', [1, 3]), ('item_count', 49)]:
            rust, candidate, corpus = synthetic_pair()
            # Change both actual-frame and snapshot copies to exercise the pair,
            # rather than merely the candidate's self-consistency check.
            for entry in candidate['cases'][0]['events']:
                if entry['operation'] != 'initial' and 'state' in entry['event']:
                    entry['event']['state'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): compare_observations(rust, candidate, corpus)

    def test_missing_frames_clip_and_order_rejected(self):
        for predicate in [lambda e: e['event']['type'] == 'frame_end',
                          lambda e: e['event']['type'] == 'scene' and e['event']['kind'] == 'clip_pop',
                          lambda e: e['event']['type'] == 'scene' and e['event']['kind'] == 'clip_push']:
            rust, candidate, corpus = synthetic_pair()
            events = candidate['cases'][0]['events']
            index = next(i for i, e in enumerate(events) if e['operation'] != 'initial' and predicate(e))
            events.pop(index)
            for i, entry in enumerate(events): entry['sequence'] = i
            with self.assertRaises(ValueError): compare_observations(rust, candidate, corpus)

    def test_exact_no_tolerance(self):
        rust, candidate, corpus = synthetic_pair()
        for e in candidate['cases'][0]['events']:
            if e['operation'] != 'initial' and 'state' in e['event']:
                e['event']['state']['offset'][1] = 0.00000001
        with self.assertRaises(ValueError): compare_observations(rust, candidate, corpus)

    def test_frame_stutter_does_not_erase_intermediate_change(self):
        a, b = {'state': {'offset': 0}}, {'state': {'offset': 1}}
        self.assertEqual(distinct_states([{'normalized': a}, {'normalized': a}], a), [a])
        self.assertEqual(distinct_states([{'normalized': a}, {'normalized': b}, {'normalized': a}], a), [a, b, a])
        self.assertEqual(distinct_states([], a), [a])

    def test_multiple_source_frames_and_no_redraw_operation(self):
        rust, candidate, corpus = synthetic_pair()
        source_events = rust['cases'][0]['events']
        start = next(i for i, e in enumerate(source_events) if e['operation'] == 'configure-dpr-one')
        duplicate = copy.deepcopy(source_events[start + 1:-1])
        for entry in duplicate:
            entry['frame'] = 3
            if entry['event'].get('factory_call') is not None:
                entry['event']['factory_call'] += 3
        source_events[-1:-1] = duplicate
        source_events[-1]['frame'] = 3
        operation = {'id': 'no-redraw-up', 'action': 'up', 'position': [100, 60]}
        corpus['cases'][0]['operations'].append(operation)
        candidate['input']['cases'][0]['operations'].append(copy.deepcopy(operation))
        for raw, frame in ((rust, 3), (candidate, 2)):
            events = raw['cases'][0]['events']
            end = copy.deepcopy(events[-1])
            end.update(operation=operation['id'])
            events.append({'sequence': 0, 'operation': operation['id'], 'frame': frame,
                           'event': {'type': 'operation_start', 'input': operation, 'applied_input': operation}})
            if raw is candidate:
                events.append({'sequence': 0, 'operation': operation['id'], 'frame': frame,
                               'event': {'type': 'route', 'capture': ['1', '2', '1000', '1001'], 'bubble': ['1001', '1000', '2', '1']}})
            if raw is candidate:
                start = next(i for i, e in enumerate(events) if e['operation'] == 'configure-dpr-one' and e['event']['type'] == 'frame_start')
                stop = next(i for i in range(start, len(events)) if events[i]['event']['type'] == 'frame_end')
                fresh = copy.deepcopy(events[start:stop + 1])
                for entry in fresh:
                    entry.update(operation=operation['id'], frame=3)
                    if entry['event'].get('factory_call') is not None: entry['event']['factory_call'] += 3
                events.extend(fresh)
                end['frame'] = 3
            events.append(end)
            for i, entry in enumerate(events): entry['sequence'] = i
        result = compare_observations(rust, candidate, corpus)
        self.assertEqual(result['counts']['rust_frames'], 3)
        self.assertEqual(result['counts']['candidate_frames'], 3)
        self.assertEqual(result['counts']['compared_operations'], 2)

    def test_whole_candidate_frame_cannot_disappear(self):
        rust, candidate, corpus = synthetic_pair()
        events = candidate['cases'][0]['events']
        start = next(i for i, e in enumerate(events) if e['operation'] == 'configure-dpr-one' and e['event']['type'] == 'frame_start')
        stop = next(i for i in range(start, len(events)) if events[i]['event']['type'] == 'frame_end')
        del events[start:stop + 1]
        events[-1]['frame'] = 1
        for i, entry in enumerate(events): entry['sequence'] = i
        with self.assertRaisesRegex(ValueError, 'exactly one complete frame'):
            compare_observations(rust, candidate, corpus)

    def test_public_profile_and_fresh_fixture_hashes(self):
        profile = json.loads((ROOT / 'diagnostics/uniform_list_pair/profile.json').read_text())
        self.assertEqual(profile['candidate_commit'], 'b9916950350b7d433ecca0d6fa88e39c957b8b6b')
        self.assertEqual(profile['candidate_tree'], 'be95df375c707bd6cf961ef7959e93772b34a966')
        for relative, digest in profile['approved_fixture_sha256'].items():
            self.assertEqual(pair_run.baseline.digest(ROOT / relative), digest)
        self.assertEqual(pair_run.suite_retained_path('.github/workflows/uniform-list-diagnostic.yml'), 'suite/workflows/uniform-list-diagnostic.yml')
        self.assertEqual(set(pair_run.OMITTED_BUILD_CACHES), {'build-source/_build/.moon_db', 'build-source/_build/.moon-lock'})
        self.assertNotIn('include-hidden-files: true', (ROOT / '.github/workflows/uniform-list-diagnostic.yml').read_text())

    def test_fresh_mode_requires_external_commit_and_unchanged_fixture(self):
        profile = json.loads((ROOT / 'diagnostics/uniform_list_pair/profile.json').read_text())
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for relative in profile['approved_fixture_sha256']:
                destination = directory / 'retained' / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes((ROOT / relative).read_bytes())
            (directory / 'manifest.json').write_text(json.dumps({'upstream': {'commit': profile['upstream_commit'], 'tree': profile['upstream_tree']}}))
            for name in ('raw.json', 'scenarios.json', 'probe'): (directory / name).write_text('synthetic fixture ONLY; no engine output')
            with patch.object(pair_run.baseline, 'verify_bundle', return_value={'source_bound': True}) as verify_bundle, patch.object(pair_run, 'command', return_value='e' * 40):
                result = pair_run.validate_baseline(directory, ROOT, Path('/synthetic-upstream'), 'f' * 40)
                self.assertEqual(result['mode'], 'fresh-source-bound')
                verify_bundle.assert_called_with(directory, 'f' * 40, 'e' * 40, ROOT, Path('/synthetic-upstream'))
                self.assertNotIn('artifact_id', result)
                with self.assertRaises(ValueError): pair_run.validate_baseline(directory, ROOT, Path('/synthetic-upstream'))
                (directory / 'retained/adapters/uniform_list_rust/src/main.rs').write_text('changed source')
                with self.assertRaisesRegex(ValueError, 'changed approved fixture'):
                    pair_run.validate_baseline(directory, ROOT, Path('/synthetic-upstream'), 'f' * 40)

    def test_source_fixture_and_baseline_stay_separate(self):
        source = (ROOT / 'adapters/uniform_list_moonbit/main.mbt').read_text()
        for marker in ('UniformList::new', 'UniformListClickSession::new', '.scroll_wheel(', '.request_layout(', '.prepaint()', '.reconcile(', '.paint().commands()', 'range.id('):
            self.assertIn(marker, source)
        for forbidden in ('.floor()', '.ceil()', 'index.to_double()', 'expected_rows', 'with_layout_bounds'):
            self.assertNotIn(forbidden, source)

if __name__ == '__main__': unittest.main()
