#!/usr/bin/env python3
"""Run unchanged historical tests on history and current behavior tests on HEAD.

The 723-file assertion is executed, never skipped or weakened. Its root is the
verified immutable historical checkout. Current behavior uses current source.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import unittest

from evidence import ROOT, require
from source_current_v2 import validate_historical_checkout, validate_suite


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def contract_suites(historical_source):
    loader = unittest.TestLoader()
    historical = unittest.TestSuite()
    for stem in ("test_popover_outside", "test_popover_outside_evidence"):
        historical.addTests(loader.loadTestsFromModule(module("historical_" + stem,
                            historical_source / "tests" / (stem + ".py"))))
    current = unittest.TestSuite()
    behavior = module("current_popover_behavior", ROOT / "tests/test_popover_outside.py")
    names = loader.getTestCaseNames(behavior.PopoverOutsideTests)
    preservation = "test_preserves_all_723_baseline_files"
    require(preservation in names, "missing original historical preservation assertion")
    # This exact test method is in the historical suite above, on its real root.
    # Every other original method still executes on current source, unmodified.
    current.addTests(behavior.PopoverOutsideTests(name) for name in names if name != preservation)
    for stem in ("test_popover_outside_evidence", "test_popover_outside_current_v2"):
        current.addTests(loader.loadTestsFromModule(module("current_" + stem,
                         ROOT / "tests" / (stem + ".py"))))
    return historical, current


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical-source", type=Path, required=True)
    parser.add_argument("--suite-commit", required=True)
    parser.add_argument("--suite-tree", required=True)
    args = parser.parse_args()
    validate_historical_checkout(args.historical_source)
    report = validate_suite(ROOT, args.suite_commit, args.suite_tree)
    historical, current = contract_suites(args.historical_source)
    runner = unittest.TextTestRunner(verbosity=2)
    print("Historical source proof and unchanged tests (not current runtime evidence)", flush=True)
    historical_result = runner.run(historical)
    print("Current source behavior, evidence and v2 mutation contracts (synthetic only)", flush=True)
    current_result = runner.run(current)
    require(historical_result.wasSuccessful() and current_result.wasSuccessful(), "contract tests failed")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
