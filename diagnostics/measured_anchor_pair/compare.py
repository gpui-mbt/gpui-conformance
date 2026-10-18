"""Strict, source-only measured-anchor comparator. This module executes no tools.

A passing comparison is geometry evidence only, never build authentication,
font-rendering parity, occlusion parity, or input-dispatch parity. Synthetic
fixtures and source-control predictions cannot authenticate real execution.
"""
import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

SPEC_SHA256 = 'dba66cc5599a99e4f74e58ea7bec0eff089e08bb42da663bf6ef1050cdc551eb'
EPSILON = 1 / 1024
UPSTREAM = '5a5fbe79917971a4d52a96b6ddb04da198a5012e'
VARIANTS = ['example_branch', 'asymmetric_fractional']
BASE_NODES = ['host', 'primary', 'primary_text', 'primary_anchor_static',
              'parent', 'parent_text', 'secondary', 'secondary_text']
CHILD_NODES = ['secondary_anchor_static', 'child', 'child_text']
QUADS = ['host', 'primary', 'parent', 'secondary']
EDGES = ('left', 'top', 'right', 'bottom')
CONTROLS = ('owner-origin', 'no-logical-rounding', 'eager-device-snap',
            'window-mode', 'stale-scale-metrics')


def canonical_fixture():
    steps = []
    for prefix, viewport, scale in [
        ('wide', [900, 700], 1), ('resize', [520, 360], 1),
        ('narrow', [320, 240], 1), ('restore', [900, 700], 1),
        ('fractional125', [519.5, 359.25], 1.25),
        ('fractional150', [519.5, 359.25], 1.5),
        ('fractional200', [519.5, 359.25], 2),
    ]:
        for nested in (False, True):
            steps.append(dict(id=prefix + ('-nested' if nested else '-parent'),
                              viewport=list(viewport), scale=scale, nested_open=nested))
    return dict(schema_version=1, variants=list(VARIANTS), steps=steps)


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def load(path):
    path = Path(path)
    if path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError('JSON input exceeds the 32 MiB read ceiling')
    return json.loads(path.read_text(), object_pairs_hook=_pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(
                          ValueError('nonfinite JSON: ' + value)))


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def same(left, right):
    """Typed JSON equality, with finite numeric int/float equivalence only."""
    if number(left) or number(right):
        return number(left) and number(right) and left == right
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(same(left[k], right[k]) for k in left)
    if type(left) is list:
        return len(left) == len(right) and all(same(a, b) for a, b in zip(left, right))
    return type(left) in (str, bool, type(None)) and left == right


def rectangle(value):
    return (type(value) is list and len(value) == 4
            and all(number(v) for v in value) and all(v >= 0 for v in value[2:]))


def physical_edges(bounds, scale):
    if not rectangle(bounds) or not number(scale) or scale <= 0:
        raise ValueError('finite rectangle and positive scale required')
    x, y, w, h = bounds
    result = [scale * x, scale * y, scale * (x + w), scale * (y + h)]
    if not all(number(v) for v in result):
        raise ValueError('physical projection overflow')
    return result


class Audit:
    def __init__(self):
        self.failures = []
        self.edge_residuals = []

    def fail(self, code, expected=None, actual=None, **context):
        self.failures.append(dict(code=code, expected=expected, actual=actual, **context))

    def check(self, condition, code, expected=None, actual=None, **context):
        if not condition:
            self.fail(code, expected, actual, **context)
        return bool(condition)

    def equal(self, actual, expected, code, **context):
        return self.check(same(actual, expected), code, expected, actual, **context)

    def rect(self, rust, core, scale, **context):
        """Every edge is emitted; each out-of-tolerance edge is a failure."""
        try:
            left, right = physical_edges(rust, scale), physical_edges(core, scale)
        except (ValueError, TypeError, OverflowError):
            self.fail('invalid_rectangle', rust, core, scale=scale, **context)
            return
        for edge, expected, actual in zip(EDGES, left, right):
            residual = actual - expected
            row = dict(edge=edge, rust=expected, core=actual,
                       signed_residual=residual, absolute_residual=abs(residual),
                       within_epsilon=abs(residual) <= EPSILON, scale=scale, **context)
            self.edge_residuals.append(row)
            if not row['within_epsilon']:
                self.fail('edge_residual', expected, actual, edge=edge,
                          signed_residual=residual, absolute_residual=abs(residual),
                          classification='unclassified_numeric_discrepancy',
                          scale=scale, **context)


def _obj(value, audit, code, **context):
    if audit.check(type(value) is dict, code, 'object', type(value).__name__, **context):
        return value
    return {}


def _list(value, audit, code, **context):
    if audit.check(type(value) is list, code, 'array', type(value).__name__, **context):
        return value
    return []


def _index(rows, key, audit, code, **context):
    result = {}
    for row in rows:
        if not audit.check(type(row) is dict and type(row.get(key)) is str,
                           code + '_row', key + ' string', row, **context):
            continue
        name = row[key]
        if audit.check(name not in result, code + '_duplicate', None, name, **context):
            result[name] = row
    return result


