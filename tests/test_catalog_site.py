import unittest
import re
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
    TEXT_RESULT_PATH,
    PRIME_RESULT_PATH,
    RETAINED_BROWSER_PINS,
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

    def test_catalog_ci_isolates_prs_and_serializes_deployments(self):
        workflow = (ROOT / ".github/workflows/catalog-pages.yml").read_text()
        self.assertIn(
            "group: ${{ github.event_name == 'pull_request' && "
            "format('catalog-pr-{0}', github.event.pull_request.number) || 'catalog-pages' }}",
            workflow,
        )
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertIn("if: github.event_name == 'push' || (github.event_name == 'workflow_dispatch' "
                      "&& github.ref == 'refs/heads/main')", workflow)

    def test_example_catalog_does_not_fabricate_interactive_routes(self):
        examples = self.data["browser_examples"]
        self.assertEqual(len(examples), 18)
        self.assertEqual(examples[0]["status"], "difference")
        self.assertEqual(sum(example["status"] == "unsupported" for example in examples), 0)
        self.assertEqual(sum(example["status"] == "unverified" for example in examples), 17)
        self.assertEqual([example["id"] for example in examples if example["implemented"] and example["interactive"]], ["text", "input", "hello_web", "scrollable", "focus_visible", "tab_stop", "drag_drop", "uniform_list", "grid_layout", "anchor", "gradient", "popover"])
        self.assertTrue(all(example["comparison_url"] is None for example in examples))

    def test_browser_unverified_count_matches_both_browser_assertions(self):
        # Run without Chromium: the CI assertion and filtered row count must use
        # one explicit expectation matching the generated catalog, not stale
        # literals that only fail after a browser launches.
        source = (ROOT / "tests/catalog-browser.mjs").read_text()
        counts = re.findall(r"const expectedUnverifiedExamples = (\d+);", source)
        self.assertEqual(len(counts), 1)
        actual = sum(item["status"] == "unverified" for item in self.data["browser_examples"])
        self.assertEqual(int(counts[0]), actual)
        self.assertIn("filter(example => example.status === 'unverified').length, expectedUnverifiedExamples)", source)
        self.assertIn("await assertCount(visibleCases, expectedUnverifiedExamples);", source)
        self.assertNotRegex(source, r"filter\(example => example.status === 'unverified'\)\.length, \d+")

    def test_anchor_card_is_bounded_unverified_without_borrowed_evidence(self):
        base = "https://gpui-conformance-browser-lab.account-name.workers.dev"
        with patch.dict(os.environ, {BROWSER_LAB_BASE_URL_ENV: base}):
            anchor = next(item for item in build_catalog("anchor-card-contract")["browser_examples"] if item["id"] == "anchor")
        self.assertTrue(anchor["implemented"])
        self.assertTrue(anchor["interactive"])
        self.assertEqual((anchor["width"], anchor["height"]), (750, 600))
        self.assertEqual(anchor["source_path"], "crates/gpui/examples/anchor.rs")
        self.assertEqual(anchor["comparison_url"], f"{base}/?example=anchor")
        self.assertEqual(anchor["status"], "unverified")
        self.assertEqual(anchor["execution"], "unverified")
        self.assertFalse(anchor["evidence_available"])
        for key in ("result_url", "result_date", "changed_pixels", "total_pixels", "thumbnail", "evidence_scope"):
            self.assertIsNone(anchor[key], key)
        self.assertIn("widths 750 and 480, height 600, DPR1", anchor["implementation"]["note"])
        self.assertIn("remain unverified", anchor["implementation"]["note"])

    def test_gradient_card_is_bounded_unverified_without_borrowed_evidence(self):
        base = "https://gpui-conformance-browser-lab.account-name.workers.dev"
        with patch.dict(os.environ, {BROWSER_LAB_BASE_URL_ENV: base}):
            entry = next(item for item in build_catalog("gradient-card-contract")["browser_examples"] if item["id"] == "gradient")
        self.assertTrue(entry["implemented"])
        self.assertTrue(entry["interactive"])
        self.assertEqual((entry["width"], entry["height"]), (960, 600))
        self.assertEqual(entry["comparison_url"], f"{base}/?example=gradient")
        self.assertEqual(entry["status"], "unverified")
        self.assertEqual(entry["execution"], "unverified")
        self.assertFalse(entry["evidence_available"])
        for key in ("result_url", "result_date", "changed_pixels", "total_pixels", "thumbnail", "evidence_scope"):
            self.assertIsNone(entry[key], key)
        self.assertIn("960×600 and 600×960, DPR1", entry["implementation"]["note"])
        self.assertIn("remain unverified", entry["implementation"]["note"])

    def test_popover_card_has_own_sources_and_no_borrowed_evidence(self):
        inventory = load_json("web/examples.json")
        entry = next(item for item in inventory["examples"] if item["id"] == "popover")
        self.assertEqual(entry["source_blob"], "7678a6a3ed865d9874b72cb99b473a115591d35c")
        self.assertEqual(entry["rust_route"], "popover")
        self.assertEqual(entry["candidate_source"], "web/moonbit/popover/popover.mbt")
        base = "https://gpui-conformance-browser-lab.account-name.workers.dev"
        with patch.dict(os.environ, {BROWSER_LAB_BASE_URL_ENV: base}):
            port = next(item for item in build_catalog("popover-card-contract")["browser_examples"] if item["id"] == "popover")
        self.assertTrue(port["implemented"])
        self.assertEqual(port["implementation"]["status"], "implemented")
        self.assertEqual((port["width"], port["height"], port["interactive"]), (800, 600, True))
        self.assertEqual(port["source_path"], "crates/gpui/examples/popover.rs")
        self.assertEqual(port["source_revision"], "5a5fbe79917971a4d52a96b6ddb04da198a5012e")
        self.assertEqual(port["source_url"], "https://github.com/zed-industries/zed/blob/"
                         "5a5fbe79917971a4d52a96b6ddb04da198a5012e/crates/gpui/examples/popover.rs")
        self.assertEqual(port["implementation"]["source_url"], "https://github.com/gpui-mbt/gpui-conformance/blob/"
                         "popover-card-contract/web/moonbit/popover/popover.mbt")
        self.assertEqual(port["comparison_url"], f"{base}/?example=popover")
        self.assertEqual(port["suite_type"], "browser")
        self.assertIn("popover", port["feature_tags"])
        self.assertEqual(port["source_features"], entry["features"])
        self.assertEqual(port["status"], "unverified")
        self.assertEqual(port["execution"], "unverified")
        self.assertFalse(port["evidence_available"])
        for key in ("result_url", "result_date", "changed_pixels", "total_pixels", "thumbnail", "evidence_scope"):
            self.assertIsNone(port[key], key)
        for boundary in ("genuine core Element", "deferred priorities", "anchored placement",
                         "outside-pointer routing", "MoonBit owns wrapping", "explicit approximations",
                         "Paired browser, native, text, shadow, full-image and callback-count parity remain unverified"):
            self.assertIn(boundary, port["implementation"]["note"])
        self.assertIsNone(browser_lab_comparison_url("popover", True, None))
        self.assertIsNone(browser_lab_comparison_url("popover", False, base))

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
            if example["id"] not in {"hello_world", "text", "text_layout", "text_wrapper", "input", "dynamic_fonts", "hello_web", "tree", "scrollable", "focus_visible", "tab_stop", "drag_drop", "uniform_list", "grid_layout", "anchor", "gradient", "popover", "pattern"}
        ))

    def test_typography_is_interactive_without_inheriting_hello_world_evidence(self):
        base = "https://gpui-conformance-browser-lab.account-name.workers.dev"
        with patch.dict(os.environ, {BROWSER_LAB_BASE_URL_ENV: base}):
            text = next(e for e in build_catalog("catalog-test-revision")["browser_examples"] if e["id"] == "text")
        self.assertTrue(text["implemented"])
        self.assertEqual((text["width"], text["height"], text["interactive"]), (920, 720, True))
        self.assertEqual(text["comparison_url"], f"{base}/?example=text")
        self.assertEqual(text["source_path"], "crates/gpui/examples/text.rs")
        self.assertEqual(text["implementation"]["source_url"],
                         "https://github.com/gpui-mbt/gpui-conformance/blob/catalog-test-revision/web/moonbit/text/text.mbt")
        self.assertEqual(text["status"], "unverified")
        self.assertEqual(text["execution"], "unverified")
        self.assertFalse(text["evidence_available"])
        for key in ("result_url", "result_date", "changed_pixels", "total_pixels", "thumbnail"):
            self.assertIsNone(text[key], key)

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

    def test_scrollable_is_interactive_without_borrowed_evidence(self):
        base = "https://gpui-conformance-browser-lab.account-name.workers.dev"
        with patch.dict(os.environ, {BROWSER_LAB_BASE_URL_ENV: base}):
            port = next(e for e in build_catalog("catalog-test-revision")["browser_examples"] if e["id"] == "scrollable")
        self.assertTrue(port["implemented"])
        self.assertEqual((port["width"], port["height"], port["interactive"]), (500, 500, True))
        self.assertEqual(port["comparison_url"], f"{base}/?example=scrollable")
        self.assertEqual(port["source_path"], "crates/gpui/examples/scrollable.rs")
        self.assertTrue(port["implementation"]["source_url"].endswith("/web/moonbit/scrollable/scrollable.mbt"))
        self.assertEqual(port["status"], "unverified")
        self.assertEqual(port["execution"], "unverified")
        self.assertFalse(port["evidence_available"])
        for key in ("result_url", "result_date", "changed_pixels", "total_pixels", "thumbnail", "evidence_scope"):
            self.assertIsNone(port[key], key)

    def test_focus_visible_has_pinned_sources_and_no_borrowed_result_or_preview(self):
        inventory = load_json("web/examples.json")
        entry = next(example for example in inventory["examples"] if example["id"] == "focus_visible")
        self.assertEqual(entry["title"], "Focus-visible")
        self.assertEqual(entry["rust_route"], "focus-visible")
        self.assertEqual(entry["source_blob"], "c5b3d5dfec3a189d088a621baff55eb55a121b6c")
        self.assertEqual(entry["candidate_source"], "web/moonbit/focus_visible/focus_visible.mbt")
        base = "https://gpui-conformance-browser-lab.account-name.workers.dev"
        with patch.dict(os.environ, {BROWSER_LAB_BASE_URL_ENV: base}):
            port = next(e for e in build_catalog("catalog-test-revision")["browser_examples"] if e["id"] == "focus_visible")
        self.assertTrue(port["implemented"])
        self.assertEqual(port["implementation"]["status"], "implemented")
        self.assertEqual((port["width"], port["height"], port["interactive"]), (800, 600, True))
        self.assertEqual(port["comparison_url"], f"{base}/?example=focus_visible")
        self.assertEqual(port["source_path"], "crates/gpui/examples/focus_visible.rs")
        self.assertEqual(port["source_url"], "https://github.com/zed-industries/zed/blob/"
                         "5a5fbe79917971a4d52a96b6ddb04da198a5012e/crates/gpui/examples/focus_visible.rs")
        self.assertEqual(port["implementation"]["source_url"], "https://github.com/gpui-mbt/gpui-conformance/blob/"
                         "catalog-test-revision/web/moonbit/focus_visible/focus_visible.mbt")
        self.assertEqual(port["status"], "unverified")
        self.assertEqual(port["execution"], "unverified")
        self.assertFalse(port["evidence_available"])
        self.assertEqual(port["suite_type"], "browser")
        self.assertIn("focus-visible", port["feature_tags"])
        for boundary in ("persistent input tree", "core flat tab traversal", "focus ownership", "host boundaries",
                         "paired browser execution", "Nested tab groups", "touch", "pointer capture", "native", "full-image", "text parity"):
            self.assertIn(boundary, port["implementation"]["note"])
        for key in ("result_url", "result_date", "changed_pixels", "total_pixels", "thumbnail", "evidence_scope"):
            self.assertIsNone(port[key], key)
        self.assertIsNone(browser_lab_comparison_url("focus_visible", True, None))
        self.assertIsNone(browser_lab_comparison_url("focus_visible", False, base))
        self.assertIsNone(browser_lab_comparison_url("focus-visible", True, base))

    def test_tab_stop_candidate_has_no_borrowed_measurements_or_preview(self):
        inventory = load_json("web/examples.json")
        entry = next(example for example in inventory["examples"] if example["id"] == "tab_stop")
        self.assertEqual(entry["rust_route"], "tab-stop")
        self.assertEqual(entry["source_blob"], "cc7c34a9979ce4027578ec2c358f503d944ee26f")
        self.assertEqual(entry["candidate_source"], "web/moonbit/tab_stop/tab_stop.mbt")
        base = "https://gpui-conformance-browser-lab.account.workers.dev"
        with patch.dict(os.environ, {BROWSER_LAB_BASE_URL_ENV: base}):
            port = next(example for example in build_catalog("tab-stop-source-contract")["browser_examples"] if example["id"] == "tab_stop")
        self.assertTrue(port["implemented"])
        self.assertEqual(port["implementation"]["status"], "implemented")
        self.assertEqual(port["source_path"], "crates/gpui/examples/tab_stop.rs")
        self.assertEqual(port["source_revision"], "5a5fbe79917971a4d52a96b6ddb04da198a5012e")
        self.assertEqual(port["source_url"], "https://github.com/zed-industries/zed/blob/"
                         "5a5fbe79917971a4d52a96b6ddb04da198a5012e/crates/gpui/examples/tab_stop.rs")
        self.assertEqual(port["implementation"]["source_url"], "https://github.com/gpui-mbt/gpui-conformance/blob/"
                         "tab-stop-source-contract/web/moonbit/tab_stop/tab_stop.mbt")
        self.assertEqual((port["width"], port["height"], port["interactive"]), (800, 600, True))
        self.assertEqual(port["status"], "unverified")
        self.assertEqual(port["execution"], "unverified")
        self.assertFalse(port["evidence_available"])
        self.assertEqual(port["comparison_url"], f"{base}/?example=tab_stop")
        self.assertEqual(port["suite_type"], "browser")
        self.assertIn("tab stop", port["feature_tags"])
        self.assertEqual(port["source_features"], entry["features"])
        for boundary in ("Source-derived candidate", "core group-prefix traversal", "host extensions",
                         "Paired browser execution", "native", "GPU shadow-kernel", "text", "full-image parity remain unverified"):
            self.assertIn(boundary, port["implementation"]["note"])
        for key in ("result_url", "result_date", "changed_pixels", "total_pixels", "thumbnail", "evidence_scope"):
            self.assertIsNone(port[key], key)
        self.assertIsNone(browser_lab_comparison_url("tab_stop", True, None))
        self.assertIsNone(browser_lab_comparison_url("tab_stop", False, base))
        self.assertIsNone(browser_lab_comparison_url("tab-stop", True, base))

    def test_drag_drop_candidate_has_no_borrowed_measurements_or_preview(self):
        inventory = load_json("web/examples.json")
        entry = next(example for example in inventory["examples"] if example["id"] == "drag_drop")
        self.assertEqual(entry["rust_route"], "drag-drop")
        self.assertEqual(entry["source_blob"], "8f038ef3308fee9b097e7289665c9fa47cd6945b")
        self.assertEqual(entry["candidate_source"], "web/moonbit/drag_drop/drag_drop.mbt")
        base = "https://gpui-conformance-browser-lab.account.workers.dev"
        with patch.dict(os.environ, {BROWSER_LAB_BASE_URL_ENV: base}):
            port = next(example for example in build_catalog("drag-drop-source-contract")["browser_examples"] if example["id"] == "drag_drop")
        self.assertTrue(port["implemented"])
        self.assertEqual(port["implementation"]["status"], "implemented")
        self.assertEqual(port["source_path"], "crates/gpui/examples/drag_drop.rs")
        self.assertEqual(port["source_revision"], "5a5fbe79917971a4d52a96b6ddb04da198a5012e")
        self.assertEqual(port["source_url"], "https://github.com/zed-industries/zed/blob/"
                         "5a5fbe79917971a4d52a96b6ddb04da198a5012e/crates/gpui/examples/drag_drop.rs")
        self.assertEqual(port["implementation"]["source_url"], "https://github.com/gpui-mbt/gpui-conformance/blob/"
                         "drag-drop-source-contract/web/moonbit/drag_drop/drag_drop.mbt")
        self.assertEqual((port["width"], port["height"], port["interactive"]), (800, 600, True))
        self.assertEqual(port["status"], "unverified")
        self.assertEqual(port["execution"], "unverified")
        self.assertFalse(port["evidence_available"])
        self.assertEqual(port["comparison_url"], f"{base}/?example=drag_drop")
        self.assertEqual(port["suite_type"], "browser")
        self.assertIn("drag session", port["feature_tags"])
        self.assertEqual(port["source_features"], entry["features"])
        for boundary in ("Source-derived candidate", "typed core DragSession", "host boundaries",
                         "Paired browser execution", "native", "GPU shadow-kernel", "text", "full-image parity remain unverified"):
            self.assertIn(boundary, port["implementation"]["note"])
        for key in ("result_url", "result_date", "changed_pixels", "total_pixels", "thumbnail", "evidence_scope"):
            self.assertIsNone(port[key], key)
        self.assertIsNone(browser_lab_comparison_url("drag_drop", True, None))
        self.assertIsNone(browser_lab_comparison_url("drag_drop", False, base))
        self.assertIsNone(browser_lab_comparison_url("drag-drop", True, base))

    def test_uniform_list_exposes_typography_limit_without_borrowed_evidence(self):
        inventory = load_json("web/examples.json")
        entry = next(example for example in inventory["examples"] if example["id"] == "uniform_list")
        self.assertEqual(entry["rust_route"], "uniform-list")
        self.assertEqual(entry["source_blob"], "4a2c4788b192d802ee3d51714c250e7c5a82db76")
        self.assertEqual(entry["candidate_source"], "web/moonbit/uniform_list/uniform_list.mbt")
        base = "https://gpui-conformance-browser-lab.account.workers.dev"
        with patch.dict(os.environ, {BROWSER_LAB_BASE_URL_ENV: base}):
            port = next(example for example in build_catalog("uniform-source-contract")["browser_examples"] if example["id"] == "uniform_list")
        self.assertTrue(port["implemented"])
        self.assertEqual((port["width"], port["height"], port["interactive"]), (300, 300, True))
        self.assertEqual(port["source_path"], "crates/gpui/examples/uniform_list.rs")
        self.assertEqual(port["status"], "unverified")
        self.assertEqual(port["execution"], "unverified")
        self.assertFalse(port["evidence_available"])
        self.assertEqual(port["comparison_url"], f"{base}/?example=uniform_list")
        for boundary in ("genuine core UniformList", "host boundaries", "Strict text-envelope", "Item 3",
                         "right-edge", "not a passed full-text", "placement/scroll/clip", "font-free GPUI diagnostic",
                         "full-image parity remain unverified"):
            self.assertIn(boundary, port["implementation"]["note"])
        self.assertIn("文字の右端", port["source_description"])
        for key in ("result_url", "result_date", "changed_pixels", "total_pixels", "thumbnail", "evidence_scope"):
            self.assertIsNone(port[key], key)
        self.assertIsNone(browser_lab_comparison_url("uniform_list", True, None))
        self.assertIsNone(browser_lab_comparison_url("uniform_list", False, base))
        self.assertIsNone(browser_lab_comparison_url("uniform-list", True, base))

    def test_grid_layout_has_bounded_profile_metadata_without_borrowed_evidence(self):
        inventory = load_json("web/examples.json")
        entry = next(example for example in inventory["examples"] if example["id"] == "grid_layout")
        self.assertEqual(entry["source_blob"], "51f9b13e41fb7913c653d716da3e8ce05a96109d")
        self.assertEqual(entry["candidate_source"], "web/moonbit/grid_layout/grid_layout.mbt")
        base = "https://gpui-conformance-browser-lab.account.workers.dev"
        with patch.dict(os.environ, {BROWSER_LAB_BASE_URL_ENV: base}):
            port = next(example for example in build_catalog("grid-source-contract")["browser_examples"] if example["id"] == "grid_layout")
        self.assertTrue(port["implemented"])
        self.assertEqual(port["implementation"]["status"], "implemented")
        self.assertEqual((port["width"], port["height"], port["interactive"]), (500, 500, True))
        self.assertEqual(port["source_path"], "crates/gpui/examples/grid_layout.rs")
        self.assertEqual(port["comparison_url"], f"{base}/?example=grid_layout")
        self.assertTrue(port["implementation"]["source_url"].endswith("/web/moonbit/grid_layout/grid_layout.mbt"))
        self.assertIn("container query", port["feature_tags"])
        self.assertEqual(port["source_features"], entry["features"])
        self.assertIn("399/400/401/500px", port["source_description"])
        for boundary in ("genuine core container_query_root", "224px", "DPR 1", "two host layout passes", "not Rust callback-count parity", "remain unverified"):
            self.assertIn(boundary, port["implementation"]["note"])
        self.assertEqual(port["status"], "unverified")
        self.assertEqual(port["execution"], "unverified")
        self.assertFalse(port["evidence_available"])
        for key in ("result_url", "result_date", "changed_pixels", "total_pixels", "thumbnail", "evidence_scope"):
            self.assertIsNone(port[key], key)
        self.assertIsNone(browser_lab_comparison_url("grid_layout", True, None))
        self.assertIsNone(browser_lab_comparison_url("grid_layout", False, base))
        self.assertIsNone(browser_lab_comparison_url("grid-layout", True, base))

    def test_pattern_is_source_bound_and_cannot_borrow_retained_pixels(self):
        inventory = load_json("web/examples.json")
        entry = next(item for item in inventory["examples"] if item["id"] == "pattern")
        port = next(item for item in self.data["browser_examples"] if item["id"] == "pattern")
        self.assertEqual(entry["source_blob"], "7d2e98d16e24dc23dc307296a3b35c18e624d9e3")
        self.assertEqual((entry["width"], entry["height"]), (600, 600))
        self.assertFalse(entry["interactive"])
        self.assertEqual(port["status"], "unverified")
        self.assertEqual(port["execution"], "unverified")
        self.assertFalse(port["evidence_available"])
        for key in ("result_url", "result_date", "changed_pixels", "thumbnail"):
            self.assertIsNone(port[key])
        self.assertIn("core SlashPattern", entry["implementation_note"])

    def test_current_browser_pin_and_sixteen_core_two_web_classifications(self):
        inventory = load_json("web/examples.json")
        self.assertEqual(inventory["upstream"]["revision"], "5a5fbe79917971a4d52a96b6ddb04da198a5012e")
        self.assertEqual(inventory["moonbit"]["revision"], "3bea4fea2dd54768a3859c7c881dda2a60fa5bbd")
        self.assertEqual(inventory["moonbit"]["tree"], "25b0647f974d8b6ffd46c1a15c7eeb5ef7e4fe85")
        self.assertEqual(len(inventory["examples"]), 18)
        self.assertEqual(sum(e["source"].startswith("crates/gpui/examples/") for e in inventory["examples"]), 16)
        self.assertEqual({e["id"] for e in inventory["examples"] if e["source"].startswith("crates/gpui/examples/")},
                         {"hello_world", "text", "text_layout", "text_wrapper", "input", "tree", "scrollable", "focus_visible", "tab_stop", "drag_drop", "uniform_list", "grid_layout", "anchor", "gradient", "popover", "pattern"})
        self.assertEqual(sum(e["source"].startswith("crates/gpui_web/examples/") for e in inventory["examples"]), 2)
        self.assertEqual({e["id"] for e in inventory["examples"] if e["source"].startswith("crates/gpui_web/examples/")},
                         {"dynamic_fonts", "hello_web"})
        self.assertEqual([e["source_path"] for e in self.data["browser_examples"]],
                         [e["source"] for e in inventory["examples"]])
        self.assertEqual(self.data["browser"]["current_pins"][1]["tree"], inventory["moonbit"]["tree"])
        self.assertTrue(all("tree" not in pin for pin in self.data["browser"]["pins"]))

    def test_unmeasured_interactive_ports_cannot_relabel_a_retained_capture(self):
        real_load = load_json
        for example_id in ("focus_visible", "tab_stop", "drag_drop", "uniform_list", "grid_layout", "anchor", "gradient", "popover", "pattern"):
            for path in (TEXT_CAPTURE_MANIFEST, PRIME_CAPTURE_MANIFEST):
                manifest = deepcopy(load_json(path))
                if path == TEXT_CAPTURE_MANIFEST:
                    manifest["examples"][0]["id"] = example_id
                else:
                    manifest["example"]["id"] = example_id
                with self.subTest(example=example_id, path=path), patch(
                    "scripts.build_test_catalog.load_json",
                    side_effect=lambda source: manifest if source == path else real_load(source),
                ):
                    with self.assertRaises(ValueError):
                        build_catalog("forged-unmeasured-capture")

    def test_unmeasured_port_inventory_claims_cannot_supply_measurement_provenance(self):
        real_load = load_json
        for example_id in ("focus_visible", "tab_stop", "drag_drop", "uniform_list", "grid_layout", "anchor", "gradient", "popover", "pattern"):
            inventory = deepcopy(load_json("web/examples.json"))
            entry = next(example for example in inventory["examples"] if example["id"] == example_id)
            entry.update(status="pass", execution="passed", evidence_available=True,
                         result_url=BROWSER_RESULT_PATH, changed_pixels=0,
                         thumbnail={"url": BROWSER_THUMBNAIL_ASSET}, evidence_scope="current")
            with self.subTest(example=example_id), patch(
                "scripts.build_test_catalog.load_json",
                side_effect=lambda path: inventory if path == "web/examples.json" else real_load(path),
            ):
                port = next(e for e in build_catalog("forged-inventory-claim")["browser_examples"] if e["id"] == example_id)
                self.assertEqual(port["status"], "unverified")
                self.assertEqual(port["execution"], "unverified")
                self.assertFalse(port["evidence_available"])
                for key in ("result_url", "result_date", "changed_pixels", "total_pixels", "thumbnail", "evidence_scope"):
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
        self.assertIsNone(browser_lab_comparison_url("input", False, "https://gpui-conformance-browser-lab.account.workers.dev"))
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

    def test_browser_inventory_pins_must_be_valid_and_keep_measured_ports(self):
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

        for tree in (None, "", "main", "a" * 39, "A" * 40):
            changed_pin = deepcopy(inventory)
            changed_pin["moonbit"]["tree"] = tree
            with self.subTest(tree=tree), self.assertRaisesRegex(ValueError, "moonbit tree pin"):
                validate_browser_inventory(browser, changed_pin)

        changed_implementation = deepcopy(inventory)
        changed_implementation["examples"][0]["moonbit"] = "not_implemented"
        with self.assertRaisesRegex(ValueError, "implemented browser examples"):
            validate_browser_inventory(browser, changed_implementation)

    def test_current_inventory_and_retained_evidence_have_separate_pin_provenance(self):
        inventory = load_json("web/examples.json")
        browser = self.data["browser"]
        self.assertEqual([pin["revision"] for pin in browser["pins"]],
                         [RETAINED_BROWSER_PINS[kind]["revision"] for kind in ("upstream", "moonbit")])
        self.assertEqual([pin["revision"] for pin in browser["current_pins"]],
                         [inventory[kind]["revision"] for kind in ("upstream", "moonbit")])
        self.assertFalse(browser["pins_match_current_inventory"])
        self.assertEqual(browser["current_status"], "unverified")
        self.assertTrue(browser["inventory_url"].endswith("/web/examples.json"))
        previews = [example["thumbnail"] for example in self.data["browser_examples"] if example["thumbnail"]]
        self.assertEqual(len(previews), 4)
        for preview in previews:
            self.assertEqual(preview["pins"], browser["pins"])
            self.assertFalse(preview["pins_match_current_inventory"])
            for pin in preview["pins"]:
                self.assertTrue(pin["url"].endswith(f'/commit/{pin["revision"]}'))
        for example in self.data["browser_examples"]:
            if example["thumbnail"] and example["id"] != "hello_world":
                self.assertIn("/web/evidence/", example["thumbnail"]["capture_report_url"])
                self.assertIn(example["thumbnail"]["capture_revision"], example["thumbnail"]["capture_source_url"])

    def test_valid_new_inventory_pins_do_not_rewrite_any_retained_report(self):
        inventory = deepcopy(load_json("web/examples.json"))
        inventory["upstream"]["revision"] = "a" * 40
        inventory["moonbit"]["revision"] = "b" * 40
        real_load = load_json
        for path in (BROWSER_RESULT_PATH, TEXT_RESULT_PATH, PRIME_RESULT_PATH):
            validate_browser_inventory(load_json(path), inventory, path)
        with patch("scripts.build_test_catalog.load_json", side_effect=lambda path: inventory if path == "web/examples.json" else real_load(path)):
            data = build_catalog("new-inventory")
        self.assertEqual(data["browser"]["pins"], self.data["browser"]["pins"])
        self.assertEqual(data["browser"]["changed_pixels"], 1532)
        self.assertTrue(all(example["source_revision"] == "a" * 40 for example in data["browser_examples"]))
        self.assertTrue(all("/" + "a" * 40 + "/" in example["source_url"] for example in data["browser_examples"]))

    def test_historical_pin_changes_fail_closed_for_all_retained_reports(self):
        real_load = load_json
        for result_path in (BROWSER_RESULT_PATH, TEXT_RESULT_PATH, PRIME_RESULT_PATH):
            for kind in ("upstream", "moonbit"):
                for field, value in (("revision", "c" * 40), ("repository", "other/project")):
                    changed = deepcopy(load_json(result_path))
                    # A well-formed new pin must not relabel an older image.
                    changed["build"][kind][field] = value
                    with self.subTest(path=result_path, kind=kind, field=field), patch(
                        "scripts.build_test_catalog.load_json",
                        side_effect=lambda path: changed if path == result_path else real_load(path),
                    ):
                        with self.assertRaisesRegex(ValueError, f"retained browser {kind} pin"):
                            build_catalog("test")

    def test_matching_dependency_pins_do_not_verify_current_adapter_sources(self):
        inventory = deepcopy(load_json("web/examples.json"))
        inventory["moonbit"]["revision"] = RETAINED_BROWSER_PINS["moonbit"]["revision"]
        real_load = load_json
        with patch("scripts.build_test_catalog.load_json", side_effect=lambda path: inventory if path == "web/examples.json" else real_load(path)):
            data = build_catalog("new-adapter-sources")
        self.assertTrue(data["browser"]["pins_match_current_inventory"])
        self.assertEqual(data["browser"]["current_status"], "unverified")
        self.assertEqual(data["browser"]["pins"], self.data["browser"]["pins"])
        self.assertEqual(sum(example["status"] == "unverified" for example in data["browser_examples"]), 16)

    def test_each_retained_report_requires_its_own_measured_port(self):
        inventory = load_json("web/examples.json")
        for path, example_id in ((BROWSER_RESULT_PATH, "hello_world"),
                                 (TEXT_RESULT_PATH, "text_layout"), (PRIME_RESULT_PATH, "hello_web")):
            changed = deepcopy(load_json(path))
            changed["build"]["implemented"].remove(example_id)
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "measured implemented examples"):
                validate_browser_inventory(changed, inventory, path)
        with self.assertRaisesRegex(ValueError, "unknown retained browser report"):
            validate_browser_inventory(load_json(BROWSER_RESULT_PATH), inventory, "unregistered/result.json")

    def test_retained_browser_reports_and_manifests_keep_their_original_bytes(self):
        digests = {
            BROWSER_RESULT_PATH: "7a5d1362a79ddb28b559a7a21585dcf49f28ca9024b00a8c6604eb7397793a89",
            TEXT_RESULT_PATH: "5aec5346d546eb449f13090a4e30e6c29ac852f848c4ce96c6c78943432210ab",
            TEXT_CAPTURE_MANIFEST: "a8d589193f819812bf25185dd8603e0fa5911b590a225fc7015f2abde756495b",
            PRIME_RESULT_PATH: "afb308ff25dd3f417bf76d05acd7b1e9a0a11ff8c6a7c885fbaf3e5b8575b726",
            PRIME_CAPTURE_MANIFEST: "7b2b92be0c5ee957416b19fe7a4c8a3a20885bce8749cf7b7b469bb13e452755",
        }
        for path, digest in digests.items():
            with self.subTest(path=path):
                self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), digest)

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
        self.assertEqual(self.data["browser"]["implemented_count"], 18)
        self.assertEqual(self.data["browser"]["evidence_count"], 1)

    def test_build_capability_is_not_per_example_measurement(self):
        # Declared build capability cannot give another port the
        # legacy file's single hello_world comparison, for equal or different.
        expected_previews = {item["id"]: item["thumbnail"] for item in build_catalog("test")["browser_examples"]}
        for pixel_result in ("equal", "different"):
            browser = deepcopy(load_json(BROWSER_RESULT_PATH))
            browser["build"]["implemented"].extend(("text_layout", "text_wrapper", "scrollable", "focus_visible", "tab_stop", "drag_drop", "uniform_list", "grid_layout", "anchor", "gradient", "popover", "pattern"))
            browser["raster_comparison"]["status"] = pixel_result
            real_load = load_json
            def patched_load(path):
                return browser if path == BROWSER_RESULT_PATH else real_load(path)
            with self.subTest(pixel_result=pixel_result), patch("scripts.build_test_catalog.load_json", side_effect=patched_load):
                examples = build_catalog("test")["browser_examples"]
            for example_id in ("text_layout", "text_wrapper", "scrollable", "focus_visible", "tab_stop", "drag_drop", "uniform_list", "grid_layout", "anchor", "gradient", "popover", "pattern"):
                new_port = next(item for item in examples if item["id"] == example_id)
                with self.subTest(example=example_id):
                    self.assertEqual(new_port["status"], "unverified")
                    self.assertEqual(new_port["execution"], "unverified")
                    self.assertFalse(new_port["evidence_available"])
                    for key in ("result_url", "result_date", "changed_pixels", "total_pixels"):
                        self.assertIsNone(new_port[key], key)
                    self.assertEqual(new_port["thumbnail"], expected_previews[example_id])

    def test_browser_ports_preserve_the_full_154_row_coverage_catalog(self):
        # 134 retained headless + 2 native + 18 browser rows; pattern adds no measurement.
        self.assertEqual(len(self.data["cases"]) + len(self.data["native_cases"]) + len(self.data["browser_examples"]), 154)
        self.assertEqual(
            {example["id"] for example in self.data["browser_examples"] if example["implemented"]},
            {"hello_world", "text", "text_layout", "text_wrapper", "input", "dynamic_fonts", "hello_web", "tree", "scrollable", "focus_visible", "tab_stop", "drag_drop", "uniform_list", "grid_layout", "anchor", "gradient", "popover", "pattern"},
        )

    def test_unimplemented_examples_have_no_borrowed_results_or_routes(self):
        # Also demote an implemented entry to exercise the fail-closed guard.
        inventory = deepcopy(load_json("web/examples.json"))
        next(e for e in inventory["examples"] if e["id"] == "focus_visible")["moonbit"] = "not_implemented"
        real_load = load_json
        with patch.dict(os.environ, {BROWSER_LAB_BASE_URL_ENV: "https://gpui-conformance-browser-lab.account.workers.dev"}), patch(
            "scripts.build_test_catalog.load_json",
            side_effect=lambda path: inventory if path == "web/examples.json" else real_load(path),
        ):
            examples = build_catalog("unimplemented-fixture")["browser_examples"]
        self.assertEqual([example["id"] for example in examples if not example["implemented"]], ["focus_visible"])
        for example in examples:
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
