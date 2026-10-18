"""Source-only synthetic comparator/runner tests. No build or execution evidence.

All fabricated geometry below is validator input, never a parity golden. No
compiler, package manager, installer, or network is invoked. The determinism
regression launches only this Python validator under explicit hash seeds.
"""
import copy
import hashlib
import importlib.util
import inspect
import json
import math
import os
import subprocess
import struct
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'diagnostics/measured_anchor_pair'


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


sys.path.insert(0, str(DIRECTORY))
compare = module(DIRECTORY / 'compare.py', 'measured_pair_compare_tests')
run = module(DIRECTORY / 'run.py', 'measured_pair_run_tests')
controls = module(DIRECTORY / 'run_controls.py', 'measured_pair_control_tests')
evidence = module(DIRECTORY / 'evidence.py', 'measured_pair_evidence_tests')
sys.path.pop(0)


def source_inputs(variant, step):
    asymmetric = variant == 'asymmetric_fractional'
    scale = step['scale']
    authored = lambda v: math.ceil(v * scale - 0.5) / scale
    paragraph_width = (authored(384) - authored(12) - authored(12)
                       - max(authored(1), 1 / scale) - max(authored(1), 1 / scale))
    source = dict(text_backend='source-derived-upstream-NoopTextSystem',
                  unbounded_available_width=0, rem_size=16, line_height_multiplier=1.618034,
                  inset_order='top,right,bottom,left', parent_width=384,
                  parent_padding=[12] * 4, parent_border=[1] * 4, parent_gap=12,
                  secondary_margin_top=8, secondary_margin_representation='unpainted-flow-wrapper-top-inset',
                  child_padding=[12] * 4, child_border=[1] * 4,
                  host_alignment='center,center', anchor='TopLeft', anchor_mode='Local',
                  anchor_position=[0, 0], anchor_margin=8, deferred_priorities=[1, 2],
                  button_padding=[3.75, 17.5, 6.5, 11.25] if asymmetric else [4, 12, 4, 12],
                  button_border=[0.75, 2.5, 1.5, 1.25] if asymmetric else [0, 0, 0, 0],
                  parent_text_available_width=paragraph_width)
    names = ['primary_text', 'parent_text', 'secondary_text'] + (['child_text'] if step['nested_open'] else [])
    source['text'] = [dict(node=node, text=compare.TEXTS[node], font_family='.SystemUIFont',
                          font_size=16 if node == 'primary_text' else 14,
                          available_width=paragraph_width if node == 'parent_text' else 0,
                          metrics_scale=scale, intrinsic=[10, 10],
                          metrics_metadata=dict(schema_version=1, qualification='source-derived-NoopTextSystem-only',
                                                upstream_revision=compare.UPSTREAM,
                                                arithmetic='adapter-local-binary32', width=10, height=10)) for node in names]
    return source


def synthetic_bounds(step):
    """Intentionally invented rectangles, not observed GPUI output."""
    scale = step['scale']
    snap = lambda v: compare._round_toward_zero(v * scale) / scale
    bounds = dict(host=[0, 0, *map(snap, step['viewport'])], primary=[40, 40, 100, 40],
                  primary_text=[52, 44, 76, 26], primary_anchor_static=[52, 70, 384, 146],
                  parent=[52, 70, 384, 146], parent_text=[65, 83, 358, 69],
                  secondary_margin=[100, 164, 134, 39], secondary=[100, 172, 134, 31],
                  secondary_text=[112, 176, 110, 23])
    if step['nested_open']:
        bounds.update(secondary_anchor_static=[112, 199, 446, 49], child=[112, 199, 446, 49],
                      child_text=[125, 212, 420, 23])
    return bounds


