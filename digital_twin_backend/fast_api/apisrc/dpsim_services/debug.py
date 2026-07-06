import hashlib
import json
from collections import defaultdict


def dump_json(filepath, obj):
    with open(filepath, "w") as f:
        json.dump(obj, f, indent=2, default=str)


def stable_hash(obj):
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]


def debug_round(obj, decimals=6):
    if isinstance(obj, float):
        return round(obj, decimals)
    if isinstance(obj, int):
        return obj
    if isinstance(obj, list):
        return [debug_round(x, decimals) for x in obj]
    if isinstance(obj, dict):
        return {str(k): debug_round(v, decimals) for k, v in obj.items()}
    return obj


def row_get(row, key, default=None):
    try:
        return row[key]
    except Exception:
        return default


def build_ts_summary(rows):
    summary = defaultdict(lambda: {
        "active": defaultdict(float),
        "reactive": defaultdict(float),
    })

    for r in rows:
        ptype = r["power_type"]
        profile = r["profile_type"]
        ts = r["ts"]
        val = float(r["value"])
        summary[ts][ptype][profile] += val

    return summary


def build_profile_power_audit(rows):
    totals = defaultdict(lambda: defaultdict(float))
    counts = defaultdict(lambda: defaultdict(int))
    timestamps = set()
    components = set()

    for r in rows:
        ts = row_get(r, "ts")
        component_id = row_get(r, "component_id")
        profile_type = row_get(r, "profile_type")
        power_type = row_get(r, "power_type")
        value = row_get(r, "value")

        timestamps.add(str(ts))
        components.add(str(component_id))

        totals[str(profile_type)][str(power_type)] += float(value)
        counts[str(profile_type)][str(power_type)] += 1

    return debug_round({
        "row_count": len(rows),
        "distinct_ts_count": len(timestamps),
        "first_ts": min(timestamps) if timestamps else None,
        "last_ts": max(timestamps) if timestamps else None,
        "component_count": len(components),
        "totals_by_profile_power": {
            profile: dict(power_map)
            for profile, power_map in totals.items()
        },
        "counts_by_profile_power": {
            profile: dict(power_map)
            for profile, power_map in counts.items()
        },
    })


def sample_rows(rows, limit=10):
    sampled = []

    for r in list(rows)[:limit]:
        sampled.append({
            "ts": str(row_get(r, "ts")),
            "bus": row_get(r, "bus"),
            "component_id": row_get(r, "component_id"),
            "profile_type": row_get(r, "profile_type"),
            "power_type": row_get(r, "power_type"),
            "value": float(row_get(r, "value")),
        })

    return debug_round(sampled)
