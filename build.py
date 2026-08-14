"""
build.py - reads orders.json + history.json, writes index.html.
Collapsible departments (collapsed by default). Click an order to see its journey.
Run: python3 build.py
"""
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
DEPT_ORDER = ["CAD","Printing / Casting","Stones","Shop","Customer Service","Other"]
DEPT_COLOR = {"CAD":"#6b6fb0","Printing / Casting":"#c08a4a","Shop":"#5b9279",
              "Stones":"#a86b8a","Customer Service":"#5b83a8","Other":"#8a8577"}

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

    total=len(rows)
    stuck=sum(1 for o in rows if isinstance(o.get("daysInCurrentService"),int) and o["daysInCurrentService"]>=13)
    now=datetime.datetime.now().strftime("%b %d, %Y  %I:%M %p")

    # per-order detail incl. history, for the click panel
    detail={}
    for o in rows:
        c=o.get("code","")
        detail[c]={"cust":o.get("customerName",""),"stage":o.get("currentService",""),
                   "days":o.get("daysInCurrentService",""),"dept":dept_of(o.get("currentService","")),
                   "journey":history.get(c,[])}

    depts_html=""
    for d in DEPT_ORDER:
        if d not in grouped: continue
        col=DEPT_COLOR[d]
        dtotal=sum(len(v) for v in grouped[d].values())
        stages_html=""
        for stage in sorted(grouped[d], key=lambda s:-len(grouped[d][s])):
            olist=sorted(grouped[d][stage], key=lambda x:-(x.get("daysInCurrentService") or 0))
            items=""
            for o in olist:
                dd=o.get("daysInCurrentService")
                sc=" stuck" if isinstance(dd,int) and dd>=13 else ""
                c=html.escape(o.get("code",""))
                items+=f'<div class="jo{sc}" onclick="showJourney(\'{c}\')"><span class="code">{c}</span><span class="cust">{html.escape((o.get("customerName") or "")[:24])}</span><span class="days">{dd if dd is not None else ""}d</span></div>'
            stages_html+=f'<div class="stage"><div class="stage-h"><span>{html.escape(stage)}</span><span class="stage-n">{len(olist)}</span></div>{items}</div>'
        depts_html+=f'<div class="dept"><button class="dept-h" onclick="toggleDept(this)" style="--c:{col}"><span class="chev">&#9656;</span><span class="dot"></span><span class="dept-name">{html.escape(d)}</span><span class="dept-n">{dtotal}</span></button><div class="dept-body">{stages_html}</div></div>'

    page=PAGE.replace("{{DEPTS}}",depts_html).replace("{{NOW}}",now)\
             .replace("{{TOTAL}}",str(total)).replace("{{STUCK}}",str(stuck))\
             .replace("{{DETAIL}}",json.dumps(detail))
    open("index.html","w").write(page)
    print(f"Built index.html ({total} orders, history on {len(history)} orders)")

