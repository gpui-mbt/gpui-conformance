#!/usr/bin/env python3
"""Compare independently observed raw frames, never source-derived expected rows."""
from __future__ import annotations
import argparse
from collections import defaultdict
import importlib.util
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('uniform_list_baseline_verify', ROOT / 'diagnostics/uniform_list/verify.py')
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)
require = baseline.require


BEHAVIORAL_MUTATIONS = frozenset({
    'bounded_overconstruction', 'first_index_plus_one', 'floor_tail_loss',
    'hardcoded_metric', 'offset_reset', 'wrong_endpoint', 'visible_slot_identity',
    'missing_ancestor_clip', 'closed_far_edge', 'ignore_x_fallback',
    'inherited_axis_dominance', 'retain_omitted_press',
})
RUNTIME_CONTROL_MUTATIONS = frozenset({'visible_only_extent', 'eager_all_n_resource'})


def validate_mutation_outcomes(results):
    """Do not let a crash silently replace the claimed behavioral coverage."""
    names = [result['mutation'] for result in results]
    require(len(names) == len(set(names)), 'duplicate mutation outcome')
    require(set(names) == BEHAVIORAL_MUTATIONS | RUNTIME_CONTROL_MUTATIONS,
            'incomplete or unexpected mutation inventory')
    for result in results:
        name, outcome = result['mutation'], result['outcome']
        if name in BEHAVIORAL_MUTATIONS:
            require(outcome == 'executed-semantic-rejection',
                    name + ': behavioral coverage requires complete-trace semantic rejection')
        else:
            require(outcome in ('executed-semantic-rejection', 'executed-runtime-rejection'),
                    name + ': surviving, timed-out or unexecuted runtime control')


def equal(actual, expected, label):
    """Exact comparison: this bounded f32-compatible corpus needs no tolerance."""
    if isinstance(expected, dict):
        require(isinstance(actual, dict) and set(actual) == set(expected), label + ': keys')
        for key in expected: equal(actual[key], expected[key], label + '.' + key)
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), label + ': length')
        for index, (left, right) in enumerate(zip(actual, expected)):
            equal(left, right, label + f'[{index}]')
    elif isinstance(expected, (float, int)) and not isinstance(expected, bool):
        require(isinstance(actual, (float, int)) and not isinstance(actual, bool)
                and math.isfinite(actual) and actual == expected, f'{label}: {actual!r} != {expected!r}')
    else:
        require(type(actual) is type(expected) and actual == expected, f'{label}: {actual!r} != {expected!r}')


def events_of(entries, kind):
    return [entry['event'] for entry in entries if entry['event']['type'] == kind]


def factory_data(entries, candidate):
    factories = events_of(entries, 'factory')
    built = defaultdict(list)
    identities = {}
    for event in events_of(entries, 'constructed'):
        built[event['factory_call']].append(event['item_id'])
        if candidate:
            index = event['item_id']
            require(type(index) is int and index >= 0, 'constructed index type')
            # Explicit stable-ID encoding only, not virtual-list layout math.
            equal(event['row_id'], str(1000 + 2 * index), 'stable row identity')
            equal(event['inner_id'], str(1001 + 2 * index), 'stable inner identity')
            identities[event['row_id']] = ('row', index, event['factory_call'])
            identities[event['inner_id']] = ('inner', index, event['factory_call'])
    calls = [f['factory_call'] for f in factories]
    require(len(set(calls)) == len(calls), 'duplicate factory call within frame')
    require(set(built) <= set(calls), 'unowned construction')
    result = [{'range': f['range'], 'constructed': built[f['factory_call']]} for f in factories]
    return result, identities, calls


