# DEPRECATED after the normalization migration. The one-time copy of
# public.inverter_data_old → public.inverter_data is now performed inside
# digital_twin_backend/migration.sql. Kept here for reference; the queries
# below still point at public.inverter_data_old (the renamed legacy table)
# and remain functional for re-runs against any leftover legacy rows.
import os
import psycopg2
from psycopg2.extras import execute_values


BATCH_SIZE = 1000

MEASUREMENT_COLUMNS = [
    "inverter_state",
    "active_power",
    "day_cap",
    "reactive_power",
    "power_factor",
    "input_power",
    "efficiency",
    "u_ab",
    "u_bc",
    "u_ca",
    "u_a",
    "u_b",
    "u_c",
    "i_a",
    "i_b",
    "i_c",
    "frequency",
    "temperature",
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
    # Reads from public.inverter_data_old (the legacy table preserved by the
    # normalization migration). Live writers now target public.inverter_data
    # directly, so this script is only useful for backfilling leftover legacy
    # rows after the one-time copy in migration.sql.
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT d.device_id, d.name
            FROM public.device d
            JOIN public.inverter_data_old i ON i.dev_id = d.name
        """)
        return cur.fetchall()


def get_last_timestamp(conn, device_id):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT timestamp
            FROM public.inverter_data
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
            FROM public.inverter_data_old
            WHERE dev_id = %s
            ORDER BY collect_time ASC
            LIMIT %s
        """
        params = (dev_name, limit)
    else:
        query = f"""
            SELECT collect_time, {select_columns}
            FROM public.inverter_data_old
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
        INSERT INTO public.inverter_data ({columns_sql})
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
        print(f"Processed {inserted} rows into public.inverter_data.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
