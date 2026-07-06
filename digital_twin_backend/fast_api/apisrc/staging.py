from datetime import datetime, timedelta

import pytz
from sqlalchemy import text
from sqlalchemy.orm import Session


def fetch_staging_energy_totals_mwh(cel_id: str, db: Session) -> dict:
    parts = cel_id.split('-')
    if len(parts) < 2 or not parts[0].startswith('cel'):
        return {"error": f"Invalid cel_id format: {cel_id}"}

    try:
        cel_number = int(parts[0][3:])
    except ValueError:
        return {"error": f"Invalid cel_id format: {cel_id}"}

    energy_type = parts[1]

    energy_type_row = db.execute(
        text("SELECT id FROM public.energy_type WHERE name = :name"),
        {"name": energy_type}
    ).fetchone()
    if not energy_type_row:
        return {"error": f"Energy type '{energy_type}' not found in staging"}

    plant_row = db.execute(
        text("SELECT plant_id FROM public.plant WHERE cel_id = :cel_id AND energy_type_id = :et_id AND plant_id > 0"),
        {"cel_id": cel_number, "et_id": energy_type_row[0]}
    ).fetchone()
    if not plant_row:
        return {"error": f"No plant found for {cel_id}"}

    device_ids = [row[0] for row in db.execute(
        text("SELECT device_id FROM public.device WHERE plant_id = :plant_id"),
        {"plant_id": plant_row[0]}
    ).fetchall()]
    if not device_ids:
        return {"error": f"No devices found for {cel_id}"}

    data_table = f"public.{energy_type}_data"

    now = datetime.today()
    one_day_before = now - timedelta(days=1)
    one_week_before = now - timedelta(weeks=1)
    one_month_before = now - timedelta(days=30)
    one_year_before = now - timedelta(days=365)

    query = text(f"""
        WITH totals AS (
            SELECT
                COALESCE(SUM(value) FILTER (WHERE timestamp BETWEEN :one_day_before AND :now), 0) AS last_day_total,
                COALESCE(SUM(value) FILTER (WHERE timestamp BETWEEN :one_week_before AND :one_day_before), 0) AS prev_week_total,
                COALESCE(SUM(value) FILTER (WHERE timestamp BETWEEN :one_month_before AND :one_week_before), 0) AS prev_month_total,
                COALESCE(SUM(value) FILTER (WHERE timestamp BETWEEN :one_year_before AND :one_month_before), 0) AS prev_year_total,
                COALESCE(SUM(value) FILTER (WHERE timestamp < :one_year_before), 0) AS rest_total
            FROM {data_table}
            WHERE device_id = ANY(:device_ids)
        )
        SELECT
            last_day_total,
            last_day_total + prev_week_total AS last_week_total,
            last_day_total + prev_week_total + prev_month_total AS last_month_total,
            last_day_total + prev_week_total + prev_month_total + prev_year_total AS last_year_total,
            last_day_total + prev_week_total + prev_month_total + prev_year_total + rest_total AS all_time_total
        FROM totals
    """)

    result = db.execute(query, {
        "device_ids": device_ids,
        "now": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "one_day_before": one_day_before.strftime("%Y-%m-%dT%H:%M:%S"),
        "one_week_before": one_week_before.strftime("%Y-%m-%dT%H:%M:%S"),
        "one_month_before": one_month_before.strftime("%Y-%m-%dT%H:%M:%S"),
        "one_year_before": one_year_before.strftime("%Y-%m-%dT%H:%M:%S"),
    }).fetchone()

    def to_mwh(val):
        return round(float(val) * 0.0833 / 1000, 3) if val is not None else 0.0

    return {
        "last_day": to_mwh(result[0]),
        "last_week": to_mwh(result[1]),
        "last_month": to_mwh(result[2]),
        "last_year": to_mwh(result[3]),
        "total": to_mwh(result[4]),
    }


