"""
Resource initialization module.

Takes structured resource input data (typically loaded from Excel),
and instantiate the appropriate Python classes for each resource
(e.g., PV, Battery, CHP, etc.), including time-series profiles and
technical parameters.

This module:
- Assigns unique model-level IDs per resource type.
- Supports all types listed in `get_resources_id_list()`.
- Logs the number and type of resources initialized.

Raises:
- ValueError if an unknown resource type is encountered.
"""

from collections import Counter

from project.resources_models.resources_PV import PV
from project.resources_models.resources_windgenerator import WindGenerator
from project.resources_models.resources_CHP import CHP
from project.resources_models.resources_battery import Battery
from project.resources_models.loads_electrical import ElectricalLoad
from project.resources_models.loads_thermal import ThermalLoad
from project.resources_models.resources_electrolyzer import Electrolyzer
from project.resources_models.resources_fuelcell import FuelCell
from project.resources_models.resources_hydrogenstorage import HydrogenStorage
from project.resources_models.loads_hydrogen import HydrogenLoad
from project.resources_models.resources_HP import HeatPump
from project.resources_models.resources_geoexchange import GeoExchange
from project.resources_models.resources_boiler import Boiler
from project.helper.helper import log_and_print
from project.helper.exceptions import ResourceInitializationError


