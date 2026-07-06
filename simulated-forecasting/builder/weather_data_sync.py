# DEPRECATED after the normalization migration. See inverter_data_sync.py for
# context. Queries still point at public.weather_data_old.
import os
import psycopg2
from psycopg2.extras import execute_values


BATCH_SIZE = 100

MEASUREMENT_COLUMNS = [
    "device_state",
    "irradiance",
    "daily_iradiation",
    "temperature",
    "wind_speed",
    "wind_direction",
    "pv_temperature",
]


def get_connection():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", 5432)),
        dbname=os.environ.get("DB_NAME", "postgres"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", ""),
    )


def get_devices(conn):
    # See comment in inverter_data_sync.py: this bridges legacy public.*_old
    # (preserved by the normalization migration) into staging.*.
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT d.device_id, d.name
            FROM public.device d
            JOIN public.weather_data_old w ON w.dev_id = d.name
        """)
        return cur.fetchall()


def get_last_timestamp(conn, device_id):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT timestamp
            FROM public.weather_data
            WHERE device_id = %s
            ORDER BY timestamp DESC
            LIMIT 1
        """, (device_id,))
        row = cur.fetchone()
        return row[0] if row else None


def fetch_batch(conn, dev_name, last_timestamp, limit):
    select_columns = ", ".join(MEASUREMENT_COLUMNS)
    if last_timestamp is None:
        query = f"""
            SELECT collect_time, {select_columns}
            FROM public.weather_data_old
            WHERE dev_id = %s
            ORDER BY collect_time ASC
            LIMIT %s
        """
        params = (dev_name, limit)
    else:
        query = f"""
            SELECT collect_time, {select_columns}
            FROM public.weather_data_old
            WHERE dev_id = %s AND collect_time > %s
            ORDER BY collect_time ASC
            LIMIT %s
        """
        params = (dev_name, last_timestamp, limit)
    with conn.cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()


def insert_batch(conn, rows):
    target_columns = ["timestamp", "device_id"] + MEASUREMENT_COLUMNS
    columns_sql = ", ".join(target_columns)
    update_sql = ", ".join(f"{c} = EXCLUDED.{c}" for c in MEASUREMENT_COLUMNS)
    query = f"""
        INSERT INTO public.weather_data ({columns_sql})
        VALUES %s
        ON CONFLICT (timestamp, device_id) DO UPDATE SET {update_sql}
    """
    with conn.cursor() as cur:
        execute_values(cur, query, rows)


def sync_device(conn, device_id, dev_name):
    last_timestamp = get_last_timestamp(conn, device_id)
    inserted = 0

    while True:
        rows = fetch_batch(conn, dev_name, last_timestamp, BATCH_SIZE)
        if not rows:
            break

        enriched = [(r[0], device_id) + r[1:] for r in rows]
        insert_batch(conn, enriched)
        conn.commit()

        last_timestamp = rows[-1][0]
        inserted += len(rows)

    return inserted


def sync(conn):
    devices = get_devices(conn)
    total_inserted = 0
    for device_id, dev_name in devices:
        total_inserted += sync_device(conn, device_id, dev_name)
    return total_inserted


def main():
    conn = get_connection()
    try:
        inserted = sync(conn)
        print(f"Processed {inserted} rows into public.weather_data.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
