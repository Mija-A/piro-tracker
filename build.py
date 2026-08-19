"""
build.py - reads orders.json + history.json, writes index.html.
Clean serif/sans dashboard: outlined department boxes (grid) -> click opens a
department's stages/orders -> click an order for image + journey card.
Defaults to parents-only view (suborders are material sub-tasks; toggle to see them).

STEP 1: Printing / Casting stages now group JOs by metal type, show colored
metal pills, and list the due date (M/D) right in the dropdown. Other
departments render exactly as before.

Run: python3 build.py
"""
import json, datetime, html, re
from zoneinfo import ZoneInfo

STALE_DAYS = 0
SHOW_SUBORDERS = False
DUE_FIELD = "dueDate"          # ISO timestamp on each order, e.g. 2026-10-01T00:00:00

DEPARTMENTS = {
    "CAD": ["Design Queue","Designing","CAD Queue","CADing","CAD Approval","CAD Check",
            "CAD Revision Queue","Design Approval","PLATINA CADing"],
    "Printing / Casting": ["3D Print Queue","3D Printing","Resin Printing","Resin/Render Approval",
            "WAX approval","Casting Queue","Casting Filled","Tree Building","Tree Breakdown","Production Prep"],
    "Shop": ["Jeweler's Queue","Jewelry Cleaning","Jewelry Assembly","Setting queue","Prepolish",
            "Stone Setting","Stone Setting additional","Final Polish","QA","QA Final","QA Setting","Engraving"],
    "Stones": ["Stone picking Queue","Stone(s) Received","Stone(s) Filled","Findings Queue",
            "Findings Filled","Waiting for Stone(s)"],
    "Customer Service": ["SP Order Processing","SP Fulfillment queue","Invoice & Ship"],
}
DEPT_ORDER = ["CAD","Printing / Casting","Stones","Shop","Customer Service","Other"]

# Departments that use the metal-grouped, DUE-column row treatment (Step 1)
METAL_GROUPED_DEPTS = {"Printing / Casting"}

# Services (by stage name) that group JOs by assigned worker, then due date (Step 2).
# These take priority over metal grouping for their specific stage.
PERSON_GROUPED_SERVICES = {"Stone Setting", "Jewelry Cleaning", "CADing"}

# metal keyword -> (background, text) . Matched case-insensitively by "contains".
# Order matters: more specific keys (18k white) before generic ones would collide,
# but our tokens are already distinct, so simple contains-matching is fine.
METAL_COLORS = {
    "18k white":   ("#cfe0f2", "#1f3a5f"),  # blue
    "14k white":   ("#d7ecd9", "#2f5133"),  # green
    "18k yellow":  ("#f3c98b", "#5f3f16"),  # orange
    "14k yellow":  ("#f6e7a8", "#5b4d17"),  # yellow
    "18k rose":    ("#e6a9b4", "#5c2530"),  # darker pink
    "14k rose":    ("#f3d0d8", "#6b3a44"),  # light pink
    "platinum":    ("#d8d8d6", "#3a3a37"),  # grey
    "silver":      ("#ececea", "#4a4a47"),  # lighter grey
}
METAL_FALLBACK = ("#e8e5df", "#5a554c")     # WAX / unknown -> neutral

def metal_color(token):
    t = (token or "").lower()
    for key,(bg,fg) in METAL_COLORS.items():
        if key in t:
            return bg, fg
    return METAL_FALLBACK

def split_metals(s):
    """Split a metals string on ; or , into cleaned tokens."""
    return [t.strip() for t in re.split(r"[;,]", s or "") if t.strip()]

def metal_group_key(s):
    """Combined metal string used as the group label (blank -> 'No metal')."""
    toks = split_metals(s)
    return ", ".join(toks) if toks else "No metal"

def metal_pill_html(s):
    """One combined pill; each metal segment colored, sitting flush together."""
    toks = split_metals(s)
    if not toks:
        return '<span class="mpill mpill-none">No metal</span>'
    segs = ""
    n = len(toks)
    for i,t in enumerate(toks):
        bg,fg = metal_color(t)
        rl = "10px" if i==0 else "0"
        rr = "10px" if i==n-1 else "0"
        segs += (f'<span class="mseg" style="background:{bg};color:{fg};'
                 f'border-top-left-radius:{rl};border-bottom-left-radius:{rl};'
                 f'border-top-right-radius:{rr};border-bottom-right-radius:{rr};">'
                 f'{html.escape(t)}</span>')
    return f'<span class="mpill">{segs}</span>'

def fmt_due(v):
    """ISO timestamp -> 'M/D' (e.g. 8/10). Blank if missing/unparseable."""
    if not v: return ""
    s = str(v)
    try:
        d = datetime.datetime.fromisoformat(s.replace("Z","").split("T")[0])
        return f"{d.month}/{d.day}"
    except Exception:
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
        if m:
            return f"{int(m.group(2))}/{int(m.group(3))}"
        return ""

def due_sort_key(o):
    """Sort earliest due first; missing dues go last."""
    v = o.get(DUE_FIELD)
    if not v: return (1, "")
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(v))
    return (0, m.group(0)) if m else (1, "")

# Fixed display order for single-metal groups. Combined/multi-metal groups sort
# after all single metals; unknowns (e.g. WAX) sort last.
METAL_ORDER = ["18k yellow","14k yellow","18k white","14k white",
               "18k rose","14k rose","platinum","silver"]

def metal_group_sort_key(gkey):
    """Order groups: single metals by METAL_ORDER, then combos, then unknown."""
    toks = split_metals(gkey)
    single = len(toks) == 1
    if single:
        t = toks[0].lower()
        for i,name in enumerate(METAL_ORDER):
            if name in t:
                return (0, i, gkey)
        return (2, 0, gkey)          # single but unknown metal (e.g. WAX)
    return (1, 0, gkey)              # multi-metal combo

def dept_of(stage):
    s=(stage or "").strip()
    for d,st in DEPARTMENTS.items():
        if s in st: return d
    return "Other"

def is_sub(code):
    return bool(re.match(r'^JO-\d+-\d+', code or ""))

