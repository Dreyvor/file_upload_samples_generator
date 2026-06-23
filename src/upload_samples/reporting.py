from __future__ import annotations

import html
import json
import sqlite3
from collections import Counter, defaultdict
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .manifest import load_manifest
from .models import GeneratorConfig
from .utils import ensure_within, to_json, utc_now, write_text


DEFAULT_SESSION_METADATA = {
    "tester_name": "",
    "target_name": "",
    "test_window": "",
    "base_url": "",
    "field_name": "",
    "overall_assessment": "",
}

CATEGORY_EXPLANATIONS = {
    "baseline": "Baseline samples are small valid files for each allowed extension. Use them to confirm the happy-path behavior, preview generation, download headers, storage naming, OCR, and metadata handling before moving to adversarial cases.",
    "mismatch": "Mismatch samples intentionally keep one allowed filename extension while embedding a different allowed content family. They help reveal whether the application validates extension and content independently instead of enforcing a strict mapping.",
    "minimal-headers": "Minimal-header samples contain only the magic bytes or signature prefix required to trigger superficial type checks. They help distinguish weak header-only validation from real parser validation.",
    "malformed": "Malformed samples start from valid or signature-looking content and then break structural integrity through truncation or bounded random tails. They help detect whether downstream components fail safely when parser validation is incomplete.",
    "metadata": "Metadata samples embed unique marker values or benign reflection probes in fields that may later appear in the UI, logs, OCR, indexing, or exports. They help identify metadata reflection and sanitization issues.",
    "filenames": "Filename recipes document risky multipart filenames that should be tested manually without creating dangerous local paths. They help assess normalization, reflection, traversal, reserved names, and shell-sensitive handling.",
    "multipart-recipes": "Multipart recipes vary the declared Content-Type and related request headers without changing the sample bytes. They help determine which layer trusts multipart metadata and whether different components disagree on routing.",
    "stress-bounded": "Bounded stress samples stay within defined safety limits while still exercising large dimensions, repeated metadata, or heavier parsing paths. They help reveal safe resource-handling weaknesses without becoming denial-of-service payloads.",
    "pdf-structures": "PDF structure samples include benign document features such as form-like objects or embedded text markers. They help identify how the upload pipeline treats richer PDF structures without relying on active content.",
    "polyglots": "Polyglot samples are optional composite files intended to exercise parser disagreement across multiple formats. They help detect whether validators, thumbnailers, renderers, or download handlers interpret the same bytes differently.",
}

TEST_RESULT_FIELDS = (
    "test_status",
    "validation_message",
    "stored_filename",
    "stored_extension",
    "displayed_type",
    "detected_mime_ui",
    "preview_generated",
    "ocr_extracted",
    "metadata_reflected",
    "download_content_type",
    "download_content_disposition",
    "download_x_content_type_options",
    "download_cache_control",
    "download_csp",
    "bytes_preserved",
    "processing_time_notes",
    "tester_notes",
    "finding_title",
    "finding_severity",
    "finding_summary",
    "recommendation",
    "evidence_paths",
    "last_updated_at",
)

ALLOWED_TEST_STATUSES = (
    "untested",
    "accepted",
    "rejected",
    "error",
    "needs-review",
    "interesting",
)


INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Upload Samples Reporting</title>
  <link rel="stylesheet" href="/ui/app.css">
</head>
<body>
  <header class="page-header">
    <div>
      <h1>Upload Samples Reporting</h1>
      <p id="session-summary">Loading session...</p>
    </div>
    <div class="status-pill" id="save-status">Ready</div>
  </header>
  <section class="toolbar">
    <label>Category
      <select id="filter-category">
        <option value="">All</option>
      </select>
    </label>
    <label>Family
      <select id="filter-family">
        <option value="">All</option>
      </select>
    </label>
    <label>Extension
      <select id="filter-extension">
        <option value="">All</option>
      </select>
    </label>
    <label>Status
      <select id="filter-status">
        <option value="">All</option>
      </select>
    </label>
    <label class="checkbox">
      <input type="checkbox" id="filter-findings">
      Findings only
    </label>
    <label class="checkbox">
      <input type="checkbox" id="filter-incomplete" checked>
      Resume incomplete
    </label>
    <button id="export-report" type="button">Export report</button>
  </section>
  <section class="metadata-panel">
    <h2>Session metadata</h2>
    <div class="metadata-grid" id="metadata-fields"></div>
  </section>
  <section class="metadata-panel">
    <h2>Test explanations</h2>
    <div id="category-explanations"></div>
  </section>
  <section class="results-panel">
    <h2>Test matrix</h2>
    <div class="table-wrapper">
      <table>
        <colgroup>
          <col class="sample-col">
          <col class="status-col">
          <col class="observed-col">
          <col class="finding-col">
          <col class="evidence-col">
        </colgroup>
        <thead>
          <tr>
            <th>Sample</th>
            <th>Status</th>
            <th>Observed</th>
            <th>Finding</th>
            <th>Evidence</th>
          </tr>
        </thead>
        <tbody id="results-body"></tbody>
      </table>
    </div>
  </section>
  <section class="findings-panel">
    <h2>Normalized findings</h2>
    <div id="findings-list"></div>
    <button id="add-finding" type="button">Add finding</button>
  </section>
  <script src="/ui/app.js"></script>
