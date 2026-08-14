"""
pull.py - logs into PIRO, pulls all Processing job orders, saves to orders.json.
Read-only: one login POST + one GET. Nothing in PIRO is changed.
Run:  python3 pull.py
"""
import json, urllib.request, sys

BASE = "https://sashaprimak.pirofusion.com/PIRO.API/api"
USER = "apiuser"
PW   = "GoPiro2025"

def get_token():
    body = json.dumps({"username": USER, "password": PW}).encode()
    req = urllib.request.Request(f"{BASE}/auth/login", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["token"]

def pull(token):
    req = urllib.request.Request(f"{BASE}/JobOrders/filtered?Status=Processing",
                                 method="GET",
                                 headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

def main():
    print("Logging in...")
    token = get_token()
    print("Pulling orders...")
    data = pull(token)
    orders = data.get("value", [])
    json.dump(data, open("orders.json", "w"))
    print(f"Saved {len(orders)} orders to orders.json")

if __name__ == "__main__":
    main()