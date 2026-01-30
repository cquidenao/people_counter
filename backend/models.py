from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal
from datetime import datetime
import uuid

class EventIn(BaseModel):
    camera_id: Optional[str] = "CAM-01"
    direction: Optional[Literal["in", "out", "unknown"]] = "unknown"
    count_delta: int = Field(..., description="Positive for IN, negative for OUT")
    meta: Optional[Dict[str, Any]] = None

class EventOut(BaseModel):
    id: str
    ts: str
    camera_id: Optional[str]
    direction: str
    count_delta: int
    meta: Optional[Dict[str, Any]] = None

def make_event_out(e: EventIn) -> EventOut:
    return EventOut(
        id=str(uuid.uuid4()),
        ts=datetime.utcnow().isoformat() + "Z",
        camera_id=e.camera_id,
        direction=e.direction,
        count_delta=e.count_delta,
        meta=e.meta or {},
    )
