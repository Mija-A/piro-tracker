"""
build.py - reads orders.json + history.json, writes index.html.
Clean serif/sans dashboard: outlined department boxes (grid) -> click opens a
department's stages/orders -> click an order for image + journey card.
Defaults to parents-only view (suborders are material sub-tasks; toggle to see them).
Run: python3 build.py
"""
import json, datetime, html, re
from zoneinfo import ZoneInfo

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

    # headline stats reflect PARENTS ONLY (suborders are material sub-tasks / noise)
    parent_rows_all=[o for o in rows if not is_sub(o.get("code",""))]
    total=len(parent_rows_all)
    stuck=sum(1 for o in parent_rows_all if isinstance(o.get("daysInCurrentService"),int) and o["daysInCurrentService"]>=13)
    now=datetime.datetime.now(ZoneInfo("America/New_York")).strftime("%b %d, %Y  %I:%M %p")+" ET"

    detail={}
    for o in rows:
        c=o.get("code","")
        detail[c]={"cust":o.get("customerName") or "","stage":o.get("currentService") or "",
                   "days":o.get("daysInCurrentService"),"dept":dept_of(o.get("currentService","")),
                   "img":o.get("imageURL") or "","metal":o.get("metals") or "",
                   "assigned":o.get("serviceAssignedUser") or "","journey":history.get(c,[])}

    boxes_html=""; panels_html=""
    for d in DEPT_ORDER:
        if d not in grouped: continue
        drows=[o for st in grouped[d].values() for o in st]
        parent_rows=[o for o in drows if not is_sub(o.get("code",""))]
        dtotal=len(parent_rows)   # box count = parents only
        dstuck=sum(1 for o in parent_rows if isinstance(o.get("daysInCurrentService"),int) and o["daysInCurrentService"]>=13)
        did=d.replace(" ","").replace("/","")
        boxes_html+=f'<button class="box" onclick="openDept(\'{did}\')"><div class="bname">{html.escape(d)}</div><div class="bnum">{dtotal}</div><div class="bsub">{dstuck} stuck</div></button>'
        stages_html=""
        for stage in sorted(grouped[d], key=lambda s:-len(grouped[d][s])):
            olist=sorted(grouped[d][stage], key=lambda x:-(x.get("daysInCurrentService") or 0))
            items=""
            for o in olist:
                dd=o.get("daysInCurrentService")
                sc=" stuck" if isinstance(dd,int) and dd>=13 else ""
                c=html.escape(o.get("code",""))
                sub=1 if is_sub(o.get("code","")) else 0
                items+=f'<div class="jo{sc}" data-sub="{sub}" onclick="showCard(\'{c}\')"><span class="code">{c}</span><span class="cust">{html.escape((o.get("customerName") or "")[:28])}</span><span class="days">{dd if dd is not None else ""}d</span></div>'
            stages_html+=f'<div class="stage"><div class="stage-h"><span>{html.escape(stage)}</span><span class="stage-n">{len(olist)}</span></div>{items}</div>'
        panels_html+=f'<div class="deptpanel" id="dept-{did}"><button class="back" onclick="closeDept()">&#8592; All departments</button><div class="dp-h"><span class="dp-name">{html.escape(d)}</span><span class="dp-n">{dtotal}</span></div><div class="controls"><div class="seg"><button data-f="all" onclick="setFilter(this,event)">All</button><button class="on" data-f="parent" onclick="setFilter(this,event)">Parents</button><button data-f="sub" onclick="setFilter(this,event)">Suborders</button></div></div>{stages_html}</div>'

    page=PAGE.replace("{{BOXES}}",boxes_html).replace("{{PANELS}}",panels_html).replace("{{NOW}}",now)\
             .replace("{{TOTAL}}",str(total)).replace("{{STUCK}}",str(stuck))\
             .replace("{{DETAIL}}",json.dumps(detail))
    open("index.html","w").write(page)
    print(f"Built index.html ({total} parent orders shown, history on {len(history)} orders)")

