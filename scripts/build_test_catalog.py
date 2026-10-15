#!/usr/bin/env python3
"""Generate the static Japanese test catalog from the repository's real inputs."""
from __future__ import annotations

import argparse
import json
import hashlib
import os
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "catalog"
REPOSITORY = "gpui-mbt/gpui-conformance"
REPO_URL = f"https://github.com/{REPOSITORY}"
SCENARIO_FILES = (
    "scenarios.json",
    "boundary_scenarios.json",
    "flex_wrap_scenarios.json",
    "fractional_grow_scenarios.json",
    "fractional_shrink_scenarios.json",
    "gap_budget_scenarios.json",
    "minmax_scenarios.json",
    "justify_between_scenarios.json",
)
NATIVE_SCENARIO_PATH = "native_scenarios.json"
NATIVE_RESULT_PATH = "results/native-merged-macos-arm64-20261014.json"
RESULT_PATH = "results/cross-axis-limits-linux-x86_64-20261015.json"
BROWSER_RESULT_PATH = "web/evidence/20261016/result.json"
AX_STATUS_PATH = "native_observer_status.json"

LAYER_LABELS = {
    "headless-layout": ("Headless · layout", "Layout", "固定配置、flex、wrap、min/max のレイアウト比較"),
    "headless-dispatch": ("Headless · input", "Input / event dispatch", "pointer・key・focus・route の配送比較"),
    "headless-scene": ("Headless · scene", "Scene", "描画シーンの構成比較"),
    "headless-clip": ("Headless · clip", "Clipping", "入れ子クリップの比較"),
    "native-window": ("Native · window", "Native window", "ネイティブウィンドウのライフサイクル"),
    "native-gpu": ("Native · GPU", "Native GPU", "ネイティブGPU出力の観測"),
    "native-ime": ("Native · IME", "Native IME", "IME合成入力"),
}
STATUS_LABELS = {
    "pass": "一致 · pass",
    "mismatch": "差分 · mismatch",
    "difference": "差分 · different",
    "unsupported": "未対応 · unsupported",
    "unverified": "未検証 · unverified",
}


def load_json(path: str) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def pixel_status(recorded_status: str | None) -> str:
    return {"equal": "pass", "different": "difference"}.get(recorded_status, "unverified")


def recorded_date(path: str) -> str:
    match = re.search(r"(20\d{6})", Path(path).name)
    if not match:
        match = re.search(r"(20\d{6})", path)
    if not match:
        return ""
    return datetime.strptime(match.group(1), "%Y%m%d").date().isoformat()


def source_url(revision: str, path: str, line: int | None = None) -> str:
    suffix = f"#L{line}" if line else ""
    return f"{REPO_URL}/blob/{revision}/{path}{suffix}"


def line_for_id(path: str, case_id: str) -> int | None:
    pattern = re.compile(r'^\s*"id"\s*:\s*"' + re.escape(case_id) + r'"\s*,?\s*$')
    for number, line in enumerate((ROOT / path).read_text(encoding="utf-8").splitlines(), start=1):
        if pattern.match(line):
            return number
    return None


def current_revision() -> str:
    explicit = os.environ.get("CATALOG_REVISION") or os.environ.get("GITHUB_SHA")
    if explicit:
        return explicit
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "main"


