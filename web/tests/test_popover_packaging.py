"""Source/packaging contracts only: no Rust or MoonBit compiler execution."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch

WEB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WEB / 'scripts'))
import build_rust

class PopoverPackaging(unittest.TestCase):
    def test_catalog_is_source_pinned_and_unverified(self):
        catalog = json.loads((WEB / 'examples.json').read_text())
        self.assertEqual(catalog['moonbit']['revision'], 'e160f5ec7bf0c6f43738d0bdcf837098299d5569')
        self.assertEqual(catalog['moonbit']['tree'], '96d62ea12a6824ee20d04cb913191bc23a424522')
        entry, = [e for e in catalog['examples'] if e['id'] == 'popover']
        self.assertEqual(entry['source_blob'], '7678a6a3ed865d9874b72cb99b473a115591d35c')
        self.assertEqual(entry['source'], 'crates/gpui/examples/popover.rs')
        self.assertIn('remain unverified', entry['implementation_note'])
        self.assertEqual(build_rust.selected_examples(catalog, [], implemented_examples=['popover']), ['popover'])
        self.assertIn('popover', build_rust.selected_examples(catalog, []))
        self.assertTrue((WEB.parent / entry['candidate_source']).is_file())

    def test_relocated_gallery_registers_unchanged_popover_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, gallery, web = root / 'source', root / 'gallery', root / 'web'
            original = source / build_rust.GALLERY
            (original / '.cargo').mkdir(parents=True)
            (original / 'Cargo.toml').write_text('[workspace]\n[package]\nname="synthetic"\nversion="0.1.0"\n')
            (web / 'rust').mkdir(parents=True)
            (web / 'rust/Cargo.lock').write_text('# synthetic packaging input, not a compiled lock\n')
            upstream = source / 'crates/gpui/examples/popover.rs'
            upstream.parent.mkdir(parents=True)
            upstream.write_text('// synthetic path fixture; not runtime evidence\n')
            before = upstream.read_bytes()
            with patch.object(build_rust, 'WEB', web):
                result = build_rust.prepare_gallery(source, gallery, ['popover'])
            self.assertFalse(result['upstream_files_modified'])
            self.assertEqual(result['additional_bins'], [{'name':'popover','source':'crates/gpui/examples/popover.rs'}])
            package = tomllib.loads((gallery / 'Cargo.toml').read_text())
            self.assertEqual((gallery / package['bin'][0]['path']).resolve(), upstream)
            self.assertEqual(upstream.read_bytes(), before)

    def test_hosts_and_japanese_catalog_include_preview(self):
        self.assertIn("popover:'./popover.mjs'", (WEB / 'moonbit/site/host.mjs').read_text())
        self.assertIn("popover: './popover.js'", (WEB / 'rust/host.mjs').read_text())
        script = WEB.parent / 'scripts/build_test_catalog.py'
        spec = importlib.util.spec_from_file_location('popover_catalog_contract', script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertIn('popover', module.BROWSER_LAB_EXAMPLES)
        self.assertIn('未検証', module.BROWSER_FEATURES['popover']['description'])
        host = (WEB / 'moonbit/site/host.mjs').read_text()
        self.assertLess(host.index('await loadPopoverFont('),host.index('  render();'))
        self.assertIn("window.addEventListener('pagehide'", host)
        self.assertIn("window.addEventListener('pageshow'", host)

if __name__ == '__main__':
    unittest.main()
