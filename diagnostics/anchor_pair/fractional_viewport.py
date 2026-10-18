#!/usr/bin/env python3
"""Separate two-case actual-Rust extension; never part of the frozen 24 cases.

The frozen verifier deliberately assumes integral physical viewport dimensions.
This validator retains its lifecycle/callback contract but checks root layout
bounds on the device grid independently from the logical viewport content mask.
No observed bounds, events or inputs are rewritten to satisfy either checker.
"""
from __future__ import annotations
from compare import baseline, require, shape, validate_schema, ROOT

LAYER = 'supplemental-fractional-viewport-rust-pair'


def corpus():
    return {'schema_version': 1, 'coordinate_system': 'Separate logical-pixel fractional viewport extension; immutable 24-case corpus unchanged',
        'cases': [{'id': 'fractional-viewport-scale-' + str(scale), 'window': [160.5, 120],
            'parent_origin': [0, 0], 'parent_size': [80, 80], 'scale_factor': scale,
            'popups': [{'id': 'popup', 'anchor': 'TopLeft', 'position': [0, 0],
                'position_mode': 'Window', 'size': [320, 240], 'priority': 0, 'interactive': True}],
            'later_sibling': None, 'hits': [{'id': 'inside-logical-viewport', 'position': [160.25, 40]},
                                           {'id': 'outside-logical-viewport', 'position': [160.75, 40]}]}
            for scale in (1, 1.25)]}


def verify_frame(entries, case, scale):
    first = entries[0]['event']
    require(first == {'type': 'frame_start', 'scale_factor': scale, 'window_size': case['window']}, 'extension frame identity')
    names = baseline.node_names(case)
    stack, phases, prepaint, painted, locations, parents = [], {}, {}, [], {}, {}
    for index, entry in enumerate(entries[1:], 1):
        event = entry['event']; kind, node = event['type'], event.get('node')
        require(node in names, 'extension unknown node')
        shape(event, ['type', 'node'] + (['bounds', 'content_mask'] if kind == 'prepaint' else ['bounds'] if kind == 'paint' else []), 'extension lifecycle')
        locations[kind, node] = index
        if kind in ('request_layout', 'prepaint', 'paint'):
            phase = {'request_layout': 0, 'prepaint': 2, 'paint': 4}[kind]
            require(phases.get(node, 0) == phase, 'extension lifecycle order/count')
            phases[node] = phase + 1
            parents[kind, node] = stack[-1][1] if stack else None
            stack.append((kind, node))
            if kind in ('prepaint', 'paint'):
                baseline.physical_grid(event['bounds'], scale, 'extension raw bounds')
                if kind == 'prepaint':
                    baseline.qualify_bounds(event['content_mask'], 'extension mask')
                    baseline.vector(event['content_mask'], [0, 0, *case['window']], 'extension logical viewport mask', 0)
                    prepaint[node] = event
                else:
                    baseline.vector(event['bounds'], prepaint[node]['bounds'], 'extension prepaint/paint', 0)
                    painted.append(node)
        else:
            require(kind in ('request_layout_end', 'prepaint_end', 'paint_end'), 'extension lifecycle kind')
            require(stack and stack.pop() == (kind[:-4], node), 'extension return nesting')
            phases[node] += 1
    require(not stack and set(phases) == names and all(v == 6 for v in phases.values()), 'extension complete lifecycle')
    host = prepaint['$host']['bounds']
    baseline.vector(host[:2], [0, 0], 'extension root origin', 0)
    for observed, requested in zip(host[2:], case['window']):
        baseline.close(observed, requested, 'extension root nearest-device extent', .5 / scale + baseline.GEOMETRY_F32_ALLOWANCE)
    baseline.vector(prepaint['parent']['bounds'], [*case['parent_origin'], *case['parent_size']], 'extension authored parent')
    for phase in ('request_layout', 'prepaint', 'paint'):
        expected = {'$host': None, 'parent': '$host', 'button': 'parent', 'deferred_popup': 'parent',
            'anchor_popup': 'deferred_popup' if phase == 'request_layout' else None, 'popup': 'anchor_popup'}
        require({name: parents[phase, name] for name in names} == expected, 'extension structural lifecycle ancestry')
        require(locations[phase, 'anchor_popup'] < locations[phase, 'popup'] < locations[phase + '_end', 'anchor_popup'], 'extension attached lifecycle nesting')
        if phase != 'request_layout':
            require(locations[phase + '_end', '$host'] < locations[phase, 'anchor_popup'], 'extension genuinely deferred attachment')
    baseline.vector(prepaint['deferred_popup']['bounds'], prepaint['anchor_popup']['bounds'], 'extension shared layout ID', 0)
    baseline.vector(prepaint['popup']['bounds'][2:], [320, 240], 'extension authored oversized popup')
    baseline.vector(prepaint['anchor_popup']['bounds'][2:], prepaint['popup']['bounds'][2:], 'extension measured popup', 0)
    baseline.vector(prepaint['popup']['bounds'][:2], [0, 0], 'extension oversized clamp')
    require(painted == ['$host', 'parent', 'button', 'deferred_popup', 'anchor_popup', 'popup'], 'extension actual paint order')
    return {'frame': entries[0]['frame'], 'scale_factor': scale,
            'bounds': {name: event['bounds'] for name, event in prepaint.items()}, 'painted_nodes': painted,
            'interactive_leaves': [prepaint[name] for name in painted if name in ('button', 'popup')]}