def initialize_resources(resource_data_list: dict, bidding_time: int, system_reserves_participation: int,
                         system_flexibility_participation: int) -> list:
    """
    Instantiate resource objects from structured data.

    Args:
        resource_data_list (list of dict): List of parameter dictionaries for each resource.
        bidding_time (int): Number of time steps (e.g., 24 for hourly over one day).
        system_reserves_participation (int): 1 if system-wide reserves are considered; 0 otherwise.

    Returns:
        list: Initialized resource class instances (PV, Battery, etc.).

    Raises:
        ValueError: If a resource type is not supported.
    """
    resources = []
    resource_id_list = get_resources_id_list()

    for resource_data in resource_data_list:
        if resource_data["ResourceType"] == "PV":
            resource = PV(
                resource_id_original=resource_data.get("ResourceNumber"),
                resource_id_model=resource_id_list[resource_data['ResourceType']],
                profile=resource_data["profile"],
                system_reserves_participation=system_reserves_participation,
                system_flexibility_participation=system_flexibility_participation,
                resource_reserves_participation=resource_data.get("ReservesParticipation"),
                hours=bidding_time,
                units="kW",
            )
            resource_id_list['PV'] = resource_id_list['PV'] + 1

        elif resource_data["ResourceType"] == "WindGenerator":
            resource = WindGenerator(
                resource_id_original=resource_data.get("ResourceNumber"),
                resource_id_model=resource_id_list[resource_data['ResourceType']],
                max_power=resource_data["max_power"],
                profile=resource_data["profile"],
                wind_begin=resource_data["wind_begin"],
                wind_max=resource_data["wind_max"],
                wind_shutdown=resource_data["wind_shutdown"],
                system_reserves_participation=system_reserves_participation,
                system_flexibility_participation=system_flexibility_participation,
                resource_reserves_participation=resource_data.get("ReservesParticipation"),
                hours=bidding_time,
                units="kW",
            )
            resource_id_list['WindGenerator'] = resource_id_list['WindGenerator'] + 1

        elif resource_data["ResourceType"] == "Battery":
            resource = Battery(
                resource_id_original=resource_data.get("ResourceNumber"),
                resource_id_model=resource_id_list[resource_data['ResourceType']],
                max_capacity=resource_data["max_capacity"],
                min_capacity=resource_data.get("min_capacity"),
                initial_SOC=resource_data.get("initial_SOC"),
                max_power_charging=resource_data.get("max_power_charging"),
                max_power_discharging=resource_data.get("max_power_discharging"),
                efficiency_ch=resource_data.get("efficiency_ch"),
                efficiency_dis=resource_data.get("efficiency_dis"),
                system_reserves_participation=system_reserves_participation,
                system_flexibility_participation=system_flexibility_participation,
                resource_reserves_participation=resource_data.get("ReservesParticipation"),
                hours=bidding_time,
                units="kW",
            )
            resource_id_list['Battery'] = resource_id_list['Battery'] + 1

        elif resource_data["ResourceType"] == "ElectricalLoad":
            resource = ElectricalLoad(
                resource_id_original=resource_data.get("ResourceNumber"),
                resource_id_model=resource_id_list[resource_data['ResourceType']],
                electrical_load_profile=resource_data["profile_electrical_load"],
                hours=bidding_time,
                units="kW",
            )
            resource_id_list['ElectricalLoad'] = resource_id_list['ElectricalLoad'] + 1
        elif resource_data["ResourceType"] == "ThermalLoad":
            resource = ThermalLoad(
                resource_id_original=resource_data.get("ResourceNumber"),
                resource_id_model=resource_id_list[resource_data['ResourceType']],
                thermal_load_profile=resource_data["profile_thermal_load"],
                hours=bidding_time,
                units="kW",
            )
            resource_id_list['ThermalLoad'] = resource_id_list['ThermalLoad'] + 1

        elif "CHP" in resource_data["ResourceType"]:
            resource = CHP(
                resource_id_original=resource_data.get("ResourceNumber"),
                resource_id_model=resource_id_list[resource_data['ResourceType']],
                max_power=resource_data["max_power"],
                efficiency_heat=resource_data["efficiency_heat"],
                efficiency_elec=resource_data["efficiency_electricity"],
                system_reserves_participation=system_reserves_participation,
                system_flexibility_participation=system_flexibility_participation,
                resource_reserves_participation=resource_data.get("ReservesParticipation"),
                hours=bidding_time,
                units="kW",
            )
            resource_id_list['CHP'] = resource_id_list['CHP'] + 1

        elif "Electrolyzer" in resource_data["ResourceType"]:
            resource = Electrolyzer(
                resource_id_original=resource_data.get("ResourceNumber"),
                resource_id_model=resource_id_list[resource_data['ResourceType']],
                max_power=resource_data["max_power"],
                efficiency=resource_data["efficiency"],
                system_reserves_participation=system_reserves_participation,
                system_flexibility_participation=system_flexibility_participation,
                resource_reserves_participation=resource_data.get("ReservesParticipation"),
                hours=bidding_time,
                units="kW",
            )
            resource_id_list['Electrolyzer'] = resource_id_list['Electrolyzer'] + 1

        elif "FuelCell" in resource_data["ResourceType"]:
            resource = FuelCell(
                resource_id_original=resource_data.get("ResourceNumber"),
                resource_id_model=resource_id_list[resource_data['ResourceType']],
                max_power=resource_data["max_power"],
                efficiency=resource_data["efficiency"],
                system_reserves_participation=system_reserves_participation,
                system_flexibility_participation=system_flexibility_participation,
                resource_reserves_participation=resource_data.get("ReservesParticipation"),
                hours=bidding_time,
                units="kW",
            )
            resource_id_list['FuelCell'] = resource_id_list['FuelCell'] + 1

        elif "HydrogenStorage" in resource_data["ResourceType"]:
            resource = HydrogenStorage(
                resource_id_original=resource_data.get("ResourceNumber"),
                resource_id_model=resource_id_list[resource_data['ResourceType']],
                max_capacity=resource_data["max_capacity"],
                min_capacity=resource_data.get("min_capacity"),
                initial_SOC=resource_data.get("initial_SOC"),
                max_power=resource_data["max_power"],
                efficiency_ch=resource_data.get("efficiency_ch"),
                efficiency_dis=resource_data.get("efficiency_dis"),
                system_reserves_participation=system_reserves_participation,
                system_flexibility_participation=system_flexibility_participation,
                resource_reserves_participation=resource_data.get("ReservesParticipation"),
                hours=bidding_time,
                units="kW",
            )
            resource_id_list['HydrogenStorage'] = resource_id_list['HydrogenStorage'] + 1

        elif resource_data["ResourceType"] == "HydrogenLoad":
            resource = HydrogenLoad(
                resource_id_original=resource_data.get("ResourceNumber"),
                resource_id_model=resource_id_list[resource_data['ResourceType']],
                hydrogen_load_profile=resource_data["profile_hydrogen_load"],
                hours=bidding_time,
                units="kW",
            )
            resource_id_list['HydrogenLoad'] = resource_id_list['HydrogenLoad'] + 1

        elif resource_data["ResourceType"] == "HeatPump":
            resource = HeatPump(
                resource_id_original=resource_data.get("ResourceNumber"),
                resource_id_model=resource_id_list[resource_data['ResourceType']],
                system_reserves_participation=system_reserves_participation,
                system_flexibility_participation=system_flexibility_participation,
                resource_reserves_participation=resource_data.get("ReservesParticipation"),
                hours=bidding_time,
                load=resource_data["load"],
                max_power=resource_data["max_power"],
                COP=resource_data["COP"],
                units="kW",
                flexibility_range=resource_data["flexibility_range"],
            )
            resource_id_list['HeatPump'] = resource_id_list['HeatPump'] + 1

        elif resource_data["ResourceType"] == "GeoExchange":
            resource = GeoExchange(
                resource_id_original=resource_data.get("ResourceNumber"),
                resource_id_model=resource_id_list[resource_data['ResourceType']],
                system_reserves_participation=system_reserves_participation,
                system_flexibility_participation=system_flexibility_participation,
                resource_reserves_participation=resource_data.get("ReservesParticipation"),
                hours=bidding_time,
                max_power=resource_data["max_power"],
                efficiency_heat=resource_data["efficiency_heat"],
                units="kW",
                flexibility_range=resource_data["flexibility_range"]
            )
            resource_id_list['GeoExchange'] = resource_id_list['GeoExchange'] + 1

        elif resource_data["ResourceType"] == "Boiler":
            resource = Boiler(
                resource_id_original=resource_data.get("ResourceNumber"),
                resource_id_model=resource_id_list[resource_data['ResourceType']],
                system_reserves_participation=system_reserves_participation,
                system_flexibility_participation=system_flexibility_participation,
                resource_reserves_participation=resource_data.get("ReservesParticipation"),
                hours=bidding_time,
                max_power=resource_data["max_power"],
                efficiency_heat=resource_data["efficiency_heat"],
                units="kW",
            )
            resource_id_list['Boiler'] = resource_id_list['Boiler'] + 1

        else:
            raise ResourceInitializationError(f"Unknown resource type: {resource_data['ResourceType']}")

        resources.append(resource)

    log_resources(resources)

    return resources


def get_resources_id_list() -> dict:
    """Get resources id list."""
    return {
        "PV": 0,
        "WindGenerator": 0,
        "Battery": 0,
        "ThermalStorage": 0,
        "CHP": 0,
        "Electrolyzer": 0,
        "FuelCell": 0,
        "HydrogenStorage": 0,
        "ElectricalLoad": 0,
        "ThermalLoad": 0,
        "HydrogenLoad": 0,
        "HeatPump": 0,
        "Boiler": 0,
        "GeoExchange": 0
    }


def log_resources(resources: list) -> None:
    """Log a count of each resource type initialized."""
    log_and_print("=======================================")
    resource_types = [r.__class__.__name__ for r in resources]
    type_counts = Counter(resource_types)

    log_and_print("Resource types in this run:")
    for rtype, count in type_counts.items():
        log_and_print(f" - {rtype}: {count}")
    log_and_print("=======================================")
