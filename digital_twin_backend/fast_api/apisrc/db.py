import os

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


dt_host = os.getenv("DB_POST_HOST")
dt_user = os.getenv("DB_POST_USER")
dt_port = os.getenv("DB_POST_PORT")
dt_pass = os.getenv("DB_POST_PASSWORD")
dt_name = os.getenv("DB_POST_NAME")

DATABASE_URL = f"postgresql+psycopg2://{dt_user}:{dt_pass}@{dt_host}:{dt_port}/{dt_name}"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=True, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