def verify_rust(raw, inputs):
    require(inputs == corpus(), 'extension input must be exact separately authored two cases')
    baseline.validate_scenarios(inputs)
    validate_schema(raw, ROOT / 'diagnostics/anchor/raw.schema.json')
    require(raw['schema_version'] == 1 and raw['layer'] == baseline.LAYER and raw['upstream_revision'] == baseline.UPSTREAM,
            'extension actual Rust identity')
    require(raw['input'] == inputs and [c['id'] for c in raw['cases']] == [c['id'] for c in inputs['cases']], 'extension exact input/coverage')
    result = []
    for observed, case in zip(raw['cases'], inputs['cases']):
        events = observed['events']
        require([e['sequence'] for e in events] == list(range(len(events))), 'extension sequence')
        cursor, frame_number, latest, parsed = 0, 0, None, []
        from compare import operations
        for operation, value in operations(case):
            scale = 2 if operation == 'initial' else case['scale_factor']
            require(cursor < len(events), 'extension missing operation')
            start = events[cursor]; cursor += 1
            require(start == {'sequence': cursor - 1, 'frame': frame_number, 'operation': operation,
                              'event': {'type': 'operation_start', 'input': value}}, 'extension operation start')
            frames, callbacks, pending, hit_frame = [], [], [], latest
            while cursor < len(events) and events[cursor]['event']['type'] != 'operation_end':
                entry = events[cursor]; cursor += 1
                require(entry['operation'] == operation, 'extension operation interleaving')
                kind = entry['event']['type']
                if kind == 'frame_start':
                    if pending: latest = verify_frame(pending, case, scale); frames.append(latest)
                    pending = []; frame_number += 1
                require(entry['frame'] == frame_number, 'extension frame sequence')
                if kind in ('mouse_down', 'click'):
                    if pending: latest = verify_frame(pending, case, scale); frames.append(latest); pending = []
                    require(value['action'] == 'click', 'extension unsolicited callback')
                    callbacks.append(entry['event'])
                else:
                    require(pending or kind == 'frame_start', 'extension lifecycle outside frame')
                    pending.append(entry)
            if pending: latest = verify_frame(pending, case, scale); frames.append(latest)
            require(cursor < len(events), 'extension unfinished operation')
            end = events[cursor]; cursor += 1
            require(end == {'sequence': cursor - 1, 'frame': frame_number, 'operation': operation,
                            'event': {'type': 'operation_end', 'scale_factor': scale}}, 'extension operation end')
            if value['action'] != 'click': require(frames and not callbacks, 'extension redraw required')
            else:
                require(hit_frame is not None, 'extension click before frame')
                point = value['position']
                for leaf in hit_frame['interactive_leaves']:
                    require(not baseline.on_edge(point, leaf['bounds']) and not baseline.on_edge(point, leaf['content_mask']), 'extension edge ambiguity')
                eligible = [leaf['node'] for leaf in hit_frame['interactive_leaves']
                            if baseline.inside(point, leaf['bounds']) and baseline.inside(point, leaf['content_mask'])]
                target = eligible[-1:]  # Logical masks, independently of rounded root geometry.
                require(target == (['popup'] if operation == 'inside-logical-viewport' else []), 'extension meaningful interior/exterior witness')
                require([c['type'] for c in callbacks] == (['mouse_down', 'click'] if target else []) and
                        [c['node'] for c in callbacks] == target * 2, 'extension actual callback target/kind/count')
                for callback in callbacks:
                    require(callback['contexts'] == ['AnchorRoot', 'AnchorParent', 'Leaf_popup'], 'extension actual focused ancestry')
                    if callback['type'] == 'mouse_down': baseline.vector(callback['position'], point, 'extension down', 0)
                    else:
                        require(callback['detail']['kind'] == 'mouse', 'extension click type')
                        for phase in ('down', 'up'): baseline.vector(callback['detail'][phase], point, 'extension click ' + phase, 0)
            parsed.append({'id': operation, 'frames': frames, 'callbacks': callbacks})
        require(cursor == len(events), 'extension trailing events')
        result.append({'id': case['id'], 'operations': parsed})
    return {'cases': result}


def compare_extension(rust, candidate, inputs):
    from compare import compare_observations
    result = compare_observations(rust, candidate, inputs, rust_verifier=verify_rust)
    result.update(layer=LAYER, qualification='separate-two-case-fractional-viewport-pair',
        frozen_24_case_qualification=False,
        claim='Separate actual-Rust/production-MoonBit fractional logical viewport masks and pointer dispatch; no browser, font, OS-input or full backend parity.')
    return result


