"""Pair-build contract checks. Synthetic fixtures are never execution evidence."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'web/scripts'))
import build_uniform_list_pair as pair


class PairPackaging(unittest.TestCase):
    def test_separate_profile_keeps_exact_original_source(self):
        p = json.loads((ROOT / 'web/pairs/uniform_list.json').read_text())
        original = json.loads((ROOT / 'web/oracles/uniform_list.json').read_text())
        self.assertEqual(p['upstream']['revision'], original['upstream_revision'])
        self.assertEqual(p['upstream']['tree'], original['upstream_tree'])
        for field in ['source', 'source_blob', 'source_sha256']:
            self.assertEqual(p['upstream'][field], original[field])
        self.assertEqual(p['viewport'], {'width': 300, 'height': 300, 'dpr': 1})

    def test_core_inventory_is_actual_source_not_compiled_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'moon.mod').write_text('name = "test"\n')
            (root / 'script').mkdir()
            (root / 'script/macos_text_prebuild.py').write_text('# fixture')
            for name in pair.CORE_DIRS:
                (root / name).mkdir()
                (root / name / 'moon.pkg').write_text('')
                (root / name / 'a.mbt').write_text(name)
                (root / name / 'ignored.js').write_text('not core source')
            inventory = pair.sources(root)
            self.assertEqual(len(inventory), 10)
            self.assertTrue(all(len(value) == 64 for value in inventory.values()))
            self.assertNotIn('element/ignored.js', inventory)

    def test_local_override_is_explicit_and_rejected_by_qualifier(self):
        build = (ROOT / 'web/scripts/build_uniform_list_pair.py').read_text()
        evidence = (ROOT / 'web/tests/uniform-list-pair-evidence.mjs').read_text()
        self.assertIn('--local-core-override', build)
        self.assertIn("'unqualified_local_override' if local_override", build)
        self.assertIn("assert.equal(build.qualification,'pinned_clean_source'", evidence)
        self.assertIn("git', 'archive', 'HEAD'", build)
        self.assertIn("--deny-warn", build)
        self.assertIn("verifyCoreSource", evidence)

    def test_actual_capture_retains_scenes_response_bodies_and_two_original_pngs(self):
        capture = (ROOT / 'web/tests/uniform-list-pair-browser.mjs').read_text()
        self.assertIn('await response.body()', capture)
        self.assertIn("await page.screenshot({animations:'disabled',scale:'device'})", capture)
        self.assertIn('previous?.rgba_sha256===attempt.rgba_sha256', capture)
        self.assertIn('font_metrics:', capture)
        self.assertIn('const profile=makeProfile(rustGeometry)', capture)
        self.assertNotIn('makeProfile(result.discovered_geometry)', capture)

    def test_workflow_is_separate_and_uploads_failed_original_evidence(self):
        workflow = (ROOT / '.github/workflows/uniform-list-pair.yml').read_text()
        for expected in ['if: always()', 'uniform-list-oracle-browser.mjs',
                         'uniform-list-pair-browser.mjs', 'verify-uniform-list-pair.mjs',
                         'build_uniform_list_pair.py', 'Pillow==12.0.0', 'playwright@1.56.1']:
            self.assertIn(expected, workflow)
        self.assertNotIn('--local-core-override', workflow)
        self.assertNotIn('git push', workflow)


if __name__ == '__main__':
    unittest.main()
