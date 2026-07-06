import os


client_key = os.getenv("CLIENT_KEY")
DPSIM_URL = os.getenv("DPSIM_URL", "http://dpsim-service:5000")

tags_metadata = [
    {"name": "User", "description": "Signing in"},
    {"name": "Schema", "description": "Regarding Database Schemas"},
    {"name": "Database", "description": "Database Transactions"},
    {"name": "Maintenance", "description": "Maintenance Page"},
    {"name": "Production", "description": "PV Production Pages"},
    {"name": "TSO", "description": "TSO related aspects"},
]

TSO_ALLOWED_POWER_TYPES = {"active", "reactive"}

# Profile-type label of the conventional balancing unit in the TSO datasets.
# Override with TSO_BALANCING_PROFILE_TYPE to match your data.
TSO_BALANCING_PROFILE_TYPE = os.getenv("TSO_BALANCING_PROFILE_TYPE", "BALANCING_UNIT")

TSO_PLOT_PROFILE_TYPES = {
    "active": ["LOAD", "PV", "WP", "CU PRODUCTION", TSO_BALANCING_PROFILE_TYPE],
    "reactive": ["LOAD", "COMPENSATOR"],
}

TSO_SPLIT_BY_COMPONENT = {
    "active": {"CU PRODUCTION"},
    "reactive": {"COMPENSATOR"},
}

TSO_DISPLAY_NAME_MAP = {
    "WP": "Wind Park",
    "PV": "Photovoltaic",
    "CU PRODUCTION": "Conventional Unit Production",
    "LOAD": "Load",
    "COMPENSATOR": "Compensator",
    TSO_BALANCING_PROFILE_TYPE: "Conventional Unit Production",
}

# DSO
DSO_ALLOWED_POWER_TYPES = {"active", "reactive"}

DSO_PLOT_PROFILE_TYPES = {
    "active": ["LOAD", "GEN"],
    "reactive": ["LOAD", "GEN"],
}

DSO_SPLIT_BY_COMPONENT: dict[str, set] = {
    "active": set(),
    "reactive": set(),
}

DSO_DISPLAY_NAME_MAP = {
    "LOAD": "Load",
    "GEN": "Generation",
}

tags_metadata.append({"name": "DSO", "description": "DSO related aspects"})
