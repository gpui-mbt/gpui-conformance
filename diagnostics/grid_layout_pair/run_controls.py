#!/usr/bin/env python3
"""Mutate retained JSON evidence only; never report these as engine mutation kills."""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
from compare import ROOT, TOLERANCE, baseline, compare_observations, require, require_semantic_match


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = args.evidence.resolve()
    rust = json.loads((source / 'rust-baseline/raw.json').read_text())
    candidate = json.loads((source / 'candidate-raw.json').read_text())
    corpus = json.loads((source / 'scenarios.json').read_text())
    witnesses = json.loads((source / 'rust-baseline/retained/diagnostics/grid_layout/witnesses.json').read_text())
    require_semantic_match(compare_observations(rust, candidate, corpus, witnesses))
    out = args.output.resolve()
    require(out.is_relative_to(ROOT / '_build'), 'output must be a new ignored _build directory')
    out.mkdir(parents=True, exist_ok=False)
    results = []
    def first(raw, kind):
        return next(e['event'] for case in raw['cases'] for e in case['events'] if e['event']['type'] == kind)
    mutations = [('eager-callback-count', lambda r: first(r, 'request_end').update(callback_count=1)),
        ('wrong-callback-size', lambda r: first(r, 'callback').update(size=[640, 640])),
        ('wrong-node-lineage', lambda r: first(r, 'node').update(parent='grid')),
        ('outside-numeric-domain', lambda r: first(r, 'node').update(bounds=[0, 0, 1025, 640])),
        ('wrong-scene-bounds', lambda r: first(r, 'scene').update(bounds=[1, 2, 3, 4])),
        ('just-beyond-numeric-tolerance', lambda r: first(r, 'scene').update(bounds=[*first(r, 'scene')['bounds'][:2], first(r, 'scene')['bounds'][2] + TOLERANCE + .000001, first(r, 'scene')['bounds'][3]])),
        ('wrong-input-route', lambda r: first(r, 'route').update(capture=[])),
        ('unsupported-case-hidden', lambda r: r['cases'].pop(2)),
        ('wrong-bootstrap-scale', lambda r: first(r, 'frame_start').update(scale_factor=1))]
    for name, change in mutations:
        altered = copy.deepcopy(candidate)
        change(altered)
        record = {'name': name, 'evidence_kind': 'synthetic-retained-json-corruption', 'executed_engine_mutant': False}
        try:
            comparison = compare_observations(rust, altered, corpus, witnesses)
            record['rejected'] = not comparison['passed']
            record['mismatches'] = comparison['mismatches']
        except (ValueError, KeyError, TypeError, IndexError) as error:
            record.update(rejected=True, error=str(error))
        (out / (name + '.json')).write_text(json.dumps(altered, indent=2) + '\n')
        results.append(record)
    (out / 'results.json').write_text(json.dumps({'evidence_kind': 'synthetic-retained-json-corruption',
        'source_manifest_sha256': baseline.digest(source / 'manifest.json'), 'controls': results}, indent=2) + '\n')
    require(all(item['rejected'] for item in results), 'checker corruption survived')
    print(json.dumps({'checker_controls_rejected': len(results), 'engine_mutation_claim': False}))


if __name__ == '__main__': main()
