#!/usr/bin/env python3
"""Inspect every raw frame, then compare final semantic states per operation.

The candidate adapter observes production APIs. This checker never synthesizes
candidate geometry or accepts fixture-final rectangles as engine observations.
Rust callbacks and candidate routed events remain separately named evidence.
"""
from __future__ import annotations
import copy
import importlib.util
import json
from jsonschema import Draft202012Validator, ValidationError
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('anchor_baseline_verify', ROOT / 'diagnostics/anchor/verify.py')
baseline = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(baseline)
require = baseline.require
CANDIDATE_LAYER = 'compiled-moonbit-anchor-deferred'
LAYER = 'supplemental-font-free-anchor-semantic-pair'
# Reuse the reviewed fixed-corpus domain and allowance, without fitting output.
# The independent candidate uses Double internally. Its conversion error at this
# bounded domain is far below the unused 2^-10 - 0.0006103515625 margin.
TOLERANCE = baseline.GEOMETRY_F32_ALLOWANCE


def load_json(text):
    """Reject duplicate object keys and non-JSON NaN/Infinity at transport ingress."""
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    def constant(value):
        raise ValueError('non-JSON numeric constant: ' + value)
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def validate_schema(raw, path):
    schema = load_json(path.read_text())
    try:
        Draft202012Validator(schema).validate(raw)
    except ValidationError as error:
        raise ValueError('raw schema: ' + error.message) from error



def shape(value, fields, label):
    require(isinstance(value, dict) and set(value) == set(fields), label + ': fields')


def operations(case):
    return [('initial', {'action': 'open_window'}),
        ('configured', {'action': 'set_scale_factor', 'scale_factor': case['scale_factor']})] + [
        (hit['id'], {'action': 'click', 'position': hit['position']}) for hit in case['hits']]


def topology(case):
    """Actual candidate structure; invisible positioning boxes are still checked."""
    nodes = {}
    def add(name, parent, interactive=False, painted=False):
        nodes[name] = {'id': str(len(nodes) + 1), 'parent': parent,
                       'interactive': interactive, 'painted': painted}
    add('$host', None)
    add('$parent_position', '$host')
    add('parent', '$parent_position')
    add('button', 'parent', True, True)
    for popup in case['popups']:
        add('anchor_' + popup['id'], 'parent')
        add(popup['id'], 'anchor_' + popup['id'], popup['interactive'], True)
    if case['later_sibling'] is not None:
        add('$sibling_position', '$host')
        add('sibling', '$sibling_position', True, True)
    return nodes


def scene_order(case):
    return ['button'] + (['sibling'] if case['later_sibling'] is not None else []) + [p['id'] for p in case['popups']]


def inspect_scene(commands, observed, case):
    """Validate structural stack balance separately from semantic clip coverage."""
    stack, leaves, clips = [], [], {}
    nodes = topology(case)
    for event in commands:
        kind, name = event['kind'], event['node']
        require(name in observed, 'scene unknown node')
        if kind == 'clip_push':
            baseline.qualify_bounds(event['bounds'], 'scene clip')
            stack.append((name, event['bounds']))
        elif kind == 'clip_pop':
            require(event['bounds'] is None and stack and stack[-1][0] == name, 'unbalanced scene clip return')
            stack.pop()
        else:
            require(kind == 'quad' and nodes[name]['painted'], 'unexpected scene command')
            baseline.vector(event['bounds'], observed[name], 'scene/tree bounds', 0)
            leaves.append(name)
            clips[name] = list(stack)
    require(not stack, 'unclosed scene clip')
    require(leaves == scene_order(case), 'ordinary/deferred scene order')
    expected = [('quad', 'button')]
    if case['later_sibling'] is not None: expected.append(('quad', 'sibling'))
    for popup in case['popups']:
        name = popup['id']
        expected.extend([('clip_push', 'anchor_' + name), ('quad', name), ('clip_pop', 'anchor_' + name)])
        own = ('anchor_' + name, [0, 0, *case['window']])
        # An outer root viewport clip may remain open across deferred traversal
        # or close at the ordinary-pass boundary. Equal nested masks have the
        # same effective region; the attachment must retain its own actual clip.
        require(clips[name] in ([own], [('$host', [0, 0, *case['window']]), own]), 'popup effective viewport clip')
    require([(event['kind'], event['node']) for event in commands if event['node'] != '$host'] == expected, 'flat deferred scene structure')
    require([event['kind'] for event in commands if event['node'] == '$host'] == ['clip_push', 'clip_pop'], 'root viewport clip coverage')
    require(all(clips[name] == [('$host', [0, 0, *case['window']])] for name in leaves if name in ('button', 'sibling')), 'ordinary effective viewport clip')
    return leaves, {name: clips[name][-1][1] for name in leaves}