def rust_frame(entries):
    first, last = entries[0]['event'], entries[-1]['event']
    config = first['configuration']
    scroll = last['scroll']
    factories, _, calls = factory_data(entries, False)
    painted = [e['event'] for e in entries if e['event']['type'] == 'prepaint']
    list_bounds = [p['bounds'] for p in painted if p['kind'] == 'list']
    require(len(list_bounds) == 1, 'Rust list prepaint')
    rows = []
    for p in painted:
        if p['kind'] in ('row', 'inner'):
            require(calls and p['factory_call'] == calls[-1], 'Rust prototype painted')
            rows.append({'kind': p['kind'], 'item_id': p['item_id'], 'bounds': p['bounds'], 'mask': p['content_mask']})
    measured = rows[0]['bounds'][2:] if rows else None
    state = {
        'list_bounds': list_bounds[0], 'item_count': config['count'],
        'measured_item_size': measured, 'content_size': scroll['last_item_size']['contents'],
        'offset': [scroll['offset'][0], -scroll['offset'][1]], 'max_offset': scroll['max_offset'],
        'visible_range': factories[-1]['range'] if factories else [0, 0], 'window_size': last['window_size'],
    }
    live = {(p['item_id'], p['factory_call']) for p in painted if p['kind'] == 'row'}
    return {'state': state, 'factories': factories, 'rows': rows}, live


def candidate_frame(entries):
    equal(entries[0]['event']['logical_layout_scale'], 1, 'candidate logical scale')
    state = entries[-1]['event']['state']
    factories, identities, calls = factory_data(entries, True)
    nodes = events_of(entries, 'node')
    by_id = {node['id']: node for node in nodes}
    require(len(by_id) == len(nodes), 'duplicate live node')
    require([n['id'] for n in nodes[:2]] == ['1', '2'], 'root/list order')
    equal(by_id['1']['parent'], None, 'root parent')
    equal(by_id['1']['bounds'], [0, 0, *state['window_size']], 'actual root bounds')
    equal(by_id['2']['parent'], '1', 'list parent')
    equal(by_id['2']['bounds'], state['list_bounds'], 'actual list bounds')
    for node in nodes[2:]:
        require(node['id'] in identities, 'live node not factory-created')
        kind, index, call = identities[node['id']]
        require(calls and call == calls[-1] == node['factory_call'], 'prototype became live')
        equal(node['parent'], '2' if kind == 'row' else str(1000 + 2 * index), 'live parent')
    stack, rows, quad_ids = [], [], []
    for command in events_of(entries, 'scene'):
        kind, identifier, rect = command['kind'], command['id'], command['bounds']
        require(identifier in by_id, 'scene ID not live')
        if kind == 'clip_push':
            equal(rect, by_id[identifier]['bounds'], 'actual scene clip bounds')
            stack.append((identifier, rect))
        elif kind == 'clip_pop':
            require(stack and stack[-1][0] == identifier and rect is None, 'unbalanced scene clip')
            stack.pop()
        elif kind == 'quad':
            require(identifier in identities, 'unexpected quad')
            require([item[0] for item in stack] == ['1', '2'], 'missing/changed window or list scene clip')
            equal(rect, by_id[identifier]['bounds'], 'scene versus actual tree bounds')
            mask = stack[0][1]
            for _, clip in stack[1:]: mask = baseline.intersection(mask, clip)
            row_kind, index, _ = identities[identifier]
            rows.append({'kind': row_kind, 'item_id': index, 'bounds': rect, 'mask': mask})
            quad_ids.append(identifier)
        else: raise ValueError('unknown scene kind')
    require(not stack, 'unclosed scene clips')
    equal(quad_ids, [n['id'] for n in nodes[2:]], 'all live nodes painted once in order')
    live = {(identities[n['id']][1], n['factory_call']) for n in nodes[2:] if identities[n['id']][0] == 'row'}
    return {'state': state, 'factories': factories, 'rows': rows}, live


