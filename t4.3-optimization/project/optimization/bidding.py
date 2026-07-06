from pyomo.environ import ConcreteModel, NonNegativeReals, Reals, Var, Objective, minimize
from numpy import arange
from typing import Callable, Generator, Tuple


class Bidding:
    """
    Handles the bidding process in the optimization model.

    This class:
    - Defines bidding-related variables (electricity, gas, reserves).
    - Aggregates resource-level outputs into market bids.
    - Constructs constraints for energy and reserve participation.
    - Defines the total cost objective function.

    Args:
        prices (dict): Dictionary of market prices per time step (energy, reserves, gas).
        bidding_time (int): Number of time periods (e.g., 24 for daily).
        system_reserves_participation (int): 1 if reserves market is considered, 0 otherwise.
        resources (list): List of resource objects that implement the required output methods.
        ratio_upward_downward_reserve (int): Multiplier relating up/down reserve capacity.
    """

    def __init__(self, prices: dict, bidding_time: int, system_reserves_participation: int,
                 system_flexibility_participation: int,
                 resources: list, ratio_upward_downward_reserve: int) -> None:
        self.prices = prices
        self.bidding_time = bidding_time
        self.system_reserves_participation = system_reserves_participation
        self.system_flexibility_participation = system_flexibility_participation
        self.resources = resources
        self.ratio_upward_downward_reserve = ratio_upward_downward_reserve

    def create_bidding(self, model: ConcreteModel) -> None:
        """
        Main entry point to add bidding logic to the Pyomo model.

        Steps:
        - Define bidding-related variables
        - Add constraints for electricity, gas, and reserve markets
        - Define objective function
        - Aggregate all bid components into a total cost
        """
        self.create_variables_bidding(model)

        self.create_constraints_bids_electricity_energy(model)
        self.create_constraints_bids_gas(model)
        self.create_constraints_bids_biomass(model)

        if self.system_reserves_participation:
            self.create_constraints_market(model)
            self.create_constraints_bids_electricity_reserves(model)

        if self.system_flexibility_participation:
            self.create_constraints_market(model)
            self.create_constraints_bids_electricity_reserves(model)

        self.define_objective(model)

        self.aggregate_all_bids(model)

    def create_variables_bidding(self, model: ConcreteModel) -> None:
        """Define bidding-related variables."""
        model.P_bidding = Var(arange(self.bidding_time), domain=Reals)
        model.P_bidding_electricity = Var(arange(self.bidding_time), domain=Reals)
        model.P_bidding_gas = Var(arange(self.bidding_time), domain=NonNegativeReals)
        model.P_bidding_biomass = Var(arange(self.bidding_time), domain=NonNegativeReals)
        model.P_bidding_reserves = Var(arange(self.bidding_time), domain=Reals)
        model.P_E = Var(range(self.bidding_time), domain=Reals)
        model.P_G = Var(range(self.bidding_time), domain=NonNegativeReals)
        model.P_biomass = Var(range(self.bidding_time), domain=NonNegativeReals)

        if self.system_reserves_participation or self.system_flexibility_participation:
            model.U_E = Var(arange(self.bidding_time), domain=NonNegativeReals)
            model.D_E = Var(arange(self.bidding_time), domain=NonNegativeReals)

    def _aggregate_resource_output(self, model: ConcreteModel, output_getter: Callable) -> Generator[
        Tuple[int, float], None, None]:
        """Generic method to aggregate resource outputs"""
        for t in range(self.bidding_time):
            total_power = sum(output_getter(resource, model, t) for resource in self.resources)
            yield t, total_power

    def _create_aggregation_constraints(self, model: ConcreteModel, model_var, output_getter: Callable) -> None:
        """Helper method to create aggregation constraints for any resource output type."""
        for t, total_power in self._aggregate_resource_output(model, output_getter):
            model.c1.add(model_var[t] == total_power)

    def create_constraints_bids_electricity_energy(self, model: ConcreteModel) -> None:
        """Aggregate electricity energy bids."""
        self._create_aggregation_constraints(model=model, model_var=model.P_E,
                                             output_getter=lambda resource, model, t: resource.get_electricity_output(
                                                 model, t))

    def create_constraints_bids_gas(self, model: ConcreteModel) -> None:
        """Aggregate gas energy bids."""
        self._create_aggregation_constraints(model=model, model_var=model.P_G,
                                             output_getter=lambda resource, model, t: resource.get_gas_output(model, t))

    def create_constraints_bids_biomass(self, model: ConcreteModel) -> None:
        """Aggregate biomass energy bids."""
        self._create_aggregation_constraints(model=model, model_var=model.P_biomass,
                                             output_getter=lambda resource, model, t: resource.get_biomass_output(model,
                                                                                                                  t))

    def create_constraints_bids_electricity_reserves(self, model: ConcreteModel) -> None:
        """Aggregate electricity reserve bids."""
        self._create_aggregation_constraints(model=model, model_var=model.U_E,
                                             output_getter=lambda resource, model,
                                                                  t: resource.get_upward_reserve_output(model, t))
        self._create_aggregation_constraints(model=model, model_var=model.D_E,
                                             output_getter=lambda resource, model,
                                                                  t: resource.get_downward_reserve_output(model, t))

    def aggregate_all_bids(self, model: ConcreteModel) -> None:
        """Aggregate all bids including reserves if applicable."""
        for t in range(self.bidding_time):
            model.c1.add(model.P_bidding_electricity[t] == self.prices["Energy"][t] * model.P_E[t])

            if self.system_reserves_participation:
                model.c1.add(model.P_bidding_reserves[t] == - (
                        self.prices["Secondary band"][t] * (model.U_E[t] + model.D_E[t])
                        + (self.prices["Downward activation"][t] * self.prices["Ratio down"][t] * model.D_E[t]
                           - self.prices["Upward activation"][t] * self.prices["Ratio up"][t] * model.U_E[t])
                ))
            elif self.system_flexibility_participation:
                model.c1.add(model.P_bidding_reserves[t] == - (
                        self.prices["Secondary band"][t] * (model.U_E[t] + model.D_E[t])

                ))
            else:
                model.c1.add(model.P_bidding_reserves[t] == 0)

            model.c1.add(model.P_bidding_gas[t] == self.prices["Gas"][t] * model.P_G[t])

            model.c1.add(model.P_bidding_biomass[t] == self.prices["Biomass"][t] * model.P_biomass[t])

            model.c1.add(model.P_bidding[t] == model.P_bidding_electricity[t]
                         + model.P_bidding_reserves[t]
                         + model.P_bidding_gas[t]
                         + model.P_bidding_biomass[t]
                         )

    def create_constraints_market(self, model: ConcreteModel) -> None:
        """Define market constraints."""
        for t in range(self.bidding_time):
            model.c1.add(model.U_E[t] == self.ratio_upward_downward_reserve * model.D_E[t])

    def define_objective(self, model: ConcreteModel) -> None:
        """Define objective function for the model."""
        model.value = Objective(
            expr=sum(model.P_bidding[t] for t in range(0, self.bidding_time)),
            sense=minimize,
        )
