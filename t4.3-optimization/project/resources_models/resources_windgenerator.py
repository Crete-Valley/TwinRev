import sys

from pyomo.environ import ConcreteModel, NonNegativeReals, Var
from numpy import arange
import pandas as pd

from project.resources_models.resources import Resource


class WindGenerator(Resource):
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
        profile: list,
        wind_begin: int,
        wind_max: int,
        wind_shutdown: int,
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
        WindGenerator.resource_count += 1
        self.max_power = max_power
        self.type = "WindGenerator"
        self.profile = profile
        self.wind_begin = wind_begin
        self.wind_max = wind_max
        self.wind_shutdown = wind_shutdown



    def __repr2__(self, abbreviated: int = 1) -> str:
            return repr(
                f"WindGenerator"
                f"Max capacity {self.units}: {self.max_power} | Wind profile (p.u.): {self.profile} | "
                f"Reserves participation: {[self.resource_reserves_participation]} | "
                f"{self.__class__.__module__}.{self.__class__.__name__} object at {hex(id(self))} with "
                f"{sys.getsizeof(self)} bits of memory"
            )

    def get_variables(self, model) -> None:
        if getattr(model, "P_WG", False):
            return
        self._create_variables_energy(model, WindGenerator.resource_count)
        self._create_reserves_variables_reserve(model, WindGenerator.resource_count)

    def get_constraints(self, model) -> None:
        self._create_constraint_energy(model)
        self._create_constraint_reserves(model)


    def _create_variables_energy(self, model, resources_count) -> None:
        """Create variables for pyomo model"""
        m = model
        m.P_WG = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)
        m.P_WG_profile = Var(arange(resources_count), range(self.hours), domain=NonNegativeReals)

    def _create_reserves_variables_reserve(self, model, resources_count) -> None:
        """Create variables for pyomo model"""
        m = model
        if (self.system_reserves_participation or self.system_flexibility_participation) and self.resource_reserves_participation:

            m.U_WG = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)
            m.D_WG = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)

    def _create_constraint_energy(self, model) -> None:
        m = model
        for t in range(0, self.hours):
            m.c1.add(m.P_WG_profile[self.resource_id_model, t] == self.profile[t])
            if self.profile[t] < self.wind_begin:
                m.c1.add(m.P_WG[self.resource_id_model, t] == 0)
            elif self.wind_max > self.profile[t] >= self.wind_begin:
                m.c1.add(m.P_WG[self.resource_id_model, t] == (self.max_power/(self.wind_max - self.wind_begin)) *
                         self.profile[t] + self.max_power * (1 - (self.wind_max/(self.wind_max - self.wind_begin))))
            elif self.wind_shutdown > self.profile[t] >= self.wind_max:
                m.c1.add(m.P_WG[self.resource_id_model, t] == self.max_power)
            else:
                m.c1.add(m.P_WG[self.resource_id_model, t] == 0)

    def _create_constraint_reserves(self, model) -> None:
        if (self.system_reserves_participation or self.system_flexibility_participation) and self.resource_reserves_participation:

            m = model
            for t in range(0, self.hours):
                if self.profile[t] < self.wind_begin:
                    m.c1.add(m.U_WG[self.resource_id_model, t] == 0)
                    m.c1.add(m.D_WG[self.resource_id_model, t] == 0)
                elif self.wind_max > self.profile[t] >= self.wind_begin:
                    m.c1.add(m.U_WG[self.resource_id_model, t] == (self.max_power / (self.wind_max - self.wind_begin)) *
                             self.profile[t] + self.max_power * (
                                         1 - (self.wind_max / (self.wind_max - self.wind_begin))) -
                             m.P_WG[self.resource_id_model, t])
                    m.c1.add(m.D_WG[self.resource_id_model, t] <= m.P_WG[self.resource_id_model, t])
                elif self.wind_shutdown > self.profile[t] >= self.wind_max:
                    m.c1.add(m.U_WG[self.resource_id_model, t] == self.max_power - m.P_WG[self.resource_id_model, t])
                    m.c1.add(m.D_WG[self.resource_id_model, t] <= m.P_WG[self.resource_id_model, t])
                else:
                    m.c1.add(m.U_WG[self.resource_id_model, t] == 0)
                    m.c1.add(m.D_WG[self.resource_id_model, t] == 0)

    def get_electricity_output(self, model, hour):
        return -model.P_WG[self.resource_id_model, hour]

    def get_upward_reserve_output(self, model, hour):
        if (self.system_reserves_participation or self.system_flexibility_participation) and self.resource_reserves_participation:

            return model.U_WG[self.resource_id_model, hour]
        else:
            return 0

    def get_downward_reserve_output(self, model, hour):
        if (self.system_reserves_participation or self.system_flexibility_participation) and self.resource_reserves_participation:

            return model.D_WG[self.resource_id_model, hour]
        else:
            return 0

    def save_results(self, model, writer):
        m = model
        df = pd.DataFrame({
            "Hour": [t + 1 for t in range(self.hours)],
            "P_WG (kW)": [m.P_WG[self.resource_id_model, t].value for t in range(self.hours)],
            "P_WG_profile (m/s)": [m.P_WG_profile[self.resource_id_model, t].value for t in range(self.hours)],
            "U_WG (kW)": [m.U_WG[self.resource_id_model, t].value if (self.system_reserves_participation or self.system_flexibility_participation)
                                           and self.resource_reserves_participation else 0 for t in range(self.hours)],
            "D_WG (kW)": [m.D_WG[self.resource_id_model, t].value if (self.system_reserves_participation or self.system_flexibility_participation)
                                             and self.resource_reserves_participation else 0 for t in range(self.hours)],
        })
        if not df.empty:
            df.to_excel(writer, sheet_name=f'WindGenerator_{self.resource_id_original}', index=False)

        return writer
