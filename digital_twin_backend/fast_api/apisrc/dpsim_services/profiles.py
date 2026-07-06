from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import text
import json
import math
import os

from .debug import (
    stable_hash,
    debug_round,
    build_ts_summary,
    build_profile_power_audit,
    sample_rows,
)


# Profile-type label of the conventional balancing unit in the TSO profile
# data. Deployment-specific (real datasets may use a plant-specific label);
# override with the TSO_BALANCING_PROFILE_TYPE environment variable.
BALANCING_PROFILE_TYPE = os.getenv("TSO_BALANCING_PROFILE_TYPE", "BALANCING_UNIT")

VALID_PROFILE_TYPES = {
    "LOAD",
    "PV",
    "WP",
    "CU PRODUCTION",
    BALANCING_PROFILE_TYPE,
    "COMPENSATOR",
}


def dpsim_component_prefix(component_id: str) -> str:
    head, sep, _ = component_id.partition("_")
    if not sep:
        raise HTTPException(
            status_code=500,
            detail=f"component_id has no underscore prefix: {component_id!r}",
        )
    return f"{head}_"


def dpsim_profile_type_for_component(component_id: str) -> str:
    return dpsim_component_prefix(component_id).rstrip("_").upper()


def build_dpsim_replace_map(component_ids) -> dict[str, str]:
    replace_map = {}
    for component_id in component_ids:
        prefix = dpsim_component_prefix(component_id)
        replace_map[prefix] = f"{dpsim_profile_type_for_component(component_id)}_{prefix}"
    return replace_map


class PipelineEarlyReturn(Exception):
    """
    Used to preserve the monolith behavior where some validation failures returned
    a normal JSON response instead of raising HTTPException.
    """

    def __init__(self, response: dict):
        self.response = response
        super().__init__(str(response))


@dataclass
class DbProfileResult:
    rows: list
    hash: str
    audit: dict
    sample_first_10: list


@dataclass
class ProfileTransformResult:
    rows: list[dict]
    hash: str
    ts_summary: dict
    audit: dict


@dataclass
class DpsimPayloadResult:
    payload: list[dict]
    hash: str
    debug: dict
    component_coverage: dict
    replace_map: dict[str, str]


def get_assets_dir(base_dir: str) -> str:
    return os.path.join(base_dir, "dpsim_assets")


def get_asset_path(base_dir: str, filename: str) -> str:
    return os.path.join(get_assets_dir(base_dir), filename)


def load_component_mapping(base_dir: str) -> dict:
    mapping_path = get_asset_path(base_dir, "component_to_exact_bus.json")

    if not os.path.exists(mapping_path):
        raise HTTPException(
            status_code=500,
            detail="component_to_exact_bus.json not found on the backend server.",
        )

    with open(mapping_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_crete_2030_zip_path(base_dir: str) -> str:
    zip_path = get_asset_path(base_dir, "Crete_2030.zip")

    if not os.path.exists(zip_path):
        raise HTTPException(
            status_code=500,
            detail="Static file Crete_2030.zip not found on the backend server.",
        )

    return zip_path


# DSO network archives are discovered by naming convention:
#   dpsim_assets/cel{cell}_{name}.zip   (any {name} of your choice)
# XMLs inside: cel{cell}_{name}_TP.xml, cel{cell}_{name}_SSH.xml, cel{cell}_{name}_EQ.xml
# The real Crete distribution-network archives are proprietary and are NOT
# distributed with this repository — supply your own.
def _find_dso_archive(base_dir: str, cell: int):
    """Return the zip base name for the given cell, or None."""
    import glob as _glob

    pattern = get_asset_path(base_dir, f"cel{cell}_*.zip")
    matches = sorted(_glob.glob(pattern))
    if not matches:
        return None
    return os.path.splitext(os.path.basename(matches[0]))[0]


def get_dso_zip_path(base_dir: str, cell: int) -> tuple[str, str]:
    """Return (zip_path, base_name) for the given DSO cell, or raise HTTPException."""
    import zipfile

    name = _find_dso_archive(base_dir, cell)
    if name is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No DPsim network archive found for DSO cell {cell} "
                f"(expected dpsim_assets/cel{cell}_<name>.zip; the real network "
                "archives are proprietary and not distributed — supply your own)."
            ),
        )

    zip_path = get_asset_path(base_dir, f"{name}.zip")

    with zipfile.ZipFile(zip_path) as zf:
        zip_names = zf.namelist()

    # Strip any directory prefix so matching works regardless of how the zip was created.
    # e.g. "some_dir/cel3_example_TP.xml" → "cel3_example_TP.xml"
    zip_basenames = {entry.split("/")[-1] for entry in zip_names}

    required_suffixes = ["_TP.xml", "_SSH.xml", "_EQ.xml"]
    missing = [
        f"{name}{suffix}"
        for suffix in required_suffixes
        if f"{name}{suffix}" not in zip_basenames
    ]

    if missing:
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"DSO asset zip '{name}.zip' is missing required XML files.",
                "missing": missing,
                "zip_contents": sorted(zip_names),
            },
        )

    return zip_path, name