PAGE=r"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Production Tracker</title>
<meta http-equiv="refresh" content="3600">
<style>
:root{--bg:#f4f2ee;--card:#fbfaf8;--ink:#33302b;--ink2:#7d7869;--ink3:#a8a293;--line:#e5e1d8;
--font:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;--mono:'SF Mono',ui-monospace,Menlo,monospace;}
*{margin:0;padding:0;box-sizing:border-box;}
body{background:var(--bg);color:var(--ink);font-family:var(--font);padding:24px 30px;}
.top{display:flex;align-items:center;gap:20px;margin-bottom:20px;flex-wrap:wrap;}
.h1{font-size:20px;font-weight:600;display:flex;align-items:center;}
.h1 .dot{width:8px;height:8px;border-radius:50%;background:#5b9279;margin-right:9px;}
.search{flex:1;max-width:420px;position:relative;}
.search input{width:100%;height:36px;border:1px solid var(--line);border-radius:9px;padding:0 12px 0 34px;font-size:13px;background:var(--card);outline:none;font-family:var(--font);}
.search .ico{position:absolute;left:12px;top:9px;color:var(--ink3);}
.updated{margin-left:auto;font-size:12px;color:var(--ink3);font-family:var(--mono);}
.stats{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin-bottom:22px;max-width:360px;}
.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:13px 16px;}
.stat .l{font-size:12px;color:var(--ink2);}
.stat .v{font-size:24px;font-weight:600;margin-top:3px;}
.stat .v.warn{color:#b07a3c;}
.depts{display:flex;flex-direction:column;gap:10px;max-width:760px;}
.dept{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;}
.dept-h{width:100%;display:flex;align-items:center;gap:10px;padding:15px 18px;background:none;border:none;cursor:pointer;font-family:var(--font);font-size:15px;color:var(--ink);}
.dept-h .chev{color:var(--ink3);font-size:11px;transition:transform .15s;}
.dept-h.open .chev{transform:rotate(90deg);}
.dept-h .dot{width:10px;height:10px;border-radius:3px;background:var(--c);}
.dept-name{font-weight:600;}
.dept-n{margin-left:auto;font-weight:600;color:var(--ink2);}
.dept-body{display:none;padding:0 18px 14px;}
.dept-body.open{display:block;}
.stage{margin-top:12px;}
.stage-h{display:flex;justify-content:space-between;font-size:12px;font-weight:600;color:var(--ink2);text-transform:uppercase;letter-spacing:.03em;margin-bottom:5px;}
.stage-n{color:var(--ink3);}
.jo{display:flex;align-items:baseline;gap:8px;font-size:12px;padding:5px 0;border-bottom:1px solid #f0ede6;cursor:pointer;}
.jo:hover{background:#f2efe9;}
.jo .code{font-family:var(--mono);font-size:11.5px;}
.jo .cust{flex:1;color:var(--ink2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.jo .days{color:var(--ink3);font-variant-numeric:tabular-nums;}
.jo.stuck .days{color:#b07a3c;font-weight:600;}
.overlay{display:none;position:fixed;inset:0;background:rgba(40,38,34,.35);align-items:center;justify-content:center;padding:20px;z-index:50;}
.overlay.open{display:flex;}
.panel{background:var(--card);border-radius:14px;max-width:440px;width:100%;padding:24px;box-shadow:0 12px 40px rgba(0,0,0,.18);}
.panel .pcode{font-family:var(--mono);font-size:20px;font-weight:600;}
.panel .pcust{color:var(--ink2);font-size:14px;margin-top:2px;margin-bottom:18px;}
.jrow{display:flex;gap:12px;align-items:flex-start;position:relative;padding-bottom:16px;}
.jrow:last-child{padding-bottom:0;}
.jdot{width:11px;height:11px;border-radius:50%;background:var(--ink3);margin-top:3px;flex-shrink:0;}
.jrow.cur .jdot{background:#5b9279;box-shadow:0 0 0 4px #dbe7e0;}
.jrow:not(:last-child):before{content:"";position:absolute;left:5px;top:14px;bottom:0;width:1px;background:var(--line);}
.jstage{font-size:13px;font-weight:600;}
.jsince{font-size:11px;color:var(--ink3);font-family:var(--mono);}
.pclose{margin-top:18px;font-size:12px;color:var(--ink3);cursor:pointer;text-align:right;}
.jnote{font-size:12px;color:var(--ink3);margin-top:6px;}
</style></head><body>
<div class="top">
  <div class="h1"><span class="dot"></span>Production Tracker</div>
  <div class="search"><span class="ico">&#9906;</span><input id="q" placeholder="Search a JO number..." oninput="doSearch()"></div>
  <div class="updated">Last updated: {{NOW}}</div>
</div>
<div class="stats">
  <div class="stat"><div class="l">Orders shown</div><div class="v">{{TOTAL}}</div></div>
  <div class="stat"><div class="l">Stuck 13+ days</div><div class="v warn">{{STUCK}}</div></div>
</div>
<div class="depts">{{DEPTS}}</div>
<div class="overlay" id="ov" onclick="if(event.target===this)closeJourney()">
  <div class="panel" id="panel"></div>
</div>
<script>
const DETAIL={{DETAIL}};
function toggleDept(btn){btn.classList.toggle('open');btn.nextElementSibling.classList.toggle('open');}
function showJourney(code){
  const d=DETAIL[code];if(!d)return;
  let j='';
  if(d.journey&&d.journey.length){
    d.journey.forEach((s,i)=>{
      const cur=i===d.journey.length-1?' cur':'';
      j+='<div class="jrow'+cur+'"><div class="jdot"></div><div><div class="jstage">'+s.stage+'</div><div class="jsince">since '+s.since+' UTC</div></div></div>';
    });
  } else {
    j='<div class="jrow cur"><div class="jdot"></div><div><div class="jstage">'+d.stage+'</div><div class="jsince">current</div></div></div>';
  }
  const note=(!d.journey||d.journey.length<2)?'<div class="jnote">History builds as the order moves. More stages will appear here over time.</div>':'';
  document.getElementById('panel').innerHTML=
    '<div class="pcode">'+code+'</div><div class="pcust">'+d.cust+' &middot; '+d.dept+'</div>'+j+note+
    '<div class="pclose" onclick="closeJourney()">Close</div>';
  document.getElementById('ov').classList.add('open');
}
function closeJourney(){document.getElementById('ov').classList.remove('open');}
function doSearch(){
  const q=document.getElementById('q').value.trim().toLowerCase();
  if(!q)return;
  const hit=Object.keys(DETAIL).find(c=>c.toLowerCase()===q)||Object.keys(DETAIL).find(c=>c.toLowerCase().includes(q));
  if(hit)showJourney(hit);
}
</script></body></html>"""

if __name__=="__main__":
    main()