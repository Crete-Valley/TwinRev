"""
Data loading utilities for the optimization workflow.

This module reads:
- Resource parameters and time-series profiles from specific Excel sheets.
- Market/price series from a "Prices" sheet.

It validates:
- Required columns per resource type (see config.REQUIRED_FIELDS_BY_TYPE).
- Profile lengths match the configured bidding horizon.
- Price labels exist (config.REQUIRED_LABELS_PRICES), lengths are consistent,
  and match the bidding horizon.

Raises:
- DataLoadingError, PriceValidationError, ResourceReadingError
  for recoverable, user-actionable input issues.
"""


import pandas as pd
import numpy as np

from helper.helper import log_and_print
from helper.exceptions import DataLoadingError, PriceValidationError, ResourceReadingError
from config import (REQUIRED_LABELS_PRICES, REQUIRED_FIELDS_BY_TYPE, PARAM_SHEET, SHEET_ELECTRICAL_LOADS,
                    SHEET_THERMAL_LOADS, SHEET_HYDROGEN_LOADS, SHEET_PV, SHEET_WIND, SHEET_HP, COLUMN_MAPPING)



class DataLoader:
    """Load and validate input data for the optimization model.

    Parameters
    ----------
    file_name : str | os.PathLike
        Path to the Excel file containing all required sheets.
    bidding_time : int
        Number of time steps expected in each time-series profile and price vector.

    Attributes
    ----------
    file_name : str | os.PathLike
        Path to the Excel file.
    data_resources : list[dict] | None
        Parsed and validated resource objects (flat dicts).
    data_prices : dict[str, list[float]] | None
        Parsed and validated price series.
    bidding_time : int
        Expected horizon length for all time-series inputs.
    """
    def __init__(self, file_name: str, bidding_time: int):
        self.file_name = file_name
        self.data_resources = None
        self.data_prices = None
        self.bidding_time = bidding_time

    def load_data(self):
        """Load and validate resource and price data from the Excel file."""
        self.data_resources = self.read_resources_from_excel()
        self.data_prices = self.read_prices_from_excel()

        return self.data_resources, self.data_prices

    def read_resources_from_excel(self) -> list:
        """Read resources and profiles from Excel and return a list of resource dicts."""
        try:
            params_df = pd.read_excel(self.file_name, sheet_name=PARAM_SHEET, engine="openpyxl")
            profile_electrical_load_df = pd.read_excel(self.file_name, sheet_name=SHEET_ELECTRICAL_LOADS,
                                                       engine="openpyxl")
            profile_thermal_load_df = pd.read_excel(self.file_name, sheet_name=SHEET_THERMAL_LOADS,
                                                    engine="openpyxl")
            profile_hydrogen_load_df = pd.read_excel(self.file_name, sheet_name=SHEET_HYDROGEN_LOADS,
                                                     engine="openpyxl")
            profiles_pv_df = pd.read_excel(self.file_name, sheet_name=SHEET_PV, engine="openpyxl")

            profiles_wind_df = pd.read_excel(self.file_name, sheet_name=SHEET_WIND, engine="openpyxl")

            profile_hp_df = pd.read_excel(self.file_name, sheet_name=SHEET_HP, engine="openpyxl")


        except Exception as e:
            log_and_print(f"Error reading Excel file: {e}")
            raise DataLoadingError(f"Error reading the Excel file: {e}")

        # Map Excel column names to code parameter names
        params_df.rename(columns=COLUMN_MAPPING, inplace=True)

        # Prepare resource list
        resource_list = []

        # Iterate through the parameters DataFrame
        for _, param_row in params_df.iterrows():
            resource_data = param_row.to_dict()

            # Match profiles by ResourceType
            resource_type = resource_data.get("ResourceType")
            resource_number = resource_data.get("ResourceNumber")

            try:
                if resource_type == 'PV' and resource_number in profiles_pv_df["ResourceNumber"].values:
                    # Extract the profile row for PV generation
                    profile_row = profiles_pv_df[(profiles_pv_df["ResourceNumber"] == resource_number)]
                    profile = profile_row.iloc[0, 1:].tolist()
                    self._validate_profile_length(profile)
                    resource_data["profile"] = profile

                elif resource_type == 'WindGenerator' and resource_number in profiles_wind_df["ResourceNumber"].values:
                    # Extract the profile row for PV generation
                    profile_row = profiles_wind_df[(profiles_wind_df["ResourceNumber"] == resource_number)]
                    profile = profile_row.iloc[0, 1:].tolist()
                    self._validate_profile_length(profile)
                    resource_data["profile"] = profile

                elif resource_type == 'ElectricalLoad':
                    if resource_number in profile_electrical_load_df["ResourceNumber"].values:
                        # Extract the profile row for electrical loads
                        profile_row = profile_electrical_load_df[(profile_electrical_load_df["ResourceNumber"] ==
                                                                  resource_number)]
                        profile = profile_row.iloc[0, 1:].tolist()
                        self._validate_profile_length(profile)
                        resource_data["profile_electrical_load"] = profile

                elif resource_type == 'ThermalLoad':
                    if resource_number in profile_thermal_load_df["ResourceNumber"].values:
                        # Extract the profile row for thermal loads
                        profile_row = profile_thermal_load_df[(profile_thermal_load_df["ResourceNumber"] ==
                                                               resource_number)]
                        profile = profile_row.iloc[0, 1:].tolist()
                        self._validate_profile_length(profile)
                        resource_data["profile_thermal_load"] = profile

                elif resource_type == 'HydrogenLoad':
                    if resource_number in profile_hydrogen_load_df["ResourceNumber"].values:
                        # Extract the profile row for electrical loads
                        profile_row = profile_hydrogen_load_df[(profile_hydrogen_load_df["ResourceNumber"] ==
                                                                  resource_number)]
                        profile = profile_row.iloc[0, 1:].tolist()
                        self._validate_profile_length(profile)
                        resource_data["profile_hydrogen_load"] = profile

                elif resource_type == 'HeatPump':
                    if resource_number in profile_hp_df["ResourceNumber"].values:
                        # Extract the profile row for hp load
                        profile_row = profile_hp_df[(profile_hp_df["ResourceNumber"] ==
                                                                  resource_number)]
                        profile = profile_row.iloc[0, 1:].tolist()
                        self._validate_profile_length(profile)
                        resource_data["load"] = profile

                self._validate_resource(resource_data, resource_number)
                resource_list.append(resource_data)

            except Exception as e:
                log_and_print(f"Error initializing resource {resource_number}: {e}")
                raise ResourceReadingError(f"Error initializing resource {resource_number}: {e}")

        return resource_list

    def read_prices_from_excel(self) -> dict:
        """Read price series from Excel (sheet 'Prices') into a dict[label] -> list[float]."""
        sheet_name = "Prices"

        try:
            # Read the entire Excel sheet without assuming headers or indices
            raw_df = pd.read_excel(self.file_name, sheet_name=sheet_name, engine="openpyxl", header=None)

        except Exception as e:
            log_and_print(f"Error reading Excel file: {e}")
            raise DataLoadingError(f"Error reading the Excel file: {e}")

        # Manually adjust the DataFrame:
        # - First column becomes the index
        # - First row becomes the column headers
        raw_df = raw_df.transpose()  # Transpose the DataFrame so the first column becomes headers
        raw_df.columns = raw_df.iloc[0]  # Set the first row as column headers
        raw_df = raw_df[1:]  # Drop the first row from the data
        raw_df.set_index(raw_df.columns[0], inplace=True)  # Set the first column as the index

        # Convert the cleaned DataFrame to a dictionary
        prices = raw_df.astype(float).to_dict(orient="list")

        self._validate_prices(prices)

        return prices

    def _validate_resource(self, resource_data: dict, resource_number: int):
        """Validate resource type and required fields (presence and NaN checks)."""
        rtype = resource_data.get("ResourceType")
        if not rtype:
            log_and_print(f"Missing ResourceType in resource {resource_number}")
            raise ResourceReadingError(f"Missing ResourceType in resource {resource_number}")

        required_fields = REQUIRED_FIELDS_BY_TYPE.get(rtype)
        if not required_fields:
            log_and_print(f"Unknown resource type: {rtype}")
            raise ResourceReadingError(f"Unknown resource type: {rtype}")

        missing_fields = [key for key in required_fields if not resource_data.get(key)]
        if missing_fields:
            log_and_print(f"Missing fields for {rtype} resource {resource_number}: {missing_fields}")
            raise ResourceReadingError(
                f"Missing fields for {rtype} resource {resource_number}: {missing_fields}"
            )

    def _validate_profile_length(self, profile):
        """Validate that the profile length matches the bidding time."""
        if len(profile) != self.bidding_time:
            log_and_print(f"Profile length {len(profile)} does not match bidding time {self.bidding_time}")
            raise ResourceReadingError(
                f"Profile length {len(profile)} does not match bidding time {self.bidding_time}"
            )
        elif True in np.isnan(profile):
            log_and_print(f"Profile contains NaN values: {profile}")
            raise ResourceReadingError(f"Profile contains NaN values: {profile}")

    def _validate_prices(self, prices: dict) -> None:
        """Validate price labels, lengths, NaNs, and consistency with bidding_time."""
        # Check required labels
        missing = [label for label in REQUIRED_LABELS_PRICES if label not in prices]
        if missing:
            log_and_print(f"Missing price labels in Excel: {missing}")
            raise PriceValidationError(f"Missing price labels in Excel: {missing}")

        # Check all lists have the same length
        lengths = {label: len(series) for label, series in prices.items()}
        unique_lengths = set(lengths.values())
        if len(unique_lengths) > 1:
            log_and_print(f"Inconsistent time series lengths in prices: {lengths}")
            raise PriceValidationError(f"Inconsistent time series lengths in prices: {lengths}")

        # Check length matches bidding_time if accessible
        expected_length = self.bidding_time  # Replace with self.bidding_time if available
        for label, series in prices.items():
            if len(series) != expected_length:
                log_and_print(f"Price series '{label}' has length {len(series)} but expected {expected_length}")
                raise PriceValidationError(f"Label '{label}' has length {len(series)} but expected {expected_length}")

        return None
