from abc import ABC, abstractmethod


class Loads(ABC):

    def __init__(self, resource_id_original: int, resource_id_model: int, hours: int, units: str) -> None:
        self.resource_id_original = resource_id_original
        self.resource_id_model = resource_id_model
        self.hours = hours
        self.units = units


    @abstractmethod
    def get_variables(self, model):
        """Every class after Load() needs to have a create_model function"""
        pass

    @abstractmethod
    def get_constraints(self, model):
        """Every class after Load() needs to have a create_model function"""
        pass

    @abstractmethod
    def save_results(self, model, writer):
        """Every class after Load() needs to have a create_model function"""
        pass

    def get_electricity_output(self, model, hour):
        """By default, resources do not consume/produce electricity energy."""
        return 0

    def get_thermal_output(self, model, hour):
        """By default, resources do not consume/produce thermal energy."""
        return 0

    def get_gas_output(self, model, hour):
        """By default, resources do not consume/produce gas energy."""
        return 0

    def get_biomass_output(self, model, hour):
        """By default, resources do not consume biomass energy."""
        return 0

    def get_upward_reserve_output(self, model, hour):
        """By default, resources do not provide reserves."""
        return 0

    def get_downward_reserve_output(self, model, hour):
        """By default, resources do not provide reserves."""
        return 0
