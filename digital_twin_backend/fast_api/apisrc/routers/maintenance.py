from datetime import datetime, timedelta

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import get_db
from ..mappings import parse_cel_id, resolve_plant
from ..schemas import CreateEventRequest


router = APIRouter()


@router.get("/scheduled_events/", tags=["Maintenance"])
def fetch_scheduled_events(cel_id: str, db: Session = Depends(get_db)):
    """
    Returns the scheduled events
    """
    cel_number, _ = parse_cel_id(cel_id)
    current_date = "2024-12-28T00:00:00"

    query = text("""
        SELECT m.submit_time, m.category, m.description, et.name, m.event_id
        FROM public.maintenance_event m
        JOIN public.plant pl ON pl.plant_id = m.plant_id
        JOIN public.energy_type et ON et.id = pl.energy_type_id
        WHERE pl.cel_id = :cel_id
          AND pl.plant_id > 0
          AND m.submit_time > :current_date
          AND m.type = 'scheduled_event'
        ORDER BY m.submit_time;
    """)

    try:
        result = db.execute(query, {"cel_id": cel_number, "current_date": current_date}).fetchall()
        return [{"Date": row[0], "Component": row[1], "Description": row[2], "Energy Source": row[3], "ID": row[4]} for row in result]
    except Exception as e:
        return {"error": str(e)}


@router.get("/past_events/", tags=["Maintenance"])
def fetch_past_events(cel_id: str, db: Session = Depends(get_db)):
    """
    Returns the past events
    """
    cel_number, _ = parse_cel_id(cel_id)

    query = text("""
        SELECT m.submit_time, m.category, m.description, et.name, m.event_id
        FROM public.maintenance_event m
        JOIN public.plant pl ON pl.plant_id = m.plant_id
        JOIN public.energy_type et ON et.id = pl.energy_type_id
        WHERE pl.cel_id = :cel_id
          AND pl.plant_id > 0
          AND m.type = 'past_event'
        ORDER BY m.submit_time DESC
        LIMIT 20;
    """)

    try:
        result = db.execute(query, {"cel_id": cel_number}).fetchall()
        return [{"Date": row[0], "Component": row[1], "Description": row[2], "Energy Source": row[3], "ID": row[4]} for row in result]
    except Exception as e:
        return {"error": str(e)}


@router.get("/fault_warnings/", tags=["Maintenance"])
def fetch_fault_warnings(cel_id: str, db: Session = Depends(get_db)):
    """
    Returns the fault warnings
    """
    cel_number, _ = parse_cel_id(cel_id)

    query = text("""
        SELECT m.severity, m.submit_time, m.description, m.status, et.name, m.event_id
        FROM public.maintenance_event m
        JOIN public.plant pl ON pl.plant_id = m.plant_id
        JOIN public.energy_type et ON et.id = pl.energy_type_id
        WHERE pl.cel_id = :cel_id
          AND pl.plant_id > 0
          AND m.type = 'fault_warning'
        ORDER BY m.submit_time DESC
        LIMIT 20;
    """)

    try:
        result = db.execute(query, {"cel_id": cel_number}).fetchall()
        return [{"Severity": row[0], "Date": row[1], "Description": row[2], "Status": row[3], "Energy Source": row[4], "ID": row[5]} for row in result]
    except Exception as e:
        return {"error": str(e)}


@router.post("/create_event", tags=["Maintenance"])
def create_event(cel: str, payload: CreateEventRequest, db: Session = Depends(get_db)):
    """
    Creates a new event
    """
    cel_number, _ = parse_cel_id(cel)
    if cel_number is None:
        return {"error": f"Invalid cel: {cel}"}

    resolved = resolve_plant(db, cel_number, payload.res)
    if resolved is None:
        return {"error": f"No plant found for cel={cel} energy_type={payload.res}"}
    plant_id, _ = resolved

    device_id = None
    if payload.device_id:
        row = db.execute(
            text("SELECT device_id FROM public.device WHERE plant_id = :plant_id AND name = :dev_name"),
            {"plant_id": plant_id, "dev_name": payload.device_id},
        ).fetchone()
        device_id = row[0] if row else None

    date = payload.submit_time + 'T00:00:00'

    query = text("""
        INSERT INTO public.maintenance_event
            (plant_id, device_id, description, type, submit_time, category, comment, recurrent)
        VALUES (:plant_id, :device_id, :description, 'scheduled_event', :date, :category, :comment, :recurrent);
    """)

    try:
        db.execute(query, {
            "plant_id": plant_id,
            "device_id": device_id,
            "description": payload.description,
            "date": date,
            "category": payload.category,
            "comment": payload.comment,
            "recurrent": payload.recurrent,
        })
        db.commit()
        return [{"Event created successfully"}]
    except Exception as e:
        return {"error": str(e)}


@router.delete("/delete_event/{event_id}", tags=["Maintenance"])
def delete_event(event_id: int, db: Session = Depends(get_db)):
    """
    Deletes an event
    """
    query = text("""
        DELETE FROM public.maintenance_event
        WHERE event_id = :event_id
        RETURNING event_id;
    """)

    result = db.execute(query, {"event_id": event_id})
    deleted = result.fetchone()
    db.commit()

    if deleted:
        return {"message": f"Event {event_id} deleted successfully"}
    raise HTTPException(status_code=404, detail="Event not found")


