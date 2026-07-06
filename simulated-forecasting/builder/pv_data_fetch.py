import os
import math
import pytz
import psycopg2
from datetime import datetime, timedelta, timezone


def simulated_solar_panel_watts(max_watts: float, timestamp) -> float:
    athens = pytz.timezone("Europe/Athens")

    if isinstance(timestamp, datetime):
        if timestamp.tzinfo is None:
            timestamp = athens.localize(timestamp)
        ts = timestamp.timestamp()
        dt = timestamp.astimezone(athens)
    else:
        ts = float(timestamp)
        dt = datetime.fromtimestamp(ts, tz=athens)

    hour = dt.hour + dt.minute / 60.0
    day_of_year = dt.timetuple().tm_yday

    seasonal_strength = 0.75 + 0.25 * math.sin(
        2 * math.pi * (day_of_year - 80) / 365.25
    )

    daylight_hours = 11 + 2 * math.sin(
        2 * math.pi * (day_of_year - 80) / 365.25
    )

    solar_noon = 13.5
    sunrise = solar_noon - daylight_hours / 2
    sunset = solar_noon + daylight_hours / 2

    # --------------------------------------------------
    # Sun position curve
    # --------------------------------------------------

    if hour < sunrise or hour > sunset:
        return 0.0

    daylight_progress = (hour - sunrise) / daylight_hours

    sun_intensity = math.sin(math.pi * daylight_progress) ** 1.5

    # --------------------------------------------------
    # Deterministic cloud simulation
    # --------------------------------------------------

    days = ts / 86400.0

    clouds = (
        0.85
        + 0.10 * math.sin(2 * math.pi * days / 5.0 + 1.1)
        + 0.05 * math.sin(2 * math.pi * days / 2.3 + 0.7)
    )

    clouds = max(0.2, min(1.0, clouds))

    # Final output
    power = max_watts * seasonal_strength * sun_intensity * clouds

    return round(power, 2)

def simulated_city_consumption_watts(max_watts: float, timestamp) -> float:
    """
    Deterministic rough small-city energy consumption simulation.

    Parameters
    ----------
    max_watts : float
        Approximate peak city demand.
    timestamp : datetime | int | float
        datetime object or unix timestamp seconds.

    Returns
    -------
    float
        Simulated instantaneous city consumption in watts.
    """

    # Normalize timestamp
    if isinstance(timestamp, datetime):
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        ts = timestamp.timestamp()
    else:
        ts = float(timestamp)

    dt = datetime.fromtimestamp(ts, tz=timezone.utc)

    hour = dt.hour + dt.minute / 60.0
    weekday = dt.weekday()  # 0 = Monday
    day_of_year = dt.timetuple().tm_yday

    # --------------------------------------------------
    # Base load
    # --------------------------------------------------

    base = 0.45

    # --------------------------------------------------
    # Daily usage profile
    # --------------------------------------------------
    #
    # Typical city behavior:
    # - low overnight
    # - morning ramp
    # - daytime business usage
    # - evening residential peak
    #

    morning_peak = 0.20 * math.exp(-((hour - 8) ** 2) / 6)

    daytime_usage = 0.15 * math.exp(-((hour - 13) ** 2) / 18)

    evening_peak = 0.35 * math.exp(-((hour - 19) ** 2) / 10)

    overnight_drop = -0.12 * math.exp(-((hour - 3) ** 2) / 8)

    daily_profile = (
        morning_peak
        + daytime_usage
        + evening_peak
        + overnight_drop
    )

    # --------------------------------------------------
    # Weekday vs weekend
    # --------------------------------------------------

    if weekday < 5:
        # Weekdays slightly higher due to business activity
        weekday_factor = 1.05
    else:
        # Weekends slightly lower daytime demand
        weekday_factor = 0.93

    # --------------------------------------------------
    # Seasonal demand
    # --------------------------------------------------
    #
    # Higher in:
    # - winter (heating)
    # - summer (cooling)
    #

    seasonal = (
        0.90
        + 0.12 * math.cos(2 * math.pi * day_of_year / 365.25)
        + 0.10 * math.cos(4 * math.pi * day_of_year / 365.25)
    )

    # --------------------------------------------------
    # Slow random-looking infrastructure variation
    # --------------------------------------------------

    days = ts / 86400.0

    variation = (
        0.03 * math.sin(2 * math.pi * days / 9.0 + 1.3)
        + 0.02 * math.sin(2 * math.pi * days / 2.7 + 0.8)
    )

    # --------------------------------------------------
    # Final normalized load
    # --------------------------------------------------

    load_factor = (
        (base + daily_profile + variation)
        * weekday_factor
        * seasonal
    )

    # Clamp
    load_factor = max(0.15, min(1.0, load_factor))

    return round(max_watts * load_factor, 2)

