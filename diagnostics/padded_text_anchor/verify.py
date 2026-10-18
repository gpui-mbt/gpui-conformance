"""Validate prospective trace structure; never authenticate execution or create goldens."""
import json
import math
from pathlib import Path
import sys

UPSTREAM = '5a5fbe79917971a4d52a96b6ddb04da198a5012e'
BASELINE = '908f39d73b70b0c9d1bf59d8d3fc76e1e3506cf8'
BASELINE_TREE = 'de80e7d598470a75cc052c951848391551dba813'
FIXTURE = Path(__file__).with_name('scenarios.json')
BASE_NODES = {'host', 'primary', 'primary_text', 'primary_anchor_static', 'parent', 'parent_text', 'secondary', 'secondary_text'}
CHILD_NODES = {'secondary_anchor_static', 'child', 'child_text'}

def require(condition, message):
    if not condition:
        raise ValueError(message)

def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, 'duplicate JSON key')
        result[key] = value
    return result

def load(path):
    return json.loads(Path(path).read_text(), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))

def number(value):
    return type(value) in (int, float) and math.isfinite(value)

def json_equal(left, right):
    """JSON equality with booleans distinct from numbers, at every depth.

    Finite int/float equivalents are allowed for geometry; schema versions and
    frame/sequence counters additionally have explicit integer checks.
    """
    if number(left) or number(right):
        return number(left) and number(right) and left == right
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(json_equal(left[k], right[k]) for k in left)
    if type(left) is list:
        return len(left) == len(right) and all(json_equal(a, b) for a, b in zip(left, right))
    return type(left) in (str, bool, type(None)) and left == right

def rectangle(value):
    return isinstance(value, list) and len(value) == 4 and all(number(v) for v in value) and all(v >= 0 for v in value[2:])

def check_frame(rows, step):
    nodes = BASE_NODES | (CHILD_NODES if step['nested_open'] else set())
    pre, paint, hit, text = {}, {}, {}, {}
    starts = [e for e in rows if e['type'] == 'frame_start']
    require(len(starts) == 1 and rows[0]['type'] == 'frame_start', 'frame start')
    require(json_equal(starts[0]['viewport'], step['viewport']) and json_equal(starts[0]['scale'], step['scale']), 'settled viewport/scale')
    returns = []
    for i, event in enumerate(rows):
        kind = event['type']
        if kind in ('prepaint', 'paint'):
            table = pre if kind == 'prepaint' else paint
            node = event['node']
            require(node in nodes and node not in table and rectangle(event['bounds']), 'node bounds')
            table[node] = (i, event['bounds'])
        elif kind == 'hitbox':
            node = event['node']
            require(node in {'primary', 'secondary', 'parent', 'child'} and node not in hit, 'hitbox identity')
            require(rectangle(event['bounds']) and rectangle(event['content_mask']), 'hitbox rectangle')
            hit[node] = (i, event['bounds'])
        elif kind == 'text_inputs':
            node = event['node']
            require(node in nodes and node.endswith('_text') and node not in text, 'text identity')
            require(isinstance(event['font_family'], str) and event['font_family'], 'font family')
            for key in ('font_size', 'rem_size', 'line_height', 'units_per_em', 'ascent', 'descent', 'em_advance'):
                require(number(event[key]), 'finite font metric')
            require(all(event[k] > 0 for k in ('font_size', 'rem_size', 'line_height', 'units_per_em', 'em_advance')), 'positive font metric')
            text[node] = event
        elif kind == 'host_paint_return':
            returns.append(i)
        else:
            require(kind == 'frame_start', 'unknown frame event')
    require(set(pre) == nodes and set(paint) == nodes, 'complete observed nodes')
    require(set(text) == {n for n in nodes if n.endswith('_text')}, 'complete text inputs')
    require(len(returns) == 1, 'host paint return')
    for node in nodes:
        require(pre[node][0] < paint[node][0], 'prepaint before paint')
    require(paint['host'][0] < returns[0] < paint['parent'][0], 'ordinary/deferred paint ordering')
    # Parent may have no hitbox while nested open: its outside listener is absent.
    required_hit = {'primary', 'secondary'} | ({'child'} if step['nested_open'] else {'parent'})
    require(required_hit <= set(hit), 'actual interactive hitboxes')
    for node, (i, bounds) in hit.items():
        require(node in pre and pre[node][0] < i < paint[node][0], 'hitbox prepaint chronology')
        require(bounds == pre[node][1], 'actual hitbox/prepaint bounds')
    # Report reference deltas without asserting guessed content/border-box formulas.
    deltas = {}
    for owner, anchor, popup, label in [('primary','primary_anchor_static','parent','primary'),('secondary','secondary_anchor_static','child','secondary')]:
        if anchor not in pre:
            continue
        owner_b, anchor_b, popup_b = pre[owner][1], pre[anchor][1], pre[popup][1]
        deltas[label] = {
            'anchor_minus_owner_origin': [anchor_b[i]-owner_b[i] for i in (0,1)],
            'popup_minus_static_origin': [popup_b[i]-anchor_b[i] for i in (0,1)],
            'owner_bounds': owner_b, 'static_bounds': anchor_b, 'popup_bounds': popup_b,
        }
    return {'reference_deltas': deltas, 'font_inputs': text}

