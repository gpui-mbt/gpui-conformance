"""V2 source-policy and synthetic evidence negatives. No GPUI execution claim."""
from contextlib import contextmanager
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


E = module("historical_policy_for_v2_tests", ROOT / "diagnostics/popover_outside/evidence.py")
with patch.dict(sys.modules, {"evidence": E}):
    S = module("current_policy_for_v2_tests", ROOT / "diagnostics/popover_outside/source_current_v2.py")
with patch.dict(sys.modules, {"evidence": E, "source_current_v2": S}):
    V = module("current_evidence_for_v2_tests", ROOT / "diagnostics/popover_outside/evidence_current_v2.py")
    R = module("current_runner_for_v2_tests", ROOT / "diagnostics/popover_outside/run_current_v2.py")
    C = module("current_contracts_for_v2_tests", ROOT / "diagnostics/popover_outside/contracts_current_v2.py")
L = module("legacy_evidence_fixture_for_v2_tests", ROOT / "tests/test_popover_outside_evidence.py")


def git(source, *args):
    return subprocess.check_output(["git", "-C", str(source), *args], stderr=subprocess.STDOUT).decode().strip()


def commit(source):
    git(source, "add", "-A")
    git(source, "-c", "user.name=Source policy test", "-c", "user.email=synthetic@example.invalid",
        "-c", "commit.gpgsign=false", "commit", "-qm", "Synthetic source policy fixture")
    return git(source, "rev-parse", "HEAD"), git(source, "rev-parse", "HEAD^{tree}")


@contextmanager
def source_fixture():
    # Tiny owned-source fixture, not a clone or historical source claim. Only the
    # historical object check is mocked here; real historical objects are tested below.
    with tempfile.TemporaryDirectory(prefix="popover-current-v2-source-") as temporary:
        source = Path(temporary)
        for path in S.CURRENT_PATHS:
            target = source / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / path, target)
        (source / ".gitignore").write_text("*.ignored\n")
        (source / "unrelated.txt").write_text("Unrelated repository files may evolve.\n")
        git(source, "init", "-q")
        git(source, "config", "core.filemode", "true")
        revision, tree = commit(source)
        with patch.object(S, "validate_historical_objects"):
            yield source, revision, tree


def bundle_fixture(directory):
    args, source = L.fixture(directory)
    manifest = E.load(directory / "manifest.json")
    manifest["schema_version"] = 2
    manifest["source_policy"] = copy.deepcopy(S.PROFILE)
    for path in S.CURRENT_PATHS:
        target = directory / "suite" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        data = (ROOT / path).read_bytes()
        target.write_bytes(data)
        source[args["suite_commit"] + ":" + path] = data
        manifest["files"]["suite/" + path] = {"sha256": E.digest(target), "size": target.stat().st_size}
    L.write(directory / "manifest.json", manifest)
    return args, source


