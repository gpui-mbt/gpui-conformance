"""Append the test-only observer to a pristine pinned production source copy."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

UPSTREAM='5a5fbe79917971a4d52a96b6ddb04da198a5012e'
IMG_BLOB='2c77e5f32ad12a8fafb88305ba208ca74a80cdac'
ASSET_BLOB='08b6d8afa0d1088e50f1e9697e01407c9c623f6d'
ASSET_SHA256='77453d98d46494b3b34b94aa863b686ea299e0190030a5c7ca5377b238332522'
def blob(data):return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
def sha(data):return hashlib.sha256(data).hexdigest()
def prepare(source,observer,report):
    source=source.resolve(); observer=observer.resolve()
    assert subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()==UPSTREAM
    assert not subprocess.check_output(['git','-C',str(source),'status','--porcelain','--untracked-files=all']).strip()
    target=source/'crates/gpui/src/elements/img.rs'
    production=target.read_bytes(); appended=observer.read_bytes()
    assert blob(production)==IMG_BLOB,'production image source mismatch'
    asset=source/'crates/gpui/examples/image/app-icon.png'; asset_bytes=asset.read_bytes()
    assert len(asset_bytes)==168173 and blob(asset_bytes)==ASSET_BLOB and sha(asset_bytes)==ASSET_SHA256
    combined=production+b'\n'+appended
    target.write_bytes(combined)
    assert target.read_bytes()[:len(production)]==production
    changed=subprocess.check_output(['git','-C',str(source),'diff','--name-only'],text=True).splitlines()
    assert changed==['crates/gpui/src/elements/img.rs']
    manifest={'upstream_commit':UPSTREAM,'production_path':'crates/gpui/src/elements/img.rs',
        'production_blob':IMG_BLOB,'production_sha256':sha(production),'production_length':len(production),
        'observer_sha256':sha(appended),'combined_sha256':sha(combined),
        'asset_path':'crates/gpui/examples/image/app-icon.png','asset_blob':ASSET_BLOB,'asset_sha256':ASSET_SHA256}
    report.write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('observer',type=Path);p.add_argument('report',type=Path)
    a=p.parse_args();prepare(a.source,a.observer,a.report)