def fetch_forecast_data_from_staging_tables(cel_id: str, db: Session):
    try:
        parts = cel_id.split('-')

        if len(parts) < 2 or not parts[0].startswith('cel'):
            return {"error": f"Invalid cel_id format: {cel_id}"}

        cel_number = int(parts[0][3:])
        energy_type = parts[1]

        athens = pytz.timezone("Europe/Athens")
        current_date = datetime.now(athens).strftime('%Y-%m-%dT%H:%M:%S')
        current_date_obj = datetime.strptime(current_date, '%Y-%m-%dT%H:%M:%S')

        current_date_obj = current_date_obj.replace(minute=0, second=0, microsecond=0).replace(tzinfo=None)
        if datetime.strptime(current_date, '%Y-%m-%dT%H:%M:%S').minute < 13:
            current_date_obj = current_date_obj - timedelta(hours=1)

        one_hour_before_obj = (current_date_obj - timedelta(hours=1) + timedelta(minutes=5))

        energy_result = db.execute(
            text("SELECT id FROM public.energy_type WHERE name = :energy_type"),
            {"energy_type": energy_type}
        ).fetchone()

        if not energy_result:
            return {"error": f"Energy type '{energy_type}' not found in staging"}

        energy_type_id = energy_result[0]

        plant_result = db.execute(
            text("""
                SELECT plant_id FROM public.plant
                WHERE cel_id = :cel_id AND energy_type_id = :energy_type_id AND plant_id > 0
            """),
            {"cel_id": cel_number, "energy_type_id": energy_type_id}
        ).fetchone()

        if not plant_result:
            return {"error": f"No plant found for cel_id {cel_number} and energy_type '{energy_type}'"}

        plant_id = plant_result[0]

        devices_result = db.execute(
            text("SELECT device_id FROM public.device WHERE plant_id = :plant_id"),
            {"plant_id": plant_id}
        ).fetchall()

        if not devices_result:
            return {"error": f"No devices found for plant_id {plant_id}"}

        device_ids = [row[0] for row in devices_result]

        data_table = f"public.{energy_type}_data"

        device_ids_csv = ','.join(str(d) for d in device_ids)

        actual_query = text(f"""
            SELECT timestamp, SUM(value) AS total_value
            FROM {data_table}
            WHERE device_id IN ({device_ids_csv})
            AND timestamp BETWEEN :start_date AND :end_date
            GROUP BY timestamp
            ORDER BY timestamp
        """)

        actual_result = db.execute(actual_query, {
            "start_date": one_hour_before_obj,
            "end_date": current_date_obj
        }).fetchall()

        forecast_query = text("""
            SELECT timestamp, value, lower, upper
            FROM public.plant_forecast
            WHERE plant_id = :plant_id
            AND timestamp > :current_date
            AND timestamp <= :forecast_end
            ORDER BY timestamp
        """)

        forecast_end = current_date_obj + timedelta(hours=2)
        forecast_result = db.execute(forecast_query, {
            "plant_id": plant_id,
            "current_date": current_date_obj,
            "forecast_end": forecast_end
        }).fetchall()

        actual = [
            [row[0].strftime("%Y-%m-%dT%H:%M:%S"), round(float(row[1]), 3)]
            for row in actual_result
        ]

        forecast = []
        forecast_range = []

        for row in forecast_result:
            timestamp_str = row[0].strftime("%Y-%m-%dT%H:%M:%S")
            forecast_value = round(float(row[1]), 3)
            lower_bound = round(float(row[2]), 3) if row[2] is not None else forecast_value
            upper_bound = round(float(row[3]), 3) if row[3] is not None else forecast_value
            forecast.append([timestamp_str, forecast_value])
            forecast_range.append([timestamp_str, lower_bound, upper_bound])

        data_state = 1 if len(forecast_result) > 0 else 0

        return {
            "actual": actual,
            "forecast": forecast,
            "forecast_range": forecast_range,
            "data_state": data_state
        }

    except Exception as e:
        return {"error": f"Exception in fetch_forecast_data_from_staging_tables: {str(e)}"}
