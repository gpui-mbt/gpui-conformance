"""Pattern registration and source-derived integration; no fabricated raster evidence."""
import importlib.util
import json
import hashlib
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'web/scripts'))
spec=importlib.util.spec_from_file_location('build_rust',ROOT/'web/scripts/build_rust.py')
build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)
import browser_build_artifacts as artifacts
class PatternPackaging(unittest.TestCase):
    def test_retained_rust_source_is_bound_to_exact_catalog_blob(self):
        with tempfile.TemporaryDirectory() as directory:
            site=Path(directory);p=site/'rust/unchanged-source/pattern.rs';p.parent.mkdir(parents=True)
            data=b'// independent source fixture\n';p.write_bytes(data)
            blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
            record={'id':'pattern','source':'crates/gpui/examples/pattern.rs','source_blob':blob,'source_sha256':hashlib.sha256(data).hexdigest(),'retained_file':'unchanged-source/pattern.rs'}
            inputs={'implemented':['pattern'],'implemented_sources':{'pattern':{'source':record['source'],'source_blob':blob}}}
            self.assertEqual(artifacts.retained_pattern_sources({'pattern_source':record},site,inputs),{'unchanged-source/pattern.rs'})
            p.write_bytes(data+b'// changed')
            with self.assertRaisesRegex(ValueError,'identity mismatch'):
                artifacts.retained_pattern_sources({'pattern_source':record},site,inputs)
            with self.assertRaisesRegex(ValueError,'provenance'):
                artifacts.retained_pattern_sources({},site,inputs)

    def test_unchanged_upstream_source_is_registered_outside_original(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'upstream';original=source/build.GALLERY
            original.mkdir(parents=True);(original/'.cargo').mkdir()
            content='[package]\nname="fixture"\nversion="0.0.0"\n'
            (original/'Cargo.toml').write_text(content)
            web=root/'web';(web/'rust').mkdir(parents=True);(web/'rust/Cargo.lock').write_text('# fixture\n')
            with patch.object(build,'WEB',web): result=build.prepare_gallery(source,root/'gallery',['pattern'])
            self.assertFalse(result['upstream_files_modified'])
            self.assertEqual((original/'Cargo.toml').read_text(),content)
            self.assertEqual(result['additional_bins'],[{'name':'pattern','source':'crates/gpui/examples/pattern.rs'}])
            self.assertIn('name = "pattern"',(root/'gallery/Cargo.toml').read_text())
    def test_catalog_and_host_use_real_core_package_without_shader_reimplementation(self):
        catalog=json.loads((ROOT/'web/examples.json').read_text());entry=next(e for e in catalog['examples'] if e['id']=='pattern')
        self.assertEqual(entry['source_blob'],'7d2e98d16e24dc23dc307296a3b35c18e624d9e3')
        self.assertEqual((entry['width'],entry['height']),(600,600))
        self.assertFalse(entry['interactive'])
        source=(ROOT/entry['candidate_source']).read_text()
        for token in ['request_layout_with_device_scale','paint_with_paints','SlashPattern::new','rasterize_paint_run_webgl2_linear']:
            self.assertIn(token,source)
        host=(ROOT/'web/moonbit/site/pattern-host.mjs').read_text()
        for token in ['createLinearGradient','fillRect','Math.sin','Math.cos','putImageData']:
            self.assertNotIn(token,host)
        self.assertIn('actualBoundingBoxLeft',host)
        self.assertIn('actualBoundingBoxDescent',host)
    def test_qualification_remains_explicitly_scoped(self):
        contract=json.loads((ROOT/'web/pairs/pattern.json').read_text())
        self.assertIn('unverified',contract['status'])
        self.assertEqual(len(contract['rows']),8)
        self.assertEqual(contract['rows'][3]['interval'],9)
        self.assertEqual(contract['rows'][-1]['height'],26)
        self.assertEqual(set(contract['controls']),{'wrong_interval','wrong_phase','wrong_color','missing_row','missing_runtime'})
if __name__=='__main__':unittest.main()
