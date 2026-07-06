import pandas as pd
from pyomo.environ import *

from project.helper.helper import log_and_print


def save_model_variables_to_excel_debugging(model: ConcreteModel,
                                  file_name: str = "model_variables_horizontal.xlsx") -> None:
    """
    Save all Pyomo model variables to an Excel file with filtering by resource type.
    This sheet is for debugging purposes.

    - The main sheet ("All_Variables") includes all decision variables.
    - Additional sheets are created for specific resource types based on naming patterns.

    Args:
        model (ConcreteModel): The solved Pyomo model.
        file_name (str): Output Excel file name.
    """

    # Create a dictionary to store variable data
    variable_data = {}

    for var in model.component_objects(Var, active=True):  # Iterate over all active variables
        var_name = var.name
        variable_data[var_name] = {}  # Initialize a dictionary for each variable

        for index in var:
            value = var[index].value
            variable_data[var_name][index] = value

    # Convert the dictionary to a pandas DataFrame
    df = pd.DataFrame.from_dict(variable_data, orient="index")

    # Transpose so indices are rows and variables are columns
    df_t = df.transpose()


    # Save to Excel with multiple sheets
    with pd.ExcelWriter(file_name, engine="openpyxl") as writer:
        # Save all variables
        df_t.to_excel(writer, sheet_name="All_Variables", index_label="Index")

        # Save only columns containing 'PV'
        pv_columns = transform_df_resource(df_t.filter(like="PV"))
        if not pv_columns.empty:
            pv_columns.to_excel(writer, sheet_name="PV")
        # Save only columns containing 'WG'
        wg_columns = df_t.filter(like="WG")
        if not wg_columns.empty:
            wg_columns.to_excel(writer, sheet_name="Wind generator", index_label="Index")
        # Save only columns containing 'CHP'
        chp_columns = df_t.filter(like="CHP")
        if not chp_columns.empty:
            chp_columns.to_excel(writer, sheet_name="CHP", index_label="Index")
        # Save only columns containing 'sto_E'
        sto_e_columns = df_t.filter(like="sto_E")
        if not sto_e_columns.empty:
            sto_e_columns.to_excel(writer, sheet_name="Battery", index_label="Index")
        # Save only columns containing 'EL'
        el_columns = df_t.filter(like="EL")
        if not el_columns.empty:
            el_columns.to_excel(writer, sheet_name="Electrolyzer", index_label="Index")
        # Save only columns containing 'FC'
        fc_columns = df_t.filter(like="FC")
        if not fc_columns.empty:
            fc_columns.to_excel(writer, sheet_name="Fuel cell", index_label="Index")
        # Save only columns containing 'sto_H2'
        h2_columns = df_t.filter(like="sto_H2")
        if not h2_columns.empty:
            h2_columns.to_excel(writer, sheet_name="Hydrogen tank", index_label="Index")
        # Save only columns containing 'load'
        load_columns = df_t.filter(like="load")
        if not load_columns.empty:
            load_columns.to_excel(writer, sheet_name="Load", index_label="Index")
        # Save only columns containing 'HP'
        hp_columns = transform_df_resource(df_t.filter(like="HP"))
        if not hp_columns.empty:
            hp_columns.to_excel(writer, sheet_name="HP", index_label="Index")
        # Save only columns containing 'GeoExchanger'
        ge_columns = transform_df_resource(df_t.filter(like="GeoExchange"))
        if not ge_columns.empty:
            ge_columns.to_excel(writer, sheet_name="GeoExchange", index_label="Index")
        # Save only columns containing 'Boiler'
        boiler_columns = transform_df_resource(df_t.filter(like="Boiler"))
        if not boiler_columns.empty:
            boiler_columns.to_excel(writer, sheet_name="Boiler", index_label="Index")

    log_and_print(f"Model variables have been saved to {file_name}")


def save_model_to_excel(model: ConcreteModel, resources: list,
                                  file_name: str = "model_variables_horizontal.xlsx") -> None:
    """
    Save resource-specific results to Excel using each resource's internal method.

    This assumes each resource implements a `save_results(model, writer)` method
    that writes to the provided ExcelWriter instance.

    Args:
        model (ConcreteModel): The solved Pyomo model.
        resources (list): List of resource objects.
        file_name (str): Output Excel file name.
    """
    new_writer = pd.ExcelWriter(file_name, engine="openpyxl")
    for resource in resources:
        new_writer = resource.save_results(model, writer=new_writer)
    # save and close the writer
    new_writer.close()

    log_and_print(f"Model variables have been saved to {file_name}")



def transform_df_resource(df):
    """
    Transforms a DataFrame of Pyomo variables into a readable format:
    - Splits the multi-index column into 'id' and 'time'
    - Drops missing values
    - Moves 'id' and 'time' to the front of the DataFrame

    Args:
        df (pd.DataFrame): DataFrame with index column as (resource_id, time) tuples.

    Returns:
        pd.DataFrame: Transformed and cleaned DataFrame.
    """
    print(df)
    
    df = df.reset_index()

    for i in range(0, len(df)):
        if isinstance(df['index'][i], tuple):
            df.at[i, 'id'] = df.at[i, 'index'][0]
            df.at[i, 'time'] = df.at[i, 'index'][1]

    # Drop the original Index column
    df = df.drop(columns=["index"])

    # Put id and time as first columns
    df = df[["id", "time"] + [col for col in df.columns if col not in ["id", "time"]]]

    # Drop nan values
    df = df.dropna()

    return df
