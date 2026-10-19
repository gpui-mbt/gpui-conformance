import copy
import json
from pathlib import Path
import unittest
import tempfile

import run_reverse_flow as runner


class ReverseFlowTests(unittest.TestCase):
    def setUp(self):
        self.corpus = json.loads((runner.ROOT / 'reverse_flow_scenarios.json').read_text())

    def test_original_corpus_is_bounded(self):
        runner.validate(self.corpus)
        self.assertEqual(len(self.corpus['cases']), 68)
        for direction in ('row_reverse', 'column_reverse'):
            cases = [c for c in self.corpus['cases'] if c['direction'] == direction]
            self.assertEqual(len(cases), 34)
            self.assertEqual({c.get('justify', 'start') for c in cases}, {'start', 'end', 'center', 'space-between', 'space-around', 'space-evenly'})
            self.assertTrue(any(c.get('wrap') == 'wrap_reverse' for c in cases))
            self.assertTrue(any(c.get('grow') for c in cases))

    def observations(self):
        return {'implementation': 'upstream', 'cases': [dict(id=c['id'], layer=c['layer'], status='observed', observation={'bounds': [[0, 0, 10, 10] for _ in range(len(c['children']) + 1)]}) for c in self.corpus['cases']]}

    def test_identical_full_bounds_pass(self):
        observed = self.observations()
        self.assertEqual(runner.compare(self.corpus, observed, dict(observed, implementation='moonbit'))['summary']['pass'], 68)

    def test_changed_origin_is_detected(self):
        a = self.observations()
        b = copy.deepcopy(a)
        b['implementation'] = 'moonbit'
        b['cases'][0]['observation']['bounds'][1][0] += 1
        result = runner.compare(self.corpus, a, b)
        self.assertEqual(result['summary']['mismatch'], 1)
        self.assertEqual(result['cases'][0]['differences'][0]['path'], 'bounds[1][0]')

    def test_missing_case_is_rejected(self):
        a = self.observations()
        b = copy.deepcopy(a)
        b['implementation'] = 'moonbit'
        b['cases'].pop()
        with self.assertRaises(ValueError):
            runner.compare(self.corpus, a, b)

    def test_projection_cannot_hide_sizes(self):
        self.corpus['cases'][0]['layout_observation'] = 'line_origins'
        with self.assertRaises(ValueError):
            runner.validate(self.corpus)

    def test_nonfinite_output_is_rejected(self):
        a = self.observations()
        a['cases'][0]['observation']['bounds'][0][0] = float('nan')
        with self.assertRaises(ValueError):
            runner.compare(self.corpus, a, dict(a, implementation='moonbit'))

    def test_backend_label_is_required(self):
        a = self.observations()
        with self.assertRaises(ValueError):
            runner.compare(self.corpus, a, a)

    def test_boolean_coordinate_is_rejected(self):
        a = self.observations()
        a['cases'][0]['observation']['bounds'][0][0] = True
        with self.assertRaises(ValueError):
            runner.compare(self.corpus, a, dict(a, implementation='moonbit'))

    def test_negative_dimensions_are_rejected(self):
        a = self.observations()
        a['cases'][0]['observation']['bounds'][0][2] = -1
        with self.assertRaises(ValueError):
            runner.compare(self.corpus, a, dict(a, implementation='moonbit'))

    def test_comparison_validates_corpus(self):
        a = self.observations()
        self.corpus['cases'][0]['layout_observation'] = 'line_origins'
        with self.assertRaises(ValueError):
            runner.compare(self.corpus, a, dict(a, implementation='moonbit'))

    def test_build_binding_rejects_changed_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'probe'
            path.write_text('original')
            source = self.pinned_sources()
            build = {'sources': copy.deepcopy(source), 'executables': {'upstream': {'sha256': runner.sha(path)}}}
            runner.validate_build(build, source, {'upstream': path})
            path.write_text('modified')
            with self.assertRaisesRegex(ValueError, 'Executable hash mismatch'):
                runner.validate_build(build, source, {'upstream': path})

    def test_build_binding_rejects_wrong_tree_or_dirty_source(self):
        source = self.pinned_sources()
        build = {'sources': copy.deepcopy(source), 'executables': {}}
        source['suite']['tree'] = 'other'
        with self.assertRaisesRegex(ValueError, 'tree mismatch'):
            runner.validate_build(build, source, {})
        source['suite']['tree'] = 'known'
        source['moonbit']['dirty'] = True
        with self.assertRaisesRegex(ValueError, 'Dirty input source'):
            runner.validate_build(build, source, {})

    def pinned_sources(self):
        pins = json.loads((runner.ROOT/'reverse_flow_pins.json').read_text())
        return {**{name: dict(pins[name], dirty=False) for name in ('upstream', 'moonbit')},
                'suite': {'tree': 'known', 'dirty': False}}

    def test_wrong_upstream_revision_or_tree_is_rejected(self):
        for key in ('revision', 'tree'):
            source = self.pinned_sources()
            source['upstream'][key] = '0' * 40
            with self.assertRaisesRegex(ValueError, 'upstream .* differs from reverse-flow pin'):
                runner.validate_pins(source)

    def test_wrong_core_revision_even_with_same_tree_is_rejected(self):
        source = self.pinned_sources()
        source['moonbit']['revision'] = 'b75cd99032d766beab42e3b82f7dfe0a743e620a'
        with self.assertRaisesRegex(ValueError, 'moonbit revision differs from reverse-flow pin'):
            runner.validate_pins(source)

    def test_wrong_core_tree_is_rejected(self):
        source = self.pinned_sources()
        source['moonbit']['tree'] = '0' * 40
        with self.assertRaisesRegex(ValueError, 'moonbit tree differs from reverse-flow pin'):
            runner.validate_pins(source)

    def test_runner_rejects_wrong_build_pin(self):
        source = self.pinned_sources()
        build = {'sources': copy.deepcopy(source), 'executables': {}}
        build['sources']['moonbit']['revision'] = '0' * 40
        with self.assertRaisesRegex(ValueError, 'moonbit revision differs from reverse-flow pin'):
            runner.validate_build(build, source, {})


if __name__ == '__main__':
    unittest.main()
