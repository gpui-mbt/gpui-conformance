#!/usr/bin/env python3
"""Verify existing compiled bytes against final committed source without rebuilding.

This is an attestation, not a new build. Original build identity, dirty state,
failed-attempt provenance and command logs remain nested and unchanged. Only
listed noncompiled corpus/comparator/test/document changes can be accepted.
"""
import argparse
import json
from pathlib import Path
from datetime import datetime,timezone
from run_root_box import ROOT,require,sha,source_identity,validate_pins

NONCOMPILED={
    'ROOT_BOX_RESULTS.md','root_box_scenarios.json','run_root_box.py',
    'run_root_box_regressions.py','tests/test_root_box.py','attest_root_box_build.py',
    '.github/workflows/harness.yml','root_box_pins.json',
}


def verify_source_equivalence(original,current):
    # Only historical build verification can admit the exact pinned local revision.
    # A current source checkout must always meet the strict public pin.
    validate_pins(original,allow_local_core=True);validate_pins(current)
    for name in ('upstream','moonbit'):
        keys=('revision','tree','source_sha256','files') if name=='upstream' else ('tree','source_sha256','files')
        for key in keys:
            require(original[name][key]==current[name][key], 'Compiled '+name+' '+key+' changed')
    before,after=original['suite']['files'],current['suite']['files']
    changed={key for key in set(before)|set(after) if before.get(key)!=after.get(key)}
    require(changed<=NONCOMPILED,'Changed compiled or unrelated suite source: '+repr(sorted(changed-NONCOMPILED)))
    return sorted(changed)


def verify_pin_migration(original,pins,current_pin_sha256):
    if original['pins_sha256']==current_pin_sha256:return
    historical=pins['moonbit_local_build']
    require(original['pins_sha256']==historical['historical_pins_sha256'],'Unrecognized historical build pins')
    require(original['sources']['moonbit']['revision']==historical['revision'],'Historical build revision differs')
    require(original['sources']['moonbit']['tree']==historical['tree']==pins['moonbit']['tree'],'Historical/public tree differs')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('original-build-manifest','upstream-source','moonbit-source','output'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();original=json.loads(a.original_build_manifest.read_text())
    current={name:source_identity(path) for name,path in [('upstream',a.upstream_source),('moonbit',a.moonbit_source),('suite',ROOT)]}
    require(not any(s['dirty'] for s in current.values()),'Final attestation requires committed clean sources')
    pins=json.loads((ROOT/'root_box_pins.json').read_text())
    verify_pin_migration(original,pins,sha(ROOT/'root_box_pins.json'))
    changed=verify_source_equivalence(original['sources'],current)
    for entry in original['executables'].values():require(sha(Path(entry['path']))==entry['sha256'],'Executable changed')
    # Verify the actual prepared source copies used for those successful commands.
    commands={row['name']:row for row in original['commands']}
    moon=Path(commands['moon']['cwd'])
    for relative,digest in current['moonbit']['files'].items():require(sha(moon/relative)==digest,'Built MoonBit snapshot differs: '+relative)
    for path in (ROOT/'adapters/root_box/moonbit').rglob('*'):
        if path.is_file():require(sha(path)==sha(moon/'conformance_probe'/path.relative_to(ROOT/'adapters/root_box/moonbit')),'Built MoonBit adapter differs')
    rust=Path(original['executables']['upstream']['path']).parent/'rust'
    for path in (ROOT/'adapters/root_box/rust').rglob('*'):
        if not path.is_file():continue
        relative=path.relative_to(ROOT/'adapters/root_box/rust')
        if str(relative)=='Cargo.toml':
            expected=path.read_text().replace('"../../../zed-source/crates/gpui"',json.dumps(str(a.upstream_source.resolve()/'crates/gpui')))
            require((rust/relative).read_text()==expected,'Built Rust manifest differs')
        else:require(sha(path)==sha(rust/relative),'Built Rust adapter differs: '+str(relative))
    deps=original['rust_dependencies'];debug=Path(deps['cache'])/'rust/target/debug'
    require(all(sha(debug/path)==digest for path,digest in deps['dependency_sha256'].items()),'Read-only dependency cache changed')
    attestation={'kind':'verified-existing-binaries-not-rebuilt','verified_at':datetime.now(timezone.utc).isoformat(),
                 'sources':current,'pins_sha256':sha(ROOT/'root_box_pins.json'),'executables':original['executables'],
                 'original_build_manifest_path':str(a.original_build_manifest.resolve()),'original_build_manifest_sha256':sha(a.original_build_manifest),
                 'original_build_manifest':original,'noncompiled_source_changes':changed,
                 'core_revision_equivalence':{'built_revision':original['sources']['moonbit']['revision'],'verified_revision':current['moonbit']['revision'],'tree':current['moonbit']['tree'],'source_sha256':current['moonbit']['source_sha256'],'meaning':'Distinct commit identities retained; exact Git tree and every source-file byte match, not a rebuilt public binary.'},
                 'verification':'Exact compiled core, upstream, adapter and prepared source-copy bytes; executable and read-only dependency hashes unchanged. Final suite commit supplies updated corpus/comparator/tests/docs, not newly compiled binaries.'}
    require(current=={name:source_identity(path) for name,path in [('upstream',a.upstream_source),('moonbit',a.moonbit_source),('suite',ROOT)]},'Source changed during verification')
    require(not a.output.exists(),'Refusing to replace evidence');a.output.write_text(json.dumps(attestation,indent=2)+'\n')
    print(json.dumps({'attestation':str(a.output),'noncompiled_source_changes':changed,'executables':attestation['executables']},indent=2))

if __name__=='__main__':main()