def main():
    orders = json.load(open("orders.json", encoding="utf-8-sig")).get("value", [])
    try:
        history = json.load(open("history.json"))
    except (FileNotFoundError, json.JSONDecodeError):
        history = {}

    rows=[]
    for o in orders:
        if not SHOW_SUBORDERS and is_sub(o.get("code","")): continue
        d=o.get("daysInCurrentService")
        if STALE_DAYS and isinstance(d,int) and d>=STALE_DAYS: continue
        rows.append(o)

    grouped={}
    for o in rows:
        stage=(o.get("currentService") or "(no stage)").strip()
        grouped.setdefault(dept_of(stage),{}).setdefault(stage,[]).append(o)

    parent_rows_all=[o for o in rows if not is_sub(o.get("code",""))]
    total=len(parent_rows_all)
    stuck=sum(1 for o in parent_rows_all if isinstance(o.get("daysInCurrentService"),int) and o["daysInCurrentService"]>=13)
    now=datetime.datetime.now(ZoneInfo("America/New_York")).strftime("%b %d, %Y  %I:%M %p")+" ET"

    detail={}
    for o in rows:
        c=o.get("code","")
        items=o.get("items") or []
        sku=", ".join(sorted({(it.get("itemSKU") or "") for it in items if it.get("itemSKU")}))
        skutype=", ".join(sorted({(it.get("itemTypeSKU") or "") for it in items if it.get("itemTypeSKU")}))
        detail[c]={"cust":o.get("customerName") or "","stage":o.get("currentService") or "",
                   "days":o.get("daysInCurrentService"),"dept":dept_of(o.get("currentService","")),
                   "img":o.get("imageURL") or "","metal":o.get("metals") or "",
                   "assigned":o.get("serviceAssignedUser") or "","journey":history.get(c,[]),
                   "due":fmt_due(o.get(DUE_FIELD)),
                   "pill":metal_pill_html(o.get("metals") or ""),
                   # extra fields for report export
                   "dueISO":(str(o.get("dueDate") or "")[:10]),
                   "status":o.get("status") or "","sku":sku,"skutype":skutype,
                   "price":o.get("totalPrice") or "","orderDate":(str(o.get("orderDate") or "")[:10]),
                   "address":o.get("customerMainAddress") or ""}

    boxes_html=""; panels_html=""
    for d in DEPT_ORDER:
        if d not in grouped: continue
        drows=[o for st in grouped[d].values() for o in st]
        parent_rows=[o for o in drows if not is_sub(o.get("code",""))]
        dtotal=len(parent_rows)
        dstuck=sum(1 for o in parent_rows if isinstance(o.get("daysInCurrentService"),int) and o["daysInCurrentService"]>=13)
        did=d.replace(" ","").replace("/","")
        boxes_html+=f'<button class="box" onclick="openDept(\'{did}\')"><div class="bname">{html.escape(d)}</div><div class="bnum">{dtotal}</div><div class="bsub">{dstuck} stuck</div></button>'

        metal_mode = d in METAL_GROUPED_DEPTS
        stages_html=""
        for stage in sorted(grouped[d], key=lambda s:-len(grouped[d][s])):
            olist=grouped[d][stage]
            if stage in PERSON_GROUPED_SERVICES:
                stages_html+=render_stage_by_person(stage, olist)
            elif metal_mode:
                stages_html+=render_stage_by_metal(stage, olist)
            else:
                stages_html+=render_stage_flat(stage, olist)

        cls = " metalgrp" if metal_mode else ""
        panels_html+=(f'<div class="deptpanel{cls}" id="dept-{did}">'
                      f'<button class="back" onclick="closeDept()">&#8592; All departments</button>'
                      f'<div class="dp-h"><span class="dp-name">{html.escape(d)}</span><span class="dp-n">{dtotal}</span></div>'
                      f'{stages_html}</div>')

    page=PAGE.replace("{{BOXES}}",boxes_html).replace("{{PANELS}}",panels_html).replace("{{NOW}}",now)\
             .replace("{{TOTAL}}",str(total)).replace("{{STUCK}}",str(stuck))\
             .replace("{{DETAIL}}",json.dumps(detail))
    open("index.html","w").write(page)
    print(f"Built index.html ({total} parent orders shown, history on {len(history)} orders)")

def jo_row_flat(o):
    dd=o.get("daysInCurrentService")
    sc=" stuck" if isinstance(dd,int) and dd>=13 else ""
    c=html.escape(o.get("code",""))
    sub=1 if is_sub(o.get("code","")) else 0
    return (f'<div class="jo{sc}" data-sub="{sub}" onclick="showCard(\'{c}\')">'
            f'<span class="code">{c}</span>'
            f'<span class="cust">{html.escape((o.get("customerName") or "")[:28])}</span>'
            f'<span class="days">{dd if dd is not None else ""}d</span></div>')

def jo_row_metal(o):
    dd=o.get("daysInCurrentService")
    sc=" stuck" if isinstance(dd,int) and dd>=13 else ""
    c=html.escape(o.get("code",""))
    sub=1 if is_sub(o.get("code","")) else 0
    due=fmt_due(o.get(DUE_FIELD))
    return (f'<div class="jo jom{sc}" data-sub="{sub}" onclick="showCard(\'{c}\')">'
            f'<span class="code">{c}</span>'
            f'<span class="cust">{html.escape((o.get("customerName") or "")[:24])}</span>'
            f'<span class="metalcell">{metal_pill_html(o.get("metals") or "")}</span>'
            f'<span class="duecell">{due}</span>'
            f'<span class="days">{dd if dd is not None else ""}d</span></div>')

def render_stage_flat(stage, olist):
    olist=sorted(olist, key=lambda x:-(x.get("daysInCurrentService") or 0))
    items="".join(jo_row_flat(o) for o in olist)
    bar=report_bar(stage, olist)
    return (f'<div class="stage collapsed"><div class="stage-h" onclick="toggleStage(this)">'
            f'<span class="stage-caret">&#9656;</span>'
            f'<span class="stage-name">{html.escape(stage)}</span>'
            f'<span class="stage-n">{len(olist)}</span></div>'
            f'<div class="stage-body">{bar}{items}</div></div>')

def report_bar(stage, olist):
    """A 'Create report' button carrying this stage's JO codes for export."""
    codes=[o.get("code","") for o in olist if o.get("code")]
    codes_attr=html.escape(",".join(codes))
    return (f'<div class="reportbar">'
            f'<button class="reportbtn" data-stage="{html.escape(stage)}" '
            f'data-codes="{codes_attr}" onclick="openReport(this)">'
            f'&#8681; Create customized report</button></div>')

def person_key(o):
    """Assigned worker name; blank -> 'Unassigned'."""
    n=(o.get("serviceAssignedUser") or "").strip()
    return n if n else "Unassigned"

