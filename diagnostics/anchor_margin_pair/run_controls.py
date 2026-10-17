#!/usr/bin/env python3
"""Forensic sensitivity on ordinary copies; never executed production kills.

Rehash the outer inventories deliberately. Independent source, plan, binary,
session, and regression checks must still reject. Original evidence is immutable.
"""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
import shutil
from compare import baseline, load_json, require, require_semantic_match
from run import inventory
from verify import verify
from verify_mutants import verify_mutants


def save(path, value): path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('evidence','mutants','suite-source','upstream-source','core-source','output'):
        parser.add_argument('--' + name, type=Path, required=True)
    for name in ('suite-commit','core-commit'): parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    original, mutants = args.evidence.resolve(), args.mutants.resolve()
    def reopen(pair):
        return verify(pair, args.suite_source, args.upstream_source, args.core_source, args.suite_commit, args.core_commit)
    ordinary = reopen(original); require_semantic_match(ordinary)
    verify_mutants(mutants, original, ordinary)
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    estimate = sum(p.stat().st_size for root in (original, mutants) for p in root.rglob('*') if p.is_file())
    require(shutil.disk_usage(out).free >= 1024**3 + estimate, 'Preserve1GiB floor while copying forensic inputs')
    pair, controls = out / 'ordinary-copy', out / 'mutants-copy'
    shutil.copytree(original, pair); shutil.copytree(mutants, controls)
    require(reopen(pair) == ordinary, 'unmodified copied ordinary evidence must pass')
    verify_mutants(controls, pair, ordinary)
    original_manifest = load_json((pair / 'manifest.json').read_text())
    original_summary = load_json((controls / 'results.json').read_text())
    results = []

    def run_case(name, changes, *, target='ordinary', mutate_manifest=None, rehash=True):
        root = pair if target == 'ordinary' else controls
        backups = {}
        changes(root, backups)
        # Changes record exact original bytes; no hardlinks or external evidence writes.
        if target == 'ordinary':
            backups.setdefault('manifest.json', (pair / 'manifest.json').read_bytes())
            manifest = copy.deepcopy(original_manifest)
            if rehash: manifest['files'] = inventory(pair)
            if mutate_manifest: mutate_manifest(manifest)
            save(pair / 'manifest.json', manifest)
        else:
            summary = copy.deepcopy(original_summary)
            mutation = summary['mutations'][0]['mutation']; folder = controls / mutation
            backups.setdefault(mutation + '/manifest.json', (folder / 'manifest.json').read_bytes())
            backups.setdefault('results.json', (controls / 'results.json').read_bytes())
            record = load_json((folder / 'manifest.json').read_text())
            record['files'] = inventory(folder)
            if mutate_manifest: mutate_manifest(record)
            save(folder / 'manifest.json', record); summary['mutations'][0] = record
            save(controls / 'results.json', summary)
        changed = {}
        for relative, before in backups.items():
            path = root / relative
            changed[relative] = {'before_sha256': __import__('hashlib').sha256(before).hexdigest(),
                'after_sha256': baseline.digest(path) if path.is_file() else None}
        rejected, error = False, None
        try:
            if target == 'ordinary': reopen(pair)
            else: verify_mutants(controls, pair, ordinary)
        except (ValueError, KeyError, TypeError, IndexError, OSError, UnicodeError) as failure:
            rejected, error = True, {'type': type(failure).__name__, 'message': str(failure)}
        finally:
            for relative, before in backups.items():
                path = root / relative; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(before)
        result = {'name': name, 'evidence_kind': 'edited-copied-evidence-forensic-checker-control',
            'executed_engine_mutation': False, 'outer_inventory_rehashed': rehash,
            'target': target, 'rejected': rejected, 'error': error, 'changed_files': changed}
        results.append(result); save(out / 'results.json', {'ordinary_source_bound': True,
            'controls': results, 'executed_engine_kills': 0})
        require(rejected, 'forensic checker control survived: ' + name)
        require((pair / 'manifest.json').read_bytes() == (original / 'manifest.json').read_bytes(), 'ordinary copy restoration')

    def write(root, backups, relative, value):
        path = root / relative; backups.setdefault(relative, path.read_bytes())
        if value is None: path.unlink()  # Normal disposable copy only; restored after this control.
        else: path.write_bytes(value)

    def change_json(relative, change):
        def edit(root, backups):
            value = load_json((root / relative).read_text()); change(value)
            write(root, backups, relative, (json.dumps(value, indent=2) + '\n').encode())
        return edit

    run_case('unrehashed-raw', lambda r,b: write(r,b,'candidate-raw.json',(r/'candidate-raw.json').read_bytes()+b' '), rehash=False)
    run_case('rehashed-stale-session', change_json('candidate-raw.json', lambda v: v.update(run_token='stale-session-000000000000')))
    run_case('rehashed-missing-required-checker', lambda r,b: write(r,b,'suite/diagnostics/anchor_margin_pair/compare.py',None))
    def adapter(r,b):
        for relative in ('build-source/probe/main.mbt','suite/adapters/anchor_margin_moonbit/main.mbt'):
            write(r,b,relative,(r/relative).read_bytes()+b'\n// Copied-evidence corruption.\n')
    run_case('rehashed-coherent-observer-source', adapter)
    def core(r,b):
        a,c = 'build-source/element/anchored.mbt','build-source/element/deferred.mbt'
        left,right = (r/a).read_bytes(),(r/c).read_bytes(); write(r,b,a,right);write(r,b,c,left)
    run_case('rehashed-swapped-production-source', core)
    def plan(r,b):
        relative='build-plan.stdout'; value=(r/relative).read_bytes(); require(b'-O0' in value,'native plan control anchor')
        write(r,b,relative,value.replace(b'-O0',b'-O1',1))
    run_case('rehashed-changed-build-plan', plan)
    linked='build-source/_build/native/debug/build/probe/__moonbit_link_core__/probe.o'
    def omit_generated(manifest):
        manifest['generated_build_inputs'].pop('probe/__moonbit_link_core__/probe.o')
        manifest['native_build_plan']['required_generated'].remove('probe/__moonbit_link_core__/probe.o')
    run_case('rehashed-missing-planned-native-object',lambda r,b:write(r,b,linked,None),mutate_manifest=omit_generated)
    run_case('rehashed-swapped-native-object',lambda r,b:write(r,b,linked,(r/'build-source/_build/native/debug/build/runtime-env.o').read_bytes()))
    run_case('rehashed-swapped-executed-elf',lambda r,b:write(r,b,'candidate-probe',(r/'regressions/candidate-probe').read_bytes()))
    def regression_session(r,b):
        change_json('regressions/candidate-raw.json',lambda v:v.update(run_token='wrong-regression-session-0000'))(r,b)
        child_path='regressions/manifest.json'
        child=load_json((r/child_path).read_text())
        child['files']['candidate-raw.json']={'sha256':baseline.digest(r/'regressions/candidate-raw.json'),
            'size':(r/'regressions/candidate-raw.json').stat().st_size}
        write(r,b,child_path,(json.dumps(child,indent=2)+'\n').encode())
    run_case('rehashed-regression-raw-session',regression_session)
    run_case('missing-regression-gate',lambda r,b:None,mutate_manifest=lambda m:m.pop('regressions'))
    first=original_summary['mutations'][0]['mutation']
    run_case('rehashed-mutant-stale-session',change_json(first+'/candidate.stdout',lambda v:v.update(run_token='wrong-control-session-0000')),target='mutants')
    def mutant_source(r,b):
        relative=first+'/mutated-source.mbt';write(r,b,relative,(r/relative).read_bytes()+b'\n// extra copied mutation\n')
    run_case('rehashed-mutant-unapproved-source',mutant_source,target='mutants')
    run_case('rehashed-mutant-swapped-elf',lambda r,b:write(r,b,first+'/candidate-probe',(pair/'candidate-probe').read_bytes()),target='mutants')
    require(reopen(pair) == ordinary, 'restored ordinary copy must still pass')
    verify_mutants(controls,pair,ordinary)
    # Original path inventories/hashes remain intact throughout; copies record
    # their actual historical execution roots, never a relabeled execution.
    require(load_json((original/'manifest.json').read_text()) == original_manifest, 'original manifest changed')
    require(load_json((mutants/'results.json').read_text()) == original_summary, 'original mutant evidence changed')
    print(json.dumps({'forensic_controls_rejected':len(results),'executed_engine_kills':0}))


if __name__ == '__main__': main()