def simulated_geothermal_watts(max_watts: float, timestamp) -> float:
    athens = pytz.timezone("Europe/Athens")

    if isinstance(timestamp, datetime):
        if timestamp.tzinfo is None:
            timestamp = athens.localize(timestamp)
        dt = timestamp.astimezone(athens)
    else:
        dt = datetime.fromtimestamp(float(timestamp), tz=athens)

    hour = dt.hour + dt.minute / 60.0
    day_of_year = dt.timetuple().tm_yday

    annual_temp = 19 - 7 * math.cos(2 * math.pi * (day_of_year - 30) / 365.25)
    daily_temp = 2 * math.sin(2 * math.pi * (hour - 9) / 24)
    temperature = annual_temp + daily_temp

    if temperature > 26:
        thermal_demand = min(1.0, (temperature - 26) / 8.0)
    elif temperature < 20:
        thermal_demand = min(1.0, (20 - temperature) / 12.0) * 0.4
    else:
        thermal_demand = 0.0

    if 6 <= hour <= 23:
        occupancy = 0.05 + 0.95 * math.sin(math.pi * (hour - 6) / 17)
    else:
        occupancy = 0.05

    baseline = 0.005 + 0.01 * occupancy
    demand_factor = baseline + (1 - baseline) * thermal_demand * occupancy

    return round(max_watts * demand_factor, 2)


def simulated_wind_turbine_watts(max_watts: float, timestamp) -> float:
    if isinstance(timestamp, datetime):
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        ts = timestamp.timestamp()
    else:
        ts = float(timestamp)

    hour = ts / 3600.0
    day = hour / 24.0
    year = day / 365.25

    seasonal = 0.55 + 0.25 * math.sin(2 * math.pi * year)
    weekly   = 0.20 * math.sin(2 * math.pi * day / 7.0 + 1.7)
    daily    = 0.10 * math.sin(2 * math.pi * hour / 24.0 + 0.4)
    gusts    = 0.08 * math.sin(2 * math.pi * hour / 3.0 + 2.1)

    wind_factor = seasonal + weekly + daily + gusts
    wind_factor = max(0.0, min(1.0, wind_factor))

    power_factor = wind_factor ** 3

    return max_watts * power_factor


def get_connection():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", 5432)),
        dbname=os.environ.get("DB_NAME", "postgres"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", ""),
    )


def get_all_devices(conn):
    """Get all simulated devices with their energy type. Inverter and weather
    devices are skipped: their data comes from the real retriever and the
    weather sync, not the simulator."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT d.device_id, e.name
            FROM public.device d
            JOIN public.plant p ON d.plant_id = p.plant_id
            JOIN public.energy_type e ON p.energy_type_id = e.id
            WHERE p.plant_id > 0
              AND p.cel_id > 0
              AND d.device_kind NOT IN ('inverter', 'weather')
        """)
        return cur.fetchall()  # Returns list of (device_id, energy_type_name)


def generate_timestamps():
    athens = pytz.timezone("Europe/Athens")
    now = datetime.now(athens)

    # Snap current time down to nearest 5-minute mark
    minute = (now.minute // 5) * 5
    now_snapped = now.replace(minute=minute, second=0, microsecond=0)

    start = now_snapped - timedelta(hours=int(os.environ.get("HOURS_TO_BACKFILL", "2")))

    ts = start
    timestamps = []
    while ts <= now_snapped:
        timestamps.append(ts)
        ts += timedelta(minutes=5)

    return timestamps


PV_MAX_WATTS = 2000
PV_CURTAILMENT = 0.70


def apply_curtailment(value, max_watts):
    return min(value, max_watts * PV_CURTAILMENT)


def calculate_device_value(energy_type, timestamp):
    energy_type = energy_type.lower()
    if energy_type == 'pv':
        value = simulated_solar_panel_watts(PV_MAX_WATTS, timestamp)
        return apply_curtailment(value, PV_MAX_WATTS)
    elif energy_type == 'wind':
        return simulated_wind_turbine_watts(1500, timestamp)
    elif energy_type == 'geothermal':
        return simulated_geothermal_watts(1000, timestamp)
    else:
        return simulated_city_consumption_watts(4000, timestamp)


def upsert_data(conn, devices, timestamps, overwrite=True):
    """
    Insert or update energy data for all devices.

    Parameters:
        conn: psycopg2 connection object
        devices: list of tuples (device_id, energy_type_name)
        timestamps: list of timestamps
        overwrite: bool, if True existing data will be overwritten, 
                   if False existing data will be ignored
    """
    with conn.cursor() as cur:
        for device_id, energy_type in devices:
            data_table = f"public.{energy_type}_data"
            for ts in timestamps:
                value = calculate_device_value(energy_type, ts)
                
                if overwrite:
                    # If overwrite is True, update existing rows
                    cur.execute(f"""
                        INSERT INTO {data_table} (timestamp, device_id, value)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (timestamp, device_id)
                        DO UPDATE SET value = EXCLUDED.value
                    """, (ts.replace(tzinfo=None), device_id, value))
                else:
                    # If overwrite is False, do nothing on conflict
                    cur.execute(f"""
                        INSERT INTO {data_table} (timestamp, device_id, value)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (timestamp, device_id) DO NOTHING
                    """, (ts.replace(tzinfo=None), device_id, value))

    conn.commit()


def main():
    conn = get_connection()
    try:
        devices = get_all_devices(conn)

        if not devices:
            print("No devices found.")
            return

        timestamps = generate_timestamps()

        upsert_data(conn, devices, timestamps)

        print(f"Upserted data for {len(devices)} devices and {len(timestamps)} timestamps.")

    finally:
        conn.close()


if __name__ == "__main__":
    main()