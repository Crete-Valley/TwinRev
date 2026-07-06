from __future__ import annotations

import os
import uuid
import httpx

from .client import (
    upload_xml,
    upload_profile,
    start_simulation,
    poll_result,
)
from .debug import (
    dump_json,
    stable_hash,
)
from .postprocess import _load_topology, postprocess_dpsim_results
from .profiles import (
    BALANCING_PROFILE_TYPE,
    PipelineEarlyReturn,
    get_crete_2030_zip_path,
    load_component_mapping,
    parse_day_window,
    fetch_profile_rows,
    transform_profile_rows,
    build_dpsim_payload,
)


DEBUG_FLAGS = {
    "DEBUG_SINGLE_TIMESTEP": False,
    "DEBUG_KEEP_REACTIVE": True,
    "DEBUG_DISABLE_BALANCING_CLAMP": False,
    "DEBUG_PRINT_SUMMARY": True,
    "DEBUG_DUMP_PAYLOAD": True,
    "DEBUG_ATTACH_SUMMARY_TO_RESPONSE": True,
    "DEBUG_FAIL_ON_NONFINITE": True,
    "DEBUG_FAIL_ON_BALANCING_LIMIT": False,
}


def payload_to_dict(payload) -> dict:
    return (
        payload.model_dump()
        if hasattr(payload, "model_dump")
        else payload.dict()
    )


def print_profile_summary(ts_summary: dict):
    print("----- PROFILE SUMMARY (first 5 timestamps) -----")

    for ts in sorted(ts_summary.keys())[:5]:
        active = ts_summary[ts]["active"]
        reactive = ts_summary[ts]["reactive"]

        print(
            f"TS={ts} | "
            f"P: LOAD={active.get('LOAD', 0.0)}, "
            f"PV={active.get('PV', 0.0)}, "
            f"WP={active.get('WP', 0.0)}, "
            f"CU={active.get('CU PRODUCTION', 0.0)}, "
            f"BALANCING={active.get(BALANCING_PROFILE_TYPE, 0.0)} | "
            f"Q: LOAD={reactive.get('LOAD', 0.0)}, "
            f"PV={reactive.get('PV', 0.0)}, "
            f"WP={reactive.get('WP', 0.0)}, "
            f"CU={reactive.get('CU PRODUCTION', 0.0)}, "
            f"BALANCING={reactive.get(BALANCING_PROFILE_TYPE, 0.0)}, "
            f"COMPENSATOR={reactive.get('COMPENSATOR', 0.0)}"
        )


def make_ts_summary_first_5(ts_summary: dict) -> list[dict]:
    debug_summary_serializable = []

    for ts in sorted(ts_summary.keys())[:5]:
        debug_summary_serializable.append({
            "ts": str(ts),
            "active": dict(ts_summary[ts]["active"]),
            "reactive": dict(ts_summary[ts]["reactive"]),
        })

    return debug_summary_serializable


def log_raw_result_debug(result_json: dict, raw_result_payload):
    if not isinstance(result_json, dict):
        return

    print("[DEBUG] outer_result_top_keys=", list(result_json.keys())[:20])

    if not isinstance(raw_result_payload, dict):
        return

    print(
        "[DEBUG] inner_result_top_keys=",
        list(raw_result_payload.keys())[:50],
    )

    list_keys = [
        k for k, v in raw_result_payload.items()
        if isinstance(v, list)
    ]

    print("[DEBUG] inner_result_list_keys_count=", len(list_keys))
    print(
        "[DEBUG] inner_result_list_keys_sample=",
        list_keys[:50],
    )

    # Probe a few expected series derived from the (deployment-supplied)
    # topology file instead of hardcoding grid-specific result keys.
    keys_to_check = []
    topology = _load_topology()
    for spec in list(topology["buses"].values())[:2]:
        keys_to_check += [spec["re"], spec["im"]]
    for spec in topology["lines"][:1]:
        for prefix in spec["prefixes"][:1]:
            keys_to_check += [f"{prefix}_P_0", f"{prefix}_Q_0"]

    for key in keys_to_check:
        if key in raw_result_payload and isinstance(raw_result_payload[key], list):
            vals = raw_result_payload[key]
            rounded = [round(float(v), 6) for v in vals[:10]]
            unique_count = len(set(round(float(v), 6) for v in vals))

            print(
                f"[DEBUG] {key} "
                f"len={len(vals)} "
                f"unique_count={unique_count} "
                f"first_10={rounded}"
            )

    for key in list_keys[:20]:
        vals = raw_result_payload[key]

        try:
            rounded = [round(float(v), 6) for v in vals[:10]]
            unique_count = len(set(round(float(v), 6) for v in vals))

            print(
                f"[DEBUG] {key} "
                f"len={len(vals)} "
                f"unique_count={unique_count} "
                f"first_10={rounded}"
            )

        except Exception:
            print(
                f"[DEBUG] {key} "
                f"len={len(vals)} "
                f"non_numeric_sample={vals[:10]}"
            )


