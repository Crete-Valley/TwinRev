import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import (
    DPSIM_URL,
    TSO_ALLOWED_POWER_TYPES,
    TSO_DISPLAY_NAME_MAP,
    TSO_PLOT_PROFILE_TYPES,
    TSO_SPLIT_BY_COMPONENT,
)
from ..db import get_db
from ..dpsim_services.pipeline import run_dpsim_pipeline as run_dpsim_pipeline_service
from ..schemas import SimulationRequest


router = APIRouter()


@router.get("/buses", tags=["TSO"])
def fetch_buses(db: Session = Depends(get_db)):
    """
    Return one stable id per distinct buses for the frontend dropdown.
    """
    query = text("""
            SELECT MIN(id) As id, bus
            FROM tso_bus_mapping_new
            GROUP BY bus
            ORDER BY bus;
    """)

    try:
        results = db.execute(query).fetchall()
        return [{"id": row[0], "bus": row[1]} for row in results]
    except Exception as e:
        return {"error": str(e)}


@router.get("/bus-power-data", tags=["TSO"])
def fetch_bus_power_data(
    busId: int,
    power_type: str,
    date: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Returns one full-day time series for a selected bus and power type.

    - LOAD / PV / WP / balancing unit are aggregated per profile_type
    - CU PRODUCTION (active) and COMPENSATOR (reactive) are split per component_id
    """
    if power_type not in TSO_ALLOWED_POWER_TYPES:
        raise HTTPException(status_code=400, detail="power_type must be 'active' or 'reactive'")

    ordered_profile_types = TSO_PLOT_PROFILE_TYPES[power_type]
    allowed_profile_types = set(ordered_profile_types)
    split_profiles = TSO_SPLIT_BY_COMPONENT[power_type]

    bus_query = text("""
        SELECT bus
        FROM tso_bus_mapping_new
        WHERE id = :busId;
    """)

    try:
        bus_row = db.execute(bus_query, {"busId": busId}).fetchone()

        if not bus_row:
            raise HTTPException(status_code=404, detail=f"No bus found for id {busId}")

        bus = bus_row[0]

        dates_query = text("""
            SELECT DISTINCT DATE(ts) AS day
            FROM tso_power_profiles_data_new
            WHERE bus = :bus
            ORDER BY day;
        """)

        date_rows = db.execute(dates_query, {"bus": bus}).fetchall()
        available_dates = [row[0].isoformat() for row in date_rows]

        if not available_dates:
            raise HTTPException(status_code=404, detail=f"No dates found for bus '{bus}'")

        selected_date = date if date else available_dates[-1]

        if selected_date not in available_dates:
            raise HTTPException(
                status_code=400,
                detail=f"date '{selected_date}' is not available for bus '{bus}'",
            )

        try:
            day_obj = datetime.strptime(selected_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="date must be in YYYY-MM-DD format")

        start_ts = day_obj.strftime("%Y-%m-%dT00:00:00")
        end_ts = (day_obj + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00")

        query = text("""
            SELECT
                ts,
                profile_type,
                component_id,
                SUM(value) AS value
            FROM tso_power_profiles_data_new
            WHERE bus = :bus
              AND power_type = :power_type
              AND ts >= :start_ts
              AND ts < :end_ts
            GROUP BY ts, profile_type, component_id
            ORDER BY ts, profile_type, component_id;
        """)

        results = db.execute(query, {
            "bus": bus,
            "power_type": power_type,
            "start_ts": start_ts,
            "end_ts": end_ts,
        }).fetchall()

        filtered_results = []
        for ts, profile_type, component_id, value in results:
            if profile_type not in allowed_profile_types:
                continue
            filtered_results.append((ts, profile_type, component_id, float(value)))

        if not filtered_results:
            return {
                "busId": busId,
                "bus": bus,
                "power_type": power_type,
                "available_dates": available_dates,
                "selected_date": selected_date,
                "data": {"labels": [], "series": []},
            }

        labels = sorted({row[0].strftime("%Y-%m-%dT%H:%M:%S") for row in filtered_results})

        aggregated_series = {}
        split_series = {}

        for ts, profile_type, component_id, value in filtered_results:
            ts_label = ts.strftime("%Y-%m-%dT%H:%M:%S")

            if profile_type in split_profiles:
                key = (profile_type, component_id)

                if key not in split_series:
                    split_series[key] = {
                        "series_key": f"{profile_type}::{component_id}",
                        "profile_type": profile_type,
                        "component_id": component_id,
                        "display_name": f'{TSO_DISPLAY_NAME_MAP.get(profile_type, profile_type)} ({component_id})',
                        "_values_by_ts": {},
                    }

                split_series[key]["_values_by_ts"][ts_label] = (
                    split_series[key]["_values_by_ts"].get(ts_label, 0.0) + value
                )
            else:
                key = profile_type

                if key not in aggregated_series:
                    aggregated_series[key] = {
                        "series_key": profile_type,
                        "profile_type": profile_type,
                        "component_id": None,
                        "display_name": TSO_DISPLAY_NAME_MAP.get(profile_type, profile_type),
                        "_values_by_ts": {},
                    }

                aggregated_series[key]["_values_by_ts"][ts_label] = (
                    aggregated_series[key]["_values_by_ts"].get(ts_label, 0.0) + value
                )

        series = []

        for profile_type in ordered_profile_types:
            if profile_type in split_profiles:
                matching = [
                    entry
                    for (ptype, _), entry in split_series.items()
                    if ptype == profile_type
                ]
                matching.sort(key=lambda x: x["component_id"])

                for entry in matching:
                    series.append({
                        "series_key": entry["series_key"],
                        "profile_type": entry["profile_type"],
                        "component_id": entry["component_id"],
                        "display_name": entry["display_name"],
                        "values": [entry["_values_by_ts"].get(label, 0.0) for label in labels],
                    })
            else:
                entry = aggregated_series.get(profile_type)
                if entry:
                    series.append({
                        "series_key": entry["series_key"],
                        "profile_type": entry["profile_type"],
                        "component_id": entry["component_id"],
                        "display_name": entry["display_name"],
                        "values": [entry["_values_by_ts"].get(label, 0.0) for label in labels],
                    })

        return {
            "busId": busId,
            "bus": bus,
            "power_type": power_type,
            "available_dates": available_dates,
            "selected_date": selected_date,
            "data": {"labels": labels, "series": series},
        }

    except HTTPException:
        raise
    except Exception as e:
        return {"error": str(e)}


@router.post("/dpsim/run-pipeline", tags=["TSO"])
async def run_dpsim_pipeline(
    payload: SimulationRequest,
    db: Session = Depends(get_db),
):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    return await run_dpsim_pipeline_service(
        payload=payload,
        db=db,
        dpsim_url=DPSIM_URL,
        base_dir=base_dir,
    )


@router.get("/tso/year-extreme-days", tags=["TSO"])
def fetch_year_extreme_days(
    year: int = Query(..., ge=2000, le=2100),
    min_timesteps: Optional[int] = Query(
        None,
        description="Optional filter for complete days, e.g. 24 for hourly data",
    ),
    db: Session = Depends(get_db),
):
    """
    Returns the days of a selected year where the whole grid has:

    1. Max renewable production: SUM(PV + WP)
    2. Min renewable production: SUM(PV + WP)
    3. Max load: SUM(LOAD)
    4. Min load: SUM(LOAD)

    Only active power is used.
    CU PRODUCTION, the balancing unit, COMPENSATOR and reactive values are ignored.
    """
    start_ts = datetime(year, 1, 1).strftime("%Y-%m-%dT00:00:00")
    end_ts = datetime(year + 1, 1, 1).strftime("%Y-%m-%dT00:00:00")

    query = text("""
        WITH daily_raw AS (
            SELECT
                DATE(ts) AS day,

                SUM(
                    CASE
                        WHEN profile_type IN ('PV', 'WP')
                        THEN COALESCE(value, 0)
                        ELSE 0
                    END
                ) AS production_sum,

                SUM(
                    CASE
                        WHEN profile_type = 'LOAD'
                        THEN COALESCE(value, 0)
                        ELSE 0
                    END
                ) AS load_sum,

                COUNT(DISTINCT ts) AS timestep_count

            FROM tso_power_profiles_data_new
            WHERE ts >= :start_ts
              AND ts < :end_ts
              AND power_type = 'active'
              AND profile_type IN ('PV', 'WP', 'LOAD')
              AND bus <> 'TOTAL'
              AND component_id NOT IN ('total_cu', 'total_load', 'total_pv', 'total_wp')
            GROUP BY DATE(ts)
        ),

        daily AS (
            SELECT *
            FROM daily_raw
            WHERE (:min_timesteps IS NULL OR timestep_count >= :min_timesteps)
        ),

        extremes AS (
            SELECT
                MAX(production_sum) AS max_production,
                MIN(production_sum) AS min_production,
                MAX(load_sum) AS max_load,
                MIN(load_sum) AS min_load
            FROM daily
        )

        SELECT
            'max_production' AS metric,
            d.day,
            d.production_sum,
            d.load_sum,
            d.timestep_count
        FROM daily d, extremes e
        WHERE d.production_sum = e.max_production

        UNION ALL

        SELECT
            'min_production' AS metric,
            d.day,
            d.production_sum,
            d.load_sum,
            d.timestep_count
        FROM daily d, extremes e
        WHERE d.production_sum = e.min_production

        UNION ALL

        SELECT
            'max_load' AS metric,
            d.day,
            d.production_sum,
            d.load_sum,
            d.timestep_count
        FROM daily d, extremes e
        WHERE d.load_sum = e.max_load

        UNION ALL

        SELECT
            'min_load' AS metric,
            d.day,
            d.production_sum,
            d.load_sum,
            d.timestep_count
        FROM daily d, extremes e
        WHERE d.load_sum = e.min_load

        ORDER BY metric, day;
    """)

    try:
        rows = db.execute(query, {
            "start_ts": start_ts,
            "end_ts": end_ts,
            "min_timesteps": min_timesteps,
        }).mappings().fetchall()

        if not rows:
            raise HTTPException(
                status_code=404,
                detail={
                    "message": f"No TSO profile data found for year {year}",
                    "year": year,
                    "start_ts": start_ts,
                    "end_ts": end_ts,
                    "min_timesteps": min_timesteps,
                },
            )

        result = {
            "year": year,
            "start_ts": start_ts,
            "end_ts": end_ts,
            "filters": {
                "power_type": "active",
                "production_profile_types": ["PV", "WP"],
                "load_profile_types": ["LOAD"],
                "excluded_bus": "TOTAL",
                "excluded_component_ids": [
                    "total_cu",
                    "total_load",
                    "total_pv",
                    "total_wp",
                ],
                "min_timesteps": min_timesteps,
            },
            "extremes": {
                "max_production": [],
                "min_production": [],
                "max_load": [],
                "min_load": [],
            },
        }

        for row in rows:
            metric = row["metric"]

            production_sum = float(row["production_sum"] or 0)
            load_sum = float(row["load_sum"] or 0)

            result["extremes"][metric].append({
                "date": row["day"].isoformat(),
                "production_sum": round(production_sum, 6),
                "load_sum": round(load_sum, 6),
                "timestep_count": int(row["timestep_count"] or 0),
            })

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error while fetching yearly grid extreme days: {str(e)}",
        )