DSO_VALID_PROFILE_TYPES = {"LOAD", "GEN"}


def fetch_dso_profile_rows(
    db,
    start_ts: str,
    end_ts: str,
    date_str: str,
    cell: int,
) -> DbProfileResult:
    table = f"dso_power_profiles_data_cel{cell}"

    query = text(f"""
        SELECT ts, bus, component_id, profile_type, power_type, value
        FROM {table}
        WHERE ts >= :start_ts
          AND ts < :end_ts
        ORDER BY ts, bus, component_id, profile_type, power_type;
    """)

    results = db.execute(
        query,
        {"start_ts": start_ts, "end_ts": end_ts},
    ).mappings().fetchall()

    if not results:
        raise PipelineEarlyReturn({
            "error": f"No DSO profile data found for cell {cell} on date {date_str}",
        })

    db_hash = stable_hash([
        {
            "ts": str(r["ts"]),
            "bus": r["bus"],
            "component_id": r["component_id"],
            "profile_type": r["profile_type"],
            "power_type": r["power_type"],
            "value": float(r["value"]),
        }
        for r in results
    ])

    db_audit = build_profile_power_audit(results)
    db_sample_first_10 = sample_rows(results, limit=10)

    print("[DEBUG][DSO] db_hash=", db_hash)
    print("[DEBUG][DSO] db_audit=", db_audit)

    return DbProfileResult(
        rows=list(results),
        hash=db_hash,
        audit=db_audit,
        sample_first_10=db_sample_first_10,
    )