PAGE=r"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Production Tracker</title>
<meta http-equiv="refresh" content="3600">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{--bg:#f6f5f1;--card:#fdfcfa;--ink:#2a2824;--ink2:#6f6a61;--ink3:#a29c90;--line:#e0dcd2;--line2:#c9c4b8;
--serif:'Cormorant Garamond',Georgia,serif;--sans:'Inter',-apple-system,sans-serif;--mono:'SF Mono',ui-monospace,Menlo,monospace;}
*{margin:0;padding:0;box-sizing:border-box;}
body{background:var(--bg);color:var(--ink);font-family:var(--sans);padding:34px 44px;font-size:14px;}
.top{display:flex;align-items:baseline;gap:18px;margin-bottom:6px;flex-wrap:wrap;}
.title{font-family:var(--serif);font-size:30px;font-weight:600;letter-spacing:.01em;}
.updated{margin-left:auto;font-size:11px;color:var(--ink3);letter-spacing:.03em;text-transform:uppercase;}
.rule{height:1px;background:var(--ink);opacity:.82;margin-bottom:26px;}
.search{position:relative;max-width:380px;margin-bottom:26px;}
.search input{width:100%;height:40px;border:1px solid var(--line2);border-radius:6px;padding:0 12px 0 36px;font-size:13.5px;background:var(--card);outline:none;font-family:var(--sans);}
.search input:focus{border-color:var(--ink);}
.search .ico{position:absolute;left:13px;top:11px;color:var(--ink3);}
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
.stage{margin-top:22px;}
.stage-h{display:flex;justify-content:space-between;font-size:11px;font-weight:600;color:var(--ink2);text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px;padding-bottom:5px;border-bottom:1px solid var(--line);}
.stage-n{color:var(--ink3);}
.jo{display:flex;align-items:baseline;gap:12px;font-size:13.5px;padding:8px 6px;border-bottom:1px solid var(--line);cursor:pointer;}
.jo:hover{background:var(--card);}
.jo .code{font-family:var(--mono);font-size:12px;min-width:150px;}
.jo .cust{flex:1;color:var(--ink2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.jo .days{color:var(--ink3);font-variant-numeric:tabular-nums;min-width:44px;text-align:right;}
.jo.stuck .days{color:#8a5a30;font-weight:600;}
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
<div class="search"><span class="ico">&#9906;</span><input id="q" placeholder="Search a JO number, then press Enter" onkeydown="if(event.key==='Enter')doSearch()"></div>
<div class="stats">
  <div><div class="slab">In production</div><div class="snum">{{TOTAL}}</div></div>
  <div><div class="slab">Stuck 13+ days</div><div class="snum warn">{{STUCK}}</div></div>
</div>
<div id="boxesWrap"><div class="boxes">{{BOXES}}</div></div>
{{PANELS}}
<div class="overlay" id="ov" onclick="if(event.target===this)closeCard()"><div class="panel" id="panel"></div></div>
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
  panel.querySelectorAll('.jo').forEach(jo=>{
    const isSub=jo.dataset.sub==="1";
    let show=(FILTER==="all")||(FILTER==="parent"&&!isSub)||(FILTER==="sub"&&isSub);
    jo.style.display=show?"":"none";
  });
  panel.querySelectorAll('.stage').forEach(st=>{
    const vis=[...st.querySelectorAll('.jo')].filter(j=>j.style.display!=="none").length;
    st.querySelector('.stage-n').textContent=vis;
    st.style.display=vis?"":"none";
  });
}
function openDept(id){
  document.getElementById('boxesWrap').style.display='none';
  document.querySelectorAll('.deptpanel').forEach(p=>p.classList.remove('open'));
  const panel=document.getElementById('dept-'+id);
  panel.classList.add('open');
  FILTER="parent";
  panel.querySelectorAll('.seg button').forEach(b=>b.classList.remove('on'));
  panel.querySelector('.seg button[data-f="parent"]').classList.add('on');
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
  document.getElementById('boxesWrap').style.display='';
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
function doSearch(){
  const q=document.getElementById('q').value.trim().toLowerCase();if(!q)return;
  const hit=Object.keys(DETAIL).find(c=>c.toLowerCase()===q)||Object.keys(DETAIL).find(c=>c.toLowerCase().includes(q));
  if(hit)showCard(hit);
}
</script></body></html>"""

if __name__=="__main__":
    main()