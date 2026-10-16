import unittest
import os
import hashlib
import json
import tempfile
from html.parser import HTMLParser
from pathlib import Path

from copy import deepcopy
from unittest.mock import patch

from scripts.build_test_catalog import (
    BROWSER_LAB_BASE_URL_ENV,
    BROWSER_RESULT_PATH,
    BROWSER_THUMBNAIL_ASSET,
    BROWSER_THUMBNAIL_SOURCE,
    TEXT_CAPTURE_MANIFEST,
    PRIME_CAPTURE_MANIFEST,
    ROOT,
    browser_lab_comparison_url,
    build_catalog,
    load_json,
    normalize_browser_lab_base_url,
    pixel_status,
    validate_browser_inventory,
    write_site,
)


class TestCatalogData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.dict(os.environ, {BROWSER_LAB_BASE_URL_ENV: ""}):
            cls.data = build_catalog("catalog-test-revision")

    def test_headless_totals_are_derived_from_retained_comparison(self):
        data = self.data
        self.assertEqual(data["headless"]["case_count"], 134)
        self.assertEqual(data["headless"]["executed_headless_case_count"], 131)
        self.assertEqual(data["counts"], {
            "pass": 131,
            "mismatch": 0,
            "unsupported": 1,
            "unverified": 2,
        })
        self.assertEqual(len(data["cases"]), 134)
        self.assertEqual(sum(suite["case_count"] for suite in data["suites"]), 134)

    def test_headless_case_ids_and_states_match_the_source_result(self):
        data = self.data
        self.assertEqual(len({case["id"] for case in data["cases"]}), 134)
        self.assertTrue(all(case["source_url"].startswith("https://github.com/") for case in data["cases"]))
        self.assertTrue(all(case["result_url"].endswith("cross-axis-limits-linux-x86_64-20261015.json") for case in data["cases"]))
        self.assertTrue(all(case["comparison_url"] is None for case in data["cases"]))

    def test_unknown_browser_pixel_status_fails_closed(self):
        self.assertEqual(pixel_status("different"), "difference")
        self.assertEqual(pixel_status("equal"), "pass")
        self.assertEqual(pixel_status("pending"), "unverified")

    def test_browser_report_separates_execution_from_pixel_difference(self):
        browser = self.data["browser"]
        self.assertEqual(browser["execution"], "passed")
        self.assertEqual(browser["candidate"], "passed")
        self.assertEqual(browser["rust"], "passed")
        self.assertEqual(browser["status"], "difference")
        self.assertEqual(browser["changed_pixels"], 1532)
        self.assertEqual(browser["total_pixels"], 250000)
        self.assertEqual(browser["changed_percent"], 0.6128)
        self.assertEqual(browser["native_conformance"], "unverified")

    def test_example_catalog_does_not_fabricate_interactive_routes(self):
        examples = self.data["browser_examples"]
        self.assertEqual(len(examples), 7)
        self.assertEqual(examples[0]["status"], "difference")
        self.assertEqual(sum(example["status"] == "unsupported" for example in examples), 2)
        self.assertEqual(sum(example["status"] == "unverified" for example in examples), 4)
        self.assertEqual([example["id"] for example in examples if example["implemented"] and example["interactive"]], ["hello_web"])
        self.assertTrue(all(example["comparison_url"] is None for example in examples))

    def test_verified_base_url_links_only_supported_implemented_examples(self):
        base_url = "https://gpui-conformance-browser-lab.account-name.workers.dev"
        with patch.dict(os.environ, {BROWSER_LAB_BASE_URL_ENV: base_url}):
            examples = build_catalog("catalog-test-revision")["browser_examples"]

        hello_world = next(example for example in examples if example["id"] == "hello_world")
        self.assertEqual(hello_world["comparison_url"], f"{base_url}/?example=hello_world")
        self.assertFalse(hello_world["interactive"])
        for example_id in ("text_layout", "text_wrapper"):
            example = next(item for item in examples if item["id"] == example_id)
            with self.subTest(example=example_id):
                self.assertEqual(example["comparison_url"], f"{base_url}/?example={example_id}")
                self.assertFalse(example["interactive"])
                self.assertEqual((example["width"], example["height"]), (800, 600))
                self.assertEqual(example["status"], "unverified")
                self.assertFalse(example["evidence_available"])
        self.assertTrue(all(
            example["comparison_url"] is None
            for example in examples
            if example["id"] not in {"hello_world", "text_layout", "text_wrapper", "dynamic_fonts", "hello_web"}
        ))

    def test_dynamic_fonts_is_implemented_without_borrowed_evidence(self):
        base = "https://gpui-conformance-browser-lab.account-name.workers.dev"
        with patch.dict(os.environ, {BROWSER_LAB_BASE_URL_ENV: base}):
            port = next(e for e in build_catalog("catalog-test-revision")["browser_examples"] if e["id"] == "dynamic_fonts")
        self.assertTrue(port["implemented"])
        self.assertEqual((port["width"], port["height"], port["interactive"]), (900, 500, False))
        self.assertEqual(port["comparison_url"], f"{base}/?example=dynamic_fonts")
        self.assertEqual(port["source_path"], "crates/gpui_web/examples/hello_web/dynamic_fonts.rs")
        self.assertEqual(port["status"], "unverified")
        self.assertEqual(port["execution"], "unverified")
        self.assertFalse(port["evidence_available"])
        for key in ("result_url", "result_date", "changed_pixels", "total_pixels", "thumbnail"):
            self.assertIsNone(port[key], key)

    def test_prime_sieve_is_interactive_without_borrowed_comparison_evidence(self):
        base = "https://gpui-conformance-browser-lab.account-name.workers.dev"
        with patch.dict(os.environ, {BROWSER_LAB_BASE_URL_ENV: base}):
            prime = next(e for e in build_catalog("catalog-test-revision")["browser_examples"] if e["id"] == "hello_web")
        self.assertTrue(prime["implemented"])
        self.assertEqual((prime["width"], prime["height"], prime["interactive"]), (640, 560, True))
        self.assertEqual(prime["comparison_url"], f"{base}/?example=hello_web")
        self.assertEqual(prime["source_path"], "crates/gpui_web/examples/hello_web/main.rs")
        self.assertEqual(prime["status"], "unverified")
        self.assertEqual(prime["execution"], "unverified")
        self.assertFalse(prime["evidence_available"])
        for key in ("result_url", "result_date", "changed_pixels", "total_pixels"):
            self.assertIsNone(prime[key], key)
        self.assertEqual((prime["thumbnail"]["width"], prime["thumbnail"]["height"]), (640, 560))
        self.assertEqual(prime["thumbnail"]["capture_revision"], "faab43b9b9ee73fc8e1f0b6864b4cf9083c44877")
        self.assertIn("38855611489", prime["thumbnail"]["capture_run_url"])

    def test_browser_lab_url_is_optional_and_fails_closed_for_unsafe_values(self):
        self.assertIsNone(normalize_browser_lab_base_url(None))
        self.assertIsNone(normalize_browser_lab_base_url(""))
        self.assertIsNone(normalize_browser_lab_base_url("  "))
        self.assertIsNone(browser_lab_comparison_url("hello_world", True, None))
        self.assertIsNone(browser_lab_comparison_url("text", True, "https://gpui-conformance-browser-lab.account.workers.dev"))
        self.assertIsNone(browser_lab_comparison_url("hello_world", False, "https://gpui-conformance-browser-lab.account.workers.dev"))
        with self.assertRaises(ValueError):
            browser_lab_comparison_url("hello_world", True, "http://gpui-conformance-browser-lab.account.workers.dev")

        for unsafe in (
            False,
            "false",
            "http://gpui-conformance-browser-lab.account.workers.dev",
            "https://other-account.workers.dev",
            "https://gpui-conformance-browser-lab.account.workers.dev.evil.example",
            "https://gpui-conformance-browser-lab.account.workers.dev/path",
            "https://gpui-conformance-browser-lab.account.workers.dev/?example=text",
            "https://gpui-conformance-browser-lab.account.workers.dev/#fragment",
            "https://user@gpui-conformance-browser-lab.account.workers.dev",
            "https://gpui-conformance-browser-lab.account.workers.dev:8443",
        ):
            with self.subTest(unsafe=unsafe):
                with self.assertRaises(ValueError):
                    normalize_browser_lab_base_url(unsafe)

        with patch.dict(os.environ, {BROWSER_LAB_BASE_URL_ENV: "http://gpui-conformance-browser-lab.account.workers.dev"}):
            with self.assertRaises(ValueError):
                build_catalog("catalog-test-revision")

    def test_browser_inventory_must_match_retained_pins_and_keep_measured_ports(self):
        browser = load_json(BROWSER_RESULT_PATH)
        inventory = load_json("web/examples.json")
        validate_browser_inventory(browser, inventory)

        for kind in ("moonbit", "upstream"):
            for key in ("repository", "revision"):
                changed_pin = deepcopy(inventory)
                changed_pin[kind][key] = "changed"
                with self.subTest(kind=kind, key=key):
                    with self.assertRaisesRegex(ValueError, f"{kind} pin"):
                        validate_browser_inventory(browser, changed_pin)

        changed_implementation = deepcopy(inventory)
        changed_implementation["examples"][0]["moonbit"] = "not_implemented"
        with self.assertRaisesRegex(ValueError, "implemented browser examples"):
            validate_browser_inventory(browser, changed_implementation)

    def test_declared_implementations_may_exceed_retained_build(self):
        browser = load_json(BROWSER_RESULT_PATH)
        inventory = deepcopy(load_json("web/examples.json"))
        self.assertEqual(browser["build"]["implemented"], ["hello_world"])
        for example_id in ("text_layout", "text_wrapper"):
            next(item for item in inventory["examples"] if item["id"] == example_id)["moonbit"] = "implemented"
        validate_browser_inventory(browser, inventory)

    def test_duplicate_browser_ids_are_rejected(self):
        inventory = deepcopy(load_json("web/examples.json"))
        inventory["examples"].append(deepcopy(inventory["examples"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate browser example IDs"):
            validate_browser_inventory(load_json(BROWSER_RESULT_PATH), inventory)

    def test_new_ports_keep_own_previews_without_inheriting_hello_world_result(self):
        examples = {example["id"]: example for example in self.data["browser_examples"]}
        hello = examples["hello_world"]
        for example_id in ("text_layout", "text_wrapper"):
            new_port = examples[example_id]
            with self.subTest(example=example_id):
                self.assertTrue(new_port["implemented"])
                self.assertEqual(new_port["implementation"]["status"], "implemented")
                self.assertEqual(new_port["implementation"]["source_url"], (
                    "https://github.com/gpui-mbt/gpui-conformance/blob/catalog-test-revision/"
                    f"web/moonbit/{example_id}/{example_id}.mbt"
                ))
                self.assertEqual(new_port["source_url"], (
                    "https://github.com/zed-industries/zed/blob/"
                    "5a5fbe79917971a4d52a96b6ddb04da198a5012e/"
                    f"crates/gpui/examples/{example_id}.rs"
                ))
                self.assertEqual((new_port["width"], new_port["height"], new_port["interactive"]), (800, 600, False))
                self.assertEqual(new_port["status"], "unverified")
                self.assertEqual(new_port["execution"], "unverified")
                self.assertFalse(new_port["evidence_available"])
                for key in ("result_url", "result_date", "changed_pixels", "total_pixels"):
                    self.assertIsNone(new_port[key], key)
                self.assertEqual((new_port["thumbnail"]["width"], new_port["thumbnail"]["height"]), (800, 600))
                self.assertNotEqual(new_port["thumbnail"]["sha256"], hello["thumbnail"]["sha256"])
                self.assertIn(example_id, new_port["thumbnail"]["url"])
                self.assertEqual(new_port["thumbnail"]["capture_revision"], "422f94adda8be205248f370a335785a9d5940118")
                self.assertIn("422f94adda8be205248f370a335785a9d5940118", new_port["thumbnail"]["capture_source_url"])
                self.assertIn("38848834623", new_port["thumbnail"]["capture_run_url"])
        self.assertTrue(hello["evidence_available"])
        self.assertEqual(hello["status"], "difference")
        self.assertEqual(hello["execution"], "passed")
        self.assertEqual(hello["changed_pixels"], 1532)
        self.assertIn(BROWSER_RESULT_PATH, hello["result_url"])
        self.assertEqual(self.data["browser"]["example_id"], "hello_world")
        self.assertEqual(self.data["browser"]["implemented_count"], 5)
        self.assertEqual(self.data["browser"]["evidence_count"], 1)

    def test_build_capability_is_not_per_example_measurement(self):
        # A build containing all three ports cannot give either new port the
        # legacy file's single hello_world comparison, for equal or different.
        expected_previews = {item["id"]: item["thumbnail"] for item in build_catalog("test")["browser_examples"]}
        for pixel_result in ("equal", "different"):
            browser = deepcopy(load_json(BROWSER_RESULT_PATH))
            browser["build"]["implemented"].extend(("text_layout", "text_wrapper"))
            browser["raster_comparison"]["status"] = pixel_result
            real_load = load_json
            def patched_load(path):
                return browser if path == BROWSER_RESULT_PATH else real_load(path)
            with self.subTest(pixel_result=pixel_result), patch("scripts.build_test_catalog.load_json", side_effect=patched_load):
                examples = build_catalog("test")["browser_examples"]
            for example_id in ("text_layout", "text_wrapper"):
                new_port = next(item for item in examples if item["id"] == example_id)
                with self.subTest(example=example_id):
                    self.assertEqual(new_port["status"], "unverified")
                    self.assertEqual(new_port["execution"], "unverified")
                    self.assertFalse(new_port["evidence_available"])
                    for key in ("result_url", "result_date", "changed_pixels", "total_pixels"):
                        self.assertIsNone(new_port[key], key)
                    self.assertEqual(new_port["thumbnail"], expected_previews[example_id])

    def test_browser_ports_preserve_the_full_143_row_coverage_catalog(self):
        self.assertEqual(len(self.data["cases"]) + len(self.data["native_cases"]) + len(self.data["browser_examples"]), 143)
        self.assertEqual(
            {example["id"] for example in self.data["browser_examples"] if example["implemented"]},
            {"hello_world", "text_layout", "text_wrapper", "dynamic_fonts", "hello_web"},
        )

    def test_unimplemented_examples_have_no_borrowed_results_or_routes(self):
        for example in self.data["browser_examples"]:
            if example["implemented"]:
                continue
            with self.subTest(example=example["id"]):
                self.assertEqual(example["implementation"]["label"], "gpui.mbt 未実装")
                self.assertIsNone(example["implementation"]["source_url"])
                self.assertEqual(example["status"], "unsupported")
                self.assertFalse(example["evidence_available"])
                self.assertIsNone(example["result_url"])
                self.assertIsNone(example["result_date"])
                self.assertIsNone(example["thumbnail"])
                self.assertIsNone(example["comparison_url"])

    def test_feature_metadata_describes_sources_separately_from_evidence(self):
        for example in self.data["browser_examples"]:
            with self.subTest(example=example["id"]):
                self.assertTrue(example["feature_title"])
                self.assertTrue(example["feature_tags"])
                self.assertTrue(example["source_description"])
                self.assertIn(example["source_revision"], example["source_url"])
                self.assertTrue(example["source_url"].endswith(example["source_path"]))
                self.assertTrue(example["inventory_url"].endswith("web/examples.json"))
                self.assertNotIn("MoonBit port は未実装", example["description"])

    def test_thumbnail_is_a_byte_exact_retained_screenshot(self):
        hello = next(item for item in self.data["browser_examples"] if item["id"] == "hello_world")
        thumbnail = hello["thumbnail"]
        self.assertEqual((ROOT / BROWSER_THUMBNAIL_ASSET).read_bytes(), (ROOT / BROWSER_THUMBNAIL_SOURCE).read_bytes())
        self.assertEqual(hashlib.sha256((ROOT / BROWSER_THUMBNAIL_ASSET).read_bytes()).hexdigest(), thumbnail["sha256"])
        self.assertEqual((ROOT / "catalog" / thumbnail["url"]).resolve(), ROOT / BROWSER_THUMBNAIL_ASSET)
        self.assertEqual((thumbnail["width"], thumbnail["height"]), (500, 500))
        self.assertIn(BROWSER_THUMBNAIL_SOURCE, thumbnail["source_url"])

    def test_mismatched_thumbnail_digest_fails_closed(self):
        browser = deepcopy(load_json(BROWSER_RESULT_PATH))
        browser["raster_comparison"]["sha256"]["moonbit.png"] = "different-digest"
        real_load = load_json
        def patched_load(path):
            return browser if path == BROWSER_RESULT_PATH else real_load(path)
        with patch("scripts.build_test_catalog.load_json", side_effect=patched_load):
            with self.assertRaisesRegex(ValueError, "thumbnail does not match"):
                build_catalog("test")

    def test_text_previews_match_original_captures_and_report(self):
        manifest = load_json(TEXT_CAPTURE_MANIFEST)
        report_bytes = (ROOT / manifest["result_path"]).read_bytes()
        self.assertEqual(hashlib.sha256(report_bytes).hexdigest(), manifest["result_sha256"])
        self.assertEqual(json.loads(report_bytes)["build"]["lab_revision"], manifest["source_run"]["build_revision"])
        for entry in manifest["examples"]:
            candidate = (ROOT / entry["moonbit"]["path"]).read_bytes()
            self.assertEqual(candidate, (ROOT / entry["asset_path"]).read_bytes())
            for side in ("moonbit", "rust"):
                self.assertEqual(hashlib.sha256((ROOT / entry[side]["path"]).read_bytes()).hexdigest(), entry[side]["sha256"])
        self.assertEqual({entry["id"] for entry in manifest["examples"]}, {"text_layout", "text_wrapper"})

    def test_text_preview_provenance_and_digest_mismatches_fail_closed(self):
        for problem in ("report", "image", "dimensions", "build", "asset", "duplicate"):
            manifest = deepcopy(load_json(TEXT_CAPTURE_MANIFEST))
            if problem == "report": manifest["result_sha256"] = "wrong"
            elif problem == "image": manifest["examples"][0]["rust"]["sha256"] = "wrong"
            elif problem == "dimensions": manifest["examples"][0]["moonbit"]["width"] = 1
            elif problem == "build": manifest["source_run"]["build_revision"] = "wrong"
            elif problem == "asset": manifest["examples"][0]["asset_path"] = BROWSER_THUMBNAIL_ASSET
            else: manifest["examples"].append(deepcopy(manifest["examples"][0]))
            real_load = load_json
            def patched_load(path):
                return manifest if path == TEXT_CAPTURE_MANIFEST else real_load(path)
            with self.subTest(problem=problem), patch("scripts.build_test_catalog.load_json", side_effect=patched_load):
                with self.assertRaises(ValueError): build_catalog("test")

    def test_prime_preview_is_byte_exact_and_validated_independently(self):
        manifest = load_json(PRIME_CAPTURE_MANIFEST)
        entry = manifest["example"]
        self.assertEqual((ROOT / entry["asset_path"]).read_bytes(), (ROOT / entry["moonbit"]["path"]).read_bytes())
        self.assertEqual(manifest["source_run"]["head_revision"], "faab43b9b9ee73fc8e1f0b6864b4cf9083c44877")
        for problem in ("report", "scene", "ocr", "image", "dimensions", "build", "asset", "source", "run"):
            changed = deepcopy(manifest)
            if problem in ("report", "scene", "ocr"):
                changed[("result" if problem == "report" else problem) + "_sha256"] = "wrong"
            elif problem == "image": changed["example"]["rust"]["sha256"] = "wrong"
            elif problem == "dimensions": changed["example"]["moonbit"]["width"] = 800
            elif problem == "build": changed["source_run"]["build_revision"] = "wrong"
            elif problem == "asset": changed["example"]["asset_path"] = BROWSER_THUMBNAIL_ASSET
            elif problem == "source": changed["example"]["id"] = "hello_world"
            else: changed["source_run"]["url"] = "https://example.invalid/"
            real_load = load_json
            def patched_load(path):
                return changed if path == PRIME_CAPTURE_MANIFEST else real_load(path)
            with self.subTest(problem=problem), patch("scripts.build_test_catalog.load_json", side_effect=patched_load):
                with self.assertRaises(ValueError): build_catalog("test")

    def test_gallery_preserves_full_coverage_catalog_and_labels_missing_previews(self):
        html = (ROOT / "catalog/index.html").read_text()
        script = (ROOT / "catalog/app.js").read_text()
        for section in ("example-list", "case-list", "overview-title", "sources-title"):
            self.assertIn(f'id="{section}"', html)
        self.assertIn("保存画像なし", script)
        self.assertIn("gpui.mbt 未実装", script)
        self.assertNotIn("MoonBit port は未実装", script)
        self.assertNotIn("result_url: item.implemented ? data.browser.result_url", script)
        self.assertNotIn("result_date: item.implemented ? data.browser.result_date", script)

    def test_native_status_is_not_carried_forward_across_candidate_pins(self):
        data = self.data
        self.assertEqual(data["native"]["current_status"], "unverified")
        self.assertEqual(data["native"]["historical_counts"]["pass"], 2)
        self.assertNotEqual(data["native"]["current_candidate_revision"], data["native"]["historical_candidate_revision"])
        self.assertEqual(data["native_ax"]["status"], "unverified")
        self.assertEqual(len(data["native_cases"]), 2)
        self.assertTrue(all(case["status"] == "unverified" for case in data["native_cases"]))

    def test_generated_document_contains_one_coherent_release(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            write_site(self.data, output)
            html = (output / "index.html").read_text()
            self.assertNotIn('src="./app.js"', html)
            self.assertNotIn('href="./style.css"', html)
            self.assertIn('<meta name="catalog-release"', html)
            self.assertIn((ROOT / "catalog/app.js").read_text(), html)
            self.assertIn((ROOT / "catalog/style.css").read_text(), html)
            self.assertEqual(json.loads((output / "data.json").read_text()), self.data)
            self.assertEqual((output / "app.js").read_bytes(), (ROOT / "catalog/app.js").read_bytes())
            self.assertEqual((output / "assets/hello_world-moonbit-20261016.png").read_bytes(), (ROOT / BROWSER_THUMBNAIL_ASSET).read_bytes())

    def test_embedded_json_cannot_escape_its_inert_script_element(self):
        class Scripts(HTMLParser):
            def __init__(self):
                super().__init__()
                self.scripts = []
                self.active = None
            def handle_starttag(self, tag, attrs):
                if tag == "script":
                    self.active = {"attrs": dict(attrs), "text": ""}
                    self.scripts.append(self.active)
            def handle_data(self, data):
                if self.active is not None:
                    self.active["text"] += data
            def handle_endtag(self, tag):
                if tag == "script":
                    self.active = None
        data = deepcopy(self.data)
        data["scope_note"] = '</script><script>alert("unexpected")</script><p>& 日本語'
        with tempfile.TemporaryDirectory() as directory:
            write_site(data, Path(directory))
            parser = Scripts()
            parser.feed((Path(directory) / "index.html").read_text())
            self.assertEqual(len(parser.scripts), 2)
            embedded = parser.scripts[0]
            self.assertEqual(embedded["attrs"], {"id": "catalog-data", "type": "application/json"})
            self.assertEqual(json.loads(embedded["text"]), data)

    def test_site_generation_does_not_overwrite_source_templates(self):
        with self.assertRaisesRegex(ValueError, "source templates"):
            write_site(self.data, ROOT / "catalog")
        with self.assertRaisesRegex(ValueError, "source templates"):
            write_site(self.data, ROOT / "catalog/generated")


if __name__ == "__main__":
    unittest.main()
