from typing import Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session


def parse_cel_id(cel_id: str) -> Tuple[Optional[int], Optional[str]]:
    """Parse strings like "cel3" or "cel3-pv" into (cel_number, energy_type)."""
    if not cel_id:
        return (None, None)
    parts = cel_id.split('-')
    if not parts[0].startswith('cel'):
        return (None, None)
    try:
        cel_number = int(parts[0][3:])
    except ValueError:
        return (None, None)
    energy_type = parts[1] if len(parts) > 1 else None
    return (cel_number, energy_type)


def resolve_plant(
    db: Session,
    cel_number: int,
    energy_type: Optional[str] = None,
) -> Optional[Tuple[int, str]]:
    """Return (plant_id, energy_type_name) for a cel/energy_type pair."""
    if energy_type is None:
        row = db.execute(
            text("""
                SELECT pl.plant_id, et.name
                FROM public.plant pl
                JOIN public.energy_type et ON et.id = pl.energy_type_id
                WHERE pl.cel_id = :cel_id
                  AND pl.plant_id > 0
                ORDER BY pl.plant_id
                LIMIT 1
            """),
            {"cel_id": cel_number},
        ).fetchone()
    else:
        row = db.execute(
            text("""
                SELECT pl.plant_id, et.name
                FROM public.plant pl
                JOIN public.energy_type et ON et.id = pl.energy_type_id
                WHERE pl.cel_id = :cel_id
                  AND lower(et.name) = lower(:energy_type)
                  AND pl.plant_id > 0
                ORDER BY pl.plant_id
                LIMIT 1
            """),
            {"cel_id": cel_number, "energy_type": energy_type},
        ).fetchone()
    return (row[0], row[1]) if row else None


def resolve_plant_id_from_cel_id(db: Session, cel_id: str) -> Optional[int]:
    """Convenience: parse a 'cel3-pv' style identifier and return plant_id only."""
    cel_number, energy_type = parse_cel_id(cel_id)
    if cel_number is None:
        return None
    resolved = resolve_plant(db, cel_number, energy_type)
    return resolved[0] if resolved else None
