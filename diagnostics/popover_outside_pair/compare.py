"""Compare actual Rust observations with independently executed MoonBit output.

Only geometry, frame production, state, registration and callbacks are projected;
this does not invent corresponding MoonBit Rust paint-phase events.
"""
import copy
import importlib.util
import json
from pathlib import Path


def require(ok, message):
    if not ok:
        raise ValueError(message)


def load(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def same_value(left, right):
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left == right
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(same_value(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(same_value(a, b) for a, b in zip(left, right))
    return left == right


def project_rust(raw, oracle_source, fixture):
    module_path = Path(oracle_source) / 'diagnostics/popover_outside/verify.py'
    spec = importlib.util.spec_from_file_location('frozen_popover_verify', module_path)
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    require(type(raw.get('schema_version')) is int, 'Rust schema type')
    require(same_value(raw.get('input'), fixture), 'Rust input')
    verifier.verify(raw, fixture)
    operations = []
    active = None
    rendered = None
    for row in raw['events']:
        event = row['event']
        kind = event['type']
        if kind == 'operation_start':
            active = {'operation': row['operation'], 'input': copy.deepcopy(event['input']), 'callbacks': []}
            operations.append(active)
        elif kind == 'render':
            rendered = {'state': copy.deepcopy(event['state']), 'registrations': [], 'bounds': {}}
            if event['parent_outside_registered']:
                rendered['registrations'].append('parent')
            if event['child_outside_registered']:
                rendered['registrations'].append('child')
        elif kind == 'frame_start':
            require('frame' not in active, 'multiple frames per operation outside scoped pairing')
            active['frame'] = rendered
            rendered['scale'] = event['scale']
        elif kind == 'prepaint':
            rendered['bounds'][event['node']] = copy.deepcopy(event['bounds'])
        elif kind == 'callback':
            active['callbacks'].append({key: copy.deepcopy(event[key]) for key in ('name', 'before', 'after', 'button')})
            button = active['callbacks'][-1]['button']
            if button is not None:
                active['callbacks'][-1]['button'] = button.lower()
        elif kind == 'operation_end':
            active['state'] = copy.deepcopy(event['state'])
    return operations


def compare(rust, candidate, oracle_source, fixture, token):
    expected = project_rust(rust, oracle_source, fixture)
    require(type(candidate.get('schema_version')) is int and candidate['schema_version'] == 1, 'candidate schema')
    require(candidate.get('layer') == 'compiled-moonbit-popover-outside', 'candidate layer')
    require(rust['run_token'] == candidate.get('run_token') == token, 'paired token')
    require(same_value(candidate.get('input'), fixture), 'candidate input')
    require(set(candidate) == {'schema_version', 'layer', 'run_token', 'input', 'operations'}, 'candidate fields')
    require(isinstance(candidate['operations'],list), 'operations array')
    differences=[]
    for index in range(max(len(expected),len(candidate['operations']))):
        left=expected[index] if index<len(expected) else None
        right=candidate['operations'][index] if index<len(candidate['operations']) else None
        if not same_value(left,right):
            differences.append({'operation':left['operation'] if left else '<extra>', 'expected':left,'actual':right})
    return {'status': 'semantic_mismatch' if differences else 'match', 'differences':differences, 'events': len(fixture['steps']),
            'operations': len(expected), 'frames': sum('frame' in row for row in expected),
            'callbacks': sum(len(row['callbacks']) for row in expected),
            'execution_authenticated': False}
