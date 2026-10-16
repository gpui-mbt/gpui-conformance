#!/usr/bin/env python3
"""Generate the static Japanese test catalog from the repository's real inputs."""
from __future__ import annotations

import argparse
import json
import hashlib
import os
import re
import shutil
import subprocess
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "catalog"
SITE_OUTPUT = ROOT / "_build" / "catalog"
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
TEXT_RESULT_PATH = "web/evidence/20261016-text-examples/result.json"
PRIME_RESULT_PATH = "web/evidence/20261016-prime-sieve/result.json"
# Retained measurements have their own immutable dependency provenance. New
# inventory pins describe today's build inputs, never a rewrite of these runs.
RETAINED_BROWSER_PINS = {
    "upstream": {"repository": "zed-industries/zed", "revision": "5a5fbe79917971a4d52a96b6ddb04da198a5012e"},
    "moonbit": {"repository": "gpui-mbt/gpui.mbt", "revision": "01818aa4e96fc21d1676f747a6b23d91445648a1"},
}
RETAINED_BROWSER_EXAMPLES = {
    BROWSER_RESULT_PATH: frozenset({"hello_world"}),
    TEXT_RESULT_PATH: frozenset({"text_layout", "text_wrapper"}),
    PRIME_RESULT_PATH: frozenset({"hello_web"}),
}
AX_STATUS_PATH = "native_observer_status.json"
BROWSER_LAB_BASE_URL_ENV = "CATALOG_BROWSER_LAB_BASE_URL"
BROWSER_LAB_WORKER_NAME = "gpui-conformance-browser-lab"
BROWSER_LAB_EXAMPLES = frozenset({"hello_world", "text", "text_layout", "text_wrapper", "input", "dynamic_fonts", "hello_web", "tree", "scrollable", "focus_visible"})
# This legacy result contains one raster comparison, for hello_world only.
# build.implemented describes build capability, never per-example evidence.
BROWSER_RESULT_EXAMPLE_ID = "hello_world"
BROWSER_THUMBNAIL_SOURCE = "web/evidence/20261016/moonbit.png"
BROWSER_THUMBNAIL_ASSET = "catalog/assets/hello_world-moonbit-20261016.png"
TEXT_CAPTURE_MANIFEST = "web/evidence/20261016-text-examples/captures.json"
PRIME_CAPTURE_MANIFEST = "web/evidence/20261016-prime-sieve/captures.json"
BROWSER_FEATURES = {
    "focus_visible": {
        "title": "入力方法に応じたフォーカス表示",
        "tags": ["focus-visible", "Tab 移動", "入力 modality", "focus ownership", "クリック・キー操作"],
        "description": "800×600 の上流例。3 個のボタンで .focus() と .focus_visible() の境界線、Tab・Shift-Tab による移動、マウスとキーボードの操作を扱います。",
    },
    "scrollable": {
        "title": "入れ子のスクロールとクリップ",
        "tags": ["縦横スクロール", "wheel 配送", "クリップ", "hit testing", "hover"],
        "description": "500×500 の上流例。入れ子の縦横スクロール領域、同じ wheel 差分の祖先への伝播、クリップと hover 再描画を扱います。",
    },
    "tree": {
        "title": "深い入れ子のレイアウト",
        "tags": ["51 階層", "内在サイズ", "padding", "描画順"],
        "description": "上流の既定 depth=50。51 個の色付きブロックを 2px の余白で入れ子にする 300×300 の静的な例です。",
    },
    "hello_world": {
        "title": "基本レイアウトと描画",
        "tags": ["Flex 配置", "色", "角丸・破線", "テキスト"],
        "implementation_note": "角丸・破線・影の描画は Canvas host の拡張です。保存結果はこの構成での比較です。",
        "description": "中央寄せの挨拶と 6 色の四角。gap、角丸、破線の境界を含む静的な例です。",
    },
    "text_layout": {
        "title": "文字の整列と装飾",
        "tags": ["テキスト", "左・中央・右寄せ", "下線・取消線", "nowrap", "太字・斜体"],
        "implementation_note": "gpui.mbt の layout と SceneSnapshot を使用。文字スタイル・装飾は Canvas host の拡張で、描画一致は未検証です。",
        "description": "800×600 の静的な例。文字の整列、下線、取消線、折り返さない文字列、太字と斜体を扱います。",
    },
    "text": {
        "title": "文字スタイルと行間",
        "tags": ["テキスト", "文字サイズ", "行間", "フォント切替"],
        "description": "文字サイズ、行間、type scale を組み合わせた上流の文字スタイル例です。",
    },
    "text_wrapper": {
        "title": "折り返しと省略表示",
        "tags": ["テキスト", "折り返し", "省略記号", "行数制限", "多言語"],
        "implementation_note": "測定済み文字幅を入力に example 内の MoonBit コードで折り返し・省略を計算し、gpui.mbt の layout と SceneSnapshot を使用。フォント測定と書記素分割は host 境界で、Unicode・描画の完全一致は未検証です。",
        "description": "長い単語、URL、日本語・中国語を含む文章の折り返しと省略を扱う上流の例です。",
    },
    "input": {
        "title": "文字入力と選択",
        "tags": ["入力", "選択", "クリップボード", "IME"],
        "description": "編集、文字選択、コピー・貼り付け、合成入力を扱う上流のテキスト入力例です。",
    },
    "dynamic_fonts": {
        "title": "動的フォント読み込み",
        "tags": ["フォント", "多言語", "非同期読み込み"],
        "description": "不足グリフを検知し、Devanagari フォントをダウンロードして再描画する上流の例です。",
        "implementation_note": "MoonBit レイアウトと SceneSnapshot の実装。ブラウザで Devanagari 文字を検知して一度だけフォントを読み込みます。GPUI 欠落グリフ通知と Cosmic Text・描画一致は未検証です。",
    },
    "hello_web": {
        "title": "バックグラウンド計算",
        "tags": ["非同期処理", "素数計算", "操作 UI"],
        "description": "10M・50M・100M の範囲を選び、12 分割の素数計算と進捗・履歴を表示する上流の例です。",
        "implementation_note": "MoonBit の実計算を Web Worker で実行し、gpui.mbt の layout・pointer dispatch・SceneSnapshot を使用。10M の操作試験は CI artifact に保存。描画一致・性能同等性・50M/100M の完走は未検証です。",
    },
}

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


