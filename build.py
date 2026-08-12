import json, datetime, html, re

STALE_DAYS = 0
SHOW_SUBORDERS = True

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
DEPT_COLOR = {"CAD":"#6b6fb0","Printing / Casting":"#c08a4a","Shop":"#5b9279",
              "Stones":"#a86b8a","Customer Service":"#5b83a8","Other":"#8a8577"}

def dept_of(stage):
    s = (stage or "").strip()
    for d, stages in DEPARTMENTS.items():
        if s in stages:
            return d
    return "Other"

def is_sub(code):
    return bool(re.match(r'^JO-\d+-\d+', code or ""))

def load():
    d = json.load(open("orders.json", encoding="utf-8-sig"))
    return d.get("value", [])

def main():
    orders = load()
    rows = []
    for o in orders:
        if not SHOW_SUBORDERS and is_sub(o.get("code","")):
            continue
        days = o.get("daysInCurrentService")
        if STALE_DAYS and isinstance(days, int) and days >= STALE_DAYS:
            continue
        rows.append(o)

    grouped = {}
    for o in rows:
        stage = (o.get("currentService") or "(no stage)").strip()
        d = dept_of(stage)
        grouped.setdefault(d, {}).setdefault(stage, []).append(o)

    order_depts = ["CAD","Printing / Casting","Stones","Shop","Customer Service","Other"]
    total = len(rows)
    urgent = sum(1 for o in rows if str(o.get("priority","")).upper()=="URGENT")
    stuck = sum(1 for o in rows if isinstance(o.get("daysInCurrentService"),int) and o["daysInCurrentService"]>=13)
    now = datetime.datetime.now().strftime("%b %d, %Y  %I:%M %p")

    search_data = [{"code":o.get("code",""),"cust":o.get("customerName",""),
                    "stage":o.get("currentService",""),"days":o.get("daysInCurrentService",""),
                    "dept":dept_of(o.get("currentService",""))} for o in rows]

    cards = ""
    for d in order_depts:
        if d not in grouped: continue
        col = DEPT_COLOR[d]
        dtotal = sum(len(v) for v in grouped[d].values())
        stage_blocks = ""
        for stage in sorted(grouped[d], key=lambda s:-len(grouped[d][s])):
            olist = grouped[d][stage]
            items = ""
            for o in sorted(olist, key=lambda x:-(x.get("daysInCurrentService") or 0)):
                dd = o.get("daysInCurrentService")
                stuck_cls = " stuck" if isinstance(dd,int) and dd>=13 else ""
                items += '<div class="jo'+stuck_cls+'"><span class="code">'+html.escape(o.get("code",""))+'</span><span class="cust">'+html.escape((o.get("customerName") or "")[:22])+'</span><span class="days">'+(str(dd) if dd is not None else "")+'d</span></div>'
            stage_blocks += '<div class="stage"><div class="stage-h"><span>'+html.escape(stage)+'</span><span class="stage-n">'+str(len(olist))+'</span></div>'+items+'</div>'
        cards += '<div class="dept"><div class="dept-h" style="--c:'+col+'"><span class="dot"></span><span class="dept-name">'+html.escape(d)+'</span><span class="dept-n">'+str(dtotal)+'</span></div>'+stage_blocks+'</div>'

    page = PAGE.replace("{{CARDS}}", cards).replace("{{NOW}}", now)\
               .replace("{{TOTAL}}", str(total)).replace("{{URGENT}}", str(urgent))\
               .replace("{{STUCK}}", str(stuck)).replace("{{SEARCH}}", json.dumps(search_data))
    open("index.html","w").write(page)
    print("Built index.html  ("+str(total)+" orders shown)")

