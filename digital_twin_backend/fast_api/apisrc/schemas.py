from typing import Optional

from pydantic import BaseModel, Field


class SignInRequest(BaseModel):
    username: str
    password: str


class CreateEventRequest(BaseModel):
    res: str = Field(..., description="Resource type", example="(PV, Wind)")
    description: str = Field(..., description="Short description of the event")
    submit_time: str = Field(..., description="Submission date", example="(YYYY-MM-DD)")
    category: str = Field(..., description="Category of the event", example="(Inverter, Electrical, PV panels, Mounting System, Environment, Other)")
    recurrent: str = Field(..., description="The event recurrency", example=" (Monthly, Quarterly, Bi-annualy, Annualy, None)")
    comment: Optional[str] = Field(None, description="Optional comment or notes")
    device_id: Optional[str] = Field(None, description="Device ID if applicable")


class DeleteEventRequest(BaseModel):
    res: str = Field(..., description="Resource type", example="(PV, Wind)")
    description: str = Field(..., description="Short description of the event")
    type: str = Field(..., description="Type of event", example="(fault_warning, past_event, scheduled_event)")
    submit_time: str = Field(..., description="Submission date", example="(YYYY-MM-DD)")


class SimulationRequest(BaseModel):
    duration: int = Field(300, description="Simulation duration in timesteps")
    timestep: float = Field(1.0, description="Timestep size")
    freq: int = Field(50, description="Grid frequency")
    solver: str = Field("NRP", description="Solver type")
    domain: str = Field("SP", description="Simulation domain")
    opf: bool = Field(False, description="Optimal powerflow flag")
    replace_map: Optional[dict] = Field(None, description="Component name mapping")

    date: str = Field("2025-01-01", description="Selected day in YYYY-MM-DD format")
    load_scale: float = Field(1.0, description="Multiplier for LOAD active/reactive")
    pv_scale: float = Field(1.0, description="Multiplier for PV active")
    wp_scale: float = Field(1.0, description="Multiplier for WP active")


class DsoSimulationRequest(BaseModel):
    cell: int = Field("3", ge=1, le=4, description="DSO cell number (1–4)")
    duration: int = Field(300, description="Simulation duration in timesteps")
    timestep: float = Field(1.0, description="Timestep size")
    freq: int = Field(50, description="Grid frequency")
    solver: str = Field("NRP", description="Solver type")
    domain: str = Field("SP", description="Simulation domain")
    opf: bool = Field(False, description="Optimal powerflow flag")
    replace_map: Optional[dict] = Field(None, description="Component name mapping")

    date: str = Field("2023-01-01", description="Selected day in YYYY-MM-DD format")
    load_scale: float = Field(1.0, description="Multiplier for LOAD active/reactive")
    gen_scale: float = Field(1.0, description="Multiplier for GEN active")