def _frame(rows, step, variant, audit):
    ctx = dict(variant=variant, operation=step['id'], backend='rust', stage='trace_structure')
    expected = BASE_NODES + (CHILD_NODES if step['nested_open'] else [])
    pre, paint, hits, texts, returns, starts = {}, {}, {}, {}, [], []
    for i, event in enumerate(rows):
        kind, node = event.get('type'), event.get('node')
        if kind == 'frame_start':
            starts.append(i)
            audit.equal(event.get('viewport'), step['viewport'], 'settled_viewport', **ctx)
            audit.equal(event.get('scale'), step['scale'], 'settled_scale', **ctx)
        elif kind in ('prepaint', 'paint', 'hitbox', 'text_inputs'):
            table = {'prepaint': pre, 'paint': paint, 'hitbox': hits, 'text_inputs': texts}[kind]
            valid = type(node) is str
            audit.check(valid, 'node_identity', 'string', node, **ctx)
            if not valid:
                continue
            if not audit.check(node not in table, kind + '_duplicate', None, node, **ctx):
                continue
            table[node] = (i, event)
            if kind != 'text_inputs':
                audit.check(rectangle(event.get('bounds')), 'finite_bounds', 'rectangle', event.get('bounds'), node=node, **ctx)
            else:
                audit.check(type(event.get('font_family')) is str and bool(event.get('font_family')),
                            'font_family', 'nonempty string', event.get('font_family'), node=node, **ctx)
                for metric in ('font_size', 'rem_size', 'line_height', 'units_per_em', 'ascent', 'descent', 'em_advance'):
                    value = event.get(metric)
                    audit.check(number(value), 'finite_font_metric', metric, value, node=node, **ctx)
                    if metric in ('font_size', 'rem_size', 'line_height', 'units_per_em', 'em_advance') and number(value):
                        audit.check(value > 0, 'positive_font_metric', metric, value, node=node, **ctx)
        elif kind == 'host_paint_return':
            returns.append(i)
        else:
            audit.fail('unknown_frame_event', None, kind, **ctx)
    audit.equal(starts, [0], 'frame_start_order', **ctx)
    audit.equal(list(pre), expected, 'prepaint_node_order', **ctx)
    audit.equal(list(paint), expected, 'paint_node_order', **ctx)
    audit.equal(sorted(texts), sorted(n for n in expected if n.endswith('_text')), 'text_node_presence', **ctx)
    expected_hit = ['primary', 'secondary', 'child' if step['nested_open'] else 'parent']
    audit.equal(list(hits), expected_hit, 'hitbox_node_order', **ctx)
    audit.equal(len(returns), 1, 'host_paint_return_count', **ctx)
    if len(returns) == 1 and 'host' in paint and 'parent' in paint:
        audit.check(paint['host'][0] < returns[0] < paint['parent'][0], 'deferred_paint_order', True, False, **ctx)
    for node in sorted(set(pre) & set(paint)):
        audit.check(pre[node][0] < paint[node][0], 'prepaint_before_paint', True, False, node=node, **ctx)
        audit.equal(paint[node][1].get('bounds'), pre[node][1].get('bounds'), 'rust_paint_bounds', node=node, **ctx)
    for node, (index, event) in hits.items():
        audit.equal(event.get('content_mask'), [0, 0, *step['viewport']], 'mask_equals_logical_viewport', node=node, **ctx)
        if node in pre and node in paint:
            audit.check(pre[node][0] < index < paint[node][0], 'hitbox_chronology', True, False, node=node, **ctx)
            audit.equal(event.get('bounds'), pre[node][1].get('bounds'), 'rust_hitbox_bounds', node=node, **ctx)
    return dict(**step, bounds={n: e['bounds'] for n, (_, e) in pre.items() if 'bounds' in e},
                paint={n: e.get('bounds') for n, (_, e) in paint.items()},
                hitboxes=[e for _, e in hits.values()], text_inputs=[e for _, e in texts.values()],
                attachments=[n for n in pre if n.endswith('_anchor_static')],
                paint_order=list(paint))


