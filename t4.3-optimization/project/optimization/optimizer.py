"""
Orchestrates the complete optimization workflow.

This module:
- Loads data from the input Excel file
- Initializes energy resources
- Sets up the bidding and energy balance components
- Builds and solves the optimization model using Pyomo

Returns the solved model, cost, computation time, and initialized resources.
"""
from project.config import BIDDING_TIME
from project.initialize_resources import initialize_resources
from project.optimization.optimization_model import OptimizationModel
from project.optimization.bidding import Bidding
from project.optimization.energy_balance import EnergyBalance
from project.helper.helper import log_and_print


JSON_FOLDER = "json"


def run_optimization(data_loader, bidding_time: int, system_reserves_participation: int,
                     system_flexibility_participation: int,
                     solver: str, ratio_upward_downward_reserve: float) -> tuple:
    """
    Run the full optimization routine using Pyomo.

    Steps:
    - Load input data (resource specs and market prices)
    - Initialize resource objects
    - Create bidding and energy balance components
    - Build and solve the Pyomo model

    Args:
        data_loader: Instance of DataLoader, already initialized with file path and bidding_time.
        bidding_time (int): Number of hourly time steps in the horizon.
        system_reserves_participation (int): 1 if reserves are considered, 0 otherwise.
        solver (str): Name of the solver (e.g., "cplex", "glpk").
        ratio_upward_downward_reserve (float): Ratio between upward and downward reserve needs.

    Returns:
        tuple:
            - results (ConcreteModel): Solved Pyomo model with all variables.
            - cost_value (float): Objective value (total cost).
            - computation_time (float): Solver wall time in seconds.
            - resources (list): List of resource objects used in the model.
    """

    # Read resource and prices data from Excel
    resource_data_list, prices = data_loader.load_data()

    # Initialize resources with their respective parameters from data
    resources = initialize_resources(resource_data_list, bidding_time, system_reserves_participation,
                                     system_flexibility_participation)

    # Create bidding model
    bidding = Bidding(resources=resources, prices=prices, bidding_time=bidding_time,
                      system_reserves_participation=system_reserves_participation,
                      system_flexibility_participation=system_flexibility_participation,
                      ratio_upward_downward_reserve=ratio_upward_downward_reserve)
    energy_balance = EnergyBalance(resources=resources, bidding_time=bidding_time)

    # Create optimization model
    model = OptimizationModel(resources=resources, prices=prices, bidding=bidding, energy_balance=energy_balance,
                              bidding_time=bidding_time, system_reserves_participation=system_reserves_participation,
                              solver=solver)

    # Build the model
    model.build_model()

    # Solve the model
    log_and_print("Solving the optimization problem...")
    results, cost_value, computation_time = model.solve_model()

    return results, cost_value, computation_time, resources
