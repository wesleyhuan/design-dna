/* Design DNA — 本地 UI。純 vanilla JS，沒有建置步驟。 */

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const S = {
  meta: null,
  profile: null,
  resolved: null,
  category: "",
  search: "",
  selected: null,
  sources: [],
  proposals: [],
  proposal: null,
  editorTab: "edit",
};

/* ---------------- API ---------------- */

async function api(method, path, body) {
  const res = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json", "X-Design-DNA": "1" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({ error: "回應不是 JSON" }));
  if (!res.ok) {
    const err = new Error(data.error || ("HTTP " + res.status));
    err.status = res.status;
    throw err;
  }
  return data;
}

let toastTimer;
function toast(msg, isError = false) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.toggle("is-error", isError);
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, isError ? 5200 : 2600);
}

/* ---------------- 工具 ---------------- */

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => (
  { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
));

const catLabel = (key) =>
  (S.meta?.categories.find((c) => c.key === key) || {}).label || key;

const PRIORITY_TAG = { must: "MUST", should: "SHOULD", may: "MAY" };

/* 極簡 Markdown 渲染。夠用就好：標題、清單、表格、引用、程式碼、行內樣式。 */
function md(src) {
  const fences = [];
  let text = String(src || "").replace(/```[\w-]*\n([\s\S]*?)```/g, (_, code) => {
    fences.push("<pre><code>" + esc(code.replace(/\n$/, "")) + "</code></pre>");
    return "F" + (fences.length - 1) + "";
  });

  const lines = text.split("\n");
  const out = [];
  let para = [], list = null, quote = [];

  const flushPara = () => {
    if (para.length) { out.push("<p>" + inline(para.join(" ")) + "</p>"); para = []; }
  };
  const flushList = () => {
    if (list) { out.push("<" + list.tag + ">" + list.items.join("") + "</" + list.tag + ">"); list = null; }
  };
  const flushQuote = () => {
    if (quote.length) { out.push("<blockquote>" + inline(quote.join(" ")) + "</blockquote>"); quote = []; }
  };
  const flushAll = () => { flushPara(); flushList(); flushQuote(); };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (/^\s*$/.test(line)) { flushAll(); continue; }

    if (/^F\d+$/.test(line.trim())) {
      flushAll();
      out.push(fences[Number(line.trim().slice(2, -1))]);
      continue;
    }

    const heading = line.match(/^(#{1,6})\s+(.*)$/);
    if (heading) {
      flushAll();
      const level = Math.min(6, heading[1].length + 1);
      out.push("<h" + level + ">" + inline(heading[2]) + "</h" + level + ">");
      continue;
    }

    // 表格：本行是 |…| 且下一行是分隔列
    if (line.trim().startsWith("|") && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1] || "")) {
      flushAll();
      const cells = (row) => row.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
      const head = cells(line);
      const rows = [];
      i += 2;
      while (i < lines.length && lines[i].trim().startsWith("|")) rows.push(cells(lines[i++]));
      i--;
      out.push(
        "<table><thead><tr>" + head.map((h) => "<th>" + inline(h) + "</th>").join("") +
        "</tr></thead><tbody>" +
        rows.map((r) => "<tr>" + r.map((c) => "<td>" + inline(c) + "</td>").join("") + "</tr>").join("") +
        "</tbody></table>"
      );
      continue;
    }

    const bullet = line.match(/^\s*[-*]\s+(.*)$/);
    const numbered = line.match(/^\s*\d+[.)]\s+(.*)$/);
    if (bullet || numbered) {
      flushPara(); flushQuote();
      const tag = bullet ? "ul" : "ol";
      if (!list || list.tag !== tag) { flushList(); list = { tag, items: [] }; }
      list.items.push("<li>" + inline((bullet || numbered)[1]) + "</li>");
      continue;
    }

    const bq = line.match(/^\s*>\s?(.*)$/);
    if (bq) { flushPara(); flushList(); quote.push(bq[1]); continue; }

    flushList(); flushQuote();
    para.push(line.trim());
  }
  flushAll();
  return out.join("");
}

