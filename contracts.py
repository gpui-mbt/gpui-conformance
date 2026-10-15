"""Bounded first-slice input and observation contracts."""
import math

LAYERS = {"layout": "headless-layout", "pointer": "headless-dispatch", "key": "headless-dispatch", "route": "headless-dispatch", "focus": "headless-dispatch",
          "scene": "headless-scene", "clip": "headless-clip", "window": "native-window", "pixels": "native-gpu", "ime": "native-ime"}


def numbers(v, count, nonnegative=False):
    return isinstance(v, list) and len(v) == count and all(
        type(x) in (int, float) and math.isfinite(x) and (not nonnegative or x >= 0) for x in v)


def validate_scenarios(scenarios):
    if scenarios.get("schema_version") != 1 or not isinstance(scenarios.get("cases"), list) or not scenarios["cases"]:
        raise ValueError("expected nonempty schema-version-1 scenarios")
    ids = set()
    for s in scenarios["cases"]:
        kind = s.get("kind")
        if kind not in LAYERS or s.get("layer") != LAYERS[kind]:
            raise ValueError("unknown scenario kind/layer")
        if not isinstance(s.get("id"), str) or not s["id"] or s["id"] in ids:
            raise ValueError("invalid or duplicate scenario ID")
        ids.add(s["id"])
        if kind in ("layout", "scene", "pointer", "key", "route", "focus", "clip", "window"):
            if not numbers([s.get("width"), s.get("height")], 2) or not (0 < s["width"] <= 4096 and 0 < s["height"] <= 4096):
                raise ValueError("invalid bounded viewport")
        if kind in ("layout", "scene", "pointer", "key", "route", "focus"):
            children = s.get("children", [])
            child_count = len(children) if isinstance(children, list) else 0
            if kind == "layout":
                allowed_counts = (
                    tuple(range(5))
                    if s.get("justify", "start") == "space-between"
                    else (2, 3)
                )
            elif kind == "pointer":
                allowed_counts = (2, 3)
            else:
                allowed_counts = (2,)
            if kind == "layout":
                direction = s.get("direction", "row")
                main_index = 1 if direction == "column" else 0
                valid_children = all(
                    isinstance(c, list) and len(c) == 2 and c[main_index] is not None
                    and all(x is None or type(x) in (int, float) and math.isfinite(x) and 0 <= x <= 4096 for x in c)
                    for c in children
                )
            else:
                valid_children = all(numbers(c, 2, True) and max(c) <= 4096 for c in children)
            if not numbers([s.get("gap")], 1, True) or s["gap"] > 4096 or child_count not in allowed_counts or not valid_children:
                raise ValueError("first slice requires bounded children (two or three for layout/pointer; space-between layouts allow zero through four) and nonnegative gap")
        if kind == "layout":
            if s.get("direction", "row") not in ("row", "column") or s.get("justify", "start") not in ("start", "center", "end", "space-between") or s.get("align", "start") not in ("start", "center", "end", "stretch"):
                raise ValueError("unknown layout direction/alignment")
            if s.get("layout_observation", "bounds") not in ("bounds", "line_origins"):
                raise ValueError("unknown bounded layout observation")
            device_scale = s.get("device_scale_factor")
            if "device_scale_factor" in s and (
                type(device_scale) not in (int, float)
                or not math.isfinite(device_scale)
                or not 0 < device_scale <= 8
            ):
                raise ValueError("invalid bounded layout device scale")
            if s.get("wrap", "nowrap") not in ("nowrap", "wrap", "wrap_reverse"):
                raise ValueError("unknown bounded flex wrapping mode")
            child_count = len(s["children"])
            for field, default in (("grow", [0] * child_count), ("shrink", [1] * child_count)):
                if not numbers(s.get(field, default), child_count, True) or max(s.get(field, default), default=0) > 16:
                    raise ValueError("invalid bounded flex factors")
            minima = s.get("min_main", [0] * child_count)
            maxima = s.get("max_main", [None] * child_count)
            if not numbers(minima, child_count, True) or max(minima, default=0) > 4096:
                raise ValueError("invalid bounded main-axis minima")
            if not isinstance(maxima, list) or len(maxima) != child_count or any(
                x is not None and (type(x) not in (int, float) or not math.isfinite(x) or not 0 <= x <= 4096)
                for x in maxima
            ) or any(limit is not None and minimum > limit for minimum, limit in zip(minima, maxima)):
                raise ValueError("invalid bounded main-axis maxima")
            cross_minima = s.get("min_cross", [0] * child_count)
            cross_maxima = s.get("max_cross", [None] * child_count)
            if not numbers(cross_minima, child_count, True) or max(cross_minima, default=0) > 4096:
                raise ValueError("invalid bounded cross-axis minima")
            if not isinstance(cross_maxima, list) or len(cross_maxima) != child_count or any(
                x is not None and (type(x) not in (int, float) or not math.isfinite(x) or not 0 <= x <= 4096)
                for x in cross_maxima
            ) or any(limit is not None and minimum > limit for minimum, limit in zip(cross_minima, cross_maxima)):
                raise ValueError("invalid bounded cross-axis maxima")
        elif any(field in s for field in ("min_main", "max_main", "min_cross", "max_cross", "layout_observation", "device_scale_factor")):
            raise ValueError("layout-specific fields require a layout scenario")
        if kind == "pointer" and (s.get("wrap", "nowrap") not in ("nowrap", "wrap", "wrap_reverse") or not s.get("points") or any(not numbers(p, 2) for p in s["points"])):
            raise ValueError("invalid pointer samples")
        if kind == "key" and (not s.get("keys") or any(not isinstance(k, list) or len(k) != 6 or not isinstance(k[0], str) or len(k[0]) != 1 or any(type(x) is not bool for x in k[1:]) for k in s["keys"])):
            raise ValueError("invalid key samples")
        if kind in ("route", "focus"):
            stop = s.get("stop")
            if stop is not None and (not isinstance(stop, list) or len(stop) != 2 or type(stop[0]) is not int or stop[0] not in (1, 2, 3) or stop[1] not in ("capture", "bubble")):
                raise ValueError("invalid propagation stop")
        if kind == "route" and (not isinstance(s.get("points"), list) or not 1 <= len(s["points"]) <= 16 or any(not numbers(p, 2) or max(abs(x) for x in p) > 4096 for p in s["points"])):
            raise ValueError("invalid bounded routing points")
        if kind == "focus" and (not isinstance(s.get("focuses"), list) or not 1 <= len(s["focuses"]) <= 16 or any(x is not None and (type(x) is not int or x not in (1, 2, 3)) for x in s["focuses"]) or s.get("event") not in ("down", "up") or not isinstance(s.get("key"), str) or len(s["key"]) != 1 or not 32 <= ord(s["key"]) <= 126):
            raise ValueError("invalid bounded focus/key sequence")
        if kind == "clip" and (len(s.get("clips", [])) != 2 or any(not numbers(c, 4) or c[2] <= 0 or c[3] <= 0 for c in s["clips"])):
            raise ValueError("first slice requires two nonempty rectangle clips")
        if kind == "clip":
            if any(any(abs(x) > 4096 for x in c) for c in s["clips"]):
                raise ValueError("clip coordinates exceed first-slice bounds")
            rectangles = [[0, 0, s["width"], s["height"]], *s["clips"]]
            if max(c[0] for c in rectangles) >= min(c[0] + c[2] for c in rectangles) or max(c[1] for c in rectangles) >= min(c[1] + c[3] for c in rectangles):
                raise ValueError("first clip slice requires a nonempty effective intersection")
        if kind == "window" and (not numbers(s.get("resize"), 2) or not all(0 < x <= 4096 for x in s["resize"])):
            raise ValueError("invalid resize")
        if kind == "pixels" and "width" in s:
            if not numbers([s.get("width"), s.get("height")], 2) or not all(0 < x <= 1024 for x in (s["width"],s["height"])):
                raise ValueError("invalid native readback viewport")
            if not numbers(s.get("rect"), 4) or not all(x >= 0 for x in s["rect"]) or s["rect"][0]+s["rect"][2] > s["width"] or s["rect"][1]+s["rect"][3] > s["height"]:
                raise ValueError("invalid native rectangle")
            if any(not numbers(s.get(k),4) or any(type(x) is not int or not 0 <= x <= 255 for x in s[k]) or s[k][3] != 255 for k in ("background","color")):
                raise ValueError("native slice requires opaque RGBA8 colors")
            if not s.get("points") or any(not numbers(p,2) or not (0 <= p[0] < s["width"] and 0 <= p[1] < s["height"]) for p in s["points"]):
                raise ValueError("invalid native sample points")
    if any(s["kind"] == "pixels" and "width" in s for s in scenarios["cases"]):
        cases=scenarios["cases"]
        if len(cases)!=2 or [s["kind"] for s in cases] != ["window","pixels"] or any(cases[0][k] != cases[1][k] for k in ("width","height")):
            raise ValueError("native fixture requires ordered window/pixels cases sharing one initial viewport")


