"""
JsonDataLoader module
=====================

Reads the same structure previously loaded from Excel sheets, but directly from
a nested JSON object that follows the format you posted.

It validates:
- Required columns per resource type (see config.REQUIRED_FIELDS_BY_TYPE).
- Profile lengths match the configured bidding horizon.
- Price labels exist (config.REQUIRED_LABELS_PRICES), lengths are consistent,
  and match the bidding horizon.

Raises:
- DataLoadingError, PriceValidationError, ResourceReadingError
  for recoverable, user-actionable input issues.
"""

import numpy as np
import pandas as pd

from project.helper.helper import log_and_print
from project.helper.exceptions import DataLoadingError, PriceValidationError, ResourceReadingError
from project.config import (
    REQUIRED_LABELS_PRICES,
    REQUIRED_FIELDS_BY_TYPE,
    COLUMN_MAPPING,   # keep same mapping if you used it in Excel version
)

class JsonDataLoader:
    """
    Load and validate input data for the optimization model from JSON.

    Parameters
    ----------
    json_data : dict
        JSON object following the Excel-like structure.
    bidding_time : int
        Number of time steps expected in each time-series profile and price vector.
    """

    def __init__(self, json_data: dict, bidding_time: int):
        self.json_data = json_data
        self.data_resources = None
        self.data_prices = None
        self.bidding_time = bidding_time

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def load_data(self):
        """Load and validate resources and prices from the JSON input."""
        try:
            self.data_resources = self.read_resources_from_json()
            self.data_prices = self.read_prices_from_json()
        except Exception as e:
            raise DataLoadingError(f"Error loading JSON input: {e}")
        return self.data_resources, self.data_prices

    # ------------------------------------------------------------------
    # Core resource loading (mirrors Excel version)
    # ------------------------------------------------------------------
    def read_resources_from_json(self) -> list:
        """
        Convert each section of the JSON into DataFrames
        and validate just like the Excel-based loader.
        """
        try:
            # Equivalent to Excel parameter & profile sheets
            params_df = pd.DataFrame.from_records(self.json_data["Energy resources"])
            profile_electrical_load_df = pd.DataFrame.from_records(self.json_data["Electrical loads"])
            profile_thermal_load_df = pd.DataFrame.from_records(self.json_data["Thermal loads"])
            profile_hydrogen_load_df = pd.DataFrame.from_records(self.json_data["Hydrogen loads"])
            profiles_pv_df = pd.DataFrame.from_records(self.json_data["PV generation"])
            profiles_wind_df = pd.DataFrame.from_records(self.json_data["Wind generation"])
            profile_hp_df = pd.DataFrame.from_records(self.json_data["HP loads"])

            # Map column names if you used COLUMN_MAPPING before
            params_df.rename(columns=COLUMN_MAPPING, inplace=True)
        except Exception as e:
            log_and_print(f"Error building DataFrames from JSON: {e}")
            raise DataLoadingError(f"Error building DataFrames from JSON: {e}")

        resource_list = []

        # Iterate through each resource parameter row
        for _, param_row in params_df.iterrows():
            resource_data = param_row.to_dict()
            resource_type = resource_data.get("ResourceType")
            resource_number = resource_data.get("ResourceNumber")

            try:
                if resource_type == "PV" and resource_number in profiles_pv_df["ResourceNumber"].values:
                    profile_row = profiles_pv_df[profiles_pv_df["ResourceNumber"] == resource_number]
                    profile = profile_row.iloc[0, 1:].tolist()
                    self._validate_profile_length(profile)
                    resource_data["profile"] = profile

                elif resource_type == "WindGenerator" and resource_number in profiles_wind_df["ResourceNumber"].values:
                    profile_row = profiles_wind_df[profiles_wind_df["ResourceNumber"] == resource_number]
                    profile = profile_row.iloc[0, 1:].tolist()
                    self._validate_profile_length(profile)
                    resource_data["profile"] = profile

                elif resource_type == "ElectricalLoad" and resource_number in profile_electrical_load_df["ResourceNumber"].values:
                    profile_row = profile_electrical_load_df[profile_electrical_load_df["ResourceNumber"] == resource_number]
                    profile = profile_row.iloc[0, 1:].tolist()
                    self._validate_profile_length(profile)
                    resource_data["profile_electrical_load"] = profile

                elif resource_type == "ThermalLoad" and resource_number in profile_thermal_load_df["ResourceNumber"].values:
                    profile_row = profile_thermal_load_df[profile_thermal_load_df["ResourceNumber"] == resource_number]
                    profile = profile_row.iloc[0, 1:].tolist()
                    self._validate_profile_length(profile)
                    resource_data["profile_thermal_load"] = profile

                elif resource_type == "HydrogenLoad" and resource_number in profile_hydrogen_load_df["ResourceNumber"].values:
                    profile_row = profile_hydrogen_load_df[profile_hydrogen_load_df["ResourceNumber"] == resource_number]
                    profile = profile_row.iloc[0, 1:].tolist()
                    self._validate_profile_length(profile)
                    resource_data["profile_hydrogen_load"] = profile

                elif resource_type == "HeatPump" and resource_number in profile_hp_df["ResourceNumber"].values:
                    profile_row = profile_hp_df[profile_hp_df["ResourceNumber"] == resource_number]
                    profile = profile_row.iloc[0, 1:].tolist()
                    self._validate_profile_length(profile)
                    resource_data["load"] = profile

                # Validate required fields
                self._validate_resource(resource_data, resource_number)
                resource_list.append(resource_data)

            except Exception as e:
                log_and_print(f"Error initializing resource {resource_number}: {e}")
                raise ResourceReadingError(f"Error initializing resource {resource_number}: {e}")

        return resource_list

    # ------------------------------------------------------------------
    # Prices
    # ------------------------------------------------------------------
    def read_prices_from_json(self) -> dict:
        """
        Convert the 'Prices' list into the same dict[label] -> list[float]
        that the Excel loader produced.
        """
        try:
            prices_raw = pd.DataFrame.from_records(self.json_data["Prices"])
            # pivot to wide format (rows = time 0..23, columns = price labels)
            prices_df = prices_raw.set_index("Price").transpose()
            prices = prices_df.astype(float).to_dict(orient="list")
        except Exception as e:
            log_and_print(f"Error parsing Prices from JSON: {e}")
            raise DataLoadingError(f"Error parsing Prices from JSON: {e}")

        self._validate_prices(prices)
        return prices

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------
    def _validate_resource(self, resource_data: dict, resource_number: int):
        rtype = resource_data.get("ResourceType")
        if not rtype:
            raise ResourceReadingError(f"Missing ResourceType in resource {resource_number}")

        required_fields = REQUIRED_FIELDS_BY_TYPE.get(rtype)
        if not required_fields:
            raise ResourceReadingError(f"Unknown resource type: {rtype}")

        missing_fields = [key for key in required_fields if not resource_data.get(key)]
        if missing_fields:
            raise ResourceReadingError(
                f"Missing fields for {rtype} resource {resource_number}: {missing_fields}"
            )

    def _validate_profile_length(self, profile):
        if len(profile) != self.bidding_time:
            raise ResourceReadingError(
                f"Profile length {len(profile)} does not match bidding time {self.bidding_time}"
            )
        if np.any(np.isnan(profile)):
            raise ResourceReadingError(f"Profile contains NaN values: {profile}")

    def _validate_prices(self, prices: dict):
        missing = [label for label in REQUIRED_LABELS_PRICES if label not in prices]
        if missing:
            raise PriceValidationError(f"Missing price labels in JSON: {missing}")

        lengths = {label: len(series) for label, series in prices.items()}
        unique_lengths = set(lengths.values())
        if len(unique_lengths) > 1:
            raise PriceValidationError(f"Inconsistent time series lengths in prices: {lengths}")

        for label, series in prices.items():
            if len(series) != self.bidding_time:
                raise PriceValidationError(
                    f"Price series '{label}' has length {len(series)} but expected {self.bidding_time}"
                )