@router.get("/Inverter_overheating/", tags=["Maintenance"])
def inverter_overheating(cel_id: str, db: Session = Depends(get_db)):
    """
    Checks whether the inverter overheated (Internal inverter temperature > 55 while connected to grid) the previous day.
    """
    cel_mapping = {"cel3-pv": "CEL3 PV Plant"}
    cel = cel_mapping.get(cel_id)
    current_date = "2025-02-19T00:00:00"
    current_date_obj = datetime.strptime(current_date, '%Y-%m-%dT%H:%M:%S')
    one_day_before = (current_date_obj - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")

    query = text("""
        SELECT d.name AS dev_id, i.temperature AS temperature,
               i.inverter_state, i.timestamp
        FROM public.inverter_data i
        JOIN public.device d ON d.device_id = i.device_id
        JOIN public.plant p ON p.plant_id = d.plant_id
        WHERE p.name = :cel
          AND p.plant_id > 0
          AND i.timestamp BETWEEN :one_day_before AND :current_date
        ORDER BY d.name;
    """)

    try:
        result = db.execute(query, {"cel": cel, "one_day_before": one_day_before, "current_date": current_date}).fetchall()
        columns = ['Device', 'Temperature', 'State', 'Time']
        df = pd.DataFrame(result, columns=columns)
        group = df.groupby('Device')
        final = []

        for device, device_df in group:
            malfunction = 0
            for temp, state, time in zip(device_df["Temperature"], device_df["State"], device_df["Time"]):
                if temp > 55 and (state == "Grid Connected" or state == "Grid connected"):
                    final.append([device, "Overheated", time])
                    malfunction = 1
            if malfunction == 0:
                final.append([device, "Normal Temperatures", "all day"])

        return [{"Device ID": row[0], "Condition": row[1], "Timestamp": row[2]} for row in final]
    except Exception as e:
        return {"error": str(e)}


@router.get("/Inverter_underperformance/", tags=["Maintenance"])
def inverter_underperformance(cel_id: str, date: str, cutoff_percentage: float, db: Session = Depends(get_db)):
    """
    Checks whether the inverter is underperforming.
    """
    cel_mapping = {"cel3-pv": "CEL3 PV Plant"}
    cel = cel_mapping.get(cel_id)
    current_date = date + "T00:00:00"
    current_date_obj = datetime.strptime(current_date, '%Y-%m-%dT%H:%M:%S')
    one_day_before = (current_date_obj - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")

    Y = 1000
    Gstc = 1
    a = -0.005
    Tstc = 25

    def expected_prod(stats):
        Total_P_expected = 0
        Total_P_actual = 0

        P_max = stats["Input Power"].max()
        Irr_max = stats["Irradiance"].max()
        print("Pmax :", P_max)
        k = 0
        j = 0
        for i in range(len(stats)):
            row = stats.iloc[i]
            T = row["PV Temperature"]
            G = row["Irradiance"] * 0.001
            P_actual = row["Input Power"]

            P_expected = Y * (G / Gstc) * (1 + a * (T - Tstc))
            P_expected = P_expected * cutoff_percentage

            if P_expected > P_max:
                print("P_expected :", P_expected)
                print("P_actual :", P_actual)
                print("Irradiance :", G * 1000)
                print("PV Temperature :", T)
                k = k + 1
            else:
                j = j + 1
            Total_P_expected = Total_P_expected + P_expected
            Total_P_actual = Total_P_actual + P_actual
        print("times expected higher than actual :", j)
        print("times expected lower than actual :", k)
        E_actual = Total_P_actual * 0.0833
        E_expected = Total_P_expected * 0.0833
        relative_diff = round(((E_actual - E_expected) / E_actual), 3)

        return relative_diff

    query = text("""
        WITH inv AS (
            SELECT i.timestamp, i.input_power AS input_power
            FROM public.inverter_data i
            JOIN public.device d ON d.device_id = i.device_id
            JOIN public.plant p ON p.plant_id = d.plant_id
            WHERE p.name = :cel
              AND p.plant_id > 0
              AND i.timestamp BETWEEN :one_day_before AND :current_date
              AND (i.inverter_state = 'Grid connected' OR i.inverter_state = 'Grid Connected')
        ),
        wea AS (
            SELECT w.timestamp,
                   AVG(w.pv_temperature) AS pv_temperature,
                   AVG(w.irradiance) AS irradiance
            FROM public.weather_data w
            JOIN public.device d ON d.device_id = w.device_id
            JOIN public.plant p ON p.plant_id = d.plant_id
            WHERE p.name = :cel
              AND p.plant_id > 0
              AND w.timestamp BETWEEN :one_day_before AND :current_date
              AND w.irradiance > 100
            GROUP BY w.timestamp
        )
        SELECT SUM(inv.input_power) AS total_input_power,
               inv.timestamp,
               wea.pv_temperature,
               wea.irradiance
        FROM inv
        JOIN wea ON wea.timestamp = inv.timestamp
        GROUP BY inv.timestamp, wea.pv_temperature, wea.irradiance
        ORDER BY inv.timestamp;
    """)
    try:
        result = db.execute(query, {"cel": cel, "one_day_before": one_day_before, "current_date": current_date}).fetchall()
        columns = ['Input Power', 'Collect Time', 'PV Temperature', 'Irradiance']
        df = pd.DataFrame(result, columns=columns)
        min_temp = df["PV Temperature"].min()
        avg_temp = df["PV Temperature"].mean()
        max_temp = df["PV Temperature"].max()

        min_irr = df["Irradiance"].min()
        avg_irr = df["Irradiance"].mean()
        max_irr = df["Irradiance"].max()

        min_power = df["Input Power"].min()
        avg_power = df["Input Power"].mean()
        max_power = df["Input Power"].max()

        rel_perf = expected_prod(df)

        return {
            "Min Temp": min_temp,
            "Avg Temp": avg_temp,
            "Max Temp": max_temp,
            "Min Irradiance": min_irr,
            "Avg Irradiance": avg_irr,
            "Max Irradiance": max_irr,
            "Min Power": min_power,
            "Avg Power": avg_power,
            "Max Power": max_power,
            "Performance Loss": str(rel_perf * 100) + "%",
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/Inverter_leakage_shutdown/", tags=["Maintenance"])
def inverter_leakage_shutdown(cel_id: str, db: Session = Depends(get_db)):
    """
    Checks whether the inverter is shutdown or leaking when input power is above 1.
    """
    cel_mapping = {"cel3-pv": "CEL3 PV Plant"}
    cel = cel_mapping.get(cel_id)
    current_date = "2025-02-19T00:00:00"
    current_date_obj = datetime.strptime(current_date, '%Y-%m-%dT%H:%M:%S')
    one_day_before = (current_date_obj - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")

    query = text("""
        WITH inv AS (
            SELECT id.name AS dev_id, i.inverter_state, i.timestamp,
                   i.input_power AS input_power
            FROM public.inverter_data i
            JOIN public.device id ON id.device_id = i.device_id
            JOIN public.plant p ON p.plant_id = id.plant_id
            WHERE p.name = :cel
              AND p.plant_id > 0
              AND i.timestamp BETWEEN :one_day_before AND :current_date
              AND (i.inverter_state = 'OFF : unexpected shutdown'
                   OR i.inverter_state = 'Standby : insulation resistance detection')
        ),
        wea AS (
            SELECT w.timestamp,
                   AVG(w.irradiance) AS irradiance
            FROM public.weather_data w
            JOIN public.device wd ON wd.device_id = w.device_id
            JOIN public.plant p ON p.plant_id = wd.plant_id
            WHERE p.name = :cel
              AND p.plant_id > 0
              AND w.timestamp BETWEEN :one_day_before AND :current_date
              AND w.irradiance > 50
            GROUP BY w.timestamp
        )
        SELECT inv.dev_id, inv.inverter_state, inv.timestamp, inv.input_power, wea.irradiance
        FROM inv
        JOIN wea ON wea.timestamp = inv.timestamp
        ORDER BY inv.dev_id;
    """)

    try:
        result = db.execute(query, {"cel": cel, "one_day_before": one_day_before, "current_date": current_date})
        return [{"Device": row[0], "Inverter_state": row[1], "Collect_time": row[2], "Input Power": row[3], "Irradiance": row[4]} for row in result]
    except Exception as e:
        return {"error": str(e)}


@router.get("/Inverter_efficiency/", tags=["Maintenance"])
def inverter_efficiency(cel_id: str, db: Session = Depends(get_db)):
    """
    Return timestamp and aggregated active power between 2 dates
    """
    cel_mapping = {"cel3-pv": "CEL3 PV Plant"}
    cel = cel_mapping.get(cel_id)
    current_date = "2025-02-19T00:00:00"
    current_date_obj = datetime.strptime(current_date, '%Y-%m-%dT%H:%M:%S')
    one_day_before = (current_date_obj - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")

    query = text("""
        SELECT d.name AS dev_id, AVG(i.efficiency) AS avg_efficiency
        FROM public.inverter_data i
        JOIN public.device d ON d.device_id = i.device_id
        JOIN public.plant p ON p.plant_id = d.plant_id
        WHERE p.name = :cel
          AND p.plant_id > 0
          AND i.timestamp BETWEEN :one_day_before AND :current_date
          AND (i.inverter_state = 'Grid connected' OR i.inverter_state = 'Grid Connected')
          AND i.input_power > 0
        GROUP BY d.name;
    """)

    try:
        result = db.execute(query, {"cel": cel, "one_day_before": one_day_before, "current_date": current_date})
        return [
            {
                "Inverter ": row[0],
                "Average_efficiency": round(row[1] * 0.01, 3),
                "Operational Health": "Good" if row[1] * 0.01 > 0.95 else "Bad",
            }
            for row in result
        ]
    except Exception as e:
        return {"error": str(e)}
