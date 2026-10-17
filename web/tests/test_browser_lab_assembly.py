"""What: exercise independent Rust/MoonBit artifact identity and tamper rejection."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/assemble_browser_lab.py"
SPEC = importlib.util.spec_from_file_location("browser_assembly", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

LAB_SHA = "a" * 40
LAB_TREE = "b" * 40
UPSTREAM_SHA = "c" * 40
UPSTREAM_TREE = "d" * 40


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ArtifactAssemblyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        web = self.root / "web"
        web.mkdir()
        self.moon = self.root / "moon"
        self.moon.mkdir()
        self.rust = self.root / "rust"
        self.evidence = self.root / "evidence"
        self.evidence.mkdir()
        self.catalog = {
            "upstream": {"revision": UPSTREAM_SHA},
            "moonbit": {"revision": "e" * 40, "tree": "f" * 40},
            "examples": [
                {"id": "hello_world", "moonbit": "implemented"},
                {"id": "text", "moonbit": "implemented"},
                {"id": "future", "moonbit": "not_implemented"},
            ],
        }
        (web / "examples.json").write_text(json.dumps(self.catalog))
        (web / "_headers").write_text("/*\n  Cross-Origin-Opener-Policy: same-origin\n")
        self.patch_web = patch.object(module, "WEB", web)
        self.patch_identity = patch.object(module, "repo_identity", return_value=(LAB_SHA, LAB_TREE))
        self.patch_web.start()
        self.patch_identity.start()
        self.addCleanup(self.patch_web.stop)
        self.addCleanup(self.patch_identity.stop)

        def write(relative: str, data: bytes):
            path = self.moon / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            return sha(data)

        runtime_hashes = {
            "hello_world": write("moonbit/runtime.mjs", b"actual compiled hello"),
            "text": write("moonbit/text.mjs", b"actual compiled text"),
        }
        font_hashes = {name: write("moonbit/" + name, name.encode())
                       for name in ["IBMPlexSans-Regular.ttf", "IBMPlexSans-Italic.ttf",
                                    "IBMPlexSans-SemiBold.ttf"]}
        host_hashes = {"load-timing.mjs": write("load-timing.mjs", b"host")}
        moon_manifest = {
            "upstream": self.catalog["upstream"], "moonbit": self.catalog["moonbit"],
            "lab_revision": LAB_SHA, "lab_tracked_dirty": False,
            "rust_bundled": False, "comparison_status": "unverified",
            "moonbit_unit_tests": "passed", "implemented": ["hello_world", "text"],
            "runtime_sha256_by_example": runtime_hashes,
            "font_sha256_by_file": font_hashes, "moonbit_host_files_sha256": host_hashes,
            "compiler": "test moon",
        }
        (self.moon / "build-manifest.json").write_text(json.dumps(moon_manifest))
        module.prepare_rust_site(self.rust)
        rust_files = {"hello_world.js": b"real Rust wasm-bindgen JS",
                      "hello_world_bg.wasm": b"real pinned WASM"}
        (self.rust / "rust").mkdir()
        for name, data in rust_files.items():
            (self.rust / "rust" / name).write_bytes(data)
        (self.rust / "_headers").write_bytes((web / "_headers").read_bytes())
        (self.rust / "rust-build.log").write_text("cargo compile evidence\n")
        rust_manifest = module.read_manifest(self.rust)
        rust_manifest.update({
            "lab_tree": LAB_TREE,
            "rust_bundled": True,
            "rust_implemented": ["hello_world", "text"],
            "rust_oracle_only": [],
            "rust_subset_sources": [],
            "rust": {
                "source_revision": UPSTREAM_SHA,
                "source_tree": UPSTREAM_TREE,
                "source_modified": False,
                "files": {name: sha(data) for name, data in rust_files.items()},
            },
        })
        (self.rust / "build-manifest.json").write_text(json.dumps(rust_manifest))
        (self.evidence / "negative-control.json").write_text('{"unchanged":true}')

    def change_manifest(self, site: Path, key: str, value):
        manifest = module.read_manifest(site)
        manifest[key] = value
        (site / "build-manifest.json").write_text(json.dumps(manifest))

    def test_prepared_manifest_is_unverified_and_pinned(self):
        prepared = module.read_manifest(self.rust)
        self.assertTrue(prepared["standalone_rust_site"])
        self.assertEqual(prepared["lab_revision"], LAB_SHA)
        self.assertEqual(prepared["upstream"], self.catalog["upstream"])
        self.assertEqual(prepared["comparison_status"], "unverified")

    def test_assemble_exact_pair_preserves_evidence_and_site_provenance(self):
        module.merge_sites(self.moon, self.rust, self.evidence)
        result = module.read_manifest(self.moon)
        self.assertTrue(result["rust_bundled"])
        self.assertEqual(result["rust_implemented"], ["hello_world", "text"])
        self.assertEqual(result["lab_tree"], LAB_TREE)
        self.assertEqual(result["comparison_status"], "unverified")
        self.assertNotIn("standalone_rust_site", result)
        self.assertEqual((self.moon / "rust/hello_world_bg.wasm").read_bytes(), b"real pinned WASM")
        self.assertEqual((self.moon / "_headers").read_bytes(), (module.WEB / "_headers").read_bytes())
        self.assertEqual((self.evidence / "rust-build.log").read_text(), "cargo compile evidence\n")
        self.assertEqual((self.evidence / "negative-control.json").read_text(), '{"unchanged":true}')

    def test_reject_unpinned_upstream_before_copy(self):
        self.change_manifest(self.rust, "upstream", {"revision": "0" * 40})
        with self.assertRaisesRegex(ValueError, "source pins"):
            module.merge_sites(self.moon, self.rust, self.evidence)
        self.assertFalse((self.moon / "rust").exists())

    def test_reject_mismatched_git_tree_before_copy(self):
        self.change_manifest(self.rust, "lab_tree", "9" * 40)
        with self.assertRaisesRegex(ValueError, "lab tree"):
            module.merge_sites(self.moon, self.rust, self.evidence)
        self.assertFalse((self.moon / "rust").exists())

    def test_reject_changed_rust_file_hash_before_copy(self):
        (self.rust / "rust/hello_world_bg.wasm").write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            module.merge_sites(self.moon, self.rust, self.evidence)
        self.assertFalse((self.moon / "rust").exists())

    def test_reject_unlisted_rust_file_before_copy(self):
        (self.rust / "rust/injected.js").write_text("unrecorded")
        with self.assertRaisesRegex(ValueError, "unrecorded"):
            module.merge_sites(self.moon, self.rust, self.evidence)
        self.assertFalse((self.moon / "rust").exists())

    def test_reject_changed_candidate_runtime_before_copy(self):
        (self.moon / "moonbit/runtime.mjs").write_text("tampered runtime")
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            module.merge_sites(self.moon, self.rust, self.evidence)
        self.assertFalse((self.moon / "rust").exists())

    def test_reject_build_attempt_presented_as_verified(self):
        self.change_manifest(self.rust, "comparison_status", "passed")
        with self.assertRaisesRegex(ValueError, "browser validation"):
            module.merge_sites(self.moon, self.rust, self.evidence)

    def test_reject_incorrect_rust_source_sha(self):
        manifest = module.read_manifest(self.rust)
        manifest["rust"]["source_revision"] = "f" * 40
        (self.rust / "build-manifest.json").write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "upstream source identity"):
            module.merge_sites(self.moon, self.rust, self.evidence)

    def test_reject_header_drift(self):
        (self.rust / "_headers").write_text("weakened browser security")
        with self.assertRaisesRegex(ValueError, "security headers"):
            module.merge_sites(self.moon, self.rust, self.evidence)

    def test_reject_preexisting_rust_bundle(self):
        (self.moon / "rust").mkdir()
        with self.assertRaisesRegex(ValueError, "already includes Rust"):
            module.merge_sites(self.moon, self.rust, self.evidence)

    def test_reject_reused_standalone_output(self):
        with self.assertRaisesRegex(ValueError, "must be new"):
            module.prepare_rust_site(self.rust)


if __name__ == "__main__":
    unittest.main()
