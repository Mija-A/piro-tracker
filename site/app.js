/* Production Tracker front-end.
 * Fetches config.json (business rules: departments, metals, grouping, thresholds)
 * and data.json (orders + stage journeys, rebuilt by CI every 10 minutes),
 * renders everything client-side, and soft-refreshes the data on a timer
 * without reloading the page or losing the user's place. */
"use strict";

let CONFIG = null;
let DETAIL = {};            // code -> order record (enriched with dept, display due)
let GENERATED_AT = null;    // ISO timestamp from data.json
let CURRENT_VIEW = { type: "home" };
let PENDING_DATA = null;    // refresh that arrived while an overlay was open

// ---------- tiny helpers ----------
function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}
function deptId(name) { return name.replace(/[^A-Za-z0-9]/g, ""); }
function overlayOpen() {
  return document.getElementById("ov").classList.contains("open") ||
         document.getElementById("ovr").classList.contains("open");
}

// ---------- config-driven lookups ----------
function deptOf(stage) {
  const s = (stage || "").trim();
  for (const d of CONFIG.departments) if (d.stages.includes(s)) return d.name;
  return "Other";
}
function deptConfig(name) {
  return CONFIG.departments.find(d => d.name === name) || null;
}
function splitMetals(s) {
  return (s || "").split(/[;,]/).map(t => t.trim()).filter(Boolean);
}
function metalColor(token) {
  const t = (token || "").toLowerCase();
  for (const [key, c] of Object.entries(CONFIG.metalColors)) {
    if (t.includes(key)) return c;
  }
  return CONFIG.metalFallback;
}
function metalGroupKey(s) {
  const toks = splitMetals(s);
  return toks.length ? toks.join(", ") : "No metal";
}
function metalPillHtml(s) {
  const toks = splitMetals(s);
  if (!toks.length) return '<span class="mpill mpill-none">No metal</span>';
  const n = toks.length;
  let segs = "";
  toks.forEach((t, i) => {
    const c = metalColor(t);
    const rl = i === 0 ? "10px" : "0", rr = i === n - 1 ? "10px" : "0";
    segs += `<span class="mseg" style="background:${c.bg};color:${c.fg};` +
      `border-top-left-radius:${rl};border-bottom-left-radius:${rl};` +
      `border-top-right-radius:${rr};border-bottom-right-radius:${rr};">${esc(t)}</span>`;
  });
  return `<span class="mpill">${segs}</span>`;
}
function metalGroupSortKey(gkey) {
  const toks = splitMetals(gkey);
  if (toks.length === 1) {
    const t = toks[0].toLowerCase();
    const i = CONFIG.metalOrder.findIndex(name => t.includes(name));
    return i >= 0 ? [0, i, gkey] : [2, 0, gkey];
  }
  return [1, 0, gkey];
}
function cmpKeys(a, b) {
  for (let i = 0; i < a.length; i++) {
    if (a[i] < b[i]) return -1;
    if (a[i] > b[i]) return 1;
  }
  return 0;
}

