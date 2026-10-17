import importlib.util
import json
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'web/scripts'))
import build_gradient_pair as builder
class GradientPairPackaging(unittest.TestCase):
    def test_frozen_source_identity(self):
        profile=json.loads(builder.PROFILE.read_text())
        self.assertEqual(profile['upstream']['source_blob'],'df1398fff58b637abf0c0b31934f6ad523d84a21')
        self.assertEqual(profile['sequence'],['wideSrgb','wideOklab','wideRestored','tallSrgb','tallOklab','tallRestored','wideAgain'])
        self.assertEqual(profile['tolerances_unorm8'],{'rgb_code':2,'opaque_alpha':0})
        self.assertEqual(profile['policy_probe']['snapshot_run']['ordered_ids'],[1,2,3,4,6])
    def test_mutations_are_genuine_core_sources(self):
        profile=json.loads(builder.PROFILE.read_text())
        self.assertGreaterEqual(len(profile['executed_controls']),8)
        for name,mutation in profile['executed_controls'].items():
            self.assertTrue(mutation['path'].startswith(('scene/','primitives/')),name)
            self.assertNotEqual(mutation['find'],mutation['replace'])
            self.assertEqual(mutation['occurrences'],1)
    def test_live_routes_use_unchanged_source_and_expected_modules(self):
        catalog=json.loads((ROOT/'web/examples.json').read_text())
        entry=next(e for e in catalog['examples'] if e['id']=='gradient')
        self.assertEqual(entry['source'],'crates/gpui/examples/gradient.rs')
        self.assertEqual(entry['source_blob'],'df1398fff58b637abf0c0b31934f6ad523d84a21')
        self.assertIn("gradient: './gradient.js'",(ROOT/'web/rust/host.mjs').read_text())
        self.assertIn("gradient:'./gradient.mjs'",(ROOT/'web/moonbit/site/host.mjs').read_text())
        self.assertEqual(catalog['moonbit'],json.loads(builder.PROFILE.read_text())['candidate'])
    def test_exact_mutation_anchor(self):
        mutation={'find':'alpha = 0.5','replace':'alpha = 1.0','occurrences':1}
        self.assertEqual(builder.mutate_source('alpha = 0.5',mutation),'alpha = 1.0')
        with self.assertRaises(ValueError):builder.mutate_source('alpha = 0.5; alpha = 0.5',mutation)
    def test_policy_and_baseline_commands_are_distinct(self):
        script=(ROOT/'web/scripts/run_gradient_pair_controls.py').read_text()
        self.assertIn('Ordinary pair did not pass independent current-source/original-byte reverification',script)
        self.assertIn("env['GRADIENT_POLICY'] = '1'",script)
        self.assertIn("evidence / 'policy'",script)
        self.assertIn("if not profile['executed_controls']",script)
if __name__=='__main__':unittest.main()
