"""Source-only pair packaging checks; mocks below do not execute MoonBit/Rust/browser."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'web/scripts'))
import build_grid_layout_pair as pair
import run_grid_layout_pair_controls as controls


class GridPairPackaging(unittest.TestCase):
    def test_separate_profile_preserves_frozen_source_and_exact_core(self):
        p = json.loads(pair.PROFILE.read_text())
        original = json.loads((ROOT / 'web/oracles/grid_layout.json').read_text())
        self.assertEqual(p['upstream']['revision'], original['upstream_revision'])
        self.assertEqual(p['upstream']['tree'], original['upstream_tree'])
        for field in ['source', 'source_blob', 'source_sha256']:
            self.assertEqual(p['upstream'][field], original[field])
        self.assertEqual(p['candidate']['revision'], '89108ad966c2d37b0cb44909b1aac3ecfa8e3c4a')
        self.assertEqual(p['candidate']['tree'], 'dd5612a412d251b468c358a25baa0b0dd592c807')
        self.assertEqual(p['sequence'], [500, 399, 400, 401, 500, 399, 400, 500])
        self.assertEqual(p['viewport'], {'widths': [399, 400, 401, 500], 'height': 500, 'dpr': 1})
        self.assertEqual(p['tolerances_physical_pixels'], {'fill_edge': 2, 'exposed_gray_gap': 1, 'fill_separation': 4})
        self.assertEqual(original['candidate'], 'not_implemented')

    def test_faults_mutate_actual_copied_source_only_at_exact_anchors(self):
        source = (ROOT / 'web/moonbit/grid_layout/grid_layout.mbt').read_text()
        p = json.loads(pair.PROFILE.read_text())
        for name, mutation in p['executed_controls'].items():
            with self.subTest(name=name):
                changed = pair.mutate_source(source, mutation)
                self.assertEqual(source.count(mutation['find']), mutation['occurrences'])
                self.assertEqual(changed.count(mutation['replace']), mutation['occurrences'])
                self.assertNotEqual(changed, source)
                with self.assertRaises(ValueError):
                    pair.mutate_source(source.replace(mutation['find'], ''), mutation)
        self.assertEqual(source, (ROOT / 'web/moonbit/grid_layout/grid_layout.mbt').read_text())

    def test_mock_build_retains_exact_mutated_inputs_patch_and_distinct_status(self):
        # This tests packaging control flow only. The mock compiler output is
        # deliberately named synthetic and the local manifest is unqualified.
        for control in [None, 'wrong_gap', 'wrong_color']:
            with self.subTest(control=control), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                core, upstream = root / 'core', root / 'upstream'
                core.mkdir(); upstream.mkdir()
                (core / 'moon.mod').write_text('synthetic module')
                (core / 'script').mkdir()
                (core / 'script/macos_text_prebuild.py').write_text('# synthetic')
                for name in pair.CORE_DIRS:
                    (core / name).mkdir()
                    (core / name / 'a.mbt').write_text('synthetic')
                    (core / name / 'moon.pkg').write_text('synthetic')
                p = json.loads(pair.PROFILE.read_text())
                source = upstream / p['upstream']['source']
                source.parent.mkdir(parents=True)
                source.write_text('// synthetic upstream fixture\n')
                p['upstream']['source_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
                profile = root / 'profile.json'; profile.write_text(json.dumps(p))
                font = upstream / 'assets/fonts/ibm-plex-sans/IBMPlexSans-Regular.ttf'
                font.parent.mkdir(parents=True)
                font.write_bytes(b'synthetic font'); (font.parent / 'license.txt').write_text('synthetic license')
                def fake_run(command, cwd, capture=False):
                    if command[:2] == ['moon', 'version']:
                        return 'moon synthetic compiler stub, never actual runtime'
                    if command[:2] == ['git', 'status']:
                        return ''
                    if command[:2] == ['git', 'rev-parse']:
                        is_tree = command[2] == 'HEAD^{tree}'
                        key = 'upstream' if cwd == upstream else 'candidate'
                        return p[key]['tree' if is_tree else 'revision']
                    self.fail(f'Unexpected command {command}')
                def fake_compile(command, cwd, **kwargs):
                    self.assertEqual(command[0], 'moon')
                    runtime = cwd / '_build/js/release/build/examples/conformance_grid_layout/conformance_grid_layout.js'
                    runtime.parent.mkdir(parents=True, exist_ok=True)
                    runtime.write_text('// synthetic compiler output; never execution evidence')
                    return subprocess.CompletedProcess(command, 0, stdout='synthetic compiler stub\n')
                out = root / 'site'
                with patch.object(pair, 'PROFILE', profile), patch.object(pair, 'run', fake_run), \
                     patch.object(pair, 'check_source'), patch.object(pair.subprocess, 'run', fake_compile):
                    pair.build(core, upstream, out, local_override=True, control=control)
                manifest = json.loads((out / 'build-manifest.json').read_text())
                self.assertEqual(manifest['qualification'], 'unqualified_local_override')
                self.assertEqual(manifest['executed_control'], control)
                self.assertEqual(manifest['unit_tests'], 'not_run_for_executed_mutant' if control else 'passed')
                self.assertEqual(len(manifest['commands']), 1 if control else 2)
                current = (ROOT / 'web/moonbit/grid_layout/grid_layout.mbt').read_text()
                compiled = (out / 'inputs/grid_layout.mbt').read_text()
                self.assertEqual(compiled, pair.mutate_source(current, p['executed_controls'][control]) if control else current)
                if control:
                    self.assertEqual((out / 'inputs/unmutated-grid_layout.mbt').read_text(), current)
                    diff = (out / 'inputs/source-mutation.patch').read_text()
                    self.assertIn('--- original/grid_layout.mbt', diff)
                    self.assertIn('+++ compiled-control/grid_layout.mbt', diff)
                    self.assertEqual(manifest['control_source']['patch_sha256'], pair.digest(out / 'inputs/source-mutation.patch'))
                else:
                    self.assertIsNone(manifest['control_source'])
                for path, digest in manifest['files'].items():
                    self.assertEqual(digest, pair.digest(out / path))

    def test_capture_and_verifier_preserve_original_evidence_and_failure(self):
        capture = (ROOT / 'web/tests/grid-layout-pair-browser.mjs').read_text()
        verify = (ROOT / 'web/tests/verify-grid-layout-pair.mjs').read_text()
        for text in ['await response.body()', "await page.screenshot({animations:'disabled',scale:'device'})",
                     'previous?.rgba_sha256===attempt.rgba_sha256', 'await page.setViewportSize',
                     'record.document_id', 'makeProfile().operations']:
            self.assertIn(text, capture)
        self.assertNotIn('inspectLayout(image)', capture)
        self.assertIn('comparePairImages(rustFiles.images,moonFiles.images)', verify)
        self.assertIn('original_comparison_failures:failures', verify)
        self.assertIn("flag:'wx'", verify)

    def test_workflow_requires_successful_ordinary_pair_and_keeps_outputs(self):
        workflow = (ROOT / '.github/workflows/grid-layout-browser-pair.yml').read_text()
        for text in ['Pillow==12.0.0', 'playwright@1.56.1', 'GPUI_GRID_LAYOUT_RUNTIME=',
                     'grid-layout-oracle-browser.mjs', 'verify-grid-layout-results.mjs',
                     'grid-layout-pair-browser.mjs', 'verify-grid-layout-pair.mjs',
                     'run_grid_layout_pair_controls.py', '--ordinary-evidence _build/grid-layout-pair-evidence', "always() && steps.ordinary_pair.outcome == 'success'",
                     '_build/grid-layout-executed-controls', 'if: always()']:
            self.assertIn(text, workflow)
        self.assertNotIn('UNIFORM_LIST_RUNTIME', workflow)
        self.assertNotIn('--local-core-override', workflow)
        self.assertNotIn('git push', workflow)
        runner = (ROOT / 'web/scripts/run_grid_layout_pair_controls.py').read_text()
        self.assertIn('this is not an accepted fault rejection', runner)
        self.assertIn("['wrong_gap', 'wrong_color']", (ROOT / 'web/scripts/build_grid_layout_pair.py').read_text())

    def test_control_runner_never_builds_faults_without_successful_ordinary_evidence(self):
        for baseline in [None, {'status': 'failed', 'expected_control': None},
                         {'status': 'bounded_color_component_pair_verified'},
                         {'status': 'bounded_color_component_pair_verified', 'expected_control': 'wrong_gap'}]:
            with self.subTest(baseline=baseline), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                ordinary = root / 'ordinary'; ordinary.mkdir()
                if baseline is not None:
                    (ordinary / 'grid-layout-pair-verification.json').write_text(json.dumps(baseline))
                with patch.object(controls.subprocess, 'run') as execute:
                    result = controls.run(root / 'core', root / 'upstream', root / 'rust', root / 'controls', ordinary)
                    execute.assert_not_called()
                self.assertEqual(result['status'], 'skipped_unqualified_ordinary_pair')
                self.assertEqual(result['controls'], [])

    def test_control_runner_failed_ordinary_reverification_is_not_a_kill(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ordinary = root / 'ordinary'; ordinary.mkdir()
            (ordinary / 'grid-layout-pair-verification.json').write_text(json.dumps(
                {'status': 'bounded_color_component_pair_verified', 'expected_control': None}))
            failed = subprocess.CompletedProcess([], 1)
            with patch.object(controls.subprocess, 'run', return_value=failed) as execute:
                result = controls.run(root / 'core', root / 'upstream', root / 'rust', root / 'controls', ordinary)
                self.assertEqual(execute.call_count, 1)
                self.assertEqual(execute.call_args.args[0][1], 'web/tests/verify-grid-layout-pair.mjs')
            self.assertEqual(result['status'], 'skipped_unqualified_ordinary_pair')
            self.assertEqual(result['controls'], [])


if __name__ == '__main__':
    unittest.main()
