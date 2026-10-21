#!/usr/bin/env python3
"""Run tests/ modules serially in isolated Python interpreters (not web/tests)."""
import argparse
from collections import Counter
from dataclasses import dataclass
import math
import os
import signal
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_MODULES = frozenset({
    'test_background_evidence', 'test_boundary_evidence', 'test_bundle_evidence',
    'test_comparator', 'test_native_evidence', 'test_observer_evidence',
})


@dataclass(frozen=True)
class Result:
    module: str
    status: str
    detail: str = ''


def command(root, module, evidence, corpus=None, expected_summary=None):
    """Construct commands without importing or discovering target code in-process."""
    if module in EVIDENCE_MODULES:
        args = [sys.executable, '-B', str(root / 'tests' / (module + '.py')),
                '--evidence', str(evidence[module])]
        if module == 'test_comparator':
            if corpus is not None:
                args += ['--corpus', str(corpus)]
            if expected_summary is not None:
                args += ['--expected-summary', str(expected_summary)]
        return args
    return [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests',
            '-p', module + '.py']


def run_child(args, root, timeout):
    """Own a POSIX session so a timed-out test cannot leave tool children running."""
    process = subprocess.Popen(args, cwd=root, shell=False, start_new_session=True)
    try:
        return process.wait(timeout=timeout)
    finally:
        # Also reap surviving descendants after an ordinary module exit.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def run_modules(root, modules, evidence, timeout, corpus=None, expected_summary=None):
    results = []
    for module in modules:
        reason = None
        if module in EVIDENCE_MODULES:
            path = evidence.get(module)
            if path is None or not path.is_dir():
                reason = f'requires --evidence {module}=EXISTING_DIRECTORY'
        if module == 'test_comparator':
            for label, path in [('corpus', corpus), ('expected-summary', expected_summary)]:
                if path is not None and not path.is_file():
                    reason = f'--{label} file does not exist: {path}'
        if reason:
            result = Result(module, 'BLOCKED', reason)
        else:
            print(f'RUN {module}', flush=True)
            try:
                code = run_child(command(root, module, evidence, corpus, expected_summary), root, timeout)
                result = Result(module, 'PASS' if code == 0 else 'FAIL',
                                f'signal {-code}' if code < 0 else f'exit {code}')
            except subprocess.TimeoutExpired:
                result = Result(module, 'ERROR', f'timeout after {timeout}s')
            except OSError as exc:
                result = Result(module, 'ERROR', f'could not start interpreter: {exc}')
        results.append(result)
        print(f'{result.status} {module}: {result.detail}', flush=True)
    return results


def main(argv=None, *, root=ROOT):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--module', action='append', default=[], help='test module stem; repeat to select a subset')
    parser.add_argument('--evidence', action='append', default=[], metavar='MODULE=DIRECTORY',
                        help='retained evidence for one of: ' + ', '.join(sorted(EVIDENCE_MODULES)))
    parser.add_argument('--corpus', type=Path, help='comparator corpus')
    parser.add_argument('--expected-summary', type=Path, help='comparator expected summary')
    parser.add_argument('--timeout', type=float, default=300, help='seconds per module (default: 300)')
    args = parser.parse_args(argv)
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error('--timeout must be finite and positive')
    if os.name != 'posix':
        parser.error('process-group cleanup requires POSIX (Linux or macOS)')
    root = root.resolve()
    available = {p.stem for p in (root / 'tests').glob('test_*.py') if p.is_file()}
    if not available:
        parser.error('no tests/test_*.py modules found')
    modules = list(dict.fromkeys(args.module)) if args.module else sorted(available)
    if set(modules) - available:
        parser.error('unknown module(s): ' + ', '.join(sorted(set(modules) - available)))
    evidence = {}
    for item in args.evidence:
        name, sep, value = item.partition('=')
        if not sep or not value or name not in EVIDENCE_MODULES or name in evidence:
            parser.error('--evidence requires a unique known MODULE=DIRECTORY')
        evidence[name] = Path(value).resolve()
    results = run_modules(root, modules, evidence, args.timeout,
                          args.corpus.resolve() if args.corpus else None,
                          args.expected_summary.resolve() if args.expected_summary else None)
    counts = Counter(result.status for result in results)
    print('Module summary: ' + ', '.join(f'{name}={counts[name]}' for name in ('PASS', 'FAIL', 'ERROR', 'BLOCKED')))
    print(f'{len(results)} modules selected of {len(available)}; unittest test counts appear in child output. web/tests excluded.')
    return int(any(result.status != 'PASS' for result in results))


if __name__ == '__main__':
    sys.exit(main())