def transform_dso_profile_rows(
    rows: list,
    payload,
    debug_flags: dict,
) -> ProfileTransformResult:
    """
    Simplified transform for DSO profiles (LOAD / GEN only, no BALANCING balancing).
    component_id is used directly as the DPSim bus — no mapping file needed.
    """
    from collections import defaultdict

    DEBUG_FAIL_ON_NONFINITE = debug_flags.get("DEBUG_FAIL_ON_NONFINITE", True)
    DEBUG_SINGLE_TIMESTEP = debug_flags.get("DEBUG_SINGLE_TIMESTEP", False)

    component_replace_map = {}
    if payload.replace_map:
        component_replace_map = payload.replace_map.get("component_id", {})

    transformed_rows = []
    bad_rows = []
    transform_audit_totals = defaultdict(lambda: {
        "count": 0,
        "raw_total": 0.0,
        "final_total": 0.0,
    })

    for row in rows:
        ts = row["ts"]
        source_component_id = row["component_id"]
        profile_type = row["profile_type"]
        power_type = row["power_type"]
        value = float(row["value"])

        if profile_type not in DSO_VALID_PROFILE_TYPES:
            raise HTTPException(
                status_code=500,
                detail=(
                    f"Unexpected DSO profile_type={profile_type!r} "
                    f"for component_id={source_component_id}"
                ),
            )

        # DSO component_id is already the exact DPSim bus identifier.
        bus = source_component_id
        component_id = component_replace_map.get(source_component_id, source_component_id)

        raw_value = value

        if profile_type == "LOAD":
            value = value * payload.load_scale
        elif profile_type == "GEN" and power_type == "active":
            value = value * payload.gen_scale

        if DEBUG_FAIL_ON_NONFINITE and not math.isfinite(value):
            bad_rows.append({
                "ts": ts,
                "bus": bus,
                "component_id": component_id,
                "profile_type": profile_type,
                "power_type": power_type,
                "value": value,
            })
            continue

        audit_key = f"{profile_type}|{power_type}"
        transform_audit_totals[audit_key]["count"] += 1
        transform_audit_totals[audit_key]["raw_total"] += raw_value
        transform_audit_totals[audit_key]["final_total"] += value

        transformed_rows.append({
            "ts": ts,
            "bus": bus,
            "component_id": component_id,
            "profile_type": profile_type,
            "original_profile_type": profile_type,
            "power_type": power_type,
            "value": value,
        })

    if bad_rows:
        raise PipelineEarlyReturn({
            "error": "Non-finite values detected before DSO profile upload.",
            "bad_rows_count": len(bad_rows),
            "bad_rows_sample": bad_rows[:10],
        })

    if DEBUG_SINGLE_TIMESTEP and transformed_rows:
        first_ts = min(r["ts"] for r in transformed_rows)
        transformed_rows = [r for r in transformed_rows if r["ts"] == first_ts]
        print(f"[DEBUG][DSO] Single-timestep mode. Using only ts={first_ts}")

    transformed_hash = stable_hash(transformed_rows)
    ts_summary = build_ts_summary(transformed_rows)
    transformed_audit = build_profile_power_audit(transformed_rows)

    transform_audit = {
        "scale_parameters": {
            "load_scale": payload.load_scale,
            "gen_scale": payload.gen_scale,
        },
        "rule_totals": debug_round({
            k: dict(v) for k, v in transform_audit_totals.items()
        }),
        "transformed_totals": transformed_audit,
    }

    return ProfileTransformResult(
        rows=transformed_rows,
        hash=transformed_hash,
        ts_summary=ts_summary,
        audit=transform_audit,
    )


