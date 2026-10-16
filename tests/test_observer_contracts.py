"""Pure observer identity tests; synthetic records never establish execution."""
import copy
from datetime import datetime
import unittest

from observer_contracts import execution_root, validate_ack, validate_frame_binding, validate_observation, validate_ready


TOKEN = "a740c390-c5f0-4db8-a281-40c8dd4b940a"
START = "2026-10-15T06:00:00+00:00"
END = "2026-10-15T06:00:05+00:00"
RUN = {"run_token": TOKEN, "revision": "a"*40, "executable": {"sha256": "b"*64}, "scenarios_sha256": "c"*64}


def ready():
    return {"protocol": 1, "run_token": TOKEN, "pid": 123, "native_window_id": 456,
            "executable": "/owned/probe", "executable_sha256": "b"*64, "source_revision": "a"*40,
            "scene_revision": "c"*64, "frame_sequence": 1, "process_start_sec": 1792044000,
            "process_start_usec": 1234, "ready_unix_ns": int(datetime.fromisoformat(START).timestamp()*1e9)+1000000000,
            "content_size": [256, 192], "scale": 2, "visible": True, "key": False,
            "application_active": False, "activation_policy": 1, "title": "GPUI conformance observer "+TOKEN}


def observed():
    r = ready()
    return {"protocol": 1, "permission_prompted": False, "ax_trusted": False,
            "window_binding": "pass", **{k:r[k] for k in ("pid", "native_window_id", "run_token", "process_start_sec", "process_start_usec", "executable")},
            "window": {"kCGWindowOwnerPID": 123, "kCGWindowNumber": 456, "kCGWindowIsOnscreen": True,
                       "kCGWindowBounds": {"X": 0, "Y": 0, "Width": 256, "Height": 214}}, "ax_status": "unverified"}


