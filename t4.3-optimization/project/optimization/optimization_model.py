import time
from abc import ABC
from typing import Optional, List, Dict, Any, Tuple
from pyomo.environ import (
    ConcreteModel,
    ConstraintList,
    Objective,
    SolverFactory,
    SolverStatus,
    TerminationCondition,
    minimize,
)


from project.helper.helper import log_and_print
from project.helper.exceptions import OptimizationError


class OptimizationModel(ABC):
    """
    Encapsulates the complete Pyomo optimization model lifecycle.

    This class:
    - Initializes a Pyomo ConcreteModel and shared constraint list.
    - Adds resource-specific variables and constraints.
    - Integrates bidding and energy balance components.
    - Solves the model using a specified solver.

    Args:
        resources (list): List of resource objects with Pyomo hooks (`get_variables`, `get_constraints`).
        prices (dict): Dictionary of time-indexed market prices.
        bidding (Bidding): Bidding logic handler (adds bidding variables, constraints, objective).
        energy_balance (EnergyBalance): Energy balancing logic (adds multi-energy carrier constraints).
        bidding_time (int): Time horizon of the problem (number of time steps).
        system_reserves_participation (int): 1 if reserves markets are considered, else 0.
        solver (str): Name of the Pyomo-compatible solver to use (e.g., "cplex", "glpk").
    """
    def __init__(self,
                 resources: Optional[List[Any]] = None,
                 prices: Optional[Dict[str, List[float]]] = None,
                 bidding: Optional[Any] = None,
                 energy_balance: Optional[Any] = None,
                 bidding_time: int = 24,
                 system_reserves_participation: int = 0,
                 solver: str = "cplex"):
        self.model = ConcreteModel()
        self.model.c1 = ConstraintList()

        self.resources = resources
        self.prices = prices
        self.bidding = bidding
        self.energy_balance = energy_balance
        self.bidding_time = bidding_time
        self.system_reserves_participation = system_reserves_participation
        self.solver = solver

    def build_model(self) -> None:
        """
        Build the full optimization model by:
        - Defining resource variables and constraints
        - Adding energy balance constraints
        - Adding bidding variables, constraints, and objective
        """
        self.define_resources_variables()
        self.define_resources_constraints()

        self.energy_balance.create_constraints(self.model)
        self.bidding.create_bidding(self.model)

    def define_resources_variables(self):
        """Call `get_variables()` on each resource to add its decision variables."""
        for resource in self.resources:
            resource.get_variables(self.model)

    def define_resources_constraints(self):
        """Call `get_constraints()` on each resource to add its constraints."""
        for resource in self.resources:
            resource.get_constraints(self.model)

    def solve_model(self) -> tuple:
        """
        Solve the optimization model using the configured solver.

        Returns:
            tuple:
                - ConcreteModel: Solved Pyomo model
                - float: Objective value (total cost)
                - float: Computation time in seconds

        Raises:
            OptimizationError: If solver fails or solution is not optimal
        """
        try:
            start_time = time.time()
            solver = SolverFactory(self.solver)
            results = solver.solve(self.model, tee=False)

            status = results.solver.status
            termination = results.solver.termination_condition

            if status == SolverStatus.ok and termination == TerminationCondition.optimal:
                log_and_print("Flow optimized")
            else:
                log_and_print(f"Solver status: {status}")
                log_and_print(f"Termination condition: {termination}")
                raise OptimizationError(
                    f"Model did not converge. Solver status: {status}, Termination: {termination}"
                )

            computation_time = time.time() - start_time
            log_and_print(f"Execution time={computation_time:.2f}")
            log_and_print(f"Cost= {self.model.value():.2f} €")

            return self.model, self.model.value(), computation_time

        except Exception as e:
            log_and_print(f"Optimization failed: {e}")
            raise OptimizationError(f"Optimization failed: {e}") from e
