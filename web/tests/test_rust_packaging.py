"""Keep extra example registration separate from immutable upstream sources."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import tomllib
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("rust_build", SCRIPTS / "build_rust.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RustPackagingTests(unittest.TestCase):
    def test_adds_tree_without_changing_original_package_or_example(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            original = source / module.GALLERY
            (original / ".cargo").mkdir(parents=True)
            (original / ".cargo/config.toml").write_text('[build]\ntarget = "wasm32-unknown-unknown"\n')
            manifest = '''[workspace]
[package]
name = "hello_web"
version = "0.1.0"
[[bin]]
name = "hello_web"
path = "main.rs"
[dependencies]
gpui = { path = "../../../gpui" }
gpui_web = { path = "../.." }
'''
            (original / "Cargo.toml").write_text(manifest)
            (original / "main.rs").write_text("fn main() {}\n")
            tree = source / "crates/gpui/examples/tree.rs"
            tree.parent.mkdir(parents=True)
            tree.write_text("// immutable oracle\n")
            before = {str(path.relative_to(source)): path.read_bytes()
                      for path in source.rglob("*") if path.is_file()}
            gallery = root / "gallery"
            record = module.prepare_gallery(source, gallery, ["hello_web", "tree"])
            packaged = tomllib.loads((gallery / "Cargo.toml").read_text())
            self.assertEqual((gallery / packaged["bin"][0]["path"]).resolve(), original / "main.rs")
            self.assertEqual((gallery / packaged["bin"][1]["path"]).resolve(), tree)
            self.assertEqual((gallery / packaged["dependencies"]["gpui"]["path"]).resolve(), source / "crates/gpui")
            self.assertEqual((gallery / packaged["dependencies"]["gpui_web"]["path"]).resolve(), source / "crates/gpui_web")
            self.assertFalse(record["upstream_files_modified"])
            self.assertEqual(record["additional_bins"], [{"name": "tree", "source": "crates/gpui/examples/tree.rs"}])
            self.assertEqual(before, {str(path.relative_to(source)): path.read_bytes()
                                     for path in source.rglob("*") if path.is_file()})

    def test_extra_oracle_is_explicitly_pinned_and_not_a_candidate(self):
        records = module.extra_oracle_records(["scrollable"])
        self.assertEqual(records[0]["source_blob"], "c81795618875aecf06e06043bd1709c48630b58f")
        self.assertEqual(records[0]["upstream_revision"], "5a5fbe79917971a4d52a96b6ddb04da198a5012e")
        self.assertEqual(records[0]["candidate"], "not_implemented")
        self.assertEqual(module.extra_oracle_records([]), [])

    def test_rejects_unknown_path_and_duplicate_extra_oracles(self):
        for names in [["../outside"], ["other"], ["scrollable", "scrollable"]]:
            with self.subTest(names=names), self.assertRaises(ValueError):
                module.extra_oracle_records(names)

    def test_registers_only_requested_additional_bins(self):
        for requested in [["scrollable"], ["tree", "scrollable"]]:
            with self.subTest(requested=requested), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = root / "source"
                original = source / module.GALLERY
                (original / ".cargo").mkdir(parents=True)
                (original / "Cargo.toml").write_text('[workspace]\n[package]\nname = "hello_web"\nversion = "0.1.0"\n')
                for name in requested:
                    example = source / f"crates/gpui/examples/{name}.rs"
                    example.parent.mkdir(parents=True, exist_ok=True)
                    example.write_text("// immutable source\n")
                before = {str(path.relative_to(source)): path.read_bytes()
                          for path in source.rglob("*") if path.is_file()}
                record = module.prepare_gallery(source, root / "gallery", requested)
                self.assertEqual([item["name"] for item in record["additional_bins"]], requested)
                packaged = tomllib.loads((root / "gallery/Cargo.toml").read_text())
                self.assertEqual([item["name"] for item in packaged["bin"]], requested)
                for item in packaged["bin"]:
                    self.assertEqual((root / "gallery" / item["path"]).resolve(),
                                     source / f"crates/gpui/examples/{item['name']}.rs")
                self.assertEqual(before, {str(path.relative_to(source)): path.read_bytes()
                                         for path in source.rglob("*") if path.is_file()})

    def test_rejects_source_paths_outside_the_archived_upstream(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            original = source / module.GALLERY
            original.mkdir(parents=True)
            (original / "Cargo.toml").write_text('path = "../../../../../../outside.rs"\n')
            with self.assertRaises(ValueError):
                module.prepare_gallery(source, root / "gallery", ["tree"])


if __name__ == "__main__":
    unittest.main()