async def run_dpsim_pipeline(payload, db, dpsim_url: str, base_dir: str) -> dict:
    print("This is a new experiment run!")

    run_id = uuid.uuid4().hex[:8]
    payload_debug = payload_to_dict(payload)

    print("[DEBUG] payload=", payload_debug)

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            # -----------------------------------------------------------------
            # STEP 1: Load local static ZIP file and POST to DPSim
            # -----------------------------------------------------------------
            zip_path = get_crete_2030_zip_path(base_dir)
            component_to_exact_bus = load_component_mapping(base_dir)

            xml_keyword = await upload_xml(
                client=client,
                dpsim_url=dpsim_url,
                zip_path=zip_path,
            )

            start_ts, end_ts = parse_day_window(payload.date)

            print(f"[DEBUG] payload.date={payload.date}")
            print(f"[DEBUG] start_ts={start_ts} end_ts={end_ts}")
            print("Step 1 Completed!")

            # -----------------------------------------------------------------
            # STEP 2: Fetch DB profiles, transform, upload to DPSim
            # -----------------------------------------------------------------
            db_profile = fetch_profile_rows(
                db=db,
                start_ts=start_ts,
                end_ts=end_ts,
                date_str=payload.date,
            )

            transformed = transform_profile_rows(
                rows=db_profile.rows,
                payload=payload,
                component_to_exact_bus=component_to_exact_bus,
                debug_flags=DEBUG_FLAGS,
            )

            if DEBUG_FLAGS["DEBUG_PRINT_SUMMARY"]:
                print_profile_summary(transformed.ts_summary)

            print("[DEBUG] transformed_first_10=", transformed.rows[:10])

            # -----------------------------------------------------------------
            # Build DPSim payload
            # -----------------------------------------------------------------
            expected_sim_components = set(component_to_exact_bus.keys())

            dpsim_profile = build_dpsim_payload(
                transformed_rows=transformed.rows,
                expected_components=expected_sim_components,
                timestamp_mode="relative_seconds",
            )

            DEBUG_FORCE_PROFILE_CANARY = False

            if DEBUG_FORCE_PROFILE_CANARY:
                for r in dpsim_profile.payload:
                    if (
                        r["ts"] == 0
                        and r["profile_type"] == "LOAD"
                        and r["power_type"] == "active"
                    ):
                        print("[DEBUG] CANARY before=", r)
                        r["value"] = float(r["value"]) * 100.0
                        print("[DEBUG] CANARY after=", r)
                        break

                dpsim_profile.hash = stable_hash(dpsim_profile.payload)
                dpsim_profile.debug["hash_after_canary"] = dpsim_profile.hash
                print("[DEBUG] dpsim_payload_hash_after_canary=", dpsim_profile.hash)

            # -----------------------------------------------------------------
            # Payload dumps
            # -----------------------------------------------------------------
            transformed_rows_dump = f"/tmp/dpsim_transformed_rows_{run_id}.json"
            dpsim_payload_dump = f"/tmp/dpsim_payload_{run_id}.json"

            distinct_payload_ts = sorted({r["ts"] for r in transformed.rows})

            print(f"[DEBUG] transformed_rows_count={len(transformed.rows)}")
            print(f"[DEBUG] transformed_distinct_ts={len(distinct_payload_ts)}")
            print(
                f"[DEBUG] transformed_first_ts="
                f"{distinct_payload_ts[0] if distinct_payload_ts else None}"
            )
            print(
                f"[DEBUG] transformed_last_ts="
                f"{distinct_payload_ts[-1] if distinct_payload_ts else None}"
            )
            print("[DEBUG] transformed_first_10=", transformed.rows[:10])

            print(f"[DEBUG] dpsim_payload_count={len(dpsim_profile.payload)}")
            print("[DEBUG] dpsim_payload_first_10=", dpsim_profile.payload[:10])

            if DEBUG_FLAGS["DEBUG_DUMP_PAYLOAD"]:
                dump_json(transformed_rows_dump, transformed.rows)
                dump_json(dpsim_payload_dump, dpsim_profile.payload)

                print(f"[DEBUG] Wrote transformed rows to: {transformed_rows_dump}")
                print(f"[DEBUG] Wrote DPSim payload to: {dpsim_payload_dump}")

            # -----------------------------------------------------------------
            # Upload profile to DPSim
            # -----------------------------------------------------------------
            profile_keyword = f"load-profile-{run_id}"

            prof_body = await upload_profile(
                client=client,
                dpsim_url=dpsim_url,
                profile_keyword=profile_keyword,
                payload=dpsim_profile.payload,
            )

            print("[DEBUG] profile_upload_body=", prof_body)

            # -----------------------------------------------------------------
            # STEP 3: Run the simulation
            # -----------------------------------------------------------------
            sim_name = f"sim-{run_id}"

            sim_duration = payload.duration
            if DEBUG_FLAGS["DEBUG_SINGLE_TIMESTEP"]:
                sim_duration = 1

            sim_payload = {
                "name": sim_name,
                "use_xml": xml_keyword,
                "use_profile": profile_keyword,
                "duration": sim_duration,
                "timestep": payload.timestep,
                "freq": payload.freq,
                "solver": payload.solver,
                "domain": payload.domain,
            }

            sim_payload["replace_map"] = {**dpsim_profile.replace_map, **(payload.replace_map or {})}

            if payload.opf is not None:
                sim_payload["opf"] = payload.opf

            print("[DEBUG] Simulation payload:", sim_payload)

            await start_simulation(
                client=client,
                dpsim_url=dpsim_url,
                sim_payload=sim_payload,
            )

            print("Step 3 ok!")

            # -----------------------------------------------------------------
            # STEP 4: Wait for results
            # -----------------------------------------------------------------
            result_json = await poll_result(
                client=client,
                dpsim_url=dpsim_url,
                sim_name=sim_name,
                max_retries=20,
                delay_seconds=2.0,
            )

            print("Simulation finished successfully.")

            if isinstance(result_json, dict):
                raw_result_payload = result_json.get("result", result_json)
            else:
                raw_result_payload = result_json

            raw_result_hash = stable_hash(raw_result_payload)
            print("[DEBUG] raw_result_hash=", raw_result_hash)

            if isinstance(result_json, dict):
                log_raw_result_debug(result_json, raw_result_payload)

            processed_result = postprocess_dpsim_results(raw_result_payload)

            response_json = {
                "result": processed_result,
            }

            # -----------------------------------------------------------------
            # Attach debug summary to response
            # -----------------------------------------------------------------
            if DEBUG_FLAGS["DEBUG_ATTACH_SUMMARY_TO_RESPONSE"]:
                response_json["_debug"] = {
                    "run_id": run_id,
                    "profile_keyword": profile_keyword,
                    "sim_name": sim_name,
                    "xml_keyword": xml_keyword,
                    "request_payload": payload_debug,
                    "hashes": {
                        "db_hash": db_profile.hash,
                        "transformed_hash": transformed.hash,
                        "dpsim_payload_hash": dpsim_profile.hash,
                        "raw_result_hash": raw_result_hash,
                    },
                    "db_audit": db_profile.audit,
                    "db_sample_first_10": db_profile.sample_first_10,
                    "transform_audit": transformed.audit,
                    "dpsim_payload_debug": dpsim_profile.debug,
                    "debug_flags": DEBUG_FLAGS,
                    "payload_count": len(dpsim_profile.payload),
                    "transformed_rows_dump": (
                        transformed_rows_dump
                        if DEBUG_FLAGS["DEBUG_DUMP_PAYLOAD"]
                        else None
                    ),
                    "dpsim_payload_dump": (
                        dpsim_payload_dump
                        if DEBUG_FLAGS["DEBUG_DUMP_PAYLOAD"]
                        else None
                    ),
                    "ts_summary_first_5": make_ts_summary_first_5(
                        transformed.ts_summary
                    ),
                    "component_coverage": dpsim_profile.component_coverage,
                }

            return response_json

    except PipelineEarlyReturn as e:
        return e.response