def verify_frame(entries, case, scale):
    label = case['id'] + '/candidate-frame-' + str(entries[0]['frame'])
    nodes, observed, scenes, probes = topology(case), {}, [], []
    phase, overflow = 'start', None
    for entry in entries:
        event = entry['event']
        kind = event['type']
        if kind in ('frame_start', 'frame_end'):
            shape(event, ['type', 'scale_factor', 'window_size'], label)
            require(event['scale_factor'] == scale, label + ': exact scale')
            baseline.vector(event['window_size'], case['window'], label + ': viewport', 0)
            if kind == 'frame_start':
                require(phase == 'start', label + ': repeated frame start')
                phase = 'request_start'
            else:
                require(phase == 'probes', label + ': incomplete frame')
                phase = 'done'
        elif kind in ('request_start', 'request_end', 'prepaint_start'):
            shape(event, ['type'], label)
            require(phase == kind, label + ': lifecycle order')
            phase = {'request_start': 'request_end', 'request_end': 'prepaint_start', 'prepaint_start': 'prepaint_end'}[kind]
        elif kind == 'prepaint_end':
            shape(event, ['type', 'overflow'], label)
            require(phase == 'prepaint_end' and type(event['overflow']) is bool, label + ': prepaint result')
            overflow, phase = event['overflow'], 'nodes'
        elif kind == 'node':
            shape(event, ['type', 'node', 'id', 'parent', 'bounds', 'pointer_events', 'focusable'], label)
            name = event['node']
            require(phase == 'nodes' and name in nodes and name not in observed, label + ': node identity/count/order')
            require(event['id'] == nodes[name]['id'] and event['parent'] == nodes[name]['parent'], label + ': structural lineage')
            require(type(event['pointer_events']) is bool and type(event['focusable']) is bool and
                    event['pointer_events'] == event['focusable'] == nodes[name]['interactive'], label + ': interactive state')
            baseline.physical_grid(event['bounds'], scale, label + '/' + name)
            observed[name] = event['bounds']
        elif kind == 'scene':
            shape(event, ['type', 'kind', 'node', 'bounds'], label)
            require(phase in ('nodes', 'scene'), label + ': scene lifecycle')
            phase = 'scene'
            scenes.append(event)
        elif kind == 'viewport_hit':
            shape(event, ['type', 'side', 'position', 'target'], label)
            require(phase in ('scene', 'probes'), label + ': viewport probe order')
            phase = 'probes'
            probes.append(event)
        else:
            require(False, label + ': unknown event ' + kind)
    require(phase == 'done' and list(observed) == list(nodes), label + ': complete structural preorder')
    leaves, masks = inspect_scene(scenes, observed, case)
    width, height = case['window']
    require(probes == [
        {'type': 'viewport_hit', 'side': 'right', 'position': [width + 1, height / 2], 'target': None},
        {'type': 'viewport_hit', 'side': 'bottom', 'position': [width / 2, height + 1], 'target': None}],
        label + ': candidate-only outside-viewport hit rejection')
    # Parent, child and static attachment are all independently observed engine
    # outputs. The cross-engine comparison below checks their coordinates.
    return {'frame': entries[0]['frame'], 'scale_factor': scale, 'bounds': observed,
            'painted_leaves': leaves, 'effective_masks': masks, 'overflow': overflow, 'logical_viewport': [0, 0, *case['window']]}


