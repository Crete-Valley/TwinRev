"""
Run the day-ahead optimization and export results.

This script:
  1) Loads input data from an Excel file.
  2) Builds and solves the optimization model.
  3) Exports model variables and summaries to Excel.

Assumptions/Constraints:
- All resource types must share the same reserves-participation setting
  (SYSTEM_RESERVES_PARTICIPATION). Mixed participation (e.g., PV1 yes, PV2 no)
  is not supported and will raise an error.

Configuration is read from `config.py`.
"""

from config import (
    INPUT_FILE, BIDDING_TIME, SYSTEM_RESERVES_PARTICIPATION, SYSTEM_FLEXIBILITY_PARTICIPATION,
    RATIO_UPWARD_DOWNWARD_RESERVE, SOLVER,
    OUTPUT_WITH_RESERVES, OUTPUT_NO_RESERVES,
    OUTPUT_WITH_RESERVES_DEBUG, OUTPUT_NO_RESERVES_DEBUG, OUTPUT_WITH_FLEXIBILITY,
    OUTPUT_WITH_FLEXIBILITY_DEBUG
)
from read_inputs import DataLoader
from optimization.optimizer import run_optimization
from save_results import save_model_variables_to_excel_debugging, save_model_to_excel
from helper.helper import log_and_print


def main():
    """Main function to run the optimization process."""

    # Initialize global model
    log_and_print("Starting optimization process...")
    initial_logging()

    # Read resource data from Excel
    log_and_print("Loading data...")
    data_loader = DataLoader(INPUT_FILE, BIDDING_TIME)

    # Run the optimization process
    log_and_print("Setting up the optimization model...")
    results, cost_value, computation_time, resources = run_optimization(
                     data_loader=data_loader,
                     bidding_time=BIDDING_TIME,
                     system_reserves_participation=SYSTEM_RESERVES_PARTICIPATION,
                     system_flexibility_participation=SYSTEM_FLEXIBILITY_PARTICIPATION,
                     solver=SOLVER,
                     ratio_upward_downward_reserve=RATIO_UPWARD_DOWNWARD_RESERVE)

    # Save model variables to Excel
    log_and_print("Saving results to Excel...")
    if SYSTEM_RESERVES_PARTICIPATION:
        OUTPUT_NAME = OUTPUT_WITH_RESERVES
        OUTPUT_NAME_DEBUGGING = OUTPUT_WITH_RESERVES_DEBUG
    elif SYSTEM_FLEXIBILITY_PARTICIPATION:
        OUTPUT_NAME = OUTPUT_WITH_FLEXIBILITY
        OUTPUT_NAME_DEBUGGING = OUTPUT_WITH_FLEXIBILITY_DEBUG
    else:
        OUTPUT_NAME = OUTPUT_NO_RESERVES
        OUTPUT_NAME_DEBUGGING = OUTPUT_NO_RESERVES_DEBUG

    save_model_variables_to_excel_debugging(model=results, file_name=OUTPUT_NAME_DEBUGGING)
    save_model_to_excel(model=results, resources=resources, file_name=OUTPUT_NAME)

    result = {"cost": cost_value, "run_time": computation_time}

def initial_logging():
    """Log initial configuration settings."""
    log_and_print("========== Run Configuration ==========")
    log_and_print(f"Solver: {SOLVER}")
    log_and_print(f"Bidding time: {BIDDING_TIME} hours")
    log_and_print(f"Reserves participation: {'Yes' if SYSTEM_RESERVES_PARTICIPATION else 'No'}")
    log_and_print(f"Input file: {INPUT_FILE.name}")
    log_and_print("=======================================")


if __name__ == "__main__":
    main()
