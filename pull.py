"""
pull.py - logs into PIRO, pulls Processing orders, saves orders.json,
and appends any stage changes to history.json (the accumulating journey log).
Read-only against PIRO. Run: python3 pull.py
"""
import json, os, urllib.request, sys, datetime

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
    """Append stage changes to history.json. Only logs when an order's stage
    differs from the last recorded stage for that order."""
    try:
        hist = json.load(open("history.json"))
    except (FileNotFoundError, json.JSONDecodeError):
        hist = {}
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M")
    for o in orders:
        code = o.get("code")
        stage = o.get("currentService")
        if not code or not stage:
            continue
        entries = hist.get(code, [])
        if not entries or entries[-1]["stage"] != stage:
            entries.append({"stage": stage, "since": now})
            hist[code] = entries
    json.dump(hist, open("history.json", "w"))
    return hist

def main():
    print("Logging in...")
    token = get_token()
    print("Pulling orders...")
    data = pull(token)
    orders = data.get("value", [])
    json.dump(data, open("orders.json", "w"))
    hist = update_history(orders)
    print(f"Saved {len(orders)} orders; history tracks {len(hist)} orders.")

if __name__ == "__main__":
    main()