import unittest
import os
import hashlib

from copy import deepcopy
from unittest.mock import patch

from scripts.build_test_catalog import (
    BROWSER_LAB_BASE_URL_ENV,
    BROWSER_RESULT_PATH,
    BROWSER_THUMBNAIL_ASSET,
    BROWSER_THUMBNAIL_SOURCE,
    ROOT,
    browser_lab_comparison_url,
    build_catalog,
    load_json,
    normalize_browser_lab_base_url,
    pixel_status,
    validate_browser_inventory,
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
        self.assertEqual(sum(example["status"] == "unsupported" for example in examples), 5)
        self.assertEqual(sum(example["status"] == "unverified" for example in examples), 1)
        self.assertFalse(any(example["interactive"] for example in examples if example["implemented"]))
        self.assertTrue(all(example["comparison_url"] is None for example in examples))

    def test_verified_base_url_links_only_supported_implemented_examples(self):
        base_url = "https://gpui-conformance-browser-lab.account-name.workers.dev"
        with patch.dict(os.environ, {BROWSER_LAB_BASE_URL_ENV: base_url}):
            examples = build_catalog("catalog-test-revision")["browser_examples"]

        hello_world = next(example for example in examples if example["id"] == "hello_world")
        self.assertEqual(hello_world["comparison_url"], f"{base_url}/?example=hello_world")
        self.assertFalse(hello_world["interactive"])
        text_layout = next(example for example in examples if example["id"] == "text_layout")
        self.assertEqual(text_layout["comparison_url"], f"{base_url}/?example=text_layout")
        self.assertFalse(text_layout["interactive"])
        self.assertTrue(all(
            example["comparison_url"] is None
            for example in examples
            if example["id"] not in {"hello_world", "text_layout"}
        ))

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
        next(item for item in inventory["examples"] if item["id"] == "text_layout")["moonbit"] = "implemented"
        validate_browser_inventory(browser, inventory)

    def test_duplicate_browser_ids_are_rejected(self):
        inventory = deepcopy(load_json("web/examples.json"))
        inventory["examples"].append(deepcopy(inventory["examples"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate browser example IDs"):
            validate_browser_inventory(load_json(BROWSER_RESULT_PATH), inventory)

    def test_new_port_does_not_inherit_retained_result_or_preview(self):
        examples = {example["id"]: example for example in self.data["browser_examples"]}
        hello = examples["hello_world"]
        new_port = examples["text_layout"]
        self.assertTrue(new_port["implemented"])
        self.assertEqual(new_port["implementation"]["status"], "implemented")
        self.assertIn("/web/moonbit/text_layout/text_layout.mbt", new_port["implementation"]["source_url"])
        self.assertEqual(new_port["status"], "unverified")
        self.assertEqual(new_port["execution"], "unverified")
        self.assertFalse(new_port["evidence_available"])
        for key in ("result_url", "result_date", "changed_pixels", "total_pixels", "thumbnail"):
            self.assertIsNone(new_port[key], key)
        self.assertTrue(hello["evidence_available"])
        self.assertEqual(hello["status"], "difference")
        self.assertEqual(hello["execution"], "passed")
        self.assertEqual(hello["changed_pixels"], 1532)
        self.assertIn(BROWSER_RESULT_PATH, hello["result_url"])
        self.assertEqual(self.data["browser"]["example_id"], "hello_world")
        self.assertEqual(self.data["browser"]["implemented_count"], 2)
        self.assertEqual(self.data["browser"]["evidence_count"], 1)

    def test_build_capability_is_not_per_example_measurement(self):
        # Even a build that contains two ports cannot give the second port the
        # legacy file's single hello_world comparison, for either equal or different.
        for pixel_result in ("equal", "different"):
            browser = deepcopy(load_json(BROWSER_RESULT_PATH))
            browser["build"]["implemented"].append("text_layout")
            browser["raster_comparison"]["status"] = pixel_result
            real_load = load_json
            def patched_load(path):
                return browser if path == BROWSER_RESULT_PATH else real_load(path)
            with self.subTest(pixel_result=pixel_result), patch("scripts.build_test_catalog.load_json", side_effect=patched_load):
                examples = build_catalog("test")["browser_examples"]
            new_port = next(item for item in examples if item["id"] == "text_layout")
            self.assertEqual(new_port["status"], "unverified")
            self.assertIsNone(new_port["result_url"])
            self.assertIsNone(new_port["thumbnail"])
            self.assertIsNone(new_port["changed_pixels"])

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


if __name__ == "__main__":
    unittest.main()
