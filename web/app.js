// Keep runtime URLs explicit: a successful iframe load is not evidence of behavior parity.
const $ = (id) => document.getElementById(id);
const params = new URLSearchParams(location.search);
const defaults = {
  rust: params.get("rust") || "",
  moon: params.get("moon") || "https://gpui-mbt.github.io/gpui.mbt/",
};
const safeHttpUrl = (input) => {
  if (!input.trim()) return "";
  try {
    const url = new URL(input.trim());
    return ["https:", "http:"].includes(url.protocol) ? url.href : "";
  } catch {
    return "";
  }
};
$("rust-url").value = defaults.rust;
$("moon-url").value = defaults.moon;
function loadFrame(side, url) {
  const frame = $(side + "-frame");
  const empty = $(side + "-empty");
  frame.removeAttribute("src");
  const validated = safeHttpUrl(url);
  frame.style.display = validated ? "block" : "none";
  empty.hidden = Boolean(validated);
  if (validated) frame.src = validated;
  return validated;
}
function loadBoth() {
  const rustInput = $("rust-url").value;
  const moonInput = $("moon-url").value;
  const rust = loadFrame("rust", rustInput);
  const moon = loadFrame("moon", moonInput);
  const query = new URLSearchParams();
  if (rust) query.set("rust", rust);
  if (moon) query.set("moon", moon);
  const next = query.toString() ? "?" + query.toString() : location.pathname;
  history.replaceState(null, "", next);
  $("notice").textContent = (!rust && rustInput.trim()) || (!moon && moonInput.trim())
    ? "Invalid URL: use only http:// or https://."
    : rust && moon
      ? "Both iframe URLs requested. Loading or embedding success does NOT indicate fixture parity."
      : "One or both runtimes are missing. Configure both URLs before comparing.";
}
$("settings").addEventListener("submit", (event) => {
  event.preventDefault();
  if ($("fixture").value !== "preview") {
    $("notice").textContent = "Shared fixture not implemented. Choose the existing demo preview; no conformance result is available.";
    return;
  }
  loadBoth();
});
$("reload").addEventListener("click", () => {
  if ($("fixture").value !== "preview") {
    $("notice").textContent = "Shared fixture not implemented.";
    return;
  }
  loadBoth();
});
$("fixture").addEventListener("change", () => {
  const experimental = $("fixture").value !== "preview";
  $("notice").textContent = experimental
    ? "UNIMPLEMENTED: identical fixture UI and controlled inputs must be added to both runtimes."
    : "Existing demos preview different applications; this is not a conformance test.";
});