</body>
</html>
"""


APP_CSS = """
:root {
  color-scheme: light;
  --bg: #f6f2ea;
  --panel: #fffdf8;
  --ink: #1f1c17;
  --muted: #6b6255;
  --border: #d8cfbf;
  --accent: #275d8c;
  --accent-soft: #dbe9f6;
  --warning: #9a4d11;
  --ok: #2c6b3f;
  --sample-col-width: clamp(220px, 16vw, 300px);
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: Georgia, "Times New Roman", serif;
  background: linear-gradient(180deg, #ece2cf 0%, var(--bg) 180px);
  color: var(--ink);
}
.page-header, .toolbar, .metadata-panel, .results-panel, .findings-panel {
  width: min(90%, calc(100vw - 32px));
  margin: 16px auto;
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 16px 18px;
  box-shadow: 0 10px 24px rgba(39, 27, 12, 0.05);
}
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}
h1, h2, h3 { margin: 0 0 8px; }
p { margin: 0; color: var(--muted); }
.status-pill {
  padding: 8px 12px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 14px;
}
.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}
.toolbar label, .metadata-grid label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 14px;
}
.label-head {
  display: flex;
  align-items: center;
  gap: 6px;
}
.help-dot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: #f3ebde;
  color: var(--accent);
  font-size: 12px;
  font-weight: bold;
  cursor: help;
}
.checkbox {
  flex-direction: row !important;
  align-items: center;
  gap: 8px !important;
  padding-top: 22px;
}
select, input, textarea, button {
  font: inherit;
}
select, input, textarea {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 10px;
  background: white;
}
textarea {
  min-height: 84px;
  resize: vertical;
}
button {
  border: none;
  border-radius: 10px;
  padding: 10px 14px;
  background: var(--accent);
  color: white;
  cursor: pointer;
}
.metadata-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}
.metadata-grid textarea {
  min-height: 96px;
}
.explanation-card {
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 12px;
  margin-bottom: 10px;
  background: #fff;
}
.explanation-card p {
  color: var(--ink);
}
.table-wrapper {
  overflow-x: auto;
}
table {
  width: 100%;
  min-width: 1100px;
  border-collapse: collapse;
}
.results-panel table {
  table-layout: fixed;
}
.results-panel col.sample-col {
  width: var(--sample-col-width);
}
th, td {
  border-bottom: 1px solid var(--border);
  padding: 12px;
  vertical-align: top;
}
th {
  text-align: left;
  font-size: 14px;
  color: var(--muted);
}
.sample-meta {
  font-size: 13px;
  color: var(--muted);
  margin-top: 4px;
  overflow-wrap: anywhere;
}
.sample-meta code {
  background: #f3ebde;
  padding: 2px 4px;
  border-radius: 4px;
  overflow-wrap: anywhere;
}
.field-stack {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.field-stack label {
  width: 100%;
}
.field-stack input,
.field-stack textarea,
.field-stack select {
  width: min(100%, 34vw);
}
.field-stack textarea {
  min-width: 260px;
}
.finding-card {
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 12px;
  margin-bottom: 12px;
  background: #fff;
}
.finding-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 280px), 1fr));
  gap: 10px;
}
.tag {
  display: inline-block;
  padding: 3px 8px;
  border-radius: 999px;
  background: #efe5d2;
  color: var(--ink);
  margin-right: 6px;
}
@media (max-width: 1280px) {
  :root {
    --sample-col-width: clamp(220px, 20vw, 320px);
  }
  .field-stack input,
  .field-stack textarea,
  .field-stack select {
    width: min(100%, 42vw);
  }
}
@media (max-width: 960px) {
  :root {
    --sample-col-width: clamp(220px, 24vw, 340px);
  }
  .page-header {
    flex-direction: column;
    gap: 12px;
  }
  .field-stack input,
  .field-stack textarea,
  .field-stack select {
    width: min(100%, 56vw);
  }
  th, td {
    padding: 10px;
  }
}
"""


APP_JS = """
const state = { session: null, results: [], findings: [] };
const CATEGORY_EXPLANATIONS = {
  "baseline": "Baseline samples are small valid files for each allowed extension. Use them to confirm the happy-path behavior, preview generation, download headers, storage naming, OCR, and metadata handling before moving to adversarial cases.",
  "mismatch": "Mismatch samples intentionally keep one allowed filename extension while embedding a different allowed content family. They help reveal whether the application validates extension and content independently instead of enforcing a strict mapping.",
  "minimal-headers": "Minimal-header samples contain only the magic bytes or signature prefix required to trigger superficial type checks. They help distinguish weak header-only validation from real parser validation.",
  "malformed": "Malformed samples start from valid or signature-looking content and then break structural integrity through truncation or bounded random tails. They help detect whether downstream components fail safely when parser validation is incomplete.",
  "metadata": "Metadata samples embed unique marker values or benign reflection probes in fields that may later appear in the UI, logs, OCR, indexing, or exports. They help identify metadata reflection and sanitization issues.",
  "filenames": "Filename recipes document risky multipart filenames that should be tested manually without creating dangerous local paths. They help assess normalization, reflection, traversal, reserved names, and shell-sensitive handling.",
  "multipart-recipes": "Multipart recipes vary the declared Content-Type and related request headers without changing the sample bytes. They help determine which layer trusts multipart metadata and whether different components disagree on routing.",
  "stress-bounded": "Bounded stress samples stay within defined safety limits while still exercising large dimensions, repeated metadata, or heavier parsing paths. They help reveal safe resource-handling weaknesses without becoming denial-of-service payloads.",
  "pdf-structures": "PDF structure samples include benign document features such as form-like objects or embedded text markers. They help identify how the upload pipeline treats richer PDF structures without relying on active content.",
  "polyglots": "Polyglot samples are optional composite files intended to exercise parser disagreement across multiple formats. They help detect whether validators, thumbnailers, renderers, or download handlers interpret the same bytes differently.",
};

const FIELD_HELP = {
  tester_name: "Name of the tester currently recording results in this session.",
  target_name: "Application, environment, or client target being tested.",
  test_window: "Date range or time window during which the upload tests are performed.",
  base_url: "Base URL of the upload application or portal under test.",
  field_name: "Name of the multipart form field used for file uploads, if known.",
  overall_assessment: "High-level conclusions, constraints, or overall testing notes for the engagement.",
  test_status: "Current outcome for this sample: untested, accepted, rejected, error, needs-review, or interesting.",
  validation_message: "Server-side validation message, UI error, or response text returned during upload.",
  stored_filename: "Filename as stored or later shown by the application after upload.",
  stored_extension: "Extension observed after storage or renaming by the target application.",
  displayed_type: "Type label shown in the UI, admin panel, or download view.",
  detected_mime_ui: "MIME type or content type displayed by the application interface, if any.",
  preview_generated: "Whether the application generated a preview, thumbnail, or inline viewer output.",
  ocr_extracted: "Whether OCR or text extraction occurred, and what was extracted.",
  metadata_reflected: "Whether metadata values appeared in the UI, logs, exports, or other reflected locations.",
  download_content_type: "Observed Content-Type header when downloading the stored file.",
  download_content_disposition: "Observed Content-Disposition header during download.",
  download_x_content_type_options: "Observed X-Content-Type-Options header during download.",
  download_cache_control: "Observed Cache-Control header during download.",
  download_csp: "Observed Content-Security-Policy header during download or preview.",
  bytes_preserved: "Whether the downloaded file matches the uploaded bytes exactly, if verified.",
  processing_time_notes: "Timing or performance observations during upload, preview, conversion, or download.",
  tester_notes: "Free-form notes about notable behavior, reproduction details, or observations for this sample.",
  finding_title: "Short title if this sample triggered or supports a finding.",
  finding_severity: "Severity rating used by the tester or reporting standard.",
  finding_summary: "Short explanation of the issue observed for this sample.",
  recommendation: "Suggested remediation or defensive recommendation tied to the observation.",
  evidence_paths: "Paths or references to screenshots, HTTP captures, exports, or downloaded files kept as evidence.",
  title: "Short name for a normalized finding that groups related sample behavior.",
  severity: "Severity assigned to the normalized finding.",
  summary: "Concise description of the grouped issue and why it matters.",
  manifest_ids: "Comma-separated sample IDs linked to this grouped finding.",
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  if (response.status === 204) return null;
  return response.json();
}

