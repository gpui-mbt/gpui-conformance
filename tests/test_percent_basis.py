"""Synthetic percentage-basis contracts, never a compiled-runtime parity claim."""
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import build_flex_basis as b
import run_flex_basis as r


RESOLVER = '''prefix
fn FlexItem::resolved_flex_basis(
  self : FlexItem,
  fallback : Double,
  main_extent : Double,
) -> Result[Double, LayoutError] {
  match self.flex_basis {
    Auto => Ok(fallback)
    Points(value) => if value < 0.0 { Err(NegativeValue) } else { Ok(value) }
    Percent(ratio) => match resolve_dimension(Dimension::Percent(ratio), Some(main_extent)) {
      Ok(Some(resolved)) => Ok(resolved)
      Ok(None) => Ok(fallback)
      Err(error) => Err(error)
    }
  }
}
suffix
'''


class PercentCorpusTests(unittest.TestCase):
    def setUp(self):
        self.corpus=json.loads((r.ROOT/'percent_basis_scenarios.json').read_text())

    def observations(self, implementation):
        rows=[]
        for case in self.corpus['cases']:
            rect=[0,0,case['width'],case['height']]
            observed={'bounds':[rect.copy()]+[[0,0,1,1] for _ in case['children']],
                      'device_scale_factor':case['device_scale_factor']}
            if implementation == 'upstream':
                observed['test_window_viewport']=rect.copy()
            else:
                observed.update(physical_viewport=rect.copy(),snapshot_viewport=rect.copy())
            rows.append({'id':case['id'],'layer':'headless-layout','status':'observed','observation':observed})
        return {'implementation':implementation,'cases':rows}

    def test_independently_authored_coverage_and_ci(self):
        r.validate(self.corpus)
        cases=self.corpus['cases']
        self.assertEqual(len(cases),144)
        self.assertEqual(sum(c['expected_capability_mismatch'] for c in cases),120)
        self.assertEqual(len({c['family'] for c in cases}),12)
        for direction in ('row','column','row_reverse','column_reverse'):
            for scale in (1,1.5,2):
                group=[c for c in cases if c['direction']==direction and c['device_scale_factor']==scale]
                self.assertEqual(len(group),12)
                self.assertEqual(sum(c['expected_capability_mismatch'] for c in group),10)
        self.assertEqual({c['wrap'] for c in cases},{'nowrap','wrap','wrap_reverse'})
        ratios={v['percent'] for c in cases for v in c['flex_basis'] if type(v) is dict}
        self.assertIn(0,ratios);self.assertIn(1,ratios)
        self.assertTrue(any(0<v<1 for v in ratios));self.assertTrue(any(v>1 for v in ratios))
        for case in cases:
            self.assertTrue(case['description'])
            self.assertTrue(case['gap_x']>0 and case['gap_y']>0)
            self.assertTrue(len(set(case['padding']))>1 and len(set(case['border']))>1)
            if not case['expected_capability_mismatch']:
                self.assertFalse(any(type(v) is dict for v in case['flex_basis']))
            self.assertFalse({'expected_bounds','expected_rectangles'} & set(case))
        self.assertIn("python3 -m unittest discover -s tests -p 'test_percent_basis.py' -v",(r.ROOT/'.github/workflows/harness.yml').read_text())

    def test_exact_percent_encoding_and_old_schema_remain_separate(self):
        for value in (None,0,0.125,{'percent':0},{'percent':0.5},{'percent':1},{'percent':1.25}):
            corpus=copy.deepcopy(self.corpus);corpus['cases'][0]['flex_basis'][0]=value
            r.validate(corpus)
        invalid=(True,-1,float('nan'),float('inf'),{},[],{'percent':None},{'percent':True},
                 {'percent':-0.1},{'percent':float('nan')},{'percent':float('inf')},
                 {'percent':'0.5'},{'percentage':0.5},{'percent':0.5,'points':1},
                 {'percent':0.5,'extra':None},'50%')
        for value in invalid:
            corpus=copy.deepcopy(self.corpus);corpus['cases'][0]['flex_basis'][0]=value
            with self.subTest(value=value),self.assertRaises(ValueError):r.validate(corpus)
        original=json.loads((r.ROOT/'flex_basis_scenarios.json').read_text())
        r.validate(original)
        original['cases'][0]['flex_basis'][0]={'percent':0.5}
        with self.assertRaises(ValueError):r.validate(original)
        for kind in (None,False,'percent','adapter-ignore-percent'):
            corpus=copy.deepcopy(self.corpus);corpus['capability_control']=kind
            with self.assertRaises(ValueError):r.validate(corpus)

    def test_every_root_and_child_coordinate_compared(self):
        self.assertEqual(r.compare(self.corpus,self.observations('upstream'),self.observations('moonbit'))['summary'],
                         {'total':144,'pass':144,'mismatch':0})
        for node in range(4):
            for coordinate in range(4):
                upstream,moon=self.observations('upstream'),self.observations('moonbit')
                moon['cases'][0]['observation']['bounds'][node][coordinate]+=1
                result=r.compare(self.corpus,upstream,moon)
                self.assertEqual(result['summary']['mismatch'],1)
                self.assertEqual(result['cases'][0]['differences'][0]['path'],f'bounds[{node}][{coordinate}]')

    def test_viewports_scale_and_projection_fail_closed(self):
        for implementation in ('upstream','moonbit'):
            for field in ('device_scale_factor','bounds','extra'):
                upstream,moon=self.observations('upstream'),self.observations('moonbit')
                observed=(upstream if implementation=='upstream' else moon)['cases'][0]['observation']
                if field=='device_scale_factor':observed[field]=True
                elif field=='bounds':observed[field].pop()
                else:observed[field]='unexpected'
                with self.subTest(implementation=implementation,field=field),self.assertRaises(ValueError):r.compare(self.corpus,upstream,moon)
        for field in ('physical_viewport','snapshot_viewport'):
            upstream,moon=self.observations('upstream'),self.observations('moonbit')
            moon['cases'][0]['observation'][field][2]+=1e-10
            with self.assertRaises(ValueError):r.compare(self.corpus,upstream,moon)
        upstream,moon=self.observations('upstream'),self.observations('moonbit')
        upstream['cases'][0]['observation']['test_window_viewport'][2]+=1
        with self.assertRaises(ValueError):r.compare(self.corpus,upstream,moon)

    def test_control_mode_cannot_relabel_points_or_positive_build(self):
        for kind in r.CONTROL_KINDS:
            positive={'control_kind':kind,'disable_flex_basis':False}
            if kind==r.PERCENT_CONTROL:
                r.validate_control_mode(positive,self.corpus,False)
            else:
                with self.assertRaises(ValueError):r.validate_control_mode(positive,self.corpus,False)
            with self.assertRaises(ValueError):r.validate_control_mode(positive,self.corpus,True)
        historical=json.loads((r.ROOT/'flex_basis_scenarios.json').read_text())
        r.validate_control_mode({'control_kind':r.PERCENT_CONTROL,'disable_flex_basis':False},historical,False)
        mutant={'control_kind':r.PERCENT_CONTROL,'disable_flex_basis':True}
        r.validate_control_mode(mutant,self.corpus,True)
        with self.assertRaises(ValueError):r.validate_control_mode(mutant,self.corpus,False)
        mutant['control_kind']=r.POINTS_CONTROL
        with self.assertRaises(ValueError):r.validate_control_mode(mutant,self.corpus,True)
        for invalid in (None,0,1,'true'):
            mutant['disable_flex_basis']=invalid
            with self.assertRaises(ValueError):r.validate_control_mode(mutant,self.corpus,True)

    def test_adapters_resolve_percent_in_real_engines_not_the_probe(self):
        rust=(r.ROOT/'adapters/flex_basis/rust/src/main.rs').read_text()
        moon=(r.ROOT/'adapters/percent_basis/moonbit/basis.mbt').read_text()
        old=(r.ROOT/'adapters/flex_basis/moonbit/basis.mbt').read_text()
        self.assertIn('child.flex_basis(relative(ratio as f32))',rust)
        self.assertIn('value.len() == 1 && value.contains_key("percent")',rust)
        self.assertIn('@layout.FlexBasis::percent(number(fields.get("percent").unwrap()))',moon)
        self.assertIn('fields.length() != 1',moon)
        self.assertNotIn('main_extent',moon)
        self.assertNotIn('FlexBasis::percent',old)
        for source in (rust,moon,old):self.assertNotIn('DISABLE_PERCENT',source)

    def test_separate_exact_source_profile_is_fail_closed(self):
        path=r.ROOT/'percent_basis_pins.json';pins=json.loads(path.read_text())
        self.assertEqual(pins['upstream']['revision'],'5a5fbe79917971a4d52a96b6ddb04da198a5012e')
        self.assertEqual(pins['upstream']['tree'],'990fb995914d51a546b20e5cf0382dafc105c299')
        for name in ('upstream','moonbit'):
            for field in ('revision','tree'):self.assertRegex(pins[name][field],r'^[0-9a-f]{40}$')
        sources={name:{**pins[name],'dirty':False} for name in ('upstream','moonbit')}
        r.validate_pins(sources,path)
        for name in sources:
            for field in ('revision','tree'):
                changed=copy.deepcopy(sources);changed[name][field]='0'*40
                with self.subTest(name=name,field=field),self.assertRaises(ValueError):r.validate_pins(changed,path)
        sources['upstream']['dirty']=True
        with self.assertRaises(ValueError):r.validate_pins(sources,path)
        old=json.loads((r.ROOT/'flex_basis_pins.json').read_text())
        self.assertEqual(old['moonbit']['revision'],'a732eacee4f8fa6df394d5b76a64f7a111ac8adc')


