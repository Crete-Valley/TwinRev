from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import get_db


router = APIRouter()


PLANT_NAME_CEL3 = "CEL3 PV Plant"


@router.get("/Day_Cap+Date/", tags=["Database"])
def fetch_day_cap(db: Session = Depends(get_db)):
    """
    Return timestamp and aggregated day_cap between 2 dates
    """
    query = text("""
        SELECT i.timestamp, SUM(i.day_cap) AS total_day_cap
        FROM public.inverter_data i
        JOIN public.device d ON d.device_id = i.device_id
        JOIN public.plant p ON p.plant_id = d.plant_id
        WHERE p.name = :plant_name
          AND p.plant_id > 0
          AND i.timestamp BETWEEN '2024-12-01T00:00:00' AND '2025-12-02T00:00:00'
        GROUP BY i.timestamp
        ORDER BY i.timestamp;
    """)

    try:
        result = db.execute(query, {"plant_name": PLANT_NAME_CEL3})
        return [{"Timestamp": row[0], "Day_cap": row[1]} for row in result]
    except Exception as e:
        return {"error": str(e)}


@router.get("/Power+Date/", tags=["Database"])
def fetch_active_power(db: Session = Depends(get_db)):
    """
    Return timestamp and aggregated active power between 2 dates
    """
    query = text("""
        SELECT i.timestamp, SUM(i.active_power) AS total_active_power
        FROM public.inverter_data i
        JOIN public.device d ON d.device_id = i.device_id
        JOIN public.plant p ON p.plant_id = d.plant_id
        WHERE p.name = :plant_name
          AND p.plant_id > 0
          AND i.timestamp BETWEEN '2025-09-11T00:00:00' AND '2025-09-30T00:00:00'
        GROUP BY i.timestamp
        ORDER BY i.timestamp;
    """)

    try:
        result = db.execute(query, {"plant_name": PLANT_NAME_CEL3})
        return [{"Timestamp": row[0], "Active_power": row[1]} for row in result]
    except Exception as e:
        return {"error": str(e)}


@router.get("/Input_Power+Date/", tags=["Database"])
def fetch_input_power(db: Session = Depends(get_db)):
    """
    Return timestamp and aggregated active power between 2 dates
    """
    query = text("""
        SELECT i.timestamp, SUM(i.input_power) AS total_input_power
        FROM public.inverter_data i
        JOIN public.device d ON d.device_id = i.device_id
        JOIN public.plant p ON p.plant_id = d.plant_id
        WHERE p.name = :plant_name
          AND p.plant_id > 0
          AND i.timestamp BETWEEN '2025-02-18T00:00:00' AND '2025-02-19T00:00:00'
        GROUP BY i.timestamp
        ORDER BY i.timestamp;
    """)

    try:
        result = db.execute(query, {"plant_name": PLANT_NAME_CEL3})
        return [{"Timestamp": row[0], "Input_power": row[1]} for row in result]
    except Exception as e:
        return {"error": str(e)}


@router.get("/Weather+Date/", tags=["Database"])
def fetch_weather(db: Session = Depends(get_db)):
    """
    Return timestamp and irradiance between 2 dates
    """
    query = text("""
        SELECT w.timestamp, w.irradiance, w.pv_temperature, d.name AS dev_id
        FROM public.weather_data w
        JOIN public.device d ON d.device_id = w.device_id
        JOIN public.plant p ON p.plant_id = d.plant_id
        WHERE p.name = :plant_name
          AND p.plant_id > 0
          AND w.timestamp BETWEEN '2025-09-01T00:00:00' AND '2025-10-01T00:00:00'
        ORDER BY w.timestamp;
    """)

    try:
        result = db.execute(query, {"plant_name": PLANT_NAME_CEL3})
        return [{"Device": row[3], "Timestamp": row[0], "Irradiance": row[1], "Pv Temperature": row[2]} for row in result]
    except Exception as e:
        return {"error": str(e)}
