"""Portable contract tests. Synthetic observations below never claim execution."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import run_align_self as runner
import build_align_self as builder


class AlignSelfTests(unittest.TestCase):
    def setUp(self):
        self.corpus = json.loads((runner.ROOT/'align_self_scenarios.json').read_text())

    def observations(self, implementation='upstream'):
        return {'implementation': implementation, 'cases': [dict(id=c['id'], layer=c['layer'], status='observed', observation={'bounds': [[0, 0, c['width'], c['height']]] + [[0, 0, 10, 10] for _ in c['children']]}) for c in self.corpus['cases']]}

    def sources(self):
        pins = json.loads((runner.ROOT/'align_self_pins.json').read_text())
        return {**{k: dict(pins[k], dirty=False) for k in ('upstream', 'moonbit')},
                'suite': {'revision': 'suite-revision', 'tree': 'suite-tree', 'dirty': False}}

    def test_bounded_corpus_and_semantic_coverage(self):
        runner.validate(self.corpus)
        self.assertEqual(len(self.corpus['cases']), 48)
        for direction in ('row', 'column', 'row_reverse', 'column_reverse'):
            cases = [c for c in self.corpus['cases'] if c['direction'] == direction]
            self.assertEqual(len(cases), 12)
            self.assertEqual({v for c in cases for v in c['align_self']}, {'auto', 'start', 'center', 'end', 'stretch', 'flex_start', 'flex_end'})
            self.assertTrue(any(c.get('wrap') == 'wrap_reverse' for c in cases))
            self.assertTrue(any(any(v is None for child in c['children'] for v in child) for c in cases))
            self.assertTrue(any(c.get('max_cross') for c in cases))
            self.assertTrue(any(c.get('min_cross') for c in cases))

    def test_identical_full_bounds_pass(self):
        self.assertEqual(runner.compare(self.corpus, self.observations(), self.observations('moonbit'))['summary'], {'total': 48, 'pass': 48, 'mismatch': 0})

    def test_every_coordinate_is_compared(self):
        for coordinate in range(4):
            a, b = self.observations(), self.observations('moonbit')
            b['cases'][0]['observation']['bounds'][1][coordinate] += 1
            result = runner.compare(self.corpus, a, b)
            self.assertEqual(result['summary']['mismatch'], 1)
            self.assertEqual(result['cases'][0]['differences'][0]['path'], f'bounds[1][{coordinate}]')

    def test_missing_extra_or_reordered_cases_rejected(self):
        for operation in ('missing', 'extra', 'order'):
            b = self.observations('moonbit')
            if operation == 'missing': b['cases'].pop()
            elif operation == 'extra': b['cases'].append(copy.deepcopy(b['cases'][0]))
            else: b['cases'][0], b['cases'][1] = b['cases'][1], b['cases'][0]
            with self.assertRaises(ValueError): runner.compare(self.corpus, self.observations(), b)

    def test_wrong_backend_status_or_layer_rejected(self):
        for name, value in [('implementation', 'upstream'), ('status', 'unverified'), ('layer', 'pixels')]:
            b = self.observations('moonbit')
            if name == 'implementation': b[name] = value
            else: b['cases'][0][name] = value
            with self.assertRaises(ValueError): runner.compare(self.corpus, self.observations(), b)

    def test_nonfinite_boolean_and_negative_size_rejected(self):
        for value, coordinate in [(float('nan'), 0), (float('inf'), 0), (True, 0), (-1, 2), (-1, 3)]:
            b = self.observations('moonbit')
            b['cases'][0]['observation']['bounds'][1][coordinate] = value
            with self.assertRaises(ValueError): runner.compare(self.corpus, self.observations(), b)

    def test_empty_extra_or_projected_observations_rejected(self):
        for observation in ({'bounds': []}, {'line_origins': [0]}, {'bounds': [[0, 0, 10, 10]], 'hidden': True}):
            b = self.observations('moonbit')
            b['cases'][0]['observation'] = observation
            with self.assertRaises(ValueError): runner.compare(self.corpus, self.observations(), b)

    def test_bad_corpus_fields_rejected(self):
        for key, value in [('device_scale_factor', True), ('width', float('inf')), ('height', -1), ('align', 'baseline'), ('justify', 'unknown'), ('align_self', ['start']), ('wrap', 'unknown'), ('gap', -1), ('padding', [0]), ('min_cross', [-1, 0, 0]), ('max_cross', [0]), ('children', [[10, True]])]:
            corpus = copy.deepcopy(self.corpus)
            corpus['cases'][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): runner.validate(corpus)

    def test_duplicate_ids_and_hidden_projection_rejected(self):
        self.corpus['cases'][1]['id'] = self.corpus['cases'][0]['id']
        with self.assertRaises(ValueError): runner.validate(self.corpus)
        self.setUp()
        self.corpus['cases'][0]['layout_observation'] = 'line_origins'
        with self.assertRaises(ValueError): runner.validate(self.corpus)

    def test_invalid_minmax_rejected(self):
        self.corpus['cases'][0]['min_cross'] = [20, 0, 0]
        self.corpus['cases'][0]['max_cross'] = [10, None, None]
        with self.assertRaises(ValueError): runner.validate(self.corpus)

    def test_wrong_revision_even_with_same_tree_rejected(self):
        for name in ('upstream', 'moonbit'):
            source = self.sources()
            source[name]['revision'] = '0'*40
            with self.assertRaisesRegex(ValueError, 'revision differs'): runner.validate_pins(source)

    def test_build_pins_dirty_or_changed_source_rejected(self):
        for name in ('upstream', 'moonbit', 'suite'):
            for key in ('revision', 'tree', 'dirty'):
                source = self.sources()
                build = {'sources': copy.deepcopy(source), 'executables': {}}
                source[name][key] = True if key == 'dirty' else 'changed'
                with self.subTest(name=name, key=key), self.assertRaises(ValueError): runner.validate_build(build, source, {})

    def test_dirty_build_input_rejected(self):
        source = self.sources()
        build = {'sources': copy.deepcopy(source), 'executables': {}}
        build['sources']['suite']['dirty'] = True
        with self.assertRaisesRegex(ValueError, 'Dirty build input'): runner.validate_build(build, source, {})

    def test_tampered_or_duplicated_executable_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory)/'a', Path(directory)/'b'
            a.write_bytes(b'upstream'); b.write_bytes(b'moonbit')
            source = self.sources()
            build = {'sources': copy.deepcopy(source), 'executables': {k: {'sha256': runner.sha(v)} for k, v in [('upstream', a), ('moonbit', b)]}}
            runner.validate_build(build, source, {'upstream': a, 'moonbit': b})
            b.write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'): runner.validate_build(build, source, {'upstream': a, 'moonbit': b})
            with self.assertRaisesRegex(ValueError, 'distinct executable'): runner.validate_build(build, source, {'upstream': a, 'moonbit': a})

    def cache_fixture(self, root):
        cache, rust = root/'cache', root/'rust'
        deps = cache/'rust/target/debug/deps'
        deps.mkdir(parents=True)
        rust.mkdir()
        for name in ('libgpui-test.rlib', 'libserde_json-test.rlib', 'libhelper-test.rmeta'):
            (deps/name).write_text(name)
        for path in (cache/'rust/Cargo.lock', rust/'Cargo.lock'):
            path.write_text('locked fixture')
        upstream = self.sources()['upstream']
        (cache/'build-manifest.json').write_text(json.dumps({'sources': {'upstream': upstream}, 'toolchains': {'rust': 'rustc test'}}))
        return cache, rust, upstream

    def test_readonly_cache_records_rlib_and_metadata_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache, rust, upstream = self.cache_fixture(root)
            with patch.object(builder.subprocess, 'check_output', return_value='rustc test\n'):
                executable, command, evidence, inputs = builder.cached_rust(rust, upstream, cache, root)
            self.assertEqual(len(inputs), 3)
            self.assertIn('deps/libhelper-test.rmeta', evidence['dependency_sha256'])
            self.assertEqual(executable, root/'gpui-conformance-probe')
            self.assertIn('--extern', command)

    def test_readonly_cache_rejects_wrong_source_or_compiler(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache, rust, upstream = self.cache_fixture(root)
            with self.assertRaisesRegex(ValueError, 'source pin mismatch'):
                builder.cached_rust(rust, dict(upstream, revision='wrong'), cache, root)
            with patch.object(builder.subprocess, 'check_output', return_value='rustc other\n'):
                with self.assertRaisesRegex(ValueError, 'compiler mismatch'):
                    builder.cached_rust(rust, upstream, cache, root)

    def test_readonly_cache_rejects_changed_lockfile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache, rust, upstream = self.cache_fixture(root)
            (rust/'Cargo.lock').write_text('changed lock')
            with patch.object(builder.subprocess, 'check_output', return_value='rustc test\n'):
                with self.assertRaisesRegex(ValueError, 'lockfile mismatch'):
                    builder.cached_rust(rust, upstream, cache, root)


if __name__ == '__main__':
    unittest.main()
