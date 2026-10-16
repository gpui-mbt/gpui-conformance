#!/usr/bin/env python3
"""Corrupt COPIES of observed candidate bytes. These are not engine mutants."""
import argparse
import copy
import json
from pathlib import Path
from compare import ROOT, baseline, compare_observations, require


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    evidence, out = args.evidence.resolve(), args.output.resolve()
    require(out.is_relative_to(ROOT / '_build'), 'output must be under _build')
    out.mkdir(parents=True, exist_ok=False)
    candidate = json.loads((evidence / 'candidate-raw.json').read_text())
    rust = json.loads((evidence / 'rust-baseline/raw.json').read_text())
    scenarios = json.loads((evidence / 'scenarios.json').read_text())
    compare_observations(rust, candidate, scenarios)
    def all_events(raw): return [e for c in raw['cases'] for e in c['events']]
    def set_event(raw, event_type, key, value, **filters):
        event = next(e['event'] for e in all_events(raw) if e['operation'] != 'initial'
                     and e['event']['type'] == event_type and all(e['event'].get(k) == v for k, v in filters.items()))
        event[key] = value
    def remove_callback(raw):
        for case in raw['cases']:
            for i, e in enumerate(case['events']):
                if e['event']['type'] == 'click':
                    case['events'].pop(i)
                    for sequence, entry in enumerate(case['events']): entry['sequence'] = sequence
                    return
    def remove_complete_candidate_frame(raw):
        events = raw['cases'][-1]['events']
        operation = events[-1]['operation']
        start = next(i for i, e in enumerate(events) if e['operation'] == operation and e['event']['type'] == 'frame_start')
        stop = next(i for i in range(start, len(events)) if events[i]['event']['type'] == 'frame_end')
        del events[start:stop + 1]
        events[-1]['frame'] -= 1
        for sequence, entry in enumerate(events): entry['sequence'] = sequence
    controls = [
        ('missing-complete-candidate-frame', remove_complete_candidate_frame),
        ('factory-range', lambda r: set_event(r, 'factory', 'range', [1, 2])),
        ('stable-row-id', lambda r: set_event(r, 'constructed', 'row_id', '9999')),
        ('measured-row-geometry', lambda r: set_event(r, 'node', 'bounds', [40, 50, 220, 27], id='1000')),
        ('prototype-live-binding', lambda r: set_event(r, 'node', 'factory_call', 1, id='1000')),
        ('scene-mask', lambda r: set_event(r, 'scene', 'bounds', [0, 0, 420, 420], id='2', kind='clip_push')),
        ('missing-callback', remove_callback),
        ('platform-scale-overclaim', lambda r: r.update(platform_scale_claim=True)),
        ('wrong-original-input', lambda r: set_event(r, 'operation_start', 'input', {'id': 'configure-dpr-one', 'action': 'set_scale_factor', 'scale_factor': 2})),
        ('wrong-applied-input', lambda r: set_event(r, 'operation_start', 'applied_input', {'id': 'configure-dpr-one', 'action': 'set_scale_factor', 'scale_factor': 2})),
        ('unknown-event', lambda r: set_event(r, 'factory', 'type', 'trusted-pass-flag')),
    ]
    results = []
    for name, mutate in controls:
        raw = copy.deepcopy(candidate)
        mutate(raw)
        path = out / (name + '.json')
        path.write_text(json.dumps(raw, separators=(',', ':')) + '\n')
        try:
            compare_observations(rust, raw, scenarios)
            result = {'control': name, 'rejected': False}
        except (ValueError, TypeError, KeyError, IndexError) as error:
            result = {'control': name, 'rejected': True, 'reason': str(error)}
        result['corrupted_raw_sha256'] = baseline.digest(path)
        results.append(result)
    report = {'kind': 'comparator-corruption-controls-only-not-engine-mutants',
              'baseline_manifest_sha256': baseline.digest(evidence / 'manifest.json'),
              'unchanged_rust_raw_sha256': baseline.digest(evidence / 'rust-baseline/raw.json'),
              'unchanged_candidate_raw_sha256': baseline.digest(evidence / 'candidate-raw.json'), 'controls': results}
    (out / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    require(all(r['rejected'] for r in results), 'surviving comparator corruption')
    print(json.dumps({'controls': len(results), 'all_rejected': True, 'kind': report['kind']}))

if __name__ == '__main__': main()
