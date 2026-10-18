"""Synthetic/source controls only; never execute Rust, install tools, or access CI."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
DIRECTORY=ROOT/'diagnostics/padded_text_anchor'
def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result
run=module(DIRECTORY/'run.py','padded_runner_tests')
evidence=module(DIRECTORY/'evidence.py','padded_evidence_tests')
fixture_tests=module(ROOT/'tests/test_padded_text_anchor.py','padded_fixture_tests')

def graph_records():
    record={'build_root':'/source/_build/padded-anchor-build-token','tools':{'rustc':{'path':'/toolchain/bin/rustc'}}}
    stage=record['build_root']+'/adapter';target=record['build_root']+'/target'
    artifact={'reason':'compiler-artifact','target':{'name':'gpui-padded-text-anchor-diagnostic','kind':['bin'],'src_path':stage+'/src/main.rs'},
        'fresh':False,'executable':target+'/debug/gpui-padded-text-anchor-diagnostic','filenames':[target+'/debug/gpui-padded-text-anchor-diagnostic'],
        'profile':{'test':False,'opt_level':'0','debug_assertions':True}}
    script={'reason':'build-script-executed','package_id':'registry+https://github.com/rust-lang/crates.io-index#libm@0.2.16','cfgs':['arch_enabled'],'env':[['CFG_OPT_LEVEL','0']]}
    directives='\n'.join(['[libm 0.2.16] cargo:rerun-if-changed=build.rs','[libm 0.2.16] cargo::rerun-if-env-changed=RUSTC_BOOTSTRAP',
        '[libm 0.2.16] cargo:rustc-check-cfg=cfg(arch_enabled)','[libm 0.2.16] cargo:rustc-cfg=arch_enabled','[libm 0.2.16] cargo:rustc-env=CFG_OPT_LEVEL=0'])
    stdout=directives+'\n'+'\n'.join(json.dumps(x) for x in [script,artifact,{'reason':'build-finished','success':True}])
    stderr=f'Running `CARGO_MANIFEST_DIR={stage} /toolchain/bin/rustc --crate-name gpui_padded_text_anchor_diagnostic src/main.rs --crate-type bin --emit=dep-info,link --out-dir {target}/debug/deps`'
    return record,stdout,stderr

def process(command,cwd='/source',index=0):
    return dict(command=command,cwd=cwd,returncode=0,pid=100+index,timed_out=False,resource_floor_breached=False,
        started_at=f'2026-10-18T00:00:{index*2:02}+00:00',finished_at=f'2026-10-18T00:00:{index*2+1:02}+00:00',
        disk_samples=[{'workspace':run.FLOOR,'tmp':run.FLOOR}])

def synthetic_bundle(directory):
    """Fabricated validator fixture. Source_bytes is mocked by callers explicitly."""
    token='01234567-89ab-cdef-0123-456789abcdef';root=Path('/source/_build/evidence');build=Path('/source/_build/padded-anchor-build-'+token)
    profile=run.load_profile();expected=dict(commit='1'*40,tree='2'*40,repository='gpui-mbt/gpui-conformance',run_id='123',run_attempt='1')
    def write(path,data):
        p=directory/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data if isinstance(data,bytes) else data.encode())
    for p in run.FIXTURE_PATHS:write('fixture/'+p,(ROOT/p).read_bytes())
    for p in run.RUNNER_PATHS:write('runner/'+p,(ROOT/p).read_bytes())
    for p in run.UPSTREAM_PATHS:write('upstream/'+p,'synthetic source only\n')
    for p in run.STAGED_PATHS:
        b=(ROOT/'adapters/padded_text_anchor_rust'/p).read_bytes()
        if p=='Cargo.toml':b=b.replace(b'"../../../zed-source/crates/gpui"',b'"/upstream/crates/gpui"')
        write('staged/'+p,b)
    record=dict(schema_version=1,status='executed',run_token=token,execution_root=str(root),build_root=str(build),
        upstream_source_path='/upstream',fixture_source_path='/fixture',profile=copy.deepcopy(profile),source_unchanged=True,
        started_at='2026-10-18T00:00:00+00:00',finished_at='2026-10-18T00:01:00+00:00',
        runner={'commit':expected['commit'],'tree':expected['tree']},
        session={'GITHUB_REPOSITORY':expected['repository'],'GITHUB_RUN_ID':expected['run_id'],'GITHUB_RUN_ATTEMPT':expected['run_attempt'],'GITHUB_SHA':expected['commit'],'GITHUB_JOB':'actual-padded-text-anchor'},
        tools={t:dict(path='/toolchain/bin/'+t,sha256='a'*64,size=100) for t in ('rustc','cargo')},
        staged_inputs=run.staged_inventory(directory/'staged'),unset_environment=sorted(run.UNSET))
    record['environment']={'CARGO_BUILD_JOBS':'2','CARGO_INCREMENTAL':'0','CARGO_HOME':str(build/'cargo-home'),'CARGO_TARGET_DIR':str(build/'target'),'RUSTUP_TOOLCHAIN':'1.98.1','RUSTC':'/toolchain/bin/rustc'}
    commands=[]
    for tool in ('rustc','cargo'):
        commands.append(('resolve-'+tool,['rustup','which','--toolchain','1.98.1',tool],'/toolchain/bin/'+tool+'\n',''))
    for tool in ('rustc','cargo'):
        commands.append((tool,['/toolchain/bin/'+tool,'--version','--verbose'],tool+' 1.98.1 synthetic\nhost: x86_64-unknown-linux-gnu\n',''))
    for name,value in [('sysroot','/toolchain'),('target-libdir','/toolchain/lib/rustlib/x86_64-unknown-linux-gnu/lib')]:
        commands.append((name,['/toolchain/bin/rustc','--print',name],value+'\n',''))
    _,stdout,stderr=graph_records()
    old='/source/_build/padded-anchor-build-token'
    stdout=stdout.replace(old,str(build));stderr=stderr.replace(old,str(build))
    commands.append(('build',['/toolchain/bin/cargo','build','--locked','-vv','--message-format=json-render-diagnostics','--manifest-path',str(build/'adapter/Cargo.toml')],stdout,stderr))
    raw=fixture_tests.synthetic();raw['run_token']=token
    commands.append(('raw',[str(root/'probe'),str(root/'fixture/diagnostics/padded_text_anchor/scenarios.json'),token],json.dumps(raw),''))
    for i,(stem,command,stdout,stderr) in enumerate(commands):
        record['execution' if stem=='raw' else stem]=process(command,index=i)
        write(stem+'.stdout',stdout);write(stem+'.stderr',stderr)
    record['graph']=run.rust_build_graph(record,(directory/'build.stdout').read_text(),(directory/'build.stderr').read_text())
    write('probe',b'\x7fELFsynthetic-not-a-runnable-binary')
    record['executable']=dict(path=record['graph']['artifact']['executable'],sha256=run.digest(directory/'probe'),size=(directory/'probe').stat().st_size)
    record['toolchain_inputs']=dict(sysroot='/toolchain',target_libdir='/toolchain/lib/rustlib/x86_64-unknown-linux-gnu/lib',
        files={'/toolchain/lib/rustlib/x86_64-unknown-linux-gnu/lib/libstd.rlib':dict(sha256='b'*64,size=200)},aliases={})
    write('toolchain-inputs.json',json.dumps(record['toolchain_inputs']))
    write('trace-shape.json',json.dumps(fixture_tests.verify.verify(raw)))
    record['files']=run.inventory(directory);run.save(directory/'manifest.json',record)
    return profile,expected,root,record

class PaddedAnchorEvidenceTests(unittest.TestCase):
    def test_bound_profile_and_immutable_seven(self):
        p=run.load_profile()
        self.assertEqual(p['fixture_commit'],'4bf568614f9a5707855a441314eec8080adbc8a7')
        self.assertNotEqual(p['fixture_commit'],p['integration_baseline_commit'])
        for name,meta in p['fixture_files'].items():
            self.assertEqual(meta,dict(sha256=run.digest(ROOT/name),size=(ROOT/name).stat().st_size))
        self.assertEqual(len(run.RUNNER_PATHS),5)
        self.assertLess(sum((ROOT/p).stat().st_size for p in run.RUNNER_PATHS),512*1024)

    def test_draft_and_malformed_profiles_fail_closed(self):
        with tempfile.TemporaryDirectory() as t:
            file=Path(t)/'profile.json';p=run.load_profile()
            p.update(status='draft_unbound',fixture_commit=None,fixture_tree=None,integration_baseline_commit=None,integration_baseline_tree=None)
            run.save(file,p)
            self.assertEqual(run.load_profile(file,require_bound=False),p)
            with self.assertRaises(ValueError):run.load_profile(file)
            for key,value in [('status','bound'),('schema_version',True),('estimated_artifact_zip_limit',True)]:
                bad=copy.deepcopy(p);bad[key]=value;run.save(file,bad)
                with self.assertRaises(ValueError):run.load_profile(file)

    def test_cargo_graph_and_build_script_protocol(self):
        record,stdout,stderr=graph_records()
        self.assertEqual(len(run.rust_build_graph(record,stdout,stderr)['build_script_output']),5)
        corruptions=[(stdout+'\nunknown chatter',stderr),(stdout+'\n{"reason":',stderr),
            (stdout.replace('"fresh": false','"fresh": true'),stderr),
            (stdout.replace('cargo:rustc-cfg=arch_enabled','cargo:rustc-cfg=other'),stderr),
            (stdout.replace('[libm 0.2.16]','[other 0.2.16]'),stderr),
            (stdout.replace('cargo:rustc-env=CFG_OPT_LEVEL=0','cargo:rustc-env=CFG_OPT_LEVEL=1'),stderr),
            (stdout,stderr.replace('/toolchain/bin/rustc','/other/rustc')),
            (stdout,stderr.replace('src/main.rs','src/other.rs')),
            (stdout,stderr.replace('CARGO_MANIFEST_DIR=/source','CARGO_MANIFEST_DIR=/other')),
            (stdout.replace('"success": true','"success": false'),stderr)]
        for bad_out,bad_err in corruptions:
            with self.subTest(out=bad_out[-100:],err=bad_err),self.assertRaises(ValueError):run.rust_build_graph(record,bad_out,bad_err)

    def test_cargo_completion_requires_exact_boolean_record(self):
        record,stdout,stderr=graph_records()
        original=json.dumps({'reason':'build-finished','success':True})
        controls=[{'reason':'build-finished','success':value} for value in (1,1.0,False,None)]
        controls += [{'reason':'build-finished'}, {'reason':'build-finished','success':True,'extra':0}]
        for value in controls:
            for roundtrip in (False,True):
                candidate=json.loads(json.dumps(value)) if roundtrip else value
                changed=stdout.replace(original,json.dumps(candidate))
                with self.subTest(value=value,roundtrip=roundtrip),self.assertRaises(ValueError):
                    run.rust_build_graph(record,changed,stderr)
        for replacement in [original+'\n'+original,'{"reason":"build-finished","success":false,"success":true}']:
            with self.assertRaises(ValueError):run.rust_build_graph(record,stdout.replace(original,replacement),stderr)
        self.assertEqual(run.rust_build_graph(record,stdout,stderr)['artifact']['fresh'],False)

    def test_other_critical_cargo_booleans_stay_strict(self):
        record,stdout,stderr=graph_records()
        for before,after in [('"fresh": false','"fresh": 0'),('"test": false','"test": 0'),('"debug_assertions": true','"debug_assertions": 1')]:
            with self.subTest(before=before),self.assertRaises(ValueError):
                run.rust_build_graph(record,stdout.replace(before,after),stderr)

    def test_process_metadata_negative_controls(self):
        good=process(['compiler']);evidence.process_ok(good,['compiler'],'/source')
        for key,value in [('returncode',False),('returncode',1),('pid',True),('timed_out',True),('resource_floor_breached',True),('disk_samples',[]),('command',['other']),('cwd','/other'),('finished_at','2026-10-17T00:00:00+00:00')]:
            row=copy.deepcopy(good);row[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):evidence.process_ok(row,['compiler'],'/source')

    def test_json_and_path_guards(self):
        self.assertFalse(run.json_same({'a':[True]},{'a':[1]}))
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);p=root/'a';p.write_text('x')
            for content in ['{"a":1,"a":2}','{"a":NaN}']:
                p.write_text(content)
                with self.assertRaises(ValueError):run.load(p)
            (root/'link').symlink_to(p)
            for rel in ['../a','/a','./a','link']:
                with self.assertRaises(ValueError):run.safe_file(root,rel)
            with self.assertRaises(ValueError):run.inventory(root)

    def test_source_bytes_requires_exact_committed_content(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'x').write_bytes(b'reviewed')
            with patch.object(evidence,'git',return_value=b'reviewed'):
                evidence.source_bytes(root,'',root,'a'*40,['x'])
            with patch.object(evidence,'git',return_value=b'other'):
                with self.assertRaises(ValueError):evidence.source_bytes(root,'',root,'a'*40,['x'])

    def test_synthetic_full_bundle_never_authenticates_execution(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);profile,expected,recorded,_=synthetic_bundle(root)
            # This test deliberately does not authenticate Git source. It only
            # exercises the complete internally consistent evidence validator.
            with patch.object(evidence,'source_bytes'):
                result=evidence.verify_execution(root,ROOT,ROOT,ROOT,profile,expected,recorded)
            self.assertFalse(result['execution_authenticated'])
            self.assertTrue(result['requires_original_ci_log_review'])
            self.assertFalse(result['font_parity'])
            self.assertIsNone(result['observed_numeric_goldens'])

    def test_full_bundle_tampering_rejected_after_roundtrip(self):
        for mutation in ['session','commit','profile_bool','failure','tool','command','binary','missing_log','raw_token','staged_source','sidecar','extra_file']:
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as t:
                root=Path(t);profile,expected,recorded,record=synthetic_bundle(root)
                if mutation=='session':record['session']['GITHUB_RUN_ID']='999'
                if mutation=='commit':record['runner']['commit']='3'*40
                if mutation=='profile_bool':record['profile']['schema_version']=True
                if mutation=='failure':record['status']='build_failed'
                if mutation=='tool':record['tools']['rustc']['path']='/other/rustc'
                if mutation=='command':record['execution']['command'][0]='/other/probe'
                if mutation=='binary':(root/'probe').write_bytes(b'\x7fELFother')
                if mutation=='missing_log':(root/'build.stderr').unlink()
                if mutation=='raw_token':
                    raw=run.load(root/'raw.stdout');raw['run_token']='other';run.save(root/'raw.stdout',raw)
                if mutation=='staged_source':(root/'staged/src/main.rs').write_text('// different')
                if mutation=='sidecar':
                    inputs=run.load(root/'toolchain-inputs.json');inputs['aliases']['/toolchain/lib/evil']='/other/lib';run.save(root/'toolchain-inputs.json',inputs)
                if mutation=='extra_file':(root/'unknown').write_text('extra')
                # Rehash mutated files so semantic source/process checks, rather
                # than the outer inventory alone, must reject the modification.
                record['files']=run.inventory(root);run.save(root/'manifest.json',record)
                with patch.object(evidence,'source_bytes'),self.assertRaises(ValueError):
                    evidence.verify_execution(root,ROOT,ROOT,ROOT,profile,expected,recorded)

    def test_integration_baseline_preservation_and_exact_additions(self):
        profile=run.load_profile();commit='1'*40;tree='2'*40
        baseline={'historical.txt':'100644 blob '+'a'*40}
        after={**baseline,**{p:'100644 blob '+'b'*40 for p in run.FIXTURE_PATHS+run.RUNNER_PATHS}}
        def git(source,*args):
            if args[0]=='rev-parse':return (profile['integration_baseline_tree']+'\n').encode()
            if args[0]=='merge-base':return b''
            if args[0]=='show':return (ROOT/args[1].split(':',1)[1]).read_bytes()
            raise AssertionError(args)
        for mutation in [None,'historical_blob','historical_mode','extra','missing','fixture_mode']:
            changed=copy.deepcopy(after)
            if mutation=='historical_blob':changed['historical.txt']='100644 blob '+'c'*40
            if mutation=='historical_mode':changed['historical.txt']='100755 blob '+'a'*40
            if mutation=='extra':changed['unapproved.txt']='100644 blob '+'d'*40
            if mutation=='missing':changed.pop(run.RUNNER_PATHS[0])
            if mutation=='fixture_mode':changed[run.FIXTURE_PATHS[0]]='120000 blob '+'b'*40
            with self.subTest(mutation=mutation),patch.object(run,'validate_source'),patch.object(run,'git',side_effect=git),patch.object(run,'entries',side_effect=[baseline,changed]):
                if mutation:
                    with self.assertRaises(ValueError):run.validate_suite(ROOT,ROOT,profile,commit,tree)
                else:run.validate_suite(ROOT,ROOT,profile,commit,tree)

    def test_workflow_scope_and_no_candidate_toolchain(self):
        text=(ROOT/'.github/workflows/padded-text-anchor.yml').read_text()
        self.assertIn('ref: '+run.load_profile()['fixture_commit'],text)
        self.assertIn('test_padded_anchor_evidence.py',text)
        for bad in ['moonbitlang','moonc','core-source','push:']:
            self.assertNotIn(bad,text)
        self.assertIn('if: always()',text)
        self.assertIn('contents: read',text)

if __name__=='__main__':unittest.main()
