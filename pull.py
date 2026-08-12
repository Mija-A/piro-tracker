import json, os, urllib.request, sys

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
                                 method="GET",
                                 headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

def main():
    print("Logging in...")
    token = get_token()
    print("Pulling orders...")
    data = pull(token)
    json.dump(data, open("orders.json", "w"))
    print(f"Saved {len(data.get('value', []))} orders to orders.json")

if __name__ == "__main__":
    main()
