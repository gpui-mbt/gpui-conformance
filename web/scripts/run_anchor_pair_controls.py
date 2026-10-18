#!/usr/bin/env python3
"""Compile, execute, retain and independently reject real source faults in CI.

Synthetic PNG/report corruption controls are separate and do not satisfy this job.
A build/startup/provenance failure is a failed control, never a successful rejection.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def run(core: Path, upstream: Path, rust: Path, out: Path, ordinary_evidence: Path) -> dict:
    if out.exists():
        raise ValueError('Control output exists; select a fresh directory')
    if shutil.disk_usage(out.parent if out.parent.exists() else ROOT).free < 1024**3:
        raise ValueError('At least 1 GiB free space is required')
    out.mkdir(parents=True)
    report = {'status': 'failed', 'kind': 'actual_compiled_browser_faults', 'controls': []}
    # Never build or count a control against an absent/failed ordinary pair.
    # The verifier reopens all original ordinary bytes again for each control,
    # so a forged success summary or direct verifier CLI cannot bypass the gate.
    try:
        ordinary = json.loads((ordinary_evidence / 'anchor-pair-verification.json').read_text())
        if ordinary.get('status') != 'bounded_color_component_pair_verified' or 'expected_control' not in ordinary or ordinary['expected_control'] is not None:
            raise ValueError('Successful non-control ordinary pair baseline is required')
        command = ['node', 'web/tests/verify-anchor-pair.mjs', str(ordinary_evidence), str(rust), str(core)]
        with (out / 'ordinary-baseline-reverification.log').open('x') as output:
            result = subprocess.run(command, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT)
        if result.returncode:
            raise ValueError('Ordinary pair did not pass independent current-source/original-byte reverification')
        report['ordinary_evidence'] = str(ordinary_evidence)
    except (ValueError, OSError) as error:
        report['status'] = 'skipped_unqualified_ordinary_pair'
        report['failure'] = str(error)
        (out / 'controls-result.json').write_text(json.dumps(report, indent=2) + '\n')
        return report
    profile = json.loads((ROOT / 'web/pairs/anchor.json').read_text())
    for name in profile['executed_controls']:
        site, evidence = out / (name + '-site'), out / (name + '-evidence')
        evidence.mkdir()
        record = {'name': name, 'status': 'failed', 'commands': []}
        report['controls'].append(record)
        commands = [
            [sys.executable, 'web/scripts/build_anchor_pair.py', '--gpui-source', str(core),
             '--upstream-source', str(upstream), '--out', str(site), '--control', name],
            ['node', 'web/tests/anchor-pair-browser.mjs', str(site), str(rust)],
            ['node', 'web/tests/verify-anchor-pair.mjs', str(evidence), str(rust), str(core), name, str(ordinary_evidence)],
        ]
        for index, command in enumerate(commands):
            env = {**os.environ, 'BROWSER_EVIDENCE': str(evidence)}
            log = evidence / f'command-{index + 1}.log'
            with log.open('x') as output:
                result = subprocess.run(command, cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT)
            record['commands'].append({'command': command, 'returncode': result.returncode, 'log': str(log)})
            if result.returncode:
                record['failure'] = f'Command {index + 1} failed; this is not an accepted fault rejection'
                break
        else:
            verified = json.loads((evidence / 'anchor-pair-verification.json').read_text())
            if verified.get('status') != 'executed_fault_rejected' or verified.get('expected_control') != name:
                record['failure'] = 'Independent original-byte verification did not reject the named executed fault'
            else:
                record['status'] = 'executed_fault_rejected'
                record['verification'] = str(evidence / 'anchor-pair-verification.json')
        # Always continue to the other independent fault; retain every failure.
        (out / 'controls-progress.json').write_text(json.dumps(report, indent=2) + '\n')
    if all(item['status'] == 'executed_fault_rejected' for item in report['controls']):
        report['status'] = 'all_executed_faults_rejected'
    (out / 'controls-result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ['gpui-source', 'upstream-source', 'rust-evidence', 'out', 'ordinary-evidence']:
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    try:
        report = run(args.gpui_source.resolve(), args.upstream_source.resolve(),
                     args.rust_evidence.resolve(), args.out.resolve(), args.ordinary_evidence.resolve())
        if report['status'] != 'all_executed_faults_rejected':
            parser.exit(1, 'Executed controls failed; retained original logs/results explain why\n')
    except (ValueError, OSError) as error:
        parser.exit(1, f'Executed controls failed: {error}\n')