def lineage(target, nodes):
    result = []
    while target is not None:
        require(target in nodes and target not in result, 'route unknown/cyclic target')
        result.append(target)
        target = nodes[target]['parent']
    return result


def context_projection(path, target):
    """Compare semantic ancestry, retaining all real wrapper nodes in raw data."""
    mapping = {'$host': 'AnchorRoot', 'parent': 'AnchorParent'}
    if target is not None: mapping[target] = 'Leaf_' + target
    return [mapping[node] for node in path if node in mapping]


def verify_route(event, action, position, nodes, frame):
    shape(event, ['type', 'action', 'position', 'hit_test', 'target', 'capture', 'bubble',
                  'callback_capture', 'callback_bubble', 'focused_target', 'focused_capture', 'focused_bubble'], 'route')
    require(event['action'] == action, 'route action')
    baseline.vector(event['position'], position, 'route position', 0)
    target = event['target']
    require(target is None or target in nodes and nodes[target]['interactive'], 'route noninteractive/unknown target')
    path = lineage(target, nodes)
    require(event['bubble'] == path and event['capture'] == path[::-1], 'route structural lineage')
    require(event['callback_capture'] == event['capture'] and event['callback_bubble'] == event['bubble'], 'actual dispatch callback traversal')
    require(event['hit_test'] == target, 'hit-test/input route disagreement')
    require(event['focused_target'] == target and event['focused_capture'] == path[::-1] and event['focused_bubble'] == path,
            'focused dispatch structural lineage')
    interactive = [name for name in frame['painted_leaves'] if nodes[name]['interactive']]
    for name in interactive:
        require(not baseline.on_edge(position, frame['bounds'][name]), 'edge hit excluded from bounded contract')
    require(not baseline.on_edge(position, frame['logical_viewport']), 'viewport edge excluded')
    eligible = [name for name in interactive if baseline.inside(position, frame['bounds'][name]) and baseline.inside(position, frame['logical_viewport'])]
    require(target == (eligible[-1] if eligible else None), 'reverse painted interactive hit order')
    return {'target': target, 'contexts': context_projection(event['focused_capture'], target)}


def extension_input(corpus):
    original = next((case for case in corpus['cases'] if case['id'] == 'oversized-popup'), None)
    require(original is not None, 'candidate-only oversized source case required')
    case = copy.deepcopy(original)
    case['id'] = 'candidate-only-interactive-oversized'
    for popup in case['popups']: popup['interactive'] = True
    return case


