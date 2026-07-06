import sys

from pyomo.environ import ConcreteModel, NonNegativeReals, Var, Binary
from numpy import arange
import pandas as pd

from project.resources_models.resources import Resource


class Battery(Resource):
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
        max_power_charging: float,
        max_power_discharging: float,
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
        Battery.resource_count += 1
        self.max_capacity = max_capacity
        self.min_capacity = min_capacity
        self.initial_SOC = initial_SOC
        self.max_power_charging = max_power_charging
        self.max_power_discharging = max_power_discharging
        self.efficiency_ch = efficiency_ch
        self.efficiency_dis = efficiency_dis
        self.type = "Battery"


    def __repr2__(self, abbreviated: int = 1) -> str:
            return repr(
                f"Max capacity {self.units}: {self.max_capacity} |"
                f"Min capacity {self.units}: {self.min_capacity} |"
                f"Initial SOC {self.units}: {self.initial_SOC} |"
                f"Max power charging {self.units}: {self.max_power_charging} |"
                f"Max power discharging {self.units}: {self.max_power_discharging} |"
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
        if getattr(model, "SOC_sto_E", False):
            return
        self._create_variables_energy(model, Battery.resource_count)
        self._create_reserves_variables_reserve(model, Battery.resource_count)

    def get_constraints(self, model) -> None:
        self._create_constraint_profile(model)
        self._create_constraint_reserves(model)


    def _create_variables_energy(self, model, resources_count) -> None:
        """Create variables for pyomo model"""
        m = model
        m.SOC_sto_E = Var(arange(resources_count), arange(self.hours + 1), domain=NonNegativeReals)
        m.P_sto_E_ch = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)
        m.P_sto_E_dis = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)
        m.P_sto_E_ch_space = Var(arange(resources_count), arange(self.hours + 1), domain=NonNegativeReals)
        m.P_sto_E_dis_space = Var(arange(resources_count), arange(self.hours + 1), domain=NonNegativeReals)
        m.b_sto_E_ch = Var(arange(resources_count), arange(self.hours), domain=Binary)
        m.b_sto_E_space = Var(arange(resources_count), arange(self.hours), domain=Binary)



    def _create_reserves_variables_reserve(self, model, resources_count) -> None:
        """Create variables for pyomo model"""
        m = model
        if (self.system_reserves_participation or self.system_flexibility_participation) and self.resource_reserves_participation:

            m.U_sto_E_ch = Var(arange(resources_count), arange(self.hours + 1), domain=NonNegativeReals)
            m.U_sto_E_dis = Var(arange(resources_count), arange(self.hours + 1), domain=NonNegativeReals)
            m.D_sto_E_ch = Var(arange(resources_count), arange(self.hours + 1), domain=NonNegativeReals)
            m.D_sto_E_dis = Var(arange(resources_count), arange(self.hours + 1), domain=NonNegativeReals)



    def _create_constraint_profile(self, model) -> None:
        m = model
        for t in range(0, self.hours):
            m.c1.add(m.SOC_sto_E[self.resource_id_model, t + 1] == m.SOC_sto_E[self.resource_id_model, t] +
                     (m.P_sto_E_ch[self.resource_id_model, t] * self.efficiency_ch -
                                                             m.P_sto_E_dis[self.resource_id_model, t] / self.efficiency_dis))
            m.c1.add(m.SOC_sto_E[self.resource_id_model, t + 1] <= self.max_capacity)
            m.c1.add(m.SOC_sto_E[self.resource_id_model, t + 1] >= self.min_capacity)


            m.c1.add(m.P_sto_E_ch[self.resource_id_model, t] + m.P_sto_E_ch_space[self.resource_id_model, t] <=
                     m.b_sto_E_ch[self.resource_id_model, t] * self.max_power_charging)
            m.c1.add(m.P_sto_E_dis[self.resource_id_model, t] + m.P_sto_E_dis_space[self.resource_id_model, t] <=
                     (1 - m.b_sto_E_ch[self.resource_id_model, t]) * self.max_power_discharging)

        m.c1.add(m.SOC_sto_E[self.resource_id_model, 0] == self.initial_SOC)
        m.c1.add(m.SOC_sto_E[self.resource_id_model, self.hours] == self.initial_SOC)



    def _create_constraint_reserves(self, model) -> None:
        if (self.system_reserves_participation or self.system_flexibility_participation) and self.resource_reserves_participation:

            m = model
            for t in range(0, self.hours):
                m.c1.add(m.U_sto_E_dis[self.resource_id_model, t] <= self.max_power_discharging -
                         m.P_sto_E_dis[self.resource_id_model, t])
                m.c1.add(m.D_sto_E_dis[self.resource_id_model, t] <= m.P_sto_E_dis[self.resource_id_model, t])
                m.c1.add(m.U_sto_E_ch[self.resource_id_model, t] <=m.P_sto_E_ch[self.resource_id_model, t])
                m.c1.add(m.D_sto_E_ch[self.resource_id_model, t] <= self.max_power_charging - m.P_sto_E_ch[self.resource_id_model, t])

                m.c1.add(m.U_sto_E_dis[self.resource_id_model, t] / self.efficiency_dis + m.U_sto_E_ch[self.resource_id_model, t] * self.efficiency_ch <=
                         m.SOC_sto_E[self.resource_id_model, t] - self.min_capacity)
                m.c1.add(m.D_sto_E_dis[self.resource_id_model, t] / self.efficiency_dis + m.D_sto_E_ch[self.resource_id_model, t] * self.efficiency_ch <=
                            self.max_capacity - m.SOC_sto_E[self.resource_id_model, t])

                m.c1.add(m.U_sto_E_ch[self.resource_id_model, t] + m.D_sto_E_dis[self.resource_id_model, t] +
                         m.U_sto_E_dis[self.resource_id_model, t] + m.D_sto_E_ch[self.resource_id_model, t] <=
                         m.P_sto_E_ch_space[self.resource_id_model, t + 1] + m.P_sto_E_dis_space[self.resource_id_model, t + 1])
                m.c1.add(m.U_sto_E_ch[self.resource_id_model, t] + m.D_sto_E_dis[self.resource_id_model, t] +
                         m.U_sto_E_dis[self.resource_id_model, t] + m.D_sto_E_ch[self.resource_id_model, t] <=
                         1000000000 * m.b_sto_E_space[self.resource_id_model, t])
                m.c1.add(m.P_sto_E_ch_space[self.resource_id_model, t] + m.P_sto_E_dis_space[self.resource_id_model, t] <=
                         1000000000 * (1 - m.b_sto_E_space[self.resource_id_model, t]))

            m.c1.add(m.U_sto_E_ch[self.resource_id_model, self.hours] == 0)
            m.c1.add(m.D_sto_E_ch[self.resource_id_model, self.hours] == 0)
            m.c1.add(m.U_sto_E_dis[self.resource_id_model, self.hours] == 0)
            m.c1.add(m.D_sto_E_dis[self.resource_id_model, self.hours] == 0)

    def get_electricity_output(self, model, hour):
        return -model.P_sto_E_dis[self.resource_id_model, hour] + model.P_sto_E_ch[self.resource_id_model, hour]

    def get_upward_reserve_output(self, model, hour):
        if (self.system_reserves_participation or self.system_flexibility_participation) and self.resource_reserves_participation:

            return model.U_sto_E_dis[self.resource_id_model, hour] + model.U_sto_E_ch[self.resource_id_model, hour]
        else:
            return 0

    def get_downward_reserve_output(self, model, hour):
        if (self.system_reserves_participation or self.system_flexibility_participation) and self.resource_reserves_participation:

            return model.D_sto_E_dis[self.resource_id_model, hour] + model.D_sto_E_ch[self.resource_id_model, hour]
        else:
            return 0

    def save_results(self, model, writer):
        m = model
        df = pd.DataFrame({
            "Hour": [t + 1 for t in range(self.hours)],
            "SOC_sto_E (kWh)": [m.SOC_sto_E[self.resource_id_model, t].value for t in range(1, self.hours + 1)],
            "P_sto_E_ch (kWh)": [m.P_sto_E_ch[self.resource_id_model, t].value for t in range(self.hours)],
            "P_sto_E_dis (kWh)": [m.P_sto_E_dis[self.resource_id_model, t].value for t in range(self.hours)],
            "P_sto_E_ch_space (kWh)": [m.P_sto_E_ch_space[self.resource_id_model, t].value for t in range(self.hours)],
            "P_sto_E_dis_space (kWh)": [m.P_sto_E_dis_space[self.resource_id_model, t].value for t in range(self.hours)],
            "b_sto_E_ch": [m.b_sto_E_ch[self.resource_id_model, t].value for t in range(self.hours)],
            "b_sto_E_space": [m.b_sto_E_space[self.resource_id_model, t].value for t in range(self.hours)],
            "U_sto_E_ch (kWh)": [m.U_sto_E_ch[self.resource_id_model, t].value
                                 if (self.system_reserves_participation or self.system_flexibility_participation)
                                    and self.resource_reserves_participation else 0 for t in range(self.hours)],
            "U_sto_E_dis (kWh)": [m.U_sto_E_dis[self.resource_id_model, t].value
                                  if (self.system_reserves_participation or self.system_flexibility_participation)
                                     and self.resource_reserves_participation else 0 for t in range(self.hours)],
            "D_sto_E_ch (kWh)": [m.D_sto_E_ch[self.resource_id_model, t].value
                                 if (self.system_reserves_participation or self.system_flexibility_participation)
                                    and self.resource_reserves_participation else 0 for t in range(self.hours)],
            "D_sto_E_dis (kWh)": [m.D_sto_E_dis[self.resource_id_model, t].value
                                  if (self.system_reserves_participation or self.system_flexibility_participation)
                                     and self.resource_reserves_participation else 0 for t in range(self.hours)],

        })
        if not df.empty:
            df.to_excel(writer, sheet_name=f'Battery_{self.resource_id_original}', index=False)

        return writer

