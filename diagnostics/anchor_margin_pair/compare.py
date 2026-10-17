#!/usr/bin/env python3
"""All-frame observation validation and fixed-allowance operation-final pairing.

No candidate coordinate is computed from anchor placement rules. Rust's frozen
verifier separately validates its getter/lifecycle observations. The candidate
is checked through real layout tree and scene records, then compared directly.
"""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('anchor_margin_rust_verify', ROOT / 'diagnostics/anchor_margin/verify.py')
baseline = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(baseline)
require = baseline.require
LAYER = 'supplemental-font-free-anchor-margin-pair'
CANDIDATE_LAYER = 'compiled-moonbit-anchor-margin'
TOLERANCE = 2 ** -10  # Fixed before any candidate execution; inherited reviewed bounded f32 policy.
GRID_TOLERANCE = 2 ** -10  # Device pixels, distinct from logical geometry allowance.


def load_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    def constant(value): raise ValueError('non-JSON numeric constant: ' + value)
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def validate_schema(raw, path):
    try: Draft202012Validator(load_json(path.read_text())).validate(raw)
    except ValidationError as error: raise ValueError('raw schema: ' + error.message) from error


def shape(value, fields, label):
    require(isinstance(value, dict) and set(value) == set(fields), label + ': fields')


def topology():
    parents = {'$host': None, '$parent_position': '$host', 'parent': '$parent_position',
               'button': 'parent', 'anchor': 'parent', 'popup': 'anchor'}
    return {name: {'id': str(i + 1), 'parent': parent} for i, (name, parent) in enumerate(parents.items())}


def inspect_scene(commands, observed, case):
    stack, leaves, masks = [], [], {}
    for event in commands:
        kind, node = event['kind'], event['node']
        require(node in observed, 'scene unknown node')
        if kind == 'clip_push':
            baseline.qualify_bounds(event['bounds']); stack.append((node, event['bounds']))
        elif kind == 'clip_pop':
            require(event['bounds'] is None and stack and stack.pop()[0] == node, 'scene clip balance')
        else:
            require(kind == 'quad' and node in ('button', 'popup'), 'scene unexpected paint')
            baseline.vector(event['bounds'], observed[node], 'actual scene/tree bounds', 0)
            leaves.append(node); masks[node] = list(stack)
    require(not stack and leaves == ['button', 'popup'], 'actual ordinary/deferred scene order')
    viewport = [0, 0, *case['window']]
    require(masks['button'] == [('$host', viewport)], 'ordinary effective viewport mask')
    require(masks['popup'] in ([('anchor', viewport)], [('$host', viewport), ('anchor', viewport)]), 'deferred effective viewport mask')
    require([(e['kind'], e['node']) for e in commands if e['node'] != '$host'] ==
            [('quad', 'button'), ('clip_push', 'anchor'), ('quad', 'popup'), ('clip_pop', 'anchor')], 'flat deferred scene structure')
    require([e['kind'] for e in commands if e['node'] == '$host'] == ['clip_push', 'clip_pop'], 'root clip coverage')
    return leaves, {name: value[-1][1] for name, value in masks.items()}


