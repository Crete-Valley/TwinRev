from fastapi import FastAPI
import os
import json
import threading
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from project.optimization.optimizer import run_optimization
from utils.db_loader import fetch_pv_data
from utils.json_loader import JsonDataLoader  # wrapper that mimics DataLoader
from project.config import (SYSTEM_RESERVES_PARTICIPATION, SYSTEM_FLEXIBILITY_PARTICIPATION,
                            RATIO_UPWARD_DOWNWARD_RESERVE, SOLVER, BIDDING_TIME, INPUT_FILE_JSON,
                            OUTPUT_WITH_RESERVES, OUTPUT_NO_RESERVES, OUTPUT_WITH_RESERVES_DEBUG,
                            OUTPUT_NO_RESERVES_DEBUG, OUTPUT_WITH_FLEXIBILITY,
                            OUTPUT_WITH_FLEXIBILITY_DEBUG)
from project.helper.helper import log_and_print
from project.save_results import save_model_variables_to_excel_debugging, save_model_to_excel

load_dotenv()

app = FastAPI()

origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pyomo's output capture (TeeStream) is process-global and not thread-safe:
# two concurrent runs deadlock its reader threads. Serialize the endpoint.
_optimize_lock = threading.Lock()


@app.get("/optimize")
def optimize():
    with _optimize_lock:
        return _optimize()


def _optimize():
    initial_logging()
    # Directory of app.py
    service_dir = os.path.dirname(os.path.abspath(__file__))

    # Go to the main folder
    main_dir = os.path.dirname(service_dir)

    # Build the path to project/data_inputs/data_inputs_cell.json
    INPUT_FILE_PATH = os.path.join(main_dir, "project", INPUT_FILE_JSON)

    if not os.path.exists(INPUT_FILE_PATH):
        raise RuntimeError(f"Input file '{INPUT_FILE_PATH}' not found!")

    try:
        with open(INPUT_FILE_PATH, "r", encoding="utf-8") as f:
            json_inputs = json.load(f)
    except json.JSONDecodeError as e:
        return {"status": "error", "message": f"Failed to parse JSON file: {e}"}

    try:
        energy_resources, pv_generation = fetch_pv_data()

        # Merge PV energy resources
        if "Energy resources" in json_inputs and isinstance(json_inputs["Energy resources"], list):
            json_inputs["Energy resources"].extend(energy_resources)
        else:
            json_inputs["Energy resources"] = energy_resources

        # Merge PV generation
        if "PV generation" in json_inputs and isinstance(json_inputs["PV generation"], list):
            json_inputs["PV generation"].extend(pv_generation)
        else:
            json_inputs["PV generation"] = pv_generation

        print("Database data successfully merged into JSON inputs.")
    except Exception as e:
        print(f"Warning: Failed to load DB data — {e}")

    # 2. Convert JSON → DataLoader-like
    data_loader = JsonDataLoader(json_inputs, bidding_time=BIDDING_TIME)
    log_and_print("Data loaded successfully from data-service.")

    # 3. Run optimization
    results, cost, runtime, resources = run_optimization(
        data_loader=data_loader,
        bidding_time=BIDDING_TIME,
        system_reserves_participation=SYSTEM_RESERVES_PARTICIPATION,
        system_flexibility_participation=SYSTEM_FLEXIBILITY_PARTICIPATION,
        solver=SOLVER,
        ratio_upward_downward_reserve=RATIO_UPWARD_DOWNWARD_RESERVE
    )
    # 4. Extract P_E, U_PV and D_PV
    P_E = [results.P_E[t].value for t in range(BIDDING_TIME)]

    # 5. Save model variables to Excel
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

    if SYSTEM_RESERVES_PARTICIPATION or SYSTEM_FLEXIBILITY_PARTICIPATION:
        U_E = [results.U_E[t].value for t in range(BIDDING_TIME)]
        D_E = [results.D_E[t].value for t in range(BIDDING_TIME)]
        # 6. Return results
        return {
            "status": "success",
            "P_E": P_E,
            "U_E": U_E,
            "D_E": D_E,
            "cost": cost,
            "runtime": runtime
        }
    else:
        # 6. Return results
        return {
            "status": "success",
            "P_E": P_E,
            "cost": cost,
            "runtime": runtime
        }


def initial_logging():
    """Log initial configuration settings."""
    log_and_print("")
    log_and_print("========== Run Configuration ==========")
    log_and_print(f"Solver: {SOLVER}")
    log_and_print(f"Bidding time: {BIDDING_TIME} hours")
    log_and_print(f"Reserves participation: {'Yes' if SYSTEM_RESERVES_PARTICIPATION else 'No'}")
    log_and_print(f"Flexibility participation: {'Yes' if SYSTEM_FLEXIBILITY_PARTICIPATION else 'No'}")
    log_and_print(f"Input file: {INPUT_FILE_JSON.name}")
    log_and_print("=======================================")