def build_catalog(revision: str | None = None) -> dict[str, Any]:
    revision = revision or current_revision()
    evidence = load_json(RESULT_PATH)
    positive = next(
        run for run in evidence["full_corpus_preservation_check"]["positive_and_negative_control_runs"]
        if run["name"] == "cross-axis-final-positive"
    )
    comparison = positive["comparison"]
    case_results = {item["id"]: item for item in comparison["cases"]}

    # Reconstruct the combined file in the same registry order used by the
    # recorded run. The digest prevents old results from being attached to
    # edited scenario inputs with unchanged IDs.
    combined_cases = []
    for path in SCENARIO_FILES:
        combined_cases.extend(load_json(path)["cases"])
    combined_bytes = (
        json.dumps({"schema_version": 1, "cases": combined_cases}, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")
    combined_sha = hashlib.sha256(combined_bytes).hexdigest()
    if combined_sha != positive.get("scenarios_sha256"):
        raise ValueError("current scenario registries do not match the retained run input digest")

    # The eight headless registries are distinct from native_scenarios.json.
    # Two generic native placeholders in scenarios.json share IDs with the
    # dedicated native cases but intentionally have different inputs.
    catalog_cases: dict[str, dict[str, Any]] = {}
    for path in SCENARIO_FILES:
        for case in load_json(path)["cases"]:
            case_id = case["id"]
            if case_id in catalog_cases:
                raise ValueError(f"duplicate ID among headless registries: {case_id}")
            catalog_cases[case_id] = {"case": case, "path": path}

    if set(catalog_cases) != set(case_results):
        missing = sorted(set(catalog_cases) - set(case_results))
        extra = sorted(set(case_results) - set(catalog_cases))
        raise ValueError(f"scenario/result IDs differ; missing results={missing}; extra results={extra}")

    result_source = source_url(revision, RESULT_PATH)
    cases: list[dict[str, Any]] = []
    by_layer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case_id, entry in catalog_cases.items():
        case = entry["case"]
        result = case_results[case_id]
        if case.get("layer") != result.get("layer"):
            raise ValueError(f"layer differs between scenario and result for {case_id}")
        path = entry["path"]
        line = line_for_id(path, case_id)
        layer, category, description = LAYER_LABELS.get(
            case.get("layer"), (case.get("layer", "other"), case.get("layer", "other"), "")
        )
        status = result["status"]
        item = {
            "id": case_id,
            "status": status,
            "status_label": STATUS_LABELS[status],
            "layer": case.get("layer", "other"),
            "layer_label": layer,
            "category": category,
            "kind": case.get("kind", "scenario"),
            "source_path": path,
            "source_url": source_url(revision, path, line),
            "result_url": result_source,
            "result_date": recorded_date(RESULT_PATH),
            "description": description,
            "interactive": False,
            "comparison_url": None,
            "suite_type": "headless",
        }
        cases.append(item)
        by_layer[item["layer"]].append(item)

    counts = Counter(item["status"] for item in cases)
    report_counts = comparison["summary"]
    for status in ("pass", "mismatch", "unsupported", "unverified"):
        if counts.get(status, 0) != report_counts.get(status, 0):
            raise ValueError(f"catalog {status} count does not match the retained comparison")

    # Native cases have a separate registry and a historical passing run. That
    # run used a different gpui.mbt revision from the current pin, so the current
    # catalog status remains unverified while preserving the older evidence.
    native_registry_bytes = (ROOT / NATIVE_SCENARIO_PATH).read_bytes()
    native_scenarios_sha = hashlib.sha256(native_registry_bytes).hexdigest()
    native_result = load_json(NATIVE_RESULT_PATH)
    native_positive = native_result["executions"]["native-merged-positive"]["comparison"]
    native_report_sha = native_positive.get("scenarios_sha256")
    native_statuses = {item["id"]: item["status"] for item in native_positive["cases"]}
    if native_report_sha != native_scenarios_sha:
        raise ValueError("native scenario inputs do not match the retained native evidence")
    current_candidate = load_json("pins.json")["moonbit"]["revision"]
    historical_candidate = native_result.get("moonbit_revision")
    native_cases = []
    for case in load_json(NATIVE_SCENARIO_PATH)["cases"]:
        case_id = case["id"]
        line = line_for_id(NATIVE_SCENARIO_PATH, case_id)
        native_cases.append({
            "id": case_id,
            "status": "unverified",
            "status_label": STATUS_LABELS["unverified"],
            "layer": case["layer"],
            "layer_label": LAYER_LABELS.get(case["layer"], (case["layer"],))[0],
            "category": LAYER_LABELS.get(case["layer"], (case["layer"], case["layer"]))[1],
            "kind": case.get("kind", "native scenario"),
            "source_path": NATIVE_SCENARIO_PATH,
            "source_url": source_url(revision, NATIVE_SCENARIO_PATH, line),
            "result_url": source_url(revision, NATIVE_RESULT_PATH),
            "result_date": recorded_date(NATIVE_RESULT_PATH),
            "description": "最新 pin に対するネイティブ実行は未確認。保存済みの旧 pin の結果は詳細リンク参照。",
            "interactive": False,
            "comparison_url": None,
            "suite_type": "native",
            "historical_status": native_statuses.get(case_id, "unverified"),
            "historical_candidate_revision": historical_candidate,
            "historical_candidate_url": f"https://github.com/gpui-mbt/gpui.mbt/commit/{historical_candidate}",
            "current_candidate_revision": current_candidate,
            "current_candidate_url": f"https://github.com/gpui-mbt/gpui.mbt/commit/{current_candidate}",
        })

    suites = []
    for layer, layer_cases in sorted(by_layer.items()):
        label, category, description = LAYER_LABELS.get(layer, (layer, layer, ""))
        suite_counts = Counter(item["status"] for item in layer_cases)
        suites.append({
            "id": layer,
            "title": label,
            "category": category,
            "description": description,
            "case_count": len(layer_cases),
            "counts": {status: suite_counts.get(status, 0) for status in ("pass", "mismatch", "unsupported", "unverified")},
        })

    browser = load_json(BROWSER_RESULT_PATH)
    current_pins = load_json("pins.json")
    browser_inventory = load_json("web/examples.json")
    raster = browser["raster_comparison"]
    browser_status = pixel_status(raster.get("status"))
    changed = raster["changed_pixels"]
    total = raster["total_pixels"]
    examples = browser_inventory
    upstream_revision = examples["upstream"]["revision"]
    browser_examples = []
    for example in examples["examples"]:
        implemented = example.get("moonbit") == "implemented"
        status = browser_status if implemented else "unsupported"
        browser_examples.append({
            "id": example["id"],
            "title": example["title"],
            "status": status,
            "status_label": STATUS_LABELS[status],
            "source_url": f"https://github.com/{examples['upstream']['repository']}/blob/{upstream_revision}/{example['source']}",
            "inventory_url": source_url(revision, "web/examples.json"),
            "implemented": implemented,
            "interactive": bool(example.get("interactive", False)),
            # No comparison page URL is assumed. A link is generated only when
            # a real interactive example and an implemented port both exist.
            "comparison_url": None,
            "suite_type": "browser",
        })

    native_ax = load_json(AX_STATUS_PATH)
    browser_run = {
        "status": browser_status,
        "status_label": STATUS_LABELS[browser_status],
        "execution": browser["overall"],
        "candidate": browser["candidate"],
        "rust": browser["rust"],
        "changed_pixels": changed,
        "total_pixels": total,
        "changed_percent": round(changed / total * 100, 4),
        "native_conformance": raster.get("native_conformance", "unverified"),
        "result_date": recorded_date(BROWSER_RESULT_PATH),
        "result_url": source_url(revision, BROWSER_RESULT_PATH),
        "details_url": source_url(revision, "web/PIXEL_ANALYSIS_20261016.md"),
        "examples_url": source_url(revision, "web/README.md"),
        "pins": [
            {"label": "gpui.rs · GPUI 0.2.2", "revision": browser_inventory["upstream"]["revision"], "url": f"https://github.com/{browser_inventory['upstream']['repository']}/commit/{browser_inventory['upstream']['revision']}"},
            {"label": "gpui.mbt", "revision": browser_inventory["moonbit"]["revision"], "url": f"https://github.com/{browser_inventory['moonbit']['repository']}/commit/{browser_inventory['moonbit']['revision']}"},
        ],
    }
    ax_status = native_ax.get("status", "unverified")
    ax_summary = {
        "status": ax_status,
        "status_label": STATUS_LABELS[ax_status],
        "scope": native_ax.get("scope", "Accessibility qualification"),
        "status_url": source_url(revision, AX_STATUS_PATH),
        "details_url": source_url(revision, "AX_COMPARISON_INVESTIGATION.md#status-and-evidence-boundary"),
    }

    return {
        "schema_version": 1,
        "title": "GPUI Conformance Test Catalog",
        "revision": revision,
        "generated_from": "registered scenario JSON, retained comparison JSON, browser example inventory, and native observer status",
        "scope_note": "記録済みの結果を一覧化したものです。表示日は保存済みファイル名の日付で、再実行日時や最新性は示しません。headless の一致はブラウザー描画やネイティブ動作の同等性を意味しません。",
        "registered_case_count": len(cases),
        "native_case_count": len(native_cases),
        "counts": {status: counts.get(status, 0) for status in ("pass", "mismatch", "unsupported", "unverified")},
        "headless": {
            "scope": evidence["scope"],
            "platform": "Linux x86_64",
            "result_date": recorded_date(RESULT_PATH),
            "suite_revision": evidence.get("suite_revision"),
            "upstream_revision": evidence.get("oracle_revision"),
            "candidate_revision": evidence.get("candidate_revision"),
            "scenario_sha256": combined_sha,
            "case_count": len(cases),
            "executed_headless_case_count": evidence["full_corpus_preservation_check"]["executed_headless_case_count"],
            "result_url": result_source,
            "suite_revision_url": f"{REPO_URL}/commit/{evidence.get('suite_revision')}",
            "pins": [
                {"label": "gpui.rs · GPUI 0.2.2", "revision": evidence.get("oracle_revision"), "url": f"https://github.com/zed-industries/zed/commit/{evidence.get('oracle_revision')}"},
                {"label": f"gpui.mbt · v{current_pins['moonbit']['version']}", "revision": evidence.get("candidate_revision"), "url": f"https://github.com/gpui-mbt/gpui.mbt/commit/{evidence.get('candidate_revision')}"},
            ],
        },
        "browser": browser_run,
        "native_ax": ax_summary,
        "native": {
            "current_status": "unverified",
            "case_count": len(native_cases),
            "result_date": recorded_date(NATIVE_RESULT_PATH),
            "historical_counts": native_positive["summary"],
            "historical_candidate_revision": historical_candidate,
            "historical_candidate_url": f"https://github.com/gpui-mbt/gpui.mbt/commit/{historical_candidate}",
            "current_candidate_revision": current_candidate,
            "current_candidate_url": f"https://github.com/gpui-mbt/gpui.mbt/commit/{current_candidate}",
            "result_url": source_url(revision, NATIVE_RESULT_PATH),
            "scenario_sha256": native_scenarios_sha,
        },
        "suites": suites,
        "cases": sorted(cases, key=lambda item: (item["layer"], item["id"])),
        "native_cases": native_cases,
        "browser_examples": browser_examples,
        "links": {
            "repository": REPO_URL,
            "scenario_sources": source_url(revision, "scenarios.json"),
            "workflow": source_url(revision, ".github/workflows/harness.yml"),
            "test_sources": f"{REPO_URL}/tree/{revision}/tests",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision", help="source revision used for GitHub links")
    args = parser.parse_args()
    SITE.mkdir(parents=True, exist_ok=True)
    target = SITE / "data.json"
    target.write_text(json.dumps(build_catalog(args.revision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {target.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