function inline(s) {
  let t = esc(s);
  t = t.replace(/`([^`]+)`/g, (_, c) => "<code>" + c + "</code>");
  t = t.replace(/\[\[([^\[\]|]+?)(?:\|([^\[\]]*))?\]\]/g,
    (_, id, label) => '<a class="wikilink" data-gene="' + esc(id.trim()) + '">' +
      esc((label || id).trim()) + "</a>");
  t = t.replace(/\[([^\]]+)\]\(([^)]+)\)/g,
    (_, label, url) => '<a href="' + esc(url) + '" target="_blank" rel="noreferrer">' + label + "</a>");
  t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  return t;
}

/* ---------------- 載入 ---------------- */

async function loadMeta(keepProfile = true) {
  S.meta = await api("GET", "/api/state");
  $("#version").textContent = S.meta.version;
  $("#rootPath").textContent = S.meta.root;
  $("#rootPath").title = S.meta.root;
  $("#countSources").textContent = S.meta.source_count;
  $("#countProposals").textContent = S.meta.pending_proposals;
  $("#apiMode").textContent = S.meta.api_mode
    ? "API 模式可用" : "agent 模式（無 API key）";

  const sel = $("#profileSelect");
  const prev = keepProfile ? (S.profile || sel.value) : null;
  sel.innerHTML = S.meta.profiles
    .map((p) => '<option value="' + esc(p.id) + '">' + esc(p.name) +
      " (" + p.confirmed_count + ")</option>").join("");
  const ids = S.meta.profiles.map((p) => p.id);
  S.profile = ids.includes(prev) ? prev : (ids.includes("personal") ? "personal" : ids[0]);
  sel.value = S.profile;
  renderProfileMeta();
}

function renderProfileMeta() {
  const p = S.meta.profiles.find((x) => x.id === S.profile);
  $("#profileMeta").textContent = p
    ? (p.extends.length ? "繼承 " + p.extends.join(", ") : "沒有繼承其他 profile")
    : "";
}

async function loadProfile() {
  if (!S.profile) return;
  S.resolved = await api("GET", "/api/profiles/" + encodeURIComponent(S.profile));
  $("#countGenes").textContent = S.resolved.genes.length;
  renderChips();
  renderGeneList();
  if (S.selected && !S.resolved.genes.some((g) => g.id === S.selected)) {
    S.selected = null;
    renderDetail();
  }
}

/* ---------------- 規則庫 ---------------- */

function renderChips() {
  const counts = {};
  S.resolved.genes.forEach((g) => { counts[g.category] = (counts[g.category] || 0) + 1; });
  const chips = [['', '全部 (' + S.resolved.genes.length + ')']];
  S.meta.categories.forEach((c) => {
    if (counts[c.key]) chips.push([c.key, c.label + " (" + counts[c.key] + ")"]);
  });
  $("#categoryChips").innerHTML = chips.map(([key, label]) =>
    '<button class="chip' + (S.category === key ? " is-active" : "") +
    '" data-cat="' + esc(key) + '">' + esc(label) + "</button>").join("");
}

function visibleGenes() {
  const q = S.search.trim().toLowerCase();
  return S.resolved.genes.filter((g) => {
    if (S.category && g.category !== S.category) return false;
    if (!q) return true;
    return (g.title + " " + g.id + " " + g.body + " " + (g.tags || []).join(" "))
      .toLowerCase().includes(q);
  });
}

function renderGeneList() {
  const genes = visibleGenes();
  if (!genes.length) {
    $("#geneList").innerHTML =
      '<div class="empty card">沒有符合的規則。<br><span class="hint">' +
      "先去「參考資料」丟一份設計來源，讓 AI 幫你抽出規則。</span></div>";
    return;
  }
  $("#geneList").innerHTML = genes.map((g) => {
    const tags = [
      '<span class="tag tag-' + g.priority + '">' + PRIORITY_TAG[g.priority] + "</span>",
      g.status === "proposed" ? '<span class="tag tag-proposed">待確認</span>' : "",
      g.status === "deprecated" ? '<span class="tag tag-may">已淘汰</span>' : "",
      g.inherited_from ? '<span class="tag tag-inherited">繼承</span>' : "",
    ].join(" ");
    return '<button class="gene-item' + (S.selected === g.id ? " is-active" : "") +
      '" data-gene="' + esc(g.id) + '">' +
      '<div class="gene-item-top"><span class="gene-item-title">' + esc(g.title) +
      "</span>" + tags + "</div>" +
      '<div class="gene-item-sub">' + esc(catLabel(g.category)) +
      " · 信心 " + g.confidence + (g.links.length ? " · " + g.links.length + " 個連結" : "") +
      "</div></button>";
  }).join("");
}

function selectGene(id) {
  S.selected = id;
  renderGeneList();
  renderDetail();
  const el = $('.gene-item[data-gene="' + CSS.escape(id) + '"]');
  if (el) el.scrollIntoView({ block: "nearest" });
}

function renderDetail() {
  const pane = $("#geneDetail");
  if (!S.selected) {
    pane.innerHTML = '<div class="empty"><p>左邊選一條規則來看內容，' +
      "或按「＋ 新增規則」自己寫一條。</p></div>";
    return;
  }
  const g = S.resolved.genes.find((x) => x.id === S.selected);
  if (!g) { pane.innerHTML = '<div class="empty">找不到這條規則。</div>'; return; }

  const opts = (items, cur, keyName = "key", labelName = "label") =>
    items.map((it) => '<option value="' + esc(it[keyName]) + '"' +
      (it[keyName] === cur ? " selected" : "") + ">" + esc(it[labelName]) + "</option>").join("");

  const inherited = g.inherited_from
    ? '<p class="hint">這條繼承自 <code>' + esc(g.inherited_from) + '</code>。' +
      "在這裡儲存會建立一份覆寫，只影響目前的 profile。</p>"
    : "";

  const evidence = (g.evidence || []).length
    ? '<div class="field"><span class="field-label">證據</span><ul class="hint">' +
      g.evidence.map((e) => "<li>" + esc(e.detail || e.locator || e.source) + "</li>").join("") +
      "</ul></div>"
    : "";

  pane.innerHTML =
    '<input class="input grow" id="dTitle" value="' + esc(g.title) + '" style="font-size:17px;font-weight:600">' +
    inherited +
    '<div class="meta-grid">' +
      '<label class="field"><span class="field-label">分類</span><select id="dCategory">' +
        opts(S.meta.categories, g.category) + "</select></label>" +
      '<label class="field"><span class="field-label">強度</span><select id="dPriority">' +
        opts(S.meta.priorities, g.priority) + "</select></label>" +
      '<label class="field"><span class="field-label">狀態</span><select id="dStatus">' +
        opts(S.meta.statuses, g.status) + "</select></label>" +
      '<label class="field"><span class="field-label">信心度 <b id="dConfVal">' + g.confidence +
        '</b></span><input type="range" id="dConfidence" min="0" max="1" step="0.05" value="' +
        g.confidence + '"></label>' +
      '<label class="field"><span class="field-label">標籤（逗號分隔）</span>' +
        '<input class="input" id="dTags" value="' + esc((g.tags || []).join(", ")) + '"></label>' +
      '<label class="field"><span class="field-label">相關規則 id（逗號分隔）</span>' +
        '<input class="input" id="dRelated" value="' + esc((g.related || []).join(", ")) + '"></label>' +
    "</div>" +
    evidence +
    '<div class="tabs">' +
      '<button class="tab' + (S.editorTab === "edit" ? " is-active" : "") + '" data-tab="edit">編輯</button>' +
      '<button class="tab' + (S.editorTab === "preview" ? " is-active" : "") + '" data-tab="preview">預覽</button>' +
    "</div>" +
    (S.editorTab === "edit"
      ? '<textarea id="dBody" rows="22">' + esc(g.body) + "</textarea>"
      : '<div class="md" id="dPreview">' + md(g.body) + "</div>") +
    '<div class="detail-actions">' +
      '<button class="btn" id="dSave">儲存</button>' +
      '<span class="hint" style="align-self:center">id: <code>' + esc(g.id) + "</code></span>" +
      '<span class="spacer"></span>' +
      (g.inherited_from ? "" : '<button class="btn btn-ghost danger" id="dDelete">刪除</button>') +
    "</div>";

  $("#dConfidence")?.addEventListener("input", (e) => {
    $("#dConfVal").textContent = Number(e.target.value).toFixed(2);
  });
  $("#dSave").addEventListener("click", () => saveGene(g));
  $("#dDelete")?.addEventListener("click", () => deleteGene(g));
}

function collectGeneForm(base) {
  const list = (sel) => ($(sel)?.value || "").split(",").map((s) => s.trim()).filter(Boolean);
  return {
    id: base.id,
    title: $("#dTitle").value.trim() || base.title,
    category: $("#dCategory").value,
    priority: $("#dPriority").value,
    status: $("#dStatus").value,
    confidence: Number($("#dConfidence").value),
    tags: list("#dTags"),
    related: list("#dRelated"),
    evidence: base.evidence || [],
    body: S.editorTab === "edit" ? $("#dBody").value : base.body,
  };
}

async function saveGene(base) {
  try {
    const payload = collectGeneForm(base);
    await api("PUT", "/api/profiles/" + encodeURIComponent(S.profile) +
      "/genes/" + encodeURIComponent(base.id), payload);
    toast("已儲存 " + payload.title);
    await loadProfile();
    renderDetail();
  } catch (e) { toast(e.message, true); }
}

async function deleteGene(g) {
  if (!confirm("確定刪除「" + g.title + "」？這會刪掉對應的 .md 檔。")) return;
  try {
    await api("DELETE", "/api/profiles/" + encodeURIComponent(S.profile) +
      "/genes/" + encodeURIComponent(g.id));
    toast("已刪除");
    S.selected = null;
    await loadProfile();
    renderDetail();
  } catch (e) { toast(e.message, true); }
}

async function newGene() {
  const title = prompt("這條規則叫什麼？（例如：核心色票）");
  if (!title) return;
  try {
    const created = await api("POST", "/api/profiles/" + encodeURIComponent(S.profile) + "/genes", {
      title,
      category: S.category || "identity",
      priority: "should",
      status: "confirmed",
      confidence: 1,
      body: "## Rule\n\n\n\n## Rationale\n\n\n\n## Do\n\n```css\n\n```\n\n## Avoid\n\n```css\n\n```",
    });
    await loadProfile();
    selectGene(created.id);
    toast("已建立，把內容補上吧");
  } catch (e) { toast(e.message, true); }
}

/* ---------------- 參考資料 ---------------- */

function swatchRow(colors) {
  if (!colors?.length) return "";
  return '<div class="swatches swatch-row">' + colors.slice(0, 12).map((c) => {
    const hex = c.value || c.hex;
    return '<div class="swatch" style="background:' + esc(hex) + '" title="' +
      esc(hex + (c.count ? " ×" + c.count : "")) + '"><span>' + esc(hex.replace("#", "")) + "</span></div>";
  }).join("") + "</div>";
}

async function loadSources() {
  const data = await api("GET", "/api/sources");
  S.sources = data.sources;
  const el = $("#sourceList");
  if (!S.sources.length) {
    el.innerHTML = '<div class="card empty">還沒有任何參考資料。' +
      "上面那格丟一個資料夾路徑或網址試試。</div>";
    return;
  }
  el.innerHTML = S.sources.map((s) => {
    const stats = s.facts.code || s.facts.web || {};
    const colors = stats.colors || (s.facts.images?.images?.[0]?.palette || []);
    return '<div class="card">' +
      '<div class="view-head" style="margin-bottom:8px">' +
        "<h2 class=\"card-title\">" + esc(s.origin) + "</h2>" +
        '<button class="btn btn-ghost btn-sm danger" data-del-source="' + esc(s.id) + '">刪除</button>' +
      "</div>" +
      '<div class="hint">' + esc(s.id) + " · " + esc(s.kind) + " · profile " +
        esc(s.profile) + (s.note ? " · " + esc(s.note) : "") + "</div>" +
      "<ul class=\"hint\">" + s.summary.map((l) => "<li>" + esc(l) + "</li>").join("") + "</ul>" +
      (s.cited_by.length
        ? '<p class="hint">被 <b>' + s.cited_by.length + "</b> 條規則當作證據：" +
          s.cited_by.map((c) => "<code>" + esc(c) + "</code>").join(" ") + "</p>"
        : "") +
      (s.integrity.length
        ? '<p class="hint danger">原件有問題：' + s.integrity.map(esc).join("、") + "</p>"
        : "") +
      swatchRow(colors) +
    "</div>";
  }).join("");
}

async function doIngest() {
  const target = $("#ingestTarget").value.trim();
  if (!target) { toast("請先填路徑或網址", true); return; }
  const btn = $("#ingestBtn");
  btn.disabled = true;
  $("#ingestHint").textContent = "分析中…（掃描檔案、抽色票、算字級）";
  try {
    const src = await api("POST", "/api/ingest", {
      target, profile: S.profile, note: $("#ingestNote").value.trim(),
      keep_raw: !$("#ingestNoRaw").checked,
    });
    toast("已登錄 " + src.id);
    $("#ingestTarget").value = "";
    $("#ingestNote").value = "";
    $("#ingestHint").textContent = src.summary.join(" · ");
    await loadSources();
    await loadMeta();
  } catch (e) {
    $("#ingestHint").textContent = "";
    toast(e.message, true);
  } finally { btn.disabled = false; }
}

async function doAnalyze() {
  const btn = $("#analyzeBtn");
  btn.disabled = true;
  try {
    const res = await api("POST", "/api/analyze", { profile: S.profile });
    if (res.mode === "api") {
      toast("AI 已產生 " + res.proposal.genes.length + " 條提案");
      await loadMeta();
      switchView("proposals");
      await loadProposals();
      return;
    }
    const cmd = '請讀取 "' + res.task_path + '" 並照裡面的指示完成分析。';
    await navigator.clipboard.writeText(cmd).catch(() => {});
    alert("任務包已產生，指令已複製到剪貼簿：\n\n" + cmd +
      "\n\n把它貼給你的 coding agent（Claude Code / Codex / Cursor），" +
      "agent 寫回提案後回到「AI 提案」分頁確認。");
  } catch (e) { toast(e.message, true); } finally { btn.disabled = false; }
}

/* ---------------- 提案 ---------------- */

async function loadProposals() {
  const data = await api("GET", "/api/proposals");
  S.proposals = data.proposals;
  const sel = $("#proposalSelect");
  sel.innerHTML = S.proposals.map((p) =>
    '<option value="' + esc(p.id) + '">' + esc(p.id) + " — " + p.genes.length +
    " 條 · " + esc(p.status) + "</option>").join("");
  if (!S.proposals.length) {
    $("#proposalBody").innerHTML = '<div class="card empty">' +
      "還沒有提案。去「參考資料」按「產生 AI 分析任務包」，" +
      "讓 agent 幫你把風格整理成規則。</div>";
    return;
  }
  S.proposal = S.proposals.find((p) => p.id === sel.value) || S.proposals[0];
  sel.value = S.proposal.id;
  renderProposal();
}

function renderProposal() {
  const p = S.proposal;
  const profileOpts = S.meta.profiles.map((x) =>
    '<option value="' + esc(x.id) + '"' + (x.id === p.profile ? " selected" : "") +
    ">" + esc(x.name) + "</option>").join("");

  $("#proposalBody").innerHTML =
    '<div class="card"><div class="form-row">' +
      '<label class="field"><span class="field-label">寫入哪個 profile</span>' +
        '<select id="applyProfile">' + profileOpts + "</select></label>" +
      '<div style="flex:1"></div>' +
      '<button class="btn btn-ghost" id="selectAllBtn">全選 / 全不選</button>' +
      '<button class="btn" id="applyBtn">套用選取的規則</button>' +
    "</div>" +
    '<p class="hint">來源：' + esc((p.sources || []).join(", ") || "—") +
      " · 狀態：" + esc(p.status) + "</p></div>" +
    p.genes.map((g, i) =>
      '<div class="proposal-gene">' +
        '<label class="proposal-head">' +
          '<input type="checkbox" data-gene-check="' + esc(g.id) + '"' +
            (g.decision === "reject" ? "" : " checked") + ">" +
          '<span class="tag tag-' + esc(g.priority) + '">' +
            (PRIORITY_TAG[g.priority] || "") + "</span>" +
          "<strong>" + esc(g.title) + "</strong>" +
          '<span class="hint">' + esc(catLabel(g.category)) + "</span>" +
          '<span style="flex:1"></span>' +
          '<span class="confidence">信心 ' + (g.confidence ?? "-") + "</span>" +
          '<button class="btn btn-ghost btn-sm" data-toggle="' + i + '">展開</button>' +
        "</label>" +
        '<div class="proposal-body md" data-body="' + i + '" hidden>' + md(g.body) + "</div>" +
      "</div>").join("");

  $("#applyBtn").addEventListener("click", applyProposal);
  $("#selectAllBtn").addEventListener("click", () => {
    const boxes = $$("[data-gene-check]");
    const allOn = boxes.every((b) => b.checked);
    boxes.forEach((b) => { b.checked = !allOn; });
  });
}

async function applyProposal() {
  const accept = $$("[data-gene-check]").filter((b) => b.checked)
    .map((b) => b.dataset.geneCheck);
  if (!accept.length && !confirm("一條都沒選，確定要繼續嗎？")) return;
  try {
    const res = await api("POST", "/api/proposals/" +
      encodeURIComponent(S.proposal.id) + "/apply",
      { accept, profile: $("#applyProfile").value });
    toast("已寫入 " + res.written.length + " 條到 " + res.profile);
    S.profile = res.profile;
    await loadMeta();
    $("#profileSelect").value = S.profile;
    await loadProfile();
    await loadProposals();
    switchView("genes");
  } catch (e) { toast(e.message, true); }
}

/* ---------------- 匯出 ---------------- */

async function loadExport() {
  try {
    const data = await api("GET", "/api/export?profile=" +
      encodeURIComponent(S.profile) + "&mode=" + encodeURIComponent($("#exportMode").value));
    $("#exportPreview").textContent = data.text;
    $("#exportHint").innerHTML =
      "已確認 <b>" + data.confirmed + "</b> 條規則會被匯出（共 " + data.total +
      " 條，proposed 與 deprecated 不匯出）。<br>寫入位置：<code>" +
      esc(data.out_dir) + "</code><br>" +
      "把整個資料夾複製到目標專案根目錄，任何讀 AGENTS.md 的 agent 都會吃到這份設計 DNA。";
  } catch (e) { toast(e.message, true); }
}

async function writeExport() {
  try {
    const res = await api("POST", "/api/export",
      { profile: S.profile, mode: $("#exportMode").value });
    toast("已寫入 " + res.count + " 個檔案到 " + res.out_dir);
  } catch (e) { toast(e.message, true); }
}

/* ---------------- 導覽 ---------------- */

function switchView(name) {
  $$(".nav-item").forEach((b) => b.classList.toggle("is-active", b.dataset.view === name));
  $$(".view").forEach((v) => v.classList.toggle("is-active", v.dataset.view === name));
  if (name === "sources") loadSources();
  if (name === "proposals") loadProposals();
  if (name === "export") loadExport();
}

/* ---------------- 事件綁定 ---------------- */

function wire() {
  $("#nav").addEventListener("click", (e) => {
    const btn = e.target.closest(".nav-item");
    if (btn) switchView(btn.dataset.view);
  });

  $("#profileSelect").addEventListener("change", async (e) => {
    S.profile = e.target.value;
    S.selected = null;
    renderProfileMeta();
    await loadProfile();
    renderDetail();
  });

  $("#categoryChips").addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (!chip) return;
    S.category = chip.dataset.cat;
    renderChips();
    renderGeneList();
  });

  $("#geneList").addEventListener("click", (e) => {
    const item = e.target.closest(".gene-item");
    if (item) selectGene(item.dataset.gene);
  });

  $("#geneDetail").addEventListener("click", (e) => {
    const tab = e.target.closest(".tab");
    if (tab) {
      // 切到預覽前先把編輯中的內容存進 state，才不會打字打一半消失
      if (S.editorTab === "edit" && $("#dBody")) {
        const g = S.resolved.genes.find((x) => x.id === S.selected);
        if (g) g.body = $("#dBody").value;
      }
      S.editorTab = tab.dataset.tab;
      renderDetail();
      return;
    }
    const link = e.target.closest(".wikilink");
    if (link) {
      const target = link.dataset.gene;
      if (S.resolved.genes.some((g) => g.id === target)) selectGene(target);
      else toast("還沒有 `" + target + "` 這條規則", true);
    }
  });

  $("#geneSearch").addEventListener("input", (e) => {
    S.search = e.target.value;
    renderGeneList();
  });

  $("#newGeneBtn").addEventListener("click", newGene);
  $("#ingestBtn").addEventListener("click", doIngest);
  $("#ingestTarget").addEventListener("keydown", (e) => { if (e.key === "Enter") doIngest(); });
  $("#analyzeBtn").addEventListener("click", doAnalyze);

  $("#sourceList").addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-del-source]");
    if (!btn) return;
    const url = "/api/sources/" + encodeURIComponent(btn.dataset.delSource);
    if (!confirm("刪除這份參考資料與它的留底原件？")) return;
    try {
      try {
        await api("DELETE", url);
      } catch (err) {
        // 409 = 有規則拿它當證據。講清楚代價，讓使用者自己決定
        if (err.status !== 409) throw err;
        if (!confirm(err.message + "\n\n仍然要刪除嗎？")) return;
        await api("DELETE", url + "?force=1");
      }
      toast("已刪除");
      await loadSources();
      await loadMeta();
    } catch (err) { toast(err.message, true); }
  });

  $("#proposalSelect").addEventListener("change", (e) => {
    S.proposal = S.proposals.find((p) => p.id === e.target.value);
    renderProposal();
  });

  $("#proposalBody").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-toggle]");
    if (!btn) return;
    e.preventDefault();
    const body = $('[data-body="' + btn.dataset.toggle + '"]');
    body.hidden = !body.hidden;
    btn.textContent = body.hidden ? "展開" : "收合";
  });

  $("#exportMode").addEventListener("change", loadExport);
  $("#writeExportBtn").addEventListener("click", writeExport);
  $("#copyExportBtn").addEventListener("click", async () => {
    await navigator.clipboard.writeText($("#exportPreview").textContent);
    toast("已複製 AGENTS.md 內容");
  });

  $("#newProfileBtn").addEventListener("click", () => $("#profileDialog").showModal());
  $("#npCreate").addEventListener("click", async (e) => {
    e.preventDefault();
    const id = $("#npId").value.trim();
    if (!id) { toast("id 不能空白", true); return; }
    try {
      await api("POST", "/api/profiles", {
        id,
        name: $("#npName").value.trim() || id,
        description: $("#npDesc").value.trim(),
        extends: $("#npExtends").value.trim(),
      });
      $("#profileDialog").close();
      S.profile = id;
      await loadMeta();
      $("#profileSelect").value = id;
      await loadProfile();
      toast("已建立 profile " + id);
    } catch (err) { toast(err.message, true); }
  });

  $("#delProfileBtn").addEventListener("click", async () => {
    if (!confirm("刪除 profile「" + S.profile + "」與它底下所有規則？")) return;
    try {
      await api("DELETE", "/api/profiles/" + encodeURIComponent(S.profile));
      S.profile = null;
      await loadMeta(false);
      await loadProfile();
      toast("已刪除");
    } catch (e) { toast(e.message, true); }
  });
}

/* ---------------- 啟動 ---------------- */

(async function start() {
  wire();
  try {
    await loadMeta();
    await loadProfile();
  } catch (e) {
    toast("載入失敗：" + e.message, true);
  }
})();
