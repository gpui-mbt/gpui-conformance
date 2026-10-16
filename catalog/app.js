const STATUS_CLASSES = {
  pass: "status-pass",
  mismatch: "status-mismatch",
  difference: "status-difference",
  unsupported: "status-unsupported",
  unverified: "status-unverified",
};

function text(tag, value, className) {
  const node = document.createElement(tag);
  node.textContent = value ?? "";
  if (className) node.className = className;
  return node;
}

function link(label, href) {
  if (!href) return null;
  const node = document.createElement("a");
  node.textContent = label;
  node.href = href;
  node.rel = "noopener noreferrer";
  node.target = "_blank";
  return node;
}

function searchableText(item) {
  return [item.id, item.title, item.feature_title, item.category, item.layer, item.kind,
    item.source_path, item.source_description, item.description, ...(item.feature_tags ?? []), ...(item.source_features ?? [])]
    .filter(Boolean).join(" ").toLocaleLowerCase();
}

function featureCard(item) {
  const row = document.createElement("li");
  row.className = "example-card";
  row.dataset.implementation = item.implementation.status;
  row.dataset.search = searchableText(item);
  const article = document.createElement("article");
  article.setAttribute("aria-labelledby", `example-${item.id}`);

  const preview = document.createElement("figure");
  preview.className = "example-preview";
  if (item.thumbnail) {
    const image = document.createElement("img");
    image.src = item.thumbnail.url;
    image.alt = item.thumbnail.alt;
    image.width = item.thumbnail.width;
    image.height = item.thumbnail.height;
    image.loading = "lazy";
    image.decoding = "async";
    preview.append(image, text("figcaption", item.thumbnail.caption));
  } else {
    preview.classList.add("preview-unavailable");
    const missing = document.createElement("div");
    missing.append(text("p", "保存画像なし", "preview-label"));
    missing.append(text("p", item.implemented ? "この例の描画画像はまだ保存されていません" : "gpui.mbt 未実装", "preview-detail"));
    preview.append(missing, text("figcaption", "プレビューなし · 代わりの画像は表示していません"));
  }
  article.append(preview);

  const body = document.createElement("div");
  body.className = "example-body";
  body.append(text("p", item.id, "example-id"));
  const heading = text("h3", item.feature_title);
  heading.id = `example-${item.id}`;
  body.append(heading);
  const tags = document.createElement("ul");
  tags.className = "feature-tags";
  tags.setAttribute("aria-label", "上流ソースの機能");
  for (const tag of item.feature_tags) tags.append(text("li", tag));
  body.append(tags, text("p", item.source_description, "feature-description"));

  const implementation = text("p", item.implementation.label, "implementation-label");
  if (item.width && item.height) implementation.append(text("span", ` · ${item.width}×${item.height}`, "case-meta"));
  body.append(implementation);
  if (item.implementation.note) body.append(text("p", item.implementation.note, "small-note implementation-note"));
  const result = document.createElement("p");
  result.className = "example-result";
  result.append(text("span", `${item.evidence_available ? "保存結果 · " : ""}${item.status_label}`, `case-status ${STATUS_CLASSES[item.status] ?? ""}`));
  if (item.result_date) result.append(text("span", item.result_date, "evidence-date"));
  body.append(result, text("p", item.description, "evidence-note"));

  const sourceLinks = document.createElement("div");
  sourceLinks.className = "case-links";
  for (const node of [link("上流ソース", item.source_url), link("gpui.mbt 実装", item.implementation.source_url)]) {
    if (node) sourceLinks.append(node);
  }
  body.append(sourceLinks);
  const evidenceLinks = document.createElement("div");
  evidenceLinks.className = "case-links evidence-links";
  for (const node of [link("保存済み結果", item.result_url), link("元の保存画像", item.thumbnail?.source_url), link("gpui.rs の保存画像", item.thumbnail?.oracle_url), link("撮影記録", item.thumbnail?.provenance_url), link("ライブ比較を開く", item.comparison_url)]) {
    if (node) evidenceLinks.append(node);
  }
  body.append(evidenceLinks);
  if (item.implemented && !item.comparison_url) body.append(text("p", "ライブ比較 URL は未設定です。", "small-note"));
  article.append(body);
  row.append(article);
  return row;
}

