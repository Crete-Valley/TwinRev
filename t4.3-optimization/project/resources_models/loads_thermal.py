import sys

from pyomo.environ import ConcreteModel, NonNegativeReals, Var, Binary
from numpy import arange
import pandas as pd

from project.resources_models.loads import Loads


class ThermalLoad(Loads):
    resource_count = 0
    def __init__(
            self,
            resource_id_original: int,
            resource_id_model: int,
            thermal_load_profile: int,
            hours: int,
            units: str = "kW",
    ):
        super().__init__(
            resource_id_original,
            resource_id_model,
            hours,
            units,
        )
        ThermalLoad.resource_count += 1
        self.thermal_load_profile = thermal_load_profile
        self.hours = hours
        self.type = "ThermalLoad"


    def __repr2__(self, abbreviated: int = 1) -> str:
            return repr(
                f"Type: {self.type} |"
                f"Load profile {self.units}: {self.thermal_load_profile} |"
                f"{self.__class__.__module__}.{self.__class__.__name__} object at {hex(id(self))} with "
                f"{sys.getsizeof(self)} bits of memory"
            )


    ##########################################################################################
    # Define PV optimization model
    ##########################################################################################

    def get_variables(self, model) -> None:
        self._create_variables_energy(model, ThermalLoad.resource_count)

    def get_constraints(self, model) -> None:
        self._create_constraint_energy(model)

    def _create_variables_energy(self, model, resources_count) -> None:
        """Create variables for pyomo model"""
        m = model
        m.P_load_thermal = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)

    def _create_constraint_energy(self, model) -> None:
        m = model
        for t in range(0, self.hours):
            m.c1.add(m.P_load_thermal[self.resource_id_model, t] == self.thermal_load_profile[t])


    def get_thermal_output(self, model, hour):
        return model.P_load_thermal[self.resource_id_model, hour]


    def save_results(self, model, writer):
        m = model
        df = pd.DataFrame({
            "Hour": [t + 1 for t in range(self.hours)],
            "Thermal Load (kW)": [m.P_load_thermal[self.resource_id_model, t].value for t in range(self.hours)],
        })
        if not df.empty:
            df.to_excel(writer, sheet_name=f'LoadThermal_{self.resource_id_original}', index=False)

        return writer
