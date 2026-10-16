"""Implemented subsets are explicit builds, never a relabeled extra oracle."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("subset_rust_build", SCRIPTS / "build_rust.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture_catalog():
    catalog = json.loads((module.WEB / "examples.json").read_text())
    catalog = copy.deepcopy(catalog)
    next(entry for entry in catalog["examples"] if entry["id"] == "tab_stop")["moonbit"] = "implemented"
    return catalog


class RustSubsetTests(unittest.TestCase):
    def test_only_explicit_implemented_subset_selected_without_mutating_catalog(self):
        catalog = fixture_catalog()
        before = copy.deepcopy(catalog)
        self.assertEqual(module.selected_examples(catalog, [], False, ["tab_stop"]), ["tab_stop"])
        self.assertEqual(catalog, before)
        self.assertEqual(module.selected_examples(catalog, [], False, ["tree", "tab_stop"]), ["tree", "tab_stop"])

    def test_unknown_unimplemented_duplicate_empty_and_incompatible_flags_rejected(self):
        catalog = fixture_catalog()
        missing = copy.deepcopy(catalog)
        next(entry for entry in missing["examples"] if entry["id"] == "tab_stop")["moonbit"] = "not_implemented"
        for requested in [[], ["tab_stop", "tab_stop"], ["unknown"], ["../outside"]]:
            with self.subTest(requested=requested), self.assertRaises(ValueError):
                module.selected_examples(catalog, [], False, requested)
        with self.assertRaises(ValueError):
            module.selected_examples(missing, [], False, ["tab_stop"])
        with self.assertRaises(ValueError):
            module.selected_examples(catalog, [], True, ["tab_stop"])
        with self.assertRaises(ValueError):
            module.selected_examples(catalog, module.extra_oracle_records(["tab_stop"]), False, ["tab_stop"])
        with self.assertRaisesRegex(ValueError, "already has an implemented"):
            module.selected_examples(catalog, module.extra_oracle_records(["tab_stop"]), True)

    def test_source_blob_mismatch_rejected_before_archive_or_compilation(self):
        catalog = fixture_catalog()
        actual_read = Path.read_text
        def read_text(path, *args, **kwargs):
            return json.dumps(catalog) if path == module.WEB / "examples.json" else actual_read(path, *args, **kwargs)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(module, "check_source"), patch.object(Path, "read_text", read_text), patch.object(module, "run", return_value="0" * 40) as run, patch.object(module.subprocess, "run") as archive:
                with self.assertRaisesRegex(ValueError, "implemented subset source blob mismatch: tab_stop"):
                    module.build(root / "upstream", root / "site", root / "target", implemented_examples=["tab_stop"])
                run.assert_called_once_with(["git", "rev-parse", "HEAD:crates/gpui/examples/tab_stop.rs"], root / "upstream", True)
                archive.assert_not_called()

    def test_subset_retains_truthful_manifest_source_fonts_and_only_one_mocked_binary(self):
        # Synthetic compiler outputs test packaging only, never actual Rust.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            upstream = root / "upstream"
            original = upstream / module.GALLERY
            (original / ".cargo").mkdir(parents=True)
            (original / "Cargo.toml").write_text('[workspace]\n[package]\nname="hello_web"\nversion="0.1.0"\n')
            (original / ".cargo/config.toml").write_text('[build]\ntarget="wasm32-unknown-unknown"\n')
            for family, names in {
                "ibm-plex-sans": ["IBMPlexSans-Regular.ttf", "IBMPlexSans-Italic.ttf", "IBMPlexSans-SemiBold.ttf", "IBMPlexSans-SemiBoldItalic.ttf", "license.txt"],
                "lilex": ["Lilex-Regular.ttf", "Lilex-Bold.ttf", "Lilex-Italic.ttf", "Lilex-BoldItalic.ttf", "OFL.txt"],
            }.items():
                for name in names:
                    path = upstream / "assets/fonts" / family / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"synthetic subset font: " + name.encode())
            (upstream / "LICENSE-APACHE").write_text("synthetic license")
            source = upstream / "crates/gpui/examples/tab_stop.rs"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"// synthetic source, not runtime evidence\n")
            catalog = fixture_catalog()
            archive = io.BytesIO()
            with tarfile.open(fileobj=archive, mode="w") as tar:
                for path in upstream.rglob("*"):
                    if path.is_file():
                        tar.add(path, arcname=str(path.relative_to(upstream)))
            site = root / "site"
            site.mkdir()
            (site / "build-manifest.json").write_text(json.dumps({"upstream": catalog["upstream"], "implemented": ["hello_world", "tab_stop"]}))
            commands = []
            def fake_run(arguments, cwd, capture=False):
                commands.append(arguments)
                if arguments[:2] == ["git", "rev-parse"]:
                    return "cc7c34a9979ce4027578ec2c358f503d944ee26f"
                if arguments[0] == "cargo":
                    return ""
                if arguments[0] == "wasm-bindgen" and "--out-dir" in arguments:
                    out = Path(arguments[arguments.index("--out-dir") + 1])
                    (out / "tab_stop.js").write_text("// synthetic binding")
                    (out / "tab_stop_bg.wasm").write_bytes(b"synthetic wasm")
                    return ""
                if arguments[0] == "rustc":
                    return "rustc 1.93.0-nightly (synthetic)"
                if arguments == ["wasm-bindgen", "--version"]:
                    return "wasm-bindgen 0.2.129"
                self.fail(f"Unexpected command: {arguments}")
            before = {str(path.relative_to(upstream)): path.read_bytes() for path in upstream.rglob("*") if path.is_file()}
            actual_read = Path.read_text
            def read_text(path, *args, **kwargs):
                return json.dumps(catalog) if path == module.WEB / "examples.json" else actual_read(path, *args, **kwargs)
            with patch.object(module, "check_source"), patch.object(module, "run", side_effect=fake_run), patch.object(Path, "read_text", read_text), patch.object(module.subprocess, "run") as command:
                command.return_value.stdout = archive.getvalue()
                module.build(upstream, site, root / "target", implemented_examples=["tab_stop"])
            build = json.loads((site / "build-manifest.json").read_text())
            self.assertEqual(build["rust_implemented"], ["tab_stop"])
            self.assertEqual(build["rust_oracle_only"], [])
            self.assertEqual(build["rust"]["implemented_subset"], ["tab_stop"])
            self.assertFalse(build["rust"]["oracle_only"])
            self.assertEqual(build["rust_subset_sources"][0]["status"], "implemented_subset")
            self.assertEqual(build["rust_subset_sources"][0]["source_sha256"], hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertEqual((site / "rust/unchanged-source/tab_stop.rs").read_bytes(), source.read_bytes())
            self.assertEqual(len(build["rust"]["embedded_fonts"]), 8)
            for relative, digest in build["rust"]["files"].items():
                self.assertEqual(hashlib.sha256((site / "rust" / relative).read_bytes()).hexdigest(), digest)
            self.assertEqual(before, {str(path.relative_to(upstream)): path.read_bytes() for path in upstream.rglob("*") if path.is_file()})
            cargo, = [command for command in commands if command[0] == "cargo"]
            self.assertEqual([cargo[i + 1] for i, arg in enumerate(cargo) if arg == "--bin"], ["tab_stop"])


if __name__ == "__main__":
    unittest.main()
