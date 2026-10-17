"""Synthetic file/manifest contracts; these fixtures are not compiled runtime evidence."""
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/browser_build_artifacts.py"
SPEC = importlib.util.spec_from_file_location("browser_build_artifacts", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class BrowserBuildArtifactContracts(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.addCleanup(patch.stopall)
        patch.object(MODULE, "ROOT", self.root).start()
        patch.dict(os.environ, {"GITHUB_RUN_ID": "12345", "GITHUB_RUN_ATTEMPT": "1",
                                "GITHUB_REPOSITORY": "gpui-mbt/gpui-conformance"}).start()
        os.environ.pop("GITHUB_OUTPUT", None)
        self.catalog = {"schema_version": 1,
                        "upstream": {"repository": "zed-industries/zed", "revision": "a" * 40,
                                     "hello_world_blob": "b" * 40},
                        "moonbit": {"repository": "gpui-mbt/gpui.mbt", "revision": "c" * 40, "tree": "d" * 40},
                        "examples": [{"id": name, "moonbit": "implemented", "source_blob": blob,
                                      "source": f"crates/gpui/examples/{name}.rs",
                                      "candidate_source": f"web/moonbit/{name}/{name}.mbt"}
                                     for name, blob in (("hello_world", "b" * 40), ("text", "e" * 40))]}
        self.write(".gitignore", "_build/\n__pycache__/\n")
        for name in MODULE.ROOT_FILES:
            self.write("web/" + name, "synthetic pinned static source: " + name)
        MODULE.write_json(self.root / "web/examples.json", self.catalog)
        for name in ("host.mjs", "render.mjs", "index.html"):
            self.write("web/moonbit/site/" + name, "synthetic pinned host source: " + name)
        for entry in self.catalog["examples"]:
            self.write(entry["candidate_source"], "// synthetic source contract; not compiled\n")
        for name in ("Cargo.lock", "host.mjs", "index.html"):
            self.write("web/rust/" + name, "synthetic pinned Rust packaging source: " + name)
        self.write("web/_headers", "/*\n  Cross-Origin-Opener-Policy: same-origin\n")
        self.git("init", "-q")
        self.commit()
        self.inputs_path = self.root / "_build/inputs.json"
        self.inputs = MODULE.pin(self.inputs_path)
        self.expected = MODULE.sha256(self.inputs_path)
        self.moon_site, self.rust_site = self.synthetic_sites()
        self.moon_bundle, self.rust_bundle = self.root / "_build/moon-bundle", self.root / "_build/rust-bundle"

    def write(self, relative, contents):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, text=True, stderr=subprocess.PIPE).strip()

    def commit(self):
        self.git("add", ".")
        self.git("-c", "user.name=Synthetic Contract", "-c", "user.email=contract@example.invalid",
                 "commit", "-qm", "Record the synthetic source boundary for artifact tests")

    def synthetic_sites(self):
        moon = self.root / "_build/moon-site"
        moon.mkdir()
        for name in MODULE.ROOT_FILES:
            shutil.copy2(self.root / "web" / name, moon / name)
        shutil.copytree(self.root / "web/moonbit/site", moon / "moonbit")
        runtime_hashes = {}
        for name in self.inputs["implemented"]:
            runtime = moon / "moonbit" / ("runtime.mjs" if name == "hello_world" else name + ".mjs")
            runtime.write_text("// synthetic runtime bytes for packaging contracts only: " + name)
            runtime_hashes[name] = MODULE.sha256(runtime)
        for name in MODULE.MOONBIT_FONTS:
            (moon / "moonbit" / name).write_text("synthetic font/license input: " + name)
        host_hashes = {"load-timing.mjs": MODULE.sha256(moon / "load-timing.mjs")}
        host_hashes.update({"moonbit/" + name: value for name, value in MODULE.files(self.root / "web/moonbit/site").items()
                           if name.endswith(".mjs")})
        MODULE.write_json(moon / "build-manifest.json", {
            "upstream": self.inputs["upstream"], "moonbit": self.inputs["moonbit"],
            "lab_revision": self.inputs["lab"]["revision"], "lab_tracked_dirty": False,
            "compiler": "synthetic packaging fixture; compiler not invoked",
            "runtime_sha256": runtime_hashes["hello_world"], "runtime_sha256_by_example": runtime_hashes,
            "font_sha256": MODULE.sha256(moon / "moonbit" / MODULE.FONT_FILES[0]),
            "font_sha256_by_file": {name: MODULE.sha256(moon / "moonbit" / name) for name in MODULE.FONT_FILES},
            "implemented": self.inputs["implemented"], "implemented_sources": self.inputs["implemented_sources"],
            "moonbit_host_files_sha256": host_hashes, "rust_bundled": False,
            "comparison_status": "unverified", "moonbit_unit_tests": "passed"})
        rust = self.root / "_build/rust-site"
        MODULE.seed_rust(self.inputs_path, self.expected, rust)
        shutil.copytree(self.root / "web/rust", rust / "rust")
        for name in self.inputs["implemented"]:
            for suffix in (".js", "_bg.wasm", ".d.ts", "_bg.wasm.d.ts"):
                (rust / "rust" / (name + suffix)).write_text("synthetic compiled-output file contract: " + name + suffix)
        for name in ("LICENSE-APACHE", "ibm-plex-sans-license.txt", "lilex-license.txt"):
            (rust / "rust" / name).write_text("synthetic license: " + name)
        shutil.copy2(self.root / "web/_headers", rust / "_headers")
        manifest = MODULE.read_json(rust / "build-manifest.json")
        manifest.update({"rust_bundled": True, "rust_implemented": self.inputs["implemented"],
                         "rust_oracle_only": [], "rust_subset_sources": [],
                         "rust": {"toolchain": "synthetic fixture; rustc not invoked",
                                  "bindings": "synthetic fixture; wasm-bindgen not invoked",
                                  "command": ["cargo", "+nightly-2026-10-14", "build", "--locked", "--release",
                                              "--target", "wasm32-unknown-unknown", "--bin", "hello_world", "--bin", "text"],
                                  "source_modified": False, "source_revision": self.inputs["upstream"]["revision"],
                                  "source_tree": "f" * 40, "oracle_only": False, "implemented_subset": None,
                                  "build_completed_at_utc": "synthetic fixture; not a measured build",
                                  "embedded_fonts": {}, "packaging": {"upstream_files_modified": False},
                                  "files": MODULE.files(rust / "rust")}})
        MODULE.write_json(rust / "build-manifest.json", manifest)
        return moon, rust

    def attest_pair(self):
        for kind, site, bundle in (("moonbit", self.moon_site, self.moon_bundle),
                                   ("rust", self.rust_site, self.rust_bundle)):
            MODULE.attest(self.inputs_path, self.expected, kind, site, bundle)

    def merge(self):
        MODULE.merge(self.inputs_path, self.expected, self.moon_bundle, self.rust_bundle,
                     self.root / "_build/merged", self.root / "_build/evidence")

    def mutate_json(self, path, mutation):
        value = MODULE.read_json(path)
        mutation(value)
        MODULE.write_json(path, value)

    def rehash_provenance(self, bundle):
        self.mutate_json(bundle / "provenance.json", lambda value: value.update(files=MODULE.files(bundle / "site")))

    def test_full_synthetic_round_trip_retains_both_originals_and_requires_future_comparison(self):
        self.attest_pair()
        original = {kind: (bundle / "site/build-manifest.json").read_bytes()
                    for kind, bundle in (("moonbit", self.moon_bundle), ("rust", self.rust_bundle))}
        self.write("_build/evidence/rust-build.log", "synthetic existing evidence")
        self.merge()
        merged = MODULE.read_json(self.root / "_build/merged/build-manifest.json")
        self.assertEqual(merged["comparison_status"], "unverified")
        self.assertEqual(merged["parallel_build"]["verification"], "input-and-artifact-integrity-only")
        self.assertEqual(merged["parallel_build"]["inputs_sha256"], self.expected)
        self.assertEqual(merged["implemented"], self.inputs["implemented"])
        self.assertEqual(merged["lab_tree"], self.inputs["lab"]["tree"])
        for key in MODULE.RUST_FIELDS:
            self.assertEqual(merged[key], MODULE.read_json(self.rust_site / "build-manifest.json")[key])
        for kind in original:
            self.assertEqual((self.root / f"_build/evidence/build-artifacts/{kind}-build-manifest.json").read_bytes(), original[kind])
        self.assertEqual(MODULE.files(self.root / "_build/merged/rust"), MODULE.files(self.rust_site / "rust"))
        self.assertEqual((self.root / "_build/evidence/rust-build.log").read_text(), "synthetic existing evidence")

    def test_seed_only_records_dependency_metadata_without_moonbit_or_oracle_evidence(self):
        site = self.root / "_build/new-seed"
        MODULE.seed_rust(self.inputs_path, self.expected, site)
        seed = MODULE.read_json(site / "build-manifest.json")
        self.assertEqual(seed["site_kind"], "browser_lab_rust_build")
        self.assertEqual(seed["build_role"], "rust")
        self.assertEqual(seed["implemented"], [])
        self.assertFalse(seed["rust_bundled"])
        for name in ("compiler", "moonbit_unit_tests", "runtime_sha256", "rust"):
            self.assertNotIn(name, seed)
        self.assertEqual(set(MODULE.files(site)), {"examples.json", "build-manifest.json"})

    def test_seed_works_with_existing_rust_builder_using_synthetic_compiler_outputs(self):
        with patch.object(sys, "path", [str(SCRIPT.parent), *sys.path]):
            spec = importlib.util.spec_from_file_location("synthetic_full_rust_builder", SCRIPT.parent / "build_rust.py")
            builder = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(builder)
        upstream = self.root / "_build/synthetic-upstream"
        gallery = upstream / builder.GALLERY
        (gallery / ".cargo").mkdir(parents=True)
        (gallery / "Cargo.toml").write_text('[workspace]\n[package]\nname="synthetic"\nversion="0.0.0"\n')
        for relative in ("LICENSE-APACHE", "assets/fonts/ibm-plex-sans/license.txt", "assets/fonts/lilex/OFL.txt"):
            path = upstream / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("synthetic source archive; not runtime evidence")
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode="w") as stream:
            for path in upstream.rglob("*"):
                stream.add(path, arcname=path.relative_to(upstream), recursive=False)
        site = self.root / "_build/existing-builder-site"
        MODULE.seed_rust(self.inputs_path, self.expected, site)
        commands = []

        def synthetic_command(arguments, cwd, capture=False):
            commands.append(arguments)
            if arguments[0] == "cargo":
                return ""
            if arguments[0] == "wasm-bindgen":
                if "--out-dir" in arguments:
                    out = Path(arguments[arguments.index("--out-dir") + 1])
                    name = arguments[arguments.index("--out-name") + 1]
                    for suffix in (".js", "_bg.wasm"):
                        (out / (name + suffix)).write_text("synthetic output; compiler not invoked")
                    return ""
                return "wasm-bindgen synthetic fixture"
            if arguments[0] == "rustc":
                return "rustc synthetic fixture"
            if arguments == ["git", "rev-parse", "HEAD"]:
                return self.inputs["upstream"]["revision"]
            if arguments == ["git", "rev-parse", "HEAD^{tree}"]:
                return self.inputs["lab"]["tree"] if cwd == self.root else "f" * 40
            self.fail(f"Unexpected synthetic builder command: {arguments}")

        with patch.object(builder, "WEB", self.root / "web"), patch.object(builder, "check_source"), patch.object(builder, "run", side_effect=synthetic_command), patch.object(builder.subprocess, "run") as archive_run, contextlib.redirect_stdout(io.StringIO()):
            archive_run.return_value.stdout = archive.getvalue()
            builder.build(upstream, site, self.root / "_build/synthetic-target")
        MODULE.attest(self.inputs_path, self.expected, "rust", site, self.root / "_build/existing-builder-bundle")
        result = MODULE.read_json(site / "build-manifest.json")
        self.assertEqual(result["implemented"], [])
        self.assertEqual(result["rust_implemented"], self.inputs["implemented"])
        self.assertNotIn("moonbit_unit_tests", result)
        self.assertEqual(len([command for command in commands if command[0] == "cargo"]), 1)

    def test_pin_and_verify_cli_export_exact_common_inputs_and_digest(self):
        out = self.root / "_build/cli-inputs.json"
        output = self.root / "_build/github-output"
        with patch.dict(os.environ, {"GITHUB_OUTPUT": str(output)}), patch.object(sys, "argv", [str(SCRIPT), "pin", "--out", str(out)]), contextlib.redirect_stdout(io.StringIO()):
            MODULE.main()
        values = dict(line.split("=", 1) for line in output.read_text().splitlines())
        self.assertEqual(values, {"lab": self.inputs["lab"]["revision"], "gpui": "c" * 40,
                                  "zed": "a" * 40, "inputs_sha256": MODULE.sha256(out)})
        with patch.object(sys, "argv", [str(SCRIPT), "verify-inputs", "--inputs", str(out), "--sha256", values["inputs_sha256"]]), contextlib.redirect_stdout(io.StringIO()):
            MODULE.main()
        self.assertEqual(MODULE.read_json(out)["candidate_sources"]["text"]["source_blob"],
                         self.git("rev-parse", "HEAD:web/moonbit/text/text.mbt"))

    def test_failed_job_rerun_can_join_prior_success_with_same_pins_and_run(self):
        MODULE.attest(self.inputs_path, self.expected, "moonbit", self.moon_site, self.moon_bundle)
        with patch.dict(os.environ, {"GITHUB_RUN_ATTEMPT": "2"}):
            MODULE.attest(self.inputs_path, self.expected, "rust", self.rust_site, self.rust_bundle)
        with patch.dict(os.environ, {"GITHUB_RUN_ATTEMPT": "3"}):
            self.merge()
        self.assertEqual(MODULE.read_json(self.moon_bundle / "provenance.json")["build_github"]["run_attempt"], "1")
        self.assertEqual(MODULE.read_json(self.rust_bundle / "provenance.json")["build_github"]["run_attempt"], "2")
        self.assertEqual(MODULE.read_json(self.rust_bundle / "provenance.json")["inputs"]["github"]["run_attempt"], "1")

    def test_pin_rejects_dirty_and_untracked_build_source_but_allows_dependency_checkouts(self):
        self.write("_sources/gpui/source.mbt", "synthetic dependency checkout")
        self.assertEqual(MODULE.verify_inputs(self.inputs_path, self.expected), self.inputs)
        self.write("web/stray.mjs", "untracked code")
        with self.assertRaisesRegex(ValueError, "untracked lab source"):
            MODULE.pin(self.root / "_build/rejected-untracked.json")
        (self.root / "web/stray.mjs").unlink()
        self.write("web/app.js", "dirty tracked code")
        with self.assertRaisesRegex(ValueError, "tracked lab source is dirty"):
            MODULE.pin(self.root / "_build/rejected-dirty.json")

    def test_pin_rejects_short_revisions_missing_source_pins_and_duplicate_examples(self):
        mutations = [lambda c: c["moonbit"].update(revision="main"),
                     lambda c: c["moonbit"].update(tree="A" * 40),
                     lambda c: c["upstream"].update(revision="a" * 39),
                     lambda c: c["examples"][1].pop("source_blob"),
                     lambda c: c["examples"].append(copy.deepcopy(c["examples"][0])),
                     lambda c: c["examples"][1].update(candidate_source="../outside"),
                     lambda c: c["examples"][0].update(source_blob="0" * 40)]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                catalog = copy.deepcopy(self.catalog)
                mutate(catalog)
                MODULE.write_json(self.root / "web/examples.json", catalog)
                self.commit()
                with self.assertRaises(ValueError):
                    MODULE.pin(self.root / f"_build/rejected-{index}.json")

    def test_verified_inputs_require_exact_bytes_current_sha_catalog_lock_and_run(self):
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            MODULE.verify_inputs(self.inputs_path, "0" * 64)
        with patch.dict(os.environ, {"GITHUB_RUN_ID": "67890"}), self.assertRaisesRegex(ValueError, "different GitHub run"):
            MODULE.verify_inputs(self.inputs_path, self.expected)
        for field in ("lab", "catalog_sha256", "cargo_lock_sha256", "implemented", "github"):
            with self.subTest(field=field):
                changed = copy.deepcopy(self.inputs)
                if field == "lab":
                    changed[field]["revision"] = "0" * 40
                elif field == "implemented":
                    changed[field] = ["hello_world"]
                elif field == "github":
                    changed[field]["run_id"] = "9"
                else:
                    changed[field] = "0" * 64
                path = self.root / "_build/changed-inputs.json"
                MODULE.write_json(path, changed)
                with self.assertRaises(ValueError):
                    MODULE.verify_inputs(path, MODULE.sha256(path))
        self.write("web/rust/Cargo.lock", "different lock contents")
        self.commit()
        with self.assertRaisesRegex(ValueError, "pinned inputs differ"):
            MODULE.verify_inputs(self.inputs_path, self.expected)

    def test_manifest_mismatches_are_rejected_even_with_recomputed_outer_file_hashes(self):
        self.attest_pair()
        path = self.moon_bundle / "site/build-manifest.json"
        original = path.read_bytes()
        mutations = [lambda m: m.update(lab_revision="0" * 40),
                     lambda m: m.update(lab_tree="0" * 40),
                     lambda m: m["moonbit"].update(revision="0" * 40),
                     lambda m: m["upstream"].update(revision="0" * 40),
                     lambda m: m.update(implemented=["hello_world"]),
                     lambda m: m["implemented_sources"].pop("text"),
                     lambda m: m.update(lab_tracked_dirty=True),
                     lambda m: m.update(moonbit_unit_tests="not_run"),
                     lambda m: m.update(comparison_status="passed"),
                     lambda m: m["runtime_sha256_by_example"].update(text="0" * 64),
                     lambda m: m["moonbit_host_files_sha256"].pop("moonbit/host.mjs"),
                     lambda m: m["font_sha256_by_file"].pop("IBMPlexSans-Italic.ttf")]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                path.write_bytes(original)
                self.mutate_json(path, mutate)
                self.rehash_provenance(self.moon_bundle)
                with self.assertRaises(ValueError):
                    self.merge()

    def test_rust_full_set_lock_scope_and_hashes_are_required_after_outer_rehash(self):
        self.attest_pair()
        path = self.rust_bundle / "site/build-manifest.json"
        original = path.read_bytes()
        mutations = [lambda m: m.update(rust_implemented=["hello_world"]),
                     lambda m: m.update(rust_oracle_only=[{"id": "text"}]),
                     lambda m: m.update(rust_subset_sources=[{"id": "text"}]),
                     lambda m: m.update(implemented=["hello_world"]),
                     lambda m: m.update(compiler="invented MoonBit compiler"),
                     lambda m: m["rust"].update(source_revision="0" * 40),
                     lambda m: m["rust"].update(source_modified=True),
                     lambda m: m["rust"].update(oracle_only=True),
                     lambda m: m["rust"].update(implemented_subset=["text"]),
                     lambda m: m["rust"]["packaging"].update(upstream_files_modified=True),
                     lambda m: m["rust"]["command"].remove("--locked"),
                     lambda m: m["rust"]["files"].pop("text_bg.wasm"),
                     lambda m: m["rust"]["files"].update({"../outside": "0" * 64})]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                path.write_bytes(original)
                self.mutate_json(path, mutate)
                self.rehash_provenance(self.rust_bundle)
                with self.assertRaises(ValueError):
                    self.merge()

    def test_missing_or_tampered_runtime_fails_before_attestation(self):
        for kind, site, relative in (("moonbit", self.moon_site, "moonbit/text.mjs"),
                                     ("rust", self.rust_site, "rust/text_bg.wasm")):
            path = site / relative
            original = path.read_bytes()
            for mutate in (lambda: path.write_text("tampered runtime"), path.unlink):
                with self.subTest(kind=kind, mutate=mutate):
                    path.write_bytes(original)
                    mutate()
                    with self.assertRaises(ValueError):
                        MODULE.attest(self.inputs_path, self.expected, kind, site, self.root / "_build/rejected")
            path.write_bytes(original)

    def test_recorded_rust_file_removal_cannot_hide_missing_compiled_example(self):
        self.attest_pair()
        (self.rust_bundle / "site/rust/text_bg.wasm").unlink()
        self.mutate_json(self.rust_bundle / "site/build-manifest.json", lambda m: m["rust"]["files"].pop("text_bg.wasm"))
        self.rehash_provenance(self.rust_bundle)
        with self.assertRaisesRegex(ValueError, "missing Rust compiled output"):
            self.merge()

    def test_rehashed_extra_rust_binary_cannot_expand_the_pinned_full_build_set(self):
        self.attest_pair()
        path = self.rust_bundle / "site/rust/unexpected_bg.wasm"
        path.write_text("synthetic unexpected binary")
        self.mutate_json(self.rust_bundle / "site/build-manifest.json",
                         lambda m: m["rust"]["files"].update({path.name: MODULE.sha256(path)}))
        self.rehash_provenance(self.rust_bundle)
        with self.assertRaisesRegex(ValueError, "unexpected or missing Rust files"):
            self.merge()

    def test_rehashed_static_files_catalog_and_lock_still_must_match_pinned_source(self):
        self.attest_pair()
        for bundle, relative in ((self.moon_bundle, "app.js"), (self.moon_bundle, "moonbit/host.mjs"),
                                 (self.moon_bundle, "examples.json"), (self.rust_bundle, "rust/Cargo.lock"),
                                 (self.rust_bundle, "_headers")):
            with self.subTest(relative=relative):
                path = bundle / "site" / relative
                original = path.read_bytes()
                manifest_path = bundle / "site/build-manifest.json"
                original_manifest = manifest_path.read_bytes()
                path.write_text("tampered pinned source")
                if relative.startswith("rust/"):
                    self.mutate_json(manifest_path, lambda m: m["rust"]["files"].update({relative[5:]: MODULE.sha256(path)}))
                self.rehash_provenance(bundle)
                with self.assertRaises(ValueError):
                    self.merge()
                path.write_bytes(original)
                manifest_path.write_bytes(original_manifest)
                self.rehash_provenance(bundle)

    def test_cross_run_cross_pin_relabeling_and_provenance_paths_fail(self):
        self.attest_pair()
        path = self.moon_bundle / "provenance.json"
        original = path.read_bytes()
        mutations = [lambda p: p.update(kind="rust"),
                     lambda p: p.update(inputs_sha256="0" * 64),
                     lambda p: p["inputs"]["lab"].update(revision="0" * 40),
                     lambda p: p["inputs"]["github"].update(run_attempt="2"),
                     lambda p: p["inputs"]["moonbit"].update(revision="0" * 40),
                     lambda p: p["build_github"].update(run_id="9999"),
                     lambda p: p["build_github"].update(run_attempt=""),
                     lambda p: p["files"].update({"../outside": "0" * 64}),
                     lambda p: p.update(comparison_status="passed")]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                path.write_bytes(original)
                self.mutate_json(path, mutate)
                with self.assertRaises(ValueError):
                    self.merge()

    def test_unexpected_bundle_entries_files_and_replaced_manifest_fail(self):
        self.attest_pair()
        extra = self.moon_bundle / "unexpected.json"
        extra.write_text("unexpected")
        with self.assertRaisesRegex(ValueError, "unexpected bundle entries"):
            self.merge()
        extra.unlink()
        extra = self.moon_bundle / "site/moonbit/unexpected.mjs"
        extra.write_text("unexpected")
        self.rehash_provenance(self.moon_bundle)
        with self.assertRaisesRegex(ValueError, "unexpected or missing MoonBit site files"):
            self.merge()
        extra.unlink()
        shutil.copy2(self.rust_bundle / "site/build-manifest.json", self.moon_bundle / "site/build-manifest.json")
        self.rehash_provenance(self.moon_bundle)
        with self.assertRaisesRegex(ValueError, "wrong build role"):
            self.merge()

    def test_symlinked_artifact_file_directory_and_input_are_rejected(self):
        self.attest_pair()
        target = self.root / "outside"
        target.write_text("external file")
        for relative in ("site/moonbit/symlink.mjs", "site/rust"):
            with self.subTest(relative=relative):
                link = self.moon_bundle / relative
                link.symlink_to(target if relative.endswith(".mjs") else self.rust_site / "rust")
                with self.assertRaisesRegex(ValueError, "symlink"):
                    self.merge()
                link.unlink()
        inputs_link = self.root / "_build/linked-inputs.json"
        inputs_link.symlink_to(self.inputs_path)
        with self.assertRaisesRegex(ValueError, "symlink"):
            MODULE.verify_inputs(inputs_link, self.expected)

    def test_duplicate_json_fields_and_existing_merge_output_are_rejected(self):
        duplicate = self.root / "_build/duplicate.json"
        duplicate.write_text('{"schema_version":1,"schema_version":1}')
        with self.assertRaisesRegex(ValueError, "duplicate JSON field"):
            MODULE.read_json(duplicate)
        self.attest_pair()
        self.write("_build/merged/preserve.txt", "existing user output")
        with self.assertRaisesRegex(ValueError, "merged output already exists"):
            self.merge()
        self.assertEqual((self.root / "_build/merged/preserve.txt").read_text(), "existing user output")


if __name__ == "__main__":
    unittest.main()
