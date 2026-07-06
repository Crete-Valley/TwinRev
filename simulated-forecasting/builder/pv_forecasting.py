import os
import psycopg2
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import sys
import logging
import pandas as pd
import pytz
from forecasting_client import EnergyForecastingClient

CHRONOS_MODEL_NAME = "chronos"
CHRONOS_MODEL_URI = "autogluon/chronos-2-small"

HISTORY_DAYS = 7
DEVICE_HORIZON_TICKS = 24

WEATHER_COLUMNS = [
    "AmbientTemperature",
    "Irradiation",
    "Irradiance",
    "PVTemperature",
    "WindSpeed",
]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_connection(config: Dict[str, Any]):
    try:
        return psycopg2.connect(
            host=config["db_host"],
            port=config["db_port"],
            dbname=config["db_name"],
            user=config["db_user"],
            password=config["db_password"],
        )
    except psycopg2.Error as e:
        logger.error(f"Failed to connect to database: {e}")
        raise


def power_source_for_kind(device_kind: str) -> Tuple[str, str]:
    """(table, value_column) for a device kind. Inverters live in inverter_data."""
    if device_kind == "inverter":
        return ("public.inverter_data", "active_power")
    return (f"public.{device_kind}_data", "value")


def prediction_table_for_kind(device_kind: str) -> str:
    """Inverter predictions go to pv_prediction (there is no inverter_prediction)."""
    if device_kind == "inverter":
        return "public.pv_prediction"
    return f"public.{device_kind}_prediction"


def get_plant_power_device_kinds(conn, plant_id: int) -> List[str]:
    """Distinct device_kind values for the plant's non-weather devices."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT device_kind
            FROM public.device
            WHERE plant_id = %s AND device_kind <> 'weather'
            ORDER BY device_kind
            """,
            (plant_id,),
        )
        return [row[0] for row in cur.fetchall()]


def get_all_plants(conn) -> List[Tuple[int, str, str]]:
    """Return (plant_id, plant_name, energy_type_name) for every plant."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.plant_id, p.name, e.name
            FROM public.plant p
            JOIN public.energy_type e ON e.id = p.energy_type_id
            WHERE p.plant_id > 0
              AND p.cel_id > 0
            ORDER BY p.plant_id
            """
        )
        return cur.fetchall()


def get_first_weather_device_for_plant(conn, plant_id: int) -> Optional[int]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT device_id FROM public.device
            WHERE plant_id = %s AND device_kind = 'weather'
            ORDER BY device_id
            LIMIT 1
            """,
            (plant_id,),
        )
        row = cur.fetchone()
        return row[0] if row else None


def get_all_power_devices(conn) -> List[Tuple[int, int, str]]:
    """Return (device_id, plant_id, device_kind) for non-weather devices."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT d.device_id, d.plant_id, d.device_kind
            FROM public.device d
            JOIN public.plant p ON p.plant_id = d.plant_id
            WHERE d.device_kind <> 'weather'
              AND p.plant_id > 0
              AND p.cel_id > 0
            ORDER BY d.plant_id, d.device_id
            """
        )
        return cur.fetchall()


def fetch_device_power_series(conn, device_id: int, device_kind: str,
                              history_start: datetime, anchor: datetime) -> Optional[pd.DataFrame]:
    """Pull (timestamp, power) for a single device based on its kind."""
    table, col = power_source_for_kind(device_kind)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT timestamp, {col}
            FROM {table}
            WHERE device_id = %s AND timestamp BETWEEN %s AND %s
            ORDER BY timestamp ASC
            """,
            (device_id, history_start, anchor),
        )
        rows = cur.fetchall()
    if not rows:
        return None
    return pd.DataFrame({
        "Timestamp": pd.to_datetime([row[0] for row in rows]),
        "Power": pd.to_numeric([row[1] for row in rows]).astype(float),
    })