def execute_extension(pair, environment):
    """Called in native CI only, after the ordinary source-bound pair passes."""
    import json
    import uuid
    from run import execute, inventory
    from compare import load_json, require_semantic_match
    directory = pair / 'fractional-viewport'
    directory.mkdir(exist_ok=False)
    inputs = corpus()
    (directory / 'scenarios.json').write_text(json.dumps(inputs, indent=2) + '\n')
    token = str(uuid.uuid4())
    env = environment.copy()
    env.pop('DISPLAY', None); env.pop('WAYLAND_DISPLAY', None)
    env.update(GPUI_SCENARIOS=(directory / 'scenarios.json').read_text(), GPUI_RUN_TOKEN=token)
    manifest = {'schema_version': 1, 'layer': LAYER, 'run_token': token,
        'recorded_execution_root': str(directory), 'frozen_24_case_qualification': False,
        'baseline_manifest_sha256': baseline.digest(pair / 'rust-baseline/manifest.json'),
        'rust_binary_sha256': baseline.digest(pair / 'rust-baseline/probe'),
        'candidate_binary_sha256': baseline.digest(pair / 'candidate-probe'),
        'input_sha256': baseline.digest(directory / 'scenarios.json')}
    manifest['rust_execution'] = execute([str(pair / 'rust-baseline/probe'), str(directory / 'scenarios.json'), token],
        pair / 'build-source', directory, 'rust', env, timeout=120)
    manifest['candidate_execution'] = execute([str(pair / 'candidate-probe')], pair / 'build-source', directory, 'candidate', env)
    for name in ('rust', 'candidate'): (directory / (name + '.stdout')).rename(directory / (name + '-raw.json'))
    successful = all(manifest[name + '_execution']['returncode'] == 0 and not manifest[name + '_execution']['timed_out'] for name in ('rust', 'candidate'))
    comparison = None
    if successful:
        try:
            for name in ('rust', 'candidate'): require((directory / (name + '.stderr')).stat().st_size == 0, 'extension stderr: ' + name)
            rust, candidate = [load_json((directory / (name + '-raw.json')).read_text()) for name in ('rust', 'candidate')]
            require(rust['run_token'] == candidate['run_token'] == token, 'extension run token')
            comparison = compare_extension(rust, candidate, inputs)
            (directory / 'comparison.json').write_text(json.dumps(comparison, indent=2) + '\n')
        except (ValueError, TypeError, KeyError, IndexError) as error:
            (directory / 'comparison-failure.json').write_text(json.dumps({'error': str(error), 'type': type(error).__name__}, indent=2) + '\n')
    manifest['files'] = inventory(directory)
    (directory / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    require(successful and comparison is not None, 'fractional extension execution/validation failed; raw evidence retained')
    require_semantic_match(comparison)
    return comparison


def verify_extension(pair, pair_manifest):
    """Verify copied evidence using recorded paths, without re-executing binaries."""
    from pathlib import Path
    from compare import load_json
    from run import inventory
    directory = pair / 'fractional-viewport'
    manifest = load_json((directory / 'manifest.json').read_text())
    require(manifest['schema_version'] == 1 and manifest['layer'] == LAYER and manifest['frozen_24_case_qualification'] is False, 'extension manifest identity')
    require(manifest['baseline_manifest_sha256'] == baseline.digest(pair / 'rust-baseline/manifest.json'), 'extension exact approved Rust baseline')
    for name, relative in [('rust', 'rust-baseline/probe'), ('candidate', 'candidate-probe')]:
        require(manifest[name + '_binary_sha256'] == baseline.digest(pair / relative), 'extension genuine binary identity')
    require(inventory(directory) == manifest['files'], 'extension complete unchanged inventory')
    for relative in manifest['files']:
        path = directory / relative
        require(not Path(relative).is_absolute() and '..' not in Path(relative).parts and not path.is_symlink() and path.resolve().is_relative_to(directory), 'extension unsafe evidence path')
    inputs = load_json((directory / 'scenarios.json').read_text())
    require(inputs == corpus() and manifest['input_sha256'] == baseline.digest(directory / 'scenarios.json'), 'extension immutable separate input')
    root = Path(pair_manifest['recorded_execution_root'])
    recorded = root / 'fractional-viewport'
    require(manifest['recorded_execution_root'] == str(recorded), 'extension recorded root')
    token = manifest['run_token']
    commands = {'rust': [str(root / 'rust-baseline/probe'), str(recorded / 'scenarios.json'), token],
                'candidate': [str(root / 'candidate-probe')]}
    for name in ('rust', 'candidate'):
        execution = manifest[name + '_execution']
        require(execution['command'] == commands[name] and execution['cwd'] == str(root / 'build-source') and
                execution['returncode'] == 0 and execution['timed_out'] is False, 'extension exact successful invocation')
        require((directory / (name + '.stderr')).stat().st_size == 0, 'extension stderr')
    rust, candidate = [load_json((directory / (name + '-raw.json')).read_text()) for name in ('rust', 'candidate')]
    require(rust['run_token'] == candidate['run_token'] == token, 'extension cross-run raw')
    result = compare_extension(rust, candidate, inputs)
    require(result == load_json((directory / 'comparison.json').read_text()), 'extension recomputed comparison')
    return result