class PercentMutationTests(unittest.TestCase):
    def test_only_percent_result_changes_and_points_mutation_still_works(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'layout').mkdir();path=root/'layout/layout.mbt'
            path.write_text(RESOLVER)
            mutation=b.disable_flex_basis(root,r.PERCENT_CONTROL)
            self.assertEqual(path.read_text(),RESOLVER.replace('Ok(Some(resolved)) => Ok(resolved)','Ok(Some(_)) => Ok(fallback)'))
            self.assertNotIn('Ok(Some(resolved))',mutation['mutated_function'])
            self.assertEqual(mutation['kind'],r.PERCENT_CONTROL)
            self.assertIn('Points(value)',mutation['mutated_function'])
            self.assertIn('Ok(value)',mutation['mutated_function'])
            self.assertIn('Err(error) => Err(error)',mutation['mutated_function'])
            with self.assertRaises(ValueError):b.disable_flex_basis(root,r.PERCENT_CONTROL)
            path.write_text(RESOLVER)
            b.disable_flex_basis(root,r.POINTS_CONTROL)
            self.assertEqual(path.read_text(),RESOLVER.replace('Ok(value)','Ok(fallback)'))
            for broken in (RESOLVER.replace('Ok(resolved)','Ok(other)'),RESOLVER.replace('Ok(resolved)','Ok(resolved) + Ok(resolved)')):
                path.write_text(broken)
                with self.assertRaises(ValueError):b.disable_flex_basis(root,r.PERCENT_CONTROL)
                self.assertEqual(path.read_text(),broken)

    def test_manifest_binds_pin_parser_mutation_and_entire_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source';mutant=root/'mutant'
            for path in (source,mutant):
                (path/'layout').mkdir(parents=True);(path/'layout/layout.mbt').write_text(RESOLVER)
            pins=root/'pins.json';pins.write_text(json.dumps({'schema_version':1,'capability_control':r.PERCENT_CONTROL}))
            sources={name:{'revision':'r','tree':'t','source_sha256':'s','files':{'layout/layout.mbt':r.sha(source/'layout/layout.mbt')},'path':str(source)} for name in ('upstream','moonbit','suite')}
            mutation=b.disable_flex_basis(mutant,r.PERCENT_CONTROL)
            manifest={'sources':copy.deepcopy(sources),'pins_sha256':r.sha(pins),'control_kind':r.PERCENT_CONTROL,
                      'basis_parser':r.basis_parser_identity(r.PERCENT_CONTROL),'disable_flex_basis':True,
                      'mutation':mutation,'executables':{}}
            with patch.object(r,'validate_pins'):
                r.validate_build(manifest,sources,{},pins)
                for key,value in [('control_kind',r.POINTS_CONTROL),('basis_parser',r.basis_parser_identity(r.POINTS_CONTROL)),
                                  ('pins_sha256','changed'),('disable_flex_basis',False),('mutation',None)]:
                    changed=copy.deepcopy(manifest);changed[key]=value
                    with self.subTest(key=key),self.assertRaises(ValueError):r.validate_build(changed,sources,{},pins)
                for key,value in [('kind',r.POINTS_CONTROL),('file','conformance_probe/basis.mbt'),
                                  ('original_sha256','changed'),('mutated_sha256','changed'),
                                  ('original_function','wrong'),('mutated_function','ignored inputs')]:
                    changed=copy.deepcopy(manifest);changed['mutation'][key]=value
                    with self.subTest(key=key),self.assertRaises(ValueError):r.validate_build(changed,sources,{},pins)
                for name in sources:
                    changed=copy.deepcopy(sources);changed[name]['source_sha256']='changed'
                    with self.assertRaises(ValueError):r.validate_build(manifest,changed,{},pins)


class BuildModeTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name);self.core=self.root/'core';(self.core/'layout').mkdir(parents=True)
        (self.core/'layout/layout.mbt').write_text(RESOLVER)
        self.pins=self.root/'pins.json';self.pins.write_text(json.dumps({'schema_version':1,'capability_control':r.PERCENT_CONTROL}))
        self.identity={'revision':'revision','tree':'tree','source_sha256':'source','dirty':False,
                       'path':str(self.core),'files':{'layout/layout.mbt':r.sha(self.core/'layout/layout.mbt')}}
        self.args=['build_flex_basis.py','--upstream-source',str(self.root/'upstream'),'--moonbit-source',str(self.core),
                   '--pins',str(self.pins),'--output',str(self.root/'output')]

    def invoke(self,extra=()):
        with patch('sys.argv',self.args+list(extra)),patch.object(b,'source_identity',return_value=self.identity),\
                patch.object(b,'validate_pins',return_value=json.loads(self.pins.read_text())),contextlib.redirect_stdout(io.StringIO()):
            b.main()
        return json.loads((self.root/'output/build-plan.json').read_text())

    def test_cold_build_is_locked_offline_and_plan_only(self):
        with patch.object(b.subprocess,'run') as run,patch.object(b,'cached_rust') as cache:
            plan=self.invoke()
        run.assert_not_called();cache.assert_not_called()
        self.assertEqual(plan['rust_build_mode'],'locked-cargo-offline')
        command=plan['commands'][0]['command']
        self.assertEqual(command[:4],['cargo','+1.98.1','build','--locked'])
        self.assertIn('--offline',command);self.assertIn('--target-dir',command)
        self.assertEqual(plan['basis_parser'],r.basis_parser_identity(r.PERCENT_CONTROL))
        self.assertEqual((self.root/'output/moon/conformance_probe/basis.mbt').read_bytes(),(r.ROOT/'adapters/percent_basis/moonbit/basis.mbt').read_bytes())
        self.assertFalse((self.root/'output/build-manifest.json').exists())

    def test_explicit_online_cold_build_never_silently_falls_back(self):
        plan=self.invoke(['--online'])
        self.assertEqual(plan['rust_build_mode'],'locked-cargo-online')
        self.assertIn('--locked',plan['commands'][0]['command'])
        self.assertNotIn('--offline',plan['commands'][0]['command'])

    def test_online_with_reuse_is_rejected_before_any_output(self):
        for option in ('--rust-dependency-cache','--reuse-rust-build'):
            with self.subTest(option=option),self.assertRaises(ValueError):self.invoke(['--online',option,str(self.root/'missing')])
            self.assertFalse((self.root/'output').exists())

    def test_cache_failure_does_not_fall_back_to_cargo(self):
        with patch.object(b,'cached_rust',side_effect=ValueError('Cached dependency source pin mismatch')) as cached,\
                patch.object(b.subprocess,'run') as run,self.assertRaisesRegex(ValueError,'source pin mismatch'):
            self.invoke(['--rust-dependency-cache',str(self.root/'cache'),'--execute-build'])
        cached.assert_called_once();run.assert_not_called()

    def test_failed_cold_build_keeps_logs_and_does_not_run_moon(self):
        with patch.object(b.subprocess,'run',return_value=type('Process',(),{'returncode':1})()) as run,\
                self.assertRaisesRegex(ValueError,'rust build failed'):
            self.invoke(['--online','--execute-build'])
        run.assert_called_once()
        self.assertTrue((self.root/'output/rust-build.stderr').exists())
        self.assertFalse((self.root/'output/build-manifest.json').exists())
        plan=json.loads((self.root/'output/build-plan.json').read_text())
        self.assertEqual(plan['commands'][0]['returncode'],1)

    def test_verified_binary_reuse_needs_no_dependency_cache(self):
        binary=self.root/'upstream.exe';binary.write_bytes(b'unique executable fixture')
        adapter=r.ROOT/'adapters/flex_basis/rust'
        previous={'sources':{'upstream':self.identity},'toolchains':{'rust':'fixture rust version'},
                  'rust_adapter_sha256':{str(path.relative_to(adapter)):r.sha(path) for path in sorted(adapter.rglob('*')) if path.is_file()},
                  'executables':{'upstream':{'path':str(binary),'sha256':r.sha(binary)}}}
        manifest=self.root/'prior.json';manifest.write_text(json.dumps(previous))
        with patch.object(b,'cached_rust') as cache,patch.object(b.subprocess,'check_output',return_value='fixture rust version\n'):
            plan=self.invoke(['--reuse-rust-build',str(manifest)])
        cache.assert_not_called()
        self.assertEqual(plan['rust_build_mode'],'verified-binary-reuse')
        self.assertEqual([row['name'] for row in plan['commands']],['moon'])
        self.assertEqual(plan['reused_rust']['manifest_sha256'],r.sha(manifest))

    def test_historical_point_profile_has_no_percent_api_dependency(self):
        self.pins.write_text(json.dumps({'schema_version':1}))
        plan=self.invoke()
        self.assertEqual(plan['control_kind'],r.POINTS_CONTROL)
        prepared=(self.root/'output/moon/conformance_probe/basis.mbt').read_text()
        self.assertNotIn('FlexBasis::percent',prepared)
        self.assertEqual(plan['basis_parser'],r.basis_parser_identity(r.POINTS_CONTROL))


if __name__=='__main__':unittest.main()
