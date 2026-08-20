"""PIRO API client. Read-only: login + fetch job orders by status."""
import json
import urllib.parse
import urllib.request

BASE = "https://sashaprimak.pirofusion.com/PIRO.API/api"


class PiroError(Exception):
    """Raised when PIRO cannot be reached or returns nothing usable."""


def login(user, pw, base=BASE):
    body = json.dumps({"username": user, "password": pw}).encode()
    req = urllib.request.Request(f"{base}/auth/login", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())["token"]
    except Exception as e:
        raise PiroError(f"PIRO login failed: {e}") from e


def fetch_status(token, status, base=BASE):
    url = f"{base}/JobOrders/filtered?Status=" + urllib.parse.quote(status)
    req = urllib.request.Request(url, method="GET",
                                 headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read()).get("value", [])


def fetch_orders(user, pw, statuses, base=BASE):
    """Fetch all statuses, dedupe by order code.

    A single status failing is tolerated (logged); every status failing, or an
    empty result set, raises so the CI run fails loudly instead of publishing a
    silently empty dashboard. This shop always has active orders, so an empty
    pull can only mean the API or credentials broke.
    """
    token = login(user, pw, base)
    seen = {}
    failures = []
    for st in statuses:
        try:
            for o in fetch_status(token, st, base):
                code = o.get("code")
                if code:
                    seen[code] = o
        except Exception as e:
            failures.append(f"{st}: {e}")
            print(f"  (status '{st}' failed: {e})")
    if len(failures) == len(statuses):
        raise PiroError("every status pull failed: " + "; ".join(failures))
    if not seen:
        raise PiroError("PIRO returned zero orders across all statuses - refusing to publish")
    return list(seen.values())
