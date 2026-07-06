import sys

from pyomo.environ import ConcreteModel, NonNegativeReals, Var
from numpy import arange
import pandas as pd

from project.resources_models.resources import Resource


class PV(Resource):
    resource_count = 0
    def __init__(
        self,
        resource_id_original: int,
        resource_id_model: int,
        system_reserves_participation: int,
        system_flexibility_participation: int,
        resource_reserves_participation: int,
        hours: int,
        profile: list,
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
        PV.resource_count += 1
        self.type = "PV"
        self.profile = profile



    def __repr2__(self, abbreviated: int = 1) -> str:
            return repr(
                f"PV"
                f"Max capacity {self.units}: {self.max_power} | Solar profile (p.u.): {self.profile} | "
                f"Reserves participation: {[self.resource_reserves_participation]} | "
                f"{self.__class__.__module__}.{self.__class__.__name__} object at {hex(id(self))} with "
                f"{sys.getsizeof(self)} bits of memory"
            )

    def get_variables(self, model) -> None:
        if getattr(model, "P_PV", False):
            return
        self._create_variables_energy(model, PV.resource_count)
        self._create_reserves_variables_reserve(model, PV.resource_count)

    def get_constraints(self, model) -> None:
        self._create_constraint_energy(model)
        self._create_constraint_reserves(model)


    def _create_variables_energy(self, model, resources_count) -> None:
        """Create variables for pyomo model"""
        m = model
        m.P_PV = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)
        m.P_PV_profile = Var(arange(resources_count), range(self.hours), domain=NonNegativeReals)

    def _create_reserves_variables_reserve(self, model, resources_count) -> None:
        """Create variables for pyomo model"""
        m = model
        if (self.system_reserves_participation or self.system_flexibility_participation) and self.resource_reserves_participation:

            m.U_PV = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)
            m.D_PV = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)


    def _create_constraint_energy(self, model) -> None:
        m = model
        for t in range(0, self.hours):
            m.c1.add(m.P_PV[self.resource_id_model, t] <= self.profile[t])
            m.c1.add(m.P_PV_profile[self.resource_id_model, t] == self.profile[t])

    def _create_constraint_reserves(self, model) -> None:
        if (self.system_reserves_participation or self.system_flexibility_participation) and self.resource_reserves_participation:

            m = model
            for t in range(0, self.hours):
                m.c1.add(m.U_PV[self.resource_id_model, t] <= self.profile[t] - m.P_PV[self.resource_id_model, t])
                m.c1.add(m.D_PV[self.resource_id_model, t] <= m.P_PV[self.resource_id_model, t])

    def get_electricity_output(self, model, hour):
        return -model.P_PV[self.resource_id_model, hour]

    def get_upward_reserve_output(self, model, hour):
        if (self.system_reserves_participation or self.system_flexibility_participation) and self.resource_reserves_participation:

            return model.U_PV[self.resource_id_model, hour]
        else:
            return 0

    def get_downward_reserve_output(self, model, hour):
        if (self.system_reserves_participation or self.system_flexibility_participation) and self.resource_reserves_participation:

            return model.D_PV[self.resource_id_model, hour]
        else:
            return 0

    def save_results(self, model, writer):
        m = model
        df = pd.DataFrame({
            "Hour": [t + 1 for t in range(self.hours)],
            "Electricity Output (kW)": [m.P_PV[self.resource_id_model, t]() for t in range(self.hours)],
            "Upward Reserve (kW)": [
                m.U_PV[self.resource_id_model, t]()
                if (self.system_reserves_participation or self.system_flexibility_participation)
                   and self.resource_reserves_participation else 0
                for t in range(self.hours)
            ],
            "Downward Reserve (kW)": [
                m.D_PV[self.resource_id_model, t]()
                if (self.system_reserves_participation or self.system_flexibility_participation)
                   and self.resource_reserves_participation else 0
                for t in range(self.hours)
            ]
        })
        if not df.empty:
            df.to_excel(writer, sheet_name=f'PV_{self.resource_id_original}', index=False)

        return writer