def valid_event_trace(value):
    return isinstance(value, list) and len(value) <= 6 and all(isinstance(e, list) and len(e) == 2 and type(e[0]) is int and e[0] in (1, 2, 3) and e[1] in ("capture", "bubble") for e in value)


def valid_observation(s, observation):
    if not isinstance(observation, dict):
        return False
    kind = s["kind"]
    if kind == "route":
        events = observation.get("events")
        return observation.keys() == {"events"} and isinstance(events, list) and len(events) == len(s["points"]) and all(valid_event_trace(v) for v in events) and any(events)
    if kind == "focus":
        steps = observation.get("steps")
        return observation.keys() == {"steps"} and isinstance(steps, list) and len(steps) == len(s["focuses"]) and all(isinstance(v, dict) and v.keys() == {"focused", "events"} and (v["focused"] is None or type(v["focused"]) is int and v["focused"] in (1, 2, 3)) and valid_event_trace(v["events"]) for v in steps) and any(v["events"] for v in steps)
    if kind == "layout":
        if s.get("layout_observation", "bounds") == "line_origins":
            origins = observation.get("line_origins")
            return observation.keys() == {"line_origins"} and numbers(origins, len(s["children"]))
        return observation.keys() == {"bounds"} and isinstance(observation["bounds"], list) and len(observation["bounds"]) == len(s["children"]) + 1 and all(numbers(r, 4) for r in observation["bounds"])
    if kind == "pointer":
        return observation.keys() == {"targets"} and isinstance(observation["targets"], list) and len(observation["targets"]) == len(s["points"]) and all(x is None or type(x) is int and 2 <= x < len(s["children"]) + 2 for x in observation["targets"])
    if kind == "scene":
        return observation.keys() == {"quads"} and isinstance(observation["quads"], list) and 0 < len(observation["quads"]) <= 32 and all(isinstance(q, dict) and q.keys() == {"bounds", "rgba"} and numbers(q["bounds"], 4) and numbers(q["rgba"], 4) and all(type(x) is int and 0 <= x <= 255 for x in q["rgba"]) for q in observation["quads"])
    if kind == "key":
        return observation.keys() == {"keys"} and isinstance(observation["keys"], list) and 0 < len(observation["keys"]) <= 256 and all(isinstance(k, list) and len(k) == 6 and isinstance(k[0], str) and all(type(x) is bool for x in k[1:]) for k in observation["keys"])
    if kind == "clip":
        return observation.keys() == {"effective_clip"} and numbers(observation["effective_clip"], 4)
    if kind == "window":
        return observation.keys() == {"initial", "resized", "live_before", "live_after"} and numbers(observation["initial"], 4) and numbers(observation["resized"], 4) and type(observation["live_before"]) is bool and type(observation["live_after"]) is bool
    if kind == "pixels" and "points" in s:
        return observation.keys() == {"width","height","scale","samples"} and type(observation["width"]) is int and type(observation["height"]) is int and 0 < observation["width"] <= 8192 and 0 < observation["height"] <= 8192 and numbers([observation["scale"]],1) and 0 < observation["scale"] <= 8 and isinstance(observation["samples"],list) and len(observation["samples"]) == len(s["points"]) and all(numbers(p,4) and all(type(x) is int and 0 <= x <= 255 for x in p) for p in observation["samples"])
    return False