def split_case(case, scenario, candidate):
    entries = case['events']
    equal([e['sequence'] for e in entries], list(range(len(entries))), 'event sequence')
    operations = [{'id': 'initial', 'action': 'open_window'}, *scenario['operations']]
    result, cursor, last, frame_number, live = [], 0, None, 0, set()
    config = scenario['initial']
    factory_ids = [e['factory_call'] for e in events_of(entries, 'factory')]
    equal(factory_ids, list(range(1, len(factory_ids) + 1)), 'factory sequence')
    for operation in operations:
        require(cursor < len(entries), 'missing operation')
        start = entries[cursor]
        require(start['event']['type'] == 'operation_start', 'missing operation start')
        equal(start['event']['input'], operation, 'original input')
        if operation['action'] != 'open_window':
            equal(start['event']['applied_input'], baseline.applied_operation(operation), 'applied f32 input')
        config = baseline.changed_configuration(config, baseline.applied_operation(operation))
        frames, clicks, routes, pending = [], [], [], None
        previous_frame = last
        while cursor < len(entries):
            entry = entries[cursor]
            equal(entry['operation'], operation['id'], 'operation ownership')
            event = entry['event']
            kind = event['type']
            if kind == 'frame_start':
                require(pending is None, 'nested frame')
                frame_number += 1
                equal(entry['frame'], frame_number, 'frame sequence')
                equal(event['configuration'], config, 'frame configuration')
                pending = []
            else:
                equal(entry['frame'], frame_number, 'event frame ownership')
            if pending is not None: pending.append(entry)
            if kind == 'frame_end':
                require(pending is not None, 'orphan frame end')
                normalized, live = (candidate_frame if candidate else rust_frame)(pending)
                frames.append({'frame': frame_number, 'normalized': normalized})
                last, pending = normalized, None
            if kind == 'route':
                require(candidate and operation['action'] in ('down', 'up', 'move'), 'unexpected pointer route')
                routes.append(event)
            if kind == 'click':
                require(pending is None and operation['action'] == 'up', 'click lifecycle')
                require((event['item_id'], event['factory_call']) in live, 'callback not bound to actual preceding live row')
                if candidate: equal(event['row_id'], str(1000 + 2 * event['item_id']), 'clicked stable ID')
                clicks.append({'item_id': event['item_id'], 'detail': event['detail']})
            cursor += 1
            if kind == 'operation_end':
                require(pending is None and last is not None, 'incomplete/missing frame')
                if candidate:
                    require(len(frames) == 1, 'synchronous candidate requires exactly one complete frame per operation')
                equal(event['configuration'], config, 'snapshot configuration')
                if candidate:
                    equal(event['state'], last['state'], 'snapshot versus last actual frame')
                else:
                    equal(event['list_bounds'], last['state']['list_bounds'], 'Rust snapshot bounds')
                    equal(event['scroll']['offset'], [0, -last['state']['offset'][1]], 'Rust snapshot offset')
                    equal(event['scroll']['max_offset'], last['state']['max_offset'], 'Rust snapshot max')
                    equal(event['scroll']['last_item_size']['contents'], last['state']['content_size'], 'Rust snapshot content')
                    equal(event['scale_factor'], config['scale_factor'], 'Rust scale')
                result.append({'id': operation['id'], 'frames': frames, 'terminal': last, 'clicks': clicks, 'routes': routes, 'before': previous_frame})
                break
        else: raise ValueError('missing operation end')
    require(cursor == len(entries), 'trailing events')
    return result


def distinct_states(frames, terminal):
    values = [f['normalized'] for f in frames] or [terminal]
    result = []
    for value in values:
        if not result or value != result[-1]: result.append(value)
    return result


