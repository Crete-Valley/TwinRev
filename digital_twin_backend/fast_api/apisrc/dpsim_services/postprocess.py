import json
import math
import os

# Bus/line topology of the simulated transmission grid. The real Crete
# topology is proprietary and NOT distributed with this repository — the
# bundled dpsim_assets/tso_topology.json is a placeholder. Supply your own
# (matching your DPsim network archives) to get per-bus/per-line results.
_TOPOLOGY_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "dpsim_assets",
    "tso_topology.json",
)

DEFAULT_BASE_KV = 150.0


def _load_topology():
    try:
        with open(_TOPOLOGY_FILE) as f:
            topo = json.load(f)
    except (OSError, ValueError):
        return {"base_kv": DEFAULT_BASE_KV, "buses": {}, "lines": []}
    return {
        "base_kv": topo.get("base_kv", DEFAULT_BASE_KV),
        "buses": topo.get("buses", {}),
        "lines": topo.get("lines", []),
    }

def postprocess_dpsim_results(raw_payload):
    topology = _load_topology()
    BASE_KV = topology["base_kv"]
    raw = raw_payload.get("result", raw_payload)
    if not isinstance(raw, dict):
        return {"time": [], "buses": {}, "lines": {}}

    def round_output(obj, decimals=4):
        if isinstance(obj, float):
            return round(obj, decimals)
        if isinstance(obj, list):
            return [round_output(x, decimals) for x in obj]
        if isinstance(obj, dict):
            return {k: round_output(v, decimals) for k, v in obj.items()}
        return obj

    def get_series(key):
        values = raw.get(key)
        if not isinstance(values, list):
            return None
        try:
            return [float(v) for v in values]
        except Exception:
            return None

    def build_bus(re_key, im_key):
        re_vals = get_series(re_key)
        im_vals = get_series(im_key)
        if re_vals is None or im_vals is None:
            return None

        v_abs = [math.hypot(re, im) for re, im in zip(re_vals, im_vals)]
        v_kv = [v / 1000.0 for v in v_abs]
        v_pu = [v / BASE_KV for v in v_kv]

        theta_deg = [math.degrees(math.atan2(im, re)) for re, im in zip(re_vals, im_vals)]

        return {
            "v_kv": v_kv,
            "v_pu": v_pu,
            "theta_deg": theta_deg,
        }

    def has_line_prefix(prefix):
        required = [
            f"{prefix}_I_0.im",
            f"{prefix}_I_0.re",
            f"{prefix}_I_1.im",
            f"{prefix}_I_1.re",
            f"{prefix}_P_0",
            f"{prefix}_P_1",
            f"{prefix}_Q_0",
            f"{prefix}_Q_1",
        ]
        return all(k in raw for k in required)

    def pick_line_prefix(prefixes):
        for prefix in prefixes:
            if has_line_prefix(prefix):
                return prefix
        return None

    def build_line(prefix, i_rated_ka, parallel_count=1):
        i0_im = get_series(f"{prefix}_I_0.im")
        i0_re = get_series(f"{prefix}_I_0.re")
        i1_im = get_series(f"{prefix}_I_1.im")
        i1_re = get_series(f"{prefix}_I_1.re")
        p0 = get_series(f"{prefix}_P_0")
        p1 = get_series(f"{prefix}_P_1")
        q0 = get_series(f"{prefix}_Q_0")
        q1 = get_series(f"{prefix}_Q_1")

        if any(x is None for x in [i0_im, i0_re, i1_im, i1_re, p0, p1, q0, q1]):
            return None

        i0_a = [math.hypot(re, im) for re, im in zip(i0_re, i0_im)]
        i1_a = [math.hypot(re, im) for re, im in zip(i1_re, i1_im)]

        i0_ka = [i / 1000.0 for i in i0_a]
        i1_ka = [i / 1000.0 for i in i1_a]

        loading_from_pct = [(i / i_rated_ka) * 100.0 for i in i0_ka]
        loading_to_pct = [(i / i_rated_ka) * 100.0 for i in i1_ka]
        loading_pct = [max(a, b) for a, b in zip(loading_from_pct, loading_to_pct)]

        return {
            "p_from_mw": [v / 1_000_000.0 for v in p0],
            "p_to_mw": [v / 1_000_000.0 for v in p1],
            "q_from_mvar": [v / 1_000_000.0 for v in q0],
            "q_to_mvar": [v / 1_000_000.0 for v in q1],
            "i_from_ka": i0_ka,
            "i_to_ka": i1_ka,
            "loading_from_pct": loading_from_pct,
            "loading_to_pct": loading_to_pct,
            "loading_pct": loading_pct,
            "i_rated_ka": i_rated_ka,
            "parallel_count": parallel_count,
        }

    bus_specs = topology["buses"]
    line_specs = topology["lines"]

    processed = {
        "time": raw.get("time", []),
        "buses": {},
        "lines": {},
    }
    if not bus_specs and not line_specs:
        processed["topology_note"] = (
            "dpsim_assets/tso_topology.json contains no buses/lines (the real "
            "grid topology is proprietary and not distributed). Raw simulation "
            "results were produced, but no per-bus/per-line series can be built."
        )

    for bus_name, spec in bus_specs.items():
        bus_data = build_bus(spec["re"], spec["im"])
        if bus_data is not None:
            processed["buses"][bus_name] = bus_data

    for spec in line_specs:
        prefix = pick_line_prefix(spec["prefixes"])
        if prefix is None:
            continue

        line_data = build_line(
            prefix=prefix,
            i_rated_ka=spec["i_rated_ka"],
            parallel_count=spec["parallel_count"],
        )
        if line_data is not None:
            line_data["source_prefix"] = prefix
            processed["lines"][spec["name"]] = line_data

    return round_output(processed)