def jo_row_person(o):
    dd=o.get("daysInCurrentService")
    sc=" stuck" if isinstance(dd,int) and dd>=13 else ""
    c=html.escape(o.get("code",""))
    sub=1 if is_sub(o.get("code","")) else 0
    due=fmt_due(o.get(DUE_FIELD))
    who=html.escape(person_key(o))
    dv=o.get(DUE_FIELD) or ""
    m=re.match(r"(\d{4}-\d{2}-\d{2})", str(dv))
    diso=m.group(1) if m else ""
    return (f'<div class="jo jom{sc}" data-sub="{sub}" data-person="{who}" '
            f'data-due="{diso}" onclick="showCard(\'{c}\')">'
            f'<span class="code">{c}</span>'
            f'<span class="cust">{html.escape((o.get("customerName") or "")[:24])}</span>'
            f'<span class="metalcell">{metal_pill_html(o.get("metals") or "")}</span>'
            f'<span class="duecell">{due}</span>'
            f'<span class="days">{dd if dd is not None else ""}d</span></div>')

def render_stage_by_person(stage, olist):
    # bucket by assigned worker
    buckets={}
    for o in olist:
        buckets.setdefault(person_key(o), []).append(o)
    # person order: alphabetical, Unassigned always last
    def psort(name): return (1,"") if name=="Unassigned" else (0,name.lower())
    people=sorted(buckets, key=psort)

    sid=re.sub(r'[^A-Za-z0-9]','',stage)  # stable id for this stage's controls

    # employee dropdown options
    opts='<option value="__all__">All employees</option>'
    for name in people:
        opts+=f'<option value="{html.escape(name)}">{html.escape(name)} ({len(buckets[name])})</option>'

    controls=(f'<div class="pfilters">'
              f'<label class="pf">Employee '
              f'<select onchange="filterPerson(this)">{opts}</select></label>'
              f'<label class="pf">Due '
              f'<select onchange="filterDue(this)">'
              f'<option value="__all__">Any date</option>'
              f'<option value="overdue">Overdue</option>'
              f'<option value="7">Next 7 days</option>'
              f'<option value="14">Next 14 days</option>'
              f'</select></label></div>')

    inner=controls+report_bar(stage, olist)
    for name in people:
        gitems=sorted(buckets[name], key=due_sort_key)
        colhead=('<div class="jo jom colhead">'
                 '<span class="code">JO</span>'
                 '<span class="cust">Customer</span>'
                 '<span class="metalcell">Metal</span>'
                 '<span class="duecell">Due date</span>'
                 '<span class="days">Days in service</span></div>')
        rows="".join(jo_row_person(o) for o in gitems)
        inner+=(f'<div class="pgroup collapsed" data-person="{html.escape(name)}">'
                f'<div class="pgroup-h" onclick="togglePerson(this)">'
                f'<span class="pgroup-caret">&#9656;</span>'
                f'<span class="pgroup-name">{html.escape(name)}</span>'
                f'<span class="pgroup-n">{len(gitems)}</span></div>'
                f'<div class="pgroup-body">{colhead}{rows}</div></div>')

    return (f'<div class="stage collapsed personmode" data-sid="{sid}">'
            f'<div class="stage-h" onclick="toggleStage(this)">'
            f'<span class="stage-caret">&#9656;</span>'
            f'<span class="stage-name">{html.escape(stage)}</span>'
            f'<span class="stage-n">{len(olist)}</span></div>'
            f'<div class="stage-body">{inner}</div></div>')

def render_stage_by_metal(stage, olist):
    # bucket by combined metal string
    buckets={}
    for o in olist:
        buckets.setdefault(metal_group_key(o.get("metals") or ""), []).append(o)
    # column labels row (once, at top of the stage body)
    header=('<div class="jo jom colhead">'
            '<span class="code">JO</span>'
            '<span class="cust">Customer</span>'
            '<span class="metalcell">Metal</span>'
            '<span class="duecell">Due date</span>'
            '<span class="days">Days in service</span></div>')
    inner=report_bar(stage, olist)+header
    for gkey in sorted(buckets, key=metal_group_sort_key):
        gitems=sorted(buckets[gkey], key=due_sort_key)
        rows="".join(jo_row_metal(o) for o in gitems)
        # no metal pill in the header — grouping is visible from the row pills;
        # just a thin count divider between metal groups
        inner+=(f'<div class="mgroup"><div class="mgroup-h">'
                f'<span class="mgroup-n">{len(gitems)}</span></div>'
                f'{rows}</div>')
    return (f'<div class="stage collapsed"><div class="stage-h" onclick="toggleStage(this)">'
            f'<span class="stage-caret">&#9656;</span>'
            f'<span class="stage-name">{html.escape(stage)}</span>'
            f'<span class="stage-n">{len(olist)}</span></div>'
            f'<div class="stage-body">{inner}</div></div>')