def validate_browser_inventory(
    browser: dict[str, Any], inventory: dict[str, Any], result_path: str = BROWSER_RESULT_PATH,
) -> None:
    """Validate historical pins independently from current build declarations.

    A valid new inventory revision is allowed, but cannot relabel a retained
    measurement. Repository identity, exact retained pins and measured ports
    remain strict for each known report.
    """
    if result_path not in RETAINED_BROWSER_EXAMPLES:
        raise ValueError("unknown retained browser report provenance")
    build = browser["build"]
    for key in ("upstream", "moonbit"):
        recorded = build.get(key, {})
        declared = inventory.get(key, {})
        expected = RETAINED_BROWSER_PINS[key]
        if any(recorded.get(field) != expected[field] for field in ("repository", "revision")):
            raise ValueError(f"retained browser {key} pin differs from its historical provenance")
        if declared.get("repository") != expected["repository"] or not re.fullmatch(r"[0-9a-f]{40}", str(declared.get("revision", ""))):
            raise ValueError(f"current browser {key} pin must declare the expected repository and an exact revision")

    if not re.fullmatch(r"[0-9a-f]{40}", str(inventory.get("moonbit", {}).get("tree", ""))):
        raise ValueError("current browser moonbit tree pin must declare an exact tree")

    recorded_implemented = set(build.get("implemented", []))
    declared_implemented = {
        example["id"] for example in inventory.get("examples", [])
        if example.get("moonbit") == "implemented"
    }
    if not recorded_implemented.issubset(declared_implemented):
        raise ValueError("implemented browser examples from the retained result are missing in the inventory")
    ids = [example["id"] for example in inventory.get("examples", [])]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate browser example IDs in the inventory")
    if not RETAINED_BROWSER_EXAMPLES[result_path].issubset(recorded_implemented):
        raise ValueError("retained browser evidence is missing its measured implemented examples")


