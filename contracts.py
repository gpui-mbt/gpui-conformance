"""Bounded first-slice input and observation contracts."""
import math

LAYERS = {"layout": "headless-layout", "pointer": "headless-dispatch", "key": "headless-dispatch",
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
        if kind in ("layout", "scene", "pointer", "key", "clip", "window"):
            if not numbers([s.get("width"), s.get("height")], 2) or not (0 < s["width"] <= 4096 and 0 < s["height"] <= 4096):
                raise ValueError("invalid bounded viewport")
        if kind in ("layout", "scene", "pointer", "key"):
            if not numbers([s.get("gap")], 1, True) or s["gap"] > 4096 or len(s.get("children", [])) != 2 or any(not numbers(c, 2, True) or max(c) > 4096 for c in s["children"]):
                raise ValueError("first slice requires two bounded children and nonnegative gap")
        if kind == "pointer" and (not s.get("points") or any(not numbers(p, 2) for p in s["points"])):
            raise ValueError("invalid pointer samples")
        if kind == "key" and (not s.get("keys") or any(not isinstance(k, list) or len(k) != 6 or not isinstance(k[0], str) or len(k[0]) != 1 or any(type(x) is not bool for x in k[1:]) for k in s["keys"])):
            raise ValueError("invalid key samples")
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


def valid_observation(s, observation):
    if not isinstance(observation, dict):
        return False
    kind = s["kind"]
    if kind == "layout":
        return observation.keys() == {"bounds"} and isinstance(observation["bounds"], list) and len(observation["bounds"]) == 3 and all(numbers(r, 4) for r in observation["bounds"])
    if kind == "pointer":
        return observation.keys() == {"targets"} and isinstance(observation["targets"], list) and len(observation["targets"]) == len(s["points"]) and all(x is None or type(x) is int and x in (2, 3) for x in observation["targets"])
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
