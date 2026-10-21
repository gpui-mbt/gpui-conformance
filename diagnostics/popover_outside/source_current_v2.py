"""Version 2 current-source policy; the historical v1 verifier remains unchanged.

The caller supplies the reviewed current commit AND tree, never bundle identities.
The owned inventory is closed; unrelated repository evolution is not a v1 claim.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

from evidence import (ROOT, BASE, BASE_TREE, FROZEN, ADDED as HISTORICAL_PATHS,
                      digest, require, safe_file,
                      validate_suite as validate_historical_suite)

HISTORICAL_COMMIT = "999e3d95ee2b67d387223ef3eaecd693f285924e"
HISTORICAL_TREE = "0e71d50fd4cfbff3f42cb4d66919822f9943a062"
POLICY_ID = "popover-outside-current-source-v2"
POLICY_PATH = "diagnostics/popover_outside/source_policy_v2.json"
# Explicit allowlist, not glob expansion or a list accepted from evidence.
CURRENT_PATHS = tuple(sorted((*HISTORICAL_PATHS,
    "diagnostics/popover_outside/source_current_v2.py",
    POLICY_PATH,
    "diagnostics/popover_outside/evidence_current_v2.py",
    "diagnostics/popover_outside/run_current_v2.py",
    "diagnostics/popover_outside/contracts_current_v2.py",
    "diagnostics/popover_outside/CURRENT_SOURCE_V2.md",
    "tests/test_popover_outside_current_v2.py")))
# In addition to the original seven frozen files, v1 executable policy stays intact.
LEGACY_SHA256 = {
    "diagnostics/popover_outside/evidence.py": "564a8835d8ed1f3d45425e4bf1099319d4691b91954a25056bef00a4a15cd508",
    "diagnostics/popover_outside/run.py": "9d0f2f8e85756014ce5e07f06f4ca0ab3d900e4aafe1d995245102ca1219939e",
}
POLICY = {
    "schema_version": 2,
    "policy_id": POLICY_ID,
    "historical": {"commit": HISTORICAL_COMMIT, "tree": HISTORICAL_TREE,
                   "baseline_commit": BASE, "baseline_tree": BASE_TREE,
                   "baseline_files": 723, "additions": 11},
    "files": list(CURRENT_PATHS),
    "frozen_sha256": {**FROZEN, **LEGACY_SHA256},
}
POLICY_BYTES = (json.dumps(POLICY, indent=2) + "\n").encode()
POLICY_SHA256 = hashlib.sha256(POLICY_BYTES).hexdigest()
PROFILE = {"id": POLICY_ID, "sha256": POLICY_SHA256}


def git(source, *args):
    # External commit/tree IDs must resolve to actual stored objects, not local
    # replacement refs or a repository redirected by inherited Git variables.
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    return subprocess.check_output(["git", "--no-replace-objects", "-C", str(source), *args], env=environment)


def entries(source, revision):
    result = {}
    for entry in git(source, "ls-tree", "-rz", revision).split(b"\0"):
        if entry:
            metadata, path = entry.split(b"\t", 1)
            result[path.decode()] = metadata.decode()
    return result


def validate_source(source, commit, tree):
    require(sys.pycache_prefix is None, "external bytecode cache prefix unsupported")
    require(re.fullmatch(r"[0-9a-f]{40}", commit) and re.fullmatch(r"[0-9a-f]{40}", tree), "Git identity shape")
    require(git(source, "rev-parse", commit + "^{tree}").decode().strip() == tree, "Git tree identity")
    require(git(source, "rev-parse", "HEAD").decode().strip() == commit, "checkout identity")
    require(not git(source, "for-each-ref", "refs/replace").strip(), "Git replacement refs")
    require(not git(source, "status", "--porcelain", "--untracked-files=all").strip(), "dirty checkout")


def in_scope(path):
    return (path.startswith(("adapters/popover_outside_rust/", "diagnostics/popover_outside/"))
            or path.startswith(("tests/test_popover_outside", "tests/__pycache__/test_popover_outside"))
            or path == ".github/workflows/popover-outside-diagnostic.yml")


def verify_worktree_file(source, commit, path, metadata):
    require(metadata.startswith("100644 blob "), "current source mode/type: " + path)
    file = safe_file(source, path)
    require(stat.S_ISREG(file.stat().st_mode) and not file.stat().st_mode & 0o111,
            "current worktree mode/type: " + path)
    require(file.read_bytes() == git(source, "show", commit + ":" + path),
            "current worktree bytes: " + path)


def validate_historical_objects(source):
    """Verify fixed Git objects, without rebasing history onto current main."""
    require(git(source, "rev-parse", HISTORICAL_COMMIT + "^{tree}").decode().strip()
            == HISTORICAL_TREE, "historical snapshot tree")
    require(git(source, "rev-parse", BASE + "^{tree}").decode().strip() == BASE_TREE,
            "historical baseline tree")
    before, after = entries(source, BASE), entries(source, HISTORICAL_COMMIT)
    require(len(before) == 723, "historical baseline count")
    require(set(after) == set(before) | set(HISTORICAL_PATHS), "historical exact eleven additions")
    require(all(after[path] == identity for path, identity in before.items()),
            "historical mode/blob changed")
    for path in HISTORICAL_PATHS:
        require(after[path].startswith("100644 blob "), "historical added source mode/type")
    for path, expected in {**FROZEN, **LEGACY_SHA256}.items():
        require(hashlib.sha256(git(source, "show", HISTORICAL_COMMIT + ":" + path)).hexdigest()
                == expected, "historical reviewed source changed: " + path)


def validate_historical_checkout(source):
    validate_source(source, HISTORICAL_COMMIT, HISTORICAL_TREE)
    validate_historical_objects(source)
    # Execute the original validator too, without replacing its globals or rules.
    validate_historical_suite(source, HISTORICAL_COMMIT, HISTORICAL_TREE)
    require(not git(source, "ls-files", "--others", "--ignored", "--exclude-standard", "-z"),
            "historical ignored extra files/cache")
    for path, metadata in entries(source, HISTORICAL_COMMIT).items():
        verify_worktree_file(source, HISTORICAL_COMMIT, path, metadata)


def validate_suite(source, commit, tree):
    validate_source(source, commit, tree)
    validate_historical_objects(source)
    tracked = entries(source, commit)
    require({p for p in tracked if in_scope(p)} == set(CURRENT_PATHS),
            "current exact scoped inventory")
    # Include ignored files and symlink directories, which git status may omit.
    actual = set()
    cache = Path(source) / "tests/__pycache__"
    require(not cache.is_symlink() and (not cache.exists() or cache.is_dir()),
            "current test bytecode cache root")
    for directory in ("adapters/popover_outside_rust", "diagnostics/popover_outside", "tests"):
        root = Path(source) / directory
        require(root.is_dir() and not root.is_symlink(), "current source directory")
        for path in root.rglob("*"):
            relative = path.relative_to(source).as_posix()
            if in_scope(relative):
                mode = path.lstat().st_mode
                require(stat.S_ISREG(mode) or stat.S_ISDIR(mode), "current special file/symlink: " + relative)
                if stat.S_ISREG(mode):
                    actual.add(relative)
    workflow = ".github/workflows/popover-outside-diagnostic.yml"
    if (Path(source) / workflow).exists() or (Path(source) / workflow).is_symlink():
        actual.add(workflow)
    require(actual == set(CURRENT_PATHS), "current exact worktree inventory")
    for path in CURRENT_PATHS:
        verify_worktree_file(source, commit, path, tracked[path])
    require(safe_file(source, POLICY_PATH).read_bytes() == POLICY_BYTES,
            "current policy schema/content/hash")
    for path, expected in {**FROZEN, **LEGACY_SHA256}.items():
        require(digest(safe_file(source, path)) == expected, "current frozen source changed: " + path)
    return {"schema_version": 2, "policy": PROFILE,
            "suite": {"commit": commit, "tree": tree},
            "historical": {"commit": HISTORICAL_COMMIT, "tree": HISTORICAL_TREE},
            "execution_authenticated": False,
            "scope": "source integrity only; no runtime or parity claim"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite-source", type=Path, required=True)
    parser.add_argument("--suite-commit", required=True)
    parser.add_argument("--suite-tree", required=True)
    parser.add_argument("--historical-source", type=Path, required=True)
    args = parser.parse_args()
    validate_historical_checkout(args.historical_source)
    print(json.dumps(validate_suite(args.suite_source, args.suite_commit, args.suite_tree), indent=2))


if __name__ == "__main__":
    main()
