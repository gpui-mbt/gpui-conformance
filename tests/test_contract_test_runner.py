"""Runner tests use tiny temporary suites, never recursively run this repository."""
import contextlib
import io
import os
import time
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import run_contract_tests as runner


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'tests').mkdir()

    def write(self, path, text):
        dest = self.root / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text)

    def run_suite(self, names, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return runner.run_modules(self.root, names, kwargs.pop('evidence', {}),
                                      kwargs.pop('timeout', 5), **kwargs)

    def test_collisions_both_orders_and_no_parent_import(self):
        for name in ('a', 'b'):
            self.write(f'{name}/run.py', f'VALUE = {name!r}\n')
            self.write(f'tests/test_{name}.py',
                       'import sys, unittest\nfrom pathlib import Path\n'
                       f'sys.path.insert(0, str(Path(__file__).resolve().parents[1] / {name!r}))\n'
                       'import run\nclass Test(unittest.TestCase):\n'
                       f' def test_value(self): self.assertEqual(run.VALUE, {name!r})\n')
        before = dict(sys.modules)
        for order in (['test_a', 'test_b'], ['test_b', 'test_a']):
            self.assertEqual([r.status for r in self.run_suite(order)], ['PASS', 'PASS'])
        self.assertIs(sys.modules.get('run'), before.get('run'))
        self.assertNotIn('test_a', sys.modules)

    def test_failure_does_not_skip_later_module(self):
        self.write('tests/test_bad.py', 'raise RuntimeError("missing evidence is still an error")\n')
        self.write('tests/test_good.py', 'import unittest\nclass T(unittest.TestCase):\n def test_ok(self): pass\n')
        self.assertEqual([r.status for r in self.run_suite(['test_bad', 'test_good'])], ['FAIL', 'PASS'])

    def test_timeout_signal_spawn_error_continue(self):
        with patch.object(runner, 'run_child', side_effect=[
                subprocess.TimeoutExpired('python', 1), -9,
                OSError('unavailable'), 0]) as run:
            result = self.run_suite(['test_a', 'test_b', 'test_c', 'test_d'])
        self.assertEqual([r.status for r in result], ['ERROR', 'FAIL', 'ERROR', 'PASS'])
        self.assertIn('signal 9', result[1].detail)
        self.assertEqual(run.call_count, 4)
        self.assertEqual(run.call_args.args[1], self.root)

    @unittest.skipUnless(os.name == 'posix', 'process groups require POSIX')
    def test_real_timeout_cleans_descendants_and_continues(self):
        marker = self.root / 'descendant_finished'
        code = f"import time; from pathlib import Path; time.sleep(1); Path({str(marker)!r}).touch()"
        self.write('tests/test_slow.py',
                   'import subprocess, sys, time\n'
                   f'subprocess.Popen([sys.executable, "-c", {code!r}])\n'
                   'time.sleep(10)\n')
        self.write('tests/test_good.py', 'import unittest\nclass T(unittest.TestCase):\n def test_ok(self): pass\n')
        results = self.run_suite(['test_slow', 'test_good'], timeout=0.3)
        self.assertEqual([r.status for r in results], ['ERROR', 'PASS'])
        time.sleep(1.1)
        self.assertFalse(marker.exists())

    @unittest.skipUnless(os.name == 'posix', 'signals require POSIX')
    def test_real_signal_failure(self):
        self.write('tests/test_signal.py', 'import os, signal\nos.kill(os.getpid(), signal.SIGTERM)\n')
        result = self.run_suite(['test_signal'])[0]
        self.assertEqual(result.status, 'FAIL')
        self.assertIn('signal', result.detail)

    def test_interrupt_cleans_only_owned_group(self):
        from unittest.mock import Mock
        child = Mock(pid=987654, **{'wait.side_effect': [KeyboardInterrupt(), 0]})
        with patch.object(runner.subprocess, 'Popen', return_value=child) as popen, \
                patch.object(runner.os, 'killpg') as kill, self.assertRaises(KeyboardInterrupt):
            runner.run_child(['python'], self.root, 3)
        self.assertEqual(popen.call_args.kwargs,
                         {'cwd': self.root, 'shell': False, 'start_new_session': True})
        kill.assert_called_once_with(child.pid, runner.signal.SIGKILL)
        self.assertEqual(child.wait.call_count, 2)

    def test_all_evidence_modules_block_without_spawn(self):
        with patch.object(runner, 'run_child') as run:
            result = self.run_suite(sorted(runner.EVIDENCE_MODULES))
        self.assertEqual(len(result), 6)
        self.assertTrue(all(r.status == 'BLOCKED' for r in result))
        run.assert_not_called()

    def test_evidence_cli_passthrough(self):
        for name in runner.EVIDENCE_MODULES:
            self.write(f'tests/{name}.py',
                       'import sys\nfrom pathlib import Path\n'
                       'assert "--evidence" in sys.argv\n'
                       'assert Path(sys.argv[sys.argv.index("--evidence")+1]).is_dir()\n'
                       + ('assert "--corpus" in sys.argv and "--expected-summary" in sys.argv\n'
                          if name == 'test_comparator' else ''))
        corpus = self.root / 'corpus.json'
        corpus.write_text('{}')
        results = self.run_suite(sorted(runner.EVIDENCE_MODULES),
                                 evidence={n: self.root for n in runner.EVIDENCE_MODULES},
                                 corpus=corpus, expected_summary=corpus)
        self.assertTrue(all(r.status == 'PASS' for r in results))

    def test_missing_comparator_file_blocks(self):
        with patch.object(runner, 'run_child') as run:
            results = self.run_suite(['test_comparator'], evidence={'test_comparator': self.root},
                                     corpus=self.root / 'missing')
        self.assertEqual(results[0].status, 'BLOCKED')
        run.assert_not_called()

    def test_selection_inventory_and_nonzero_blocker(self):
        self.write('tests/test_background_evidence.py', 'raise AssertionError("must not import")')
        self.write('web/tests/test_ignored.py', 'raise AssertionError("out of scope")')
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(runner.main([], root=self.root), 1)
        self.assertIn('1 modules selected of 1', output.getvalue())
        self.assertIn('BLOCKED=1', output.getvalue())

    def test_invalid_selections_and_timeout(self):
        self.write('tests/test_good.py', '')
        for args in (['--module', '../bad'], ['--timeout', 'nan'], ['--timeout', '0'],
                     ['--evidence', 'test_unknown=x']):
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                runner.main(args, root=self.root)


if __name__ == '__main__':
    unittest.main()
