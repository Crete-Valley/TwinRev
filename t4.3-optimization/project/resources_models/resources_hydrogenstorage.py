import sys

from pyomo.environ import ConcreteModel, NonNegativeReals, Var, Binary
from numpy import arange
import pandas as pd

from project.resources_models.resources import Resource


class HydrogenStorage(Resource):
    resource_count = 0
    def __init__(
        self,
        resource_id_original: int,
        resource_id_model: int,
        system_reserves_participation: int,
        system_flexibility_participation: int,
        resource_reserves_participation: int,
        hours: int,
        max_capacity: float,
        min_capacity: float,
        initial_SOC: float,
        max_power: float,
        efficiency_ch: float,
        efficiency_dis: float,
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
        HydrogenStorage.resource_count += 1
        self.max_capacity = max_capacity
        self.min_capacity = min_capacity
        self.initial_SOC = initial_SOC
        self.max_power = max_power
        self.efficiency_ch = efficiency_ch
        self.efficiency_dis = efficiency_dis
        self.type = "Battery"


    def __repr2__(self, abbreviated: int = 1) -> str:
            return repr(
                f"Max capacity {self.units}: {self.max_capacity} |"
                f"Min capacity {self.units}: {self.min_capacity} |"
                f"Initial SOC {self.units}: {self.initial_SOC} |"
                f"Max power {self.units}: {self.max_power} |"
                f"Efficiency charging: {self.efficiency_ch} |"
                f"Efficiency discharging: {self.efficiency_dis} |"
                f"Reserves participation: {['No', 'Yes'][self.resource_reserves_participation]} | "
                f"{self.__class__.__module__}.{self.__class__.__name__} object at {hex(id(self))} with "
                f"{sys.getsizeof(self)} bits of memory"
            )


    ##########################################################################################
    # Define PV optimization model
    ##########################################################################################
    def get_variables(self, model) -> None:
        if getattr(model, "SOC_sto_H2", False):
            return
        self._create_variables_energy(model, HydrogenStorage.resource_count)
        self._create_reserves_variables_reserve(model, HydrogenStorage.resource_count)

    def get_constraints(self, model) -> None:
        self._create_constraint_profile(model)
        self._create_constraint_reserves(model)


    def _create_variables_energy(self, model, resources_count) -> None:
        """Create variables for pyomo model"""
        m = model
        m.SOC_sto_H2 = Var(arange(resources_count), arange(self.hours + 1), domain=NonNegativeReals)
        m.P_sto_H2_ch = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)
        m.P_sto_H2_dis = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)
        m.b_sto_H2_ch = Var(arange(resources_count), arange(self.hours), domain=Binary)
        m.b_sto_H2_dis = Var(arange(resources_count), arange(self.hours), domain=Binary)
        m.P_sto_H2_H2V = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)
        if not hasattr(model, "P_sto_H2_FC"):
            m.P_sto_H2_FC = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)



    def _create_reserves_variables_reserve(self, model, resources_count) -> None:
        """Create variables for pyomo model"""
        m = model
        if (self.system_reserves_participation or self.system_flexibility_participation) and self.resource_reserves_participation:

            m.U_sto_H2_ch = Var(arange(resources_count), arange(self.hours + 1), domain=NonNegativeReals)
            m.U_sto_H2_dis = Var(arange(resources_count), arange(self.hours + 1), domain=NonNegativeReals)
            m.D_sto_H2_ch = Var(arange(resources_count), arange(self.hours + 1), domain=NonNegativeReals)
            m.D_sto_H2_dis = Var(arange(resources_count), arange(self.hours + 1), domain=NonNegativeReals)



    def _create_constraint_profile(self, model) -> None:
        m = model
        for t in range(0, self.hours):
            m.c1.add(m.SOC_sto_H2[self.resource_id_model, t + 1] == m.SOC_sto_H2[self.resource_id_model, t] + (m.P_sto_H2_ch[self.resource_id_model, t] * self.efficiency_ch -
                                                             m.P_sto_H2_dis[self.resource_id_model, t] / self.efficiency_dis))
            m.c1.add(m.SOC_sto_H2[self.resource_id_model, t + 1] <= self.max_capacity)
            m.c1.add(m.SOC_sto_H2[self.resource_id_model, t + 1] >= self.min_capacity)

            m.c1.add(m.P_sto_H2_ch[self.resource_id_model, t] == m.P_EL_sto_H2[self.resource_id_model, t])
            m.c1.add(m.P_sto_H2_dis[self.resource_id_model, t] == m.P_sto_H2_H2V[self.resource_id_model, t] + m.P_sto_H2_FC[self.resource_id_model, t])

            m.c1.add(m.P_sto_H2_ch[self.resource_id_model, t] <= m.b_sto_H2_ch[self.resource_id_model, t] * self.max_power)
            m.c1.add(m.P_sto_H2_dis[self.resource_id_model, t] <= m.b_sto_H2_dis[self.resource_id_model, t] * self.max_power)

            m.c1.add(m.b_sto_H2_ch[self.resource_id_model, t] + m.b_sto_H2_dis[self.resource_id_model, t] <= 1)

        m.c1.add(m.SOC_sto_H2[self.resource_id_model, 0] == self.initial_SOC)
        m.c1.add(m.SOC_sto_H2[self.resource_id_model, self.hours] == self.initial_SOC)



    def _create_constraint_reserves(self, model) -> None:
        if (self.system_reserves_participation or self.system_flexibility_participation) and self.resource_reserves_participation:

            m = model
            for t in range(0, self.hours):
                m.c1.add(m.D_EL_sto_H2[self.resource_id_model, t] <= self.max_power - m.P_sto_H2_ch[self.resource_id_model, t])
                m.c1.add(m.U_EL_sto_H2[self.resource_id_model, t] <= m.P_sto_H2_ch[self.resource_id_model, t])
                m.c1.add(m.D_sto_H2_FC[self.resource_id_model, t] <= m.P_sto_H2_FC[self.resource_id_model, t])
                m.c1.add(m.U_sto_H2_FC[self.resource_id_model, t] <= self.max_power - m.P_sto_H2_dis[self.resource_id_model, t])
                m.c1.add(m.D_EL_sto_H2[self.resource_id_model, t] + m.D_sto_H2_FC[self.resource_id_model, t] <= self.max_capacity - m.SOC_sto_H2[self.resource_id_model, t + 1])
                m.c1.add(m.U_EL_sto_H2[self.resource_id_model, t] + m.U_sto_H2_FC[self.resource_id_model, t] <= m.SOC_sto_H2[self.resource_id_model, t + 1] - self.min_capacity)

            m.c1.add(m.U_sto_H2_ch[self.resource_id_model, self.hours] == 0)
            m.c1.add(m.D_sto_H2_ch[self.resource_id_model, self.hours] == 0)
            m.c1.add(m.U_sto_H2_dis[self.resource_id_model, self.hours] == 0)
            m.c1.add(m.D_sto_H2_dis[self.resource_id_model, self.hours] == 0)

    def save_results(self, model, writer):
        m = model
        df = pd.DataFrame({
            "Hour": [t + 1 for t in range(self.hours)],
            "SOC_sto_H2 (kW)": [m.SOC_sto_H2[self.resource_id_model, t + 1].value for t in range(self.hours)],
            "P_sto_H2_ch (kW)": [m.P_sto_H2_ch[self.resource_id_model, t].value for t in range(self.hours)],
            "P_sto_H2_dis (kW)": [m.P_sto_H2_dis[self.resource_id_model, t].value for t in range(self.hours)],
            "P_sto_H2_H2V (kW)": [m.P_sto_H2_H2V[self.resource_id_model, t].value for t in range(self.hours)],
            "P_sto_H2_FC (kW)": [m.P_sto_H2_FC[self.resource_id_model, t].value for t in range(self.hours)],
            "b_sto_H2_ch": [m.b_sto_H2_ch[self.resource_id_model, t].value for t in range(self.hours)],
            "b_sto_H2_dis": [m.b_sto_H2_dis[self.resource_id_model, t].value for t in range(self.hours)],
            "U_sto_H2_ch (kW)": [m.U_sto_H2_ch[self.resource_id_model, t].value
                                         if (self.system_reserves_participation or self.system_flexibility_participation) and
                                            self.resource_reserves_participation else 0 for t in range(self.hours)],
            "D_sto_H2_ch (kW)": [m.D_sto_H2_ch[self.resource_id_model, t].value
                                            if (self.system_reserves_participation or self.system_flexibility_participation) and
                                                self.resource_reserves_participation else 0 for t in range(self.hours)],
            "U_sto_H2_dis (kW)": [m.U_sto_H2_dis[self.resource_id_model, t].value
                                            if (self.system_reserves_participation or self.system_flexibility_participation) and
                                                self.resource_reserves_participation else 0 for t in range(self.hours)],
            "D_sto_H2_dis (kW)": [m.D_sto_H2_dis[self.resource_id_model, t].value
                                            if (self.system_reserves_participation or self.system_flexibility_participation) and
                                                self.resource_reserves_participation else 0 for t in range(self.hours)],



        })
        if not df.empty:
            df.to_excel(writer, sheet_name=f'TankHydrogen_{self.resource_id_original}', index=False)

        return writer