def parse_day_window(date_str: str) -> tuple[str, str]:
    try:
        day_obj = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="payload.date must be in YYYY-MM-DD format",
        )

    start_ts = day_obj.strftime("%Y-%m-%dT00:00:00")
    end_ts = (day_obj + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00")

    return start_ts, end_ts


def fetch_profile_rows(db, start_ts: str, end_ts: str, date_str: str) -> DbProfileResult:
    query = text("""
        SELECT ts, bus, component_id, profile_type, power_type, value
        FROM tso_power_profiles_data_new
        WHERE ts >= :start_ts
            AND ts < :end_ts
            AND bus <> 'TOTAL'
            AND component_id NOT IN ('total_cu', 'total_load', 'total_pv', 'total_wp')
        ORDER BY ts, bus, component_id, profile_type, power_type;
    """)

    results = db.execute(
        query,
        {"start_ts": start_ts, "end_ts": end_ts},
    ).mappings().fetchall()

    if not results:
        raise PipelineEarlyReturn({
            "error": f"No TSO profile data found for date {date_str}",
        })

    db_hash = stable_hash([
        {
            "ts": str(r["ts"]),
            "bus": r["bus"],
            "component_id": r["component_id"],
            "profile_type": r["profile_type"],
            "power_type": r["power_type"],
            "value": float(r["value"]),
        }
        for r in results
    ])

    db_audit = build_profile_power_audit(results)
    db_sample_first_10 = sample_rows(results, limit=10)

    print("[DEBUG] db_hash=", db_hash)
    print("[DEBUG] db_audit=", db_audit)
    print("[DEBUG] db_sample_first_10=", db_sample_first_10)

    return DbProfileResult(
        rows=list(results),
        hash=db_hash,
        audit=db_audit,
        sample_first_10=db_sample_first_10,
    )


def transform_profile_rows(
    rows: list,
    payload,
    component_to_exact_bus: dict,
    debug_flags: dict,
) -> ProfileTransformResult:
    DEBUG_KEEP_REACTIVE = debug_flags["DEBUG_KEEP_REACTIVE"]
    DEBUG_DISABLE_BALANCING_CLAMP = debug_flags["DEBUG_DISABLE_BALANCING_CLAMP"]
    DEBUG_SINGLE_TIMESTEP = debug_flags["DEBUG_SINGLE_TIMESTEP"]
    DEBUG_FAIL_ON_NONFINITE = debug_flags["DEBUG_FAIL_ON_NONFINITE"]
    DEBUG_FAIL_ON_BALANCING_LIMIT = debug_flags["DEBUG_FAIL_ON_BALANCING_LIMIT"]

    bus_replace_map = {}
    component_replace_map = {}

    if payload.replace_map:
        bus_replace_map = payload.replace_map.get("bus", {})
        component_replace_map = payload.replace_map.get("component_id", {})

    transformed_rows = []
    balancing_active_rows = []
    totals_by_ts = {}
    bad_rows = []

    transform_audit_rows = []
    transform_audit_totals = defaultdict(lambda: {
        "count": 0,
        "raw_total": 0.0,
        "after_scale_total": 0.0,
        "final_total": 0.0,
        "computed_balance_total": 0.0,
    })

    balancing_balance_audit = []

    for row in rows:
        ts = row["ts"]
        db_bus_alias = row["bus"]
        source_component_id = row["component_id"]
        profile_type = row["profile_type"]
        power_type = row["power_type"]
        value = float(row["value"])

        raw_value = value
        applied_scale = 1.0
        scale_rule = "none"
        reactive_rule = "none"
        final_rule_notes = []

        if profile_type not in VALID_PROFILE_TYPES:
            raise HTTPException(
                status_code=500,
                detail=(
                    f"Invalid DB profile_type={profile_type!r} "
                    f"for component_id={source_component_id}"
                ),
            )

        exact_bus = component_to_exact_bus.get(source_component_id)

        if exact_bus is None:
            raise HTTPException(
                status_code=500,
                detail=(
                    f"No exact bus mapping found for component_id={source_component_id} "
                    f"(db bus alias={db_bus_alias})"
                ),
            )

        bus = bus_replace_map.get(exact_bus, exact_bus)
        component_id = component_replace_map.get(
            source_component_id,
            source_component_id,
        )

        upload_profile_type = profile_type
        original_profile_type = profile_type

        # ---------------------------------------------------------------------
        # Scaling logic
        # ---------------------------------------------------------------------
        if profile_type == "LOAD":
            applied_scale = payload.load_scale
            scale_rule = "LOAD scaled for both active and reactive"
            value = value * payload.load_scale

        elif profile_type == "PV" and power_type == "active":
            applied_scale = payload.pv_scale
            scale_rule = "PV active scaled"
            value = value * payload.pv_scale

        elif profile_type == "WP" and power_type == "active":
            applied_scale = payload.wp_scale
            scale_rule = "WP active scaled"
            value = value * payload.wp_scale

        after_scale_value = value
        original_value = value

        # ---------------------------------------------------------------------
        # Reactive power rules
        # ---------------------------------------------------------------------
        if power_type == "reactive":
            if DEBUG_KEEP_REACTIVE:
                value = original_value
                reactive_rule = "kept reactive value after scaling"
            else:
                if profile_type in {"PV", "WP", "CU PRODUCTION", BALANCING_PROFILE_TYPE}:
                    value = 0.0
                    reactive_rule = "reactive forced to zero"
                else:
                    value = original_value
                    reactive_rule = "reactive kept"

        # ---------------------------------------------------------------------
        # Compensators have no active power input
        # ---------------------------------------------------------------------
        if profile_type == "COMPENSATOR" and power_type == "active":
            value = 0.0
            final_rule_notes.append("COMPENSATOR active forced to zero")

        final_value = value

        audit_row = {
            "ts": str(ts),
            "bus_before": db_bus_alias,
            "bus_after": bus,
            "component_id_before": source_component_id,
            "component_id_after": component_id,
            "profile_type": profile_type,
            "power_type": power_type,
            "raw_value": raw_value,
            "applied_scale": applied_scale,
            "after_scale_value": after_scale_value,
            "final_value": final_value,
            "scale_rule": scale_rule,
            "reactive_rule": reactive_rule,
            "final_rule_notes": final_rule_notes,
        }

        # ---------------------------------------------------------------------
        # Non-finite input validation
        # ---------------------------------------------------------------------
        if DEBUG_FAIL_ON_NONFINITE and not math.isfinite(value):
            bad_rows.append({
                "ts": ts,
                "bus": bus,
                "component_id": component_id,
                "profile_type": profile_type,
                "power_type": power_type,
                "value": value,
            })
            continue

        # ---------------------------------------------------------------------
        # BALANCING active power is calculated later as balancing term
        # ---------------------------------------------------------------------
        if profile_type == BALANCING_PROFILE_TYPE and power_type == "active":
            audit_row["deferred_for_balancing_balancing"] = True
            transform_audit_rows.append(audit_row)

            balancing_active_rows.append({
                "ts": ts,
                "bus": bus,
                "component_id": component_id,
                "profile_type": profile_type,
                "power_type": power_type,
                "db_bus_alias": db_bus_alias,
            })
            continue

        audit_key = f"{profile_type}|{power_type}"
        transform_audit_totals[audit_key]["count"] += 1
        transform_audit_totals[audit_key]["raw_total"] += raw_value
        transform_audit_totals[audit_key]["after_scale_total"] += after_scale_value
        transform_audit_totals[audit_key]["final_total"] += final_value

        transform_audit_rows.append(audit_row)

        transformed_rows.append({
            "ts": ts,
            "bus": bus,
            "component_id": component_id,
            "profile_type": upload_profile_type,
            "original_profile_type": original_profile_type,
            "power_type": power_type,
            "value": value,
            "db_bus_alias": db_bus_alias,
        })

        # ---------------------------------------------------------------------
        # Totals used for BALANCING balancing
        # ---------------------------------------------------------------------
        if power_type == "active":
            if ts not in totals_by_ts:
                totals_by_ts[ts] = {
                    "load": 0.0,
                    "pv": 0.0,
                    "wp": 0.0,
                    "cu": 0.0,
                }

            if profile_type == "LOAD":
                totals_by_ts[ts]["load"] += value
            elif profile_type == "PV":
                totals_by_ts[ts]["pv"] += value
            elif profile_type == "WP":
                totals_by_ts[ts]["wp"] += value
            elif profile_type == "CU PRODUCTION":
                totals_by_ts[ts]["cu"] += value

    if bad_rows:
        raise PipelineEarlyReturn({
            "error": "Non-finite values detected before profile upload.",
            "bad_rows_count": len(bad_rows),
            "bad_rows_sample": bad_rows[:10],
        })

    # -------------------------------------------------------------------------
    # Calculate BALANCING active balancing rows
    # -------------------------------------------------------------------------
    for row in balancing_active_rows:
        ts = row["ts"]

        totals = totals_by_ts.get(ts, {
            "load": 0.0,
            "pv": 0.0,
            "wp": 0.0,
            "cu": 0.0,
        })

        balancing_unclamped = totals["load"] - (
            totals["pv"] + totals["wp"] + totals["cu"]
        )

        balancing_p = balancing_unclamped

        if not DEBUG_DISABLE_BALANCING_CLAMP:
            balancing_p = max(-500.0, min(500.0, balancing_p))
        else:
            print(
                f"[DEBUG] BALANCING unclamped at ts={ts}: "
                f"load={totals['load']}, "
                f"pv={totals['pv']}, "
                f"wp={totals['wp']}, "
                f"cu={totals['cu']}, "
                f"balancing={balancing_p}"
            )

        if DEBUG_FAIL_ON_BALANCING_LIMIT and abs(balancing_p) > 500.0:
            raise PipelineEarlyReturn({
                "error": "BALANCING balancing requirement exceeds clamp limit.",
                "ts": str(ts),
                "balancing_p": balancing_p,
                "totals": totals,
            })

        if DEBUG_FAIL_ON_NONFINITE and not math.isfinite(balancing_p):
            raise PipelineEarlyReturn({
                "error": "Non-finite BALANCING value detected.",
                "ts": str(ts),
                "balancing_p": balancing_p,
                "totals": totals,
            })

        balancing_balance_audit.append({
            "ts": str(ts),
            "load": totals["load"],
            "pv": totals["pv"],
            "wp": totals["wp"],
            "cu": totals["cu"],
            "balancing_unclamped": balancing_unclamped,
            "balancing_final": balancing_p,
            "was_clamped": balancing_unclamped != balancing_p,
            "formula": "BALANCING = LOAD - (PV + WP + CU)",
            "clamp_enabled": not DEBUG_DISABLE_BALANCING_CLAMP,
        })

        audit_key = f"{BALANCING_PROFILE_TYPE}|active"
        transform_audit_totals[audit_key]["count"] += 1
        transform_audit_totals[audit_key]["computed_balance_total"] += balancing_p
        transform_audit_totals[audit_key]["final_total"] += balancing_p

        transformed_rows.append({
            "ts": row["ts"],
            "bus": row["bus"],
            "component_id": row["component_id"],
            "profile_type": BALANCING_PROFILE_TYPE,
            "original_profile_type": BALANCING_PROFILE_TYPE,
            "power_type": row["power_type"],
            "value": balancing_p,
            "db_bus_alias": row.get("db_bus_alias"),
        })

    # -------------------------------------------------------------------------
    # Optional first-timestep-only debugging
    # -------------------------------------------------------------------------
    if DEBUG_SINGLE_TIMESTEP and transformed_rows:
        first_ts = min(r["ts"] for r in transformed_rows)
        transformed_rows = [
            r for r in transformed_rows
            if r["ts"] == first_ts
        ]
        print(f"[DEBUG] Single-timestep mode enabled. Using only ts={first_ts}")

    # -------------------------------------------------------------------------
    # Validate transformed profile_type values before payload build
    # -------------------------------------------------------------------------
    bad_profile_types = sorted({
        r["profile_type"]
        for r in transformed_rows
        if r["profile_type"] not in VALID_PROFILE_TYPES
    })

    if bad_profile_types:
        raise PipelineEarlyReturn({
            "error": "Invalid profile_type values before DPSim upload.",
            "bad_profile_types": bad_profile_types[:50],
            "hint": (
                "profile_type must stay semantic: "
                "LOAD/PV/WP/CU PRODUCTION/<balancing unit>/COMPENSATOR. "
                "Component IDs belong only in component_id."
            ),
        })

    transformed_hash = stable_hash(transformed_rows)
    print("[DEBUG] transformed_hash=", transformed_hash)

    ts_summary = build_ts_summary(transformed_rows)
    transformed_audit = build_profile_power_audit(transformed_rows)

    transform_audit = {
        "scale_parameters": {
            "load_scale": payload.load_scale,
            "pv_scale": payload.pv_scale,
            "wp_scale": payload.wp_scale,
        },
        "rule_totals": debug_round({
            k: dict(v)
            for k, v in transform_audit_totals.items()
        }),
        "sample_rows_first_20": debug_round(transform_audit_rows[:20]),
        "balancing_balance_first_24": debug_round(balancing_balance_audit[:24]),
        "transformed_totals": transformed_audit,
    }

    print("[DEBUG] transformed_audit=", transform_audit)

    return ProfileTransformResult(
        rows=transformed_rows,
        hash=transformed_hash,
        ts_summary=ts_summary,
        audit=transform_audit,
    )


def build_dpsim_payload(
    transformed_rows: list[dict],
    expected_components: set[str],
    timestamp_mode: str = "relative_seconds",
) -> DpsimPayloadResult:
    """
    Preserves current monolith behavior by default:

        timestamp_mode="relative_seconds" -> 0, 3600, 7200, ...

    For later DPSim testing only, you can call with:

        timestamp_mode="index" -> 0, 1, 2, ..., 23
    """

    dpsim_payload = []

    if not transformed_rows:
        raise PipelineEarlyReturn({
            "error": "No transformed rows available before DPSim payload build.",
        })

    if timestamp_mode == "index":
        ordered_timestamps = sorted({r["ts"] for r in transformed_rows})
        ts_to_value = {
            ts: idx
            for idx, ts in enumerate(ordered_timestamps)
        }

        for row in transformed_rows:
            dpsim_payload.append({
                "ts": ts_to_value[row["ts"]],
                "value": row["value"],
                "profile_type": dpsim_profile_type_for_component(row["component_id"]),
                "component_id": row["component_id"],
                "power_type": row["power_type"],
               # "bus": row["bus"],
            })

    elif timestamp_mode == "relative_seconds":
        ATHENS_TZ = ZoneInfo("Europe/Athens")

        def to_utc(dt_obj):
            if dt_obj.tzinfo is None:
                dt_obj = dt_obj.replace(tzinfo=ATHENS_TZ)
            return dt_obj.astimezone(timezone.utc)

        first_dt_utc = min(to_utc(r["ts"]) for r in transformed_rows)

        for row in transformed_rows:
            dt_obj_utc = to_utc(row["ts"])

            dpsim_payload.append({
                "ts": int((dt_obj_utc - first_dt_utc).total_seconds()),
                "value": row["value"],
                "profile_type": dpsim_profile_type_for_component(row["component_id"]),
                "component_id": row["component_id"],
                "power_type": row["power_type"],
                "bus": row["bus"],
            })

    else:
        raise HTTPException(
            status_code=500,
            detail=f"Unsupported DPSim timestamp_mode={timestamp_mode!r}",
        )

    dpsim_payload_hash = stable_hash(dpsim_payload)
    print("[DEBUG] dpsim_payload_hash=", dpsim_payload_hash)

    payload_ts_values = sorted({r["ts"] for r in dpsim_payload})

    print("[DEBUG] dpsim_payload_first_relative_ts=", payload_ts_values[0])
    print("[DEBUG] dpsim_payload_last_relative_ts=", payload_ts_values[-1])
    print("[DEBUG] dpsim_payload_distinct_ts_count=", len(payload_ts_values))
    print("[DEBUG] dpsim_payload_ts_sample=", payload_ts_values[:10])

    uploaded_components = {
        r["component_id"]
        for r in dpsim_payload
    }

    missing_from_upload = sorted(expected_components - uploaded_components)
    extra_in_upload = sorted(uploaded_components - expected_components)

    component_coverage = {
        "expected_sim_components_count": len(expected_components),
        "uploaded_components_count": len(uploaded_components),
        "missing_from_upload_count": len(missing_from_upload),
        "missing_from_upload_sample": missing_from_upload[:50],
        "extra_in_upload_count": len(extra_in_upload),
        "extra_in_upload_sample": extra_in_upload[:50],
    }

    print("[DEBUG] expected_sim_components_count=", component_coverage["expected_sim_components_count"])
    print("[DEBUG] uploaded_components_count=", component_coverage["uploaded_components_count"])
    print("[DEBUG] missing_from_upload_count=", component_coverage["missing_from_upload_count"])
    print("[DEBUG] missing_from_upload_sample=", component_coverage["missing_from_upload_sample"])
    print("[DEBUG] extra_in_upload_count=", component_coverage["extra_in_upload_count"])
    print("[DEBUG] extra_in_upload_sample=", component_coverage["extra_in_upload_sample"])

    dpsim_payload_audit = build_profile_power_audit(dpsim_payload)

    replace_map = build_dpsim_replace_map(uploaded_components)

    dpsim_payload_debug = {
        "hash": dpsim_payload_hash,
        "timestamp_mode": timestamp_mode,
        "row_count": len(dpsim_payload),
        "distinct_ts_count": len(payload_ts_values),
        "first_ts": payload_ts_values[0] if payload_ts_values else None,
        "last_ts": payload_ts_values[-1] if payload_ts_values else None,
        "ts_sample": payload_ts_values[:10],
        "profile_power_totals": dpsim_payload_audit,
        "sample_first_20": debug_round(dpsim_payload[:20]),
        "component_coverage": component_coverage,
        "replace_map": replace_map,
    }

    print("[DEBUG] dpsim_payload_debug=", dpsim_payload_debug)

    return DpsimPayloadResult(
        payload=dpsim_payload,
        hash=dpsim_payload_hash,
        debug=dpsim_payload_debug,
        component_coverage=component_coverage,
        replace_map=replace_map,
    )