def normalize_rust(raw, fixture, audit=None):
    """Select the final frame inside each operation; never reuse earlier bounds."""
    audit = Audit() if audit is None else audit
    raw = _obj(raw, audit, 'rust_root', backend='rust', stage='schema')
    ctx = dict(backend='rust', stage='schema')
    audit.check(type(raw.get('schema_version')) is int and raw.get('schema_version') == 1,
                'schema_version', 1, raw.get('schema_version'), **ctx)
    for field, expected in [('layer', 'source-derived-padded-text-anchor'),
                            ('upstream_revision', UPSTREAM), ('text_backend', 'upstream-NoopTextSystem')]:
        audit.equal(raw.get(field), expected, field, **ctx)
    audit.equal(raw.get('input'), fixture, 'frozen_fixture', **ctx)
    variants = _list(raw.get('variants'), audit, 'variants_array', **ctx)
    audit.equal([v.get('variant') if type(v) is dict else None for v in variants], VARIANTS, 'variant_order', **ctx)
    result = []
    for variant in variants:
        if type(variant) is not dict:
            continue
        name = variant.get('variant')
        events = _list(variant.get('events'), audit, 'events_array', variant=name, **ctx)
        current, frames, operations, last_frame = None, {}, [], -1
        for sequence, row in enumerate(events):
            c = dict(variant=name, backend='rust', stage='trace_structure', sequence=sequence)
            if type(row) is not dict:
                audit.fail('event_row', 'object', row, **c)
                continue
            audit.check(type(row.get('sequence')) is int and row['sequence'] == sequence,
                        'sequence', sequence, row.get('sequence'), **c)
            frame = row.get('frame')
            valid_frame = type(frame) is int and frame >= last_frame and frame >= 0
            audit.check(valid_frame, 'frame_monotonicity', 'nondecreasing nonnegative integer', frame, **c)
            if type(frame) is int:
                last_frame = max(frame, last_frame)
            event = row.get('event')
            if not audit.check(type(event) is dict, 'event_object', 'object', event, **c):
                continue
            kind = event.get('type')
            if kind == 'operation_start':
                audit.check(current is None, 'operation_nesting', None, current, **c)
                current = row.get('operation')
                index = len(operations)
                expected = fixture['steps'][index] if index < len(fixture['steps']) else None
                audit.equal(current, expected['id'] if expected else None, 'operation_order', **c)
                if expected:
                    for key in ('viewport', 'scale', 'nested_open'):
                        audit.equal(event.get(key), expected[key], 'operation_' + key, operation=current, **c)
                audit.check(type(event.get('nested_open')) is bool, 'boolean_nested_state', 'bool', event.get('nested_open'), **c)
                frames = {}
            elif kind == 'operation_end':
                audit.check(current is not None, 'unmatched_operation_end', 'open operation', current, **c)
                audit.equal(row.get('operation'), current, 'operation_end_tag', **c)
                index = len(operations)
                step = fixture['steps'][index] if index < len(fixture['steps']) else None
                if audit.check(bool(frames), 'settled_frame_presence', 'at least one frame', len(frames), **c) and step:
                    op = _frame(frames[max(frames)], step, name, audit)
                    op['id'] = current
                    op['settled_frame'] = max(frames)
                    op['frames_in_operation'] = len(frames)
                    operations.append(op)
                else:
                    operations.append(dict(id=current))
                current, frames = None, {}
            else:
                allowed = {'frame_start', 'text_inputs', 'prepaint', 'paint', 'hitbox', 'host_paint_return'}
                audit.check(kind in allowed, 'event_kind', sorted(allowed), kind, **c)
                if current is None:
                    audit.check(not operations and row.get('operation') == 'bootstrap', 'unbracketed_event', 'bootstrap before first operation', row.get('operation'), **c)
                else:
                    audit.equal(row.get('operation'), current, 'operation_event_tag', **c)
                    if type(frame) is int:
                        frames.setdefault(frame, []).append(event)
        audit.equal(current, None, 'operation_closed', variant=name, **ctx)
        audit.equal([o.get('id') for o in operations], [s['id'] for s in fixture['steps']], 'operation_order', variant=name, **ctx)
        result.append(dict(variant=name, operations=operations))
    return result


def _paint_commands(op, expected_quads, audit, context):
    commands = _list(op.get('paint_commands'), audit, 'paint_commands_array', **context)
    stack, quads = [], []
    viewport = op.get('viewport')
    mask = [0, 0, *viewport] if type(viewport) is list else None
    anchors = ['host', 'primary_anchor_static'] + (['secondary_anchor_static'] if op.get('nested_open') is True else [])
    pushes, pops = [], []
    for index, command in enumerate(commands):
        if type(command) is not dict:
            audit.fail('paint_command_object', 'object', command, command=index, **context)
            continue
        node, kind = command.get('node'), command.get('kind')
        c = dict(node=node, command=index, **context)
        audit.check(type(command.get('clip_depth_before')) is int, 'clip_depth_integer', 'integer', command.get('clip_depth_before'), **c)
        audit.equal(command.get('clip_depth_before'), len(stack), 'clip_depth_before', **c)
        audit.equal(command.get('clip'), mask, 'paint_mask_equals_logical_viewport', **c)
        if kind == 'clip_push':
            pushes.append(node)
            audit.check(node in anchors and node not in stack, 'clip_push_identity', anchors, node, **c)
            audit.equal(command.get('bounds'), mask, 'clip_bounds_equal_logical_viewport', **c)
            stack.append(node)
        elif kind == 'clip_pop':
            pops.append(node)
            audit.equal(command.get('bounds'), None, 'clip_pop_bounds', **c)
            audit.equal(node, stack[-1] if stack else None, 'clip_pop_identity', **c)
            if stack:
                stack.pop()
        elif kind == 'quad':
            quads.append(node)
            audit.equal(command.get('bounds'), op.get('bounds', {}).get(node), 'quad_command_bounds', **c)
        else:
            audit.fail('paint_command_kind', ['quad', 'clip_push', 'clip_pop'], kind, **c)
        audit.check(type(command.get('clip_depth_after')) is int, 'clip_depth_integer', 'integer', command.get('clip_depth_after'), **c)
        audit.equal(command.get('clip_depth_after'), len(stack), 'clip_depth_after', **c)
        if 'clip_stack_after' in command:
            audit.equal(command['clip_stack_after'], stack, 'clip_stack_after', **c)
    audit.equal(quads, expected_quads, 'paint_command_quad_order', **context)
    audit.equal(pushes, anchors, 'clip_push_order', **context)
    audit.equal(sorted(pops), sorted(anchors), 'clip_pop_presence', **context)
    audit.equal(stack, [], 'clip_stack_restored', **context)
    # Production element paint retains each ancestor clip through deferred descendants.
    expected_commands = [('quad', 'host'), ('clip_push', 'host'), ('quad', 'primary'),
                         ('clip_push', 'primary_anchor_static'), ('quad', 'parent'), ('quad', 'secondary')]
    if op.get('nested_open') is True:
        expected_commands += [('clip_push', 'secondary_anchor_static'), ('quad', 'child'), ('clip_pop', 'secondary_anchor_static')]
    expected_commands += [('clip_pop', 'primary_anchor_static'), ('clip_pop', 'host')]
    audit.equal([[c.get('kind'), c.get('node')] for c in commands if type(c) is dict],
                [list(c) for c in expected_commands], 'paint_command_order', **context)