def verify(raw, fixture=None):
    fixture = load(FIXTURE) if fixture is None else fixture
    require(type(raw.get('schema_version')) is int and raw['schema_version'] == 1, 'schema')
    require(raw.get('layer') == 'source-derived-padded-text-anchor', 'layer')
    require(raw.get('upstream_revision') == UPSTREAM, 'upstream declaration')
    require(raw.get('text_backend') == 'upstream-NoopTextSystem', 'font backend declaration')
    require(isinstance(raw.get('run_token'), str) and raw['run_token'], 'run token')
    require(type(raw.get('input')) is dict and type(raw['input'].get('schema_version')) is int, 'input schema type')
    require(json_equal(raw['input'], fixture), 'frozen typed fixture')
    variants = raw.get('variants')
    require(isinstance(variants, list) and [v['variant'] for v in variants] == fixture['variants'], 'variants')
    summaries = []
    for variant in variants:
        events = variant['events']
        require(isinstance(events, list) and events, 'nonempty trace')
        index, current, frames, last_frame = 0, None, {}, 0
        results = []
        for seq, row in enumerate(events):
            require(type(row['sequence']) is int and row['sequence'] == seq, 'sequence')
            require(type(row['frame']) is int and row['frame'] >= last_frame, 'frame monotonicity')
            last_frame = row['frame']
            event = row['event']; kind = event['type']
            if kind == 'operation_start':
                require(current is None and index < len(fixture['steps']), 'operation nesting')
                current = fixture['steps'][index]
                require(row['operation'] == current['id'] and json_equal({k:event[k] for k in ('viewport','scale','nested_open')}, {k:current[k] for k in ('viewport','scale','nested_open')}), 'operation input')
                require(type(event['nested_open']) is bool, 'boolean nested state')
                frames = {}
            elif kind == 'operation_end':
                require(current is not None and row['operation'] == current['id'] and frames, 'operation end')
                # All raw frames remain available. The last one is the settled state;
                # intermediate callbacks may schedule frames during resize/scale changes.
                summary = check_frame(frames[max(frames)], current)
                results.append({'operation':current['id'], 'frames':len(frames), **summary})
                index += 1; current = None
            else:
                require(kind in {'frame_start','text_inputs','prepaint','paint','hitbox','host_paint_return'}, 'event kind')
                if current is None:
                    require(index == 0 and row['operation'] == 'bootstrap', 'unbracketed event')
                else:
                    require(row['operation'] == current['id'], 'operation tag')
                    frames.setdefault(row['frame'], []).append(event)
        require(current is None and index == len(fixture['steps']), 'complete operations')
        summaries.append({'variant':variant['variant'], 'operations':results})
    return {'status':'trace_shape_valid', 'execution_authenticated':False,
            'observed_numeric_goldens':None, 'attachment_reference_hypothesis_confirmed':None,
            'font_parity':False, 'unchanged_example_parity':False, 'variants':summaries}

if __name__ == '__main__':
    print(json.dumps(verify(load(sys.argv[1])), indent=2, allow_nan=False))