function renderExamples(data) {
  const list = document.getElementById("example-list");
  // A previous Pages document may still request this loose compatibility script.
  // Keep its coverage table usable rather than crashing on newly added elements.
  if (!list || !data.browser_examples.every(item => item.implementation && item.feature_tags)) {
    showRefreshNotice("古いページまたはカタログ形式が残っています。機能カードには最新版を読み込んでください。");
    return;
  }
  const examples = [...data.browser_examples].sort((a, b) => Number(b.implemented) - Number(a.implemented));
  for (const item of examples) list.append(featureCard(item));
  document.getElementById("examples-summary").textContent = `${examples.length} examples · gpui.mbt 実装 ${data.browser.implemented_count} 件 · 保存済み比較 ${data.browser.evidence_count} 件`;
  const search = document.getElementById("example-search");
  const implementationFilter = document.getElementById("implementation-filter");
  const rows = [...list.children];
  const refresh = () => {
    const query = search.value.trim().toLocaleLowerCase();
    let visible = 0;
    for (const row of rows) {
      const matches = (!query || row.dataset.search.includes(query))
        && (!implementationFilter.value || row.dataset.implementation === implementationFilter.value);
      row.hidden = !matches;
      if (matches) visible += 1;
    }
    document.getElementById("example-count").textContent = `${visible} / ${rows.length} examples を表示`;
    document.getElementById("examples-empty").hidden = visible !== 0;
  };
  for (const control of [search, implementationFilter]) control.addEventListener("input", refresh);
  implementationFilter.addEventListener("change", refresh);
  const filters = document.getElementById("example-filters");
  filters.addEventListener("submit", event => event.preventDefault());
  filters.addEventListener("reset", () => setTimeout(refresh, 0));
  refresh();
}

function resultItem(item) {
  const row = document.createElement("li");
  row.className = "case-row";
  row.dataset.suite = item.suite_type;
  row.dataset.status = item.status;
  row.dataset.search = searchableText(item);

  const article = document.createElement("article");
  const heading = document.createElement("div");
  heading.className = "case-heading";
  heading.append(text("h3", item.id));
  if (item.title && item.title !== item.id) heading.append(text("p", item.title, "case-meta"));
  article.append(heading);

  const state = text("span", item.status_label, `case-status ${STATUS_CLASSES[item.status] ?? ""}`);
  article.append(state);

  const details = document.createElement("div");
  details.className = "case-meta";
  details.append(text("span", item.category || item.layer_label || item.suite_type, "case-category"));
  const detailBits = [item.kind, item.result_date ? `記録日 ${item.result_date}` : ""].filter(Boolean);
  if (detailBits.length) details.append(text("span", ` · ${detailBits.join(" · ")}`));
  article.append(details);

  const links = document.createElement("div");
  links.className = "case-links";
  const source = link("source", item.source_url);
  const evidence = link("result", item.result_url);
  const inventory = link("inventory", item.inventory_url);
  const comparison = link("ライブ比較", item.comparison_url);
  for (const node of [source, evidence, inventory, comparison]) if (node) links.append(node);
  article.append(links);

  let note = item.description;
  if (item.historical_status) {
    note = `現行 pin ${item.current_candidate_revision.slice(0, 8)} は未検証。旧 pin ${item.historical_candidate_revision.slice(0, 8)} の保存済み結果は ${item.historical_status}。`;
  }
  if (note) article.append(text("p", note, "case-note"));
  row.append(article);
  return row;
}

function renderPins(id, pins) {
  const host = document.getElementById(id);
  host.replaceChildren();
  for (const pin of pins ?? []) {
    const item = link(`${pin.label} · ${pin.revision.slice(0, 8)}`, pin.url);
    if (item) host.append(item);
  }
}

function setLink(id, label, href) {
  const node = document.getElementById(id);
  if (!href) {
    node.hidden = true;
    return;
  }
  node.href = href;
  node.textContent = label;
  node.rel = "noopener noreferrer";
  node.target = "_blank";
}

