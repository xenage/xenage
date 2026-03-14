from __future__ import annotations

from typing import Literal

from ..base import Structure
from ..common import ObjectMeta
from .base import ResourceDocument


class EventSpec(Structure):
    kind = "EventSpec"
    regarding: str
    type: Literal["Normal", "Warning"]
    reason: str
    message: str


class EventStatus(Structure):
    kind = "EventStatus"
    phase: Literal["Observed"]
    count: int
    lastSeenAt: str


class Event(ResourceDocument):
    kind = "Event"
    metadata: ObjectMeta = ObjectMeta(name="event-1d2f")
    spec: EventSpec = EventSpec(
        regarding="Node/cp-1",
        type="Normal",
        reason="Joined",
        message="Node cp-1 joined the group",
    )
    status: EventStatus = EventStatus(phase="Observed", count=1, lastSeenAt="2026-03-14T12:24:00Z")
