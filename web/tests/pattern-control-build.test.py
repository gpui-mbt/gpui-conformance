import importlib.util,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('controls',Path(__file__).resolve().parents[1]/'scripts/build_pattern_controls.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ControlBuildTests(unittest.TestCase):
 def test_binding_source_anchors_are_exact_and_unique(self):
  source=(m.ROOT/'web/moonbit/pattern/pattern.mbt').read_bytes()
  for name,(kind,path,find,replace) in m.CONTROLS.items():
   if kind=='package':
    result=m.mutate_source(source,find,replace,name)
    self.assertNotEqual(m.sha(result),m.sha(source));self.assertEqual(source.count(find.encode()),1);self.assertIn(replace.encode(),result)
 def test_missing_and_ambiguous_anchors_reject(self):
  for before in [b'absent',b'needle needle']:
   with self.assertRaisesRegex(AssertionError,'anchor is not unique'):m.mutate_source(before,'needle','mutation','test')
 def test_selective_site_copy_omits_other_runtimes_and_rust(self):
  with tempfile.TemporaryDirectory() as temp:
   base=Path(temp)/'base';base.mkdir();moon=base/'moonbit';moon.mkdir();(base/'rust').mkdir();(base/'rust/huge.wasm').write_bytes(b'unused')
   for file in ['pattern.mjs','runtime.mjs','gradient.mjs','host.mjs','render.mjs','IBMPlexSans-Regular.ttf']:(moon/file).write_bytes(file.encode())
   (base/'load-timing.mjs').write_bytes(b'timing');out=Path(temp)/'out'
   m.copy_pattern_site(base,out,{'runtime_sha256_by_example':{'pattern':'a','hello_world':'b','gradient':'c'}})
   self.assertEqual({p.name for p in (out/'moonbit').iterdir()},{'pattern.mjs','host.mjs','render.mjs','IBMPlexSans-Regular.ttf'})
   self.assertFalse((out/'rust').exists());self.assertEqual((out/'moonbit/pattern.mjs').read_bytes(),b'pattern.mjs')
if __name__=='__main__':unittest.main(verbosity=2)