PAGE = r"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Production Tracker</title>
<meta http-equiv="refresh" content="300">
<style>
:root{--bg:#f4f2ee;--card:#fbfaf8;--ink:#33302b;--ink2:#7d7869;--ink3:#a8a293;--line:#e5e1d8;
--font:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;--mono:'SF Mono',ui-monospace,Menlo,monospace;}
*{margin:0;padding:0;box-sizing:border-box;}
body{background:var(--bg);color:var(--ink);font-family:var(--font);padding:24px 30px;}
.top{display:flex;align-items:center;gap:20px;margin-bottom:4px;flex-wrap:wrap;}
.h1{font-size:20px;font-weight:600;}
.h1 .dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#5b9279;margin-right:9px;}
.search{flex:1;max-width:420px;position:relative;}
.search input{width:100%;height:36px;border:1px solid var(--line);border-radius:9px;padding:0 12px 0 34px;font-size:13px;background:var(--card);outline:none;font-family:var(--font);}
.search .ico{position:absolute;left:12px;top:9px;color:var(--ink3);}
.updated{margin-left:auto;font-size:12px;color:var(--ink3);font-family:var(--mono);}
.sub{font-size:13px;color:var(--ink2);margin-bottom:20px;}
#result{margin-bottom:20px;}
.rcard{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 20px;}
.rcard .rcode{font-family:var(--mono);font-size:18px;font-weight:600;}
.rcard .rrow{font-size:13px;color:var(--ink2);margin-top:6px;}
.rcard .rrow b{color:var(--ink);font-weight:600;}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:24px;max-width:520px;}
.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:13px 16px;}
.stat .l{font-size:12px;color:var(--ink2);}
.stat .v{font-size:24px;font-weight:600;margin-top:3px;}
.stat .v.warn{color:#b07a3c;}
.board{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px;align-items:start;}
.dept{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;}
.dept-h{display:flex;align-items:center;gap:9px;padding-bottom:11px;margin-bottom:11px;border-bottom:1px solid var(--line);}
.dept-h .dot{width:10px;height:10px;border-radius:3px;background:var(--c);}
.dept-name{font-weight:600;font-size:15px;}
.dept-n{margin-left:auto;font-size:15px;font-weight:600;color:var(--ink2);}
.stage{margin-bottom:12px;}
.stage-h{display:flex;justify-content:space-between;font-size:12px;font-weight:600;color:var(--ink2);text-transform:uppercase;letter-spacing:.03em;margin-bottom:5px;}
.stage-n{color:var(--ink3);}
.jo{display:flex;align-items:baseline;gap:8px;font-size:12px;padding:3px 0;border-bottom:1px solid #f0ede6;}
.jo .code{font-family:var(--mono);font-size:11.5px;}
.jo .cust{flex:1;color:var(--ink2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.jo .days{color:var(--ink3);font-variant-numeric:tabular-nums;}
.jo.stuck .days{color:#b07a3c;font-weight:600;}
</style></head><body>
<div class="top">
  <div class="h1"><span class="dot"></span>Production Tracker</div>
  <div class="search"><span class="ico">&#9906;</span><input id="q" placeholder="Search a JO number..." oninput="doSearch()"></div>
  <div class="updated">updated {{NOW}}</div>
</div>
<div class="sub">Live board &middot; grouped by department and stage &middot; auto-refreshes every 5 min</div>
<div id="result"></div>
<div class="stats">
  <div class="stat"><div class="l">Orders shown</div><div class="v">{{TOTAL}}</div></div>
  <div class="stat"><div class="l">Urgent</div><div class="v">{{URGENT}}</div></div>
  <div class="stat"><div class="l">Stuck 13+ days</div><div class="v warn">{{STUCK}}</div></div>
</div>
<div class="board">{{CARDS}}</div>
<script>
const DATA = {{SEARCH}};
function doSearch(){
  const q=document.getElementById('q').value.trim().toLowerCase();
  const r=document.getElementById('result');
  if(!q){r.innerHTML='';return;}
  const hit=DATA.find(o=>o.code.toLowerCase()===q)||DATA.find(o=>o.code.toLowerCase().includes(q));
  if(!hit){r.innerHTML='<div class="rcard">No order matching "'+q+'"</div>';return;}
  r.innerHTML='<div class="rcard"><div class="rcode">'+hit.code+'</div>'+
    '<div class="rrow">Customer: <b>'+hit.cust+'</b></div>'+
    '<div class="rrow">Department: <b>'+hit.dept+'</b> &middot; Stage: <b>'+hit.stage+'</b></div>'+
    '<div class="rrow">Days in current stage: <b>'+hit.days+'</b></div></div>';
}
</script></body></html>"""

if __name__ == "__main__":
    main()
