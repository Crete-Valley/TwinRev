import psycopg2
from datetime import datetime
import pytz
from dotenv import load_dotenv
import os

def fetch_pv_data():
    """
    Reads PV table and returns two arrays: energy_resources e pv_generation
    """
    load_dotenv()
    HOST = os.getenv("DB_POST_HOST")
    PORT = os.getenv("DB_POST_PORT", 5432)  #ADDITION OF PORT
    DATABASE = os.getenv("DB_POST_NAME")
    USER = os.getenv("DB_POST_USER")
    PASSWORD = os.getenv("DB_POST_PASSWORD")

    athens_tz = pytz.timezone("Europe/Athens")
    now_athens = datetime.now(athens_tz)
    current_date = now_athens.replace(hour=0, minute=0, second=0, microsecond=0).replace(tzinfo=None)

    query = """
        SELECT cel, array_agg(total_value ORDER BY ts) AS q50
        FROM (
            SELECT p.cel_id AS cel,
                   pf.timestamp AS ts,
                   SUM(pf.value) AS total_value
            FROM public.plant_forecast pf
            JOIN public.plant p ON p.plant_id = pf.plant_id
            JOIN public.energy_type e ON e.id = p.energy_type_id
            WHERE e.name = 'pv'
            AND p.plant_id > 0
            AND p.cel_id > 0
            AND pf.timestamp > %(date)s
            AND pf.timestamp <= %(date)s + INTERVAL '24 hours'
            AND EXTRACT(MINUTE FROM pf.timestamp) = 0
            GROUP BY p.cel_id, pf.timestamp
        ) hourly
        GROUP BY cel
        HAVING COUNT(*) = 24;
        """

    conn = psycopg2.connect(
        host=HOST,
        database=DATABASE,
        port=PORT,  #ADDITION OF PORT
        user=USER,
        password=PASSWORD,
    )
    
    cur = conn.cursor()
    cur.execute(query, {"date": current_date}) #CHANGED QUERY TO REFLECT DAILY FORECASTS 
    rows = cur.fetchall()

    energy_resources = []
    pv_generation = []

    for row in rows:
        cel, q50 = row

        # Energy resources
        energy_obj = {
            "ResourceType": "PV",
            "ResourceNumber": cel,
            "Reserves participation": 1,
            "Maximum capacity": " - ",
            "Minimum capacity": " - ",
            "Initial SOC": " - ",
            "Maximum power": " - ",
            "Maximum charging power": " - ",
            "Maximum discharging power": " - ",
            "COP": "-",
            "Efficiency": " - ",
            "Efficiency heat": " - ",
            "Efficiency electricity": " - ",
            "Efficiency charging": " - ",
            "Efficiency discharging": " - ",
            "Losses": "-",
            "Wind begin": " - ",
            "Wind max": " - ",
            "Wind shutdown": "-",
            "Flexibility range": "-"
        }
        energy_resources.append(energy_obj)

        # PV generation
        generation_entry = {"ResourceNumber": cel}
        for hour, value in enumerate(q50):
            generation_entry[str(hour)] = value
        pv_generation.append(generation_entry)

    cur.close()
    conn.close()
    return energy_resources, pv_generation

# Test the function directly
if __name__ == "__main__":
    fetch_pv_data()