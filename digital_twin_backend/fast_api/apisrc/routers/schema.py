from fastapi import APIRouter, Depends
from sqlalchemy import MetaData, inspect, text
from sqlalchemy.orm import Session

from ..db import engine, get_db


router = APIRouter()


@router.get("/get_schema/", tags=["Schema"])
def get_database_schema(db: Session = Depends(get_db)):
    """
    Returns the database schema, listing all tables and their column names.

    Response:
    {
        "table_name_1": ["column1", "column2", "column3"],
        "table_name_2": ["columnA", "columnB", "columnC"]
    }
    """
    metadata = MetaData()
    metadata.reflect(bind=engine)

    return {
        table_name: [column.name for column in table.columns]
        for table_name, table in metadata.tables.items()
    }


@router.get("/get_primary_key/", tags=["Schema"])
def get_pk(table: str, db: Session = Depends(get_db)):
    """
    Returns the pk of a selected table
    """
    inspector = inspect(db.bind)
    pk = inspector.get_pk_constraint(table)
    return pk.get('constrained_columns', [])


@router.get("/unique_column_values/", tags=["Schema"])
def unique_column_values(table: str, column: str, db: Session = Depends(get_db)):
    """
    Get 5 unique values of a selected column from a selected table
    """
    query = text(f"""SELECT DISTINCT {column} FROM {table}""")

    try:
        result = db.execute(query)
        return [row[0] for row in result]
    except Exception as e:
        return {"error": str(e)}


@router.get("/Random_values_from_column/", tags=["Schema"])
def random_column_values(table: str, column: str, db: Session = Depends(get_db)):
    """
    Get 5 random values of a selected column from a selected table
    """
    query = text(f"SELECT {column} FROM {table} ORDER BY RANDOM() LIMIT 5;")

    try:
        result = db.execute(query)
        return [row[0] for row in result]
    except Exception as e:
        return {"error": str(e)}
