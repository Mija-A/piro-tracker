"""
pull.py - logs into PIRO, pulls orders across statuses (Processing, New, On hold),
saves orders.json, appends stage changes to history.json, writes a line to log.txt.
Read-only against PIRO. Run: python3 pull.py
"""
import json, os, urllib.request, urllib.parse, sys, datetime
from zoneinfo import ZoneInfo

BASE = "https://sashaprimak.pirofusion.com/PIRO.API/api"
USER = os.environ.get("PIRO_USER")
PW   = os.environ.get("PIRO_PW")
STATUSES = ["Processing", "New", "On hold"]   # all statuses to include
if not USER or not PW:
    sys.exit("Missing PIRO_USER / PIRO_PW environment variables.")

def get_token():
    body = json.dumps({"username": USER, "password": PW}).encode()
    req = urllib.request.Request(f"{BASE}/auth/login", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["token"]

def pull_status(token, status):
    url = f"{BASE}/JobOrders/filtered?Status=" + urllib.parse.quote(status)
    req = urllib.request.Request(url, method="GET",
                                 headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read()).get("value", [])

def pull_all(token):
    seen = {}
    for st in STATUSES:
        try:
            for o in pull_status(token, st):
                code = o.get("code")
                if code:
                    seen[code] = o   # dedupe by code
        except Exception as e:
            print(f"  (status '{st}' failed: {e})")
    return list(seen.values())

def update_history(orders):
    try:
        hist = json.load(open("history.json"))
    except (FileNotFoundError, json.JSONDecodeError):
        hist = {}
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M")
    moved = 0
    for o in orders:
        code = o.get("code"); stage = o.get("currentService")
        if not code or not stage: continue
        entries = hist.get(code, [])
        if not entries:
            hist[code] = [{"stage": stage, "since": now}]
        elif entries[-1]["stage"] != stage:
            entries.append({"stage": stage, "since": now}); hist[code] = entries; moved += 1
    json.dump(hist, open("history.json", "w"))
    return hist, moved

def write_log(n_orders, n_moved, n_tracked):
    stamp = datetime.datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M %p ET")
    with open("log.txt", "a") as f:
        f.write(f"{stamp}  |  pulled {n_orders} orders  |  {n_moved} moved stage  |  tracking {n_tracked}\n")

def main():
    print("Logging in...")
    token = get_token()
    print(f"Pulling orders ({', '.join(STATUSES)})...")
    orders = pull_all(token)
    json.dump({"value": orders}, open("orders.json", "w"))
    hist, moved = update_history(orders)
    write_log(len(orders), moved, len(hist))
    print(f"Saved {len(orders)} orders; {moved} moved stage; history tracks {len(hist)}.")

if __name__ == "__main__":
    main()