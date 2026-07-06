from pyomo.environ import ConcreteModel, NonNegativeReals, Reals, Var, Expression

from project.resources_models.resources_hydrogenstorage import HydrogenStorage
from project.resources_models.resources_electrolyzer import Electrolyzer
from project.resources_models.loads_hydrogen import HydrogenLoad

class EnergyBalance:
    """
    Adds energy balance constraints for thermal and hydrogen systems.

    This class is responsible for:
    - Ensuring thermal outputs and demands are balanced at each time step.
    - Ensuring hydrogen production (electrolyzers, storage) meets hydrogen loads.

    Args:
        bidding_time (int): Time horizon length (e.g., 24 for daily).
        resources (list): List of all model resource objects.
    """
    def __init__(self, bidding_time: int, resources: list) -> None:
        self.bidding_time = bidding_time
        self.resources = resources

    def create_constraints(self, model: ConcreteModel) -> None:
        """Defines the bidding variables and constraints in the optimization model."""
        self.create_constraints_energy_balance_thermal(model)
        self.create_constraints_energy_balance_hydrogen(model)

    def create_constraints_energy_balance_thermal(self, model: ConcreteModel) -> None:
        """
        Enforces thermal energy balance for each time step.

        Total thermal output of all resources must sum to zero (e.g., production = consumption).
        """
        for t in range(self.bidding_time):
            thermal_outputs = []
            for resource in self.resources:
                if hasattr(resource, "get_thermal_output"):
                    expr = resource.get_thermal_output(model, t)
                    # Only keep Pyomo expressions or Vars
                    if isinstance(expr, (Var, Expression)) or hasattr(expr, "is_expression_type"):
                        thermal_outputs.append(expr)

            if thermal_outputs:
                resources_power = sum(thermal_outputs)
                model.c1.add(resources_power == 0)

    def create_constraints_energy_balance_hydrogen(self, model: ConcreteModel) -> None:
        """
        Enforces hydrogen energy balance for each time step.

        The sum of hydrogen production (electrolyzers + storage discharge)
        must equal the total hydrogen load and consumption from fuel cell.

        The model must have these variables:
            - model.P_EL_H2V_H2[r, t] for electrolyzers
            - model.P_sto_H2_H2V[r, t] for hydrogen storage
            - model.P_load_hydrogen[r, t] for hydrogen-consuming loads
        """
        for t in range(self.bidding_time):
            resources_power = 0
            # Sum hydrogen production from electrolyzers to hydrogen vehicles
            if hasattr(model, "P_EL_H2V_H2"):
                resources_power += sum(model.P_EL_H2V_H2[r, t] for r in range(Electrolyzer.resource_count))
            # Sum hydrogen discharge from hydrogen storage to hydrogen vehicles
            if hasattr(model, "P_sto_H2_H2V"):
                resources_power += sum(model.P_sto_H2_H2V[r, t] for r in range(HydrogenStorage.resource_count))
            # Hydrogen vehicles load must be equal to the production of hydrogen
            if hasattr(model, "P_load_hydrogen"):
                model.c1.add(sum(model.P_load_hydrogen[r, t] for r in range(HydrogenLoad.resource_count)) ==
                             resources_power)