def fetch_plant_power_series(conn, plant_id: int, device_kind: str,
                             history_start: datetime, anchor: datetime) -> Optional[pd.DataFrame]:
    """Sum power across the plant's devices, reading the table for device_kind."""
    table, col = power_source_for_kind(device_kind)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT t.timestamp, SUM(t.{col}) AS total
            FROM {table} t
            JOIN public.device d ON d.device_id = t.device_id
            WHERE d.plant_id = %s
              AND t.timestamp BETWEEN %s AND %s
            GROUP BY t.timestamp
            ORDER BY t.timestamp ASC
            """,
            (plant_id, history_start, anchor),
        )
        rows = cur.fetchall()
    if not rows:
        return None
    return pd.DataFrame({
        "Timestamp": pd.to_datetime([row[0] for row in rows]),
        "Power": pd.to_numeric([row[1] for row in rows]).astype(float),
    })


def fetch_weather_covariates(conn, weather_device_id: int,
                             history_start: datetime, anchor: datetime,
                             full_index: pd.DatetimeIndex) -> Dict[str, List[float]]:
    """Read weather_data for one weather device, align to the 5-min grid."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT timestamp, temperature, daily_iradiation, irradiance,
                   pv_temperature, wind_speed
            FROM public.weather_data
            WHERE device_id = %s AND timestamp BETWEEN %s AND %s
            ORDER BY timestamp
            """,
            (weather_device_id, history_start, anchor),
        )
        rows = cur.fetchall()
    if not rows:
        return {}
    df = pd.DataFrame(
        [row[1:] for row in rows],
        columns=WEATHER_COLUMNS,
        index=pd.to_datetime([row[0] for row in rows]),
        dtype=float,
    )
    aligned = (
        df.reindex(full_index)
        .interpolate(method="time", limit_direction="both")
        .fillna(0.0)
    )
    return {col: [float(v) for v in aligned[col].values] for col in WEATHER_COLUMNS}


def call_chronos(client: EnergyForecastingClient, model_uri: str,
                 series: pd.Series,
                 past_covariates: Dict[str, List[float]],
                 horizon: int) -> Optional[Dict[str, Any]]:
    try:
        return client.create_forecast(
            model_name=CHRONOS_MODEL_NAME,
            data={
                "timestamps": [t.isoformat() for t in series.index],
                "values": [float(v) for v in series.values],
            },
            horizon=horizon,
            model_uri=model_uri,
            past_covariates=past_covariates or None,
        )
    except Exception as e:
        logger.error(f"chronos forecast failed: {e}")
        return None


def _iter_forecast_rows(forecast: Dict[str, Any]):
    """Yield (timestamp, value, lower, upper) tuples from a forecast response."""
    predicted_values = forecast.get("forecast", [])
    predicted_timestamps = forecast.get("timestamps", [])
    ci = forecast.get("confidence_intervals") or {}
    lower_bounds = ci.get("lower", [])
    upper_bounds = ci.get("upper", [])
    if len(predicted_values) != len(predicted_timestamps):
        return
    for i, timestamp_str in enumerate(predicted_timestamps):
        try:
            ts = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00')).replace(tzinfo=None)
            value = max(0, round(float(predicted_values[i]), 3))
            lower = max(0, round(float(lower_bounds[i]), 3)) if i < len(lower_bounds) else None
            upper = max(0, round(float(upper_bounds[i]), 3)) if i < len(upper_bounds) else None
            if lower is not None and lower < 1 and value < 1:
                value, lower, upper = 0, 0, 0
            yield ts, value, lower, upper
        except (ValueError, IndexError) as e:
            logger.error(f"Error parsing forecast row {i}: {e}")
            continue


def upsert_plant_forecast(conn, plant_id: int, forecast: Dict[str, Any]) -> int:
    if not forecast or "forecast" not in forecast:
        logger.error(f"Invalid forecast response for plant {plant_id}")
        return 0
    rows_affected = 0
    with conn.cursor() as cur:
        for ts, value, lower, upper in _iter_forecast_rows(forecast):
            cur.execute(
                """
                INSERT INTO public.plant_forecast (timestamp, plant_id, value, lower, upper)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (timestamp, plant_id) DO UPDATE
                    SET value = EXCLUDED.value,
                        lower = EXCLUDED.lower,
                        upper = EXCLUDED.upper
                """,
                (ts, plant_id, value, lower, upper),
            )
            rows_affected += 1
    conn.commit()
    return rows_affected


def upsert_device_predictions(conn, device_id: int, prediction_table: str,
                              forecast: Dict[str, Any]) -> int:
    if not forecast or "forecast" not in forecast:
        logger.error(f"Invalid forecast response for device {device_id}")
        return 0
    rows_affected = 0
    with conn.cursor() as cur:
        for ts, value, lower, upper in _iter_forecast_rows(forecast):
            cur.execute(
                f"""
                INSERT INTO {prediction_table} (timestamp, device_id, value, lower, upper)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (timestamp, device_id) DO UPDATE
                    SET value = EXCLUDED.value,
                        lower = EXCLUDED.lower,
                        upper = EXCLUDED.upper
                """,
                (ts, device_id, value, lower, upper),
            )
            rows_affected += 1
    conn.commit()
    return rows_affected


def _build_anchor_grid() -> Tuple[datetime, datetime, pd.DatetimeIndex]:
    athens = pytz.timezone("Europe/Athens")
    now_athens = datetime.now(athens).replace(tzinfo=None)
    rounded = now_athens.replace(minute=0, second=0, microsecond=0)
    anchor = rounded if now_athens.minute >= 13 else rounded - timedelta(hours=1)
    history_start = anchor - timedelta(days=HISTORY_DAYS)
    full_index = pd.date_range(start=history_start, end=anchor, freq="5min")
    return history_start, anchor, full_index


def ticks_until_end_of_next_day(anchor: datetime, step_minutes: int = 5) -> int:
    """Number of 5-minute steps from the anchor to the end of the next day (the
    midnight that closes tomorrow), so the forecast always reaches tomorrow's end
    regardless of when in the day it runs."""
    end_of_next_day = anchor.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=2)
    return int((end_of_next_day - anchor) / timedelta(minutes=step_minutes))


def _series_from(power_df: pd.DataFrame, full_index: pd.DatetimeIndex) -> pd.Series:
    return (
        power_df.set_index("Timestamp")["Power"]
        .reindex(full_index)
        .interpolate(method="time", limit_direction="both")
        .fillna(0.0)
    )


def run_plant_forecasts(conn, client: EnergyForecastingClient, model_uri: str) -> int:
    history_start, anchor, full_index = _build_anchor_grid()
    horizon = ticks_until_end_of_next_day(anchor)
    plants = get_all_plants(conn)
    logger.info(f"Plant-level forecasting: {len(plants)} plants, horizon {horizon} ticks to end of next day")

    total = 0
    successes = 0
    for plant_id, plant_name, energy_type in plants:
        kinds = get_plant_power_device_kinds(conn, plant_id)
        if not kinds:
            logger.warning(f"plant {plant_id} ({plant_name}, {energy_type}): no power devices; skipping")
            continue
        if len(kinds) > 1:
            print(f"ERROR: plant {plant_id} ({plant_name}, {energy_type}) has mixed device kinds {kinds}; skipping")
            continue
        device_kind = kinds[0]

        power_df = fetch_plant_power_series(conn, plant_id, device_kind, history_start, anchor)
        if power_df is None or power_df.empty:
            logger.warning(f"plant {plant_id} ({plant_name}, {energy_type}, {device_kind}): no power history; skipping")
            continue

        series = _series_from(power_df, full_index)

        past_covariates: Dict[str, List[float]] = {}
        weather_device_id = get_first_weather_device_for_plant(conn, plant_id)
        if weather_device_id is not None:
            past_covariates = fetch_weather_covariates(
                conn, weather_device_id, history_start, anchor, full_index
            )

        forecast = call_chronos(client, model_uri, series, past_covariates, horizon)
        if not forecast:
            logger.error(f"plant {plant_id} ({plant_name}): forecast failed")
            continue

        rows = upsert_plant_forecast(conn, plant_id, forecast)
        logger.info(f"plant {plant_id} ({plant_name}, {energy_type}): upserted {rows} plant_forecast rows")
        total += rows
        successes += 1

    logger.info(f"Plant-level forecasting done: {successes}/{len(plants)} plants, {total} rows")
    return total


def run_device_forecasts(conn, client: EnergyForecastingClient, model_uri: str,
                         horizon: int = DEVICE_HORIZON_TICKS) -> int:
    history_start, anchor, full_index = _build_anchor_grid()
    devices = get_all_power_devices(conn)
    logger.info(f"Device-level forecasting: {len(devices)} power-producing devices")

    weather_cache: Dict[int, Dict[str, List[float]]] = {}
    total = 0
    successes = 0

    for device_id, plant_id, device_kind in devices:
        prediction_table = prediction_table_for_kind(device_kind)

        power_df = fetch_device_power_series(
            conn, device_id, device_kind, history_start, anchor
        )
        if power_df is None or power_df.empty:
            logger.warning(f"device {device_id} ({device_kind}): no power history; skipping")
            continue

        series = _series_from(power_df, full_index)

        if plant_id not in weather_cache:
            wd_id = get_first_weather_device_for_plant(conn, plant_id)
            weather_cache[plant_id] = (
                fetch_weather_covariates(conn, wd_id, history_start, anchor, full_index)
                if wd_id is not None else {}
            )
        past_covariates = weather_cache[plant_id]

        forecast = call_chronos(client, model_uri, series, past_covariates, horizon)
        if not forecast:
            logger.error(f"device {device_id} ({device_kind}): forecast failed")
            continue

        rows = upsert_device_predictions(conn, device_id, prediction_table, forecast)
        logger.info(f"device {device_id} ({device_kind}): upserted {rows} rows into {prediction_table}")
        total += rows
        successes += 1

    logger.info(f"Device-level forecasting done: {successes}/{len(devices)} devices, {total} rows")
    return total


def load_env_config() -> Dict[str, Any]:
    return {
        "db_host": os.environ["DB_HOST"],
        "db_port": int(os.environ["DB_PORT"]),
        "db_name": os.environ["DB_NAME"],
        "db_user": os.environ["DB_USER"],
        "db_password": os.environ["DB_PASSWORD"],
        "forecasting_api_endpoint": os.environ["FORECASTING_API_ENDPOINT"],
        "forecasting_api_key": os.environ["FORECASTING_API_KEY"],
        "api_timeout": int(os.environ.get("API_TIMEOUT", "60")),
        "api_retry_attempts": int(os.environ.get("API_RETRY_ATTEMPTS", "3")),
        "hours_to_backfill": int(os.environ.get("HOURS_TO_BACKFILL", "2")),
    }


def main():
    config = load_env_config()
    conn = None
    try:
        conn = get_connection(config)
        logger.info("Connected to database")

        client = EnergyForecastingClient(
            base_url=config["forecasting_api_endpoint"],
            token=config["forecasting_api_key"],
        )

        try:
            health = client.health()
            logger.info(f"Forecasting API health: {health.get('status', 'unknown')}")
        except Exception as e:
            logger.error(f"Forecasting API health check failed: {e}; aborting")
            return

        try:
            load_result = client.load_model(CHRONOS_MODEL_NAME, uri=CHRONOS_MODEL_URI)
            logger.info(f"Loaded {CHRONOS_MODEL_NAME}: {load_result.get('status', load_result)}")
        except Exception as e:
            logger.error(f"Failed to load model: {e}; aborting")
            return

        run_plant_forecasts(conn, client, CHRONOS_MODEL_URI)
        run_device_forecasts(conn, client, CHRONOS_MODEL_URI)

    except Exception as e:
        logger.error(f"Energy forecasting job failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    main()