TEXTS = {
    'primary_text': 'Open Popover',
    'parent_text': 'This is first level Popover, we can use deferred to render it in a floating layer.\nClick outside to close.',
    'secondary_text': 'Child Popover',
    'child_text': 'This is second level Popover with nested deferred!',
}


def _source_inputs(op, variant, step, audit, context):
    source = _obj(op.get('source_inputs'), audit, 'source_inputs_object', **context)
    asymmetric = variant == 'asymmetric_fractional'
    fixed = dict(text_backend='source-derived-upstream-NoopTextSystem',
                 unbounded_available_width=0, rem_size=16, line_height_multiplier=1.618034,
                 inset_order='top,right,bottom,left', parent_width=384,
                 parent_padding=[12, 12, 12, 12], parent_border=[1, 1, 1, 1], parent_gap=12,
                 secondary_margin_top=8, secondary_margin_representation='unpainted-flow-wrapper-top-inset',
                 child_padding=[12, 12, 12, 12], child_border=[1, 1, 1, 1],
                 host_alignment='center,center', anchor='TopLeft', anchor_mode='Local',
                 anchor_position=[0, 0], anchor_margin=8, deferred_priorities=[1, 2],
                 button_padding=[3.75, 17.5, 6.5, 11.25] if asymmetric else [4, 12, 4, 12],
                 button_border=[0.75, 2.5, 1.5, 1.25] if asymmetric else [0, 0, 0, 0])
    scale = step['scale']
    authored = lambda value: math.ceil(value * scale - 0.5) / scale
    # Preserve the authored adapter's left-to-right Double subtraction association.
    paragraph_width = (authored(384) - authored(12) - authored(12)
                       - max(authored(1), 1 / scale) - max(authored(1), 1 / scale))
    fixed['parent_text_available_width'] = paragraph_width
    for key, expected in fixed.items():
        audit.equal(source.get(key), expected, 'source_input', field=key, **context)
    rows = _list(source.get('text'), audit, 'source_text_array', **context)
    expected_nodes = ['primary_text', 'parent_text', 'secondary_text'] + (['child_text'] if step['nested_open'] else [])
    audit.equal([r.get('node') if type(r) is dict else None for r in rows], expected_nodes, 'source_text_order', **context)
    for row in rows:
        if type(row) is not dict or row.get('node') not in TEXTS:
            continue
        node = row['node']
        for key, expected in [('text', TEXTS[node]), ('font_family', '.SystemUIFont'),
                              ('font_size', 16 if node == 'primary_text' else 14),
                              ('metrics_scale', scale), ('available_width', paragraph_width if node == 'parent_text' else 0)]:
            audit.equal(row.get(key), expected, 'source_text_input', node=node, field=key, **context)
        intrinsic = row.get('intrinsic')
        audit.check(type(intrinsic) is list and len(intrinsic) == 2 and all(number(v) and v >= 0 for v in intrinsic),
                    'source_text_intrinsic', 'finite nonnegative width,height', intrinsic, node=node, **context)
        metadata = _obj(row.get('metrics_metadata'), audit, 'metrics_metadata_object', node=node, **context)
        for key, expected in [('schema_version', 1), ('qualification', 'source-derived-NoopTextSystem-only'),
                              ('upstream_revision', UPSTREAM), ('arithmetic', 'adapter-local-binary32')]:
            audit.equal(metadata.get(key), expected, 'metrics_source_identity', node=node, field=key, **context)
        audit.check(type(metadata.get('schema_version')) is int, 'metrics_schema_integer', 'integer', metadata.get('schema_version'), node=node, **context)
        audit.equal([metadata.get('width'), metadata.get('height')], intrinsic, 'metrics_intrinsic_consistency', node=node, **context)


