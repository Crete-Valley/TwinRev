import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import tags_metadata
from .db import Base, engine
from .routers import database, dso, maintenance, production, schema, tso, user


Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Digital Twin Backend",
    description="Collection of REST APIs for Serving Execution of Self Consumption Optimization tool for TwinREV",
    version="0.0.1",
    openapi_tags=tags_metadata,
    license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/sys-path")
def get_sys_path():
    return {"sys_path": sys.path}

app.include_router(user.router)
app.include_router(schema.router)
app.include_router(database.router)
app.include_router(maintenance.router)
app.include_router(production.router)
app.include_router(tso.router)
app.include_router(dso.router)