class ObserverContracts(unittest.TestCase):
    def test_original_root_binds_flat_and_bundled_retained_executable(self):
        for path in ("upstream/probe", "upstream/Fixture.app/Contents/MacOS/probe"):
            run = {"execution":{"command":["/original/result/"+path]}, "executable":{"path":path}}
            self.assertEqual(str(execution_root(run)), "/original/result")
            for command in (["/foreign/probe"], ["/original/result/"+path,"extra"], ["relative/"+path], ["/original/../result/"+path]):
                run["execution"]["command"] = command
                with self.subTest(path=path,command=command), self.assertRaises(ValueError): execution_root(run)

    def test_escaping_retained_executable_cannot_bind_original_root(self):
        for path in ("/absolute/probe", "upstream/../probe", "probe"):
            run = {"execution":{"command":["/original/result/upstream/probe"]}, "executable":{"path":path}}
            with self.subTest(path=path), self.assertRaises(ValueError): execution_root(run)

    def test_bundled_ready_requires_measured_runtime_identity(self):
        run = {**RUN,"implementation":"upstream","fixture_packaging":"app-bundle-v1"}
        r = ready(); r["executable"] = "/owned/Fixture.app/Contents/MacOS/probe"
        identifier = "org.gpui-mbt.conformance.upstream."+TOKEN
        r.update(local_ax_read=True,local_ax={"bundle_path":"/owned/Fixture.app",
            "bundle_identifier":identifier,"running_bundle_identifier":identifier})
        def validate(value): validate_ready(value,run,123,r["executable"],[256,192],START,END)
        validate(r)
        for field in ("bundle_path","bundle_identifier","running_bundle_identifier"):
            changed = copy.deepcopy(r); changed["local_ax"][field] = "foreign"
            with self.subTest(field=field), self.assertRaises(ValueError): validate(changed)
        changed = copy.deepcopy(r); changed["local_ax_read"] = False
        with self.assertRaises(ValueError): validate(changed)

    def validate(self, value):
        validate_ready(value, RUN, 123, "/owned/probe", [256, 192], START, END)

    def test_complete_ready_and_untrusted_observer_are_distinct(self):
        self.validate(ready())
        validate_observation(observed(), ready())

    def test_wrong_process_executable_source_scene_or_challenge_rejected(self):
        for key, value in (("pid",124),("executable","/foreign/probe"),("executable_sha256","d"*64),
                           ("source_revision","d"*40),("scene_revision","d"*64),("run_token","b740c390-c5f0-4db8-a281-40c8dd4b940a")):
            r = ready(); r[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.validate(r)

    def test_missing_or_stale_frame_and_window_rejected(self):
        for key, value in (("frame_sequence",0),("native_window_id",0),("native_window_id",True),("process_start_sec",0),("process_start_usec",1000000)):
            r = ready(); r[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.validate(r)

    def test_wrong_dimensions_scale_or_visibility_rejected(self):
        for key, value in (("content_size",[0,192]),("scale",float("nan")),("scale",0),("visible",False),("key",True),("application_active",True),("activation_policy",0)):
            r = ready(); r[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.validate(r)

    def test_ready_must_fall_within_owned_execution(self):
        for stamp in (0, ready()["ready_unix_ns"]+6000000000):
            r = ready(); r["ready_unix_ns"] = stamp
            with self.subTest(stamp=stamp), self.assertRaises(ValueError): self.validate(r)

    def test_unknown_or_boolean_protocol_rejected(self):
        for protocol in (None, True, 2):
            r = ready(); r["protocol"] = protocol
            with self.subTest(protocol=protocol), self.assertRaises(ValueError): self.validate(r)

    def test_foreign_or_hidden_or_zero_sized_window_rejected(self):
        for key,value in (("kCGWindowOwnerPID",124),("kCGWindowNumber",789),("kCGWindowIsOnscreen",False),("kCGWindowBounds",{"X":0,"Y":0,"Width":0,"Height":214})):
            o = observed(); o["window"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): validate_observation(o,ready())

    def test_observer_identity_is_bound_to_ready(self):
        for key,value in (("pid",124),("native_window_id",789),("process_start_sec",0),("executable","/foreign/probe")):
            o = observed(); o[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): validate_observation(o,ready())

    def test_missing_permission_or_multiple_ax_windows_cannot_pass(self):
        for trusted,matches in ((False,1),(True,0),(True,2),(True,True)):
            o = observed(); o.update(ax_status="pass",ax_trusted=trusted,ax_matching_windows=matches)
            with self.subTest(trusted=trusted,matches=matches), self.assertRaises(ValueError): validate_observation(o,ready())

    def test_one_trusted_owned_ax_window(self):
        o = observed(); o.update(ax_status="pass",ax_trusted=True,ax_matching_windows=1)
        o["ax_windows"] = [{"pid":123,"title":ready()["title"],"role":"AXWindow","position":[0,0],"size":[256,214]}]
        validate_observation(o,ready())
        for key,value in (("pid",124),("title","foreign"),("role","AXButton"),("position",[10,0]),("size",[0,214])):
            changed = copy.deepcopy(o); changed["ax_windows"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): validate_observation(changed,ready())

    def test_permission_prompt_cannot_qualify(self):
        o = observed(); o["permission_prompted"] = True
        with self.assertRaises(ValueError): validate_observation(o,ready())

    def test_application_alias_cannot_qualify_despite_matching_window_fields(self):
        o = observed(); o.update(ax_status="pass",ax_trusted=True,ax_matching_windows=1)
        o["ax_windows"] = [{"pid":123,"title":ready()["title"],"role":"AXWindow",
                            "position":[0,0],"size":[256,214],"same_application_element":False}]
        validate_observation(o,ready())
        for alias in (True, None, 0, "false"):
            changed = copy.deepcopy(o); changed["ax_windows"][0]["same_application_element"] = alias
            with self.subTest(alias=alias), self.assertRaises(ValueError):
                validate_observation(changed,ready())

    def test_ack_is_nonce_window_process_and_frame_bound(self):
        ack = {"run_token":TOKEN,"pid":123,"native_window_id":456,"frame_sequence":1,"observer_completed":True}
        validate_ack(ack,ready())
        for key,value in (("run_token","wrong"),("pid",124),("native_window_id",789),("frame_sequence",0),("observer_completed",1)):
            a = copy.deepcopy(ack); a[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): validate_ack(a,ready())

    def test_ready_is_bound_to_same_rendered_window_and_full_frame(self):
        output = {"native_fixture":{"snapshots":[{"native_window_id":456} for _ in range(4)]},
                  "frame":{"width":512,"height":384,"scale":2}}
        validate_frame_binding(ready(),output)
        for field,value in (("width",256),("height",192),("scale",1)):
            changed = copy.deepcopy(output); changed["frame"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): validate_frame_binding(ready(),changed)
        changed = copy.deepcopy(output); changed["native_fixture"]["snapshots"][1]["native_window_id"] = 789
        with self.assertRaises(ValueError): validate_frame_binding(ready(),changed)


if __name__ == "__main__": unittest.main()
