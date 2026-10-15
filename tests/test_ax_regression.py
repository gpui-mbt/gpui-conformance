"""Synthetic protocol and owned-process tests; no native AX qualification."""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import run_ax_regression
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


class FakeChild:
    def __init__(self, pid, alive_polls):
        self.pid = pid
        self.alive_polls = alive_polls
        self.poll_count = 0
        self.wait_count = 0
        self.killed = False

    def poll(self):
        self.poll_count += 1
        return None if self.poll_count <= self.alive_polls else 0

    def wait(self, timeout=None):
        self.wait_count += 1
        return 0

    def kill(self):
        self.killed = True


class FakeRunner:
    """Exercise main/run_control without invoking a subprocess or native code."""
    pid = 43210

    def __init__(self, observation_kinds, ready_kind=None):
        self.observation_kinds = list(observation_kinds)
        self.ready_kind = ready_kind
        self.child = None
        self.ready_record = None

    def popen(self, args, env, cwd, stdout, stderr):
        executable = str(args[0])
        token = env["GPUI_RUN_TOKEN"]
        record = ready()
        record.update(
            run_token=token,
            pid=self.pid,
            native_window_id=456,
            executable=executable,
            executable_sha256=env["GPUI_EXECUTABLE_SHA256"],
            source_revision=env["GPUI_SOURCE_REVISION"],
            scene_revision=env["GPUI_SCENE_SHA256"],
            ready_unix_ns=time.time_ns(),
            title="GPUI conformance observer " + token,
            control_kind="stock-appkit-no-gpu",
            pump=env["GPUI_AX_CONTROL_PUMP"],
            local_ax={
                "application_windows": [
                    {
                        "same_owned_window": True,
                        "role": "AXWindow",
                        "title": "GPUI conformance observer " + token,
                    }
                ],
                "button_role": "AXButton",
            },
        )
        if self.ready_kind == "ready-root-null":
            record = None
        elif self.ready_kind == "ready-root-list":
            record = [record]
        elif self.ready_kind == "local-ax-null":
            record["local_ax"] = None
        elif self.ready_kind == "local-ax-list":
            record["local_ax"] = []
        elif self.ready_kind == "application-windows-null":
            record["local_ax"]["application_windows"] = [None]
        elif self.ready_kind == "application-windows-string":
            record["local_ax"]["application_windows"] = ["x"]
        elif self.ready_kind == "nonce-list":
            record["run_token"] = []
        elif self.ready_kind == "nonce-dict":
            record["run_token"] = {}
        elif self.ready_kind == "nonce-int":
            record["run_token"] = 7
        self.ready_record = record
        ready_path = Path(env["GPUI_OBSERVER_DIR"]) / "ready.json"
        ready_path.write_text(json.dumps(record) + "\n")
        self.child = FakeChild(self.pid, alive_polls=len(self.observation_kinds) + 1)
        return self.child

    def make_observation(self, kind):
        if kind == "root-string":
            return "not an observer object"
        record = self.ready_record
        value = observed()
        value.update(
            pid=record["pid"],
            native_window_id=record["native_window_id"],
            run_token=record["run_token"],
            process_start_sec=record["process_start_sec"],
            process_start_usec=record["process_start_usec"],
            executable=record["executable"],
        )
        value["window"]["kCGWindowOwnerPID"] = record["pid"]
        value["window"]["kCGWindowNumber"] = record["native_window_id"]
        if kind == "candidate-null":
            value["ax_owned_candidates"] = [None]
        elif kind == "candidate-string":
            value["ax_owned_candidates"] = "x"
        elif kind == "window-null":
            value["window"] = None
        elif kind == "bounds-null":
            value["window"]["kCGWindowBounds"] = None
        elif kind == "windows-null":
            value.update(ax_trusted=True, ax_status="pass", ax_matching_windows=1)
            value["ax_owned_candidates"] = [
                {"same_application_element": False, "role": "AXWindow"}
            ]
            value["ax_windows"] = [None]
        elif kind == "matched":
            value.update(ax_trusted=True, ax_status="pass", ax_matching_windows=1)
            value["ax_owned_candidates"] = [
                {
                    "pid": record["pid"],
                    "title": record["title"],
                    "role": "AXWindow",
                    "same_application_element": False,
                }
            ]
            value["ax_windows"] = [
                {
                    "pid": record["pid"],
                    "title": record["title"],
                    "role": "AXWindow",
                    "position": [0, 0],
                    "size": [256, 214],
                }
            ]
        else:
            raise AssertionError("unknown fake observation kind: " + kind)
        return value

    def execute(self, args, env, out, err, cwd, timeout, before_terminate=None):
        out.parent.mkdir(parents=True, exist_ok=True)
        err.parent.mkdir(parents=True, exist_ok=True)
        if args[0] == "xcrun":
            executable = Path(args[-1])
            executable.parent.mkdir(parents=True, exist_ok=True)
            executable.write_bytes(b"fake executable; no compiler invoked\n")
            out.write_bytes(b"fake build output\n")
            err.write_bytes(b"")
        else:
            kind = self.observation_kinds.pop(0)
            out.write_text(json.dumps(self.make_observation(kind)) + "\n")
            err.write_bytes(b"")
        return {
            "command": args,
            "pid": self.pid,
            "started_at": "fake-start",
            "finished_at": "fake-finish",
            "returncode": 0,
            "timed_out": False,
        }

    def run_main(self, output):
        argv = ["run_ax_regression.py", "--packaging", "flat", "--output", str(output)]

        def fake_command(args, cwd=None):
            if args[:2] == ["git", "rev-parse"]:
                return "d" * 40
            if args[0] == "xcrun":
                return "fake clang"
            return ""

        with (
            patch.object(sys, "argv", argv),
            patch("run_ax_regression.platform.system", return_value="Darwin"),
            patch("run_ax_regression.platform.machine", return_value="arm64"),
            patch("run_ax_regression.platform.mac_ver", return_value=("14.0", ("", "", ""), "arm64")),
            patch("run_ax_regression.command", side_effect=fake_command),
            patch("run_ax_regression.execute", side_effect=self.execute),
            patch("run_ax_regression.subprocess.Popen", side_effect=self.popen),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            return run_ax_regression.main()


class AXRegressionTests(unittest.TestCase):
    def test_malformed_ready_shapes_are_retained_with_unverified_summary(self):
        for kind in (
            "ready-root-null",
            "ready-root-list",
            "local-ax-null",
            "local-ax-list",
            "application-windows-null",
            "application-windows-string",
            "nonce-list",
            "nonce-dict",
            "nonce-int",
        ):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "evidence"
                fake = FakeRunner([], ready_kind=kind)
                result = fake.run_main(output)
                summary = json.loads((output / "summary.json").read_text())
                self.assertEqual(result, 1)
                self.assertEqual(summary["status"], "unverified")
                self.assertEqual(summary["gpui_ax_compatibility"], "unverified")
                self.assertEqual(summary["run"]["status"], "unverified")
                self.assertEqual(summary["run"]["cleanup"], "owned-child-reaped")
                self.assertEqual(summary["run"]["returncode"], 0)
                self.assertEqual(summary["run"]["attempts"], [])
                self.assertIn("invalid ready record", summary["run"]["reason"])
                self.assertIn("ready", summary["run"])
                retained_ready = output / summary["run"]["ready"]["path"]
                self.assertTrue(retained_ready.is_file())
                self.assertEqual(
                    summary["run"]["ready"]["sha256"],
                    hashlib.sha256(retained_ready.read_bytes()).hexdigest(),
                )
                self.assertEqual(json.loads(retained_ready.read_text()), fake.ready_record)
                self.assertIsNotNone(fake.child)
                self.assertFalse(fake.child.killed)
                self.assertGreater(fake.child.wait_count, 0)

    def test_malformed_observer_shapes_are_retained_in_unverified_summaries(self):
        for kind in (
            "root-string",
            "candidate-null",
            "candidate-string",
            "window-null",
            "bounds-null",
            "windows-null",
        ):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "evidence"
                fake = FakeRunner([kind])
                result = fake.run_main(output)
                summary_path = output / "summary.json"
                self.assertEqual(result, 1)
                self.assertTrue(summary_path.is_file())
                summary = json.loads(summary_path.read_text())
                self.assertEqual(summary["status"], "unverified")
                self.assertEqual(summary["gpui_ax_compatibility"], "unverified")
                self.assertEqual(summary["run"]["status"], "unverified")
                self.assertEqual(summary["run"]["cleanup"], "owned-child-reaped")
                self.assertEqual(summary["run"]["returncode"], 0)
                self.assertEqual(len(summary["run"]["attempts"]), 1)

                attempt = summary["run"]["attempts"][0]
                self.assertEqual(attempt["classification"], "invalid-observer-record")
                self.assertIn("invalid observer record", attempt["reason"])
                raw_stdout = output / attempt["stdout"]["path"]
                self.assertTrue(raw_stdout.is_file())
                self.assertEqual(
                    attempt["stdout"]["sha256"],
                    hashlib.sha256(raw_stdout.read_bytes()).hexdigest(),
                )
                self.assertEqual(json.loads(raw_stdout.read_text()), fake.make_observation(kind))
                self.assertIsNotNone(fake.child)
                self.assertFalse(fake.child.killed)
                self.assertGreater(fake.child.wait_count, 0)

    def test_later_valid_observation_does_not_erase_earlier_invalid_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "evidence"
            fake = FakeRunner(["candidate-null", "matched"])
            result = fake.run_main(output)
            summary = json.loads((output / "summary.json").read_text())
            self.assertEqual(result, 0)
            self.assertEqual(summary["status"], "pass")
            attempts = summary["run"]["attempts"]
            self.assertEqual([item["classification"] for item in attempts], [
                "invalid-observer-record",
                "external-window-matched",
            ])
            self.assertTrue((output / attempts[0]["stdout"]["path"]).is_file())
            self.assertFalse(fake.child.killed)
            self.assertEqual(summary["run"]["cleanup"], "owned-child-reaped")

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