def repaint(op):
    bounds = op['bounds']
    mask = [0, 0, *op['viewport']]
    quads = compare.QUADS + (['child'] if op['nested_open'] else [])
    op['paint_traversal'] = [dict(node=n, bounds=copy.deepcopy(bounds[n]), clip=list(mask)) for n in quads]
    order = [('quad', 'host'), ('clip_push', 'host'), ('quad', 'primary'),
             ('clip_push', 'primary_anchor_static'), ('quad', 'parent'), ('quad', 'secondary')]
    if op['nested_open']:
        order += [('clip_push', 'secondary_anchor_static'), ('quad', 'child'), ('clip_pop', 'secondary_anchor_static')]
    order += [('clip_pop', 'primary_anchor_static'), ('clip_pop', 'host')]
    stack, commands = [], []
    for kind, node in order:
        before = len(stack)
        if kind == 'clip_push':
            stack.append(node)
        elif kind == 'clip_pop':
            stack.pop()
        commands.append(dict(kind=kind, node=node,
                             bounds=copy.deepcopy(bounds[node]) if kind == 'quad' else (list(mask) if kind == 'clip_push' else None),
                             clip=list(mask), clip_depth_before=before, clip_depth_after=len(stack),
                             clip_stack_after=list(stack)))
    op['paint_commands'] = commands
    op['corresponding_core_input_geometry'] = [dict(node=n, bounds=copy.deepcopy(bounds[n]), content_mask=list(mask))
        for n in ['primary', 'secondary', 'child' if op['nested_open'] else 'parent']]
    op['attachments'] = ([dict(node=n, reference=reference, popup=popup, static_origin=bounds[n][:2])
                         for n, reference, popup in [('primary_anchor_static', 'primary_text', 'parent')]]
                         + ([dict(node='secondary_anchor_static', reference='secondary_text', popup='child',
                                  static_origin=bounds['secondary_anchor_static'][:2])] if op['nested_open'] else []))


def synthetic_pair():
    fixture = compare.canonical_fixture()
    rust = dict(schema_version=1, layer='source-derived-padded-text-anchor',
                upstream_revision=compare.UPSTREAM, text_backend='upstream-NoopTextSystem',
                run_token='synthetic-never-executed', input=copy.deepcopy(fixture), variants=[])
    core = dict(schema_version=1, layer='source-derived-measured-anchor-pair', backend='moonbit-core',
                run_token=rust['run_token'], input=copy.deepcopy(fixture), variants=[])
    for variant in fixture['variants']:
        events, operations = [], []
        for index, step in enumerate(fixture['steps']):
            frame = index + 1
            b = synthetic_bounds(step)
            def emit(event):
                events.append(dict(sequence=len(events), frame=frame, operation=step['id'], event=event))
            emit(dict(type='operation_start', **{k: step[k] for k in ('viewport', 'scale', 'nested_open')}))
            emit(dict(type='frame_start', viewport=step['viewport'], scale=step['scale']))
            nodes = compare.BASE_NODES + (compare.CHILD_NODES if step['nested_open'] else [])
            for node in nodes:
                if node.endswith('_text'):
                    emit(dict(type='text_inputs', node=node, font_family='.SystemUIFont', font_size=16,
                              rem_size=16, line_height=26, units_per_em=1000, ascent=16.4,
                              descent=-4.4, em_advance=9.6))
            for node in nodes:
                emit(dict(type='prepaint', node=node, bounds=copy.deepcopy(b[node])))
            for node in ['primary', 'secondary', 'child' if step['nested_open'] else 'parent']:
                emit(dict(type='hitbox', node=node, bounds=copy.deepcopy(b[node]), content_mask=[0, 0, *step['viewport']]))
            for node in nodes:
                if node == 'primary_anchor_static':
                    emit(dict(type='host_paint_return'))
                emit(dict(type='paint', node=node, bounds=copy.deepcopy(b[node])))
            emit(dict(type='operation_end'))
            op = dict(**copy.deepcopy(step), bounds=copy.deepcopy(b), source_inputs=source_inputs(variant, step),
                      scene_valid=True, logical_viewport_mask=[0, 0, *step['viewport']])
            repaint(op)
            operations.append(op)
        rust['variants'].append(dict(variant=variant, events=events))
        core['variants'].append(dict(variant=variant, operations=operations))
    return rust, core, fixture


def op(core, name='fractional200-parent', variant=0):
    return next(o for o in core['variants'][variant]['operations'] if o['id'] == name)


