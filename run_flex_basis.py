#!/usr/bin/env python3
"""Process-backed full root/child bounds differential and exact physical viewport checks.

Observed GPUI TestWindow bounds are headless test-platform evidence, not desktop
or renderer parity. MoonBit viewport checks do not normalize any layout bounds.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
from datetime import datetime, timezone

from run_flex_justify import numeric, require, sha
ROOT = Path(__file__).resolve().parent


def source_identity(path):
    """Record actual source bytes, not HEAD tree identity for a dirty worktree."""
    path = path.resolve()
    def git(*args):
        return subprocess.check_output(['git', '-C', str(path), *args])
    names = sorted(set(git('ls-files', '-z', '--cached', '--others', '--exclude-standard').decode().split('\0')) - {''})
    files = {name: sha(path/name) for name in names if (path/name).is_file()}
    missing = [name for name in names if not (path/name).is_file()]
    require(not missing, 'Missing/nonregular source files: '+repr(missing))
    digest = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return {'path': str(path), 'revision': git('rev-parse', 'HEAD').decode().strip(),
            'tree': git('rev-parse', 'HEAD^{tree}').decode().strip(),
            'dirty': bool(git('status', '--porcelain', '--untracked-files=all').strip()),
            'source_sha256': digest, 'files': files}


def validate_pins(sources):
    pins = json.loads((ROOT/'flex_basis_pins.json').read_text())
    require(pins['schema_version'] == 1, 'Unknown flex basis pin schema')
    for key in ('revision', 'tree'):
        require(sources['upstream'][key] == pins['upstream'][key], 'upstream '+key+' differs from pin')
    for key in ('revision', 'tree'):
        require(sources['moonbit'][key] == pins['moonbit'][key], 'moonbit '+key+' differs from pin')
    require(not sources['upstream']['dirty'], 'Upstream source must be clean')


def validate(corpus):
    require(type(corpus) is dict and corpus.get('schema_version') == 1)
    require(type(corpus.get('cases')) is list and corpus['cases'])
    ids = set()
    for c in corpus['cases']:
        require(type(c) is dict and type(c.get('id')) is str and c['id'] and c['id'] not in ids)
        ids.add(c['id'])
        require(c.get('kind') == 'layout' and c.get('layer') == 'headless-layout')
        require(c.get('direction') in ('row', 'column', 'row_reverse', 'column_reverse'))
        require(all(numeric(c.get(k)) and c[k] <= 4096 for k in ('width', 'height')))
        require(type(c.get('device_scale_factor')) in (int, float) and c['device_scale_factor'] in (1, 1.5, 2))
        require(c.get('layout_observation', 'bounds') == 'bounds')
        children = c.get('children')
        require(type(children) is list and len(children) <= 3)
        require(all(type(child) is list and len(child) == 2 and all(numeric(v, nullable=True) for v in child) for child in children))
        require(c.get('align') in ('start', 'center', 'end', 'stretch'))
        require(c.get('justify') in ('start', 'center', 'end', 'space-between', 'space-around', 'space-evenly', 'flex_start', 'flex_end'))
        require(c.get('wrap', 'nowrap') in ('nowrap', 'wrap', 'wrap_reverse'))
        require(c.get('align_content', 'stretch') in ('start', 'center', 'end', 'stretch', 'space-between', 'space-around', 'space-evenly'))
        require(numeric(c.get('gap')))
        for k in ('gap_x', 'gap_y'):
            require(k not in c or numeric(c[k]))
        for k in ('padding', 'border'):
            require(type(c.get(k)) is list and len(c[k]) == 4 and all(numeric(v) for v in c[k]))
        require(type(c.get('align_self')) is list and len(c['align_self']) == len(children))
        require(all(v in ('auto','start','center','end','stretch','flex_start','flex_end') for v in c['align_self']))
        for k in ('grow', 'shrink', 'min_main', 'max_main', 'min_cross', 'max_cross'):
            if k in c:
                require(type(c[k]) is list and len(c[k]) == len(children))
                require(all(numeric(v, nullable=k.startswith('max')) for v in c[k]))
        for axis in ('main','cross'):
            for minimum, maximum in zip(c.get('min_'+axis,[0]*len(children)),c.get('max_'+axis,[None]*len(children))):
                require(maximum is None or minimum <= maximum)
        require(type(c.get('flex_basis')) is list and len(c['flex_basis']) == len(children))
        require(all(numeric(v, nullable=True) for v in c['flex_basis']))
        require(type(c.get('expected_capability_mismatch')) is bool)


def rectangle(value):
    require(type(value) is list and len(value) == 4, 'Invalid rectangle')
    require(all(type(v) in (int,float) and math.isfinite(v) for v in value), 'Invalid coordinate')
    require(value[2] >= 0 and value[3] >= 0, 'Negative size')


def compare(corpus, rust, moon, fixed_root=False):
    validate(corpus)
    require(rust.get('implementation') == 'upstream' and moon.get('implementation') == 'moonbit')
    require(len(rust['cases']) == len(moon['cases']) == len(corpus['cases']))
    rows=[]
    for c,a,b in zip(corpus['cases'],rust['cases'],moon['cases']):
        require(c['id'] == a['id'] == b['id'])
        require(a['status'] == b['status'] == 'observed' and a['layer'] == b['layer'] == 'headless-layout')
        ao,bo=a['observation'],b['observation']
        require(set(ao) == {'bounds','test_window_viewport','device_scale_factor'})
        require(set(bo) == {'bounds','physical_viewport','snapshot_viewport','device_scale_factor'})
        require(type(ao['bounds']) is list and type(bo['bounds']) is list)
        require(len(ao['bounds']) == len(bo['bounds']) == len(c['children'])+1)
        differences=[]
        for i,(ar,br) in enumerate(zip(ao['bounds'],bo['bounds'])):
            rectangle(ar);rectangle(br)
            for j,(x,y) in enumerate(zip(ar,br)):
                if abs(x-y)>1e-5: differences.append({'path':f'bounds[{i}][{j}]','upstream':x,'moonbit':y})
        expected=[0,0,c['width'],c['height']]
        for key in ('test_window_viewport',):
            rectangle(ao[key])
            require(all(abs(x-y)<=1e-5 for x,y in zip(ao[key],expected)), 'GPUI test window viewport changed')
        for key in ('physical_viewport','snapshot_viewport'):
            rectangle(bo[key])
            if not fixed_root:
                require(bo[key] == expected, 'MoonBit exact '+key+' differs from supplied physical viewport')
        for o in (ao,bo):
            require(type(o['device_scale_factor']) in (int,float) and o['device_scale_factor']==c['device_scale_factor'], 'Observed scale mismatch')
        rows.append({'id':c['id'],'status':'mismatch' if differences else 'pass','differences':differences,
                     'upstream_bounds':ao['bounds'],'moonbit_bounds':bo['bounds'],
                     'gpui_test_window_viewport':ao['test_window_viewport'],
                     'moonbit_physical_viewport':bo['physical_viewport'],'moonbit_snapshot_viewport':bo['snapshot_viewport']})
    return {'summary':{'total':len(rows),'pass':sum(r['status']=='pass' for r in rows),'mismatch':sum(r['status']=='mismatch' for r in rows)},'cases':rows}


def validate_build(build,sources,executables):
    validate_pins(sources);validate_pins(build['sources'])
    require(build['pins_sha256']==sha(ROOT/'flex_basis_pins.json'), 'Changed flex-basis pins')
    for name in ('upstream','moonbit','suite'):
        # A subsequent suite commit may name the exact same recorded source bytes.
        # Keep original build revision/dirty provenance; never relabel it as rebuilt.
        keys = ('source_sha256','files') if name == 'suite' else ('revision','tree','source_sha256','files')
        for key in keys:
            require(build['sources'][name][key]==sources[name][key], 'Build/source '+name+' '+key+' mismatch')
    require(type(build.get('disable_flex_basis')) is bool, 'Missing control classification')
    mutation=build.get('mutation')
    if build['disable_flex_basis']:
        require(type(mutation) is dict and mutation.get('kind')=='production-points-resolve-as-auto', 'Missing production mutation')
        require(mutation.get('file')=='layout/layout.mbt', 'Unexpected mutation target')
        require(mutation.get('original_sha256')==sources['moonbit']['files']['layout/layout.mbt'], 'Mutation original source mismatch')
        require(mutation.get('mutated_sha256')!=mutation.get('original_sha256'), 'Mutation did not change production source')
    else:
        require(mutation is None, 'Positive build cannot contain a mutation')
    require(len({sha(p) for p in executables.values()})==len(executables), 'Distinct executable bytes required')
    for name,path in executables.items():
        require(build['executables'][name]['sha256']==sha(path), 'Executable hash mismatch')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('rust-exe','moon-exe','upstream-source','moonbit-source','build-manifest','output'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--scenarios',type=Path,default=ROOT/'flex_basis_scenarios.json')
    p.add_argument('--negative-control',action='store_true',help='Corrupt every observed MoonBit root width by one logical pixel')
    p.add_argument('--capability-control',action='store_true',help='Require separately compiled production-basis-disabled mutant')
    a=p.parse_args()
    corpus=json.loads(a.scenarios.read_text());validate(corpus)
    sources={name:source_identity(path) for name,path in [('upstream',a.upstream_source),('moonbit',a.moonbit_source),('suite',ROOT)]}
    build=json.loads(a.build_manifest.read_text())
    executables={'upstream':a.rust_exe,'moonbit':a.moon_exe}
    validate_build(build,sources,executables)
    require(bool(build.get('disable_flex_basis')) == a.capability_control, 'Capability control/build mismatch')
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    (out/'scenarios.json').write_bytes(a.scenarios.read_bytes())
    manifest={'started_at':datetime.now(timezone.utc).isoformat(),'build_manifest':build,'build_manifest_sha256':sha(a.build_manifest),'sources':sources,
              'scenarios_sha256':sha(a.scenarios),'negative_control':a.negative_control,'capability_control':a.capability_control,'runs':{},
              'projection':'complete root and source-order child bounds, separately observed headless TestWindow and exact MoonBit snapshot viewport',
              'limitation':'No native desktop, renderer, clipping or pixel parity claim.'}
    env=os.environ.copy();env.update(GPUI_SCENARIOS=json.dumps(corpus),GPUI_NEGATIVE_CONTROL=str(int(a.negative_control)),GPUI_FIXED_ROOT_CONTROL='0')
    observed={}
    for name,path in executables.items():
        proc=subprocess.run([str(path.resolve())],env=env,capture_output=True,timeout=90)
        (out/(name+'.stdout')).write_bytes(proc.stdout);(out/(name+'.stderr')).write_bytes(proc.stderr)
        manifest['runs'][name]={'returncode':proc.returncode,'executable':str(path.resolve()),'sha256':sha(path),
                               'stdout_sha256':sha(out/(name+'.stdout')),'stderr_sha256':sha(out/(name+'.stderr'))}
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        require(proc.returncode==0, name+' failed: '+proc.stderr.decode(errors='replace')[-2000:])
        lines=[s.removeprefix('GPUI_CONFORMANCE ') for s in proc.stdout.decode().splitlines() if s.startswith('GPUI_CONFORMANCE ')]
        require(len(lines)==1, 'Expected exactly one observation record');observed[name]=json.loads(lines[0])
    require(sources=={name:source_identity(path) for name,path in [('upstream',a.upstream_source),('moonbit',a.moonbit_source),('suite',ROOT)]},'Source changed during run')
    result=compare(corpus,observed['upstream'],observed['moonbit'])
    expected_mismatches={c['id'] for c in corpus['cases'] if c['expected_capability_mismatch']} if a.capability_control else set()
    if a.negative_control: expected_mismatches={c['id'] for c in corpus['cases']}
    actual_mismatches={r['id'] for r in result['cases'] if r['status']=='mismatch'}
    result['control_expectation']={'expected_mismatch_ids':sorted(expected_mismatches),'matches_expected':actual_mismatches==expected_mismatches}
    manifest['finished_at']=datetime.now(timezone.utc).isoformat()
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (out/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result['summary']));return int(actual_mismatches!=expected_mismatches)

if __name__=='__main__': raise SystemExit(main())