function setSaveStatus(text) {
  document.getElementById("save-status").textContent = text;
}

function field(label, key, value, onChange, multiline = false) {
  const wrapper = document.createElement("label");
  const head = document.createElement("div");
  head.className = "label-head";
  const title = document.createElement("span");
  title.textContent = label;
  head.appendChild(title);
  if (FIELD_HELP[key]) {
    const help = document.createElement("span");
    help.className = "help-dot";
    help.textContent = "?";
    help.title = FIELD_HELP[key];
    help.setAttribute("aria-label", FIELD_HELP[key]);
    head.appendChild(help);
  }
  wrapper.appendChild(head);
  const input = multiline ? document.createElement("textarea") : document.createElement("input");
  input.value = value || "";
  input.addEventListener("change", () => onChange(input.value));
  wrapper.appendChild(input);
  return wrapper;
}

async function loadSession() {
  state.session = await api("/api/session");
  state.results = await api("/api/results");
  state.findings = await api("/api/findings");
  render();
}

function populateFilters() {
  const categories = [...new Set(state.results.map((item) => item.category))].sort();
  const families = [...new Set(state.results.map((item) => item.generated_content_family))].sort();
  const extensions = [...new Set(state.results.map((item) => item.logical_extension))].sort();
  const statuses = [...new Set(state.results.map((item) => item.test_status))].sort();
  const specs = [
    ["filter-category", categories],
    ["filter-family", families],
    ["filter-extension", extensions],
    ["filter-status", statuses],
  ];
  for (const [id, values] of specs) {
    const select = document.getElementById(id);
    const existing = new Set([...select.options].map((option) => option.value));
    for (const value of values) {
      if (!existing.has(value)) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        select.appendChild(option);
      }
    }
  }
}

function activeFilters() {
  return {
    category: document.getElementById("filter-category").value,
    family: document.getElementById("filter-family").value,
    extension: document.getElementById("filter-extension").value,
    status: document.getElementById("filter-status").value,
    findingsOnly: document.getElementById("filter-findings").checked,
    incompleteOnly: document.getElementById("filter-incomplete").checked,
  };
}

function filteredResults() {
  const filters = activeFilters();
  return state.results.filter((item) => {
    if (filters.category && item.category !== filters.category) return false;
    if (filters.family && item.generated_content_family !== filters.family) return false;
    if (filters.extension && item.logical_extension !== filters.extension) return false;
    if (filters.status && item.test_status !== filters.status) return false;
    if (filters.findingsOnly && !item.finding_title && !item.finding_summary) return false;
    if (filters.incompleteOnly && item.test_status !== "untested" && item.test_status !== "needs-review") return false;
    return true;
  });
}

async function saveSessionField(key, value) {
  setSaveStatus("Saving session...");
  state.session.metadata[key] = value;
  await api("/api/session", {
    method: "PATCH",
    body: JSON.stringify({ [key]: value }),
  });
  setSaveStatus("Saved");
}

