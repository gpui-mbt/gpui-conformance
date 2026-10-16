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

function resultItem(item) {
  const row = document.createElement("li");
  row.className = "case-row";
  row.dataset.suite = item.suite_type;
  row.dataset.status = item.status;
  row.dataset.search = [item.id, item.title, item.category, item.layer, item.kind, item.source_path, item.description]
    .filter(Boolean).join(" ").toLocaleLowerCase();

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
  const response = await fetch("./data.json", { cache: "no-store" });
  if (!response.ok) throw new Error(`Catalog data could not be loaded (${response.status}).`);
  const data = await response.json();

  document.getElementById("scope-note").textContent = data.scope_note;
  document.getElementById("headless-metric").textContent = `${data.counts.pass} pass / ${data.headless.case_count} 件`;
  document.getElementById("headless-detail").textContent = `差分 ${data.counts.mismatch} · 未対応 ${data.counts.unsupported} · 未検証 ${data.counts.unverified}`;
  const headlessDate = document.getElementById("headless-date");
  headlessDate.textContent = `保存済み証拠の日付: ${data.headless.result_date} · `;
  headlessDate.append(link(`suite ${data.headless.suite_revision.slice(0, 8)}`, data.headless.suite_revision_url));
  renderPins("headless-pins", data.headless.pins);
  setLink("headless-result", "headless 結果 JSON", data.headless.result_url);

  document.getElementById("browser-metric").textContent = `${data.browser.changed_pixels} / ${data.browser.total_pixels} pixels different`;
  document.getElementById("browser-detail").textContent = `実行 ${data.browser.execution} · pixel 差分 ${data.browser.changed_percent}% · native parity ${data.browser.native_conformance}`;
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
    kind: item.implemented ? "matched browser example" : "unimplemented port",
    result_date: item.implemented ? data.browser.result_date : "",
    result_url: item.implemented ? data.browser.result_url : null,
    description: item.implemented ? "実際の Rust/WASM と MoonBit のペアで測定。静的 example であり、interactive ではありません。" : "Rust example の登録あり。MoonBit port は未実装です。",
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

init().catch(error => {
  const note = document.getElementById("scope-note");
  note.textContent = error.message;
  document.getElementById("result-count").textContent = "テスト一覧を表示できません。リポジトリの data.json を確認してください。";
});
