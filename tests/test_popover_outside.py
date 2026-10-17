"""Synthetic checker sensitivity tests. No GPUI execution or parity claim."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("popover_verify", ROOT / "diagnostics/popover_outside/verify.py")
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)
FIXTURE = json.loads((ROOT / "diagnostics/popover_outside/scenarios.json").read_text())


def synthetic_trace():
    raw = dict(schema_version=1, upstream_revision=VERIFY.UPSTREAM,
               layer="supplemental-headless-popover-outside",
               fixture="source-derived-font-free-two-level-popover",
               run_token="SYNTHETIC-NOT-EXECUTED", input=copy.deepcopy(FIXTURE), events=[])
    frame = 0
    state = [False, False]
    steps = [{"id": "initial", "kind": "open_window"}] + FIXTURE["steps"]
    for step in steps:
        operation = step["id"]
        def emit(event):
            raw["events"].append(dict(sequence=len(raw["events"]), operation=operation,
                                      frame=frame, event=event))
        emit(dict(type="operation_start", input={k:v for k,v in step.items() if k != "id"}))
        hypothesis = FIXTURE["source_hypotheses"].get(operation, dict(state=state, callbacks=[]))
        for name in hypothesis["callbacks"]:
            after = hypothesis["state"][:]
            emit(dict(type="callback", name=name, before=state[:], after=after,
                      button=step["button"].capitalize() if name.startswith("dismiss") else None))
            state = after
        emit(dict(type="render", state=state[:], parent_outside_registered=state[0] and not state[1],
                  child_outside_registered=state[0] and state[1]))
        frame += 1
        emit(dict(type="frame_start", scale=2))
        nodes = ["host", "parent_trigger"] + (["parent", "child_trigger"] if state[0] else []) + (["child"] if all(state) else [])
        for node in nodes:
            emit(dict(type="prepaint", node=node, bounds=VERIFY.BOUNDS[node][:]))
        for node in nodes[:2]:
            emit(dict(type="paint", node=node, bounds=VERIFY.BOUNDS[node][:]))
        emit(dict(type="host_paint_return"))
        for node in nodes[2:]:
            emit(dict(type="paint", node=node, bounds=VERIFY.BOUNDS[node][:]))
        emit(dict(type="operation_end", state=state[:]))
    return raw


class PopoverOutsideTests(unittest.TestCase):
    def test_synthetic_round_trip(self):
        raw = synthetic_trace()
        report = VERIFY.verify(raw)
        self.assertFalse(report["execution_authenticated"])
        self.assertEqual(report, VERIFY.verify(json.loads(json.dumps(raw))))
        self.assertEqual(report, json.loads(json.dumps(report)))

    def test_cross_phase_chronology_mutations(self):
        # Each mutation preserves both per-phase node arrays and return count.
        # Only a single combined chronology can reject all of them.
        for operation in ("initial", "open-parent-up", "open-child-up"):
            for mode in ("paint_before_prepaint", "premature_host_return", "late_host_return"):
                if operation == "initial" and mode == "late_host_return":
                    continue  # With no deferred nodes, root return is already last.
                with self.subTest(operation=operation, mode=mode):
                    raw = synthetic_trace()
                    indices = [i for i, row in enumerate(raw["events"])
                               if row["operation"] == operation and row["event"]["type"]
                               in ("prepaint", "paint", "host_paint_return")]
                    rows = [raw["events"][i] for i in indices]
                    prepaint = [r for r in rows if r["event"]["type"] == "prepaint"]
                    paint = [r for r in rows if r["event"]["type"] == "paint"]
                    returned = [r for r in rows if r["event"]["type"] == "host_paint_return"]
                    if mode == "paint_before_prepaint":
                        reordered = paint[:2] + returned + paint[2:] + prepaint
                    elif mode == "premature_host_return":
                        reordered = prepaint + paint[:1] + returned + paint[1:]
                    else:
                        reordered = prepaint + paint + returned
                    for index, row in zip(indices, reordered):
                        raw["events"][index] = row
                    for index, row in enumerate(raw["events"]):
                        row["sequence"] = index
                    with self.assertRaisesRegex(ValueError, "cross-phase chronology"):
                        VERIFY.verify(raw)
                    # The exact malformed raw trace remains failing after serialization.
                    with self.assertRaisesRegex(ValueError, "cross-phase chronology"):
                        VERIFY.verify(json.loads(json.dumps(raw)))

    def test_wrong_same_event_parent_close(self):
        raw = synthetic_trace()
        row = next(r for r in raw["events"] if r["operation"] == "outside-both-first-down" and r["event"]["type"] == "callback")
        row["event"]["after"] = [False, False]
        with self.assertRaises(ValueError): VERIFY.verify(raw)

    def test_mutations(self):
        mutations = [
            ("callback", "button", "Left", "nonprimary-first-down"),
            ("callback", "name", "dismiss_parent", "parent-outside-child-down"),
            ("operation_end", "state", [False, False], "release-only-outside"),
            ("render", "parent_outside_registered", True, "open-child-up"),
            ("paint", "bounds", [0,0,0,0], "initial"),
            ("frame_start", "scale", 1, "initial"),
        ]
        for kind, key, value, operation in mutations:
            with self.subTest(kind=kind, key=key, operation=operation):
                raw = synthetic_trace()
                row = next(r for r in raw["events"] if r["operation"] == operation and r["event"]["type"] == kind)
                row["event"][key] = value
                with self.assertRaises(ValueError): VERIFY.verify(raw)

    def test_missing_duplicate_and_reordered_callbacks(self):
        for mode in ("missing", "duplicate", "reordered"):
            raw = synthetic_trace()
            indices = [i for i,r in enumerate(raw["events"]) if r["event"]["type"] == "callback"]
            if mode == "missing": raw["events"].pop(indices[0])
            elif mode == "duplicate": raw["events"].insert(indices[0],copy.deepcopy(raw["events"][indices[0]]))
            else:
                a,b=indices[:2]
                raw["events"][a]["event"],raw["events"][b]["event"]=raw["events"][b]["event"],raw["events"][a]["event"]
            for i,row in enumerate(raw["events"]): row["sequence"]=i
            with self.assertRaises(ValueError): VERIFY.verify(raw)

    def test_observer_uses_upstream_dispatch(self):
        source = (ROOT / "adapters/popover_outside_rust/src/main.rs").read_text()
        for required in ("TestAppContext::single()", "cx.simulate_mouse_down(", "cx.simulate_mouse_up(",
                         ".on_mouse_down_out(", ".when(!self.secondary_open,", ".priority(2)", ".priority(1)"):
            self.assertIn(required, source)
        self.assertNotIn("source_hypotheses", source)
        self.assertNotIn(".contains(", source)

    def test_preserves_all_723_baseline_files(self):
        base="cd205b17b6650bd7e518560640fc31084e723eeb"
        entries=subprocess.check_output(["git","-C",str(ROOT),"ls-tree","-r",base],text=True).splitlines()
        self.assertEqual(len(entries),723)
        for entry in entries:
            metadata,path=entry.split("\t",1)
            mode,kind,blob=metadata.split()
            current=subprocess.check_output(["git","-C",str(ROOT),"hash-object",path],text=True).strip()
            self.assertEqual(current,blob,path)
            self.assertEqual(bool((ROOT/path).stat().st_mode & 0o111),mode=="100755",path)


if __name__ == "__main__": unittest.main()
