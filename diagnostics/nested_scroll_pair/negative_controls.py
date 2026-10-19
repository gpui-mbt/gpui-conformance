#!/usr/bin/env python3
"""Rebuild intentionally broken adapters from a completed actual runtime pair."""
import argparse
from collections import Counter
import os
from pathlib import Path
import json
import shutil

import run as pair


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    baseline, output = args.baseline.resolve(), args.output.resolve()
    manifest = pair.load(baseline / 'manifest.json')
    pair.require(manifest['status'] in ('pass', 'mismatch'), 'completed baseline required')
    for path, digest in manifest['source_files']['moon'].items():
        pair.require(pair.digest(baseline / 'moon-source' / path) == digest, 'baseline source drift')
    for path in ('scenarios.json', 'rust.stdout', 'moon.stdout'):
        pair.require(pair.digest(baseline / path) == manifest['files'][path], 'baseline observation drift')
    fixture = pair.load(baseline / 'scenarios.json')
    rust = pair.load(baseline / 'rust.stdout')
    pair.compare(rust, pair.load(baseline / 'moon.stdout'), fixture)
    pair.require(not output.exists(), 'fresh control output required')
    output.mkdir(parents=True)
    env = os.environ.copy()
    env['SCROLL_SCENARIOS'] = json.dumps(fixture)
    summaries = []
    for name in ('no-wheel', 'no-scale'):
        out = output / name
        out.mkdir()
        source = out / 'source'
        shutil.copytree(baseline / 'moon-source', source,
                        ignore=shutil.ignore_patterns('_build', '.moon-lock'))
        path = source / 'probe/main.mbt'
        original = path.read_text()
        if name == 'no-wheel':
            changed = original.replace('-number(wheel[2])', '0.0').replace('-number(wheel[3])', '0.0')
        else:
            changed = original.replace('  scale : Double,', '  _scale : Double,').replace(
                '.request_layout_with_device_scale(\n    @primitives.Size::new(240, 180).unwrap(),\n    scale,\n  )',
                '.request_layout(@primitives.Size::new(240, 180).unwrap())')
        pair.require(changed != original, 'control mutation missing')
        path.write_text(changed)
        record = {'control': name, 'source_files': pair.inventory(source), 'runs': {}}
        for stage, command in (
            ('build', ['moon', 'build', '--target', 'js', '--deny-warn', 'probe']),
            ('moon', ['node', str(source / '_build/js/debug/build/probe/probe.js')]),
        ):
            record['runs'][stage] = pair.execute(command, source, env, out, stage)
            pair.require(record['runs'][stage]['returncode'] == 0, stage + ' failed: ' + str(out))
        report = pair.compare(rust, pair.load(out / 'moon.stdout'), fixture)
        fields = Counter(difference['field'] for difference in report['differences'])
        pair.require(fields['bounds'] > 0 and fields['targets'] > 0, 'insensitive geometry/hit control')
        pair.require(fields['offsets'] > 0 if name == 'no-wheel' else fields['offsets'] == 0,
                     'unexpected offset control result')
        record.update(differences=len(report['differences']), fields=dict(fields))
        pair.save(out / 'comparison.json', report)
        record['files'] = {p.name: pair.digest(p) for p in out.iterdir() if p.is_file()}
        pair.save(out / 'manifest.json', record)
        summaries.append({'control': name, 'differences': record['differences'], 'fields': dict(fields)})
    pair.save(output / 'summary.json', summaries)
    print(json.dumps(summaries))


if __name__ == '__main__':
    main()