def verify_frame(entries, case, scale):
    nodes, observed, scenes, probes = topology(), {}, [], []
    phase, overflow = 'start', None
    for entry in entries:
        event = entry['event']; kind = event['type']
        if kind in ('frame_start', 'frame_end'):
            shape(event, ['type', 'scale_factor', 'window_size'], 'frame')
            require(event['scale_factor'] == scale and event['window_size'] == case['window'], 'exact frame scale/viewport')
            if kind == 'frame_start':
                require(phase == 'start', 'repeated frame start'); phase = 'request_start'
            else:
                require(phase == 'probes', 'incomplete frame'); phase = 'done'
        elif kind in ('request_start', 'request_end', 'prepaint_start'):
            shape(event, ['type'], 'lifecycle')
            require(phase == kind, 'candidate lifecycle order')
            phase = {'request_start': 'request_end', 'request_end': 'prepaint_start', 'prepaint_start': 'prepaint_end'}[kind]
        elif kind == 'prepaint_end':
            shape(event, ['type', 'overflow'], 'prepaint')
            require(phase == 'prepaint_end' and type(event['overflow']) is bool, 'prepaint result')
            overflow, phase = event['overflow'], 'nodes'
        elif kind == 'node':
            shape(event, ['type', 'node', 'id', 'parent', 'bounds', 'pointer_events', 'focusable'], 'node')
            name = event['node']
            require(phase == 'nodes' and name in nodes and name not in observed, 'node identity/count/order')
            require(event['id'] == nodes[name]['id'] and event['parent'] == nodes[name]['parent'], 'structural lineage')
            require(event['pointer_events'] is False and event['focusable'] is False, 'noninteractive margin fixture')
            baseline.physical_grid(event['bounds'], scale)
            observed[name] = event['bounds']
        elif kind == 'scene':
            shape(event, ['type', 'kind', 'node', 'bounds'], 'scene')
            require(phase in ('nodes', 'scene'), 'scene lifecycle'); phase = 'scene'; scenes.append(event)
        elif kind == 'viewport_hit':
            shape(event, ['type', 'side', 'position', 'target'], 'candidate-only hit probe')
            require(phase in ('scene', 'probes'), 'hit API lifecycle'); phase = 'probes'; probes.append(event)
        else: require(False, 'unexpected candidate event: ' + kind)
    require(phase == 'done' and list(observed) == list(nodes), 'complete structural preorder/frame')
    leaves, masks = inspect_scene(scenes, observed, case)
    width, height = case['window']
    require(probes == [{'type': 'viewport_hit', 'side': 'right', 'position': [width + 1, height / 2], 'target': None},
                       {'type': 'viewport_hit', 'side': 'bottom', 'position': [width / 2, height + 1], 'target': None}],
            'candidate-only noninteractive hit API observations')
    return {'frame': entries[0]['frame'], 'scale_factor': scale, 'observed_bounds': observed,
            'painted_leaves': leaves, 'effective_masks': masks, 'overflow': overflow,
            'candidate_bounds_translation_derived': [observed['popup'][a] - observed['anchor'][a] for a in (0, 1)]}


def decode_transport(raw, token, corpus):
    validate_schema(raw, ROOT / 'diagnostics/anchor_margin_pair/raw.schema.json')
    shape(raw, ['schema_version', 'layer', 'fixture', 'input', 'run_token', 'cases'], 'candidate')
    require(raw['schema_version'] == 1 and raw['layer'] == CANDIDATE_LAYER and raw['fixture'] == 'font-free-bounded-anchor-margin', 'candidate identity')
    require(isinstance(token, str) and 16 <= len(token) <= 64 and raw['run_token'] == token, 'candidate session token')
    require(raw['input'] == corpus and [item['id'] for item in raw['cases']] == [case['id'] for case in corpus['cases']], 'candidate exact input/coverage/order')
    return raw


def verify_candidate(raw, corpus):
    baseline.validate_scenarios(corpus)
    decode_transport(raw, raw.get('run_token'), corpus)
    results = []
    for observed, case in zip(raw['cases'], corpus['cases']):
        events = observed['events']
        require([e['sequence'] for e in events] == list(range(len(events))), 'candidate event sequence')
        cursor, frame_number, operations = 0, 0, []
        for operation, value, scale in [('initial', {'action': 'open_window'}, 2),
                ('configured', {'action': 'set_scale_factor', 'scale_factor': case['scale_factor']}, case['scale_factor'])]:
            require(cursor < len(events), 'missing candidate operation')
            require(events[cursor] == {'sequence': cursor, 'operation': operation, 'frame': frame_number,
                    'event': {'type': 'operation_start', 'input': value}}, 'operation start/input')
            cursor += 1; frames, pending = [], None
            while cursor < len(events) and events[cursor]['event']['type'] != 'operation_end':
                entry = events[cursor]; cursor += 1
                require(entry['operation'] == operation, 'operation interleaving')
                kind = entry['event']['type']
                if kind == 'frame_start':
                    require(pending is None, 'nested candidate frame'); pending = []; frame_number += 1
                require(entry['frame'] == frame_number and pending is not None, 'candidate frame sequence')
                pending.append(entry)
                if kind == 'frame_end': frames.append(verify_frame(pending, case, scale)); pending = None
            require(frames and pending is None and cursor < len(events), 'missing candidate redraw/end')
            require(events[cursor] == {'sequence': cursor, 'operation': operation, 'frame': frame_number,
                    'event': {'type': 'operation_end', 'scale_factor': scale}}, 'operation end/scale')
            cursor += 1; operations.append({'id': operation, 'frames': frames})
        require(cursor == len(events), 'trailing candidate events')
        results.append({'id': case['id'], 'operations': operations})
    return results


