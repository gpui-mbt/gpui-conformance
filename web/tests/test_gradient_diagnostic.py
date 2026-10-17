import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

WEB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WEB / 'scripts'))
from build_gradient_diagnostic import prepare_diagnostic, REVISION

class DiagnosticContracts(unittest.TestCase):
    def test_exact_profile_arguments_are_submitted_by_rust(self):
        profile = json.loads((WEB / 'gradient-diagnostic/profile.json').read_text())
        source = (WEB / 'gradient-diagnostic/main.rs').read_text()
        rows = re.findall(r'Probe \{ kind: "(.*?)", space: ColorSpace::(\w+), x: ([\d.]+), y: ([\d.]+), width: ([\d.]+), height: ([\d.]+), angle: ([\d.]+), stop0: ([-\d.]+), stop1: ([-\d.]+) \}', source)
        self.assertEqual(len(rows), 36)
        for row, case in zip(rows, profile['cases']):
            kind, space, *numbers = row
            self.assertEqual(kind, case['kind'])
            self.assertEqual(space, case['color_space'])
            self.assertEqual(list(map(float, numbers)), case['bounds'] + [case['angle']] + case['stops'])
        self.assertIn('color.a = 0.5;', source)
        self.assertIn('first.a = 0.25; second.a = 0.75;', source)
        self.assertIn('first.a = 0.0; second.a = 0.75;', source)
        self.assertNotIn('stop0 ==', source)
        self.assertNotIn('stop0.clamp', source)

    def test_relocation_does_not_change_upstream_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source = root / 'source'
            original = source / 'crates/gpui_web/examples/hello_web'
            (original / '.cargo').mkdir(parents=True)
            manifest = '[workspace]\n[package]\nname="test"\nversion="0.1.0"\n[dependencies]\ngpui={path = "../../../gpui"}\n'
            (original / 'Cargo.toml').write_text(manifest)
            (original / '.cargo/config.toml').write_text('[build]\n')
            gallery = root / 'gallery'
            result = prepare_diagnostic(source, gallery)
            self.assertEqual((original / 'Cargo.toml').read_text(), manifest)
            self.assertFalse(result['upstream_files_modified'])
            self.assertFalse(result['original_example'])
            self.assertIn('name = "gradient_diagnostic"', (gallery / 'Cargo.toml').read_text())
            self.assertEqual((gallery / 'gradient_diagnostic.rs').read_bytes(), (WEB / 'gradient-diagnostic/main.rs').read_bytes())
            self.assertEqual(REVISION, '5a5fbe79917971a4d52a96b6ddb04da198a5012e')

if __name__ == '__main__':
    unittest.main()
