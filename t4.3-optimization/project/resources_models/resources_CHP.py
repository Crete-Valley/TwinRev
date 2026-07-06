import sys

from numpy import arange
from pyomo.environ import ConcreteModel, NonNegativeReals, Var, Binary
import pandas as pd

from project.resources_models.resources import Resource


class CHP(Resource):
    resource_count = 0
    __slots__ = (
        "max_power",
        "efficiency_heat",
        "efficiency_elec",
        "type",
    )

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
            efficiency_elec: float,
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
        CHP.resource_count += 1
        self.max_power = max_power
        self.efficiency_heat = efficiency_heat
        self.efficiency_elec = efficiency_elec
        self.type = "CHP"

    def __repr2__(self, abbreviated: int = 1) -> str:
        return repr(
            f"Max capacity  {self.units}: {self.max_power} |"
            f"Efficiency heat: {self.efficiency_heat} |"
            f"Efficiency elec: {self.efficiency_elec} |"
            f"Reserves participation: {['No', 'Yes'][self.resource_reserves_participation]} | "
            f"{self.__class__.__module__}.{self.__class__.__name__} object at {hex(id(self))} with "
            f"{sys.getsizeof(self)} bits of memory"
        )

    ##########################################################################################
    # Define PV optimization model
    ##########################################################################################

    def get_variables(self, model) -> None:
        if getattr(model, "P_CHP_G", False):
            return
        self._create_variables_energy(model, CHP.resource_count)
        self._create_reserves_variables_reserve(model, CHP.resource_count)

    def get_constraints(self, model) -> None:
        self._create_constraint_energy(model)
        self._create_constraint_reserves(model)

    def _create_variables_energy(self, model, resources_count) -> None:
        """Create variables for pyomo model"""
        m = model
        m.P_CHP_G = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)
        m.P_CHP_H = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)
        m.P_CHP_E = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)

    def _create_reserves_variables_reserve(self, model, resources_count) -> None:
        """Create variables for pyomo model"""
        m = model
        if (
                self.system_reserves_participation or self.system_flexibility_participation) and self.resource_reserves_participation:
            m.U_CHP_G = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)
            m.U_CHP_H = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)
            m.U_CHP_E = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)
            m.D_CHP_G = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)
            m.D_CHP_H = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)
            m.D_CHP_E = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)

    def _create_constraint_energy(self, model) -> None:
        m = model
        for t in range(0, self.hours):
            m.c1.add(m.P_CHP_G[self.resource_id_model, t] <= self.max_power)
            m.c1.add(
                m.P_CHP_E[self.resource_id_model, t] == self.efficiency_elec * m.P_CHP_G[self.resource_id_model, t])
            m.c1.add(
                m.P_CHP_H[self.resource_id_model, t] == self.efficiency_heat * m.P_CHP_G[self.resource_id_model, t])

    def _create_constraint_reserves(self, model) -> None:
        if (
                self.system_reserves_participation or self.system_flexibility_participation) and self.resource_reserves_participation:

            m = model
            for t in range(0, self.hours):
                m.c1.add(m.U_CHP_G[self.resource_id_model, t] <= self.max_power - m.P_CHP_G[self.resource_id_model, t])
                m.c1.add(m.D_CHP_G[self.resource_id_model, t] <= m.P_CHP_G[self.resource_id_model, t])
                m.c1.add(
                    m.U_CHP_H[self.resource_id_model, t] == self.efficiency_heat * m.U_CHP_G[self.resource_id_model, t])
                m.c1.add(
                    m.D_CHP_H[self.resource_id_model, t] == self.efficiency_heat * m.D_CHP_G[self.resource_id_model, t])
                m.c1.add(
                    m.U_CHP_E[self.resource_id_model, t] == self.efficiency_elec * m.U_CHP_G[self.resource_id_model, t])
                m.c1.add(
                    m.D_CHP_E[self.resource_id_model, t] == self.efficiency_elec * m.D_CHP_G[self.resource_id_model, t])

    def get_electricity_output(self, model, hour):
        return -model.P_CHP_E[self.resource_id_model, hour]

    def get_thermal_output(self, model, hour):
        return -model.P_CHP_H[self.resource_id_model, hour]

    def get_gas_output(self, model, hour):
        return model.P_CHP_G[self.resource_id_model, hour]

    def get_upward_reserve_output(self, model, hour):
        if (
                self.system_reserves_participation or self.system_flexibility_participation) and self.resource_reserves_participation:

            return model.U_CHP_E[self.resource_id_model, hour]
        else:
            return 0

    def get_downward_reserve_output(self, model, hour):
        if (
                self.system_reserves_participation or self.system_flexibility_participation) and self.resource_reserves_participation:

            return model.D_CHP_E[self.resource_id_model, hour]
        else:
            return 0

    def save_results(self, model, writer):
        m = model
        df = pd.DataFrame({
            "Hour": [t + 1 for t in range(self.hours)],
            "CHP_G (kW)": [m.P_CHP_G[self.resource_id_model, t].value for t in range(self.hours)],
            "CHP_E (kW)": [m.P_CHP_E[self.resource_id_model, t].value for t in range(self.hours)],
            "CHP_H (kW)": [m.P_CHP_H[self.resource_id_model, t].value for t in range(self.hours)],
            "U_CHP_G (kW)": [m.U_CHP_G[self.resource_id_model, t].value
                             if (self.system_reserves_participation or self.system_flexibility_participation) and
                             self.resource_reserves_participation else 0 for t in range(self.hours)],
            "U_CHP_E (kW)": [m.U_CHP_E[self.resource_id_model, t].value
                             if (self.system_reserves_participation or self.system_flexibility_participation) and
                             self.resource_reserves_participation else 0 for t in range(self.hours)],
            "U_CHP_H (kW)": [m.U_CHP_H[self.resource_id_model, t].value
                             if (self.system_reserves_participation or self.system_flexibility_participation) and
                             self.resource_reserves_participation else 0 for t in range(self.hours)],
            "D_CHP_G (kW)": [m.D_CHP_G[self.resource_id_model, t].value
                             if (self.system_reserves_participation or self.system_flexibility_participation) and
                             self.resource_reserves_participation else 0 for t in range(self.hours)],
            "D_CHP_E (kW)": [m.D_CHP_E[self.resource_id_model, t].value
                             if (self.system_reserves_participation or self.system_flexibility_participation) and
                             self.resource_reserves_participation else 0 for t in range(self.hours)],
            "D_CHP_H (kW)": [m.D_CHP_H[self.resource_id_model, t].value
                             if (self.system_reserves_participation or self.system_flexibility_participation) and
                             self.resource_reserves_participation else 0 for t in range(self.hours)],
        })
        if not df.empty:
            df.to_excel(writer, sheet_name=f'CHP_{self.resource_id_original}', index=False)

        return writer
