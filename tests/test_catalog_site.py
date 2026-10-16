import unittest
import os

from copy import deepcopy
from unittest.mock import patch

from scripts.build_test_catalog import (
    BROWSER_LAB_BASE_URL_ENV,
    BROWSER_RESULT_PATH,
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
        self.assertEqual(sum(example["status"] == "unsupported" for example in examples), 6)
        self.assertTrue(all(example["comparison_url"] is None for example in examples))

    def test_verified_base_url_links_only_the_implemented_static_hello_world_example(self):
        base_url = "https://gpui-conformance-browser-lab.account-name.workers.dev"
        with patch.dict(os.environ, {BROWSER_LAB_BASE_URL_ENV: base_url}):
            examples = build_catalog("catalog-test-revision")["browser_examples"]

        hello_world = next(example for example in examples if example["id"] == "hello_world")
        self.assertEqual(hello_world["comparison_url"], f"{base_url}/?example=hello_world")
        self.assertFalse(hello_world["interactive"])
        self.assertTrue(all(
            example["comparison_url"] is None
            for example in examples
            if example["id"] != "hello_world"
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

    def test_browser_inventory_must_match_retained_build_provenance(self):
        browser = load_json(BROWSER_RESULT_PATH)
        inventory = load_json("web/examples.json")
        validate_browser_inventory(browser, inventory)

        changed_pin = deepcopy(inventory)
        changed_pin["moonbit"]["revision"] = "changed"
        with self.assertRaisesRegex(ValueError, "moonbit pin"):
            validate_browser_inventory(browser, changed_pin)

        changed_implementation = deepcopy(inventory)
        changed_implementation["examples"][0]["moonbit"] = "not_implemented"
        with self.assertRaisesRegex(ValueError, "implemented browser examples"):
            validate_browser_inventory(browser, changed_implementation)

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