def browser_pin_links(pins: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"label": label, "revision": pins[key]["revision"],
         **({"tree": pins[key]["tree"]} if "tree" in pins[key] else {}),
         "url": f"https://github.com/{pins[key]['repository']}/commit/{pins[key]['revision']}"}
        for key, label in (("upstream", "gpui.rs · GPUI 0.2.2"), ("moonbit", "gpui.mbt"))
    ]


def browser_evidence_provenance(browser: dict[str, Any], inventory: dict[str, Any]) -> dict[str, Any]:
    """Expose measured dependency pins without treating them as current evidence."""
    return {
        "pins": browser_pin_links(browser["build"]),
        "pins_match_current_inventory": all(
            browser["build"][key]["revision"] == inventory[key]["revision"]
            for key in ("upstream", "moonbit")
        ),
    }


def saved_text_previews(inventory: dict[str, Any], revision: str) -> dict[str, dict[str, Any]]:
    """Validate byte-exact captures independently of the hello_world pixel result."""
    manifest = load_json(TEXT_CAPTURE_MANIFEST)
    result_path = TEXT_RESULT_PATH
    if manifest["result_path"] != result_path or hashlib.sha256((ROOT / result_path).read_bytes()).hexdigest() != manifest["result_sha256"]:
        raise ValueError("saved text capture report digest mismatch")
    report = load_json(result_path)
    validate_browser_inventory(report, inventory, result_path)
    run = manifest["source_run"]
    if report["build"]["lab_revision"] != run["build_revision"] or report["build"]["lab_tracked_dirty"]:
        raise ValueError("saved text capture build provenance mismatch")
    if any(report[key] != "passed" for key in ("overall", "candidate", "rust")) or report["errors"]:
        raise ValueError("saved text captures require successful paired execution")
    previews = {}
    for entry in manifest["examples"]:
        example_id = entry["id"]
        if example_id not in {"text_layout", "text_wrapper"} or example_id in previews:
            raise ValueError("unknown or duplicate saved text capture")
        for side in ("moonbit", "rust"):
            capture = entry[side]
            expected = f"web/evidence/20261016-text-examples/{example_id.replace('_', '-')}-{side}.png"
            if capture["path"] != expected:
                raise ValueError("saved text capture path mismatch")
            pixels = (ROOT / expected).read_bytes()
            size = tuple(int.from_bytes(pixels[i:i + 4], "big") for i in (16, 20))
            clip = report["captures"][f"{example_id}_{side}"]["clip"]
            if pixels[:8] != b"\x89PNG\r\n\x1a\n" or pixels[12:16] != b"IHDR" or size != (800, 600) or size != (capture["width"], capture["height"]) or size != (clip["width"], clip["height"]):
                raise ValueError("saved text capture dimensions mismatch")
            if hashlib.sha256(pixels).hexdigest() != capture["sha256"]:
                raise ValueError("saved text capture digest mismatch")
        asset = f"catalog/assets/{example_id}-moonbit-20261016.png"
        if entry["asset_path"] != asset or (ROOT / asset).read_bytes() != (ROOT / entry["moonbit"]["path"]).read_bytes():
            raise ValueError("saved text preview must equal its retained capture")
        previews[example_id] = {
            **browser_evidence_provenance(report, inventory),
            "url": f"./assets/{example_id}-moonbit-20261016.png",
            "source_url": source_url(revision, entry["moonbit"]["path"]),
            "oracle_url": source_url(revision, entry["rust"]["path"]),
            "provenance_url": source_url(revision, TEXT_CAPTURE_MANIFEST),
            "capture_run_url": run["url"],
            "capture_revision": run["head_revision"],
            "capture_source_url": source_url(run["head_revision"], entry["candidate_source"]),
            "capture_report_url": source_url(revision, result_path),
            "sha256": entry["moonbit"]["sha256"],
            "alt": f"保存済み {example_id} の gpui.mbt 実描画。文字の配置と装飾。" if example_id == "text_layout" else "保存済み text_wrapper の gpui.mbt 実描画。多言語の折り返し、省略記号、行数制限。",
            "caption": f"gpui.mbt の保存画像 · {manifest['captured_date']} · 800×600 · {run['head_revision'][:8]}",
            "width": 800, "height": 600,
        }
    return previews


