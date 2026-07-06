"""
Configuration for the optimization model.

This module centralizes runtime parameters, file paths, and required
resource field definitions. It is intended to be imported by other
modules (not executed directly).

Contents:
- Runtime parameters: cell name, bidding horizon, reserves settings, solver.
- Paths: input Excel file and output result files.
- Required labels for market prices.
- Required fields by resource type (validation dictionaries).

Notes:
- Update CELL_NAME to switch between different input datasets.
- SYSTEM_RESERVES_PARTICIPATION must be consistent across all resources
  (mixed participation is not supported).
- Paths are relative to the project root.
"""
from pathlib import Path

# Runtime parameters
CELL_NAME = "cell_3" # CHANGED IT TO CEL 3 BECAUSE THIS IS THE ONLY ONE WITH DATA
BIDDING_TIME = 24
# Only SYSTEM_RESERVES_PARTICIPATION or SYSTEM_FLEXIBILITY_PARTICIPATION set to 1
SYSTEM_RESERVES_PARTICIPATION = 0
SYSTEM_FLEXIBILITY_PARTICIPATION = 1
RATIO_UPWARD_DOWNWARD_RESERVE = 2
SOLVER = "highs"

# Paths
INPUT_FILE = Path("data_inputs") / f"data_inputs_{CELL_NAME}.xlsx"
INPUT_FILE_JSON = Path("data_inputs") / f"data_inputs_{CELL_NAME}.json"
OUTPUT_FOLDER = Path(__file__).resolve().parent / "data_outputs"
# OUTPUT_FOLDER = Path("data_outputs")
OUTPUT_WITH_RESERVES = OUTPUT_FOLDER / "results_with_reserves.xlsx"
OUTPUT_WITH_RESERVES_DEBUG = OUTPUT_FOLDER / "results_with_reserves_debugging.xlsx"
OUTPUT_WITH_FLEXIBILITY = OUTPUT_FOLDER / "results_with_flexibility.xlsx"
OUTPUT_WITH_FLEXIBILITY_DEBUG = OUTPUT_FOLDER / "results_with_flexibility_debugging.xlsx"
OUTPUT_NO_RESERVES = OUTPUT_FOLDER / "results_no_reserves.xlsx"
OUTPUT_NO_RESERVES_DEBUG = OUTPUT_FOLDER / "results_no_reserves_debugging.xlsx"

REQUIRED_LABELS_PRICES = [
    "Energy",
    "Secondary band",
    "Upward activation",
    "Downward activation",
    "Ratio up",
    "Ratio down",
    "Gas",
    "Biomass"
]
# Fields required to be filled in the excel input file for each resource type
REQUIRED_FIELDS_BY_TYPE = {
    "PV": ["profile"],
    "WindGenerator": ["profile", "max_power", "wind_begin", "wind_max", "wind_shutdown"],
    "Battery": ["max_capacity", "max_power_charging", "max_power_discharging", "efficiency_ch", "efficiency_dis"],
    "CHP": ["max_power", "efficiency_heat", "efficiency_electricity"],
    "Electrolyzer": ["max_power", "efficiency"],
    "FuelCell": ["max_power", "efficiency"],
    "HydrogenStorage": ["max_capacity", "max_power", "efficiency_ch", "efficiency_dis"],
    "HeatPump": ["load", "max_power", "COP", "flexibility_range"],
    "ElectricalLoad": ["profile_electrical_load"],
    "ThermalLoad": ["profile_thermal_load"],
    "HydrogenLoad": ["profile_hydrogen_load"],
    "GeoExchange": ["max_power", "flexibility_range", "efficiency_heat"],
    "Boiler": ["max_power", "efficiency_heat"]
}

# Excel sheet names - read_inputs.py
PARAM_SHEET = "Energy resources"
SHEET_ELECTRICAL_LOADS = "Electrical loads"
SHEET_THERMAL_LOADS = "Thermal loads"
SHEET_HYDROGEN_LOADS = "Hydrogen loads"
SHEET_PV = "PV generation"
SHEET_WIND = "Wind generation"
SHEET_PRICES = "Prices"
SHEET_HP = "HP loads"


# Column mapping for the parameters sheet - read_inputs.py
COLUMN_MAPPING = {
    "Maximum capacity": "max_capacity",
    "Minimum capacity": "min_capacity",
    "Initial SOC": "initial_SOC",
    "Maximum power": "max_power",
    "Maximum charging power": "max_power_charging",
    "Maximum discharging power": "max_power_discharging",
    "COP": "COP",
    "Efficiency": "efficiency",
    "Efficiency heat": "efficiency_heat",
    "Efficiency electricity": "efficiency_electricity",
    "Efficiency charging": "efficiency_ch",
    "Efficiency discharging": "efficiency_dis",
    "Reserves participation": "ReservesParticipation",
    "Losses": "losses",
    "Wind begin": "wind_begin",
    "Wind max": "wind_max",
    "Wind shutdown": "wind_shutdown",
    "Flexibility range": "flexibility_range"
}