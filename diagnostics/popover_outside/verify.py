"""Check trace structure and frozen source hypotheses, not execution provenance.

A matching JSON file is not proof that GPUI ran. Only independently retained,
source-bound execution evidence can establish actual upstream behavior.
"""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
UPSTREAM = "5a5fbe79917971a4d52a96b6ddb04da198a5012e"
BOUNDS = {"host": [0, 0, 320, 240], "parent_trigger": [20, 20, 60, 24],
          "parent": [60, 70, 180, 110], "child_trigger": [76, 86, 64, 24],
          "child": [160, 130, 100, 60]}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(raw, fixture=None):
    fixture = fixture or json.loads((HERE / "scenarios.json").read_text())
    require(raw["schema_version"] == 1, "schema")
    require(raw["upstream_revision"] == UPSTREAM, "upstream")
    require(raw["layer"] == "supplemental-headless-popover-outside", "layer")
    require(raw["fixture"] == "source-derived-font-free-two-level-popover", "fixture")
    require(isinstance(raw["run_token"], str) and bool(raw["run_token"]), "token")
    require(raw["input"] == fixture, "input differs from frozen fixture")
    steps = [{"id": "initial", "kind": "open_window"}] + fixture["steps"]
    hypotheses = {"initial": {"state": [False, False], "callbacks": []},
                  **fixture["source_hypotheses"]}
    state = [False, False]
    operation_index = 0
    active = None
    callbacks = []
    frame = 0
    frames = []
    rendered_state = None
    frame_events = None
    summary = []
    def close_frame():
        if frame_events is None:
            return
        expected = ["host", "parent_trigger"]
        if rendered_state[0]:
            expected += ["parent", "child_trigger"]
        if rendered_state[0] and rendered_state[1]:
            expected += ["child"]
        # draw_roots prepaints all deferred draws before painting the root;
        # the observed root paint returns before paint_deferred_draws begins.
        chronology = [("prepaint", node) for node in expected]
        chronology += [("paint", node) for node in expected[:2]]
        chronology += [("host_paint_return", None)]
        chronology += [("paint", node) for node in expected[2:]]
        require(frame_events == chronology, f"frame {frame} cross-phase chronology")
    for sequence, row in enumerate(raw["events"]):
        require(row["sequence"] == sequence, "non-contiguous sequence")
        event = row["event"]
        kind = event["type"]
        if kind == "operation_start":
            require(active is None and operation_index < len(steps), "operation nesting/count")
            step = steps[operation_index]
            active = step["id"]
            callbacks = []
            require(event["input"] == {k:v for k,v in step.items() if k != "id"}, "operation input")
        require(active is not None and row["operation"] == active, "unbracketed event")
        if kind == "frame_start":
            close_frame()
            frame += 1
            require(rendered_state is not None, "frame without render")
            require(event["scale"] == 2, "unexpected bootstrap scale; investigate, do not normalize")
            frame_events = []
            frames.append({"frame": frame, "operation": active, "state": rendered_state[:]})
        require(row["frame"] == frame, "frame identity")
        if kind == "render":
            # Finish the previous frame before replacing its state snapshot.
            close_frame()
            frame_events = None
            require(event["state"] == state, "render state")
            rendered_state = state[:]
            require(event["parent_outside_registered"] == (state[0] and not state[1]), "parent registration")
            require(event["child_outside_registered"] == (state[0] and state[1]), "child registration")
        elif kind in ("prepaint", "paint"):
            require(frame_events is not None, "geometry outside frame")
            node = event["node"]
            require(node in BOUNDS and event["bounds"] == BOUNDS[node], "geometry")
            frame_events.append((kind, node))
        elif kind == "host_paint_return":
            require(frame_events is not None, "host return outside frame")
            frame_events.append((kind, None))
        elif kind == "callback":
            require(event["before"] == state, "callback before state")
            name = event["name"]
            callbacks.append(name)
            require(name in ("open_parent", "open_child", "dismiss_parent", "dismiss_child"), "callback name")
            expected = state[:]
            expected[0 if name.endswith("parent") else 1] = name.startswith("open")
            require(event["after"] == expected, "callback mutation")
            step = steps[operation_index]
            if name.startswith("dismiss"):
                require(step["kind"] == "down", "dismiss on release")
                require(event["button"] == step["button"].capitalize(), "button")
            else:
                require(step["kind"] == "up" and event["button"] is None, "open is on_click")
            state = expected
        elif kind == "operation_end":
            close_frame()
            require(frame_events is not None and rendered_state == state, "unsettled frame state")
            require(event["state"] == state == hypotheses[active]["state"], "final state")
            require(callbacks == hypotheses[active]["callbacks"], "callback order/count")
            summary.append({"operation": active, "state": state[:], "callbacks": callbacks[:]})
            active = None
            operation_index += 1
        else:
            require(kind in ("operation_start", "frame_start"), "unknown event")
    close_frame()
    require(active is None and operation_index == len(steps), "missing operations")
    require(frame > 0, "missing actual frame callbacks")
    return {"status": "source_hypotheses_match", "execution_authenticated": False,
            "operations": summary, "frames": frames}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(json.loads(args.raw.read_text())), indent=2))