def verify_candidate(raw, corpus, extensions=None):
    if extensions is None: extensions = "candidate_only" in raw
    baseline.validate_scenarios(corpus)
    validate_schema(raw, ROOT / 'diagnostics/anchor_pair/raw.schema.json')
    shape(raw, ['schema_version', 'layer', 'fixture', 'input', 'run_token', 'cases'] + (['candidate_only'] if extensions else []), 'candidate')
    require(raw['schema_version'] == 1 and raw['layer'] == CANDIDATE_LAYER and raw['fixture'] == 'font-free-bounded-anchor', 'candidate identity')
    require(isinstance(raw['run_token'], str) and len(raw['run_token']) >= 16 and raw['input'] == corpus, 'candidate token/input')
    require([item['id'] for item in raw['cases']] == [case['id'] for case in corpus['cases']], 'candidate case coverage/order')
    results = []
    for observed, case in zip(raw['cases'], corpus['cases']):
        shape(observed, ['id', 'events'], 'candidate case')
        events, nodes = observed['events'], topology(case)
        require([entry['sequence'] for entry in events] == list(range(len(events))), 'candidate event sequence')
        for entry in events: shape(entry, ['sequence', 'frame', 'operation', 'event'], 'entry')
        cursor, frame_number, latest, parsed = 0, 0, None, []
        for operation, input_value in operations(case):
            require(cursor < len(events), 'missing candidate operation')
            start = events[cursor]; cursor += 1
            require(start['operation'] == operation and start['frame'] == frame_number and
                    start['event'] == {'type': 'operation_start', 'input': input_value}, 'candidate operation start')
            frames, routes, pending = [], [], None
            hit_frame = latest
            scale = 2 if operation == 'initial' else case['scale_factor']
            while cursor < len(events) and events[cursor]['event']['type'] != 'operation_end':
                entry = events[cursor]; cursor += 1
                event = entry['event']
                require(entry['operation'] == operation, 'candidate operation interleaving')
                if event['type'] == 'frame_start':
                    require(pending is None, 'nested candidate frame')
                    frame_number += 1
                    pending = []
                require(entry['frame'] == frame_number, 'candidate frame numbering')
                if pending is not None:
                    pending.append(entry)
                    if event['type'] == 'frame_end':
                        latest = verify_frame(pending, case, scale)
                        frames.append(latest)
                        pending = None
                elif event['type'] == 'route':
                    require(input_value['action'] == 'click' and len(routes) < 2 and hit_frame is not None, 'unexpected route')
                    routes.append(verify_route(event, ('down', 'up')[len(routes)], input_value['position'], nodes, hit_frame))
                else: require(False, 'candidate event outside frame')
            require(cursor < len(events) and pending is None, 'unfinished candidate operation/frame')
            end = events[cursor]; cursor += 1
            require(end['operation'] == operation and end['frame'] == frame_number and
                    end['event'] == {'type': 'operation_end', 'scale_factor': scale}, 'candidate operation end')
            if operation in ('initial', 'configured'): require(frames and not routes, 'required candidate redraw')
            else: require(len(routes) == 2 and routes[0] == routes[1], 'incomplete/inconsistent candidate down/up')
            parsed.append({'id': operation, 'frames': frames, 'final': latest, 'routes': routes})
        require(cursor == len(events), 'candidate trailing events')
        results.append({'id': case['id'], 'operations': parsed})
    if extensions:
        extension = raw['candidate_only']
        shape(extension, ['kind', 'source_case_id', 'input', 'observation'], 'candidate-only extension')
        require(extension['kind'] == 'interactive-oversized-viewport-contract' and extension['source_case_id'] == 'oversized-popup', 'candidate-only extension identity')
        require(extension['input'] == extension_input(corpus), 'candidate-only extension must change only identity and authored interactivity')
        extension_corpus = dict(corpus, cases=[extension['input']])
        extension_raw = {key: value for key, value in raw.items() if key != 'candidate_only'}
        extension_raw.update(input=extension_corpus, cases=[extension['observation']])
        try:
            verify_candidate(extension_raw, extension_corpus, extensions=False)
        except (ValueError, KeyError, TypeError, IndexError) as error:
            raise CandidateOnlyContractError('candidate-only interactive viewport contract: ' + str(error)) from error
    return results


class CandidateOnlyContractError(ValueError):
    """A separately authored core-contract failure, never a Rust-paired kill."""