async function init() {
  const embedded = document.getElementById("catalog-data");
  let data;
  if (embedded) {
    data = JSON.parse(embedded.textContent);
  } else {
    // Compatibility for old cached documents and source-template development.
    const response = await fetch("./data.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`Catalog data could not be loaded (${response.status}).`);
    data = await response.json();
  }

  document.getElementById("scope-note").textContent = data.scope_note;
  renderExamples(data);
  document.getElementById("headless-metric").textContent = `${data.counts.pass} pass / ${data.headless.case_count} 件`;
  document.getElementById("headless-detail").textContent = `差分 ${data.counts.mismatch} · 未対応 ${data.counts.unsupported} · 未検証 ${data.counts.unverified}`;
  const headlessDate = document.getElementById("headless-date");
  headlessDate.textContent = `保存済み証拠の日付: ${data.headless.result_date} · `;
  headlessDate.append(link(`suite ${data.headless.suite_revision.slice(0, 8)}`, data.headless.suite_revision_url));
  renderPins("headless-pins", data.headless.pins);
  setLink("headless-result", "headless 結果 JSON", data.headless.result_url);

  document.getElementById("browser-metric").textContent = `${data.browser.changed_pixels} / ${data.browser.total_pixels} pixels different`;
  document.getElementById("browser-detail").textContent = `${data.browser.example_id} の実行 ${data.browser.execution} · pixel 差分 ${data.browser.changed_percent}% · native parity ${data.browser.native_conformance}`;
  document.getElementById("browser-date").textContent = `保存済み証拠の日付: ${data.browser.result_date} · 画像同一ではありません`;
  renderPins("browser-pins", data.browser.pins);
  setLink("browser-result", "browser 結果 JSON", data.browser.result_url);
  setLink("browser-details", "差分の内訳", data.browser.details_url);

  document.getElementById("native-detail").textContent = `ネイティブ ${data.native.case_count} cases は現行 pin で未検証。旧 pin ${data.native.historical_candidate_revision.slice(0, 8)} の保存結果は ${data.native.historical_counts.pass} pass。`;
  document.getElementById("native-date").textContent = `旧 run の保存日: ${data.native.result_date}`;
  renderPins("native-pins", [
    { label: "current candidate · unverified", revision: data.native.current_candidate_revision, url: data.native.current_candidate_url },
    { label: "historical run candidate", revision: data.native.historical_candidate_revision, url: data.native.historical_candidate_url },
  ]);
  setLink("native-result", "旧 pin の結果", data.native.result_url);
  setLink("ax-status", "AX status JSON", data.native_ax.status_url);
  setLink("ax-details", "AX investigation", data.native_ax.details_url);
  document.getElementById("native-metric").textContent = `Native: ${data.native.current_status} · AX: ${data.native_ax.status}`;
  document.getElementById("native-metric").className = `metric status-${data.native.current_status}`;

  setLink("repo-link", "GitHub repository", data.links.repository);
  setLink("scenario-link", "シナリオ JSON", data.links.scenario_sources);
  setLink("workflow-link", "CI workflow", data.links.workflow);
  setLink("tests-link", "Test source files", data.links.test_sources);
  setLink("browser-examples-link", "Browser example inventory", data.browser.examples_url);
  document.getElementById("catalog-revision").textContent = `Catalog source ${data.revision.slice(0, 12)}`;

  const headlessItems = data.cases.map(item => ({ ...item, suite_type: "headless" }));
  const nativeItems = data.native_cases.map(item => ({ ...item, suite_type: "native" }));
  const browserItems = data.browser_examples.map(item => ({
    ...item,
    suite_type: "browser",
    category: "Browser example",
    kind: item.implementation?.label ?? (item.implemented ? "gpui.mbt 実装あり" : "gpui.mbt 未実装"),
    // Per-example evidence is produced by the generator. Never borrow the
    // summary's hello_world result for another implemented port.
  }));
  const items = [...headlessItems, ...nativeItems, ...browserItems];
  const list = document.getElementById("case-list");
  const fragment = document.createDocumentFragment();
  for (const item of items) fragment.append(resultItem(item));
  list.append(fragment);

  document.getElementById("inventory-count").textContent = `${data.headless.case_count} headless scenarios · ${data.browser_examples.length} browser examples · ${data.native.case_count} native cases`;

  const search = document.getElementById("search");
  const suiteFilter = document.getElementById("suite-filter");
  const statusFilter = document.getElementById("status-filter");
  const rows = [...list.querySelectorAll(".case-row")];
  const count = document.getElementById("result-count");
  const empty = document.getElementById("empty-state");
  const refresh = () => {
    const query = search.value.trim().toLocaleLowerCase();
    const suite = suiteFilter.value;
    const status = statusFilter.value;
    let visible = 0;
    for (const row of rows) {
      const matches = (!query || row.dataset.search.includes(query))
        && (!suite || row.dataset.suite === suite)
        && (!status || row.dataset.status === status);
      row.hidden = !matches;
      if (matches) visible += 1;
    }
    count.textContent = `${visible} / ${rows.length} 件を表示`;
    empty.hidden = visible !== 0;
  };
  for (const control of [search, suiteFilter, statusFilter]) control.addEventListener("input", refresh);
  for (const control of [suiteFilter, statusFilter]) control.addEventListener("change", refresh);
  document.getElementById("filters").addEventListener("submit", event => event.preventDefault());
  document.getElementById("filters").addEventListener("reset", () => setTimeout(refresh, 0));
  refresh();
}

function showRefreshNotice(message) {
  const note = document.getElementById("scope-note");
  if (!note) return;
  note.textContent = message;
  note.append(" ", link("最新版を読み込む", `?catalog-refresh=${Date.now()}`));
}

init().catch(error => {
  showRefreshNotice(`カタログを読み込めませんでした: ${error.message}`);
  const count = document.getElementById("result-count");
  if (count) count.textContent = "テスト一覧を表示できません。上のリンクから再読み込みしてください。";
  const summary = document.getElementById("examples-summary");
  if (summary) summary.textContent = "example を表示できません。";
});