def normalize_core(raw, fixture, audit):
    raw = _obj(raw, audit, 'core_root', backend='moonbit-core', stage='schema')
    ctx = dict(backend='moonbit-core', stage='schema')
    audit.check(type(raw.get('schema_version')) is int and raw.get('schema_version') == 1,
                'schema_version', 1, raw.get('schema_version'), **ctx)
    audit.equal(raw.get('layer'), 'source-derived-measured-anchor-pair', 'layer', **ctx)
    audit.equal(raw.get('backend'), 'moonbit-core', 'backend', **ctx)
    audit.equal(raw.get('input'), fixture, 'frozen_fixture', **ctx)
    variants = _list(raw.get('variants'), audit, 'variants_array', **ctx)
    audit.equal([v.get('variant') if type(v) is dict else None for v in variants], VARIANTS, 'variant_order', **ctx)
    for variant in variants:
        if type(variant) is not dict:
            continue
        name = variant.get('variant')
        operations = _list(variant.get('operations'), audit, 'operations_array', variant=name, **ctx)
        audit.equal([o.get('id') if type(o) is dict else None for o in operations],
                    [s['id'] for s in fixture['steps']], 'operation_order', variant=name, **ctx)
        indexed = _index(operations, 'id', audit, 'operation', variant=name, **ctx)
        for step in fixture['steps']:
            op = indexed.get(step['id'])
            if op is None:
                continue
            c = dict(variant=name, operation=step['id'], backend='moonbit-core', stage='core_structure')
            for key in ('viewport', 'scale', 'nested_open'):
                audit.equal(op.get(key), step[key], key, **c)
            audit.check(type(op.get('nested_open')) is bool, 'boolean_nested_state', 'bool', op.get('nested_open'), **c)
            audit.equal(op.get('scene_valid'), True, 'scene_valid', **c)
            audit.equal(op.get('logical_viewport_mask'), [0, 0, *step['viewport']], 'logical_viewport_mask', **c)
            bounds = _obj(op.get('bounds'), audit, 'bounds_object', **c)
            expected = BASE_NODES + ['secondary_margin'] + (CHILD_NODES if step['nested_open'] else [])
            audit.equal(sorted(bounds), sorted(expected), 'node_presence', **c)
            for node, rect in bounds.items():
                audit.check(rectangle(rect), 'finite_bounds', 'rectangle', rect, node=node, **c)
            attachments = _list(op.get('attachments'), audit, 'attachments_array', **c)
            names = ['primary_anchor_static'] + (['secondary_anchor_static'] if step['nested_open'] else [])
            audit.equal([a.get('node') if type(a) is dict else None for a in attachments], names, 'attachment_order', **c)
            for attachment in attachments:
                if type(attachment) is not dict:
                    continue
                node = attachment.get('node')
                if node not in names:
                    continue
                prefix = 'primary' if node == 'primary_anchor_static' else 'secondary'
                audit.equal(attachment.get('reference'), prefix + '_text', 'attachment_reference', node=node, **c)
                audit.equal(attachment.get('popup'), 'parent' if prefix == 'primary' else 'child', 'attachment_popup', node=node, **c)
                if rectangle(bounds.get(node)):
                    audit.equal(attachment.get('static_origin'), bounds[node][:2], 'attachment_origin', node=node, **c)
                ref = bounds.get(prefix + '_text')
                if rectangle(ref) and rectangle(bounds.get(node)):
                    # Static anchor is measured text's bottom-left, not owner bounds.
                    audit.rect([ref[0], ref[1] + ref[3], 0, 0], [*bounds[node][:2], 0, 0], step['scale'],
                               node=node, backend='moonbit-core', stage='measured_reference',
                               variant=name, operation=step['id'])
            geometry = _list(op.get('corresponding_core_input_geometry'), audit, 'input_geometry_array', **c)
            hit_order = ['primary', 'secondary', 'child' if step['nested_open'] else 'parent']
            audit.equal([g.get('node') if type(g) is dict else None for g in geometry], hit_order, 'input_geometry_order', **c)
            for geom in geometry:
                if type(geom) is dict:
                    node = geom.get('node')
                    audit.equal(geom.get('bounds'), bounds.get(node), 'input_geometry_bounds', node=node, **c)
                    audit.equal(geom.get('content_mask'), [0, 0, *step['viewport']], 'mask_equals_logical_viewport', node=node, **c)
            paint = _list(op.get('paint_traversal'), audit, 'paint_traversal_array', **c)
            quad_order = QUADS + (['child'] if step['nested_open'] else [])
            audit.equal([p.get('node') if type(p) is dict else None for p in paint], quad_order, 'paint_order', **c)
            for painted in paint:
                if type(painted) is dict:
                    node = painted.get('node')
                    audit.equal(painted.get('bounds'), bounds.get(node), 'paint_bounds', node=node, **c)
                    audit.equal(painted.get('clip'), [0, 0, *step['viewport']], 'paint_mask_equals_logical_viewport', node=node, **c)
            _paint_commands(op, quad_order, audit, c)
            _source_inputs(op, name, step, audit, c)
    return variants


def _operation_map(variants):
    result = {}
    if type(variants) is not list:
        return result
    for variant in variants:
        if type(variant) is dict and type(variant.get('variant')) is str and type(variant.get('operations')) is list:
            for op in variant['operations']:
                if type(op) is dict and type(op.get('id')) is str:
                    result.setdefault((variant['variant'], op['id']), op)
    return result


def _restoration(operations, backend, audit):
    rows = []
    for variant in VARIANTS:
        for suffix in ('parent', 'nested'):
            original = operations.get((variant, 'wide-' + suffix), {})
            restored = operations.get((variant, 'restore-' + suffix), {})
            c = dict(backend=backend, stage='restoration', variant=variant, operation='restore-' + suffix)
            keys = ('viewport', 'scale', 'nested_open', 'bounds')
            keys += ('paint', 'hitboxes', 'attachments', 'paint_order', 'text_inputs') if backend == 'rust' else (
                'attachments', 'corresponding_core_input_geometry', 'paint_traversal', 'paint_commands', 'logical_viewport_mask')
            matches = []
            for key in keys:
                value = same(original.get(key), restored.get(key)) and key in original and key in restored
                audit.check(value, 'restoration_exact', original.get(key), restored.get(key), field=key, **c)
                matches.append(value)
            rows.append(dict(**c, exact=all(matches)))
    return rows


