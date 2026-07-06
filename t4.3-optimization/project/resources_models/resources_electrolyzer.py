import sys

from numpy import arange
from pyomo.environ import ConcreteModel, NonNegativeReals, Var, Binary
import pandas as pd

from project.resources_models.resources import Resource


class Electrolyzer(Resource):
    resource_count = 0
    __slots__ = (
        "max_power",
        "efficiency",
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
        efficiency: float,
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
        Electrolyzer.resource_count += 1
        self.max_power = max_power
        self.efficiency = efficiency
        self.type = "Electrolyzer"


    def __repr2__(self, abbreviated: int = 1) -> str:
            return repr(
                f"Max capacity  {self.units}: {self.max_power} |"
                f"Efficiency: {self.efficiency} |"
                f"Reserves participation: {['No', 'Yes'][self.resource_reserves_participation]} | "
                f"{self.__class__.__module__}.{self.__class__.__name__} object at {hex(id(self))} with "
                f"{sys.getsizeof(self)} bits of memory"
            )


    ##########################################################################################
    # Define PV optimization model
    ##########################################################################################

    def get_variables(self, model) -> None:
        if getattr(model, "P_EL_E", False):
            return
        self._create_variables_energy(model, Electrolyzer.resource_count)
        self._create_reserves_variables_reserve(model, Electrolyzer.resource_count)

    def get_constraints(self, model) -> None:
        self._create_constraint_energy(model)
        self._create_constraint_reserves(model)



    def _create_variables_energy(self, model, resources_count) -> None:
        """Create variables for pyomo model"""
        m = model
        m.P_EL_E = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)
        m.P_EL_H2 = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)
        m.P_EL_H2V_H2 = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)
        m.P_EL_sto_H2 = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)


    def _create_reserves_variables_reserve(self, model, resources_count) -> None:
        """Create variables for pyomo model"""
        m = model
        if (self.system_reserves_participation or self.system_flexibility_participation) and self.resource_reserves_participation:

            m.U_EL_E = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)
            m.D_EL_E = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)
            m.U_EL_H2 = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)
            m.D_EL_H2 = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)
            m.U_EL_H2V_H2 = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)
            m.U_EL_sto_H2 = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)
            m.D_EL_H2V_H2 = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)
            m.D_EL_sto_H2 = Var(arange(resources_count), arange(self.hours), domain=NonNegativeReals)


    def _create_constraint_energy(self, model) -> None:
        m = model
        for t in range(0, self.hours):
            m.c1.add(m.P_EL_E[self.resource_id_model, t] <= self.max_power)
            m.c1.add(m.P_EL_H2[self.resource_id_model, t] == self.efficiency * m.P_EL_E[self.resource_id_model, t])
            m.c1.add(m.P_EL_H2[self.resource_id_model, t] == m.P_EL_H2V_H2[self.resource_id_model, t] + m.P_EL_sto_H2[self.resource_id_model, t])



    def _create_constraint_reserves(self, model) -> None:
        if (self.system_reserves_participation or self.system_flexibility_participation) and self.resource_reserves_participation:

            m = model
            for t in range(0, self.hours):
                    m.c1.add(m.U_EL_E[self.resource_id_model, t] <= m.P_EL_E[self.resource_id_model, t])
                    m.c1.add(m.D_EL_E[self.resource_id_model, t] <= self.max_power - m.P_EL_E[self.resource_id_model, t])

                    m.c1.add(m.U_EL_H2[self.resource_id_model, t] == self.efficiency * m.U_EL_E[self.resource_id_model, t])
                    m.c1.add(m.D_EL_H2[self.resource_id_model, t] == self.efficiency * m.D_EL_E[self.resource_id_model, t])
                    m.c1.add(m.U_EL_H2[self.resource_id_model, t] == m.U_EL_sto_H2[self.resource_id_model, t])
                    m.c1.add(m.D_EL_H2[self.resource_id_model, t] == m.D_EL_sto_H2[self.resource_id_model, t])

    def get_electricity_output(self, model, hour):
        return model.P_EL_E[self.resource_id_model, hour]

    def get_upward_reserve_output(self, model, hour):
        if (self.system_reserves_participation or self.system_flexibility_participation) and self.resource_reserves_participation:

            return model.U_EL_E[self.resource_id_model, hour]
        else:
            return 0

    def get_downward_reserve_output(self, model, hour):
        if (self.system_reserves_participation or self.system_flexibility_participation) and self.resource_reserves_participation:

            return model.D_EL_E[self.resource_id_model, hour]
        else:
            return 0

    def save_results(self, model, writer):
        m = model
        df = pd.DataFrame({
            "Hour": [t + 1 for t in range(self.hours)],
            "Electricity consumption - P_EL_E (kW)": [m.P_EL_E[self.resource_id_model, t].value for t in range(self.hours)],
            "Hydrogen production - P_EL_H2 (kW)": [m.P_EL_H2[self.resource_id_model, t].value for t in range(self.hours)],
            "Hydrogen to vehicle - P_EL_H2V_H2 (kW)": [m.P_EL_H2V_H2[self.resource_id_model, t].value for t in range(self.hours)],
            "Hydrogen to storage - P_EL_sto_H2 (kW)": [m.P_EL_sto_H2[self.resource_id_model, t].value for t in range(self.hours)],
            "Upward reserve electricity - U_EL_E (kW)": [m.U_EL_E[self.resource_id_model, t].value
                                                         if (self.system_reserves_participation or self.system_flexibility_participation) and
                                                            self.resource_reserves_participation else 0 for t in range(self.hours)],
            "Downward reserve electricity - D_EL_E (kW)": [m.D_EL_E[self.resource_id_model, t].value
                                                           if (self.system_reserves_participation or self.system_flexibility_participation)and
                                                              self.resource_reserves_participation else 0 for t in range(self.hours)],
            "Upward reserve hydrogen - U_EL_H2 (kW)": [m.U_EL_H2[self.resource_id_model, t].value
                                                       if (self.system_reserves_participation or self.system_flexibility_participation) and
                                                          self.resource_reserves_participation else 0 for t in range(self.hours)],
            "Downward reserve hydrogen - D_EL_H2 (kW)": [m.D_EL_H2[self.resource_id_model, t].value
                                                         if (self.system_reserves_participation or self.system_flexibility_participation) and
                                                            self.resource_reserves_participation else 0 for t in range(self.hours)],
            "Upward reserve hydrogen to storage - U_EL_sto_H2 (kW)": [m.U_EL_sto_H2[self.resource_id_model, t].value
                                                                      if (self.system_reserves_participation or self.system_flexibility_participation) and
                                                                         self.resource_reserves_participation else 0 for t in range(self.hours)],
            "Downward reserve hydrogen to storage - D_EL_sto_H2 (kW)": [m.D_EL_sto_H2[self.resource_id_model, t].value
                                                                        if (self.system_reserves_participation or self.system_flexibility_participation) and
                                                                           self.resource_reserves_participation else 0 for t in range(self.hours)],



        })
        if not df.empty:
            df.to_excel(writer, sheet_name=f'Electrolyzer_{self.resource_id_original}', index=False)

        return writer

