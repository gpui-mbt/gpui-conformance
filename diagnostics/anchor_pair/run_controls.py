#!/usr/bin/env python3
"""Synthetic raw-JSON corruptions only; never executed engine mutation kills."""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
from compare import load_json, ROOT, TOLERANCE, baseline, compare_observations, require, require_semantic_match


def first(raw, kind, predicate=lambda event: True):
    return next(entry['event'] for case in raw['cases'] for entry in case['events']
                if entry['event']['type'] == kind and predicate(entry['event']))


def corruptions():
    return [
        ('wrong-bootstrap-scale', lambda r: first(r, 'frame_start').update(scale_factor=1)),
        ('wrong-node-lineage', lambda r: first(r, 'node').update(parent='parent')),
        ('outside-numeric-domain', lambda r: first(r, 'node').update(bounds=[4097, 0, 1, 1])),
        ('wrong-scene-bounds', lambda r: first(r, 'scene', lambda e: e['kind'] == 'quad').update(bounds=[1, 2, 3, 4])),
        ('just-beyond-numeric-allowance', lambda r: first(r, 'node').update(bounds=[TOLERANCE + .000001, 0, 640, 480])),
        ('wrong-input-route', lambda r: first(r, 'route').update(capture=[])),
        ('missing-dispatch-callback', lambda r: first(r, 'route').update(callback_bubble=[])),
        ('focused-lineage-loss', lambda r: first(r, 'route').update(focused_capture=[])),
        ('background-popup-interactive', lambda r: first(r, 'node', lambda e: e['node'] == 'popup').update(pointer_events=True)),
        ('case-coverage-loss', lambda r: r['cases'].pop()),
        ('unbalanced-clip', lambda r: first(r, 'scene', lambda e: e['kind'] == 'clip_pop').update(node='button')),
        ('wrong-viewport-clip', lambda r: first(r, 'scene', lambda e: e['kind'] == 'clip_push').update(bounds=[0, 0, 639, 480])),
        ('missing-attachment-clip', lambda r: first(r, 'scene', lambda e: e['kind'] == 'clip_push' and e['node'].startswith('anchor_')).update(kind='quad')),
        ('outside-viewport-hit', lambda r: first(r, 'viewport_hit').update(target='popup')),
    ]


def run_controls(rust, candidate, corpus):
    require_semantic_match(compare_observations(rust, candidate, corpus))
    controls = []
    for name, change in corruptions():
        altered = copy.deepcopy(candidate)
        change(altered)
        record = {'name': name, 'evidence_kind': 'synthetic-retained-json-corruption', 'executed_engine_mutant': False}
        try:
            comparison = compare_observations(rust, altered, corpus)
            record.update(rejected=not comparison['passed'], mismatches=comparison['mismatches'])
        except (ValueError, KeyError, TypeError, IndexError) as error:
            record.update(rejected=True, error=str(error))
        controls.append((record, altered))
    return controls


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source, out = args.evidence.resolve(), args.output.resolve()
    controls = run_controls(load_json((source / 'rust-baseline/raw.json').read_text()),
                            load_json((source / 'candidate-raw.json').read_text()),
                            load_json((source / 'scenarios.json').read_text()))
    require(out.is_relative_to(ROOT / '_build'), 'output must be a new ignored _build directory')
    out.mkdir(parents=True, exist_ok=False)
    for record, altered in controls:
        (out / (record['name'] + '.json')).write_text(json.dumps(altered, indent=2) + '\n')
    results = [record for record, _ in controls]
    (out / 'results.json').write_text(json.dumps({'evidence_kind': 'synthetic-retained-json-corruption',
        'source_manifest_sha256': baseline.digest(source / 'manifest.json'), 'controls': results}, indent=2) + '\n')
    require(all(item['rejected'] for item in results), 'synthetic checker corruption survived')
    print(json.dumps({'checker_controls_rejected': len(results), 'engine_mutation_claim': False}))


if __name__ == '__main__': main()
