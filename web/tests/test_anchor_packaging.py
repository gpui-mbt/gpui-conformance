"""Synthetic/static packaging tests only. No Rust or browser execution."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import build_rust
import prepare_anchor_site


class AnchorPackagingTests(unittest.TestCase):
    def test_exact_extra_oracle_and_no_matched_placeholder(self):
        record, = build_rust.extra_oracle_records(["anchor"])
        self.assertEqual(record["source_blob"], "b4b280b714a61cea2cd3f3a8ffd82a8f0000eb6b")
        self.assertEqual(record["source_sha256"], "5be423ce91b36db94857a8f7758f7f5967d0103b77941fa7bc7c5a64e3c4fe72")
        self.assertEqual(record["upstream_revision"], "5a5fbe79917971a4d52a96b6ddb04da198a5012e")
        self.assertEqual((record["width"], record["height"], record["dpr"]), (750, 600, 1))
        catalog = json.loads(build_rust.anchor_oracle_catalog_bytes(build_rust.WEB))
        self.assertFalse(any(entry["id"] == "anchor" for entry in catalog["examples"]))
        self.assertEqual(build_rust.selected_examples(catalog, [record], True), ["anchor"])
        self.assertNotIn("anchor", build_rust.selected_examples(catalog, []))
        with self.assertRaises(ValueError):
            build_rust.extra_oracle_records(["anchor", "anchor"])
        with self.assertRaises(ValueError):
            build_rust.selected_examples(catalog, [], False, ["anchor"])

    def test_relocates_exact_example_path_without_upstream_edits(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            original = source / build_rust.GALLERY
            (original / ".cargo").mkdir(parents=True)
            (original / "Cargo.toml").write_text('[workspace]\n[package]\nname="hello_web"\nversion="0.1.0"\n')
            example = source / "crates/gpui/examples/anchor.rs"
            example.parent.mkdir(parents=True)
            example.write_text("// synthetic unchanged upstream input, not execution evidence\n")
            before = {str(p.relative_to(source)): p.read_bytes() for p in source.rglob("*") if p.is_file()}
            record = build_rust.prepare_gallery(source, root / "gallery", ["anchor"])
            bins = tomllib.loads((root / "gallery/Cargo.toml").read_text())["bin"]
            self.assertEqual(len(bins), 1)
            self.assertEqual(bins[0]["name"], "anchor")
            self.assertEqual((root / "gallery" / bins[0]["path"]).resolve(), example)
            self.assertFalse(record["upstream_files_modified"])
            self.assertEqual(before, {str(p.relative_to(source)): p.read_bytes() for p in source.rglob("*") if p.is_file()})

    def test_static_site_records_unused_core_metadata_without_a_candidate_build(self):
        calls = []
        def run(args, cwd, capture):
            calls.append(args)
            if args[1] == "status":
                return ""
            return ("1" if args[-1] == "HEAD" else "2") * 40
        with tempfile.TemporaryDirectory() as temporary, patch.object(prepare_anchor_site, "run", side_effect=run):
            out = Path(temporary) / "site"
            prepare_anchor_site.prepare(out)
            manifest = json.loads((out / "build-manifest.json").read_text())
            self.assertEqual(manifest["implemented"], [])
            self.assertEqual(manifest["moonbit_execution"], "not_run")
            self.assertEqual(manifest["comparison_status"], "not_run")
            self.assertFalse(manifest["rust_bundled"])
            self.assertEqual(manifest["moonbit"], json.loads((out / "examples.json").read_text())["moonbit"])
            self.assertEqual(manifest["moonbit_host_files_sha256"]["load-timing.mjs"], hashlib.sha256((out / "load-timing.mjs").read_bytes()).hexdigest())
            self.assertEqual(sorted(p.name for p in out.iterdir()), ["_headers", "build-manifest.json", "examples.json", "load-timing.mjs"])
            self.assertTrue(all(command[0] == "git" for command in calls))
            with self.assertRaisesRegex(ValueError, "output exists"):
                prepare_anchor_site.prepare(out)

    def test_isolated_oracle_uses_frozen_metadata_after_live_candidate_registration(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = root / build_rust.ANCHOR_CATALOG
            fixture.parent.mkdir(parents=True)
            raw = build_rust.anchor_oracle_catalog_bytes(build_rust.WEB)
            fixture.write_bytes(raw)
            live = json.loads(raw)
            live["moonbit"]["revision"] = "a" * 40
            live["examples"].append({"id": "anchor", "moonbit": "implemented"})
            (root / "examples.json").write_text(json.dumps(live))
            for name in ["load-timing.mjs", "_headers"]:
                (root / name).write_bytes((prepare_anchor_site.WEB / name).read_bytes())
            site = root / "site"
            def git(args, cwd, capture):
                return "" if args[1] == "status" else "1" * 40
            with patch.object(prepare_anchor_site, "WEB", root), patch.object(prepare_anchor_site, "run", side_effect=git):
                prepare_anchor_site.prepare(site)
            self.assertEqual((site / "examples.json").read_bytes(), raw)
            manifest = json.loads((site / "build-manifest.json").read_text())
            with patch.object(build_rust, "WEB", root):
                self.assertEqual(build_rust.site_catalog(site, manifest, ["anchor"], True, None), json.loads(raw))
                self.assertEqual(build_rust.site_catalog(site, {}, [], False, None), live)
                for flags in [([], True, None), (["anchor"], False, None), (["anchor", "tree"], True, None), (["anchor"], True, ["anchor"])]:
                    with self.assertRaisesRegex(ValueError, "requires only"):
                        build_rust.site_catalog(site, manifest, *flags)
                bad = {**manifest, "moonbit": {**manifest["moonbit"], "revision": "0" * 40}}
                with self.assertRaisesRegex(ValueError, "metadata differs"):
                    build_rust.site_catalog(site, bad, ["anchor"], True, None)
                (site / "examples.json").write_text(json.dumps(live))
                with self.assertRaisesRegex(ValueError, "catalog differs"):
                    build_rust.site_catalog(site, manifest, ["anchor"], True, None)
                fixture.write_bytes(raw + b" ")
                with self.assertRaisesRegex(ValueError, "catalog bytes changed"):
                    build_rust.anchor_oracle_catalog_bytes(root)
            with patch.object(prepare_anchor_site, "WEB", root):
                with self.assertRaisesRegex(ValueError, "catalog bytes changed"):
                    prepare_anchor_site.prepare(root / "corrupt-site")
                self.assertFalse((root / "corrupt-site").exists())

    def test_frozen_oracle_remains_candidate_free_and_ci_is_isolated(self):
        host = (build_rust.WEB / "rust/host.mjs").read_text()
        self.assertIn("anchor: './anchor.js'", host)
        self.assertNotIn("anchor", [entry["id"] for entry in json.loads(build_rust.anchor_oracle_catalog_bytes(build_rust.WEB))["examples"]])
        workflow = (build_rust.WEB.parent / ".github/workflows/anchor-oracle.yml").read_text()
        self.assertIn("--oracle-only --extra-example anchor", workflow)
        self.assertNotIn("build_moonbit.py", workflow)
        self.assertIn("if: always()", workflow)
        self.assertIn("verify-anchor-results.mjs", workflow)

    def test_dirty_suite_refused_before_preparation(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(prepare_anchor_site, "run", return_value=" M web/rust/host.mjs"):
            out = Path(temporary) / "site"
            with self.assertRaisesRegex(ValueError, "clean and committed"):
                prepare_anchor_site.prepare(out)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
