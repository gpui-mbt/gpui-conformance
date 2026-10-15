"""Synthetic protocol and real subprocess cleanup tests; no native AX qualification."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from run_ax_regression import classify_attempt, stop_owned
from test_observer_contracts import observed, ready


def matched():
    value = observed()
    value.update(ax_trusted=True, ax_status="pass", ax_matching_windows=1,
        ax_windows=[{"pid":123,"title":ready()["title"],"role":"AXWindow",
                     "position":[0,0],"size":[256,214]}],
        ax_owned_candidates=[{"pid":123,"title":ready()["title"],"role":"AXWindow",
                              "same_application_element":False}])
    return value


class AXRegressionTests(unittest.TestCase):
    def test_successful_ipc_and_trust_do_not_make_application_a_window(self):
        value = observed()
        value.update(ax_trusted=True,ax_application_attribute_status={"AXWindows":0},
            ax_owned_candidates=[{"pid":123,"role":"AXApplication","title":"probe",
                                  "same_application_element":True}])
        self.assertEqual(classify_attempt(value,ready()),"application-returned-as-window")
        value["ax_status"] = "pass"
        with self.assertRaises(ValueError): classify_attempt(value,ready())

    def test_exact_external_window_is_distinct_from_application(self):
        self.assertEqual(classify_attempt(matched(),ready()),"external-window-matched")
        for equality in (True,None,0):
            value = matched()
            value["ax_owned_candidates"][0]["same_application_element"] = equality
            with self.subTest(equality=equality), self.assertRaises(ValueError):
                classify_attempt(value,ready())

    def test_role_title_owner_and_bounds_cannot_be_replaced_by_local_getters(self):
        for key, replacement in (("role","AXApplication"),("title","probe"),
                                 ("pid",456),("size",[255,214])):
            value = matched()
            value["ax_windows"][0][key] = replacement
            value["local_ax"] = {"window_role":"AXWindow","window_title":ready()["title"]}
            with self.subTest(key=key), self.assertRaises(ValueError):
                classify_attempt(value,ready())

    def test_foreign_process_or_window_cannot_match(self):
        for key in ("pid","native_window_id","process_start_sec","process_start_usec","executable","run_token"):
            value = matched()
            value[key] = "foreign"
            with self.subTest(key=key), self.assertRaises(ValueError): classify_attempt(value,ready())

    def test_permissions_missing_windows_and_prompt_are_separate(self):
        value = observed()
        self.assertEqual(classify_attempt(value,ready()),"observer-untrusted")
        value["ax_trusted"] = True
        self.assertEqual(classify_attempt(value,ready()),"external-window-unmatched")
        value["permission_prompted"] = True
        with self.assertRaises(ValueError): classify_attempt(value,ready())

    def test_earlier_failure_remains_in_attempt_history(self):
        initial = observed()
        initial.update(ax_trusted=True,ax_owned_candidates=[{"role":"AXApplication","same_application_element":True}])
        retained = copy.deepcopy(initial)
        self.assertEqual([classify_attempt(x,ready()) for x in (initial,matched())],
                         ["application-returned-as-window","external-window-matched"])
        self.assertEqual(initial,retained)

    def test_cleanup_reaps_only_owned_child_and_preserves_sentinel(self):
        child = subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"])
        sentinel = subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"])
        try:
            self.assertLess(stop_owned(child),0)
            self.assertIsNotNone(child.poll())
            self.assertIsNone(sentinel.poll())
        finally:
            stop_owned(child)
            stop_owned(sentinel)

    @unittest.skipIf(sys.platform == "darwin", "unsupported-platform guard is a Linux check")
    def test_non_macos_cannot_report_native_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)/"evidence"
            result = subprocess.run([sys.executable,"run_ax_regression.py","--output",str(output)],
                                    capture_output=True,text=True,timeout=5)
            self.assertEqual(result.returncode,77,result.stderr)
            summary = json.loads((output/"summary.json").read_text())
            self.assertEqual(summary["status"],"unverified")
            self.assertEqual(summary["gpui_ax_compatibility"],"unverified")
            self.assertNotIn("run",summary)


if __name__ == "__main__":
    unittest.main()
