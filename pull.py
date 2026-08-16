"""
pull.py - logs into PIRO, pulls Processing orders, saves orders.json,
appends stage changes to history.json, and writes a line to log.txt each run.
Read-only against PIRO. Run: python3 pull.py
"""
import json, os, urllib.request, sys, datetime
from zoneinfo import ZoneInfo

BASE = "https://sashaprimak.pirofusion.com/PIRO.API/api"
USER = os.environ.get("PIRO_USER")
PW   = os.environ.get("PIRO_PW")
if not USER or not PW:
    sys.exit("Missing PIRO_USER / PIRO_PW environment variables.")

def get_token():
    body = json.dumps({"username": USER, "password": PW}).encode()
    req = urllib.request.Request(f"{BASE}/auth/login", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["token"]

def pull(token):
    req = urllib.request.Request(f"{BASE}/JobOrders/filtered?Status=Processing",
                                 method="GET", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

def update_history(orders):
    """Append stage changes to history.json. Returns (history, number_moved_this_run)."""
    try:
        hist = json.load(open("history.json"))
    except (FileNotFoundError, json.JSONDecodeError):
        hist = {}
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M")
    moved = 0
    for o in orders:
        code = o.get("code")
        stage = o.get("currentService")
        if not code or not stage:
            continue
        entries = hist.get(code, [])
        if not entries:
            hist[code] = [{"stage": stage, "since": now}]
        elif entries[-1]["stage"] != stage:
            entries.append({"stage": stage, "since": now})
            hist[code] = entries
            moved += 1   # existing order that changed stage
    json.dump(hist, open("history.json", "w"))
    return hist, moved

def write_log(n_orders, n_moved, n_tracked):
    stamp = datetime.datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M %p ET")
    line = f"{stamp}  |  pulled {n_orders} orders  |  {n_moved} moved stage  |  tracking {n_tracked}\n"
    with open("log.txt", "a") as f:
        f.write(line)

def main():
    print("Logging in...")
    token = get_token()
    print("Pulling orders...")
    data = pull(token)
    orders = data.get("value", [])
    json.dump(data, open("orders.json", "w"))
    hist, moved = update_history(orders)
    write_log(len(orders), moved, len(hist))
    print(f"Saved {len(orders)} orders; {moved} moved stage; history tracks {len(hist)}.")

if __name__ == "__main__":
    main()