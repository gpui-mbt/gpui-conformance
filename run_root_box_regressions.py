#!/usr/bin/env python3
"""Preserve original 72/48/68 corpora using the unchanged legacy root request.

The root-box binaries emit additional viewport observations. Original comparators
receive all root/child rectangles unchanged, omitting only these new metadata keys.
Original corpus bytes and unabridged process output remain in the evidence folder.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
from datetime import datetime,timezone
import run_flex_justify
import run_align_self
import run_reverse_flow
from run_root_box import ROOT,require,sha,source_identity,validate_build

CORPORA=[('flex_justify',run_flex_justify),('align_self',run_align_self),('reverse_flow',run_reverse_flow)]

def full_bounds_observation(observed):
    return {'implementation':observed['implementation'],'cases':[
        {**case,'observation':{'bounds':case['observation']['bounds']}} for case in observed['cases']]}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('rust-exe','moon-exe','upstream-source','moonbit-source','build-manifest','output'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    sources={name:source_identity(path) for name,path in [('upstream',a.upstream_source),('moonbit',a.moonbit_source),('suite',ROOT)]}
    exes={'upstream':a.rust_exe,'moonbit':a.moon_exe};build=json.loads(a.build_manifest.read_text())
    validate_build(build,sources,exes)
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    evidence={'started_at':datetime.now(timezone.utc).isoformat(),'sources':sources,'build_manifest':build,'build_manifest_sha256':sha(a.build_manifest),
              'mode':'original legacy request_layout_with_device_scale; complete root and child rectangle comparison; original corpus bytes retained','corpora':{}}
    all_pass=True
    for name,runner in CORPORA:
        d=out/name;d.mkdir();source=ROOT/(name+'_scenarios.json');(d/'scenarios.json').write_bytes(source.read_bytes())
        corpus=json.loads(source.read_text());runner.validate(corpus)
        env=os.environ.copy();env.update(GPUI_SCENARIOS=json.dumps(corpus),GPUI_FIXED_ROOT_CONTROL='1',GPUI_NEGATIVE_CONTROL='0')
        observed={};runs={}
        for implementation,exe in exes.items():
            proc=subprocess.run([str(exe.resolve())],env=env,capture_output=True,timeout=90)
            (d/(implementation+'.stdout')).write_bytes(proc.stdout);(d/(implementation+'.stderr')).write_bytes(proc.stderr)
            runs[implementation]={'returncode':proc.returncode,'executable_sha256':sha(exe),'stdout_sha256':sha(d/(implementation+'.stdout')),'stderr_sha256':sha(d/(implementation+'.stderr'))}
            require(proc.returncode==0,implementation+' regression process failed: '+proc.stderr.decode(errors='replace')[-2000:])
            lines=[x.removeprefix('GPUI_CONFORMANCE ') for x in proc.stdout.decode().splitlines() if x.startswith('GPUI_CONFORMANCE ')]
            require(len(lines)==1);observed[implementation]=json.loads(lines[0])
        result=runner.compare(corpus,full_bounds_observation(observed['upstream']),full_bounds_observation(observed['moonbit']))
        (d/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
        evidence['corpora'][name]={'scenarios_sha256':sha(source),'runs':runs,'summary':result['summary']}
        all_pass=all_pass and result['summary']['mismatch']==0
    require(sources=={name:source_identity(path) for name,path in [('upstream',a.upstream_source),('moonbit',a.moonbit_source),('suite',ROOT)]},'Source changed during regression execution')
    evidence['finished_at']=datetime.now(timezone.utc).isoformat()
    (out/'manifest.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps({name:data['summary'] for name,data in evidence['corpora'].items()}));return int(not all_pass)

if __name__=='__main__':raise SystemExit(main())