def compare_observations(rust, candidate, scenarios):
    baseline.verify_observations(rust, scenarios)
    equal(candidate['schema_version'], 1, 'candidate schema')
    equal(candidate['layer'], 'compiled-moonbit-uniform-list-semantics', 'candidate layer')
    equal(candidate['fixture'], 'font-free-nested-auto-height', 'candidate fixture')
    equal(candidate['logical_layout_scale'], 1, 'candidate logical layout')
    equal(candidate['platform_scale_claim'], False, 'candidate platform claim')
    equal(candidate['input'], scenarios, 'candidate input')
    require(isinstance(candidate.get('run_token'), str) and len(candidate['run_token']) >= 16, 'candidate run token')
    allowed = {'operation_start', 'operation_end', 'frame_start', 'frame_end', 'factory', 'constructed', 'node', 'scene', 'route', 'pressed', 'cancelled', 'click', 'wheel_update'}
    require(all(e['event']['type'] in allowed for c in candidate['cases'] for e in c['events']), 'unknown candidate event')
    equal([c['id'] for c in candidate['cases']], [c['id'] for c in scenarios['cases']], 'candidate cases')
    summaries = []
    for rc, cc, scenario in zip(rust['cases'], candidate['cases'], scenarios['cases']):
        rs, cs = split_case(rc, scenario, False), split_case(cc, scenario, True)
        ops = []
        for r, c in zip(rs, cs):
            label = scenario['id'] + '/' + r['id']
            operation = next((o for o in scenario['operations'] if o['id'] == r['id']), {'action': 'open_window'})
            if operation['action'] in ('down', 'up', 'move'):
                require(len(c['routes']) == 1, label + ': missing/duplicate routed input')
                route = c['routes'][0]
                equal(route['capture'], list(reversed(route['bubble'])), label + '/route direction')
                at = baseline.applied_operation(operation)['position']
                hits = [row for row in r['before']['rows'] if row['kind'] == 'row' and baseline.inside(at, baseline.intersection(row['bounds'], row['mask']))]
                require(len(hits) <= 1, label + ': ambiguous observed mask')
                candidate_rows = [int(identifier) for identifier in route['bubble'] if int(identifier) >= 1000 and int(identifier) % 2 == 0]
                equal(candidate_rows, [1000 + 2 * hits[0]['item_id']] if hits else [], label + '/observed-mask-derived row route')
            else:
                require(not c['routes'], label + ': unexpected route')
            if r['id'] != 'initial':
                # Only consecutive equal semantic states are stutter-normalized.
                # Any meaningful extra intermediate state remains and must match.
                equal(distinct_states(c['frames'], c['terminal']), distinct_states(r['frames'], r['terminal']), label + '/all-frame-semantics')
                equal(c['terminal'], r['terminal'], label + '/terminal')
                equal(c['clicks'], r['clicks'], label + '/callbacks')
            else:
                require(not c['clicks'] and not r['clicks'], 'bootstrap callbacks')
            ops.append({'id': r['id'], 'compared': r['id'] != 'initial',
                        'rust_frames': [f['frame'] for f in r['frames']], 'candidate_frames': [f['frame'] for f in c['frames']],
                        'clicked_ids': [click['item_id'] for click in c['clicks']]})
        summaries.append({'id': scenario['id'], 'operations': ops})
    return {'schema_version': 1, 'equal': True, 'comparison': 'exact bounded operational logical-pixel semantics',
            'bootstrap_policy': 'Retained Rust 2x initial frames and candidate logical initialization are not scale-equivalence evidence',
            'frame_policy': 'Compare ordered semantic state sequences per operation; collapse consecutive equal frames only; retain raw frame IDs',
            'numeric_tolerance': 0, 'cases': summaries,
            'counts': {'cases': len(summaries), 'operations': sum(len(c['operations']) for c in summaries),
                       'compared_operations': sum(o['compared'] for c in summaries for o in c['operations']),
                       'rust_frames': sum(len(o['rust_frames']) for c in summaries for o in c['operations']),
                       'candidate_frames': sum(len(o['candidate_frames']) for c in summaries for o in c['operations']),
                       'callbacks': sum(len(o['clicked_ids']) for c in summaries for o in c['operations'])}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rust-raw', type=Path, required=True)
    parser.add_argument('--candidate-raw', type=Path, required=True)
    parser.add_argument('--scenarios', type=Path, default=ROOT / 'diagnostics/uniform_list/scenarios.json')
    args = parser.parse_args()
    result = compare_observations(*(json.loads(p.read_text()) for p in (args.rust_raw, args.candidate_raw, args.scenarios)))
    print(json.dumps(result, indent=2))

if __name__ == '__main__': main()