def _secondary_proof(core, rust, audit):
    rows = []
    for (variant, operation), op in core.items():
        b, scale = op.get('bounds', {}), op.get('scale')
        if type(b) is not dict or not number(scale) or scale <= 0:
            continue
        c = dict(variant=variant, operation=operation, scale=scale, backend='moonbit-core', stage='secondary_margin_proof')
        source = _obj(op.get('source_inputs'), audit, 'source_inputs', **c)
        audit.equal(source.get('secondary_margin_top'), 8, 'authored_secondary_margin', **c)
        audit.equal(source.get('parent_gap'), 12, 'authored_parent_gap', **c)
        if not all(rectangle(b.get(n)) for n in ('secondary_margin', 'secondary', 'parent_text')):
            continue
        margin, secondary, text = b['secondary_margin'], b['secondary'], b['parent_text']
        measurements = {
            'top_inset': (secondary[1] - margin[1], 8),
            'preceding_gap': (margin[1] - text[1] - text[3], 12),
            'same_left': (secondary[0] - margin[0], 0),
            'same_width': (secondary[2] - margin[2], 0),
            'wrapper_extra_height': (margin[3] - secondary[3], 8),
        }
        for name, (actual, expected) in measurements.items():
            residual = scale * (actual - expected)
            row = dict(**c, proof=name, expected_logical=expected, actual_logical=actual,
                       signed_physical_residual=residual, within_epsilon=abs(residual) <= EPSILON)
            rows.append(row)
            audit.check(row['within_epsilon'], 'secondary_margin_geometry', expected * scale, actual * scale,
                        proof=name, signed_residual=residual, **c)
        rb = rust.get((variant, operation), {}).get('bounds', {})
        if rectangle(rb.get('secondary')) and rectangle(rb.get('parent_text')):
            distance = rb['secondary'][1] - rb['parent_text'][1] - rb['parent_text'][3]
            residual = scale * (distance - 20)
            rows.append(dict(**{**c, 'backend': 'rust'}, proof='gap_plus_margin', expected_logical=20,
                             actual_logical=distance, signed_physical_residual=residual,
                             within_epsilon=abs(residual) <= EPSILON))
            audit.check(abs(residual) <= EPSILON, 'rust_gap_plus_margin', 20 * scale, distance * scale,
                        **{**c, 'backend': 'rust'})
    return rows


def compare(rust, core, fixture=None, token=None):
    """Compare the complete frozen corpus. All differences remain strict failures."""
    audit = Audit()
    canonical = canonical_fixture()
    supplied = canonical if fixture is None else fixture
    audit.equal(supplied, canonical, 'canonical_fixture', backend='pair', stage='frozen_spec')
    spec_path = Path(__file__).with_name('comparison_spec.json')
    digest = hashlib.sha256(spec_path.read_bytes()).hexdigest() if spec_path.is_file() else None
    audit.equal(digest, SPEC_SHA256, 'frozen_spec_digest', backend='pair', stage='frozen_spec')
    # Never let a modified fixture redefine the expected operations or tolerance.
    fixture = canonical
    rv = normalize_rust(rust, fixture, audit)
    cv = normalize_core(core, fixture, audit)
    for backend, raw in [('rust', rust), ('moonbit-core', core)]:
        actual = raw.get('run_token') if type(raw) is dict else None
        audit.check(type(actual) is str and bool(actual), 'run_token_nonempty', 'nonempty string', actual, backend=backend, stage='schema')
        if token is not None:
            audit.equal(actual, token, 'run_token', backend=backend, stage='schema')
    if type(rust) is dict and type(core) is dict:
        audit.equal(core.get('run_token'), rust.get('run_token'), 'paired_run_token', backend='pair', stage='schema')
    rm, cm = _operation_map(rv), _operation_map(cv)
    counts = {
        'rust_settled_operations': sum(len(v.get('operations', [])) for v in rv if type(v) is dict),
        'core_settled_operations': sum(len(v.get('operations', [])) for v in cv if type(v) is dict and type(v.get('operations')) is list),
        'rust_attachments': sum(len(o.get('attachments', [])) for o in rm.values()),
        'core_attachments': sum(len(o.get('attachments', [])) for o in cm.values() if type(o.get('attachments')) is list),
        'rust_div_hitboxes': sum(len(o.get('hitboxes', [])) for o in rm.values()),
        'corresponding_core_input_geometry': sum(len(o.get('corresponding_core_input_geometry', [])) for o in cm.values() if type(o.get('corresponding_core_input_geometry')) is list),
    }
    for key, expected in [('rust_settled_operations', 28), ('core_settled_operations', 28),
                          ('rust_attachments', 42), ('core_attachments', 42),
                          ('rust_div_hitboxes', 84), ('corresponding_core_input_geometry', 84)]:
        audit.equal(counts[key], expected, 'corpus_count', backend='pair', stage='corpus', field=key)
    for variant in VARIANTS:
        for step in fixture['steps']:
            key = (variant, step['id'])
            r, c = rm.get(key, {}), cm.get(key, {})
            rb, cb = r.get('bounds', {}), c.get('bounds', {})
            if type(rb) is not dict or type(cb) is not dict:
                continue
            ctx = dict(variant=variant, operation=step['id'], backend='moonbit-core-minus-rust')
            expected = BASE_NODES + (CHILD_NODES if step['nested_open'] else [])
            for node in expected:
                if node in rb and node in cb:
                    audit.rect(rb[node], cb[node], step['scale'], node=node, stage='layout_prepaint', **ctx)
            for stage, rust_rows, core_rows in [
                ('input_geometry', r.get('hitboxes', []), c.get('corresponding_core_input_geometry', [])),
                ('paint', [dict(node=n, bounds=r.get('paint', {}).get(n)) for n in QUADS + (['child'] if step['nested_open'] else [])], c.get('paint_traversal', [])),
            ]:
                if type(rust_rows) is not list or type(core_rows) is not list:
                    continue
                ri = _index(rust_rows, 'node', audit, stage, stage=stage, **ctx)
                ci = _index(core_rows, 'node', audit, stage, stage=stage, **ctx)
                for node in sorted(ri.keys() & ci.keys()):
                    audit.rect(ri[node].get('bounds'), ci[node].get('bounds'), step['scale'], node=node, stage=stage, **ctx)
    restoration = _restoration(rm, 'rust', audit) + _restoration(cm, 'moonbit-core', audit)
    proofs = _secondary_proof(cm, rm, audit)
    return dict(schema_version=1, status='strict_match' if not audit.failures else 'strict_fail',
                strict_match=not audit.failures, execution_authenticated=False,
                comparison_spec_sha256=digest, absolute_epsilon=EPSILON, inclusive=True,
                counts=counts, failure_count=len(audit.failures), failures=audit.failures,
                edge_residuals=audit.edge_residuals,
                maximum_absolute_residual=max((r['absolute_residual'] for r in audit.edge_residuals), default=None),
                secondary_margin_proofs=proofs, restoration=restoration,
                qualification='Bounded source-derived NoopTextSystem text/layout pairing; no native-font, glyph painting, full-popover, occlusion or input-dispatch parity claim.')


