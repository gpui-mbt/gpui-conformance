#!/usr/bin/env python3
"""Strict semantic comparison, with raw frame histories retained independently.

This module never solves tracks or synthesizes expected coordinates. It validates
candidate production observations and pairs final states per operation with the
independently validated actual-Rust trace. A click target means the leaf target
of the candidate's actual down/up route, not a claimed native click callback.
"""
from __future__ import annotations
import importlib.util
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('grid_baseline_verify', ROOT / 'diagnostics/grid_layout/verify.py')
baseline = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(baseline)
require = baseline.require
CANDIDATE_LAYER = 'compiled-moonbit-grid-container-query'
LAYER = 'supplemental-font-free-grid-semantic-pair'
UNSUPPORTED = {'explicit-collision': 'explicit-grid-line-placement'}
# The frozen corpus is bounded to |coordinates, far edges, sizes| <= 1024.
# Float32 ULP at 1024 is 2^-13. Two such ULPs cover rounded edge division
# and subtraction (three half-ULP roundings), with no coordinate re-rounding.
MAX_COORDINATE = 1024.0
TOLERANCE = 2.0 ** -12  # 0.000244140625 logical pixels; not an engine-fit epsilon.


def shape(value, expected, label):
    require(isinstance(value, dict) and set(value) == set(expected), label + ': fields')


def vector(actual, expected, label):
    require(isinstance(actual, list) and len(actual) == len(expected), label + ': vector')
    for index, (a, b) in enumerate(zip(actual, expected)):
        require(type(a) in (int, float) and math.isfinite(a), label + ': finite')
        require(abs(a - b) <= TOLERANCE, f'{label}[{index}]: {a} != {b}')


def bounded_geometry(values, label, rectangle=False):
    numbers = list(values)
    if rectangle: numbers += [values[0] + values[2], values[1] + values[3]]
    require(all(type(value) in (int, float) and math.isfinite(value) and abs(value) <= MAX_COORDINATE for value in numbers),
            label + ': outside explicit numeric comparison domain')


def topology(case):
    result = {'$host': {'kind': 'host', 'parent': None, 'numeric_id': '1'}}
    def walk(node, parent):
        result[node['id']] = dict(node, parent=parent, numeric_id=str(len(result) + 1))
        for child in node.get('children', []): walk(child, node['id'])
    walk(case['root'], '$host')
    return result


def operations(case):
    return [('initial', {'action': 'open_window'}),
        ('configured', {'action': 'set_scale_factor', 'scale_factor': case['scale_factor']})] + [
        (hit['id'], {'action': 'click', 'position': hit['position']}) for hit in case['hits']]


