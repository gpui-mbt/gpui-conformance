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
        return observation.keys() == {"initial", "resized", "count_before", "count_after"} and numbers(observation["initial"], 4) and numbers(observation["resized"], 4) and type(observation["count_before"]) is int and type(observation["count_after"]) is int
    return False  # Native pixels/IME observations require a future reviewed contract.