def _round_away(value):
    return math.copysign(math.floor(abs(value) + 0.5), value)


def _round_toward_zero(value):
    return math.copysign(math.ceil(abs(value) - 0.5), value)


def _source_line_height(font, scale):
    f32 = lambda value: struct.unpack('!f', struct.pack('!f', value))[0]
    line = f32(f32(font) * f32(1.618034))
    rounded = math.ceil(f32(abs(f32(line * f32(scale))) - 0.5))
    return f32(rounded / f32(scale))


def _fit(origin, size, viewport, margin=8):
    result = list(origin)
    for axis in (0, 1):
        if result[axis] + size[axis] > viewport[axis]:
            result[axis] -= result[axis] + size[axis] - viewport[axis] + margin
        if result[axis] < 0:
            result[axis] = margin
    return result


def control_witness(name, baseline_core, mutant_core, fixture=None):
    """Independent relational/rounding witnesses, never a generic 'red' predicate.

    The rounding witnesses predict baseline and mutant popup translations from
    static geometry, not from observed mutant-minus-baseline output. When the
    available trace cannot prove the prediction, the control is inconclusive.
    """
    if name not in CONTROLS:
        raise ValueError('unknown source mutation control: ' + str(name))
    baseline = _operation_map(baseline_core.get('variants', []))
    mutant = _operation_map(mutant_core.get('variants', []))
    witnesses, candidates = [], []
    for key, b in baseline.items():
        m = mutant.get(key)
        if m is None:
            continue
        variant, operation = key
        bb, mb, scale = b.get('bounds', {}), m.get('bounds', {}), b.get('scale')
        if not number(scale) or scale <= 0 or not same(m.get('scale'), scale):
            continue
        predictions = []
        if name == 'owner-origin' and operation == 'wide-parent':
            if all(rectangle(bb.get(n)) and rectangle(mb.get(n)) for n in ('primary', 'primary_text', 'primary_anchor_static')):
                predictions.append(('primary_anchor_static',
                                    [bb['primary_text'][0], bb['primary_text'][1] + bb['primary_text'][3]],
                                    [mb['primary'][0], mb['primary'][1] + mb['primary'][3]],
                                    'measured text bottom-left becomes owner border-box bottom-left'))
        elif name == 'window-mode' and operation == 'wide-parent':
            if all(rectangle(bb.get(n)) and rectangle(mb.get(n)) for n in ('primary_anchor_static', 'parent')):
                predictions.append(('parent', bb['primary_anchor_static'][:2], [0, 0],
                                    'Local zero position becomes Window zero position with no crossed edge'))
        elif name == 'stale-scale-metrics' and operation.startswith('fractional125'):
            # Child Popover is a single 14px line. The authored phi line height
            # is snapped using binary32 at metric scale, then its measured size
            # is ceiled to the core's actual device scale. No raw trace is an
            # input to this independently predicted metric value.
            if rectangle(bb.get('secondary_text')) and rectangle(mb.get('secondary_text')):
                expected_base = math.ceil(_source_line_height(14, scale) * scale) / scale
                expected_mutant = math.ceil(_source_line_height(14, 1) * scale) / scale
                actual_base, actual_mutant = bb['secondary_text'][3], mb['secondary_text'][3]
                row = dict(variant=variant, operation=operation, node='secondary_text', scale=scale,
                           semantic='14px one-line source metric uses stale scale1 before actual-scale measured ceiling',
                           expected_baseline=[expected_base], expected_mutant=[expected_mutant],
                           actual_baseline=[actual_base], actual_mutant=[actual_mutant])
                row['predicted_displacement_physical'] = [scale * (expected_mutant - expected_base)]
                row['observed_displacement_physical'] = [scale * (actual_mutant - actual_base)]
                row['witnessed'] = (abs(scale * (actual_base - expected_base)) <= EPSILON
                    and abs(scale * (actual_mutant - expected_mutant)) <= EPSILON
                    and abs(scale * (expected_mutant - expected_base)) > EPSILON)
                candidates.append(row)
                if row['witnessed']:
                    witnesses.append(row)
        elif name in ('no-logical-rounding', 'eager-device-snap') and scale != 1:
            for anchor, popup in [('primary_anchor_static', 'parent'), ('secondary_anchor_static', 'child')]:
                if (name == 'eager-device-snap' and popup != 'child') or (name == 'no-logical-rounding' and popup != 'parent'):
                    continue  # Parent-only no-round witness avoids assuming inherited raw offsets.
                if not all(rectangle(table.get(node)) for table in (bb, mb) for node in (anchor, popup)):
                    continue
                if not same(bb[anchor], mb[anchor]) or not same(bb[popup][2:], mb[popup][2:]):
                    continue  # Inherited changes need more trace evidence, not a guessed witness.
                origin, size = bb[anchor][:2], bb[popup][2:]
                fitted = _fit(origin, size, b['viewport'])
                offset = [fitted[i] - origin[i] for i in (0, 1)]
                rounded = [_round_away(v) for v in offset]
                predicted_base = [origin[i] + _round_toward_zero(rounded[i] * scale) / scale for i in (0, 1)]
                if name == 'no-logical-rounding':
                    predicted_mutant = [origin[i] + _round_toward_zero(offset[i] * scale) / scale for i in (0, 1)]
                    predictions.append((popup, predicted_base, predicted_mutant,
                                        'fitted offset is device-snapped without logical half-away rounding'))
                else:
                    # The eager bug acts on the unsnapped inherited translation.
                    # Reconstruct it from the parent anchor's fit, independently
                    # of the child output; require enough trace to prove both.
                    if not all(rectangle(bb.get(n)) for n in ('primary_anchor_static', 'parent')):
                        continue
                    parent_origin = bb['primary_anchor_static'][:2]
                    parent_fitted = _fit(parent_origin, bb['parent'][2:], b['viewport'])
                    inherited = [_round_away(parent_fitted[i] - parent_origin[i]) for i in (0, 1)]
                    inherited_snap = [_round_toward_zero(v * scale) / scale for v in inherited]
                    parent_expected = [parent_origin[i] + inherited_snap[i] for i in (0, 1)]
                    if not all(abs(scale * (bb['parent'][i] - parent_expected[i])) <= EPSILON
                               and abs(scale * (mb['parent'][i] - parent_expected[i])) <= EPSILON for i in (0, 1)):
                        continue
                    base = [origin[i] - inherited_snap[i] + _round_toward_zero((inherited[i] + rounded[i]) * scale) / scale for i in (0, 1)]
                    eager = [origin[i] - inherited_snap[i] + _round_toward_zero((inherited_snap[i] + _round_toward_zero(rounded[i] * scale) / scale) * scale) / scale for i in (0, 1)]
                    predictions.append((popup, base, eager,
                                        'device snapping each local offset precedes inherited translation sum'))
        for node, expected_b, expected_m, semantic in predictions:
            if not rectangle(bb.get(node)) or not rectangle(mb.get(node)):
                continue
            actual_b, actual_m = bb[node][:2], mb[node][:2]
            predicted = [scale * (y - x) for x, y in zip(expected_b, expected_m)]
            observed = [scale * (y - x) for x, y in zip(actual_b, actual_m)]
            witnessed = (max(map(abs, predicted), default=0) > EPSILON
                and all(abs(scale * (x - y)) <= EPSILON for x, y in zip(actual_b, expected_b))
                and all(abs(scale * (x - y)) <= EPSILON for x, y in zip(actual_m, expected_m)))
            row = dict(variant=variant, operation=operation, node=node, scale=scale, semantic=semantic,
                       expected_baseline=expected_b, expected_mutant=expected_m,
                       actual_baseline=actual_b, actual_mutant=actual_m,
                       predicted_displacement_physical=predicted,
                       observed_displacement_physical=observed, witnessed=witnessed)
            candidates.append(row)
            if witnessed:
                witnesses.append(row)
    return dict(control=name, witnessed=bool(witnesses), witnesses=witnesses, candidates=candidates,
                execution_authenticated=False)


