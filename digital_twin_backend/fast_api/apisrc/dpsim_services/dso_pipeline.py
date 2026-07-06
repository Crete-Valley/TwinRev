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
from .postprocess import postprocess_dpsim_results
from .profiles import (
    PipelineEarlyReturn,
    get_dso_zip_path,
    parse_day_window,
    fetch_dso_profile_rows,
    transform_dso_profile_rows,
    build_dpsim_payload,
)


DEBUG_FLAGS = {
    "DEBUG_SINGLE_TIMESTEP": False,
    "DEBUG_PRINT_SUMMARY": True,
    "DEBUG_DUMP_PAYLOAD": True,
    "DEBUG_ATTACH_SUMMARY_TO_RESPONSE": True,
    "DEBUG_FAIL_ON_NONFINITE": True,
}



def _make_ts_summary_first_5(ts_summary: dict) -> list[dict]:
    result = []
    for ts in sorted(ts_summary.keys())[:5]:
        result.append({
            "ts": str(ts),
            "active": dict(ts_summary[ts]["active"]),
            "reactive": dict(ts_summary[ts]["reactive"]),
        })
    return result


async def run_dso_pipeline(payload, db, dpsim_url: str, base_dir: str) -> dict:
    cell = payload.cell
    run_id = uuid.uuid4().hex[:8]
    payload_debug = (
        payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    )

    print(f"[DSO] Starting pipeline for cell={cell} run_id={run_id}")
    print("[DSO][DEBUG] payload=", payload_debug)

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            # -----------------------------------------------------------------
            # STEP 1: Load DSO zip asset, validate XMLs, upload to DPSim
            # -----------------------------------------------------------------
            zip_path, asset_name = get_dso_zip_path(base_dir, cell)

            xml_keyword = await upload_xml(
                client=client,
                dpsim_url=dpsim_url,
                zip_path=zip_path,
                filename=f"{asset_name}.zip",
                fallback_keyword=asset_name,
            )

            start_ts, end_ts = parse_day_window(payload.date)

            print(f"[DSO][DEBUG] payload.date={payload.date}")
            print(f"[DSO][DEBUG] start_ts={start_ts} end_ts={end_ts}")
            print("[DSO] Step 1 completed.")

            # -----------------------------------------------------------------
            # STEP 2: Fetch DSO profiles, transform, upload to DPSim
            # -----------------------------------------------------------------
            db_profile = fetch_dso_profile_rows(
                db=db,
                start_ts=start_ts,
                end_ts=end_ts,
                date_str=payload.date,
                cell=cell,
            )

            transformed = transform_dso_profile_rows(
                rows=db_profile.rows,
                payload=payload,
                debug_flags=DEBUG_FLAGS,
            )

            print("[DSO][DEBUG] transformed_first_10=", transformed.rows[:10])

            expected_sim_components = {r["component_id"] for r in db_profile.rows}

            dpsim_profile = build_dpsim_payload(
                transformed_rows=transformed.rows,
                expected_components=expected_sim_components,
                timestamp_mode="relative_seconds",
            )

            # -----------------------------------------------------------------
            # Payload dumps
            # -----------------------------------------------------------------
            transformed_rows_dump = f"/tmp/dso_transformed_rows_{run_id}.json"
            dpsim_payload_dump = f"/tmp/dso_payload_{run_id}.json"

            distinct_payload_ts = sorted({r["ts"] for r in transformed.rows})
            print(f"[DSO][DEBUG] transformed_rows_count={len(transformed.rows)}")
            print(f"[DSO][DEBUG] transformed_distinct_ts={len(distinct_payload_ts)}")
            print(f"[DSO][DEBUG] dpsim_payload_count={len(dpsim_profile.payload)}")

            if DEBUG_FLAGS["DEBUG_DUMP_PAYLOAD"]:
                dump_json(transformed_rows_dump, transformed.rows)
                dump_json(dpsim_payload_dump, dpsim_profile.payload)

            profile_keyword = f"dso-load-profile-{run_id}"

            prof_body = await upload_profile(
                client=client,
                dpsim_url=dpsim_url,
                profile_keyword=profile_keyword,
                payload=dpsim_profile.payload,
            )

            print("[DSO][DEBUG] profile_upload_body=", prof_body)
            print("[DSO] Step 2 completed.")

            # -----------------------------------------------------------------
            # STEP 3: Run the simulation
            # -----------------------------------------------------------------
            sim_name = f"dso-sim-{run_id}"

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

            # DSO component IDs already match DPSim names — no prefix remapping needed.
            # Only pass through explicit overrides from the request payload.
            sim_payload["replace_map"] = payload.replace_map or {}

            if payload.opf is not None:
                sim_payload["opf"] = payload.opf

            print("[DSO][DEBUG] sim_payload=", sim_payload)

            await start_simulation(
                client=client,
                dpsim_url=dpsim_url,
                sim_payload=sim_payload,
            )

            print("[DSO] Step 3 completed.")

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

            print("[DSO] Simulation finished successfully.")

            if isinstance(result_json, dict):
                raw_result_payload = result_json.get("result", result_json)
            else:
                raw_result_payload = result_json

            raw_result_hash = stable_hash(raw_result_payload)
            print("[DSO][DEBUG] raw_result_hash=", raw_result_hash)

            # processed_result = postprocess_dpsim_results(raw_result_payload)

            response_json: dict = {"result": raw_result_payload}

            if DEBUG_FLAGS["DEBUG_ATTACH_SUMMARY_TO_RESPONSE"]:
                response_json["_debug"] = {
                    "run_id": run_id,
                    "cell": cell,
                    "asset_name": asset_name,
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
                    "ts_summary_first_5": _make_ts_summary_first_5(transformed.ts_summary),
                    "component_coverage": dpsim_profile.component_coverage,
                }

            return response_json

    except PipelineEarlyReturn as e:
        return e.response
