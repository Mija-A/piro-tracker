"""Stage-change journal.

history.json format:
    {"orders": {"<JO code>": {"journey": [{"stage": ..., "since": "YYYY-MM-DD HH:MM"}, ...],
                              "last_seen": "YYYY-MM-DD HH:MM"}}}

Timestamps are UTC, minute precision - the same format the journal has always
used, so existing `since` values stay valid. Loading transparently migrates the
old flat format ({"<code>": [entries]}).
"""
import datetime
import json

TS_FMT = "%Y-%m-%d %H:%M"
PRUNE_AFTER_DAYS = 60


def now_stamp():
    return datetime.datetime.now(datetime.timezone.utc).strftime(TS_FMT)


def _migrate(raw):
    """Old flat {code: [entries]} -> new {"orders": {code: {...}}}.

    Old entries have no last_seen; use their latest stage timestamp so pruning
    has something reasonable to work with.
    """
    orders = {}
    for code, entries in raw.items():
        if not isinstance(entries, list):
            continue
        last = entries[-1]["since"] if entries else now_stamp()
        orders[code] = {"journey": entries, "last_seen": last}
    return {"orders": orders}


def load(path="history.json"):
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"orders": {}}
    if isinstance(raw, dict) and isinstance(raw.get("orders"), dict):
        return raw
    if isinstance(raw, dict):
        return _migrate(raw)
    return {"orders": {}}


def save(hist, path="history.json"):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(hist, f, indent=1, sort_keys=True)


def update(hist, orders, now=None):
    """Record stage changes and last-seen stamps. Returns number of moves."""
    now = now or now_stamp()
    moved = 0
    tracked = hist["orders"]
    for o in orders:
        code, stage = o.get("code"), o.get("currentService")
        if not code or not stage:
            continue
        rec = tracked.setdefault(code, {"journey": [], "last_seen": now})
        rec["last_seen"] = now
        journey = rec["journey"]
        if not journey:
            journey.append({"stage": stage, "since": now})
        elif journey[-1]["stage"] != stage:
            journey.append({"stage": stage, "since": now})
            moved += 1
    return moved


def prune(hist, now=None, keep_days=PRUNE_AFTER_DAYS):
    """Drop orders not seen for keep_days; returns {code: record} of pruned."""
    now_dt = datetime.datetime.strptime(now or now_stamp(), TS_FMT)
    cutoff = now_dt - datetime.timedelta(days=keep_days)
    pruned = {}
    for code, rec in list(hist["orders"].items()):
        try:
            seen = datetime.datetime.strptime(rec.get("last_seen", ""), TS_FMT)
        except ValueError:
            continue  # unparseable stamp: keep rather than silently discard
        if seen < cutoff:
            pruned[code] = hist["orders"].pop(code)
    return pruned


def archive(pruned, path="history_archive.json"):
    """Merge pruned records into the archive file (kept on the data branch)."""
    if not pruned:
        return
    try:
        with open(path, encoding="utf-8") as f:
            arch = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        arch = {}
    arch.update(pruned)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(arch, f, indent=1, sort_keys=True)