def saved_prime_preview(inventory: dict[str, Any], revision: str) -> dict[str, dict[str, Any]]:
    """Validate the actual paired 10M capture without assigning a pixel score."""
    root = "web/evidence/20261016-prime-sieve"
    manifest = load_json(PRIME_CAPTURE_MANIFEST)
    for name, expected in (("result", f"{root}/result.json"),
                           ("scene", f"{root}/prime-sieve-moonbit-scene.json"),
                           ("ocr", f"{root}/prime-sieve-rust-ocr.txt")):
        if manifest[f"{name}_path"] != expected or hashlib.sha256((ROOT / expected).read_bytes()).hexdigest() != manifest[f"{name}_sha256"]:
            raise ValueError("saved Prime report digest/path mismatch")
    report = load_json(manifest["result_path"])
    validate_browser_inventory(report, inventory, PRIME_RESULT_PATH)
    run = manifest["source_run"]
    if report["build"]["lab_revision"] != run["build_revision"] or report["build"]["lab_tracked_dirty"]:
        raise ValueError("saved Prime build provenance mismatch")
    if any(report[key] != "passed" for key in ("overall", "candidate", "rust")) or report["errors"]:
        raise ValueError("saved Prime capture requires successful paired execution")
    if run["url"] != f"{REPO_URL}/actions/runs/{run['id']}" or not re.fullmatch(r"[0-9a-f]{40}", run["head_revision"]):
        raise ValueError("saved Prime source run mismatch")
    scene = load_json(manifest["scene_path"])
    state, workers = scene["content"], scene["workers"]
    chunks = sorted(workers["completed"], key=lambda chunk: chunk["index"])
    if (scene["metadata"]["id"] != "hello_web" or state["total"] != 664579 or state["chunks_done"] != 12
            or state["running"] or state["failed"] or workers["active"] != 0
            or workers["created"] != workers["terminated"] or workers["failures"]
            or [chunk["index"] for chunk in chunks] != list(range(12))
            or chunks[0]["start"] != 0 or chunks[-1]["end"] != 10000000
            or any(left["end"] != right["start"] for left, right in zip(chunks, chunks[1:]))
            or sum(chunk["count"] for chunk in chunks) != 664579):
        raise ValueError("saved Prime computation evidence mismatch")
    if not re.search(r"Found\s+664,579\s+primes\s+below\s+10,000,000", (ROOT / manifest["ocr_path"]).read_text()):
        raise ValueError("saved Prime upstream rendered count mismatch")
    entry = manifest["example"]
    if entry["id"] != "hello_web" or entry["candidate_source"] != "web/moonbit/hello_web/hello_web.mbt":
        raise ValueError("saved Prime example/source mismatch")
    for side in ("moonbit", "rust"):
        capture = entry[side]
        expected = f"{root}/prime-sieve-{side}-result.png"
        if capture["path"] != expected:
            raise ValueError("saved Prime capture path mismatch")
        pixels = (ROOT / expected).read_bytes()
        size = tuple(int.from_bytes(pixels[i:i + 4], "big") for i in (16, 20))
        clip = report["captures"][f"hello_web_{side}_result"]["clip"]
        if (pixels[:8] != b"\x89PNG\r\n\x1a\n" or pixels[12:16] != b"IHDR" or size != (640, 560)
                or size != (capture["width"], capture["height"]) or size != (clip["width"], clip["height"])):
            raise ValueError("saved Prime capture dimensions mismatch")
        if hashlib.sha256(pixels).hexdigest() != capture["sha256"]:
            raise ValueError("saved Prime capture digest mismatch")
    asset = "catalog/assets/hello_web-moonbit-20261016.png"
    if entry["asset_path"] != asset or (ROOT / asset).read_bytes() != (ROOT / entry["moonbit"]["path"]).read_bytes():
        raise ValueError("saved Prime preview must equal its retained capture")
    return {"hello_web": {
        **browser_evidence_provenance(report, inventory),
        "url": "./assets/hello_web-moonbit-20261016.png",
        "source_url": source_url(revision, entry["moonbit"]["path"]),
        "oracle_url": source_url(revision, entry["rust"]["path"]),
        "provenance_url": source_url(revision, PRIME_CAPTURE_MANIFEST),
        "capture_run_url": run["url"], "capture_revision": run["head_revision"],
        "capture_source_url": source_url(run["head_revision"], entry["candidate_source"]),
        "capture_report_url": source_url(revision, PRIME_RESULT_PATH),
        "sha256": entry["moonbit"]["sha256"],
        "alt": "保存済み Prime sieve の gpui.mbt 実描画。10M の実計算で 664,579 個の素数、12 分割の進捗と履歴。",
        "caption": f"gpui.mbt の CI 実計算 · {manifest['captured_date']} · 640×560 · 経過時間は性能比較ではありません",
        "width": 640, "height": 560,
    }}


