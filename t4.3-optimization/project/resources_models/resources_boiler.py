import sys

from pyomo.environ import ConcreteModel, NonNegativeReals, Var
from numpy import arange
import pandas as pd

from project.resources_models.resources import Resource


class Boiler(Resource):
    resource_count = 0
    def __init__(
        self,
        resource_id_original: int,
        resource_id_model: int,
        system_reserves_participation: int,
        system_flexibility_participation: int,
        resource_reserves_participation: int,
        hours: int,
        max_power: float,
        efficiency_heat: float,
        units: str = "kW",
    ):
        super().__init__(
            resource_id_original,
            resource_id_model,
            system_reserves_participation,
            system_flexibility_participation,
            resource_reserves_participation,
            hours,
            units,
        )
        Boiler.resource_count += 1
        self.max_power = max_power
        self.type = "Boiler"
        self.efficiency_heat = efficiency_heat


    def __repr2__(self, abbreviated: int = 1) -> str:
        return repr(
            f"Boiler"
            f"Max power {self.units}: {self.max_power} "
            f"Efficiency heat: {self.efficiency_heat} |"
            f"Reserves participation: {[self.resource_reserves_participation]} | "
            f"{self.__class__.__module__}.{self.__class__.__name__} object at {hex(id(self))} with "
            f"{sys.getsizeof(self)} bits of memory"
        )

    def get_variables(self, model) -> None:
        if getattr(model, "P_boiler_B", False):
            return
        self._create_variables_energy(model, Boiler.resource_count)

    def get_constraints(self, model) -> None:
        self._create_constraint_energy(model)

    def _create_variables_energy(self, model, resources_count)-> None:
        """Create variables for Pyomo model"""
        m = model
        m.P_boiler_B = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)
        m.P_boiler_H = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)

    def _create_constraint_energy(self, model) -> None:
        m = model
        for t in range(0, self.hours):
            m.c1.add(m.P_boiler_B[self.resource_id_model, t] <= self.max_power)
            m.c1.add(m.P_boiler_H[self.resource_id_model, t] == self.efficiency_heat * m.P_boiler_B[self.resource_id_model, t])

    def get_biomass_output(self, model, hour):
        return model.P_boiler_B[self.resource_id_model, hour]

    def get_thermal_output(self, model, hour):
        return -model.P_boiler_H[self.resource_id_model, hour]

    def save_results(self, model, writer):
        m = model
        df = pd.DataFrame({
            "Hour": [t + 1 for t in range(self.hours)],
            "Boiler_B (kW)": [m.P_boiler_B[self.resource_id_model, t].value for t in range(self.hours)],
            "Boiler_H (kW)": [m.P_boiler_H[self.resource_id_model, t].value for t in range(self.hours)],
        })
        if not df.empty:
            df.to_excel(writer, sheet_name=f'Boiler_{self.resource_id_original}', index=False)

        return writer