PAGE=r"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Production Tracker</title>
<meta http-equiv="refresh" content="3600">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/exceljs/4.4.0/exceljs.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/FileSaver.js/2.0.5/FileSaver.min.js"></script>
<style>
:root{--bg:#f6f5f1;--card:#fdfcfa;--ink:#2a2824;--ink2:#6f6a61;--ink3:#a29c90;--line:#e0dcd2;--line2:#c9c4b8;
--serif:'Cormorant Garamond',Georgia,serif;--sans:'Inter',-apple-system,sans-serif;--mono:'SF Mono',ui-monospace,Menlo,monospace;}
*{margin:0;padding:0;box-sizing:border-box;}
body{background:var(--bg);color:var(--ink);font-family:var(--sans);padding:34px 44px;font-size:14px;}
.top{display:flex;align-items:baseline;gap:18px;margin-bottom:6px;flex-wrap:wrap;}
.title{font-family:var(--serif);font-size:30px;font-weight:600;letter-spacing:.01em;}
.updated{margin-left:auto;font-size:11px;color:var(--ink3);letter-spacing:.03em;text-transform:uppercase;}
.rule{height:1px;background:var(--ink);opacity:.82;margin-bottom:26px;}
.searchrow{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:26px;}
.search{position:relative;flex:1;min-width:300px;max-width:420px;}
.search input{width:100%;height:44px;border:1px solid var(--line2);border-radius:6px;padding:0 12px 0 38px;font-size:14.5px;background:var(--card);outline:none;font-family:var(--sans);}
.search input:focus{border-color:var(--ink);}
.search .ico{position:absolute;left:14px;top:13px;color:var(--ink3);font-size:15px;}
/* employee search results (inline, full view) */
.personview{display:none;max-width:940px;}
.personview.open{display:block;}
.pv-back{background:none;border:none;font-family:var(--sans);font-size:12.5px;color:var(--ink2);cursor:pointer;padding:6px 0;margin-bottom:16px;}
.pv-back:hover{color:var(--ink);}
.pv-h{padding-bottom:16px;border-bottom:1px solid var(--ink);margin-bottom:8px;}
.pv-name{font-family:var(--sans);font-size:30px;font-weight:600;color:var(--ink);letter-spacing:.01em;}
.pv-sub{font-size:14px;color:var(--ink2);margin-top:6px;}
.pr-stage{font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:var(--ink3);padding:22px 8px 8px;border-bottom:1px solid var(--line);}
.pr-row{display:flex;align-items:center;gap:12px;font-size:16.5px;padding:12px 8px;border-bottom:1px solid var(--line);cursor:pointer;}
.pr-row:hover{background:var(--card);}
.pr-row .code{font-family:var(--mono);font-size:15px;min-width:160px;}
.pr-row .cust{flex:1;color:var(--ink2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0;}
.pr-row .metalcell{flex-shrink:0;min-width:150px;display:flex;justify-content:center;align-items:center;}
.pr-row .duecell{flex-shrink:0;min-width:80px;text-align:center;color:var(--ink2);font-variant-numeric:tabular-nums;font-size:16px;}
.pr-row .days{flex-shrink:0;min-width:110px;text-align:center;color:var(--ink3);font-variant-numeric:tabular-nums;}
.pr-row .days.stuck{color:#8a5a30;font-weight:600;}
.pr-colhead{font-size:12px !important;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:var(--ink3);cursor:default;padding-top:8px;padding-bottom:8px;}
.pr-colhead:hover{background:transparent;}
.pr-colhead .code,.pr-colhead .cust,.pr-colhead .metalcell,.pr-colhead .duecell,.pr-colhead .days{font-family:var(--sans) !important;font-size:12px !important;color:var(--ink3) !important;font-weight:600;}
.pr-none{padding:30px 8px;color:var(--ink2);font-size:15px;}
/* report builder */
.reportbar{padding:10px 2px 16px;}
.reportbtn{font-family:var(--sans);font-size:13.5px;font-weight:600;color:#fff;background:var(--ink);border:1px solid var(--ink);border-radius:8px;padding:11px 20px;cursor:pointer;transition:background .12s,box-shadow .12s;box-shadow:0 1px 3px rgba(0,0,0,.12);letter-spacing:.01em;}
.reportbtn:hover{background:#000;box-shadow:0 2px 8px rgba(0,0,0,.2);}
.rpanel{background:var(--card);border-radius:10px;max-width:520px;width:100%;box-shadow:0 18px 55px rgba(0,0,0,.24);max-height:88vh;overflow-y:auto;}
.rp-h{padding:24px 28px 8px;}
.rp-title{font-family:var(--sans);font-size:20px;font-weight:600;color:var(--ink);}
.rp-sub{font-size:13px;color:var(--ink2);margin-top:5px;}
.rp-body{padding:16px 28px 8px;}
.rp-seclabel{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--ink3);font-weight:600;margin:6px 0 10px;}
.rp-cols{display:grid;grid-template-columns:1fr 1fr;gap:10px 20px;}
.rp-col{display:flex;align-items:center;gap:9px;font-size:14px;color:var(--ink);cursor:pointer;user-select:none;}
.rp-col input{width:16px;height:16px;cursor:pointer;accent-color:var(--ink);}
.rp-actions{display:flex;gap:10px;justify-content:flex-end;align-items:center;padding:18px 28px 24px;border-top:1px solid var(--line);margin-top:16px;}
.rp-selall{margin-right:auto;font-size:12.5px;color:var(--ink2);cursor:pointer;background:none;border:none;font-family:var(--sans);text-decoration:underline;}
.rp-selall:hover{color:var(--ink);}
.rp-cancel{font-size:13px;color:var(--ink2);cursor:pointer;background:none;border:none;font-family:var(--sans);padding:10px 14px;}
.rp-cancel:hover{color:var(--ink);}
.rp-export{font-family:var(--sans);font-size:13.5px;font-weight:600;color:#fff;background:var(--ink);border:none;border-radius:7px;padding:11px 20px;cursor:pointer;}
.rp-export:hover{background:#000;}
.rp-export:disabled{opacity:.4;cursor:not-allowed;}
.stats{display:flex;gap:46px;margin-bottom:30px;}
.slab{font-size:11px;text-transform:uppercase;letter-spacing:.07em;color:var(--ink3);margin-bottom:5px;}
.snum{font-family:var(--serif);font-size:30px;font-weight:600;line-height:1;}
.snum.warn{color:#8a5a30;}
.boxes{display:grid;grid-template-columns:repeat(3,1fr);gap:15px;max-width:940px;}
.box{border:1px solid var(--line2);border-radius:7px;padding:22px 24px 20px;cursor:pointer;font-family:var(--sans);text-align:left;background:var(--card);aspect-ratio:1.95/1;display:flex;flex-direction:column;transition:border-color .13s,background .13s;}
.box:hover{border-color:var(--ink);}
.bname{font-family:var(--serif);font-size:19px;font-weight:600;letter-spacing:.01em;margin-bottom:auto;color:var(--ink);}
.bnum{font-size:33px;font-weight:600;letter-spacing:-.02em;line-height:1;}
.bsub{font-size:12px;color:var(--ink2);margin-top:6px;}
.deptpanel{display:none;max-width:940px;}
.deptpanel.open{display:block;}
.back{background:none;border:none;font-family:var(--sans);font-size:12.5px;color:var(--ink2);cursor:pointer;padding:6px 0;margin-bottom:16px;}
.back:hover{color:var(--ink);}
.dp-h{display:flex;align-items:baseline;gap:12px;padding-bottom:14px;border-bottom:1px solid var(--ink);margin-bottom:4px;}
.dp-name{font-family:var(--serif);font-size:24px;font-weight:600;}
.dp-n{margin-left:auto;font-size:18px;font-weight:500;color:var(--ink2);}
.controls{margin:16px 0 4px;}
.seg{display:inline-flex;border:1px solid var(--line2);border-radius:7px;overflow:hidden;}
.seg button{border:none;border-right:1px solid var(--line2);background:var(--card);font-family:var(--sans);font-size:12.5px;color:var(--ink2);padding:8px 16px;cursor:pointer;}
.seg button:last-child{border-right:none;}
.seg button.on{background:var(--ink);color:#fff;}
.stage{margin-top:14px;}
.stage-h{display:flex;align-items:center;gap:9px;font-size:13px;font-weight:600;color:var(--ink2);text-transform:uppercase;letter-spacing:.06em;padding:13px 10px;border:1px solid var(--line2);border-radius:8px;background:var(--card);cursor:pointer;user-select:none;transition:border-color .12s;}
.stage-h:hover{border-color:var(--ink2);}
.stage-caret{font-size:10px;color:var(--ink3);transition:transform .14s;display:inline-block;}
.stage.collapsed .stage-caret{transform:rotate(0deg);}
.stage:not(.collapsed) .stage-caret{transform:rotate(90deg);}
.stage-name{flex:1;}
.stage-n{color:var(--ink3);font-variant-numeric:tabular-nums;}
.stage-body{padding:6px 2px 4px;}
.stage.collapsed .stage-body{display:none;}
.jo{display:flex;align-items:baseline;gap:12px;font-size:16.5px;padding:12px 6px;border-bottom:1px solid var(--line);cursor:pointer;}
.jo:hover{background:var(--card);}
.jo .code{font-family:var(--mono);font-size:15px;min-width:160px;}
.jo .cust{flex:1;color:var(--ink2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.jo .days{color:var(--ink3);font-variant-numeric:tabular-nums;min-width:110px;text-align:center;}
.jo.stuck .days{color:#8a5a30;font-weight:600;}

/* ---- Step 1: metal-grouped Printing/Casting ---- */
.mgroup{margin:2px 0 12px;padding:0 2px;}
.mgroup-h{display:flex;align-items:center;padding:6px 2px 4px;}
.mgroup-n{margin-left:auto;font-size:10.5px;font-weight:600;color:var(--ink3);font-variant-numeric:tabular-nums;}
.jo.jom{align-items:center;background:transparent;border-bottom:1px solid var(--line);}
.jo.jom:last-child{border-bottom:none;}
.jo.jom:hover{background:var(--card);}
.jo.colhead{font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:var(--ink3);cursor:default;border-bottom:1px solid var(--line2);padding-bottom:8px;}
.jo.colhead:hover{background:transparent;}
.jo.colhead .code,.jo.colhead .cust,.jo.colhead .metalcell,.jo.colhead .duecell,.jo.colhead .days{color:var(--ink3);font-family:var(--sans);font-size:12px;}
/* person-grouped services (Step 2) */
.pfilters{display:flex;gap:16px;flex-wrap:wrap;padding:6px 2px 12px;}
.pf{display:flex;align-items:center;gap:7px;font-size:10.5px;text-transform:uppercase;letter-spacing:.05em;color:var(--ink3);font-weight:600;}
.pf select{font-family:var(--sans);font-size:12.5px;font-weight:500;text-transform:none;letter-spacing:0;color:var(--ink);background:var(--card);border:1px solid var(--line2);border-radius:6px;padding:6px 10px;cursor:pointer;outline:none;}
.pf select:focus{border-color:var(--ink);}
.pgroup{margin:2px 0 6px;padding:0 2px;}
.pgroup-h{display:flex;align-items:center;gap:9px;padding:11px 2px;border-bottom:1px solid var(--line2);cursor:pointer;user-select:none;}
.pgroup-h:hover .pgroup-name{color:#000;}
.pgroup-caret{font-size:9px;color:var(--ink3);transition:transform .14s;display:inline-block;}
.pgroup.collapsed .pgroup-caret{transform:rotate(0deg);}
.pgroup:not(.collapsed) .pgroup-caret{transform:rotate(90deg);}
.pgroup-name{font-size:17px;font-weight:600;color:var(--ink);font-family:var(--sans);letter-spacing:0;}
.pgroup-n{margin-left:auto;font-size:10.5px;font-weight:600;color:var(--ink3);font-variant-numeric:tabular-nums;}
.pgroup-body{padding:2px 0 8px;}
.pgroup.collapsed .pgroup-body{display:none;}
.jo.jom .code{min-width:120px;}
.jo.jom .cust{flex:1;min-width:0;}
.metalcell{flex-shrink:0;min-width:150px;display:flex;justify-content:center;align-items:center;}
.metalcell .mpill{justify-content:center;}
.duecell{flex-shrink:0;min-width:80px;text-align:center;color:var(--ink2);font-variant-numeric:tabular-nums;font-size:16px;}
.mpill{display:inline-flex;overflow:hidden;border-radius:11px;font-size:13.5px;font-weight:600;line-height:1;white-space:nowrap;}
.mseg{padding:6px 11px;}
.mpill-none{background:#eceae5;color:var(--ink3);padding:5px 9px;font-weight:500;}

.overlay{display:none;position:fixed;inset:0;background:rgba(30,28,24,.42);align-items:center;justify-content:center;padding:20px;z-index:50;}
.overlay.open{display:flex;}
.panel{background:var(--card);border-radius:10px;max-width:520px;width:100%;overflow:hidden;box-shadow:0 18px 55px rgba(0,0,0,.24);max-height:90vh;overflow-y:auto;}
.pimg{width:100%;max-height:340px;object-fit:contain;background:#f1efe9;display:block;padding:10px;}
.pbody{padding:24px 28px 26px;}
.pcode{font-family:var(--mono);font-size:20px;font-weight:600;}
.pcust{font-family:var(--serif);font-size:22px;font-weight:600;margin-top:4px;}
.pdept{color:var(--ink2);font-size:13px;margin-bottom:22px;}
.pinfo{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px;}
.pinfo .k{font-size:10.5px;color:var(--ink3);text-transform:uppercase;letter-spacing:.05em;}
.pinfo .val{font-size:14px;font-weight:500;margin-top:3px;}
.jhead{font-size:11px;color:var(--ink2);text-transform:uppercase;letter-spacing:.06em;font-weight:600;margin-bottom:14px;padding-bottom:6px;border-bottom:1px solid var(--line);}
.jrow{display:flex;gap:12px;align-items:flex-start;position:relative;padding-bottom:16px;}
.jrow:last-child{padding-bottom:0;}
.jdot{width:10px;height:10px;border-radius:50%;background:var(--ink3);margin-top:3px;flex-shrink:0;}
.jrow.cur .jdot{background:var(--ink);box-shadow:0 0 0 4px var(--line);}
.jrow:not(:last-child):before{content:"";position:absolute;left:4.5px;top:13px;bottom:0;width:1px;background:var(--line2);}
.jstage{font-size:13px;font-weight:500;}
.jsince{font-size:11px;color:var(--ink3);font-family:var(--mono);}
.pclose{margin-top:22px;font-size:12.5px;color:var(--ink2);cursor:pointer;text-align:right;}
.pclose:hover{color:var(--ink);}
.jnote{font-size:12px;color:var(--ink3);margin-top:8px;line-height:1.5;}
</style></head><body>
<div class="top">
  <div class="title">Production Tracker</div>
  <div class="updated">Updated {{NOW}}</div>
</div>
<div class="rule"></div>
<div class="searchrow">
  <div class="search"><span class="ico">&#9906;</span><input id="q" placeholder="Search a JO number, then press Enter" onkeydown="if(event.key==='Enter')doSearch()"></div>
  <div class="search"><span class="ico">&#9906;</span><input id="qp" placeholder="Search an employee, then press Enter" onkeydown="if(event.key==='Enter')doPersonSearch()"></div>
</div>
<div class="stats">
  <div><div class="slab">In production</div><div class="snum">{{TOTAL}}</div></div>
  <div><div class="slab">Stuck 13+ days</div><div class="snum warn">{{STUCK}}</div></div>
</div>
<div id="boxesWrap"><div class="boxes">{{BOXES}}</div></div>
{{PANELS}}
<div id="personView" class="personview"></div>
<div class="overlay" id="ov" onclick="if(event.target===this)closeCard()"><div class="panel" id="panel"></div></div>
<div class="overlay" id="ovr" onclick="if(event.target===this)closeReport()"><div class="rpanel" id="rpanel"></div></div>
<script>
const DETAIL={{DETAIL}};
let FILTER="parent";
function fmtET(utc){
  try{
    const d=new Date(utc.replace(' ','T')+':00Z');
    return d.toLocaleString('en-US',{timeZone:'America/New_York',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'})+' ET';
  }catch(e){return utc+' UTC';}
}
function applyFilterToPanel(panel){
  // person-grouped stages handle their own row visibility (person + due + parent/sub)
  panel.querySelectorAll('.stage.personmode').forEach(st=>applyPersonFilters(st));
  // everything else: plain parent/sub visibility
  panel.querySelectorAll('.stage:not(.personmode) .jo:not(.colhead)').forEach(jo=>{
    const isSub=jo.dataset.sub==="1";
    let show=(FILTER==="all")||(FILTER==="parent"&&!isSub)||(FILTER==="sub"&&isSub);
    jo.style.display=show?"":"none";
  });
  // hide empty metal groups
  panel.querySelectorAll('.mgroup').forEach(g=>{
    const vis=[...g.querySelectorAll('.jo:not(.colhead)')].filter(j=>j.style.display!=="none").length;
    const n=g.querySelector('.mgroup-n'); if(n)n.textContent=vis;
    g.style.display=vis?"":"none";
  });
  panel.querySelectorAll('.stage:not(.personmode)').forEach(st=>{
    const vis=[...st.querySelectorAll('.jo:not(.colhead)')].filter(j=>j.style.display!=="none").length;
    st.querySelector('.stage-n').textContent=vis;
    st.style.display=vis?"":"none";
    const ch=st.querySelector('.colhead'); if(ch)ch.style.display=vis?"":"none";
  });
}
function openDept(id){
  document.getElementById('boxesWrap').style.display='none';
  const pv=document.getElementById('personView'); if(pv)pv.classList.remove('open');
  document.querySelectorAll('.deptpanel').forEach(p=>p.classList.remove('open'));
  const panel=document.getElementById('dept-'+id);
  panel.classList.add('open');
  panel.querySelectorAll('.stage').forEach(s=>s.classList.add('collapsed'));
  panel.querySelectorAll('.pgroup').forEach(g=>g.classList.add('collapsed'));
  FILTER="parent";
  applyFilterToPanel(panel);
  window.scrollTo(0,0);
  history.pushState({view:'dept'},'');
}
function closeDept(){
  if(history.state&&history.state.view==='dept'){history.back();return;}
  showBoxes();
}
function showBoxes(){
  document.querySelectorAll('.deptpanel').forEach(p=>p.classList.remove('open'));
  const pv=document.getElementById('personView'); if(pv)pv.classList.remove('open');
  document.getElementById('boxesWrap').style.display='';
}
function toggleStage(h){
  h.parentElement.classList.toggle('collapsed');
}
function togglePerson(h){
  h.parentElement.classList.toggle('collapsed');
}
function daysUntil(iso){
  if(!iso)return null;
  const t=new Date(iso+'T00:00:00');
  const now=new Date(); now.setHours(0,0,0,0);
  return Math.round((t-now)/86400000);
}
function applyPersonFilters(stage){
  const pv=stage.dataset.person||"__all__";
  const dv=stage.dataset.due||"__all__";
  stage.querySelectorAll('.jo.jom:not(.colhead)').forEach(jo=>{
    // respect parent/sub filter first
    const isSub=jo.dataset.sub==="1";
    let ok=(FILTER==="all")||(FILTER==="parent"&&!isSub)||(FILTER==="sub"&&isSub);
    if(ok&&pv!=="__all__") ok=(jo.dataset.person===pv);
    if(ok&&dv!=="__all__"){
      const du=daysUntil(jo.dataset.due);
      if(dv==="overdue") ok=(du!==null&&du<0);
      else ok=(du!==null&&du>=0&&du<=parseInt(dv,10));
    }
    jo.style.display=ok?"":"none";
  });
  // hide empty person groups + update counts
  const filtering=(pv!=="__all__")||(dv!=="__all__");
  stage.querySelectorAll('.pgroup').forEach(g=>{
    const vis=[...g.querySelectorAll('.jo.jom:not(.colhead)')].filter(j=>j.style.display!=="none").length;
    const n=g.querySelector('.pgroup-n'); if(n)n.textContent=vis;
    g.style.display=vis?"":"none";
    // when a filter is active, auto-expand matching groups so results are visible;
    // with no filter, leave groups collapsed (name list only)
    if(filtering) g.classList.remove('collapsed');
    else g.classList.add('collapsed');
  });
  const total=[...stage.querySelectorAll('.jo.jom:not(.colhead)')].filter(j=>j.style.display!=="none").length;
  stage.querySelector('.stage-n').textContent=total;
}
function filterPerson(sel){
  const stage=sel.closest('.stage');
  stage.dataset.person=sel.value;
  applyPersonFilters(stage);
}
function filterDue(sel){
  const stage=sel.closest('.stage');
  stage.dataset.due=sel.value;
  applyPersonFilters(stage);
}
function setFilter(btn,e){
  const panel=btn.closest('.deptpanel');
  panel.querySelectorAll('.seg button').forEach(b=>b.classList.remove('on'));
  btn.classList.add('on'); FILTER=btn.dataset.f;
  applyFilterToPanel(panel);
}
function showCard(code){
  const d=DETAIL[code];if(!d)return;
  let j='';
  if(d.journey&&d.journey.length){
    d.journey.forEach((s,i)=>{const cur=i===d.journey.length-1?' cur':'';
      j+='<div class="jrow'+cur+'"><div class="jdot"></div><div><div class="jstage">'+s.stage+'</div><div class="jsince">since '+fmtET(s.since)+'</div></div></div>';});
  }else{j='<div class="jrow cur"><div class="jdot"></div><div><div class="jstage">'+(d.stage||'')+'</div><div class="jsince">current</div></div></div>';}
  const note=(!d.journey||d.journey.length<2)?'<div class="jnote">Journey builds as this order moves through stages.</div>':'';
  const img=d.img?'<img class="pimg" src="'+d.img+'" loading="lazy" onerror="this.style.display=\'none\'">':'';
  const days=(d.days!==null&&d.days!==undefined)?d.days+' days':'\u2014';
  const info='<div class="pinfo">'+
    '<div><div class="k">Current stage</div><div class="val">'+(d.stage||'\u2014')+'</div></div>'+
    '<div><div class="k">Days in stage</div><div class="val">'+days+'</div></div>'+
    '<div><div class="k">Due date</div><div class="val">'+(d.due||'\u2014')+'</div></div>'+
    '<div><div class="k">Metal</div><div class="val">'+(d.metal||'\u2014')+'</div></div>'+
    '<div><div class="k">Assigned to</div><div class="val">'+(d.assigned||'\u2014')+'</div></div>'+
    '</div>';
  document.getElementById('panel').innerHTML=img+'<div class="pbody"><div class="pcode">'+code+'</div><div class="pcust">'+d.cust+'</div><div class="pdept">'+d.dept+'</div>'+info+'<div class="jhead">Journey</div>'+j+note+'<div class="pclose" onclick="closeCard()">Close</div></div>';
  document.getElementById('ov').classList.add('open');
}
function closeCard(){document.getElementById('ov').classList.remove('open');}
window.addEventListener('popstate',function(){
  document.getElementById('ov').classList.remove('open');
  showBoxes();
});
// ---- Report builder ----
// Each column: [key, label, valueFn(code, detail)]  (image handled specially)
const REPORT_COLS=[
  ["image","Image",(c,d)=>d.img||""],
  ["jo","JO #",(c,d)=>c],
  ["cust","Customer",(c,d)=>d.cust||""],
  ["service","Service",(c,d)=>d.stage||""],
  ["dept","Department",(c,d)=>d.dept||""],
  ["assigned","Assigned to",(c,d)=>d.assigned||""],
  ["metal","Metal",(c,d)=>d.metal||""],
  ["due","Due date",(c,d)=>d.dueISO||""],
  ["days","Days in service",(c,d)=>(d.days!=null?d.days:"")],
  ["status","Status",(c,d)=>d.status||""],
  ["sku","SKU",(c,d)=>d.sku||""],
  ["skutype","SKU type",(c,d)=>d.skutype||""],
  ["price","Total price",(c,d)=>d.price||""],
  ["orderDate","Order date",(c,d)=>d.orderDate||""],
  ["address","Customer address",(c,d)=>d.address||""],
];
const REPORT_DEFAULT=new Set(["image","jo","cust","service","assigned","metal","due","days"]);
let REPORT_CODES=[], REPORT_STAGE="";
function openReport(btn){
  REPORT_STAGE=btn.dataset.stage||"";
  REPORT_CODES=(btn.dataset.codes||"").split(",").filter(Boolean);
  const cols=REPORT_COLS.map(([k,label])=>{
    const on=REPORT_DEFAULT.has(k)?"checked":"";
    return '<label class="rp-col"><input type="checkbox" value="'+k+'" '+on+'>'+label+'</label>';
  }).join("");
  document.getElementById('rpanel').innerHTML=
    '<div class="rp-h"><div class="rp-title">Create customized report</div>'+
    '<div class="rp-sub">'+REPORT_STAGE+' &middot; '+REPORT_CODES.length+' orders. Choose columns to include.</div></div>'+
    '<div class="rp-body"><div class="rp-seclabel">Columns</div>'+
    '<div class="rp-cols">'+cols+'</div>'+
    '<div class="rp-progress" id="rpProgress" style="display:none"><div class="rp-bar"><div class="rp-bar-fill" id="rpBarFill"></div></div><div class="rp-progtext" id="rpProgText"></div></div>'+
    '</div>'+
    '<div class="rp-actions">'+
    '<button class="rp-selall" onclick="toggleAllCols()">Select all / none</button>'+
    '<button class="rp-cancel" onclick="closeReport()">Cancel</button>'+
    '<button class="rp-export" id="rpExport" onclick="exportReport()">Download Excel</button></div>';
  document.getElementById('ovr').classList.add('open');
}
function toggleAllCols(){
  const boxes=[...document.querySelectorAll('#rpanel .rp-col input')];
  const anyOff=boxes.some(b=>!b.checked);
  boxes.forEach(b=>b.checked=anyOff);
}
function closeReport(){document.getElementById('ovr').classList.remove('open');}

async function fetchImageAsBase64(url){
  try{
    const resp=await fetch(url,{credentials:'include'});
    if(!resp.ok) return null;
    const blob=await resp.blob();
    return await new Promise((res,rej)=>{
      const r=new FileReader();
      r.onloadend=()=>res(r.result); // data URL
      r.onerror=rej;
      r.readAsDataURL(blob);
    });
  }catch(e){ return null; }
}

async function exportReport(){
  const chosen=[...document.querySelectorAll('#rpanel .rp-col input')].filter(b=>b.checked).map(b=>b.value);
  if(!chosen.length){alert('Pick at least one column.');return;}
  const colDefs=REPORT_COLS.filter(([k])=>chosen.includes(k));
  const wantImages=chosen.includes('image');

  const wb=new ExcelJS.Workbook();
  const safe=REPORT_STAGE.replace(/[^A-Za-z0-9 ]/g,'').slice(0,28)||'Report';
  const ws=wb.addWorksheet(safe);

  // header row
  ws.addRow(colDefs.map(([k,label])=>label));
  ws.getRow(1).font={bold:true};
  ws.getRow(1).height=20;

  // column widths
  ws.columns=colDefs.map(([k])=>{
    if(k==='image') return {width:14};
    if(k==='address') return {width:40};
    if(k==='cust') return {width:26};
    return {width:16};
  });

  const exportBtn=document.getElementById('rpExport');
  const prog=document.getElementById('rpProgress');
  const fill=document.getElementById('rpBarFill');
  const ptext=document.getElementById('rpProgText');
  exportBtn.disabled=true;

  const imgColIndex=colDefs.findIndex(([k])=>k==='image'); // 0-based
  let r=2;
  for(let i=0;i<REPORT_CODES.length;i++){
    const code=REPORT_CODES[i];
    const d=DETAIL[code]; if(!d){continue;}
    const rowVals=colDefs.map(([k,label,fn])=> k==='image' ? '' : fn(code,d));
    const row=ws.addRow(rowVals);
    if(wantImages){
      prog.style.display='block';
      const pct=Math.round(((i+1)/REPORT_CODES.length)*100);
      fill.style.width=pct+'%';
      ptext.textContent='Fetching images '+(i+1)+' / '+REPORT_CODES.length;
      row.height=54;
      if(d.img){
        const dataUrl=await fetchImageAsBase64(d.img);
        if(dataUrl){
          const ext=dataUrl.substring(dataUrl.indexOf('/')+1,dataUrl.indexOf(';'));
          const imgId=wb.addImage({base64:dataUrl, extension:(ext==='jpeg'?'jpeg':(ext==='png'?'png':'jpeg'))});
          ws.addImage(imgId,{tl:{col:imgColIndex, row:r-1}, ext:{width:70,height:70}});
        }
      }
    }
    r++;
  }

  ptext && (ptext.textContent='Building file...');
  const buf=await wb.xlsx.writeBuffer();
  const blob=new Blob([buf],{type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'});
  const a=document.createElement('a');
  const today=new Date().toISOString().slice(0,10);
  a.href=URL.createObjectURL(blob);
  a.download=safe.replace(/ /g,'_')+'_'+today+'.xlsx';
  a.click();
  URL.revokeObjectURL(a.href);
  exportBtn.disabled=false;
  closeReport();
}
function doSearch(){
  const q=document.getElementById('q').value.trim().toLowerCase();if(!q)return;
  const hit=Object.keys(DETAIL).find(c=>c.toLowerCase()===q)||Object.keys(DETAIL).find(c=>c.toLowerCase().includes(q));
  if(hit)showCard(hit);
}
function normName(s){return (s||'').trim().toLowerCase();}
function doPersonSearch(){
  const q=normName(document.getElementById('qp').value);
  if(!q)return;
  // collect all assigned names present in the data
  const names={};
  Object.values(DETAIL).forEach(d=>{const a=(d.assigned||'').trim(); if(a) names[a]=(names[a]||0)+1;});
  const allNames=Object.keys(names);
  // exact match first, else the closest "contains" match by most orders
  let target=allNames.find(n=>normName(n)===q);
  if(!target){
    const partial=allNames.filter(n=>normName(n).includes(q)).sort((a,b)=>names[b]-names[a]);
    target=partial[0];
  }
  renderPersonResults(target);
}
function renderPersonResults(name){
  const view=document.getElementById('personView');
  if(!name){
    view.innerHTML='<button class="pv-back" onclick="closePerson()">&#8592; Back</button>'+
      '<div class="pv-h"><div class="pv-name">No match</div></div>'+
      '<div class="pr-none">No employee found by that name. Try a first or last name as it appears in the system.</div>';
    showPersonView();
    return;
  }
  // gather this person's active JOs
  const items=Object.keys(DETAIL).filter(c=>(DETAIL[c].assigned||'').trim()===name)
    .map(c=>({code:c,...DETAIL[c]}));
  // group by current stage, stages sorted by how many each holds
  const byStage={};
  items.forEach(it=>{const s=it.stage||'(no stage)'; (byStage[s]=byStage[s]||[]).push(it);});
  const stages=Object.keys(byStage).sort((a,b)=>byStage[b].length-byStage[a].length);
  const colhead='<div class="pr-row pr-colhead">'+
    '<span class="code">JO</span>'+
    '<span class="cust">Customer</span>'+
    '<span class="metalcell">Metal</span>'+
    '<span class="duecell">Due date</span>'+
    '<span class="days">Days in service</span></div>';
  let body='';
  stages.forEach(s=>{
    const rows=byStage[s].sort((a,b)=>(a.due||'').localeCompare(b.due||''));
    let r='';
    rows.forEach(it=>{
      const stuck=(typeof it.days==='number'&&it.days>=13)?' stuck':'';
      r+='<div class="pr-row" onclick="fromPerson(\''+it.code+'\')">'+
         '<span class="code">'+it.code+'</span>'+
         '<span class="cust">'+(it.cust||'')+'</span>'+
         '<span class="metalcell">'+(it.pill||'')+'</span>'+
         '<span class="duecell">'+(it.due||'')+'</span>'+
         '<span class="days'+stuck+'">'+(it.days!=null?it.days+'d':'')+'</span></div>';
    });
    body+='<div class="pr-stage">'+s+' &middot; '+byStage[s].length+'</div>'+colhead+r;
  });
  view.innerHTML='<button class="pv-back" onclick="closePerson()">&#8592; Back</button>'+
    '<div class="pv-h"><div class="pv-name">'+name+'</div>'+
    '<div class="pv-sub">'+items.length+' active '+(items.length===1?'order':'orders')+
    ' across '+stages.length+' '+(stages.length===1?'stage':'stages')+'</div></div>'+body;
  showPersonView();
}
function showPersonView(){
  document.querySelectorAll('.deptpanel').forEach(p=>p.classList.remove('open'));
  document.getElementById('boxesWrap').style.display='none';
  document.getElementById('personView').classList.add('open');
  window.scrollTo(0,0);
  history.pushState({view:'person'},'');
}
function fromPerson(code){
  showCard(code);
}
function closePerson(){
  document.getElementById('personView').classList.remove('open');
  showBoxes();
}
</script></body></html>"""

if __name__=="__main__":
    main()