def normalize_browser_lab_base_url(value: Any) -> str | None:
    """Accept only an explicit HTTPS root URL for this worker; unset stays disabled."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{BROWSER_LAB_BASE_URL_ENV} must be a string URL")

    candidate = value.strip()
    if not candidate:
        return None
    if any(char.isspace() or ord(char) < 0x20 for char in candidate):
        raise ValueError(f"{BROWSER_LAB_BASE_URL_ENV} must not contain whitespace or control characters")
    if "?" in candidate or "#" in candidate:
        raise ValueError(f"{BROWSER_LAB_BASE_URL_ENV} must be a root URL without query or fragment")

    try:
        parsed = urlsplit(candidate)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as error:
        raise ValueError(f"{BROWSER_LAB_BASE_URL_ENV} is not a valid URL") from error

    if parsed.scheme.lower() != "https" or not hostname:
        raise ValueError(f"{BROWSER_LAB_BASE_URL_ENV} must use HTTPS")
    if parsed.username is not None or parsed.password is not None or port is not None:
        raise ValueError(f"{BROWSER_LAB_BASE_URL_ENV} must not contain credentials or a port")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError(f"{BROWSER_LAB_BASE_URL_ENV} must be the worker root without a path, query, or fragment")

    labels = hostname.lower().split(".")
    account_label = labels[1] if len(labels) == 4 else ""
    if (
        len(labels) != 4
        or labels[0] != BROWSER_LAB_WORKER_NAME
        or labels[2:] != ["workers", "dev"]
        or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", account_label)
    ):
        raise ValueError(
            f"{BROWSER_LAB_BASE_URL_ENV} must match "
            f"https://{BROWSER_LAB_WORKER_NAME}.<account>.workers.dev root URL"
        )
    return f"https://{hostname.lower()}"


def browser_lab_comparison_url(example_id: str, implemented: bool, base_url: str | None) -> str | None:
    """Link only declared ports supported by the lab, with an opt-in host URL."""
    if example_id not in BROWSER_LAB_EXAMPLES or not implemented:
        return None
    normalized_base_url = normalize_browser_lab_base_url(base_url)
    if normalized_base_url is None:
        return None
    return f"{normalized_base_url}/?example={example_id}"


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
    validate_browser_inventory(browser, browser_inventory)
    text_previews = saved_text_previews(browser_inventory, revision)
    text_previews.update(saved_prime_preview(browser_inventory, revision))
    browser_lab_base_url = normalize_browser_lab_base_url(os.environ.get(BROWSER_LAB_BASE_URL_ENV))
    raster = browser["raster_comparison"]
    browser_status = pixel_status(raster.get("status"))
    changed = raster["changed_pixels"]
    total = raster["total_pixels"]
    examples = browser_inventory
    upstream_revision = browser_inventory["upstream"]["revision"]
    # Preserve the saved image bytes exactly; the catalog only scales its display.
    thumbnail_sha = raster.get("sha256", {}).get("moonbit.png")
    for path in (BROWSER_THUMBNAIL_SOURCE, BROWSER_THUMBNAIL_ASSET):
        if not thumbnail_sha or hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != thumbnail_sha:
            raise ValueError(f"browser thumbnail does not match the retained screenshot digest: {path}")
    browser_examples = []
    for example in examples["examples"]:
        example_id = example["id"]
        implemented = example.get("moonbit") == "implemented"
        has_evidence = example_id == BROWSER_RESULT_EXAMPLE_ID
        status = browser_status if has_evidence else ("unverified" if implemented else "unsupported")
        features = BROWSER_FEATURES.get(example_id, {
            "title": example["title"], "tags": [], "description": "上流に登録された example です。",
        })
        implementation_path = example.get("candidate_source", f"web/moonbit/{example_id}/{example_id}.mbt") if implemented else None
        result_url = source_url(revision, BROWSER_RESULT_PATH) if has_evidence else None
        if has_evidence:
            evidence_note = f"撮影時 pin の hello_world 比較では実行 {browser['overall']}、画像は {STATUS_LABELS[browser_status]}。現行ソースや他の例の検証結果ではありません。"
        elif example_id in text_previews:
            evidence_note = "gpui.mbt の CI 保存画像あり。撮影時のソースと gpui.rs の画像も参照できます。画像はプレビューであり、pixel 差分・native parity は未検証です。"
        elif implemented:
            evidence_note = "gpui.mbt の実装あり。この例の保存済み比較結果・画像はなく、描画の一致は未検証です。"
        else:
            evidence_note = "gpui.mbt 未実装。タグと説明は上流ソースの機能を示し、検証済みの機能を示すものではありません。"
        browser_examples.append({
            "id": example_id,
            "title": example["title"],
            "feature_title": features["title"],
            "feature_tags": features["tags"],
            "source_features": example.get("features", []),
            "source_description": features["description"],
            "description": evidence_note,
            "status": status,
            "status_label": STATUS_LABELS[status],
            "source_path": example["source"],
            "source_url": f"https://github.com/{examples['upstream']['repository']}/blob/{upstream_revision}/{example['source']}",
            "source_revision": upstream_revision,
            "inventory_url": source_url(revision, "web/examples.json"),
            "implemented": implemented,
            "implementation": {
                "status": "implemented" if implemented else "not_implemented",
                "label": "gpui.mbt 実装あり" if implemented else "gpui.mbt 未実装",
                "source_url": source_url(revision, implementation_path) if implementation_path else None,
                "note": features.get("implementation_note", example.get("implementation_note")) if implemented else None,
            },
            "interactive": bool(example.get("interactive", False)),
            "width": example.get("width"),
            "height": example.get("height"),
            "evidence_available": has_evidence,
            "evidence_scope": "retained" if has_evidence else None,
            "result_url": result_url,
            "result_date": recorded_date(BROWSER_RESULT_PATH) if has_evidence else None,
            "execution": browser["overall"] if has_evidence else "unverified",
            "changed_pixels": changed if has_evidence else None,
            "total_pixels": total if has_evidence else None,
            "thumbnail": {
                **browser_evidence_provenance(browser, browser_inventory),
                "url": "./assets/hello_world-moonbit-20261016.png",
                "source_url": source_url(revision, BROWSER_THUMBNAIL_SOURCE),
                "sha256": thumbnail_sha,
                "alt": "保存済み hello_world の gpui.mbt 実描画。灰色の背景、挨拶と 6 色の四角。",
                "caption": "gpui.mbt の保存画像 · 2026-10-16 · 500×500",
                "width": raster["width"],
                "height": raster["height"],
            } if has_evidence else text_previews.get(example_id),
            "comparison_url": browser_lab_comparison_url(example_id, implemented, browser_lab_base_url),
            "suite_type": "browser",
        })

    native_ax = load_json(AX_STATUS_PATH)
    browser_run = {
        "example_id": BROWSER_RESULT_EXAMPLE_ID,
        "implemented_count": sum(example["implemented"] for example in browser_examples),
        "evidence_count": sum(example["evidence_available"] for example in browser_examples),
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
        **browser_evidence_provenance(browser, browser_inventory),
        "current_pins": browser_pin_links(browser_inventory),
        "inventory_url": source_url(revision, "web/examples.json"),
        "current_status": "unverified",
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
        "scope_note": "上流 example、gpui.mbt の実装状況、保存済みの比較結果をまとめたカタログです。表示日は保存済みファイル名の日付で、再実行日時や最新性は示しません。headless の一致はブラウザー描画やネイティブ動作の同等性を意味しません。",
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


def write_site(data: dict[str, Any], output: Path = SITE_OUTPUT) -> None:
    """Ship one coherent document, even when Pages caches different URLs separately.

    The loose assets remain for older cached documents and machine consumers.
    New documents never fetch those assets to initialize the catalog.
    """
    if output.resolve() == SITE.resolve() or SITE.resolve() in output.resolve().parents:
        raise ValueError("Catalog output must not overwrite the source templates")
    template = (SITE / "index.html").read_text(encoding="utf-8")
    script = (SITE / "app.js").read_text(encoding="utf-8")
    style = (SITE / "style.css").read_text(encoding="utf-8")
    # These are trusted source files, but do not silently introduce an HTML end tag.
    if re.search(r"</script", script, re.IGNORECASE) or re.search(r"</style", style, re.IGNORECASE):
        raise ValueError("Inline catalog source contains an HTML closing tag")
    serialized = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    # JSON is inert, but a literal </script> would still terminate its HTML element.
    embedded = serialized.replace("<", "\\u003c")
    style_ref = '<link rel="stylesheet" href="./style.css">'
    script_ref = '<script type="module" src="./app.js"></script>'
    if template.count(style_ref) != 1 or template.count(script_ref) != 1:
        raise ValueError("Catalog template must contain exactly one stylesheet and module reference")
    release = hashlib.sha256((template + script + style + serialized).encode()).hexdigest()
    html = template.replace(style_ref, f'<meta name="catalog-release" content="{release}">\n  <style>{style}</style>')
    html = html.replace(script_ref, f'<script id="catalog-data" type="application/json">{embedded}</script>\n  <script type="module">{script}</script>')
    output.mkdir(parents=True, exist_ok=True)
    (output / "index.html").write_text(html, encoding="utf-8")
    (output / "data.json").write_text(serialized, encoding="utf-8")
    for name in ("app.js", "style.css"):
        shutil.copyfile(SITE / name, output / name)
    shutil.copytree(SITE / "assets", output / "assets", dirs_exist_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision", help="source revision used for GitHub links")
    parser.add_argument("--output", type=Path, default=SITE_OUTPUT, help="generated site directory (default: _build/catalog)")
    args = parser.parse_args()
    write_site(build_catalog(args.revision), args.output)
    print(f"wrote coherent catalog to {args.output}")


if __name__ == "__main__":
    main()
