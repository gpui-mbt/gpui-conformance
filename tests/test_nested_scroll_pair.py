"""Comparator/fixture unit tests; synthetic records never establish runtime parity."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('nested_scroll_pair', ROOT / 'diagnostics/nested_scroll_pair/run.py')
PAIR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PAIR)


def observation(fixture, backend):
    frame = {'offsets': [[0, 0], [0, 0]], 'maximums': [[160, 240], [160, 0]],
             'bounds': [[i, [0, 0, 10, 10]] for i in range(2, 7)], 'targets': [None] * len(fixture['points'])}
    return {'schema_version': 1, 'backend': backend, 'input': copy.deepcopy(fixture),
            'cases': [{'id': case['id'], 'frames': [copy.deepcopy(frame) for _ in range(len(case['wheels']) + 1)]}
                      for case in fixture['cases']]}


class NestedScrollPairTests(unittest.TestCase):
    def setUp(self):
        self.fixture = PAIR.load(ROOT / 'diagnostics/nested_scroll_pair/scenarios.json')
        self.rust = observation(self.fixture, 'rust-gpui')
        self.moon = observation(self.fixture, 'moonbit')

    def compare(self):
        return PAIR.compare(self.rust, self.moon, self.fixture)

    def test_fixture_and_synthetic_equal_records(self):
        report = self.compare()
        self.assertEqual((report['status'], report['cases'], report['frames']), ('pass', 7, 31))

    def test_every_observed_field_detects_difference(self):
        for field in ('offsets', 'maximums', 'bounds', 'targets'):
            with self.subTest(field=field):
                changed = copy.deepcopy(self.moon)
                frame = changed['cases'][0]['frames'][1]
                if field == 'targets':
                    frame[field][0] = 5
                elif field == 'bounds':
                    frame[field][0][1][0] = 1
                else:
                    frame[field][0][0] = 1
                report = PAIR.compare(self.rust, changed, self.fixture)
                self.assertEqual(report['status'], 'mismatch')
                self.assertEqual(report['differences'][0]['field'], field)

    def test_offscreen_maximum_is_not_ignored(self):
        self.rust['cases'][3]['frames'][1]['maximums'][1][1] = 180
        self.assertEqual(self.compare()['status'], 'mismatch')

    def test_missing_extra_reordered_cases_rejected(self):
        for change in ('missing', 'extra', 'reordered'):
            with self.subTest(change=change):
                changed = copy.deepcopy(self.moon)
                if change == 'missing': changed['cases'].pop()
                if change == 'extra': changed['cases'].append(changed['cases'][0])
                if change == 'reordered': changed['cases'].reverse()
                with self.assertRaises(ValueError): PAIR.compare(self.rust, changed, self.fixture)

    def test_missing_frame_rejected(self):
        self.moon['cases'][0]['frames'].pop()
        with self.assertRaises(ValueError): self.compare()

    def test_wrong_input_rejected(self):
        self.moon['input']['cases'][0]['wheels'][0][2] = 99
        with self.assertRaises(ValueError): self.compare()

    def test_backend_and_unknown_field_rejected(self):
        self.moon['backend'] = 'rust-gpui'
        with self.assertRaises(ValueError): self.compare()
        self.moon['backend'] = 'moonbit'
        self.moon['cases'][0]['frames'][0]['expected'] = True
        with self.assertRaises(ValueError): self.compare()

    def test_nonfinite_and_boolean_observations_rejected(self):
        for value in (float('nan'), float('inf'), True):
            self.moon['cases'][0]['frames'][0]['offsets'][0][0] = value
            with self.assertRaises(ValueError): self.compare()

    def test_wrong_bounds_and_targets_rejected(self):
        self.moon['cases'][0]['frames'][0]['bounds'][0][0] = 3
        with self.assertRaises(ValueError): self.compare()
        self.moon = observation(self.fixture, 'moonbit')
        self.moon['cases'][0]['frames'][0]['targets'][0] = True
        with self.assertRaises(ValueError): self.compare()

    def test_fixture_invalid_rows_and_duplicate_ids(self):
        for value in (float('nan'), True, '1'):
            changed = copy.deepcopy(self.fixture)
            changed['cases'][0]['wheels'][0][0] = value
            with self.assertRaises(ValueError): PAIR.validate_fixture(changed)
        self.fixture['cases'][1]['id'] = self.fixture['cases'][0]['id']
        with self.assertRaises(ValueError): PAIR.validate_fixture(self.fixture)


if __name__ == '__main__':
    unittest.main()