class CurrentSourceTests(unittest.TestCase):
    def test_real_historical_objects_and_frozen_bytes_are_unchanged(self):
        S.validate_historical_objects(ROOT)
        self.assertEqual(len(E.FROZEN), 7)
        for path, expected in {**E.FROZEN, **S.LEGACY_SHA256}.items():
            self.assertEqual(E.digest(ROOT / path), expected, path)

    def test_wrong_historical_tree_rejected(self):
        original = S.git
        def changed(source, *args):
            if args == ("rev-parse", S.HISTORICAL_COMMIT + "^{tree}"):
                return b"0" * 40 + b"\n"
            return original(source, *args)
        with patch.object(S, "git", side_effect=changed), self.assertRaisesRegex(ValueError, "snapshot tree"):
            S.validate_historical_objects(ROOT)

    def test_explicit_policy_inventory_and_unrelated_evolution(self):
        self.assertEqual((ROOT / S.POLICY_PATH).read_bytes(), S.POLICY_BYTES)
        self.assertEqual(set(S.CURRENT_PATHS), set(S.POLICY["files"]))
        with source_fixture() as (source, revision, tree):
            report = S.validate_suite(source, revision, tree)
            self.assertFalse(report["execution_authenticated"])
            (source / "unrelated.txt").write_text("New unrelated feature, not historical proof.\n")
            revision, tree = commit(source)
            self.assertEqual(S.validate_suite(source, revision, tree)["suite"], {"commit": revision, "tree": tree})

    def test_external_commit_and_tree_are_required(self):
        with self.assertRaises(TypeError):
            S.validate_suite(ROOT)
        with source_fixture() as (source, revision, tree):
            for wrong_commit, wrong_tree in ((revision, "0" * 40), ("HEAD", tree), (revision, "HEAD")):
                with self.subTest(commit=wrong_commit, tree=wrong_tree), self.assertRaises(ValueError):
                    S.validate_suite(source, wrong_commit, wrong_tree)
            old = revision, tree
            (source / "unrelated.txt").write_text("Different commit.\n")
            revision, tree = commit(source)
            with self.assertRaisesRegex(ValueError, "checkout identity"):
                S.validate_suite(source, *old)

    def test_dirty_current_source_and_index_rejected(self):
        for staged in (False, True):
            with self.subTest(staged=staged), source_fixture() as (source, revision, tree):
                path = "diagnostics/popover_outside/run_current_v2.py"
                with (source / path).open("a") as stream:
                    stream.write("\n# changed\n")
                if staged:
                    git(source, "add", path)
                with self.assertRaisesRegex(ValueError, "dirty checkout"):
                    S.validate_suite(source, revision, tree)

    def test_assume_unchanged_cannot_hide_modified_owned_bytes(self):
        with source_fixture() as (source, revision, tree):
            path = "diagnostics/popover_outside/run_current_v2.py"
            git(source, "update-index", "--assume-unchanged", path)
            with (source / path).open("a") as stream:
                stream.write("\n# hidden from ordinary status\n")
            self.assertEqual(git(source, "status", "--porcelain"), "")
            with self.assertRaisesRegex(ValueError, "worktree bytes"):
                S.validate_suite(source, revision, tree)

    def test_git_replacement_objects_cannot_spoof_external_source_identity(self):
        with source_fixture() as (source, revision, tree):
            path = "diagnostics/popover_outside/run_current_v2.py"
            original_blob = git(source, "rev-parse", revision + ":" + path)
            git(source, "update-index", "--assume-unchanged", path)
            with (source / path).open("a") as stream:
                stream.write("\n# replaced object\n")
            replacement_blob = git(source, "hash-object", "-w", path)
            git(source, "replace", original_blob, replacement_blob)
            self.assertEqual(git(source, "status", "--porcelain"), "")
            self.assertNotEqual(S.git(source, "show", revision + ":" + path), (source / path).read_bytes())
            with self.assertRaisesRegex(ValueError, "replacement refs"):
                S.validate_suite(source, revision, tree)

    def test_git_environment_cannot_redirect_bound_checkout(self):
        with source_fixture() as (source, revision, tree):
            with patch.dict(os.environ, {"GIT_DIR": str(ROOT / ".git"), "GIT_WORK_TREE": str(ROOT)}):
                self.assertEqual(S.validate_suite(source, revision, tree)["suite"]["commit"], revision)

    def test_external_bytecode_cache_prefix_rejected(self):
        with source_fixture() as (source, revision, tree):
            with patch.object(sys, "pycache_prefix", "/external-cache"), self.assertRaisesRegex(ValueError, "cache prefix"):
                S.validate_suite(source, revision, tree)

    def test_clean_committed_scoped_inventory_mutations_rejected(self):
        for mutation in ("extra", "missing", "executable", "symlink", "frozen", "legacy_verifier"):
            with self.subTest(mutation=mutation), source_fixture() as (source, revision, tree):
                path = source / "adapters/popover_outside_rust/src/main.rs"
                if mutation == "extra":
                    (source / "diagnostics/popover_outside/unlisted.py").write_text("# unlisted\n")
                elif mutation == "missing":
                    path.unlink()
                elif mutation == "executable":
                    path.chmod(0o755)
                elif mutation == "symlink":
                    path.unlink()
                    path.symlink_to("../../../unrelated.txt")
                else:
                    if mutation == "legacy_verifier":
                        path = source / "diagnostics/popover_outside/evidence.py"
                    with path.open("a") as stream:
                        stream.write("\n# changed\n")
                revision, tree = commit(source)
                with self.assertRaises(ValueError):
                    S.validate_suite(source, revision, tree)

    def test_ignored_additional_scoped_file_and_symlink_directory_rejected(self):
        for mutation in ("file", "symlink", "fifo", "test_cache", "cache_symlink"):
            with self.subTest(mutation=mutation), source_fixture() as (source, revision, tree):
                extra = source / "diagnostics/popover_outside/extra.ignored"
                if mutation == "file":
                    extra.write_text("Ignored does not mean authorized.\n")
                elif mutation == "symlink":
                    extra.symlink_to(source / "tests", target_is_directory=True)
                elif mutation == "fifo":
                    os.mkfifo(extra)
                else:
                    cache = source / "tests/__pycache__"
                    if mutation == "cache_symlink":
                        cache.symlink_to(source / "diagnostics", target_is_directory=True)
                    else:
                        cache.mkdir()
                        (cache / "test_popover_outside.cpython-313.pyc").write_bytes(b"untrusted bytecode")
                    with (source / ".gitignore").open("a") as stream:
                        stream.write("__pycache__/\n")
                    revision, tree = commit(source)
                self.assertEqual(git(source, "status", "--porcelain"), "")
                with self.assertRaisesRegex(ValueError, "worktree inventory|special file/symlink|cache root"):
                    S.validate_suite(source, revision, tree)

    def test_historical_ignored_cache_is_rejected_before_test_loading(self):
        with source_fixture() as (source, revision, tree):
            extra = source / "tests/cache.ignored"
            extra.write_bytes(b"untrusted cached test")
            # Fixed historical identities are covered by the real object test.
            # Isolate the ignored-extra gate here without fabricating old objects.
            with patch.object(S, "validate_source"), patch.object(S, "validate_historical_suite"), \
                 self.assertRaisesRegex(ValueError, "historical ignored extra"):
                S.validate_historical_checkout(source)

    def test_clean_committed_policy_manipulation_rejected(self):
        for mutation in ("schema", "inventory", "frozen_hash", "historical", "whitespace"):
            with self.subTest(mutation=mutation), source_fixture() as (source, revision, tree):
                policy = copy.deepcopy(S.POLICY)
                if mutation == "schema": policy["schema_version"] = 1
                elif mutation == "inventory": policy["files"].remove(S.POLICY_PATH)
                elif mutation == "frozen_hash": policy["frozen_sha256"][next(iter(E.FROZEN))] = "0" * 64
                elif mutation == "historical": policy["historical"]["commit"] = "0" * 40
                data = json.dumps(policy, indent=2) + ("\n\n" if mutation == "whitespace" else "\n")
                (source / S.POLICY_PATH).write_text(data)
                revision, tree = commit(source)
                with self.assertRaisesRegex(ValueError, "policy schema/content/hash"):
                    S.validate_suite(source, revision, tree)

    def test_historical_contract_is_routed_not_removed(self):
        # Inspect suite membership only. Historical checkout authentication and
        # execution occur in the integration entry point, not this synthetic test.
        historical, current = C.contract_suites(ROOT)
        def flatten(suite):
            for item in suite:
                if isinstance(item, unittest.TestSuite): yield from flatten(item)
                else: yield item.id()
        old_ids, current_ids = list(flatten(historical)), list(flatten(current))
        name = "test_preserves_all_723_baseline_files"
        self.assertEqual(sum(item.endswith(name) for item in old_ids), 1)
        self.assertEqual(sum(item.endswith(name) for item in current_ids), 0)
        behavior_count = len(unittest.TestLoader().getTestCaseNames(L.T.PopoverOutsideTests)) - 1
        self.assertEqual(sum("current_popover_behavior." in item for item in current_ids), behavior_count)

    def test_ci_uses_verified_history_and_current_v2_entry_points(self):
        workflow = (ROOT / ".github/workflows/popover-outside-diagnostic.yml").read_text()
        for value in (S.HISTORICAL_COMMIT, "contracts_current_v2.py", "run_current_v2.py",
                      "evidence_current_v2.py", '--suite-commit "$GITHUB_SHA"', '--suite-tree "$(git rev-parse HEAD^{tree})"'):
            self.assertIn(value, workflow)
        self.assertNotIn("continue-on-error", workflow)
        self.assertIn('manifest={"schema_version":2,"source_policy":PROFILE', (ROOT / "diagnostics/popover_outside/run_current_v2.py").read_text())
        self.assertIs(R.validate_suite, S.validate_suite)
        self.assertEqual(tuple(R.ADDED), S.CURRENT_PATHS)
        self.assertIs(V.validate_suite, S.validate_suite)