def evaluate_control(name, baseline_report, mutant_report, baseline_core, mutant_core,
                     fixture=None, execution=None):
    """Require execution success AND predicted semantic change AND extra violation.

    A failed compilation, changed exit code, already-red baseline, unchanged
    residual, or an unrelated new failure never kills a production-path control.
    """
    proof = control_witness(name, baseline_core, mutant_core, fixture)
    execution = {} if execution is None else execution
    executed = all(type(execution.get(k)) is int and execution[k] == 0
                   for k in ('build_returncode', 'execution_returncode'))
    def edge_key(row):
        return tuple(row.get(k) for k in ('variant', 'operation', 'node', 'stage', 'edge'))
    before = {edge_key(r): r for r in baseline_report.get('edge_residuals', [])}
    sites = {(w['variant'], w['operation'], w['node']) for w in proof['witnesses']}
    additions = []
    for row in mutant_report.get('edge_residuals', []):
        if (row.get('variant'), row.get('operation'), row.get('node')) not in sites:
            continue
        previous = before.get(edge_key(row))
        if previous is None:
            continue
        old, new = previous.get('absolute_residual'), row.get('absolute_residual')
        displacement = row.get('core', 0) - previous.get('core', 0)
        if number(old) and number(new) and new > EPSILON and new > old and abs(displacement) > EPSILON:
            additions.append(dict(key=list(edge_key(row)), baseline_absolute_residual=old,
                                  mutant_absolute_residual=new, signed_candidate_displacement=displacement))
    killed = executed and proof['witnessed'] and bool(additions)
    return dict(control=name, status='killed' if killed else 'inconclusive', killed=killed,
                compiled_and_executed=executed, semantic_witness=proof,
                additional_violations=additions,
                baseline_strict_match=baseline_report.get('strict_match') is True,
                mutant_strict_match=mutant_report.get('strict_match') is True,
                execution_authenticated=False,
                reason=('predicted semantic witness and new/worse strict residual after successful execution'
                        if killed else 'requires successful compilation/execution, an independent semantic witness, and a new/worse violation at that witness'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rust')
    parser.add_argument('core')
    parser.add_argument('--fixture')
    parser.add_argument('--token')
    parser.add_argument('--output')
    args = parser.parse_args()
    result = compare(load(args.rust), load(args.core), load(args.fixture) if args.fixture else None, args.token)
    rendered = json.dumps(result, indent=2, allow_nan=False) + '\n'
    if args.output:
        Path(args.output).write_text(rendered)
    else:
        print(rendered, end='')
    return 0 if result['strict_match'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
