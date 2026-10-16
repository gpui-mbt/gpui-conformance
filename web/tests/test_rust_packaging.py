"""Keep extra example registration separate from immutable upstream sources."""
import importlib.util
import hashlib
import io
import json
import tarfile
from unittest.mock import patch
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


# Exact historical source catalog from suite d6945a888bd0512b4c60af518806e034df665626.
# Candidate registration must never rewrite the historical Rust-only contract.
HISTORICAL_CATALOG = Path(__file__).parent / "fixtures/tab-stop-rust-only-catalog-d6945a88.json"
HISTORICAL_CATALOG_SHA256 = "39ed4ba5868c3c9eb5d6b7e26b9f668640e08d460ca8a26af568890e51cbc8c2"

def historical_catalog():
    raw = HISTORICAL_CATALOG.read_bytes()
    if hashlib.sha256(raw).hexdigest() != HISTORICAL_CATALOG_SHA256:
        raise AssertionError("Historical Rust-only catalog fixture changed")
    return json.loads(raw)


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

    def test_focus_visible_oracle_keeps_unchanged_source_identity(self):
        record, = module.extra_oracle_records(["focus_visible"])
        self.assertEqual(record["source"], "crates/gpui/examples/focus_visible.rs")
        self.assertEqual(record["source_blob"], "c5b3d5dfec3a189d088a621baff55eb55a121b6c")
        self.assertEqual(record["upstream_revision"], "5a5fbe79917971a4d52a96b6ddb04da198a5012e")
        self.assertEqual((record["width"], record["height"], record["dpr"]), (800, 600, 1))
        self.assertEqual(record["status"], "rust_oracle_only")
        self.assertEqual(record["candidate"], "not_implemented")

    def test_rejects_unknown_path_and_duplicate_extra_oracles(self):
        for names in [["../outside"], ["other"], ["scrollable", "scrollable"],
                      ["focus_visible", "focus_visible"], ["tab_stop", "tab_stop"], ["drag_drop", "drag_drop"]]:
            with self.subTest(names=names), self.assertRaises(ValueError):
                module.extra_oracle_records(names)

    def test_registers_only_requested_additional_bins(self):
        for requested in [["scrollable"], ["tree", "scrollable"], ["focus_visible"],
                          ["tree", "scrollable", "focus_visible"], ["tab_stop"],
                          ["tree", "scrollable", "focus_visible", "tab_stop"], ["drag_drop"]]:
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

    def test_tab_stop_oracle_is_source_pinned_and_selected_without_candidate_claims(self):
        record, = module.extra_oracle_records(["tab_stop"])
        self.assertEqual(record["source_blob"], "cc7c34a9979ce4027578ec2c358f503d944ee26f")
        self.assertEqual(record["source_sha256"], "be187a56c091ee0b609fa396cae4a13b49dcf98ff9e602d8caed3126de3f6a8e")
        self.assertEqual(record["candidate"], "not_implemented")
        catalog = historical_catalog()
        self.assertEqual(module.selected_examples(catalog, [record], True), ["tab_stop"])
        self.assertNotIn("tab_stop", module.selected_examples(catalog, []))
        self.assertEqual(module.selected_examples(catalog, [record])[-1], "tab_stop")
        with self.assertRaisesRegex(ValueError, "requires"):
            module.selected_examples(catalog, [], True)
        for name in ["scrollable", "focus_visible"]:
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "already has an implemented"):
                module.selected_examples(catalog, module.extra_oracle_records([name]), True)

    def test_drag_drop_oracle_is_explicit_and_absent_from_matched_gallery(self):
        record, = module.extra_oracle_records(["drag_drop"])
        self.assertEqual(record["source_blob"], "8f038ef3308fee9b097e7289665c9fa47cd6945b")
        self.assertEqual(record["source_sha256"], "4011afde7c64fac2559b78918e6fdabdc563fe9f7591c74425d72da906dcc47a")
        self.assertEqual(record["candidate"], "not_implemented")
        catalog = json.loads((module.WEB / "examples.json").read_text())
        self.assertFalse(any(entry["id"] == "drag_drop" for entry in catalog["examples"]))
        self.assertEqual(module.selected_examples(catalog, [record], True), ["drag_drop"])
        self.assertNotIn("drag_drop", module.selected_examples(catalog, []))
        self.assertEqual(module.selected_examples(catalog, [record])[-1], "drag_drop")
        with self.assertRaises(ValueError):
            module.selected_examples(catalog, [], False, ["drag_drop"])

    def test_implemented_tab_stop_uses_normal_packaging_and_cannot_be_an_extra_oracle(self):
        catalog = json.loads((module.WEB / "examples.json").read_text())
        self.assertIn("tab_stop", module.selected_examples(catalog, []))
        record, = module.extra_oracle_records(["tab_stop"])
        for oracle_only in (False, True):
            with self.subTest(oracle_only=oracle_only), self.assertRaisesRegex(ValueError, "already has an implemented"):
                module.selected_examples(catalog, [record], oracle_only)

    def test_oracle_only_build_manifest_and_retained_inputs_are_truthful_without_running_rust(self):
        # Mocked compiler output exercises packaging, never runtime evidence.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            upstream = root / "upstream"
            original = upstream / module.GALLERY
            (original / ".cargo").mkdir(parents=True)
            (original / "Cargo.toml").write_text('[workspace]\n[package]\nname = "hello_web"\nversion = "0.1.0"\n')
            (original / ".cargo/config.toml").write_text('[build]\ntarget = "wasm32-unknown-unknown"\n')
            for family, names in {
                "ibm-plex-sans": ["IBMPlexSans-Regular.ttf", "IBMPlexSans-Italic.ttf", "IBMPlexSans-SemiBold.ttf", "IBMPlexSans-SemiBoldItalic.ttf", "license.txt"],
                "lilex": ["Lilex-Regular.ttf", "Lilex-Bold.ttf", "Lilex-Italic.ttf", "Lilex-BoldItalic.ttf", "OFL.txt"],
            }.items():
                for name in names:
                    path = upstream / "assets/fonts" / family / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"synthetic packaging input: " + name.encode())
            (upstream / "LICENSE-APACHE").write_text("synthetic license")
            example = upstream / "crates/gpui/examples/tab_stop.rs"
            example.parent.mkdir(parents=True)
            example.write_bytes(b"// synthetic source input, not Rust evidence\n")
            record, = module.extra_oracle_records(["tab_stop"])
            record["source_sha256"] = hashlib.sha256(example.read_bytes()).hexdigest()
            archive = io.BytesIO()
            with tarfile.open(fileobj=archive, mode="w") as tar:
                for path in upstream.rglob("*"):
                    if path.is_file():
                        tar.add(path, arcname=str(path.relative_to(upstream)))
            catalog = historical_catalog()
            site = root / "site"
            site.mkdir()
            (site / "build-manifest.json").write_text(json.dumps({"upstream": catalog["upstream"], "implemented": ["hello_world"]}))
            commands = []
            def fake_run(arguments, cwd, capture=False):
                commands.append(arguments)
                if arguments[:2] == ["git", "rev-parse"]:
                    return record["source_blob"]
                if arguments[0] == "cargo":
                    return ""
                if arguments[0] == "wasm-bindgen" and "--out-dir" in arguments:
                    output = Path(arguments[arguments.index("--out-dir") + 1])
                    (output / "tab_stop.js").write_text("// synthetic binding")
                    (output / "tab_stop_bg.wasm").write_bytes(b"synthetic wasm")
                    return ""
                if arguments[0] == "rustc":
                    return "rustc 1.93.0-nightly (synthetic)"
                if arguments == ["wasm-bindgen", "--version"]:
                    return "wasm-bindgen 0.2.129"
                self.fail(f"Unexpected command: {arguments}")
            before = {str(path.relative_to(upstream)): path.read_bytes() for path in upstream.rglob("*") if path.is_file()}
            original_read_text = Path.read_text
            def read_historical_catalog(path, *args, **kwargs):
                if path == module.WEB / "examples.json":
                    return json.dumps(catalog)
                return original_read_text(path, *args, **kwargs)
            with patch.object(Path, "read_text", read_historical_catalog), patch.object(module, "check_source"), patch.object(module, "extra_oracle_records", return_value=[record]), patch.object(module, "run", side_effect=fake_run), patch.object(module.subprocess, "run") as archive_run:
                archive_run.return_value.stdout = archive.getvalue()
                module.build(upstream, site, root / "target", ["tab_stop"], True)
            build = json.loads((site / "build-manifest.json").read_text())
            self.assertEqual(build["rust_implemented"], ["tab_stop"])
            self.assertEqual(build["implemented"], ["hello_world"])
            self.assertTrue(build["rust"]["oracle_only"])
            self.assertFalse(build["rust"]["source_modified"])
            self.assertEqual(build["rust"]["packaging"]["additional_bins"], [{"name": "tab_stop", "source": record["source"]}])
            self.assertEqual(len(build["rust"]["embedded_fonts"]), 8)
            self.assertEqual((site / "rust/unchanged-source/tab_stop.rs").read_bytes(), example.read_bytes())
            for relative, digest in build["rust"]["files"].items():
                self.assertEqual(hashlib.sha256((site / "rust" / relative).read_bytes()).hexdigest(), digest)
            self.assertEqual(before, {str(path.relative_to(upstream)): path.read_bytes() for path in upstream.rglob("*") if path.is_file()})
            cargo, = [command for command in commands if command[0] == "cargo"]
            self.assertEqual([cargo[index + 1] for index, argument in enumerate(cargo) if argument == "--bin"], ["tab_stop"])

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