class ComparatorTests(unittest.TestCase):
    def setUp(self):
        self.rust, self.core, self.fixture = synthetic_pair()

    def report(self):
        return compare.compare(self.rust, self.core, self.fixture, 'synthetic-never-executed')

    def codes(self, report):
        return {row['code'] for row in report['failures']}

    def test_synthetic_complete_pair_cannot_authenticate_execution(self):
        report = self.report()
        self.assertTrue(report['strict_match'], report['failures'][:8])
        self.assertFalse(report['execution_authenticated'])
        self.assertEqual(report['counts'], dict(rust_settled_operations=28, core_settled_operations=28,
            rust_attachments=42, core_attachments=42, rust_div_hitboxes=84, corresponding_core_input_geometry=84))
        self.assertEqual(report['maximum_absolute_residual'], 0)
        self.assertEqual(len(report['restoration']), 8)
        self.assertEqual(len(report['secondary_margin_proofs']), 28 * 6)
        self.assertTrue(all(row['within_epsilon'] for row in report['edge_residuals']))

    def test_physical_projection_and_inclusive_epsilon(self):
        self.assertEqual(compare.physical_edges([2, 3, 4, 5], 1.5), [3, 4.5, 9, 12])
        target = op(self.core)
        target['bounds']['primary'][0] += compare.EPSILON / target['scale']
        repaint(target)
        report = self.report()
        self.assertTrue(report['strict_match'], report['failures'][:3])
        self.assertEqual(report['maximum_absolute_residual'], compare.EPSILON)
        target['bounds']['primary'][0] += compare.EPSILON / target['scale']
        repaint(target)
        report = self.report()
        self.assertFalse(report['strict_match'])
        self.assertEqual(report['maximum_absolute_residual'], 2 * compare.EPSILON)

    def test_logical_tolerance_cannot_replace_physical_tolerance(self):
        target = op(self.core)
        target['bounds']['primary'][0] += 0.75 * compare.EPSILON
        repaint(target)
        report = self.report()
        self.assertFalse(report['strict_match'])
        self.assertEqual(report['maximum_absolute_residual'], 1.5 * compare.EPSILON)

    def test_far_edge_is_origin_plus_size_and_signed_residuals_retained(self):
        target = op(self.core)
        target['bounds']['primary'][0] -= 0.5
        target['bounds']['primary'][2] += 0.5
        repaint(target)
        report = self.report()
        rows = [r for r in report['edge_residuals'] if r['stage'] == 'layout_prepaint'
                and r['variant'] == 'example_branch' and r['operation'] == target['id'] and r['node'] == 'primary']
        self.assertEqual([r['signed_residual'] for r in rows], [-1, 0, 0, 0])
        self.assertFalse(report['strict_match'])

    def test_all_failures_survive_source_explanation_and_are_not_aggregated_away(self):
        target = op(self.core)
        target['bounds']['primary'][0] += 1
        target['bounds']['child_text'] = [0, 0, 1, 1]
        target['source_explanation'] = 'Double/f32 expected difference; please ignore'
        repaint(target)
        report = self.report()
        self.assertFalse(report['strict_match'])
        self.assertGreaterEqual(len([f for f in report['failures'] if f['code'] == 'edge_residual']), 6)
        self.assertIn('node_presence', self.codes(report))
        self.assertEqual(report['failure_count'], len(report['failures']))

    def test_counts_nodes_order_and_typed_state_are_exact(self):
        for mutation, code in [
            (lambda c: op(c)['corresponding_core_input_geometry'].pop(), 'corpus_count'),
            (lambda c: op(c)['bounds'].pop('primary_text'), 'node_presence'),
            (lambda c: c['variants'].reverse(), 'variant_order'),
            (lambda c: c['variants'][0]['operations'].reverse(), 'operation_order'),
            (lambda c: op(c).__setitem__('nested_open', 0), 'boolean_nested_state'),
            (lambda c: op(c).__setitem__('scene_valid', 1), 'scene_valid'),
            (lambda c: op(c)['attachments'].append(copy.deepcopy(op(c)['attachments'][0])), 'attachment_order'),
        ]:
            with self.subTest(code=code):
                candidate = copy.deepcopy(self.core)
                mutation(candidate)
                report = compare.compare(self.rust, candidate, self.fixture)
                self.assertFalse(report['strict_match'])
                self.assertIn(code, self.codes(report))

    def test_logical_mask_is_not_snapped_host_bounds(self):
        target = op(self.core, 'fractional125-parent')
        self.assertNotEqual(target['bounds']['host'], target['logical_viewport_mask'])
        self.assertTrue(self.report()['strict_match'])
        target['corresponding_core_input_geometry'][0]['content_mask'] = target['bounds']['host'][:]
        report = self.report()
        self.assertIn('mask_equals_logical_viewport', self.codes(report))

    def test_secondary_margin_and_gap_proved_independently(self):
        target = op(self.core)
        target['bounds']['secondary_margin'][1] += 2
        target['bounds']['secondary_margin'][3] -= 2
        report = self.report()
        failures = [f for f in report['failures'] if f['code'] == 'secondary_margin_geometry']
        self.assertEqual({f['proof'] for f in failures}, {'top_inset', 'preceding_gap', 'wrapper_extra_height'})
        self.assertEqual(target['bounds']['secondary'][1] - sum(target['bounds']['parent_text'][i] for i in (1, 3)), 20)

    def test_measured_reference_and_popup_final_bounds_both_compared(self):
        target = op(self.core, 'fractional125-nested')
        target['bounds']['secondary_anchor_static'][0] += 1
        target['bounds']['child'][0] -= 1
        repaint(target)
        report = self.report()
        failures = {(f.get('stage'), f.get('node')) for f in report['failures']}
        self.assertIn(('measured_reference', 'secondary_anchor_static'), failures)
        self.assertIn(('layout_prepaint', 'secondary_anchor_static'), failures)
        self.assertIn(('layout_prepaint', 'child'), failures)

    def test_restoration_is_exact_even_below_edge_epsilon(self):
        target = op(self.core, 'restore-parent')
        target['bounds']['primary'][0] += compare.EPSILON / 2
        repaint(target)
        report = self.report()
        self.assertFalse(report['strict_match'])
        self.assertIn('restoration_exact', self.codes(report))
        self.assertNotIn('edge_residual', self.codes(report))

    def test_source_width_preserves_sequential_double_association(self):
        target = next(o for o in self.core['variants'][0]['operations'] if o['scale'] == 1.5)
        authored = lambda value: math.ceil(value * 1.5 - 0.5) / 1.5
        sequential = authored(384) - authored(12) - authored(12) - authored(1) - authored(1)
        grouped = authored(384) - 2 * authored(12) - 2 * authored(1)
        self.assertNotEqual(sequential, grouped)
        self.assertEqual(struct.pack('>f', sequential).hex(), '43b35555')
        self.assertEqual(struct.pack('>f', sequential), struct.pack('>f', grouped))
        self.assertEqual(target['source_inputs']['parent_text_available_width'], sequential)
        self.assertTrue(self.report()['strict_match'])
        target['source_inputs']['parent_text_available_width'] = grouped
        next(row for row in target['source_inputs']['text'] if row['node'] == 'parent_text')['available_width'] = grouped
        report = self.report()
        self.assertIn('source_input', self.codes(report))
        self.assertIn('source_text_input', self.codes(report))

    def test_flattened_balanced_clips_are_rejected(self):
        target = op(self.core)
        commands = target['paint_commands']
        host_pop = commands.pop()
        commands.insert(3, host_pop)
        stack = []
        for command in commands:
            command['clip_depth_before'] = len(stack)
            if command['kind'] == 'clip_push':
                stack.append(command['node'])
            elif command['kind'] == 'clip_pop':
                stack.pop()
            command['clip_depth_after'] = len(stack)
            command['clip_stack_after'] = list(stack)
        report = self.report()
        self.assertIn('paint_command_order', self.codes(report))
        self.assertNotIn('clip_stack_after', self.codes(report))
        self.assertNotIn('clip_pop_identity', self.codes(report))

    def test_paint_clip_order_and_stack_are_actual_not_invented(self):
        target = op(self.core)
        target['paint_commands'][1]['clip_stack_after'] = []
        target['paint_commands'][-1]['node'] = 'primary_anchor_static'
        report = self.report()
        self.assertIn('clip_stack_after', self.codes(report))
        self.assertIn('clip_pop_identity', self.codes(report))
        self.assertIn('paint_command_order', self.codes(report))

    def test_selects_final_frame_and_keeps_exact_operation_count(self):
        events = self.rust['variants'][0]['events']
        start = next(i for i, r in enumerate(events) if r['operation'] == 'wide-parent' and r['event']['type'] == 'frame_start')
        end = next(i for i, r in enumerate(events) if r['operation'] == 'wide-parent' and r['event']['type'] == 'operation_end')
        intermediate = copy.deepcopy(events[start:end])
        for row in intermediate:
            if row['event'].get('type') in ('prepaint', 'paint', 'hitbox'):
                row['event']['bounds'][0] += 100
        for row in events[start:]:
            row['frame'] += 1
        events[start:start] = intermediate
        for i, row in enumerate(events):
            row['sequence'] = i
        report = self.report()
        self.assertTrue(report['strict_match'], report['failures'][:4])
        audit = compare.Audit()
        normalized = compare.normalize_rust(self.rust, self.fixture, audit)
        self.assertEqual(normalized[0]['operations'][0]['frames_in_operation'], 2)

    def test_bad_final_frame_does_not_fall_back_to_previous_frame(self):
        for row in self.rust['variants'][0]['events']:
            if row['operation'] == 'fractional200-parent' and row['event']['type'] == 'prepaint' and row['event']['node'] == 'primary':
                row['event']['bounds'][0] += 1
        report = self.report()
        self.assertFalse(report['strict_match'])
        self.assertIn('rust_paint_bounds', self.codes(report))
        self.assertIn('edge_residual', self.codes(report))

    def test_bad_fixture_cannot_redefine_epsilon_or_corpus(self):
        fixture = copy.deepcopy(self.fixture)
        fixture['steps'].pop()
        report = compare.compare(self.rust, self.core, fixture)
        self.assertIn('canonical_fixture', self.codes(report))
        self.assertEqual(report['counts']['core_settled_operations'], 28)
        self.assertEqual(report['absolute_epsilon'], 1 / 1024)

    def test_json_duplicate_nonfinite_and_bool_guards(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'bad.json'
            for text in ['{"a":1,"a":2}', '{"x":NaN}', '{"x":Infinity}']:
                path.write_text(text)
                with self.assertRaises(ValueError):
                    compare.load(path)
        self.assertFalse(compare.same({'a': [False]}, {'a': [0]}))
        self.assertFalse(compare.rectangle([0, 0, True, 2]))
        self.assertFalse(compare.rectangle([0, 0, float('inf'), 2]))
        self.assertTrue(compare.same([1, 2.0], [1.0, 2]))

    def test_invalid_bounds_and_missing_outputs_fail_closed(self):
        for value in [None, [0, 1], [0, 0, -1, 1], [0, 0, float('nan'), 1]]:
            candidate = copy.deepcopy(self.core)
            op(candidate)['bounds']['primary'] = value
            report = compare.compare(self.rust, candidate, self.fixture)
            self.assertFalse(report['strict_match'])
            self.assertIn('finite_bounds', self.codes(report))
        report = compare.compare({}, {}, self.fixture)
        self.assertFalse(report['strict_match'])
        self.assertIn('corpus_count', self.codes(report))


class MutationWitnessTests(unittest.TestCase):
    def setUp(self):
        self.rust, self.core, self.fixture = synthetic_pair()
        self.executed = dict(build_returncode=0, execution_returncode=0)

    def test_owner_origin_requires_predicted_relation_and_new_violation(self):
        # Start with an independently red, unrelated primary input geometry.
        base = copy.deepcopy(self.core)
        op(base)['bounds']['primary'][0] += 1
        repaint(op(base))
        mutant = copy.deepcopy(base)
        target = op(mutant, 'wide-parent')
        owner = target['bounds']['primary']
        target['bounds']['primary_anchor_static'][:2] = [owner[0], owner[1] + owner[3]]
        repaint(target)
        before = compare.compare(self.rust, base, self.fixture)
        after = compare.compare(self.rust, mutant, self.fixture)
        result = compare.evaluate_control('owner-origin', before, after, base, mutant, self.fixture, self.executed)
        self.assertFalse(before['strict_match'])
        self.assertTrue(result['killed'])
        self.assertTrue(result['additional_violations'])
        self.assertFalse(result['execution_authenticated'])

    def test_red_baseline_unchanged_or_unrelated_mutant_never_killed(self):
        base = copy.deepcopy(self.core)
        op(base)['bounds']['primary'][0] += 1
        repaint(op(base))
        report = compare.compare(self.rust, base, self.fixture)
        unchanged = compare.evaluate_control('owner-origin', report, report, base, base, self.fixture, self.executed)
        self.assertFalse(unchanged['killed'])
        mutant = copy.deepcopy(base)
        op(mutant)['bounds']['primary'][0] += 4
        repaint(op(mutant))
        changed = compare.compare(self.rust, mutant, self.fixture)
        result = compare.evaluate_control('owner-origin', report, changed, base, mutant, self.fixture, self.executed)
        self.assertFalse(result['killed'])

    def test_compile_failure_bool_or_missing_execution_never_killed(self):
        mutant = copy.deepcopy(self.core)
        target = op(mutant, 'wide-parent')
        target['bounds']['primary_anchor_static'][:2] = [40, 80]
        repaint(target)
        before, after = compare.compare(self.rust, self.core), compare.compare(self.rust, mutant)
        for execution in [None, {}, dict(build_returncode=1, execution_returncode=0),
                          dict(build_returncode=False, execution_returncode=0)]:
            result = compare.evaluate_control('owner-origin', before, after, self.core, mutant, self.fixture, execution)
            self.assertFalse(result['killed'])
            self.assertFalse(result['compiled_and_executed'])

    def test_semantic_witness_that_improves_baseline_is_not_killed(self):
        mutant = copy.deepcopy(self.core)
        target = op(mutant, 'wide-parent')
        target['bounds']['parent'][:2] = [0, 0]
        repaint(target)
        proof = compare.control_witness('window-mode', self.core, mutant)
        self.assertTrue(proof['witnessed'])
        # Deliberately report an improved preexisting residual at the witness.
        row = dict(variant='example_branch', operation='wide-parent', node='parent', stage='layout_prepaint', edge='left')
        before = dict(strict_match=False, edge_residuals=[dict(**row, core=52, absolute_residual=100)])
        after = dict(strict_match=False, edge_residuals=[dict(**row, core=0, absolute_residual=48)])
        result = compare.evaluate_control('window-mode', before, after, self.core, mutant, execution=self.executed)
        self.assertFalse(result['killed'])

    def test_stale_metrics_source_derived_secondary_witness_and_primary_collision(self):
        scale = 1.25
        primary_base = math.ceil(compare._source_line_height(16, scale) * scale) / scale
        primary_mutant = math.ceil(compare._source_line_height(16, 1) * scale) / scale
        self.assertEqual(primary_base, primary_mutant)
        self.assertEqual(primary_base, 26.4)
        secondary_base = math.ceil(compare._source_line_height(14, scale) * scale) / scale
        secondary_mutant = math.ceil(compare._source_line_height(14, 1) * scale) / scale
        self.assertEqual((secondary_base, secondary_mutant), (22.4, 23.2))
        base, mutant = copy.deepcopy(self.core), copy.deepcopy(self.core)
        op(base, 'fractional125-parent')['bounds']['secondary_text'][3] = secondary_base
        op(mutant, 'fractional125-parent')['bounds']['secondary_text'][3] = secondary_mutant
        result = compare.control_witness('stale-scale-metrics', base, mutant)
        self.assertTrue(result['witnessed'])
        self.assertAlmostEqual(result['witnesses'][0]['predicted_displacement_physical'][0], 1)
        op(mutant, 'fractional125-parent')['bounds']['secondary_text'][3] = secondary_base
        self.assertFalse(compare.control_witness('stale-scale-metrics', base, mutant)['witnessed'])

    def test_no_logical_rounding_independent_prediction(self):
        base, mutant = copy.deepcopy(self.core), copy.deepcopy(self.core)
        b, m = op(base, 'fractional125-parent'), op(mutant, 'fractional125-parent')
        # Crossing the raw right edge applies margin8 once: fitted x127.5.
        # Static x136.9 gives delta-9.4: logical rounding-9 device-snaps-8.8,
        # whereas direct device-snapping of -9.4 gives-9.6.
        origin = 136.9
        b['bounds']['primary_anchor_static'][0] = origin
        m['bounds']['primary_anchor_static'][0] = origin
        b['bounds']['parent'][0] = origin - 8.8
        m['bounds']['parent'][0] = origin - 9.6
        b['bounds']['parent'][1] = m['bounds']['parent'][1] = 70
        result = compare.control_witness('no-logical-rounding', base, mutant)
        self.assertTrue(result['witnessed'], result['candidates'])
        self.assertAlmostEqual(result['witnesses'][0]['predicted_displacement_physical'][0], -1)

    def test_eager_snap_independent_nested_translation_sum(self):
        base, mutant = copy.deepcopy(self.core), copy.deepcopy(self.core)
        b, m = op(base, 'fractional150-nested'), op(mutant, 'fractional150-nested')
        # Both crossed-edge corrections are -9 logical. At1.5 each snaps
        # -8 2/3; sum-first -18 stays-18, while eager snapping yields-17 1/3.
        for candidate in (b, m):
            candidate['bounds']['primary_anchor_static'] = [136.5, 70, 384, 146]
            candidate['bounds']['parent'] = [136.5 - 26/3, 70, 384, 146]
            candidate['bounds']['secondary_anchor_static'] = [74.5, 199, 446, 49]
        b['bounds']['child'] = [74.5 + 26/3 - 18, 199, 446, 49]
        m['bounds']['child'] = [74.5 + 26/3 - 52/3, 199, 446, 49]
        result = compare.control_witness('eager-device-snap', base, mutant)
        self.assertTrue(result['witnessed'], result['candidates'])


class RunnerContractTests(unittest.TestCase):
    def test_report_is_identical_across_python_hash_seeds(self):
        program = """
import json, sys
sys.path.insert(0, sys.argv[1])
import test_measured_anchor_pair as tests
rust, core, fixture = tests.synthetic_pair()
# Deliberately invalid geometry exercises both residual and failure ordering.
core['variants'][0]['operations'][0]['bounds']['primary'][0] += 1
for variant in rust['variants']:
    for row in variant['events']:
        event = row['event']
        if event.get('type') == 'paint' and event.get('node') in ('primary', 'parent'):
            event['bounds'][0] += 1
report = tests.compare.compare(rust, core, fixture, 'synthetic-never-executed')
assert report['strict_match'] is False and report['failures']
print(json.dumps(report, sort_keys=True, separators=(',', ':'), allow_nan=False))
"""
        reports = []
        for seed in ('1', '2', '321'):
            environment = dict(os.environ, PYTHONHASHSEED=seed, PYTHONDONTWRITEBYTECODE='1')
            result = subprocess.run([sys.executable, '-B', '-c', program, str(Path(__file__).parent)],
                                    env=environment, capture_output=True, text=True, timeout=30, check=True)
            reports.append(result.stdout)
        self.assertEqual(reports[0], reports[1])
        self.assertEqual(reports[0], reports[2])

    def test_frozen_spec_and_exact_fourteen_additions(self):
        self.assertEqual(hashlib.sha256((DIRECTORY / 'comparison_spec.json').read_bytes()).hexdigest(), compare.SPEC_SHA256)
        self.assertEqual(run.SPEC_SHA256, compare.SPEC_SHA256)
        self.assertEqual(len(run.ADDITIONS), 14)
        self.assertEqual(len(set(run.ADDITIONS)), 14)
        source = inspect.getsource(run.validate_pair)
        self.assertIn("all(after.get(p)==v for p,v in before.items())", source)
        self.assertIn("set(after)-set(before)==set(ADDITIONS)", source)
        self.assertIn("after[p].startswith('100644 blob ')", source)

    def test_unbound_profile_fails_before_writes_or_tools(self):
        profile = run.load_profile(require_bound=False)
        profile.update(status='draft_unbound', core_commit=None, core_tree=None)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'profile.json'
            path.write_text(json.dumps(profile))
            with self.assertRaisesRegex(ValueError, 'unbound profile'):
                run.load_profile(path)
            self.assertEqual(run.load_profile(path, require_bound=False), profile)
        args = ['run.py', '--core-source', '/unused', '--fixture-source', '/unused',
                '--upstream-source', '/unused', '--output', '/unused']
        with patch.object(sys, 'argv', args), patch.object(run, 'load_profile', side_effect=ValueError('unbound profile')), \
             patch.object(run, 'git') as git, patch.object(run, 'execute') as execute, \
             patch.object(run.shutil, 'which') as which, patch.object(Path, 'mkdir') as mkdir:
            with self.assertRaisesRegex(ValueError, 'unbound profile'):
                run.main()
            git.assert_not_called()
            execute.assert_not_called()
            which.assert_not_called()
            mkdir.assert_not_called()

    def test_s_fixture_and_b_integration_baseline_are_distinct(self):
        profile = run.load_profile(require_bound=False)
        self.assertEqual(profile['fixture_commit'], '4bf568614f9a5707855a441314eec8080adbc8a7')
        self.assertEqual(profile['integration_baseline_commit'], '1afff3fc1540657cd6060c7e7bb29be0030ad66e')
        self.assertNotEqual(profile['fixture_commit'], profile['integration_baseline_commit'])
        for commit in (profile['fixture_commit'], profile['integration_baseline_commit']):
            with self.assertRaisesRegex(ValueError, 'must be distinct'), patch.object(run, 'validate_source') as validate:
                run.validate_pair(ROOT, ROOT, profile, commit, 'f' * 40)
            validate.assert_not_called()

    def test_no_historical_env_override_and_three_adapters_bound(self):
        compile_source = inspect.getsource(run.compile_candidate)
        verify_source = inspect.getsource(evidence.verify_candidate)
        for source in (compile_source, verify_source):
            self.assertIn("('main.mbt','noop_metrics.mbt','moon.pkg')", source)
            for forbidden in ('GPUI_BASELINE_COMMIT', 'GPUI_BASELINE_TREE', 'GPUI_LINE_HEIGHT', 'GPUI_OBSERVED_BOUNDS'):
                self.assertNotIn(forbidden, source)
        self.assertIn("candidate['inputs']==expected", verify_source)
        self.assertIn("actual==set(expected)|{'moon.mod'}", verify_source)
        self.assertIn("NODE_OPTIONS", compile_source)
        self.assertIn("NODE_PATH", compile_source)

    def test_mutation_markers_exactly_one_and_fail_on_duplicate(self):
        candidate = Path('/workspace/shared/padded-anchor-core-source-20261018/candidate/element/anchored.mbt')
        for name, mutation in controls.MUTATIONS.items():
            path = ROOT / 'adapters/measured_anchor_moonbit/main.mbt' if mutation['path'].startswith('probe/') else candidate
            if path.is_file():
                with self.subTest(control=name):
                    self.assertEqual(path.read_text().count(mutation['before']), 1)
            with tempfile.TemporaryDirectory() as temp:
                stage = Path(temp)
                file = stage / mutation['path']
                file.parent.mkdir(parents=True)
                file.write_text('// synthetic single mutation-site control\n' + mutation['before'])
                changed = controls.apply_mutation(stage, name)
                self.assertEqual(changed['name'], name)
                self.assertIn(mutation['after'], file.read_text())
                file.write_text(mutation['before'] * 2)
                with self.assertRaisesRegex(ValueError, 'one reviewed production mutation site'):
                    controls.apply_mutation(stage, name)

    def test_actual_rust_trace_selector_if_retained_is_read_only(self):
        raw = Path('/tmp/padded-text-anchor-actual-review-20261018/bundle/padded-text-anchor-evidence/raw.stdout')
        if not raw.is_file():
            self.skipTest('retained earlier Rust trace is unavailable; synthetic tests remain sufficient')
        audit = compare.Audit()
        normalized = compare.normalize_rust(compare.load(raw), compare.canonical_fixture(), audit)
        self.assertEqual(audit.failures, [])
        self.assertEqual(sum(len(v['operations']) for v in normalized), 28)
        self.assertEqual(sum(len(o['attachments']) for v in normalized for o in v['operations']), 42)
        self.assertEqual(sum(len(o['hitboxes']) for v in normalized for o in v['operations']), 84)


if __name__ == '__main__':
    unittest.main()
