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
    spec: EventSpec = EventSpec(regarding="Agent/research-agent", type="Normal", reason="Scaled", message="Scaled replicas from 2 to 4")
    status: EventStatus = EventStatus(phase="Observed", count=1, lastSeenAt="2026-03-14T12:24:00Z")


class LogSpec(Structure):
    kind = "LogSpec"
    sourceRef: str
    stream: Literal["stdout", "stderr", "audit"]
    retentionHours: int
    indexName: str


class LogStatus(Structure):
    kind = "LogStatus"
    phase: Literal["Streaming", "Archived"]
    entriesLastMinute: int
    lastOffset: str


class Log(ResourceDocument):
    kind = "Log"
    metadata: ObjectMeta = ObjectMeta(name="run-4f9a-logs")
    spec: LogSpec = LogSpec(sourceRef="Run/run-4f9a", stream="stdout", retentionHours=168, indexName="logs-runs")
    status: LogStatus = LogStatus(phase="Streaming", entriesLastMinute=84, lastOffset="582019")


class AlertSpec(Structure):
    kind = "AlertSpec"
    severity: Literal["info", "warning", "critical"]
    sourceRef: str
    signal: str
    threshold: str


class AlertStatus(Structure):
    kind = "AlertStatus"
    phase: Literal["Firing", "Resolved", "Muted"]
    since: str
    notificationsSent: int


class Alert(ResourceDocument):
    kind = "Alert"
    metadata: ObjectMeta = ObjectMeta(name="latency-spike")
    spec: AlertSpec = AlertSpec(severity="warning", sourceRef="Interface/desktop", signal="p95LatencyMs", threshold="> 250 for 5m")
    status: AlertStatus = AlertStatus(phase="Firing", since="2026-03-14T12:20:00Z", notificationsSent=3)