def verify_frame(entries, case, scale):
    label = case['id'] + '/candidate-frame-' + str(entries[0]['frame'])
    nodes = topology(case)
    callbacks, observed, scene = {}, {}, []
    phase = 'start'
    for entry in entries:
        event = entry['event']
        kind = event['type']
        if kind == 'frame_start':
            require(phase == 'start', label + ': repeated frame start')
            phase = 'request_start'
        elif kind == 'request_start':
            require(phase == 'request_start', label + ': request start order')
            shape(event, ['type'], label)
            phase = 'request_end'
        elif kind == 'request_end':
            require(phase == 'request_end', label + ': request end order')
            shape(event, ['type', 'callback_count'], label)
            require(event['callback_count'] == 0, label + ': eager callback')
            phase = 'prepaint_start'
        elif kind == 'prepaint_start':
            require(phase == 'prepaint_start', label + ': prepaint start order')
            shape(event, ['type'], label)
            phase = 'callbacks'
        elif kind == 'callback':
            require(phase == 'callbacks', label + ': callback outside actual prepaint')
            shape(event, ['type', 'node', 'size'], label)
            name = event['node']
            require(name in nodes and nodes[name]['kind'] == 'query' and name not in callbacks, label + ': callback identity/count')
            vector(event['size'], event['size'], label + ': callback size')
            bounded_geometry(event['size'], label + ': callback size')
            require(len(event['size']) == 2, label + ': callback dimensions')
            callbacks[name] = event['size']
        elif kind == 'prepaint_end':
            require(phase == 'callbacks', label + ': prepaint end order')
            shape(event, ['type', 'callback_count', 'overflow'], label)
            require(event['callback_count'] == len(callbacks) and type(event['overflow']) is bool, label + ': prepaint result')
            overflow = event['overflow']
            phase = 'nodes'
        elif kind == 'node':
            require(phase == 'nodes', label + ': node outside published tree')
            shape(event, ['type', 'node', 'id', 'parent', 'bounds'], label)
            name = event['node']
            require(name in nodes and name not in observed, label + ': node identity/count')
            require(event['parent'] == nodes[name]['parent'] and event['id'] == nodes[name]['numeric_id'], label + ': node lineage')
            rect = event['bounds']
            require(isinstance(rect, list) and len(rect) == 4 and min(rect[2:]) >= 0, label + ': bounds shape')
            vector(rect, rect, label + ': bounds')
            bounded_geometry(rect, label + ': bounds', rectangle=True)
            for edge in (rect[0], rect[1], rect[0] + rect[2], rect[1] + rect[3]):
                require(abs(edge * scale - round(edge * scale)) <= TOLERANCE, label + ': unsnapped device edge')
            observed[name] = rect
        elif kind == 'scene':
            require(phase in ('nodes', 'scene'), label + ': scene order')
            phase = 'scene'
            shape(event, ['type', 'kind', 'node', 'bounds'], label)
            require(event['kind'] == 'quad' and event['node'] in observed and nodes[event['node']]['kind'] == 'box', label + ': unexpected scene command')
            vector(event['bounds'], observed[event['node']], label + ': scene/tree bounds')
            scene.append(event['node'])
        elif kind == 'frame_end':
            require(phase in ('nodes', 'scene'), label + ': frame end order')
            phase = 'done'
        else: require(False, label + ': unknown event ' + kind)
        if kind in ('frame_start', 'frame_end'):
            shape(event, ['type', 'scale_factor', 'window_size'], label)
            require(event['scale_factor'] == scale, label + ': scale')
            vector(event['window_size'], case['window'], label + ': window')
    require(phase == 'done', label + ': incomplete frame')
    require(list(observed) == list(nodes), label + ': node preorder/coverage')
    require(list(callbacks) == [name for name, node in nodes.items() if node['kind'] == 'query'], label + ': callback preorder/coverage')
    require(scene == [name for name, node in nodes.items() if node['kind'] == 'box'], label + ': quad preorder/coverage')
    for name, assigned in callbacks.items():
        vector(assigned, observed[name][2:], label + ': callback assigned allocation')
        child = nodes[name]['children'][0]['id']
        vector(observed[child][:2], observed[name][:2], label + ': generated origin')
    return {'frame': entries[0]['frame'], 'scale_factor': scale, 'bounds': observed,
            'callbacks': callbacks, 'painted_leaf_ids': scene, 'overflow': overflow}


def verify_route(event, action, position, nodes):
    shape(event, ['type', 'action', 'position', 'target', 'capture', 'bubble'], 'route')
    require(event['action'] == action, 'route action')
    vector(event['position'], position, 'route position')
    target = event['target']
    require(target is None or target in nodes, 'route unknown target')
    lineage = []
    node = target
    while node is not None:
        lineage.append(node)
        node = nodes[node]['parent']
    require(event['bubble'] == lineage and event['capture'] == lineage[::-1], 'route lineage')
    return target