def compare_observations(rust, candidate, corpus):
    original = baseline.verify_observations(rust, corpus)['cases']
    replacement = verify_candidate(candidate, corpus)
    mismatches, cases, maximum = [], [], 0.0
    counts = {'cases': len(corpus['cases']), 'rust_frames': 0, 'candidate_frames': 0, 'compared_operations': 0,
              'configured_comparisons': 0, 'paired_clicks': 0, 'candidate_only_noninteractive_hit_probes': 0}
    for left, right in zip(original, replacement):
        pairs = []
        for rust_op, candidate_op in zip(left['operations'], right['operations']):
            require(rust_op['id'] == candidate_op['id'], 'operation coverage')
            a, b = rust_op['frames'][-1], candidate_op['frames'][-1]
            counts['rust_frames'] += len(rust_op['frames']); counts['candidate_frames'] += len(candidate_op['frames'])
            counts['candidate_only_noninteractive_hit_probes'] += 2 * len(candidate_op['frames'])
            counts['compared_operations'] += 1; counts['configured_comparisons'] += int(rust_op['id'] == 'configured')
            def check(field, observed_rust, observed_candidate, numeric=False):
                nonlocal maximum
                try:
                    if numeric:
                        if len(observed_rust) == len(observed_candidate): maximum = max(maximum, *(abs(x-y) for x,y in zip(observed_rust, observed_candidate)))
                        baseline.vector(observed_rust, observed_candidate, field, TOLERANCE)
                    else: require(observed_rust == observed_candidate, field + ': different values')
                except ValueError as error:
                    mismatches.append({'case': left['id'], 'operation': rust_op['id'], 'field': field,
                        'rust': observed_rust, 'candidate': observed_candidate, 'error': str(error)})
            check('scale_factor', a['scale_factor'], b['scale_factor'])
            for node in ('$host', 'parent', 'button', 'anchor', 'popup'):
                check('bounds/' + node, a['observed_bounds'][node], b['observed_bounds'][node], True)
            check('painted_leaves', [n for n in a['painted_nodes'] if n in ('button','popup')], b['painted_leaves'])
            for node in ('button', 'popup'): check('effective_mask/' + node, a['observed_content_mask'], b['effective_masks'][node])
            pairs.append({'id': rust_op['id'], 'rust_frame_ids': [f['frame'] for f in rust_op['frames']],
                'candidate_frame_ids': [f['frame'] for f in candidate_op['frames']], 'compared_rust_frame': a['frame'],
                'compared_candidate_frame': b['frame'], 'scale_factor': b['scale_factor'],
                'rust_logical_offset_getter_observed': a['observed_logical_offset'],
                'candidate_bounds_translation_derived': b['candidate_bounds_translation_derived']})
        cases.append({'id': left['id'], 'operations': pairs})
    return {'schema_version': 1, 'layer': LAYER, 'passed': not mismatches, 'counts': counts, 'cases': cases,
        'mismatches': mismatches, 'numeric_policy': {'absolute_logical_allowance': TOLERANCE, 'physical_grid_allowance': GRID_TOLERANCE,
            'raw_coordinate_limit': 4096, 'raw_size_limit': 2048, 'raw_far_edge_limit': 4096, 'maximum_observed_difference': maximum,
            'basis': 'Predeclared inherited bounded f32 policy. No fitted epsilon or output normalization.'},
        'frame_policy': 'Validate all raw frames; compare each operation final. Configured comparisons counted separately. Redraw counts never paired.',
        'claim': '88-case scalar margin layout and effective scene-mask pair only. Candidate hit probes are noninteractive smoke. No paired pointer, raster, browser, native-window, nesting or full popover claim.'}


def require_semantic_match(comparison):
    require(comparison['passed'], 'actual margin pair mismatch; retain both raw traces')


def validate_mutation_outcomes(results):
    descriptors = load_json((ROOT / 'diagnostics/anchor_margin_pair/mutations.json').read_text())
    require([item['mutation'] for item in results] == [item['name'] for item in descriptors], 'complete exact production-control coverage')
    require(all(item['outcome'] == 'executed-paired-margin-rejection' for item in results),
            'every margin control must compile, execute, pass transport/structure, and fail its predefined paired margin witness')
