from datetime import datetime, timedelta

import httpx
import pandas as pd
import pytz
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import get_db
from ..staging import (
    fetch_forecast_data_from_staging_tables,
    fetch_staging_energy_totals_mwh,
)


router = APIRouter()


CEL_ID_TO_PLANT_CODE = {
    "cel3-pv": "CEL3 PV Plant",
}


@router.get("/production-analytics/weather/", tags=["Production"])
def production_weather(cel_id: str, date: str, db: Session = Depends(get_db)):
    """
    Return the weather features (MIN, MAX AVG) for a specific date (day)
    """
    cel = CEL_ID_TO_PLANT_CODE.get(cel_id)
    if not cel:
        return {"error": "Invalid cel_id provided"}

    date_obj = datetime.strptime(date, "%Y-%m-%d")
    start_date = date_obj.strftime("%Y-%m-%dT00:00:00")
    end_date = (date_obj + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%S')

    query = text("""
        SELECT
            AVG(w.irradiance) AS avg_irradiance, MIN(w.irradiance) AS min_irradiance, MAX(w.irradiance) AS max_irradiance,
            AVG(w.daily_iradiation) AS avg_iradiation, MIN(w.daily_iradiation) AS min_iradiation, MAX(w.daily_iradiation) AS max_iradiation,
            AVG(w.temperature) AS avg_temperature, MIN(w.temperature) AS min_temperature, MAX(w.temperature) AS max_temperature,
            AVG(w.wind_speed) AS avg_wind_speed, MIN(w.wind_speed) AS min_wind_speed, MAX(w.wind_speed) AS max_wind_speed,
            AVG(w.pv_temperature) AS avg_pv_temperature, MIN(w.pv_temperature) AS min_pv_temperature, MAX(w.pv_temperature) AS max_pv_temperature
        FROM public.weather_data w
        JOIN public.device d ON d.device_id = w.device_id
        JOIN public.plant p ON p.plant_id = d.plant_id
        WHERE p.name = :cel
          AND p.plant_id > 0
          AND w.timestamp BETWEEN :start_date AND :end_date;
    """)

    try:
        result = db.execute(query, {"cel": cel, "start_date": start_date, "end_date": end_date}).fetchone()
        return {
            "irradiance": {"avg": result[0], "min": result[1], "max": result[2]},
            "irradiation": {"avg": result[3], "min": result[4], "max": result[5]},
            "ambient_temperature": {"avg": result[6], "min": result[7], "max": result[8]},
            "wind_speed": {"avg": result[9], "min": result[10], "max": result[11]},
            "pv_temperature": {"avg": result[12], "min": result[13], "max": result[14]},
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/production-analytics/production/", tags=["Production"])
def production_totals(cel_id: str, db: Session = Depends(get_db)):
    """
    Returns the total power produced for the last day, week, month, year and total
    """
    cel = CEL_ID_TO_PLANT_CODE.get(cel_id)

    if not cel:
        staging_totals = fetch_staging_energy_totals_mwh(cel_id, db)
        if "error" in staging_totals:
            return staging_totals

        last_day_energy = staging_totals["last_day"]
        last_week_energy = staging_totals["last_week"]
        last_month_energy = staging_totals["last_month"]
        last_year_energy = staging_totals["last_year"]
        total_energy = staging_totals["total"]

        safe_last_day = last_day_energy if last_day_energy > 0 else 1

        return {
            "last_day": {"production": last_day_energy, "savings": 289, "cost_reduction": round(last_day_energy * 0.312, 3)},
            "last_week": {"production": last_week_energy, "savings": round((last_week_energy / safe_last_day) * 289, 0), "cost_reduction": round(last_week_energy * 0.312, 3)},
            "last_month": {"production": last_month_energy, "savings": round((last_month_energy / safe_last_day) * 289, 0), "cost_reduction": round(last_month_energy * 0.312, 3)},
            "last_year": {"production": last_year_energy, "savings": round((last_year_energy / safe_last_day) * 289, 0), "cost_reduction": round(last_year_energy * 0.312, 3)},
            "total": {"production": total_energy, "savings": round((total_energy / safe_last_day) * 289, 0), "cost_reduction": round(total_energy * 0.312, 3)},
        }

    current_date = datetime.today().strftime('%Y-%m-%dT%H:%M:%S')
    current_date_obj = datetime.strptime(current_date, '%Y-%m-%dT%H:%M:%S')

    one_day_before = (current_date_obj - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")
    one_week_before = (current_date_obj - timedelta(weeks=1)).strftime("%Y-%m-%dT%H:%M:%S")
    one_month_before = (current_date_obj - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S")
    one_year_before = (current_date_obj - timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%S")

    query = text("""
            WITH total_power AS (
                SELECT
                    i.timestamp, SUM(i.active_power) AS total_active_power
                FROM public.inverter_data i
                JOIN public.device d ON d.device_id = i.device_id
                JOIN public.plant p ON p.plant_id = d.plant_id
                WHERE p.name = :cel
                  AND p.plant_id > 0
                GROUP BY i.timestamp
            ),
            step_totals AS (
                SELECT
                    SUM(total_active_power) FILTER (WHERE timestamp BETWEEN :one_day_before AND :current_date) AS last_day_total,
                    SUM(total_active_power) FILTER (WHERE timestamp BETWEEN :one_week_before AND :one_day_before) AS prev_week_total,
                    SUM(total_active_power) FILTER (WHERE timestamp BETWEEN :one_month_before AND :one_week_before) AS prev_month_total,
                    SUM(total_active_power) FILTER (WHERE timestamp BETWEEN :one_year_before AND :one_month_before) AS prev_year_total,
                    SUM(total_active_power) FILTER (WHERE timestamp < :one_year_before) AS rest_total
                FROM total_power
            )
            SELECT
                last_day_total,
                last_day_total + prev_week_total AS last_week_total,
                last_day_total + prev_week_total + prev_month_total AS last_month_total,
                last_day_total + prev_week_total + prev_month_total + prev_year_total AS last_year_total,
                last_day_total + prev_week_total + prev_month_total + prev_year_total + rest_total AS all_time_total
            FROM step_totals;
        """)

    result = db.execute(query, {
        "cel": cel,
        "current_date": current_date,
        "one_day_before": one_day_before,
        "one_week_before": one_week_before,
        "one_month_before": one_month_before,
        "one_year_before": one_year_before,
    }).fetchone()

    try:
        last_day_energy = round(result[0] * 0.0833 / 1000, 3) if result[0] is not None else 0
        last_week_energy = round(result[1] * 0.0833 / 1000, 3) if result[1] is not None else 0
        last_month_energy = round(result[2] * 0.0833 / 1000, 3) if result[2] is not None else 0
        last_year_energy = round(result[3] * 0.0833 / 1000, 3) if result[3] is not None else 0
        total_energy = round(result[4] * 0.0833 / 1000, 3) if result[4] is not None else 0

        return {
            "last_day": {"production": last_day_energy, "savings": 289, "cost_reduction": round(last_day_energy * 0.312, 3)},
            "last_week": {"production": last_week_energy, "savings": round((last_week_energy / last_day_energy) * 289, 0), "cost_reduction": round(last_week_energy * 0.312, 3)},
            "last_month": {"production": last_month_energy, "savings": round((last_month_energy / last_day_energy) * 289, 0), "cost_reduction": round(last_month_energy * 0.312, 3)},
            "last_year": {"production": last_year_energy, "savings": round((last_year_energy / last_day_energy) * 289, 0), "cost_reduction": round(last_year_energy * 0.312, 3)},
            "total": {"production": total_energy, "savings": round((total_energy / last_day_energy) * 289, 0), "cost_reduction": round(total_energy * 0.312, 3)},
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/production-analytics/emission-reduction/", tags=["Production"])
def production_emission_reduction(cel_id: str, db: Session = Depends(get_db)):
    """
    Return the CO2 emissions saved, the amount of lignite saved and the respective amount of trees planted
    """
    cel = CEL_ID_TO_PLANT_CODE.get(cel_id)

    if not cel:
        staging_totals = fetch_staging_energy_totals_mwh(cel_id, db)
        if "error" in staging_totals:
            return staging_totals
        total_energy_mwh = staging_totals["total"]
        return {
            "co2_emissions_saved": round(total_energy_mwh * 0.312, 3),
            "lignite_saved": round(total_energy_mwh * 1.5, 3),
            "equivalent_tree": round((total_energy_mwh * 0.312) / 0.039, 3),
        }

    query = text("""
            WITH total_power AS (
                SELECT
                    i.timestamp, SUM(i.active_power) AS total_active_power
                FROM public.inverter_data i
                JOIN public.device d ON d.device_id = i.device_id
                JOIN public.plant p ON p.plant_id = d.plant_id
                WHERE p.name = :cel
                  AND p.plant_id > 0
                GROUP BY i.timestamp
            )
            SELECT SUM(total_active_power) FROM total_power
    """)

    result = db.execute(query, {"cel": cel}).fetchone()

    energy_kW = result[0]
    energy = (energy_kW * 0.0833) / 1000
    emissions = energy * 0.312
    lignite_saved = energy * 1.5
    trees_planted = emissions / 0.039

    try:
        return {
            "co2_emissions_saved": round(emissions, 3),
            "lignite_saved": round(lignite_saved, 3),
            "equivalent_tree": round(trees_planted, 3),
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/production-forecasting/", tags=["Production"])
def production_forecasting(cel_id: str, db: Session = Depends(get_db)):
    """
    Returns actual PV production for the previous hour and forecast for the next 2 hours.
    """
    cel_mapping = {
        "cel3": {"cel": 3, "plant_code": "CEL3 PV Plant"},
        "cel3-pv": {"cel": 3, "plant_code": "CEL3 PV Plant"},
    }

    mapped = cel_mapping.get(cel_id)

    if not mapped:
        return fetch_forecast_data_from_staging_tables(cel_id, db)

    cel = mapped["cel"]
    plant_code = mapped["plant_code"]

    athens = pytz.timezone("Europe/Athens")
    now_athens = datetime.now(athens).replace(tzinfo=None)
    rounded_hour = now_athens.replace(minute=0, second=0, microsecond=0)

    if now_athens.minute >= 13:
        current_date_obj = rounded_hour
    else:
        current_date_obj = rounded_hour - timedelta(hours=1)

    one_hour_before_obj = current_date_obj - timedelta(hours=1) + timedelta(minutes=5)
    forecast_end_obj = current_date_obj + timedelta(hours=2)

    forecast_query = text("""
        SELECT pf.timestamp, pf.value, pf.lower, pf.upper
        FROM public.plant_forecast pf
        JOIN public.plant p ON p.plant_id = pf.plant_id
        WHERE p.name = :plant_code
          AND p.plant_id > 0
          AND pf.timestamp > :start_date
          AND pf.timestamp <= :end_date
        ORDER BY pf.timestamp;
    """)

    actual_query = text("""
        SELECT i.timestamp, SUM(i.active_power) AS total_active_power
        FROM public.inverter_data i
        JOIN public.device d ON d.device_id = i.device_id
        JOIN public.plant p ON p.plant_id = d.plant_id
        WHERE p.name = :plant_code
          AND p.plant_id > 0
          AND i.timestamp BETWEEN :start_date AND :end_date
        GROUP BY i.timestamp
        ORDER BY i.timestamp;
    """)

    try:
        forecast_result = db.execute(forecast_query, {
            "plant_code": plant_code,
            "start_date": current_date_obj.strftime("%Y-%m-%dT%H:%M:%S"),
            "end_date": forecast_end_obj.strftime("%Y-%m-%dT%H:%M:%S"),
        }).fetchall()

        if not forecast_result:
            raise HTTPException(
                status_code=404,
                detail={
                    "message": "No recent plant_forecast rows found.",
                    "searched_after": current_date_obj.strftime("%Y-%m-%dT%H:%M:%S"),
                    "searched_until": forecast_end_obj.strftime("%Y-%m-%dT%H:%M:%S"),
                    "cel": cel,
                    "plant_code": plant_code,
                },
            )

        actual_result = db.execute(actual_query, {
            "plant_code": plant_code,
            "start_date": one_hour_before_obj.strftime("%Y-%m-%dT%H:%M:%S"),
            "end_date": current_date_obj.strftime("%Y-%m-%dT%H:%M:%S"),
        }).fetchall()

        actual = [
            [
                collect_time.strftime("%Y-%m-%dT%H:%M:%S"),
                round(float(active_power), 3) if active_power is not None else 0.0,
            ]
            for collect_time, active_power in actual_result
        ]

        forecast = []
        forecast_range = []

        for timestamp, value, lower, upper in forecast_result:
            time_label = timestamp.strftime("%Y-%m-%dT%H:%M:%S")
            forecast.append([time_label, float(value) if value is not None else 0.0])
            forecast_range.append([
                time_label,
                float(lower) if lower is not None else 0.0,
                float(upper) if upper is not None else 0.0,
            ])

        return {
            "actual": actual,
            "forecast": forecast,
            "forecast_range": forecast_range,
            "data_state": 0,
            "debug": {
                "requested_cel_id": cel_id,
                "resolved_cel": cel,
                "forecast_start_time": forecast_result[0][0].strftime("%Y-%m-%dT%H:%M:%S"),
                "forecast_end_time": forecast_result[-1][0].strftime("%Y-%m-%dT%H:%M:%S"),
                "actual_start_time": one_hour_before_obj.strftime("%Y-%m-%dT%H:%M:%S"),
                "actual_end_time": current_date_obj.strftime("%Y-%m-%dT%H:%M:%S"),
                "actual_points": len(actual),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error while fetching production forecasting data: {str(e)}",
        )


@router.get("/production-forecasting-daily/", tags=["Production"])
def production_forecasting_daily(cel_id: str, db: Session = Depends(get_db)):
    """
    Forecasts the next 2 hours
    """
    state = "full"

    if cel_id == "cel3-pv":
        cel = 3
        plant_code = "CEL3 PV Plant"

    if not cel:
        return {"error": "Invalid cel_id provided"}

    athens = pytz.timezone("Europe/Athens")
    current_date = datetime.now(athens).strftime('%Y-%m-%dT%H:%M:%S')
    current_date_obj = datetime.strptime(current_date, '%Y-%m-%dT%H:%M:%S')

    if current_date_obj.hour == 0 and current_date_obj.minute > 30:
        current_date_obj_fixed = current_date_obj.replace(minute=0, second=0, microsecond=0).replace(tzinfo=None)
    elif current_date_obj.hour > 0:
        current_date_obj_fixed = current_date_obj.replace(hour=0, minute=0, second=0, microsecond=0).replace(tzinfo=None)
    elif current_date_obj.hour == 0 and current_date_obj.minute <= 30:
        state = "none"
        current_date_obj_fixed = current_date_obj.replace(minute=0, second=0, microsecond=0).replace(tzinfo=None)

    forecast_query = text("""
        SELECT pf.timestamp, pf.value, pf.lower, pf.upper
        FROM public.plant_forecast pf
        JOIN public.plant p ON p.plant_id = pf.plant_id
        WHERE p.name = :plant_code
          AND p.plant_id > 0
          AND pf.timestamp > :start_date
          AND pf.timestamp <= :end_date
          AND EXTRACT(MINUTE FROM pf.timestamp) = 0
        ORDER BY pf.timestamp;
    """)

    query2 = text("""
        SELECT i.timestamp, SUM(i.active_power) AS total_active_power
        FROM public.inverter_data i
        JOIN public.device d ON d.device_id = i.device_id
        JOIN public.plant p ON p.plant_id = d.plant_id
        WHERE p.name = :plant_code
          AND p.plant_id > 0
          AND i.timestamp BETWEEN :start_date AND :end_date
        GROUP BY i.timestamp
        ORDER BY i.timestamp;
    """)

    try:
        forecast_result = []
        if state == "full":
            forecast_result = db.execute(forecast_query, {
                "plant_code": plant_code,
                "start_date": current_date_obj_fixed.strftime("%Y-%m-%dT%H:%M:%S"),
                "end_date": (current_date_obj_fixed + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S"),
            }).fetchall()

        data_state = 1 if forecast_result else 0

        result2 = db.execute(query2, {
            "plant_code": plant_code,
            "start_date": current_date_obj_fixed.strftime("%Y-%m-%dT%H:%M:%S"),
            "end_date": current_date_obj.strftime("%Y-%m-%dT%H:%M:%S"),
        }).fetchall()

        df_inverter = pd.DataFrame(result2, columns=["Timestamp", "ActivePower"])
        total_columns = ["Timestamp", "ActivePower"]
        new_df_inverter = pd.DataFrame(columns=total_columns)

        for i in range(0, len(df_inverter), 12):
            values = []
            values.append(df_inverter.loc[i, "Timestamp"])

            sum_val = 0
            total = 0
            for j in range(i, i + 12):
                if j < len(df_inverter):
                    sum_val = sum_val + df_inverter.loc[j, "ActivePower"]
                    total = total + 1

                if total > 0:
                    values.append(sum_val / total)
                else:
                    values.append(0)

            new_df_inverter.loc[len(new_df_inverter)] = values

        actual = []
        for i in range(len(new_df_inverter)):
            actual.append([
                new_df_inverter.at[i, "Timestamp"].strftime("%H:%M"),
                round(new_df_inverter.at[i, "ActivePower"], 3),
            ])

        print("Actuals:", len(actual))

        forecast = []
        forecast_range = []

        if state == "full":
            for timestamp, value, lower, upper in forecast_result:
                date = timestamp.strftime("%H:%M")
                forecast.append([date, float(value) if value is not None else 0.0])
                forecast_range.append([
                    date,
                    float(lower) if lower is not None else 0.0,
                    float(upper) if upper is not None else 0.0,
                ])

        elif state == "none":
            date_list = pd.date_range(
                start=current_date_obj_fixed + timedelta(hours=1),
                end=(current_date_obj_fixed + timedelta(hours=24)),
                freq="1h",
            ).to_list()
            for date_point in date_list:
                date = date_point.strftime("%H:%M")
                forecast.append([date, 0])
                forecast_range.append([date, 0, 0])

        return {
            "actual": actual,
            "forecast": forecast,
            "forecast_range": forecast_range,
            "data_state": data_state,
        }

    except Exception as e:
        return {"error": str(e)}


@router.get("/call-flexibility", tags=["Production"])
async def call_flexibility():
    # The optimization can run for minutes; httpx's default timeout is only 5s.
    timeout = httpx.Timeout(600.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get("http://multi-energy-optimization-model-fastapi-service:8000/optimize")
        return {"internal_response": response.json()}