def verify_candidate(raw, corpus):
    baseline.validate_scenarios(corpus)
    shape(raw, ['schema_version', 'layer', 'fixture', 'input', 'run_token', 'cases'], 'candidate')
    require(raw['schema_version'] == 1 and raw['layer'] == CANDIDATE_LAYER and raw['fixture'] == 'font-free-bounded-grid', 'candidate identity')
    require(isinstance(raw['run_token'], str) and len(raw['run_token']) >= 16 and raw['input'] == corpus, 'candidate token/input')
    require([item['id'] for item in raw['cases']] == [case['id'] for case in corpus['cases']], 'candidate case coverage/order')
    results = []
    for observed, case in zip(raw['cases'], corpus['cases']):
        if case['id'] in UNSUPPORTED:
            require(observed == {'id': case['id'], 'status': 'unsupported', 'reason': UNSUPPORTED[case['id']], 'events': []}, 'named unsupported case must remain explicit')
            results.append(observed.copy())
            continue
        shape(observed, ['id', 'status', 'events'], 'candidate case')
        require(observed['status'] == 'observed', 'unexpected unsupported case')
        nodes, events = topology(case), observed['events']
        require([entry['sequence'] for entry in events] == list(range(len(events))), 'candidate sequence')
        for entry in events: shape(entry, ['sequence', 'frame', 'operation', 'event'], 'entry')
        cursor, frame_number, latest = 0, 0, None
        parsed = []
        for operation, input_value in operations(case):
            require(cursor < len(events), 'missing candidate operation')
            start = events[cursor]
            require(start['operation'] == operation and start['frame'] == frame_number and start['event'] == {'type': 'operation_start', 'input': input_value}, 'candidate operation start')
            cursor += 1
            frames, routes, pending = [], [], None
            scale = 2 if operation == 'initial' else case['scale_factor']
            while cursor < len(events) and events[cursor]['event']['type'] != 'operation_end':
                entry, cursor = events[cursor], cursor + 1
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
                    require(input_value['action'] == 'click' and len(routes) < 2, 'unexpected input route')
                    routes.append(verify_route(event, ('down', 'up')[len(routes)], input_value['position'], nodes))
                else: require(False, 'candidate event outside frame')
            require(cursor < len(events) and pending is None, 'unfinished candidate operation/frame')
            end = events[cursor]
            require(end['operation'] == operation and end['frame'] == frame_number and end['event'] == {'type': 'operation_end', 'scale_factor': scale}, 'candidate operation end')
            cursor += 1
            if operation in ('initial', 'configured'): require(frames and not routes, 'required candidate redraw')
            else: require(len(routes) == 2 and routes[0] == routes[1], 'incomplete/inconsistent candidate down/up')
            targets = [routes[-1]] if routes and routes[-1] is not None and nodes[routes[-1]]['kind'] == 'box' else []
            parsed.append({'id': operation, 'frames': frames, 'final': latest, 'leaf_route_targets': targets})
        require(cursor == len(events), 'candidate trailing events')
        results.append({'id': case['id'], 'status': 'observed', 'operations': parsed})
    return results


def verify_rust_topology(raw, corpus):
    """Check observed lifecycle parentage; no construction-time claim is made."""
    for observed, case in zip(raw['cases'], corpus['cases']):
        nodes, stack, prepaint = topology(case), [], {}
        scale = None
        expected_inputs = dict(operations(case))
        for entry in observed['events']:
            event = entry['event']
            kind = event['type']
            if kind == 'frame_start':
                scale = event['scale_factor']
                prepaint = {}
            if kind in ('prepaint', 'paint'):
                rect = event['bounds']
                bounded_geometry(rect, 'Rust bounds', rectangle=True)
                for edge in (rect[0], rect[1], rect[0] + rect[2], rect[1] + rect[3]):
                    require(abs(edge * scale - round(edge * scale)) <= TOLERANCE * scale, 'Rust device edge exceeds numeric allowance')
                if kind == 'prepaint':
                    prepaint[event['node']] = rect
                    vector(event['content_mask'], [0, 0, *case['window']], 'Rust content mask')
                else: vector(rect, prepaint[event['node']], 'Rust paint/prepaint')
            if kind == 'callback':
                bounded_geometry(event['size'], 'Rust callback size')
                vector(event['size'], prepaint[event['node']][2:], 'Rust callback allocation')
            if kind == 'click':
                for endpoint in ('down', 'up'):
                    vector(event['detail'][endpoint], expected_inputs[entry['operation']]['position'], 'Rust click position')
            if kind in ('request_layout', 'prepaint', 'paint'):
                name = event['node']
                parent = nodes[name]['parent']
                require((stack[-1][1] if stack else None) == parent,
                        case['id'] + ': Rust lifecycle parent/topology')
                stack.append((kind, name))
            elif kind in ('request_layout_end', 'prepaint_end', 'paint_end'):
                require(stack and stack.pop() == (kind[:-4], event['node']), 'Rust lifecycle nesting')
        require(not stack, 'Rust unclosed lifecycle')


