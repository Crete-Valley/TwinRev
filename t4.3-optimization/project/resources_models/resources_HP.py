import sys

from pyomo.environ import ConcreteModel, NonNegativeReals, Var
from numpy import arange
import pandas as pd

from project.resources_models.resources import Resource


class HeatPump(Resource):
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
        load: list,
        COP: float,
        units: str = "kW",
        flexibility_range: float = 0.1,
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
        HeatPump.resource_count += 1
        self.max_power = max_power
        self.load = load
        self.type = "HeatPump"
        self.COP = COP
        self.flexibility_range = flexibility_range



    def __repr2__(self, abbreviated: int = 1) -> str:
        return repr(
            f"Heat Pump"
            f"Max power {self.units}: {self.max_power} "
            f"Efficiency heat: {self.COP} |"
            f"Reserves participation: {[self.resource_reserves_participation]} | "
            f"{self.__class__.__module__}.{self.__class__.__name__} object at {hex(id(self))} with "
            f"{sys.getsizeof(self)} bits of memory"
        )

    def get_variables(self, model) -> None:
        if getattr(model, "P_HP", False):
            return
        self._create_variables_energy(model, HeatPump.resource_count)
        self._create_reserves_variables_reserve(model, HeatPump.resource_count)

    def get_constraints(self, model) -> None:
        self._create_constraint_energy(model)
        self._create_constraint_reserves(model)

    def _create_variables_energy(self, model, resources_count) -> None:
        """Create variables for Pyomo model"""
        m = model
        m.P_HP_E = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)
        m.P_HP_H = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)
        m.P_load_HP = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)

    def _create_reserves_variables_reserve(self, model, resources_count) -> None:
        """Create variables for Pyomo model"""
        m = model
        if (self.system_reserves_participation or self.system_flexibility_participation) and self.resource_reserves_participation:

            m.U_HP = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)
            m.D_HP = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)

    def _create_constraint_energy(self, model) -> None:
        m = model
        for t in range(0, self.hours):
            m.c1.add(m.P_load_HP[self.resource_id_model, t] == self.load[t])
            m.c1.add(m.P_HP_E[self.resource_id_model, t] <= self.max_power)
            m.c1.add(m.P_HP_H[self.resource_id_model, t] == m.P_load_HP[self.resource_id_model, t])
            m.c1.add(m.P_HP_H[self.resource_id_model, t] == self.COP * m.P_HP_E[self.resource_id_model, t])

    def _create_constraint_reserves(self, model) -> None:
        if (self.system_reserves_participation or self.system_flexibility_participation) and self.resource_reserves_participation:

            m = model
            for t in range(0, self.hours):
                m.c1.add(m.U_HP[self.resource_id_model, t] <= self.flexibility_range * m.P_HP_E[self.resource_id_model, t])
                m.c1.add(m.U_HP[self.resource_id_model, t] + m.P_HP_E[self.resource_id_model, t] <= self.max_power)
                m.c1.add(m.D_HP[self.resource_id_model, t] <= self.flexibility_range * m.P_HP_E[self.resource_id_model, t])

    def get_electricity_output(self, model, hour):
        return model.P_HP_E[self.resource_id_model, hour]

    def get_upward_reserve_output(self, model, hour):
        if (self.system_reserves_participation or self.system_flexibility_participation) and self.resource_reserves_participation:

            return model.U_HP[self.resource_id_model, hour]
        else:
            return 0

    def get_downward_reserve_output(self, model, hour):
        if (self.system_reserves_participation or self.system_flexibility_participation) and self.resource_reserves_participation:

            return model.D_HP[self.resource_id_model, hour]
        else:
            return 0

    def save_results(self, model, writer):
        m = model
        df = pd.DataFrame({
            "Hour": [t + 1 for t in range(self.hours)],
            "HP Load (kW)": [m.P_load_HP[self.resource_id_model, t]() for t in range(self.hours)],
            "Electricity Input (kW)": [m.P_HP_E[self.resource_id_model, t]() for t in range(self.hours)],
            "Heat Output (kW)": [m.P_HP_H[self.resource_id_model, t]() for t in range(self.hours)],
            "Upward Reserve (kW)": [
                m.U_HP[
                    self.resource_id_model, t]() if (self.system_reserves_participation or self.system_flexibility_participation) and self.resource_reserves_participation else 0
                for t in range(self.hours)
            ],
            "Downward Reserve (kW)": [
                m.D_HP[
                    self.resource_id_model, t]() if (self.system_reserves_participation or self.system_flexibility_participation) and self.resource_reserves_participation else 0
                for t in range(self.hours)
            ],
        })
        if not df.empty:
            df.to_excel(writer, sheet_name=f'HeatPump_{self.resource_id_original}', index=False)

        return writer