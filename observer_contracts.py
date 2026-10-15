"""Owned-window observer contracts; no UI or permission changes."""
from datetime import datetime
import math
from pathlib import Path
import uuid


def validate_ready(value, run, pid, executable, dimensions, started_at, finished_at=None):
    if not isinstance(value, dict) or type(value.get("protocol")) is not int or value["protocol"] != 1:
        raise ValueError("unknown ready protocol")
    uuid.UUID(value["run_token"])
    expected = {"run_token": run["run_token"], "pid": pid, "executable": str(executable),
                "executable_sha256": run["executable"]["sha256"], "source_revision": run["revision"],
                "scene_revision": run["scenarios_sha256"], "frame_sequence": 1,
                "title": "GPUI conformance observer " + run["run_token"], "content_size": dimensions,
                "visible": True, "key": False, "application_active": False, "activation_policy": 1}
    for key, expected_value in expected.items():
        actual = value.get(key)
        if actual != expected_value or isinstance(expected_value, (bool, int)) and type(actual) is not type(expected_value):
            raise ValueError("ready identity/state differs: " + key)
    for key in ("process_start_sec", "process_start_usec", "native_window_id", "ready_unix_ns"):
        if type(value.get(key)) is not int or value[key] < 0:
            raise ValueError("invalid native identity: " + key)
    if not value["process_start_sec"] or not value["native_window_id"] or value["process_start_usec"] >= 1000000:
        raise ValueError("missing process start/window identity")
    if type(value.get("scale")) not in (int, float) or not math.isfinite(value["scale"]) or value["scale"] <= 0:
        raise ValueError("invalid ready scale")
    start = datetime.fromisoformat(started_at)
    if start.tzinfo is None or value["ready_unix_ns"] < int(start.timestamp()*1e9):
        raise ValueError("ready predates owned execution")
    if finished_at is not None:
        end = datetime.fromisoformat(finished_at)
        if end.tzinfo is None or value["ready_unix_ns"] > int(end.timestamp()*1e9):
            raise ValueError("ready follows owned execution")
    # An executable path is an identity, never a relocation target to read.
    if not Path(value["executable"]).is_absolute():
        raise ValueError("missing absolute executable identity")


def validate_observation(value, ready):
    if not isinstance(value, dict) or type(value.get("protocol")) is not int or value["protocol"] != 1 or value.get("permission_prompted") is not False:
        raise ValueError("unknown observer protocol or permission prompt")
    if type(value.get("ax_trusted")) is not bool or value.get("window_binding") != "pass":
        raise ValueError("owned visible window not bound")
    for key in ("pid", "native_window_id", "run_token", "process_start_sec", "process_start_usec", "executable"):
        if value.get(key) != ready[key] or type(value.get(key)) is not type(ready[key]):
            raise ValueError("observer identity differs: " + key)
    window = value.get("window", {})
    for key, expected in (("kCGWindowOwnerPID", ready["pid"]), ("kCGWindowNumber", ready["native_window_id"])):
        if type(window.get(key)) is not int or window[key] != expected:
            raise ValueError("foreign WindowServer window")
    if window.get("kCGWindowIsOnscreen") is not True:
        raise ValueError("owned window is not onscreen")
    bounds = window.get("kCGWindowBounds", {})
    for key in ("X", "Y", "Width", "Height"):
        if type(bounds.get(key)) not in (int, float) or not math.isfinite(bounds[key]):
            raise ValueError("invalid WindowServer bounds")
    if bounds["Width"] <= 0 or bounds["Height"] <= 0:
        raise ValueError("zero-sized WindowServer window")
    if value.get("ax_status") not in ("pass", "unverified"):
        raise ValueError("unknown AX status")
    if value["ax_status"] == "pass" and (value["ax_trusted"] is not True or type(value.get("ax_matching_windows")) is not int or value["ax_matching_windows"] != 1):
        raise ValueError("AX pass lacks one trusted owned window")


def validate_ack(value, ready):
    expected = {"run_token": ready["run_token"], "pid": ready["pid"], "native_window_id": ready["native_window_id"],
                "frame_sequence": 1, "observer_completed": True}
    if not isinstance(value, dict) or value.keys() != expected.keys() or any(value[k] != v or type(value[k]) is not type(v) for k, v in expected.items()):
        raise ValueError("owned acknowledgment identity differs")


def validate_frame_binding(ready, output):
    snapshots = output["native_fixture"]["snapshots"]
    if any(sample["native_window_id"] != ready["native_window_id"] for sample in snapshots[:3]):
        raise ValueError("observer window differs from rendered fixture")
    frame = output["frame"]
    if frame["scale"] != ready["scale"] or any(frame[key] != size*ready["scale"] for key, size in zip(("width", "height"), ready["content_size"])):
        raise ValueError("ready dimensions/scale differ from completed GPU frame")