def compare_observations(rust, candidate, corpus, witnesses=None):
    original = baseline.verify_observations(rust, corpus, witnesses)['cases']
    verify_rust_topology(rust, corpus)
    replacement = verify_candidate(candidate, corpus)
    result, mismatches = [], []
    maximum_coordinate_difference = 0.0
    maximum_callback_difference = 0.0
    counts = {'supported_cases': 0, 'unsupported_cases': 0, 'rust_frames': 0, 'candidate_frames': 0, 'compared_operations': 0}
    for left, right in zip(original, replacement):
        counts['rust_frames'] += sum(len(op['frames']) for op in left['operations'])
        if right['status'] == 'unsupported':
            counts['unsupported_cases'] += 1
            result.append({'id': left['id'], 'status': 'unsupported', 'reason': right['reason'], 'rust_operations': left['operations']})
            continue
        counts['supported_cases'] += 1
        latest = None
        pairs = []
        for rust_op, candidate_op in zip(left['operations'], right['operations']):
            require(rust_op['id'] == candidate_op['id'], 'operation coverage')
            counts['candidate_frames'] += len(candidate_op['frames'])
            counts['compared_operations'] += 1
            if rust_op['frames']: latest = rust_op['frames'][-1]
            current = candidate_op['final']
            label = left['id'] + '/' + rust_op['id']
            def check(field, a, b):
                try:
                    if isinstance(a, list) and a and type(a[0]) in (int, float): vector(a, b, label + '/' + field)
                    else: require(a == b, label + '/' + field + ': different values')
                except ValueError as error:
                    mismatches.append({'case': left['id'], 'operation': rust_op['id'], 'field': field, 'rust': a, 'candidate': b, 'error': str(error)})
            check('scale_factor', latest['scale_factor'], current['scale_factor'])
            check('node_ids', list(latest['bounds']), list(current['bounds']))
            for node in latest['bounds']:
                if node in current['bounds']:
                    maximum_coordinate_difference = max(maximum_coordinate_difference, *(abs(a - b) for a, b in zip(latest['bounds'][node], current['bounds'][node])))
                check('bounds/' + node, latest['bounds'][node], current['bounds'].get(node, []))
            check('callback_ids', list(latest['callbacks']), list(current['callbacks']))
            for node in latest['callbacks']:
                if node in current['callbacks']:
                    maximum_callback_difference = max(maximum_callback_difference, *(abs(a - b) for a, b in zip(latest['callbacks'][node], current['callbacks'][node])))
                check('callbacks/' + node, latest['callbacks'][node], current['callbacks'].get(node, []))
            check('painted_leaf_ids', [leaf['node'] for leaf in latest['painted_leaves']], current['painted_leaf_ids'])
            check('click_vs_leaf_route_targets', rust_op['clicked_ids'], candidate_op['leaf_route_targets'])
            pairs.append({'id': rust_op['id'], 'rust_frame_ids': [f['frame'] for f in rust_op['frames']],
                'candidate_frame_ids': [f['frame'] for f in candidate_op['frames']], 'compared_rust_frame': latest['frame'],
                'compared_candidate_frame': current['frame'], 'scale_factor': current['scale_factor']})
        result.append({'id': left['id'], 'status': 'compared', 'operations': pairs})
    return {'schema_version': 1, 'layer': LAYER, 'passed': not mismatches, 'counts': counts, 'cases': result,
        'mismatches': mismatches, 'numeric_policy': {'absolute_logical_tolerance': TOLERANCE, 'maximum_geometry_magnitude': MAX_COORDINATE, 'maximum_observed_coordinate_difference': maximum_coordinate_difference, 'maximum_observed_callback_difference': maximum_callback_difference, 'basis': 'Two Float32 ULPs at the enforced 1024-pixel bound cover snapped-edge division and subtraction; no coordinate normalization.'}, 'frame_policy': 'Validate every raw frame; compare final published state per operation, inheriting previous state when no redraw occurs. Never pair by frame count.',
        'claim': 'Bounded font-free production layout/query/scene/dispatch semantic pair only; no unchanged-example, native click callback, font, screenshot, browser pixel, OS input or backend equivalence.'}


def require_semantic_match(comparison):
    require(comparison['passed'], 'actual pair mismatch; retain comparison.json and both raw traces')


def validate_mutation_outcomes(results):
    require(results and all(item['outcome'] == 'executed-semantic-rejection' for item in results),
            'every engine control must compile, execute successfully, and fail a semantic predicate; compile/crash/timeout is not a kill')