class CurrentEvidenceTests(unittest.TestCase):
    def verify_synthetic(self, directory, args, source):
        # Only external authentication is mocked. Source-policy tests above use
        # real Git repositories; these bytes remain synthetic, never a CI claim.
        with patch.object(V, "validate_suite"), patch.object(V, "validate_source"), \
             patch.object(V, "git", side_effect=lambda source_root, action, key: source[key]):
            return V.verify_bundle(directory, **args)

    def test_round_trip_binds_v2_identity_and_never_authenticates_execution(self):
        with tempfile.TemporaryDirectory(prefix="popover-current-v2-bundle-") as temporary:
            directory = Path(temporary)
            args, source = bundle_fixture(directory)
            result = self.verify_synthetic(directory, args, source)
            self.assertEqual(result["source_policy"], S.PROFILE)
            self.assertEqual(result["suite"], {"commit": args["suite_commit"], "tree": args["suite_tree"]})
            self.assertFalse(result["execution_authenticated"])
            self.assertFalse(result["source_hypotheses"]["execution_authenticated"])
            self.assertEqual(result, json.loads(json.dumps(result)))

    def test_cross_profile_replay_and_policy_mismatch_rejected(self):
        for mutation in ("v1", "bool_schema", "policy_id", "policy_hash", "missing_policy", "extra_policy"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory(prefix="popover-current-v2-bundle-") as temporary:
                directory = Path(temporary)
                args, source = bundle_fixture(directory)
                record = E.load(directory / "manifest.json")
                if mutation == "v1": record["schema_version"] = 1
                elif mutation == "bool_schema": record["schema_version"] = True
                elif mutation == "policy_id": record["source_policy"]["id"] = "historical"
                elif mutation == "policy_hash": record["source_policy"]["sha256"] = "0" * 64
                elif mutation == "missing_policy": del record["source_policy"]
                else: record["source_policy"]["override"] = True
                L.write(directory / "manifest.json", record)
                with self.assertRaises((ValueError, KeyError)):
                    self.verify_synthetic(directory, args, source)
        with tempfile.TemporaryDirectory(prefix="popover-current-v2-bundle-") as temporary:
            directory = Path(temporary)
            args, source = bundle_fixture(directory)
            with self.assertRaisesRegex(ValueError, "manifest origin"):
                E.verify_bundle(directory, **args)

    def test_v2_retains_original_evidence_fail_closed_checks(self):
        mutations = ("compiler_exit", "build_exit", "runtime_exit", "token", "session", "suite", "source_changed",
                     "lock", "binary", "raw", "missing", "extra", "hypotheses", "chronology", "disk_floor")
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory(prefix="popover-current-v2-bundle-") as temporary:
                directory = Path(temporary)
                args, source = bundle_fixture(directory)
                record = E.load(directory / "manifest.json")
                if mutation == "compiler_exit": record["rustc"]["returncode"] = 1
                elif mutation == "build_exit": record["build"]["returncode"] = 101
                elif mutation == "runtime_exit": record["execution"]["returncode"] = -9
                elif mutation == "token": record["run_token"] = "2" * 36
                elif mutation == "session": args["run_id"] = "456"
                elif mutation == "suite": args["suite_tree"] = "c" * 40
                elif mutation == "source_changed": record["source_unchanged"] = False
                elif mutation == "missing": record["files"].pop("suite/" + S.POLICY_PATH)
                elif mutation == "extra": (directory / "extra").write_text("extra")
                elif mutation == "chronology": record["execution"]["started_at"] = "2026-10-17T11:00:00+00:00"
                elif mutation == "disk_floor": record["disk_samples"][0]["tmp"] = 0
                elif mutation == "hypotheses": L.write(directory / "hypotheses.json", {"execution_authenticated": True})
                else:
                    path = {"lock": "build-Cargo.lock", "binary": "probe", "raw": "raw.stdout"}[mutation]
                    with (directory / path).open("ab") as stream: stream.write(b"corruption")
                L.write(directory / "manifest.json", record)
                with self.assertRaises(ValueError): self.verify_synthetic(directory, args, source)

    def test_rehashed_source_or_policy_cannot_choose_its_own_authority(self):
        for path in (S.POLICY_PATH, "diagnostics/popover_outside/evidence_current_v2.py"):
            with self.subTest(path=path), tempfile.TemporaryDirectory(prefix="popover-current-v2-bundle-") as temporary:
                directory = Path(temporary)
                args, source = bundle_fixture(directory)
                relative = "suite/" + path
                target = directory / relative
                target.write_bytes(target.read_bytes() + b"\n")
                record = E.load(directory / "manifest.json")
                record["files"][relative] = {"sha256": E.digest(target), "size": target.stat().st_size}
                L.write(directory / "manifest.json", record)
                with self.assertRaisesRegex(ValueError, "source bytes"):
                    self.verify_synthetic(directory, args, source)

    def test_v2_sidecar_symlinks_rejected(self):
        for name in ("hypotheses.json", "manifest.json"):
            with self.subTest(name=name), tempfile.TemporaryDirectory(prefix="popover-current-v2-bundle-") as temporary:
                parent = Path(temporary)
                directory = parent / "bundle"
                directory.mkdir()
                args, source = bundle_fixture(directory)
                external = parent / name
                (directory / name).rename(external)
                (directory / name).symlink_to(external)
                with self.assertRaisesRegex(ValueError, "symlink"):
                    self.verify_synthetic(directory, args, source)


if __name__ == "__main__":
    unittest.main()