def compare_observations(rust, candidate, corpus, rust_verifier=baseline.verify_observations):
    validate_schema(rust, ROOT / 'diagnostics/anchor/raw.schema.json')
    original = rust_verifier(rust, corpus)['cases']
    replacement = verify_candidate(candidate, corpus)
    mismatches, result, maximum = [], [], 0.0
    counts = {'cases': 0, 'rust_frames': 0, 'candidate_frames': 0, 'compared_operations': 0, 'paired_clicks': 0,
              'transparent_or_nonoverlapping_outside_probes': 0,
              'candidate_only_interactive_cases': int('candidate_only' in candidate), 'candidate_only_interactive_viewport_probes': 4 if 'candidate_only' in candidate else 0}
    rust_masks = {(observed['id'], entry['frame'], entry['event']['node']): entry['event']['content_mask']
                  for observed in rust['cases'] for entry in observed['events'] if entry['event']['type'] == 'prepaint'}
    for left, right, case in zip(original, replacement, corpus['cases']):
        counts['cases'] += 1
        latest, pairs = None, []
        for rust_op, candidate_op in zip(left['operations'], right['operations']):
            require(rust_op['id'] == candidate_op['id'], 'operation coverage')
            counts['rust_frames'] += len(rust_op['frames'])
            counts['candidate_frames'] += len(candidate_op['frames'])
            counts['transparent_or_nonoverlapping_outside_probes'] += 2 * len(candidate_op['frames'])
            counts['compared_operations'] += 1
            if rust_op['frames']: latest = rust_op['frames'][-1]
            current = candidate_op['final']
            def check(field, a, b, numeric=False):
                nonlocal maximum
                try:
                    if numeric:
                        if len(a) == len(b): maximum = max(maximum, *(abs(x - y) for x, y in zip(a, b)))
                        baseline.vector(a, b, field, TOLERANCE)
                    else: require(a == b, field + ': different values')
                except ValueError as error:
                    mismatches.append({'case': left['id'], 'operation': rust_op['id'], 'field': field,
                                       'rust': a, 'candidate': b, 'error': str(error)})
            check('scale_factor', latest['scale_factor'], current['scale_factor'])
            for node, bounds in latest['bounds'].items():
                # GPUI's deferred wrapper delegates exactly the same layout ID
                # as its anchored child. The candidate has one attachment node.
                if node.startswith('deferred_'): continue
                check('bounds/' + node, bounds, current['bounds'].get(node, []), True)
            expected_paint = [name for name in latest['painted_nodes'] if topology(case).get(name, {}).get('painted')]
            check('painted_leaves', expected_paint, current['painted_leaves'])
            for name in current['painted_leaves']:
                check('effective_mask/' + name, rust_masks[left['id'], latest['frame'], name], current['effective_masks'][name])
            callbacks = rust_op['callbacks']
            routes = candidate_op['routes']
            check('rust_callbacks_vs_candidate_routes', [callback['node'] for callback in callbacks],
                  [route['target'] for route in routes if route['target'] is not None])
            check('focused_dispatch_contexts', [callback['contexts'] for callback in callbacks],
                  [route['contexts'] for route in routes if route['target'] is not None])
            if routes: counts['paired_clicks'] += 1
            pairs.append({'id': rust_op['id'], 'rust_frame_ids': [f['frame'] for f in rust_op['frames']],
                          'candidate_frame_ids': [f['frame'] for f in candidate_op['frames']],
                          'compared_rust_frame': latest['frame'], 'compared_candidate_frame': current['frame'],
                          'scale_factor': current['scale_factor']})
        result.append({'id': left['id'], 'operations': pairs})
    return {'schema_version': 1, 'layer': LAYER, 'passed': not mismatches, 'counts': counts,
        'cases': result, 'mismatches': mismatches, 'numeric_policy': {
            'absolute_logical_allowance': TOLERANCE, 'physical_grid_allowance': baseline.PHYSICAL_GRID_F32_ALLOWANCE,
            'raw_coordinate_limit': baseline.RAW_COORDINATE_LIMIT, 'raw_size_limit': baseline.RAW_SIZE_LIMIT,
            'raw_far_edge_limit': baseline.RAW_FAR_EDGE_LIMIT, 'maximum_observed_difference': maximum,
            'basis': 'Frozen corpus and reviewed f32 domain bound; no output normalization or fitted allowance.'},
        'frame_policy': 'Validate every raw frame; compare final state per operation, inheriting previous state when no redraw occurs. Redraw counts are never paired.',
        'claim': 'Bounded supplemental actual-GPUI/production-MoonBit geometry, scene, hit and dispatch pair; no unchanged-example, native-window, native click callback, font, screenshot, browser pixel, OS input or backend parity.'}


def require_semantic_match(comparison):
    require(comparison['passed'], 'actual pair mismatch; retain comparison and both raw traces')


def validate_mutation_outcomes(results):
    require(results and all(item['outcome'] == ({'candidate-only-core-contract': 'executed-candidate-only-contract-rejection', 'fractional-viewport-rust-pair': 'executed-fractional-viewport-semantic-rejection'}.get(item.get('scope'), 'executed-semantic-rejection')) for item in results),
            'every production control must compile, execute and fail semantics; transport/build/crash/timeout is not a kill')