async function saveResult(manifestId, payload) {
  setSaveStatus(`Saving ${manifestId}...`);
  const updated = await api(`/api/results/${manifestId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  const index = state.results.findIndex((item) => item.id === manifestId);
  state.results[index] = updated;
  setSaveStatus("Saved");
  renderResults();
}

async function saveFinding(findingId, payload) {
  setSaveStatus("Saving finding...");
  const method = findingId ? "PATCH" : "POST";
  const path = findingId ? `/api/findings/${findingId}` : "/api/findings";
  const finding = await api(path, {
    method,
    body: JSON.stringify(payload),
  });
  const index = state.findings.findIndex((item) => item.id === finding.id);
  if (index >= 0) state.findings[index] = finding;
  else state.findings.push(finding);
  setSaveStatus("Saved");
  renderFindings();
}

async function deleteFinding(findingId) {
  setSaveStatus("Deleting finding...");
  await api(`/api/findings/${findingId}`, { method: "DELETE" });
  state.findings = state.findings.filter((item) => item.id !== findingId);
  setSaveStatus("Saved");
  renderFindings();
}

function renderSession() {
  const summary = document.getElementById("session-summary");
  summary.textContent = `${state.session.total_entries} samples loaded. ${state.session.progress_summary}`;
  const metadataRoot = document.getElementById("metadata-fields");
  metadataRoot.innerHTML = "";
  const fields = [
    ["tester_name", "Tester name"],
    ["target_name", "Target name"],
    ["test_window", "Test window"],
    ["base_url", "Base URL"],
    ["field_name", "Field name"],
    ["overall_assessment", "Overall assessment", true],
  ];
  for (const [key, label, multiline] of fields) {
    metadataRoot.appendChild(field(label, key, state.session.metadata[key], (value) => saveSessionField(key, value), Boolean(multiline)));
  }
  const explanationRoot = document.getElementById("category-explanations");
  explanationRoot.innerHTML = "";
  const categories = [...new Set(state.results.map((item) => item.category))].sort();
  for (const category of categories) {
    const card = document.createElement("div");
    card.className = "explanation-card";
    card.innerHTML = `<h3>${category}</h3><p>${CATEGORY_EXPLANATIONS[category] || "This category exercises a specific upload validation behavior."}</p>`;
    explanationRoot.appendChild(card);
  }
}

function resultRow(item) {
  const row = document.createElement("tr");
  const sampleCell = document.createElement("td");
  sampleCell.innerHTML = `<strong>${item.filename}</strong><div class="sample-meta"><code>${item.id}</code> · ${item.category} · ${item.generated_content_family} · ${item.logical_extension}<br><strong>Why this test exists:</strong> ${item.description}<br><strong>What to verify:</strong> ${item.expected_behavior}<br><strong>Category guide:</strong> ${CATEGORY_EXPLANATIONS[item.category] || ""}</div>`;
  row.appendChild(sampleCell);

  const statusCell = document.createElement("td");
  const statusStack = document.createElement("div");
  statusStack.className = "field-stack";
  const statusLabel = document.createElement("label");
  const statusHead = document.createElement("div");
  statusHead.className = "label-head";
  const statusTitle = document.createElement("span");
  statusTitle.textContent = "Status";
  statusHead.appendChild(statusTitle);
  const statusHelp = document.createElement("span");
  statusHelp.className = "help-dot";
  statusHelp.textContent = "?";
  statusHelp.title = FIELD_HELP.test_status;
  statusHelp.setAttribute("aria-label", FIELD_HELP.test_status);
  statusHead.appendChild(statusHelp);
  statusLabel.appendChild(statusHead);
  const statusSelect = document.createElement("select");
  for (const status of ["untested","accepted","rejected","error","needs-review","interesting"]) {
    const option = document.createElement("option");
    option.value = status;
    option.textContent = status;
    if (item.test_status === status) option.selected = true;
    statusSelect.appendChild(option);
  }
  statusSelect.addEventListener("change", () => saveResult(item.id, { test_status: statusSelect.value }));
  statusLabel.appendChild(statusSelect);
  statusStack.appendChild(statusLabel);
  statusStack.appendChild(field("Validation message", "validation_message", item.validation_message, (value) => saveResult(item.id, { validation_message: value }), true));
  statusCell.appendChild(statusStack);
  row.appendChild(statusCell);

  const observedCell = document.createElement("td");
  const observedStack = document.createElement("div");
  observedStack.className = "field-stack";
  observedStack.appendChild(field("Stored filename", "stored_filename", item.stored_filename, (value) => saveResult(item.id, { stored_filename: value })));
  observedStack.appendChild(field("Displayed type", "displayed_type", item.displayed_type, (value) => saveResult(item.id, { displayed_type: value })));
  observedStack.appendChild(field("Metadata reflected", "metadata_reflected", item.metadata_reflected, (value) => saveResult(item.id, { metadata_reflected: value })));
  observedStack.appendChild(field("Tester notes", "tester_notes", item.tester_notes, (value) => saveResult(item.id, { tester_notes: value }), true));
  observedCell.appendChild(observedStack);
  row.appendChild(observedCell);

  const findingCell = document.createElement("td");
  const findingStack = document.createElement("div");
  findingStack.className = "field-stack";
  findingStack.appendChild(field("Finding title", "finding_title", item.finding_title, (value) => saveResult(item.id, { finding_title: value })));
  findingStack.appendChild(field("Finding severity", "finding_severity", item.finding_severity, (value) => saveResult(item.id, { finding_severity: value })));
  findingStack.appendChild(field("Finding summary", "finding_summary", item.finding_summary, (value) => saveResult(item.id, { finding_summary: value }), true));
  findingCell.appendChild(findingStack);
  row.appendChild(findingCell);

  const evidenceCell = document.createElement("td");
  const evidenceStack = document.createElement("div");
  evidenceStack.className = "field-stack";
  evidenceStack.appendChild(field("Evidence paths", "evidence_paths", item.evidence_paths, (value) => saveResult(item.id, { evidence_paths: value }), true));
  evidenceStack.appendChild(field("Recommendation", "recommendation", item.recommendation, (value) => saveResult(item.id, { recommendation: value }), true));
  evidenceCell.appendChild(evidenceStack);
  row.appendChild(evidenceCell);

  return row;
}

function renderResults() {
  populateFilters();
  const body = document.getElementById("results-body");
  body.innerHTML = "";
  for (const item of filteredResults()) {
    body.appendChild(resultRow(item));
  }
}

function renderFindings() {
  const root = document.getElementById("findings-list");
  root.innerHTML = "";
  for (const finding of state.findings) {
    const card = document.createElement("div");
    card.className = "finding-card";
    card.innerHTML = `<div class="tag">${finding.severity || "unspecified"}</div><div class="tag">${(finding.manifest_ids || []).length} sample(s)</div>`;
    const deleteWrap = document.createElement("div");
    deleteWrap.style.display = "flex";
    deleteWrap.style.justifyContent = "flex-end";
    deleteWrap.style.marginBottom = "10px";
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "Delete";
    remove.addEventListener("click", () => {
      if (confirm("Delete this finding?")) {
        deleteFinding(finding.id);
      }
    });
    deleteWrap.appendChild(remove);
    card.appendChild(deleteWrap);
    const grid = document.createElement("div");
    grid.className = "finding-grid";
    grid.appendChild(field("Title", "title", finding.title, (value) => saveFinding(finding.id, { ...finding, title: value })));
    grid.appendChild(field("Severity", "severity", finding.severity, (value) => saveFinding(finding.id, { ...finding, severity: value })));
    grid.appendChild(field("Affected sample IDs", "manifest_ids", (finding.manifest_ids || []).join(", "), (value) => saveFinding(finding.id, { ...finding, manifest_ids: value.split(",").map((item) => item.trim()).filter(Boolean) }), true));
    grid.appendChild(field("Summary", "summary", finding.summary, (value) => saveFinding(finding.id, { ...finding, summary: value }), true));
    grid.appendChild(field("Recommendation", "recommendation", finding.recommendation, (value) => saveFinding(finding.id, { ...finding, recommendation: value }), true));
    card.appendChild(grid);
    root.appendChild(card);
  }
}

function render() {
  renderSession();
  renderResults();
  renderFindings();
}

for (const id of ["filter-category", "filter-family", "filter-extension", "filter-status", "filter-findings", "filter-incomplete"]) {
  window.addEventListener("load", () => document.getElementById(id).addEventListener("change", renderResults));
}

window.addEventListener("load", () => {
  document.getElementById("add-finding").addEventListener("click", () => {
    saveFinding(null, { title: "", severity: "", summary: "", recommendation: "", manifest_ids: [] });
  });
  document.getElementById("export-report").addEventListener("click", async () => {
    setSaveStatus("Exporting...");
    await api("/api/export", { method: "POST", body: "{}" });
    setSaveStatus("Exported");
    alert("Report exported to reporting/final-report.html");
  });
  loadSession().catch((error) => {
    setSaveStatus("Failed");
    console.error(error);
    alert(error.message);
  });
});
"""


def reporting_dir(out_dir: Path) -> Path:
    return out_dir / "reporting"


def ui_dir(out_dir: Path) -> Path:
    return reporting_dir(out_dir) / "ui"


def session_db_path(out_dir: Path) -> Path:
    return reporting_dir(out_dir) / "session.sqlite3"


def require_manifest(out_dir: Path) -> dict[str, Any]:
    manifest_path = out_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest not found: {manifest_path}")
    return load_manifest(manifest_path)


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA foreign_keys = ON;
        CREATE TABLE IF NOT EXISTS session_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS manifest_import (
            manifest_hash TEXT PRIMARY KEY,
            imported_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS manifest_entries (
            id TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            relative_path TEXT NOT NULL,
            filename TEXT NOT NULL,
            logical_extension TEXT NOT NULL,
            generated_content_family TEXT NOT NULL,
            expected_mime TEXT NOT NULL,
            expected_magic_hex TEXT NOT NULL,
            mismatch INTEGER NOT NULL,
            risk_level TEXT NOT NULL,
            generator TEXT NOT NULL,
            description TEXT NOT NULL,
            expected_behavior TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            provenance_json TEXT NOT NULL,
            manifest_present INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS test_results (
            manifest_id TEXT PRIMARY KEY,
            test_status TEXT NOT NULL DEFAULT 'untested',
            validation_message TEXT NOT NULL DEFAULT '',
            stored_filename TEXT NOT NULL DEFAULT '',
            stored_extension TEXT NOT NULL DEFAULT '',
            displayed_type TEXT NOT NULL DEFAULT '',
            detected_mime_ui TEXT NOT NULL DEFAULT '',
            preview_generated TEXT NOT NULL DEFAULT '',
            ocr_extracted TEXT NOT NULL DEFAULT '',
            metadata_reflected TEXT NOT NULL DEFAULT '',
            download_content_type TEXT NOT NULL DEFAULT '',
            download_content_disposition TEXT NOT NULL DEFAULT '',
            download_x_content_type_options TEXT NOT NULL DEFAULT '',
            download_cache_control TEXT NOT NULL DEFAULT '',
            download_csp TEXT NOT NULL DEFAULT '',
            bytes_preserved TEXT NOT NULL DEFAULT '',
            processing_time_notes TEXT NOT NULL DEFAULT '',
            tester_notes TEXT NOT NULL DEFAULT '',
            finding_title TEXT NOT NULL DEFAULT '',
            finding_severity TEXT NOT NULL DEFAULT '',
            finding_summary TEXT NOT NULL DEFAULT '',
            recommendation TEXT NOT NULL DEFAULT '',
            evidence_paths TEXT NOT NULL DEFAULT '',
            last_updated_at TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (manifest_id) REFERENCES manifest_entries(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS findings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL DEFAULT '',
            severity TEXT NOT NULL DEFAULT '',
            summary TEXT NOT NULL DEFAULT '',
            recommendation TEXT NOT NULL DEFAULT '',
            manifest_ids_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS evidence_refs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            manifest_id TEXT,
            finding_id INTEGER,
            ref_path TEXT NOT NULL,
            kind TEXT NOT NULL DEFAULT 'path',
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (manifest_id) REFERENCES manifest_entries(id) ON DELETE CASCADE,
            FOREIGN KEY (finding_id) REFERENCES findings(id) ON DELETE CASCADE
        );
        """
    )
    for key, value in DEFAULT_SESSION_METADATA.items():
        connection.execute(
            "INSERT OR IGNORE INTO session_metadata(key, value) VALUES (?, ?)",
            (key, value),
        )
    connection.commit()


def manifest_snapshot_hash(payload: dict[str, Any]) -> str:
    snapshot = json.dumps(payload.get("entries", []), sort_keys=True)
    return __import__("hashlib").sha256(snapshot.encode("utf-8")).hexdigest()


def write_ui_assets(out_dir: Path) -> None:
    ui_root = ensure_within(out_dir, ui_dir(out_dir))
    ui_root.mkdir(parents=True, exist_ok=True)
    write_text(ui_root / "index.html", INDEX_HTML, overwrite=True)
    write_text(ui_root / "app.css", APP_CSS.strip() + "\n", overwrite=True)
    write_text(ui_root / "app.js", APP_JS.strip() + "\n", overwrite=True)


def init_reporting(out_dir: Path) -> dict[str, int]:
    payload = require_manifest(out_dir)
    write_ui_assets(out_dir)
    db_path = session_db_path(out_dir)
    connection = connect(db_path)
    ensure_schema(connection)
    manifest_hash = manifest_snapshot_hash(payload)
    connection.execute("UPDATE manifest_entries SET manifest_present = 0")
    added = 0
    for entry in payload.get("entries", []):
        record = dict(entry)
        connection.execute(
            """
            INSERT INTO manifest_entries (
                id, category, relative_path, filename, logical_extension, generated_content_family,
                expected_mime, expected_magic_hex, mismatch, risk_level, generator, description,
                expected_behavior, sha256, size_bytes, created_at, provenance_json, manifest_present
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(id) DO UPDATE SET
                category=excluded.category,
                relative_path=excluded.relative_path,
                filename=excluded.filename,
                logical_extension=excluded.logical_extension,
                generated_content_family=excluded.generated_content_family,
                expected_mime=excluded.expected_mime,
                expected_magic_hex=excluded.expected_magic_hex,
                mismatch=excluded.mismatch,
                risk_level=excluded.risk_level,
                generator=excluded.generator,
                description=excluded.description,
                expected_behavior=excluded.expected_behavior,
                sha256=excluded.sha256,
                size_bytes=excluded.size_bytes,
                created_at=excluded.created_at,
                provenance_json=excluded.provenance_json,
                manifest_present=1
            """,
            (
                record["id"],
                record["category"],
                record["relative_path"],
                record["filename"],
                record["logical_extension"],
                record["generated_content_family"],
                record["expected_mime"],
                record["expected_magic_hex"],
                int(record["mismatch"]),
                record["risk_level"],
                record["generator"],
                record["description"],
                record["expected_behavior"],
                record["sha256"],
                record["size_bytes"],
                record["created_at"],
                json.dumps(record.get("provenance", {}), sort_keys=True),
            ),
        )
        result = connection.execute(
            """
            INSERT OR IGNORE INTO test_results(manifest_id, last_updated_at)
            VALUES (?, ?)
            """,
            (record["id"], ""),
        )
        added += result.rowcount
    connection.execute("DELETE FROM manifest_import")
    connection.execute(
        "INSERT INTO manifest_import(manifest_hash, imported_at) VALUES (?, ?)",
        (manifest_hash, utc_now()),
    )
    connection.commit()
    total = connection.execute("SELECT COUNT(*) FROM manifest_entries WHERE manifest_present = 1").fetchone()[0]
    removed = connection.execute("SELECT COUNT(*) FROM manifest_entries WHERE manifest_present = 0").fetchone()[0]
    connection.close()
    return {"total_entries": total, "new_results": added, "retired_entries": removed}


def reset_reporting(out_dir: Path) -> dict[str, int]:
    db_path = session_db_path(out_dir)
    if db_path.exists():
        db_path.unlink()
    return init_reporting(out_dir)


def load_session_state(out_dir: Path) -> dict[str, Any]:
    payload = require_manifest(out_dir)
    db_path = session_db_path(out_dir)
    if not db_path.exists():
        init_reporting(out_dir)
    connection = connect(db_path)
    ensure_schema(connection)
    metadata = {
        row["key"]: row["value"]
        for row in connection.execute("SELECT key, value FROM session_metadata ORDER BY key")
    }
    counts = Counter(
        row["test_status"]
        for row in connection.execute("SELECT test_status FROM test_results")
    )
    total_entries = connection.execute(
        "SELECT COUNT(*) FROM manifest_entries WHERE manifest_present = 1"
    ).fetchone()[0]
    progress_summary = ", ".join(
        f"{status}: {counts.get(status, 0)}"
        for status in ALLOWED_TEST_STATUSES
    )
    connection.close()
    return {
        "metadata": metadata,
        "total_entries": total_entries,
        "progress_summary": progress_summary,
        "manifest_config": payload.get("config", {}),
    }


def list_results(out_dir: Path) -> list[dict[str, Any]]:
    connection = connect(session_db_path(out_dir))
    rows = connection.execute(
        """
        SELECT
            me.id, me.category, me.relative_path, me.filename, me.logical_extension,
            me.generated_content_family, me.expected_mime, me.expected_magic_hex,
            me.mismatch, me.risk_level, me.generator, me.description,
            me.expected_behavior, me.created_at, me.provenance_json,
            tr.test_status, tr.validation_message, tr.stored_filename, tr.stored_extension,
            tr.displayed_type, tr.detected_mime_ui, tr.preview_generated, tr.ocr_extracted,
            tr.metadata_reflected, tr.download_content_type, tr.download_content_disposition,
            tr.download_x_content_type_options, tr.download_cache_control, tr.download_csp,
            tr.bytes_preserved, tr.processing_time_notes, tr.tester_notes, tr.finding_title,
            tr.finding_severity, tr.finding_summary, tr.recommendation, tr.evidence_paths,
            tr.last_updated_at
        FROM manifest_entries me
        JOIN test_results tr ON tr.manifest_id = me.id
        WHERE me.manifest_present = 1
        ORDER BY me.category, me.filename
        """
    ).fetchall()
    results = []
    for row in rows:
        record = dict(row)
        record["mismatch"] = bool(record["mismatch"])
        record["provenance"] = json.loads(record.pop("provenance_json"))
        results.append(record)
    connection.close()
    return results


def patch_session_metadata(out_dir: Path, payload: dict[str, str]) -> dict[str, str]:
    connection = connect(session_db_path(out_dir))
    ensure_schema(connection)
    for key, value in payload.items():
        if key not in DEFAULT_SESSION_METADATA:
            raise KeyError(f"unknown session metadata field: {key}")
        connection.execute(
            "INSERT INTO session_metadata(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
    connection.commit()
    result = {
        row["key"]: row["value"]
        for row in connection.execute("SELECT key, value FROM session_metadata ORDER BY key")
    }
    connection.close()
    return result


def patch_result(out_dir: Path, manifest_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    connection = connect(session_db_path(out_dir))
    ensure_schema(connection)
    if not connection.execute("SELECT 1 FROM manifest_entries WHERE id = ? AND manifest_present = 1", (manifest_id,)).fetchone():
        raise KeyError(f"unknown manifest id: {manifest_id}")
    assignments = []
    values: list[Any] = []
    for key, value in payload.items():
        if key not in TEST_RESULT_FIELDS or key == "last_updated_at":
            raise KeyError(f"unknown or immutable result field: {key}")
        if key == "test_status" and value not in ALLOWED_TEST_STATUSES:
            raise ValueError(f"invalid test status: {value}")
        assignments.append(f"{key} = ?")
        values.append(value)
    assignments.append("last_updated_at = ?")
    values.append(utc_now())
    values.append(manifest_id)
    connection.execute(
        f"UPDATE test_results SET {', '.join(assignments)} WHERE manifest_id = ?",
        values,
    )
    connection.commit()
    connection.close()
    for result in list_results(out_dir):
        if result["id"] == manifest_id:
            return result
    raise KeyError(f"manifest result not found after update: {manifest_id}")


def list_findings(out_dir: Path) -> list[dict[str, Any]]:
    connection = connect(session_db_path(out_dir))
    ensure_schema(connection)
    rows = connection.execute(
        "SELECT id, title, severity, summary, recommendation, manifest_ids_json, created_at, updated_at FROM findings ORDER BY id"
    ).fetchall()
    findings = []
    for row in rows:
        finding = dict(row)
        finding["manifest_ids"] = json.loads(finding.pop("manifest_ids_json"))
        findings.append(finding)
    connection.close()
    return findings


def upsert_finding(out_dir: Path, payload: dict[str, Any], finding_id: int | None = None) -> dict[str, Any]:
    connection = connect(session_db_path(out_dir))
    ensure_schema(connection)
    manifest_ids = payload.get("manifest_ids", [])
    now = utc_now()
    if finding_id is None:
        cursor = connection.execute(
            """
            INSERT INTO findings(title, severity, summary, recommendation, manifest_ids_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get("title", ""),
                payload.get("severity", ""),
                payload.get("summary", ""),
                payload.get("recommendation", ""),
                json.dumps(manifest_ids),
                now,
                now,
            ),
        )
        finding_id = int(cursor.lastrowid)
    else:
        connection.execute(
            """
            UPDATE findings
            SET title = ?, severity = ?, summary = ?, recommendation = ?, manifest_ids_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                payload.get("title", ""),
                payload.get("severity", ""),
                payload.get("summary", ""),
                payload.get("recommendation", ""),
                json.dumps(manifest_ids),
                now,
                finding_id,
            ),
        )
    connection.commit()
    connection.close()
    for finding in list_findings(out_dir):
        if finding["id"] == finding_id:
            return finding
    raise KeyError(f"finding not found after update: {finding_id}")


def delete_finding(out_dir: Path, finding_id: int) -> None:
    connection = connect(session_db_path(out_dir))
    ensure_schema(connection)
    connection.execute("DELETE FROM findings WHERE id = ?", (finding_id,))
    connection.commit()
    connection.close()


def status_summary(out_dir: Path) -> dict[str, int]:
    connection = connect(session_db_path(out_dir))
    ensure_schema(connection)
    counts = {
        row["test_status"]: row["count"]
        for row in connection.execute(
            "SELECT test_status, COUNT(*) AS count FROM test_results GROUP BY test_status"
        )
    }
    connection.close()
    return {status: counts.get(status, 0) for status in ALLOWED_TEST_STATUSES}


def methodology_html(out_dir: Path) -> str:
    methodology_path = Path(__file__).resolve().parents[2] / "documentation" / "06-TESTING-METHODOLOGY.md"
    if methodology_path.exists():
        lines = methodology_path.read_text(encoding="utf-8").splitlines()
        selected: list[str] = []
        for line in lines:
            if line.startswith("## "):
                break
            if line and not line.startswith("# "):
                selected.append(line)
        if selected:
            return "<p>" + html.escape(" ".join(selected)) + "</p>"
    return "<p>Use the generated corpus to map how the target handles file type signals across the upload lifecycle.</p>"


def export_report(out_dir: Path) -> dict[str, str]:
    session = load_session_state(out_dir)
    results = list_results(out_dir)
    findings = list_findings(out_dir)
    reporting_root = ensure_within(out_dir, reporting_dir(out_dir))
    reporting_root.mkdir(parents=True, exist_ok=True)

    grouped_findings: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        key = (
            result["finding_title"].strip(),
            result["finding_severity"].strip(),
            result["finding_summary"].strip(),
            result["recommendation"].strip(),
        )
        if any(key):
            grouped_findings[key].append(result)

    summary_counts = Counter(result["test_status"] for result in results)
    interesting = [result for result in results if result["test_status"] in {"interesting", "needs-review", "error"} or result["finding_title"]]
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        by_category[result["category"]].append(result)

    summary_payload = {
        "generated_at": utc_now(),
        "session_metadata": session["metadata"],
        "progress": {status: summary_counts.get(status, 0) for status in ALLOWED_TEST_STATUSES},
        "normalized_findings": [
            {
                "title": title,
                "severity": severity,
                "summary": finding_summary,
                "recommendation": recommendation,
                "sample_ids": [row["id"] for row in rows],
                "filenames": [row["filename"] for row in rows],
            }
            for (title, severity, finding_summary, recommendation), rows in grouped_findings.items()
            if any((title, severity, finding_summary, recommendation))
        ],
        "explicit_findings": findings,
        "interesting_samples": [
            {
                "id": row["id"],
                "filename": row["filename"],
                "category": row["category"],
                "status": row["test_status"],
                "finding_title": row["finding_title"],
            }
            for row in interesting
        ],
    }
    summary_json_path = reporting_root / "report-summary.json"
    summary_json_path.write_text(to_json(summary_payload) + "\n", encoding="utf-8")

    summary_lines = [
        "# Upload Sample Test Report Summary",
        "",
        f"- Generated at: {summary_payload['generated_at']}",
        f"- Target: {session['metadata'].get('target_name', '') or 'Not set'}",
        f"- Tester: {session['metadata'].get('tester_name', '') or 'Not set'}",
        "",
        "## Progress",
        "",
    ]
    summary_lines.extend(
        f"- {status}: {summary_counts.get(status, 0)}"
        for status in ALLOWED_TEST_STATUSES
    )
    summary_lines.extend(["", "## Findings", ""])
    if summary_payload["normalized_findings"]:
        for finding in summary_payload["normalized_findings"]:
            summary_lines.append(
                f"- {finding['title'] or 'Untitled finding'} ({finding['severity'] or 'unspecified'}) :: {', '.join(finding['sample_ids'])}"
            )
    else:
        summary_lines.append("- No normalized findings recorded.")
    summary_md_path = reporting_root / "report-summary.md"
    summary_md_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    category_sections = []
    for category, rows in sorted(by_category.items()):
        rendered_rows = "".join(
            f"""
            <tr data-report-sample="1" data-status="{html.escape(row['test_status'])}" data-category="{html.escape(category)}" data-has-finding="{'yes' if row['finding_title'] else 'no'}">
              <td><code>{html.escape(row['id'])}</code><br>{html.escape(row['filename'])}<br><small>{html.escape(row['description'])}</small></td>
              <td>{html.escape(row['test_status'])}</td>
              <td>{html.escape(row['displayed_type'] or row['detected_mime_ui'] or '')}</td>
              <td>{html.escape(row['validation_message'])}</td>
              <td>{html.escape(row['finding_title'])}</td>
              <td>{html.escape(row['evidence_paths'])}</td>
            </tr>
            """
            for row in rows
        )
        category_sections.append(
            f"""
            <section class="report-section">
              <h3>{html.escape(category)}</h3>
              <p>{html.escape(CATEGORY_EXPLANATIONS.get(category, 'This category exercises a specific upload validation behavior.'))}</p>
              <table>
                <thead><tr><th>Sample</th><th>Status</th><th>Displayed type</th><th>Validation</th><th>Finding</th><th>Evidence</th></tr></thead>
                <tbody>{rendered_rows}</tbody>
              </table>
            </section>
            """
        )

    findings_blocks = []
    for finding in summary_payload["normalized_findings"]:
        findings_blocks.append(
            f"""
            <article class="finding">
              <h3>{html.escape(finding['title'] or 'Untitled finding')}</h3>
              <p><strong>Severity:</strong> {html.escape(finding['severity'] or 'unspecified')}</p>
              <p>{html.escape(finding['summary'])}</p>
              <p><strong>Recommendation:</strong> {html.escape(finding['recommendation'])}</p>
              <p><strong>Triggered by:</strong> {html.escape(', '.join(finding['sample_ids']))}</p>
            </article>
            """
        )
    if not findings_blocks:
        findings_blocks.append("<p>No normalized findings recorded.</p>")

    report_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Upload Sample Test Report</title>
  <style>
    body {{ font-family: Georgia, "Times New Roman", serif; margin: 0; background: #f7f2e9; color: #1e1a15; }}
    main {{ width: min(90%, calc(100vw - 32px)); margin: 24px auto; }}
    header, section {{ background: #fffdf8; border: 1px solid #d7ccbc; border-radius: 16px; padding: 18px 22px; margin-bottom: 16px; }}
    h1, h2, h3 {{ margin-top: 0; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }}
    .metric {{ border: 1px solid #eadfcd; border-radius: 12px; padding: 12px; background: #faf5ed; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ border-bottom: 1px solid #eadfcd; padding: 10px; text-align: left; vertical-align: top; }}
    code {{ background: #f2e9dc; padding: 2px 4px; border-radius: 4px; }}
    .finding {{ border: 1px solid #eadfcd; border-radius: 12px; padding: 12px; margin-bottom: 12px; }}
    .report-toolbar {{ display:flex; flex-wrap:wrap; gap:12px; align-items:center; margin-bottom: 14px; }}
    .report-toolbar label {{ display:flex; flex-direction:column; gap:6px; font-size:14px; }}
    .hidden-row {{ display:none; }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Upload Sample Test Report</h1>
      <p>Generated at {html.escape(summary_payload['generated_at'])}</p>
      <div class="grid">
        <div class="metric"><strong>Target</strong><br>{html.escape(session['metadata'].get('target_name', '') or 'Not set')}</div>
        <div class="metric"><strong>Tester</strong><br>{html.escape(session['metadata'].get('tester_name', '') or 'Not set')}</div>
        <div class="metric"><strong>Base URL</strong><br>{html.escape(session['metadata'].get('base_url', '') or 'Not set')}</div>
        <div class="metric"><strong>Field Name</strong><br>{html.escape(session['metadata'].get('field_name', '') or 'Not set')}</div>
      </div>
    </header>
    <section>
      <h2>Executive Summary</h2>
      <p>This report summarizes observed upload behavior for the generated sample corpus. Counts below reflect only saved tester input.</p>
      <div class="grid">
        {''.join(f"<div class='metric'><strong>{status}</strong><br>{summary_counts.get(status, 0)}</div>" for status in ALLOWED_TEST_STATUSES)}
      </div>
      <p><strong>Overall assessment:</strong> {html.escape(session['metadata'].get('overall_assessment', '') or 'Not recorded')}</p>
    </section>
    <section>
      <h2>Methodology</h2>
      {methodology_html(out_dir)}
    </section>
    <section>
      <h2>Test Explanations</h2>
      {''.join(f"<article class='finding'><h3>{html.escape(category)}</h3><p>{html.escape(CATEGORY_EXPLANATIONS.get(category, 'This category exercises a specific upload validation behavior.'))}</p></article>" for category in sorted(by_category))}
    </section>
    <section>
      <h2>Notable Findings</h2>
      {''.join(findings_blocks)}
    </section>
    <section>
      <h2>Explicit Findings</h2>
      {''.join(
          f"<article class='finding'><h3>{html.escape(finding['title'] or 'Untitled finding')}</h3><p><strong>Severity:</strong> {html.escape(finding['severity'] or 'unspecified')}</p><p>{html.escape(finding['summary'])}</p><p><strong>Recommendation:</strong> {html.escape(finding['recommendation'])}</p><p><strong>Sample IDs:</strong> {html.escape(', '.join(finding['manifest_ids']))}</p></article>"
          for finding in findings
      ) or '<p>No explicit findings recorded.</p>'}
    </section>
    <section>
      <h2>Category Results</h2>
      <div class="report-toolbar">
        <label>Filter status
          <select id="sample-filter-status">
            <option value="">All</option>
            {''.join(f"<option value='{status}'>{status}</option>" for status in ALLOWED_TEST_STATUSES)}
          </select>
        </label>
        <label>Filter category
          <select id="sample-filter-category">
            <option value="">All</option>
            {''.join(f"<option value='{html.escape(category)}'>{html.escape(category)}</option>" for category in sorted(by_category))}
          </select>
        </label>
        <label>Findings only
          <select id="sample-filter-findings">
            <option value="">All</option>
            <option value="yes">Only samples with findings</option>
          </select>
        </label>
      </div>
      {''.join(category_sections)}
    </section>
    <section>
      <h2>Interesting Samples Appendix</h2>
      <table>
        <thead><tr><th>Sample</th><th>Status</th><th>Finding</th><th>Notes</th><th>Evidence</th></tr></thead>
        <tbody>
          {''.join(
              f"<tr><td><code>{html.escape(row['id'])}</code><br>{html.escape(row['filename'])}</td><td>{html.escape(row['test_status'])}</td><td>{html.escape(row['finding_title'])}</td><td>{html.escape(row['tester_notes'])}</td><td>{html.escape(row['evidence_paths'])}</td></tr>"
              for row in interesting
          ) or "<tr><td colspan='5'>No interesting samples recorded.</td></tr>"}
        </tbody>
      </table>
    </section>
  </main>
  <script>
    (() => {{
      const statusFilter = document.getElementById("sample-filter-status");
      const categoryFilter = document.getElementById("sample-filter-category");
      const findingsFilter = document.getElementById("sample-filter-findings");
      const sampleRows = [...document.querySelectorAll("tr[data-report-sample='1']")];
      const applySampleFilters = () => {{
        sampleRows.forEach((row) => {{
          const matchesStatus = !statusFilter.value || row.dataset.status === statusFilter.value;
          const matchesCategory = !categoryFilter.value || row.dataset.category === categoryFilter.value;
          const matchesFinding = !findingsFilter.value || row.dataset.hasFinding === "yes";
          row.classList.toggle("hidden-row", !(matchesStatus && matchesCategory && matchesFinding));
        }});
      }};
      if (statusFilter && categoryFilter && findingsFilter) {{
        statusFilter.addEventListener("change", applySampleFilters);
        categoryFilter.addEventListener("change", applySampleFilters);
        findingsFilter.addEventListener("change", applySampleFilters);
        applySampleFilters();
      }}
    }})();
  </script>
</body>
</html>
"""
    report_html_path = reporting_root / "final-report.html"
    report_html_path.write_text(report_html, encoding="utf-8")
    return {
        "html": str(report_html_path),
        "json": str(summary_json_path),
        "markdown": str(summary_md_path),
    }


class ReportingRequestHandler(BaseHTTPRequestHandler):
    server_version = "UploadSamplesReporting/0.1"

    @property
    def out_dir(self) -> Path:
        return self.server.out_dir  # type: ignore[attr-defined]

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _send_json(self, payload: Any, status: int = 200) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_text(self, text: str, status: int = 200, content_type: str = "text/plain; charset=utf-8") -> None:
        encoded = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _serve_ui_file(self, name: str) -> None:
        asset_path = ensure_within(self.out_dir, ui_dir(self.out_dir) / name)
        if not asset_path.exists():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = "text/plain; charset=utf-8"
        if asset_path.suffix == ".html":
            content_type = "text/html; charset=utf-8"
        elif asset_path.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif asset_path.suffix == ".js":
            content_type = "application/javascript; charset=utf-8"
        self._send_text(asset_path.read_text(encoding="utf-8"), content_type=content_type)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/ui", "/ui/"}:
            self._serve_ui_file("index.html")
            return
        if parsed.path.startswith("/ui/"):
            self._serve_ui_file(parsed.path.split("/ui/", 1)[1])
            return
        if parsed.path == "/api/session":
            self._send_json(load_session_state(self.out_dir))
            return
        if parsed.path == "/api/results":
            self._send_json(list_results(self.out_dir))
            return
        if parsed.path == "/api/findings":
            self._send_json(list_findings(self.out_dir))
            return
        if parsed.path == "/api/status":
            self._send_json(status_summary(self.out_dir))
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_PATCH(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        payload = self._read_json()
        try:
            if parsed.path == "/api/session":
                self._send_json(patch_session_metadata(self.out_dir, payload))
                return
            if parsed.path.startswith("/api/results/"):
                manifest_id = parsed.path.rsplit("/", 1)[1]
                self._send_json(patch_result(self.out_dir, manifest_id, payload))
                return
            if parsed.path.startswith("/api/findings/"):
                finding_id = int(parsed.path.rsplit("/", 1)[1])
                self._send_json(upsert_finding(self.out_dir, payload, finding_id=finding_id))
                return
        except (KeyError, ValueError) as exc:
            self._send_text(str(exc), status=400)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        payload = self._read_json()
        try:
            if parsed.path == "/api/findings":
                self._send_json(upsert_finding(self.out_dir, payload), status=201)
                return
            if parsed.path == "/api/export":
                self._send_json(export_report(self.out_dir), status=201)
                return
        except (KeyError, ValueError) as exc:
            self._send_text(str(exc), status=400)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_DELETE(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            if parsed.path.startswith("/api/findings/"):
                finding_id = int(parsed.path.rsplit("/", 1)[1])
                delete_finding(self.out_dir, finding_id)
                self.send_response(HTTPStatus.NO_CONTENT)
                self.end_headers()
                return
        except (KeyError, ValueError) as exc:
            self._send_text(str(exc), status=400)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:
        return


def run_report_ui(out_dir: Path, host: str, port: int) -> None:
    write_ui_assets(out_dir)
    if not session_db_path(out_dir).exists():
        init_reporting(out_dir)
    server = ThreadingHTTPServer((host, port), ReportingRequestHandler)
    server.out_dir = out_dir  # type: ignore[attr-defined]
    try:
        server.serve_forever()
    finally:
        server.server_close()
