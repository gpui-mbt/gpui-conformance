"""Synthetic sensitivity/source tests, never evidence of candidate execution."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
ORACLE=Path(os.environ.get('POPOVER_ORACLE_SOURCE',ROOT))
sys.path.insert(0,str(ROOT/'diagnostics/popover_outside_pair'))
import compare
import evidence
import run_controls
import run_rust
import run as pair_run

def module(path):
    spec=importlib.util.spec_from_file_location('synthetic_original',path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result

ORIGINAL=module(ORACLE/'tests/test_popover_outside.py')

class PairSourceTests(unittest.TestCase):
    def setUp(self):
        self.raw=ORIGINAL.synthetic_trace()
        self.fixture=copy.deepcopy(ORIGINAL.FIXTURE)
        self.candidate=dict(schema_version=1,layer='compiled-moonbit-popover-outside',
            run_token=self.raw['run_token'],input=copy.deepcopy(self.fixture),
            operations=compare.project_rust(self.raw,ORACLE,self.fixture))

    def compared(self,candidate):
        return compare.compare(self.raw,candidate,ORACLE,self.fixture,self.raw['run_token'])

    def test_synthetic_match_is_unauthenticated(self):
        report=self.compared(self.candidate)
        self.assertEqual(report['status'],'match')
        self.assertFalse(report['execution_authenticated'])
        self.assertEqual(report['events'],23)

    def test_projection_does_not_alias_raw(self):
        before=copy.deepcopy(self.raw)
        self.candidate['operations'][0]['frame']['bounds']['host'][0]=100
        self.assertEqual(self.raw,before)

    def test_semantic_mutations_rejected(self):
        for mode in ('state','callbacks','registration','bounds','frame','extra','boolean-number'):
            with self.subTest(mode=mode):
                candidate=copy.deepcopy(self.candidate)
                first=candidate['operations'][0]
                if mode=='state':first['state']=[True,False]
                if mode=='callbacks':candidate['operations'][2]['callbacks']=[]
                if mode=='registration':first['frame']['registrations']=['parent']
                if mode=='bounds':first['frame']['bounds']['host'][0]=1
                if mode=='frame':first.pop('frame')
                if mode=='extra':first['extra']='unobserved'
                if mode=='boolean-number':first['state']=[0,0]
                self.assertEqual(self.compared(candidate)['status'],'semantic_mismatch')

    def test_button_semantics_rejected(self):
        candidate=copy.deepcopy(self.candidate)
        callback=next(cb for row in candidate['operations'] for cb in row['callbacks'] if cb['button']=='right')
        callback['button']='left'
        self.assertEqual(self.compared(candidate)['status'],'semantic_mismatch')

    def test_raw_oracle_is_authoritative(self):
        self.raw['events'][0]['sequence']=100
        with self.assertRaises(ValueError):self.compared(self.candidate)

    def test_envelope_types_and_input(self):
        for key,value in [('schema_version',True),('run_token','other'),('input',{})]:
            candidate=copy.deepcopy(self.candidate);candidate[key]=value
            with self.assertRaises(ValueError):self.compared(candidate)

    def test_nonfinite_and_duplicate_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'x.json'
            for text in ('{"a":1,"a":2}','{"a":NaN}'):
                path.write_text(text)
                with self.assertRaises(ValueError):compare.load(path)
                with self.assertRaises(ValueError):run_rust.load(path)

    def test_mutation_sites_unique_and_described(self):
        self.assertEqual(len(run_controls.NAMES),5)
        core=os.environ.get('POPOVER_CORE_SOURCE')
        for name in run_controls.NAMES:
            relative,before,after=run_controls.replacements(name)
            if relative.startswith('element/'):
                if not core:continue  # CI full core unit coverage separately executes this source.
                source=Path(core)/relative
            else:source=ROOT/'adapters/popover_outside_moonbit/main.mbt'
            self.assertEqual(source.read_text().count(before),1,name)
            with tempfile.TemporaryDirectory() as temporary:
                target=Path(temporary)/relative;target.parent.mkdir(parents=True);target.write_bytes(source.read_bytes())
                descriptor=run_controls.apply_mutation(temporary,name)
                self.assertNotEqual(descriptor['original_sha256'],descriptor['mutated_sha256'])
                self.assertIn(after,target.read_text())

    def test_adapter_uses_production_api(self):
        source=(ROOT/'adapters/popover_outside_moonbit/main.mbt').read_text()
        for call in ('PointerOutsideFrame::new','dispatch_input_with','request_layout_with_device_scale',
                     '.prepaint()', '.handle_input(', '.with_bounds(', '.anchored_after('):
            # Associated anchored constructor has a namespace delimiter.
            self.assertIn(call.replace('.anchored_after(', '::anchored_after('),source)
        self.assertNotIn('.contains(',source)
        for step in self.fixture['steps']:self.assertNotIn('"'+step['id']+'"',source)

    def test_exact_core_projection_accepts_unselected_modes(self):
        core=os.environ.get('POPOVER_CORE_SOURCE')
        if not core:self.skipTest('exact core source is supplied by dedicated CI')
        entries=pair_run.blobs(Path(core))
        self.assertEqual(len(entries),914)
        self.assertIn('README.md',entries)
        selected=pair_run.production_paths(Path(core))
        self.assertIn('element/pointer_outside.mbt',selected)
        self.assertIn('controls/button/button.mbt',selected)
        self.assertNotIn('README.md',selected)
        for path in selected:
            self.assertTrue(run_rust.git(core,'ls-tree','HEAD','--',path).startswith(b'100644 blob '))

    def test_selected_unsafe_source_modes_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'safe.mbt').write_text('// source')
            for mode in ('100755','120000'):
                with patch.object(pair_run,'git',return_value=(mode+' blob '+'a'*40+'\tunsafe.mbt\n').encode()):
                    with self.assertRaises(ValueError):pair_run.require_selected_source(root,'unsafe.mbt')
            with patch.object(pair_run,'git',return_value=('100644 blob '+'a'*40+'\tsafe.mbt\n').encode()):
                pair_run.require_selected_source(root,'safe.mbt')
                (root/'link.mbt').symlink_to(root/'safe.mbt')
                with self.assertRaises(ValueError):pair_run.require_selected_source(root,'link.mbt')

    def test_source_pins(self):
        profile=json.loads((ROOT/'diagnostics/popover_outside_pair/profile.json').read_text())
        for key,value in [('core_commit',run_rust.CORE),('oracle_commit',run_rust.ORACLE),('upstream_commit',run_rust.UPSTREAM)]:
            self.assertEqual(profile[key],value)
        self.assertEqual(len(evidence.ADDITIONS),11)
        self.assertIn('tests/test_outside_pointer_pair.py',evidence.ADDITIONS)

    def test_safe_paths_and_sidecar_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'manifest.json').write_text('{}');(root/'sidecar').write_text('a')
            recorded={'files':run_rust.inventory(root)}
            evidence.check_inventory(root,recorded)
            (root/'sidecar').write_text('b')
            with self.assertRaises(ValueError):evidence.check_inventory(root,recorded)
            for relative in ('../sidecar','/absolute','./sidecar'):
                with self.assertRaises(ValueError):run_rust.safe_file(root,relative)
            (root/'link').symlink_to(root/'sidecar')
            with self.assertRaises(ValueError):run_rust.inventory(root)

    def test_directory_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'a').mkdir();(root/'a/x').write_text('x');(root/'link').symlink_to(root/'a',target_is_directory=True)
            with self.assertRaises(ValueError):run_rust.safe_file(root,'link/x')
            with self.assertRaises(ValueError):run_rust.inventory(root)

    def test_process_bool_exit_and_resource_records_rejected(self):
        record=dict(command=['tool'],cwd='/source',returncode=0,pid=10,timed_out=False,
            resource_floor_breached=False,started_at='2026-10-17T00:00:00+00:00',
            finished_at='2026-10-17T00:00:01+00:00',
            disk_samples=[dict(workspace=run_rust.FLOOR,tmp=run_rust.FLOOR)])
        evidence.process_ok(record,['tool'],'/source')
        for key,value in [('returncode',False),('pid',True),('disk_samples',[]),('finished_at','2026-10-16T00:00:00+00:00')]:
            changed={**record,key:value}
            with self.assertRaises(ValueError):evidence.process_ok(changed,['tool'],'/source')

    def test_unknown_compiler_plan_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'build-plan.stdout').write_text('evil build-package -target js -g -O0\n')
            record={'environment':{'MOON_HOME':'/moon'},'toolchain':{'moonc':{'command_path':'/moon/moonc','resolved_path':'/moon/moonc'}}}
            with self.assertRaises(ValueError):evidence.verify_js_plan(root,record,{'probe/main.mbt':{}})

    def test_rust_cargo_graph_source_and_output_binding(self):
        record={'build_root':'/build','tools':{'rustc':{'path':'/toolchain/bin/rustc'}}}
        artifact={'reason':'compiler-artifact','target':{'name':'gpui-popover-outside-diagnostic',
            'kind':['bin'],'src_path':'/build/adapter/src/main.rs'},'fresh':False,
            'executable':'/build/target/debug/gpui-popover-outside-diagnostic',
            'filenames':['/build/target/debug/gpui-popover-outside-diagnostic'],
            'profile':{'test':False,'opt_level':'0','debug_assertions':True}}
        stdout=json.dumps(artifact)+'\n'+json.dumps({'reason':'build-finished','success':True})
        stderr='Running `CARGO_MANIFEST_DIR=/build/adapter /toolchain/bin/rustc --crate-name gpui_popover_outside_diagnostic src/main.rs --crate-type bin --emit=dep-info,link --out-dir /build/target/debug/deps`'
        result=run_rust.rust_build_graph(record,stdout,stderr)
        self.assertEqual(result['artifact'],artifact)
        absolute=stderr.replace(' src/main.rs ',' /build/adapter/src/main.rs ')
        self.assertEqual(run_rust.rust_build_graph(record,stdout,absolute)['artifact'],artifact)
        for bad_out,bad_err in [
            (stdout.replace('"fresh": false','"fresh": true'),stderr),
            (stdout,stderr.replace('/toolchain/bin/rustc','/other/rustc')),
            (stdout,stderr.replace(' src/main.rs ',' src/other.rs ')),
            (stdout,stderr.replace('CARGO_MANIFEST_DIR=/build/adapter','CARGO_MANIFEST_DIR=/other')),
            (stdout,stderr.replace('--out-dir /build/target/debug/deps','--out-dir /other')),
            (stdout.replace('/build/target/debug/gpui-popover-outside-diagnostic','/other/probe'),stderr),
        ]:
            with self.subTest(stdout=bad_out,stderr=bad_err):
                with self.assertRaises(ValueError):run_rust.rust_build_graph(record,bad_out,bad_err)

    def test_cargo_verbose_build_script_protocol(self):
        record={'build_root':'/build','tools':{'rustc':{'path':'/toolchain/bin/rustc'}}}
        artifact={'reason':'compiler-artifact','target':{'name':'gpui-popover-outside-diagnostic',
            'kind':['bin'],'src_path':'/build/adapter/src/main.rs'},'fresh':False,
            'executable':'/build/target/debug/gpui-popover-outside-diagnostic',
            'filenames':['/build/target/debug/gpui-popover-outside-diagnostic'],
            'profile':{'test':False,'opt_level':'0','debug_assertions':True}}
        script={'reason':'build-script-executed',
            'package_id':'registry+https://github.com/rust-lang/crates.io-index#libm@0.2.16',
            'cfgs':['arch_enabled'],'env':[['CFG_OPT_LEVEL','0']]}
        directives='\n'.join([
            '[libm 0.2.16] cargo:rerun-if-changed=build.rs',
            '[libm 0.2.16] cargo::rerun-if-env-changed=RUSTC_BOOTSTRAP',
            '[libm 0.2.16] cargo:rustc-check-cfg=cfg(arch_enabled)',
            '[libm 0.2.16] cargo:rustc-cfg=arch_enabled',
            '[libm 0.2.16] cargo:rustc-env=CFG_OPT_LEVEL=0'])
        stdout=directives+'\n'+'\n'.join(json.dumps(m) for m in [script,artifact,{'reason':'build-finished','success':True}])
        stderr='Running `CARGO_MANIFEST_DIR=/build/adapter /toolchain/bin/rustc --crate-name gpui_popover_outside_diagnostic src/main.rs --crate-type bin --emit=dep-info,link --out-dir /build/target/debug/deps`'
        result=run_rust.rust_build_graph(record,stdout,stderr)
        self.assertEqual(len(result['build_script_output']),5)
        self.assertEqual(result['artifact'],artifact)
        for bad in [
            stdout+'\nunknown build chatter',
            stdout+'\n{"reason":',
            stdout+'\n{"reason":"not-a-cargo-record"}',
            stdout+'\n{"reason":"build-finished","reason":"build-finished","success":true}',
            stdout.replace('[libm 0.2.16]','[unknown 0.2.16]'),
            stdout.replace('cargo:rustc-cfg=arch_enabled','cargo:rustc-cfg=unreported_cfg'),
            stdout.replace('cargo:rustc-env=CFG_OPT_LEVEL=0','cargo:rustc-env=CFG_OPT_LEVEL=3'),
            stdout.replace('cargo:rerun-if-changed=build.rs','cargo:unexpected=build.rs'),
        ]:
            with self.subTest(stdout=bad):
                with self.assertRaises(ValueError):run_rust.rust_build_graph(record,bad,stderr)

    def test_compiler_version_flags_match_retained_cli_help(self):
        # Fresh CI39077117020 retained moonc's rejection of --version and its
        # explicit help: '-v show version'. This test invokes no compiler.
        self.assertEqual(pair_run.version_command('moonc','/moon/moonc'),['/moon/moonc','-v'])
        self.assertEqual(pair_run.version_command('moon','/moon/moon'),['/moon/moon','--version'])
        self.assertEqual(pair_run.version_command('node','/bin/node'),['/bin/node','--version'])
        with self.assertRaises(ValueError):pair_run.version_command('other','/bin/other')

if __name__=='__main__':unittest.main()