// ---------- formatting ----------
function fmtDue(iso) {          // "2026-10-01" -> "10/1"
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || "");
  return m ? `${parseInt(m[2], 10)}/${parseInt(m[3], 10)}` : "";
}
function fmtET(utc) {           // journal stamp "YYYY-MM-DD HH:MM" (UTC) -> ET
  try {
    const d = new Date(utc.replace(" ", "T") + ":00Z");
    return d.toLocaleString("en-US", { timeZone: "America/New_York",
      month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) + " ET";
  } catch (e) { return utc + " UTC"; }
}
function fmtGeneratedET(iso) {
  try {
    return new Date(iso).toLocaleString("en-US", { timeZone: "America/New_York",
      month: "short", day: "numeric", year: "numeric",
      hour: "numeric", minute: "2-digit" }) + " ET";
  } catch (e) { return iso; }
}
function daysUntil(iso) {
  if (!iso) return null;
  const t = new Date(iso + "T00:00:00");
  const now = new Date(); now.setHours(0, 0, 0, 0);
  return Math.round((t - now) / 86400000);
}
function dueSortKey(o) { return o.due ? [0, o.due] : [1, ""]; }
function isStuck(days) { return typeof days === "number" && days >= CONFIG.stuckDays; }
function isSubJO(code) { return /^JO-\d+-\d+/.test(code || ""); }
function personKey(o) { return (o.assigned || "").trim() || "Unassigned"; }

// ---------- data intake ----------
function applyData(data) {
  const saved = captureViewState();
  GENERATED_AT = data.generated_at;
  DETAIL = {};
  for (const r of data.orders) {
    if (CONFIG.staleDays && typeof r.days === "number" && r.days >= CONFIG.staleDays) continue;
    DETAIL[r.code] = Object.assign({}, r, { dept: deptOf(r.stage), dueDisp: fmtDue(r.due) });
  }
  renderAll();
  restoreViewState(saved);
  paintHeader();
}
function paintHeader() {
  document.getElementById("updatedAt").textContent = fmtGeneratedET(GENERATED_AT);
  const banner = document.getElementById("staleBanner");
  const ageMin = (Date.now() - new Date(GENERATED_AT).getTime()) / 60000;
  if (ageMin > CONFIG.staleDataMinutes) {
    banner.textContent = `This data is ${Math.round(ageMin)} minutes old - the update pipeline may be failing. Showing the last successful pull.`;
    banner.hidden = false;
  } else {
    banner.hidden = true;
  }
}

// ---------- rendering: shared row pieces ----------
const COLHEAD =
  '<div class="jo jom colhead">' +
  '<span class="thumbcell thumbhead">Image</span>' +
  '<span class="code">JO</span>' +
  '<span class="cust">Customer</span>' +
  '<span class="metalcell">Metal</span>' +
  '<span class="duecell">Due date</span>' +
  '<span class="days">Days in service</span></div>';

function thumbCell(o) {
  const url = (o.img || "").trim();
  if (url) {
    return `<span class="thumbcell"><img class="thumb" src="${esc(url)}" loading="lazy" ` +
      `onerror="this.parentElement.classList.add('noimg');this.remove();"></span>`;
  }
  return '<span class="thumbcell noimg"></span>';
}
function joRow(o, extraAttrs) {
  const stuck = isStuck(o.days) ? " stuck" : "";
  return `<div class="jo jom${stuck}" data-card="${esc(o.code)}"${extraAttrs || ""}>` +
    thumbCell(o) +
    `<span class="code">${esc(o.code)}</span>` +
    `<span class="cust">${esc((o.cust || "").slice(0, 24))}</span>` +
    `<span class="metalcell">${metalPillHtml(o.metal)}</span>` +
    `<span class="duecell">${o.dueDisp}</span>` +
    `<span class="days">${o.days != null ? o.days : ""}d</span></div>`;
}

// Report buttons for a stage. The green service report always shows; the coral
// employee report shows whenever any order in the stage has an assigned worker
// (data-driven - not tied to which layout the stage uses).
function reportBar(stage, olist) {
  const codes = esc(olist.map(o => o.code).join(","));
  let html = `<div class="reportbar"><button class="reportbtn" data-report="service" ` +
    `data-stage="${esc(stage)}" data-codes="${codes}">Generate customized service report</button>`;
  if (olist.some(o => (o.assigned || "").trim())) {
    html += `<button class="reportbtn reportbtn-emp" data-report="employee" ` +
      `data-stage="${esc(stage)}" data-codes="${codes}">Generate employee-specific report</button>`;
  }
  return html + "</div>";
}
function stageShell(stage, count, bodyHtml, extraCls) {
  return `<div class="stage collapsed${extraCls || ""}">` +
    `<div class="stage-h"><span class="stage-caret">&#9656;</span>` +
    `<span class="stage-name">${esc(stage)}</span>` +
    `<span class="stage-n">${count}</span></div>` +
    `<div class="stage-body">${bodyHtml}</div></div>`;
}

// ---------- rendering: stage layouts ----------
function renderStageFlat(stage, olist) {
  const sorted = [...olist].sort((a, b) => (b.days || 0) - (a.days || 0));
  const body = reportBar(stage, olist) + COLHEAD + sorted.map(o => joRow(o)).join("");
  return stageShell(stage, olist.length, body);
}
function renderStageByMetal(stage, olist) {
  const buckets = {};
  for (const o of olist) (buckets[metalGroupKey(o.metal)] = buckets[metalGroupKey(o.metal)] || []).push(o);
  let inner = reportBar(stage, olist) + COLHEAD;
  const keys = Object.keys(buckets).sort((a, b) => cmpKeys(metalGroupSortKey(a), metalGroupSortKey(b)));
  for (const gkey of keys) {
    const items = buckets[gkey].sort((a, b) => cmpKeys(dueSortKey(a), dueSortKey(b)));
    inner += `<div class="mgroup"><div class="mgroup-h"><span class="mgroup-n">${items.length}</span></div>` +
      items.map(o => joRow(o)).join("") + "</div>";
  }
  return stageShell(stage, olist.length, inner);
}
function renderStageByPerson(stage, olist) {
  const buckets = {};
  for (const o of olist) (buckets[personKey(o)] = buckets[personKey(o)] || []).push(o);
  const people = Object.keys(buckets).sort((a, b) =>
    a === "Unassigned" ? 1 : b === "Unassigned" ? -1 : a.toLowerCase().localeCompare(b.toLowerCase()));

  let opts = '<option value="__all__">All employees</option>';
  for (const name of people) opts += `<option value="${esc(name)}">${esc(name)} (${buckets[name].length})</option>`;

  const controls =
    '<div class="pfilters">' +
    `<label class="pf">Employee <select data-filter="person">${opts}</select></label>` +
    '<label class="pf">Due <select data-filter="due">' +
    '<option value="__all__">Any date</option>' +
    '<option value="overdue">Overdue</option>' +
    '<option value="7">Next 7 days</option>' +
    '<option value="14">Next 14 days</option>' +
    "</select></label></div>";

  let inner = controls + reportBar(stage, olist);
  for (const name of people) {
    const items = buckets[name].sort((a, b) => cmpKeys(dueSortKey(a), dueSortKey(b)));
    const rows = items.map(o =>
      joRow(o, ` data-person="${esc(personKey(o))}" data-due="${esc(o.due || "")}"`)).join("");
    inner += `<div class="pgroup collapsed" data-person="${esc(name)}">` +
      `<div class="pgroup-h"><span class="pgroup-caret">&#9656;</span>` +
      `<span class="pgroup-name">${esc(name)}</span>` +
      `<span class="pgroup-n">${items.length}</span></div>` +
      `<div class="pgroup-body">${COLHEAD}${rows}</div></div>`;
  }
  return stageShell(stage, olist.length, inner, " personmode");
}

// ---------- rendering: page ----------
function renderAll() {
  const rows = Object.values(DETAIL);
  const grouped = {};   // dept -> stage -> [orders]
  for (const o of rows) {
    const stage = (o.stage || "(no stage)").trim();
    ((grouped[o.dept] = grouped[o.dept] || {})[stage] = grouped[o.dept][stage] || []).push(o);
  }

  const inclSub = document.getElementById("inclSub");
  const paintTotal = () => {
    const on = inclSub && inclSub.checked;
    const n = on ? rows.length : rows.filter(o => !isSubJO(o.code)).length;
    document.getElementById("statTotal").textContent = n;
  };
  if (inclSub && !inclSub.dataset.wired) { inclSub.addEventListener("change", paintTotal); inclSub.dataset.wired = "1"; }
  paintTotal();
  document.getElementById("statStuck").textContent = rows.filter(o => isStuck(o.days)).length;
  document.getElementById("statStuckLabel").textContent = CONFIG.stuckDays;

  const deptOrder = CONFIG.departments.map(d => d.name).concat(["Other"]);
  let boxes = "", panels = "";
  for (const d of deptOrder) {
    if (!grouped[d]) continue;
    const drows = Object.values(grouped[d]).flat();
    const dstuck = drows.filter(o => isStuck(o.days)).length;
    const did = deptId(d);
    boxes += `<button class="box" data-dept="${did}"><div class="bname">${esc(d)}</div>` +
      `<div class="bnum">${drows.length}</div><div class="bsub">${dstuck} stuck</div></button>`;

    const cfg = deptConfig(d);
    const metalMode = !!(cfg && cfg.groupBy === "metal");
    const stages = Object.keys(grouped[d]).sort((a, b) => grouped[d][b].length - grouped[d][a].length);
    let stagesHtml = "";
    for (const stage of stages) {
      const olist = grouped[d][stage];
      if (CONFIG.personGroupedStages.includes(stage)) stagesHtml += renderStageByPerson(stage, olist);
      else if (metalMode) stagesHtml += renderStageByMetal(stage, olist);
      else stagesHtml += renderStageFlat(stage, olist);
    }
    panels += `<div class="deptpanel${metalMode ? " metalgrp" : ""}" id="dept-${did}" data-dept-name="${esc(d)}">` +
      `<button class="back">&#8592; All departments</button>` +
      `<div class="dp-h"><span class="dp-name">${esc(d)}</span><span class="dp-n">${drows.length}</span></div>` +
      stagesHtml + "</div>";
  }
  document.getElementById("boxes").innerHTML = boxes;
  document.getElementById("panels").innerHTML = panels;
}

// ---------- view state across soft refreshes ----------
function currentOpenPanel() {
  const p = document.querySelector(".deptpanel.open");
  if (p) return p;
  const pv = document.getElementById("personView");
  return pv.classList.contains("open") ? pv : null;
}
function captureViewState() {
  const st = { view: Object.assign({}, CURRENT_VIEW), scroll: window.scrollY || 0,
               stages: [], groups: [], filters: {} };
  const panel = currentOpenPanel();
  if (!panel) return st;
  panel.querySelectorAll(".stage").forEach(s => {
    const nm = s.querySelector(".stage-name");
    if (!nm) return;
    const name = nm.textContent.trim();
    if (!s.classList.contains("collapsed")) st.stages.push(name);
    const sels = s.querySelectorAll(".pf select");
    if (sels.length) {
      const f = {};
      sels.forEach(sel => { f[sel.dataset.filter] = sel.value; });
      if (Object.values(f).some(v => v !== "__all__")) st.filters[name] = f;
    }
  });
  panel.querySelectorAll(".pgroup:not(.collapsed)").forEach(g => {
    if (g.dataset.person) st.groups.push(g.dataset.person);
  });
  return st;
}
function restoreViewState(st) {
  if (!st || !st.view || st.view.type === "home") { showBoxes(); return; }
  if (st.view.type === "dept") {
    const panel = document.getElementById("dept-" + st.view.id);
    if (!panel) { showBoxes(); return; }
    openDept(st.view.id, false);
    panel.querySelectorAll(".stage").forEach(s => {
      const nm = s.querySelector(".stage-name");
      const name = nm ? nm.textContent.trim() : "";
      if (st.stages.includes(name)) s.classList.remove("collapsed");
      const f = st.filters[name];
      if (f) {
        s.querySelectorAll(".pf select").forEach(sel => {
          const v = f[sel.dataset.filter];
          if (v && [...sel.options].some(op => op.value === v)) sel.value = v;
          s.dataset[sel.dataset.filter] = sel.value;
        });
        applyPersonFilters(s);
      }
    });
    panel.querySelectorAll(".pgroup").forEach(g => {
      if (st.groups.includes(g.dataset.person)) g.classList.remove("collapsed");
    });
  } else if (st.view.type === "person") {
    renderPersonResults(st.view.name, false);
  }
  if (st.scroll) window.scrollTo(0, st.scroll);
}

// ---------- navigation ----------
function openDept(id, push) {
  document.getElementById("boxesWrap").style.display = "none";
  document.getElementById("personView").classList.remove("open");
  document.querySelectorAll(".deptpanel").forEach(p => p.classList.remove("open"));
  const panel = document.getElementById("dept-" + id);
  if (!panel) { showBoxes(); return; }
  panel.classList.add("open");
  panel.querySelectorAll(".stage").forEach(s => s.classList.add("collapsed"));
  panel.querySelectorAll(".pgroup").forEach(g => g.classList.add("collapsed"));
  window.scrollTo(0, 0);
  CURRENT_VIEW = { type: "dept", id: id };
  if (push !== false) history.pushState({ view: "dept" }, "");
}
function closeDept() {
  if (history.state && history.state.view === "dept") { history.back(); return; }
  showBoxes();
}
function showBoxes() {
  document.querySelectorAll(".deptpanel").forEach(p => p.classList.remove("open"));
  document.getElementById("personView").classList.remove("open");
  document.getElementById("boxesWrap").style.display = "";
  CURRENT_VIEW = { type: "home" };
}

// ---------- person filters ----------
function applyPersonFilters(stage) {
  const pv = stage.dataset.person || "__all__";
  const dv = stage.dataset.due || "__all__";
  stage.querySelectorAll(".jo.jom:not(.colhead)").forEach(jo => {
    let ok = true;
    if (pv !== "__all__") ok = (jo.dataset.person === pv);
    if (ok && dv !== "__all__") {
      const du = daysUntil(jo.dataset.due);
      if (dv === "overdue") ok = (du !== null && du < 0);
      else ok = (du !== null && du >= 0 && du <= parseInt(dv, 10));
    }
    jo.style.display = ok ? "" : "none";
  });
  const filtering = (pv !== "__all__") || (dv !== "__all__");
  stage.querySelectorAll(".pgroup").forEach(g => {
    const vis = [...g.querySelectorAll(".jo.jom:not(.colhead)")].filter(j => j.style.display !== "none").length;
    const n = g.querySelector(".pgroup-n");
    if (n) n.textContent = vis;
    g.style.display = vis ? "" : "none";
    g.classList.toggle("collapsed", !filtering);
  });
  const total = [...stage.querySelectorAll(".jo.jom:not(.colhead)")].filter(j => j.style.display !== "none").length;
  stage.querySelector(".stage-n").textContent = total;
}

// ---------- order card ----------
function showCard(code) {
  const d = DETAIL[code];
  if (!d) return;
  let j = "";
  if (d.journey && d.journey.length) {
    d.journey.forEach((s, i) => {
      const cur = i === d.journey.length - 1 ? " cur" : "";
      j += `<div class="jrow${cur}"><div class="jdot"></div><div>` +
        `<div class="jstage">${esc(s.stage)}</div>` +
        `<div class="jsince">since ${fmtET(s.since)}</div></div></div>`;
    });
  } else {
    j = `<div class="jrow cur"><div class="jdot"></div><div>` +
      `<div class="jstage">${esc(d.stage)}</div><div class="jsince">current</div></div></div>`;
  }
  const note = (!d.journey || d.journey.length < 2)
    ? '<div class="jnote">Journey builds as this order moves through stages.</div>' : "";
  const img = d.img
    ? `<img class="pimg" src="${esc(d.img)}" loading="lazy" onerror="this.style.display='none'">` : "";
  const days = d.days != null ? d.days + " days" : "—";
  const info = '<div class="pinfo">' +
    `<div><div class="k">Current stage</div><div class="val">${esc(d.stage) || "—"}</div></div>` +
    `<div><div class="k">Days in stage</div><div class="val">${days}</div></div>` +
    `<div><div class="k">Due date</div><div class="val">${d.dueDisp || "—"}</div></div>` +
    `<div><div class="k">Metal</div><div class="val">${esc(d.metal) || "—"}</div></div>` +
    `<div><div class="k">Assigned to</div><div class="val">${esc(d.assigned) || "—"}</div></div>` +
    "</div>";
  const cardReport = `<div class="reportbar" style="padding:2px 0 18px;">` +
    `<button class="reportbtn" data-report="service" data-stage="${esc(code)}" ` +
    `data-codes="${esc(code)}">Create customized report</button></div>`;
  document.getElementById("panel").innerHTML = img + `<div class="pbody">` +
    `<div class="pcode">${esc(code)}</div><div class="pcust">${esc(d.cust)}</div>` +
    `<div class="pdept">${esc(d.dept)}</div>` + cardReport + info +
    `<div class="jhead">Journey</div>` + j + note +
    `<div class="pclose">Close</div></div>`;
  document.getElementById("ov").classList.add("open");
}
function closeCard() {
  document.getElementById("ov").classList.remove("open");
  flushPendingData();
}

// ---------- search ----------
function doSearch() {
  const q = document.getElementById("q").value.trim().toLowerCase();
  if (!q) return;
  const codes = Object.keys(DETAIL);
  const hit = codes.find(c => c.toLowerCase() === q) || codes.find(c => c.toLowerCase().includes(q));
  if (hit) showCard(hit);
}
function normName(s) { return (s || "").trim().toLowerCase(); }
function doPersonSearch() {
  const q = normName(document.getElementById("qp").value);
  if (!q) return;
  const names = {};
  Object.values(DETAIL).forEach(d => {
    const a = (d.assigned || "").trim();
    if (a) names[a] = (names[a] || 0) + 1;
  });
  const allNames = Object.keys(names);
  let target = allNames.find(n => normName(n) === q);
  if (!target) {
    target = allNames.filter(n => normName(n).includes(q)).sort((a, b) => names[b] - names[a])[0];
  }
  renderPersonResults(target);
}
function renderPersonResults(name, push) {
  const view = document.getElementById("personView");
  if (!name) {
    view.innerHTML = '<button class="pv-back">&#8592; Back</button>' +
      '<div class="pv-h"><div class="pv-name">No match</div></div>' +
      '<div class="pr-none">No employee found by that name. Try a first or last name as it appears in the system.</div>';
    showPersonView(push);
    return;
  }
  const items = Object.values(DETAIL).filter(d => (d.assigned || "").trim() === name);
  const byStage = {};
  items.forEach(it => { const s = it.stage || "(no stage)"; (byStage[s] = byStage[s] || []).push(it); });
  const stages = Object.keys(byStage).sort((a, b) => byStage[b].length - byStage[a].length);
  const colhead = '<div class="pr-row colhead">' +
    '<span class="thumbcell thumbhead">Image</span>' +
    '<span class="code">JO</span>' +
    '<span class="cust">Customer</span>' +
    '<span class="metalcell">Metal</span>' +
    '<span class="duecell">Due date</span>' +
    '<span class="days">Days in service</span></div>';
  let body = "";
  stages.forEach(s => {
    const rows = byStage[s].sort((a, b) => (a.due || "").localeCompare(b.due || ""));
    let r = "";
    rows.forEach(it => {
      const stuck = isStuck(it.days) ? " stuck" : "";
      r += `<div class="pr-row" data-card="${esc(it.code)}">` + thumbCell(it) +
        `<span class="code">${esc(it.code)}</span>` +
        `<span class="cust">${esc(it.cust)}</span>` +
        `<span class="metalcell">${metalPillHtml(it.metal)}</span>` +
        `<span class="duecell">${it.dueDisp || ""}</span>` +
        `<span class="days${stuck}">${it.days != null ? it.days + "d" : ""}</span></div>`;
    });
    body += `<div class="pr-stage">${esc(s)} &middot; ${byStage[s].length}</div>` + colhead + r;
  });
  const pcodes = esc(items.map(it => it.code).join(","));
  const rbar = `<div class="reportbar"><button class="reportbtn reportbtn-emp" data-report="employee" ` +
    `data-stage="${esc(name)}" data-codes="${pcodes}" data-lock="${esc(name)}">` +
    "Generate employee-specific report</button></div>";
  view.innerHTML = '<button class="pv-back">&#8592; Back</button>' +
    `<div class="pv-h"><div class="pv-name">${esc(name)}</div>` +
    `<div class="pv-sub">${items.length} active ${items.length === 1 ? "order" : "orders"}` +
    ` across ${stages.length} ${stages.length === 1 ? "stage" : "stages"}</div></div>` + rbar + body;
  CURRENT_VIEW = { type: "person", name: name };
  showPersonView(push);
}
function showPersonView(push) {
  document.querySelectorAll(".deptpanel").forEach(p => p.classList.remove("open"));
  document.getElementById("boxesWrap").style.display = "none";
  document.getElementById("personView").classList.add("open");
  window.scrollTo(0, 0);
  if (push !== false) history.pushState({ view: "person" }, "");
}
function closePerson() {
  document.getElementById("personView").classList.remove("open");
  showBoxes();
}

// ---------- report builder ----------
const REPORT_COLS = [
  ["image", "Image", null],
  ["jo", "JO #", d => d.code],
  ["cust", "Customer", d => d.cust || ""],
  ["service", "Service", d => d.stage || ""],
  ["dept", "Department", d => d.dept || ""],
  ["assigned", "Assigned to", d => d.assigned || ""],
  ["metal", "Metal", d => d.metal || ""],
  ["due", "Due date", d => d.due || ""],
  ["days", "Days in service", d => (d.days != null ? d.days : "")],
  ["status", "Status", d => d.status || ""],
  ["sku", "SKU", d => d.sku || ""],
  ["skutype", "SKU type", d => d.skutype || ""],
  ["price", "Total price", d => d.price || ""],
  ["orderDate", "Order date", d => d.orderDate || ""],
  ["address", "Customer address", d => d.address || ""],
];
const REPORT_DEFAULT = new Set(["image", "jo", "cust", "service", "assigned", "metal", "due", "days"]);
let REPORT_CODES = [], REPORT_STAGE = "", REPORT_EMP_MODE = false;

function reportColsHtml() {
  return REPORT_COLS.map(([k, label]) =>
    `<label class="rp-col"><input type="checkbox" value="${k}" ${REPORT_DEFAULT.has(k) ? "checked" : ""}>${label}</label>`
  ).join("");
}
function reportActionsHtml(empMode) {
  return '<div class="rp-actions">' +
    '<button class="rp-selall">Select all / none</button>' +
    '<button class="rp-cancel">Cancel</button>' +
    `<button class="rp-export${empMode ? " rp-export-emp" : ""}" id="rpExport">Download Excel</button></div>`;
}
function openReport(btn) {
  REPORT_STAGE = btn.dataset.stage || "";
  REPORT_CODES = (btn.dataset.codes || "").split(",").filter(Boolean);
  REPORT_EMP_MODE = false;
  document.getElementById("rpanel").innerHTML =
    `<div class="rp-h"><div class="rp-title">Create customized report</div>` +
    `<div class="rp-sub">${esc(REPORT_STAGE)} &middot; ${REPORT_CODES.length} orders. Choose columns to include.</div></div>` +
    `<div class="rp-body"><div class="rp-seclabel">Columns</div>` +
    `<div class="rp-cols">${reportColsHtml()}</div></div>` + reportActionsHtml(false);
  document.getElementById("rpanel").classList.remove("emp-mode");
  document.getElementById("ovr").classList.add("open");
}
function openEmployeeReport(btn) {
  REPORT_STAGE = btn.dataset.stage || "";
  REPORT_CODES = (btn.dataset.codes || "").split(",").filter(Boolean);
  REPORT_EMP_MODE = true;
  const lockName = btn.dataset.lock || "";
  const counts = {};
  REPORT_CODES.forEach(c => {
    const d = DETAIL[c];
    if (!d) return;
    const a = personKey(d);
    counts[a] = (counts[a] || 0) + 1;
  });
  const names = Object.keys(counts).sort((a, b) =>
    a === "Unassigned" ? 1 : (b === "Unassigned" ? -1 : a.localeCompare(b)));
  let opts, subtitle;
  if (lockName) {
    opts = `<option value="${esc(lockName)}">${esc(lockName)} (${REPORT_CODES.length})</option>`;
    subtitle = `Report for <strong>${esc(lockName)}</strong>. Choose columns below.`;
  } else {
    opts = '<option value="__all__">All employees</option>';
    names.forEach(n => { opts += `<option value="${esc(n)}">${esc(n)} (${counts[n]})</option>`; });
    subtitle = `${esc(REPORT_STAGE)}. Pick an employee, then choose columns.`;
  }
  document.getElementById("rpanel").innerHTML =
    `<div class="rp-h"><div class="rp-title">Generate employee-specific report</div>` +
    `<div class="rp-sub">${subtitle}</div></div>` +
    `<div class="rp-body"><div class="rp-seclabel">Employee</div>` +
    `<select id="rpEmp" class="rp-empsel"${lockName ? " disabled" : ""}>${opts}</select>` +
    `<div class="rp-seclabel" style="margin-top:18px;">Columns</div>` +
    `<div class="rp-cols">${reportColsHtml()}</div></div>` + reportActionsHtml(true);
  document.getElementById("rpanel").classList.add("emp-mode");
  document.getElementById("ovr").classList.add("open");
  updateEmpCount();
}
function empSelected() {
  const sel = document.getElementById("rpEmp");
  return sel ? sel.value : "__all__";
}
function scopedCodes() {
  if (!REPORT_EMP_MODE) return REPORT_CODES;
  const emp = empSelected();
  if (emp === "__all__") return REPORT_CODES;
  return REPORT_CODES.filter(c => DETAIL[c] && personKey(DETAIL[c]) === emp);
}
function updateEmpCount() {
  const btn = document.getElementById("rpExport");
  if (btn) btn.textContent = "Download Excel" + (REPORT_EMP_MODE ? ` (${scopedCodes().length})` : "");
}
function toggleAllCols() {
  const boxes = [...document.querySelectorAll("#rpanel .rp-col input")];
  const anyOff = boxes.some(b => !b.checked);
  boxes.forEach(b => { b.checked = anyOff; });
}
function closeReport() {
  document.getElementById("ovr").classList.remove("open");
  flushPendingData();
}

async function fetchImageData(url) {
  try {
    const resp = await fetch(url, { mode: "cors" });
    if (!resp.ok) return null;
    const blob = await resp.blob();
    let ext;
    if (blob.type.includes("jpeg") || blob.type.includes("jpg")) ext = "jpeg";
    else if (blob.type.includes("png")) ext = "png";
    else if (blob.type.includes("gif")) ext = "gif";
    else return null; // exceljs supports png/jpeg/gif only
    const buf = await blob.arrayBuffer();
    let binary = "";
    const bytes = new Uint8Array(buf);
    for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
    return { base64: btoa(binary), ext };
  } catch (e) { return null; }
}

async function exportReport() {
  if (typeof ExcelJS === "undefined") { alert("Excel library failed to load - check your connection and refresh."); return; }
  const chosen = [...document.querySelectorAll("#rpanel .rp-col input")].filter(b => b.checked).map(b => b.value);
  if (!chosen.length) { alert("Pick at least one column."); return; }
  const codes = scopedCodes();
  if (!codes.length) { alert("No orders for that employee."); return; }
  const emp = REPORT_EMP_MODE ? empSelected() : "__all__";
  const colDefs = REPORT_COLS.filter(([k]) => chosen.includes(k));
  const wantImage = chosen.includes("image");
  const btn = document.getElementById("rpExport");
  btn.disabled = true;
  btn.textContent = wantImage ? "Fetching images…" : "Building…";

  const wb = new ExcelJS.Workbook();
  let baseName = REPORT_STAGE;
  if (REPORT_EMP_MODE && emp !== "__all__") baseName = emp + " - " + REPORT_STAGE;
  const safe = baseName.replace(/[^A-Za-z0-9 ]/g, "").slice(0, 28) || "Report";
  const ws = wb.addWorksheet(safe.slice(0, 28));

  ws.addRow(colDefs.map(([, label]) => label));
  const hRow = ws.getRow(1);
  hRow.font = { bold: true };
  hRow.alignment = { vertical: "middle" };

  let imageColIdx = -1;
  ws.columns = colDefs.map(([k], i) => {
    if (k === "image") { imageColIdx = i; return { width: 16 }; }
    return { width: k === "address" ? 40 : (k === "cust" ? 26 : 16) };
  });

  const IMG_W = 90, ROW_H = 70;
  let r = 2;
  for (const code of codes) {
    const d = DETAIL[code];
    if (!d) continue;
    const row = ws.addRow(colDefs.map(([k, , fn]) => k === "image" ? "" : fn(d)));
    row.alignment = { vertical: "middle" };
    if (wantImage && d.img) {
      const data = await fetchImageData(d.img);
      if (data) {
        const imgId = wb.addImage({ base64: `data:image/${data.ext};base64,${data.base64}`, extension: data.ext });
        row.height = ROW_H;
        ws.addImage(imgId, { tl: { col: imageColIdx + 0.15, row: (r - 1) + 0.1 },
                             ext: { width: IMG_W, height: ROW_H - 8 } });
        ws.getColumn(imageColIdx + 1).width = IMG_W / 7;
      }
    }
    r++;
  }

  btn.textContent = "Saving…";
  const buf = await wb.xlsx.writeBuffer();
  const blob = new Blob([buf], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
  const today = new Date().toISOString().slice(0, 10);
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = safe.replace(/ /g, "_") + "_" + today + ".xlsx";
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  btn.disabled = false;
  btn.textContent = "Download Excel";
  closeReport();
}

// ---------- soft refresh ----------
let refreshDeadline = 0;
let refreshing = false;

async function fetchData() {
  const resp = await fetch("data.json?t=" + Date.now(), { cache: "no-store" });
  if (!resp.ok) throw new Error("data.json HTTP " + resp.status);
  return resp.json();
}
function flushPendingData() {
  if (PENDING_DATA && !overlayOpen()) {
    const d = PENDING_DATA;
    PENDING_DATA = null;
    applyData(d);
  }
}
async function refreshData() {
  if (refreshing) return;
  refreshing = true;
  try {
    const data = await fetchData();
    // Don't rip the DOM out from under an open card or a report being built;
    // apply the new data as soon as the overlay closes.
    if (overlayOpen()) PENDING_DATA = data;
    else applyData(data);
  } catch (e) {
    paintHeader(); // keeps showing the old stamp; the stale banner takes over eventually
  } finally {
    refreshing = false;
    refreshDeadline = Date.now() + CONFIG.refreshSeconds * 1000;
  }
}
function tick() {
  const left = Math.round((refreshDeadline - Date.now()) / 1000);
  const el = document.getElementById("reloadCountdown");
  if (el) {
    const s = Math.max(left, 0);
    el.textContent = `refresh in ${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  }
  if (left <= 0 && !refreshing) refreshData();
}

// ---------- events ----------
document.addEventListener("click", e => {
  if (e.target.closest(".rp-selall")) { toggleAllCols(); return; }
  if (e.target.closest(".rp-cancel")) { closeReport(); return; }
  if (e.target.closest("#rpExport")) { exportReport(); return; }
  if (e.target.closest(".pclose")) { closeCard(); return; }
  const rbtn = e.target.closest("button.reportbtn");
  if (rbtn) {
    if (rbtn.dataset.report === "employee") openEmployeeReport(rbtn);
    else openReport(rbtn);
    return;
  }
  const box = e.target.closest(".box[data-dept]");
  if (box) { openDept(box.dataset.dept); return; }
  if (e.target.closest(".back")) { closeDept(); return; }
  if (e.target.closest(".pv-back")) { closePerson(); return; }
  const sh = e.target.closest(".stage-h");
  if (sh) { sh.parentElement.classList.toggle("collapsed"); return; }
  const ph = e.target.closest(".pgroup-h");
  if (ph) { ph.parentElement.classList.toggle("collapsed"); return; }
  const row = e.target.closest("[data-card]");
  if (row) { showCard(row.dataset.card); return; }
});
document.addEventListener("change", e => {
  const sel = e.target.closest(".pf select");
  if (sel) {
    const stage = sel.closest(".stage");
    stage.dataset[sel.dataset.filter] = sel.value;
    applyPersonFilters(stage);
    return;
  }
  if (e.target.id === "rpEmp") updateEmpCount();
});
document.getElementById("ov").addEventListener("click", e => { if (e.target === e.currentTarget) closeCard(); });
document.getElementById("ovr").addEventListener("click", e => { if (e.target === e.currentTarget) closeReport(); });
document.getElementById("q").addEventListener("keydown", e => { if (e.key === "Enter") doSearch(); });
document.getElementById("qp").addEventListener("keydown", e => { if (e.key === "Enter") doPersonSearch(); });
window.addEventListener("popstate", () => {
  document.getElementById("ov").classList.remove("open");
  document.getElementById("ovr").classList.remove("open");
  showBoxes();
  flushPendingData();
});
document.addEventListener("visibilitychange", () => { if (!document.hidden) tick(); });

// ---------- boot ----------
(async function init() {
  try {
    const [cfgResp, data] = await Promise.all([
      fetch("config.json", { cache: "no-store" }).then(r => {
        if (!r.ok) throw new Error("config.json HTTP " + r.status);
        return r.json();
      }),
      // data fetch depends on nothing in config, so run it in parallel
      (async () => {
        const resp = await fetch("data.json?t=" + Date.now(), { cache: "no-store" });
        if (!resp.ok) throw new Error("data.json HTTP " + resp.status);
        return resp.json();
      })(),
    ]);
    CONFIG = cfgResp;
    applyData(data);
    refreshDeadline = Date.now() + CONFIG.refreshSeconds * 1000;
    setInterval(tick, 1000);
    tick();
  } catch (e) {
    document.getElementById("boxes").innerHTML =
      `<div class="loadnote">Could not load tracker data (${esc(e.message)}). ` +
      "The update pipeline may be down - try again in a few minutes.</div>";
  }
})();
