"""main.py - pull orders from PIRO, update the stage journal, emit site/data.json.

Read-only against PIRO. Requires PIRO_USER / PIRO_PW environment variables.
Run: python3 main.py
"""
import datetime
import json
import os
import sys
from zoneinfo import ZoneInfo

from tracker import history, payload, piro

STATUSES = ["Processing", "New", "On hold"]
DATA_OUT = os.path.join("site", "data.json")


def write_log(n_orders, n_moved, n_tracked, path="log.txt"):
    stamp = datetime.datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M %p ET")
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{stamp}  |  pulled {n_orders} orders  |  {n_moved} moved stage  |  tracking {n_tracked}\n")


def main():
    user, pw = os.environ.get("PIRO_USER"), os.environ.get("PIRO_PW")
    if not user or not pw:
        sys.exit("Missing PIRO_USER / PIRO_PW environment variables.")

    print(f"Pulling orders ({', '.join(STATUSES)})...")
    orders = piro.fetch_orders(user, pw, STATUSES)

    hist = history.load()
    moved = history.update(hist, orders)
    pruned = history.prune(hist)
    history.archive(pruned)
    history.save(hist)

    with open(os.path.join("site", "config.json"), encoding="utf-8") as cf:
        _cfg = json.load(cf)
    data = payload.build(orders, hist, suborder_stages=_cfg.get("suborderStages", []))
    os.makedirs(os.path.dirname(DATA_OUT), exist_ok=True)
    with open(DATA_OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, sort_keys=True, separators=(",", ":"))

    write_log(len(orders), moved, len(hist["orders"]))
    print(f"Saved {len(data['orders'])} parent orders to {DATA_OUT}; "
          f"{moved} moved stage; tracking {len(hist['orders'])}; pruned {len(pruned)}.")


if __name__ == "__main__":
    main()
