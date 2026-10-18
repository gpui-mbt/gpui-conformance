#!/usr/bin/env python3
"""Build honest disposable compiled faults; never overwrite baseline evidence."""
import argparse, hashlib, json, shutil, subprocess, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
PACKAGE='examples/conformance_pattern'
CONTROLS={
 'wrong_interval':('package','pattern.mbt','if id == 23 { 9.0 }','if id == 23 { 4.5 }'),
 'wrong_color':('package','pattern.mbt','31 => rgba(0,0.5,0,1)','31 => rgba(1,0,1,1)'),
 'missing_row':('package','pattern.mbt','33 => rgba(1,1,0,1)','33 => rgba(1,1,0,0)'),
 'wrong_phase':('core','scene/slash_pattern.mbt','let relative_x = point.x() - bounds.left()','let relative_x = point.x() - bounds.left() + 2.0'),
}
def copy_pattern_site(baseline,site,manifest):
 site.mkdir()
 compiled={('runtime.mjs' if name=='hello_world' else name+'.mjs') for name in manifest.get('runtime_sha256_by_example',{}) if name!='pattern'}
 for source in baseline.iterdir():
  if source.is_file():shutil.copy2(source,site/source.name)
 moon=site/'moonbit';moon.mkdir()
 for source in (baseline/'moonbit').rglob('*'):
  relative=source.relative_to(baseline/'moonbit')
  if source.is_file() and str(relative) not in compiled:
   destination=moon/relative;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,destination)

def mutate_source(before,find,replace,label):
 text=before.decode();assert text.count(find)==1,f'{label}: mutation anchor is not unique'
 return text.replace(find,replace).encode()

def sha(data):return hashlib.sha256(data).hexdigest()
def run(args,cwd,check=True):
 p=subprocess.run(args,cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 if check and p.returncode:raise RuntimeError(p.stdout)
 return p

def build(core,baseline,out,controls):
 manifest_bytes=(baseline/'build-manifest.json').read_bytes();original=json.loads(manifest_bytes)
 contract=json.loads((ROOT/'web/pairs/pattern.json').read_text())
 assert original['moonbit']['revision']==contract['candidate']['revision'],'baseline revision differs from frozen candidate'
 assert original['moonbit']['tree']==contract['candidate']['tree'],'baseline tree differs from frozen candidate'
 assert original.get('pattern_control') is None,'baseline is already a mutation'
 assert not out.exists(),'use a fresh output path'
 assert run(['git','status','--porcelain','--untracked-files=no'],core).stdout.strip()=='','core must be clean'
 head=run(['git','rev-parse','HEAD'],core).stdout.strip()
 tree=run(['git','rev-parse','HEAD^{tree}'],core).stdout.strip()
 assert tree==contract['candidate']['tree'],'core tree differs from frozen candidate'
 assert head==original['moonbit']['revision'],'core revision differs from baseline pin'
 baseline_runtime=(baseline/'moonbit/pattern.mjs').read_bytes()
 expected=original.get('files',{}).get('moonbit/pattern.mjs') or original['runtime_sha256_by_example']['pattern']
 assert sha(baseline_runtime)==expected,'baseline compiled runtime differs from manifest'
 out.mkdir(parents=True)
 for control in controls:
  kind,path,find,replace=CONTROLS[control]
  with tempfile.TemporaryDirectory(prefix=f'pattern-{control}-',dir=out) as temporary:
   work=Path(temporary);candidate=work/'core'
   shutil.copytree(core,candidate,ignore=shutil.ignore_patterns('.git','_build','target','node_modules'))
   destination=candidate/PACKAGE
   if destination.exists():shutil.rmtree(destination)
   shutil.copytree(ROOT/'web/moonbit/pattern',destination)
   target=(destination if kind=='package' else candidate)/path
   before=target.read_bytes();after=mutate_source(before,find,replace,control)
   # Prove these exact copied sources reproduce the accepted baseline bytes
   # before applying any mutation; a manifest pin alone does not prove this.
   baseline_test=run(['moon','test',PACKAGE,'--target','js'],candidate)
   baseline_build=run(['moon','build',PACKAGE,'--target','js','--release'],candidate)
   baseline_rebuilt=(candidate/'_build/js/release/build'/PACKAGE/'conformance_pattern.js').read_bytes()
   assert baseline_rebuilt==baseline_runtime,'copied baseline source does not reproduce baseline runtime bytes'
   target.write_bytes(after)
   compiler=run(['moon','version','--all'],candidate).stdout
   tests=run(['moon','test',PACKAGE,'--target','js'],candidate,check=False)
   compilation=run(['moon','build',PACKAGE,'--target','js','--release'],candidate)
   runtime=(candidate/'_build/js/release/build'/PACKAGE/'conformance_pattern.js').read_bytes()
   assert runtime!=baseline_runtime,'control produced unchanged compiled runtime'
   site=out/control;copy_pattern_site(baseline,site,original)
   (site/'moonbit/pattern.mjs').write_bytes(runtime)
   evidence=site/'pattern-control-evidence';evidence.mkdir()
   (evidence/'baseline-build-manifest.json').write_bytes(manifest_bytes)
   (evidence/'before-source.txt').write_bytes(before);(evidence/'after-source.txt').write_bytes(after)
   (evidence/'baseline-test.log').write_text(baseline_test.stdout);(evidence/'baseline-build.log').write_text(baseline_build.stdout);
   (evidence/'test.log').write_text(tests.stdout);(evidence/'build.log').write_text(compilation.stdout)
   declaration={'id':control,'kind':'compiled_source_fault','core_baseline_revision':head,'core_baseline_tree':tree,'baseline_manifest_sha256':sha(manifest_bytes),'baseline_runtime_sha256':sha(baseline_runtime),'baseline_rebuilt_runtime_sha256':sha(baseline_rebuilt),'runtime_sha256':sha(runtime),'source_path':(PACKAGE+'/' if kind=='package' else '')+path,'source_before_sha256':sha(before),'source_after_sha256':sha(after),'find':find,'replace':replace,'compiler':compiler,'package_tests_exit':tests.returncode,'package_tests_note':'Faulted package test failures retained; never claimed passed. Build must succeed.','scope':'All stripe x phases shifted +2 logical pixels' if control=='wrong_phase' else control}
   mutated=json.loads(manifest_bytes);mutated['pattern_control']=declaration;mutated['comparison_status']='intentional_negative_control_unverified'
   if 'files' in mutated:mutated['files']['moonbit/pattern.mjs']=sha(runtime)
   if 'runtime_sha256_by_example' in mutated:mutated['runtime_sha256_by_example']['pattern']=sha(runtime)
   (site/'build-manifest.json').write_text(json.dumps(mutated,indent=2)+'\n')
   (evidence/'control.json').write_text(json.dumps(declaration,indent=2)+'\n')
   print(json.dumps({'control':control,'site':str(site),'status':'compiled_fault_not_browser_verified'}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--gpui',required=True,type=Path);p.add_argument('--baseline-site',required=True,type=Path);p.add_argument('--out',required=True,type=Path);p.add_argument('--control',action='append',choices=list(CONTROLS));a=p.parse_args();build(a.gpui.resolve(),a.baseline_site.resolve(),a.out.resolve(),a.control or list(CONTROLS))
