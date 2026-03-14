from __future__ import annotations

import msgspec
from typing import Literal

from ..base import Structure
from ..common import MetricsWindow, ObjectMeta
from .base import ResourceDocument


class AgentSpec(Structure):
    kind = "AgentSpec"
    modelRef: str
    toolchain: list[str]
    concurrency: int
    executionEnvironment: str
    interfaceRef: str


class AgentStatus(Structure):
    kind = "AgentStatus"
    phase: Literal["Running", "Idle", "Failed"]
    replicas: int
    activeRuns: int
    successRatePct: int


class Agent(ResourceDocument):
    kind = "Agent"
    metadata: ObjectMeta = ObjectMeta(name="research-agent")
    spec: AgentSpec = AgentSpec(
        modelRef="gpt-5.4",
        toolchain=["browser", "shell", "mcp"],
        concurrency=8,
        executionEnvironment="python-sandbox",
        interfaceRef="chat-ui",
    )
    status: AgentStatus = AgentStatus(phase="Running", replicas=4, activeRuns=12, successRatePct=97)


class RunSpec(Structure):
    kind = "RunSpec"
    agentRef: str
    trigger: str
    priority: Literal["low", "normal", "high"]
    timeoutSeconds: int


class RunStatus(Structure):
    kind = "RunStatus"
    phase: Literal["Queued", "Running", "Succeeded", "Failed"]
    nodeName: str
    durationSeconds: int
    tokensConsumed: int


class Run(ResourceDocument):
    kind = "Run"
    metadata: ObjectMeta = ObjectMeta(name="run-4f9a")
    spec: RunSpec = RunSpec(agentRef="research-agent", trigger="schedule/daily-brief", priority="high", timeoutSeconds=900)
    status: RunStatus = RunStatus(phase="Running", nodeName="node-a", durationSeconds=214, tokensConsumed=18420)


class SessionSpec(Structure):
    kind = "SessionSpec"
    agentRef: str
    userId: str
    interfaceRef: str
    sharedContextRefs: list[str] = msgspec.field(default_factory=list)


class SessionStatus(Structure):
    kind = "SessionStatus"
    phase: Literal["Open", "Idle", "Closed"]
    transport: Literal["web", "desktop", "api"]
    lastActivityAt: str


class Session(ResourceDocument):
    kind = "Session"
    metadata: ObjectMeta = ObjectMeta(name="session-82a1")
    spec: SessionSpec = SessionSpec(agentRef="research-agent", userId="ops@example.com", interfaceRef="desktop")
    status: SessionStatus = SessionStatus(phase="Open", transport="desktop", lastActivityAt="2026-03-14T12:30:00Z")


class JobSpec(Structure):
    kind = "JobSpec"
    schedule: str
    concurrencyPolicy: Literal["Allow", "Forbid", "Replace"]
    templateRef: str
    suspend: bool = False


class JobStatus(Structure):
    kind = "JobStatus"
    phase: Literal["Scheduled", "Running", "Suspended"]
    lastRunAt: str
    successCount: int
    failureCount: int


class Job(ResourceDocument):
    kind = "Job"
    metadata: ObjectMeta = ObjectMeta(name="nightly-sync")
    spec: JobSpec = JobSpec(schedule="0 */6 * * *", concurrencyPolicy="Forbid", templateRef="sync-template")
    status: JobStatus = JobStatus(phase="Scheduled", lastRunAt="2026-03-14T06:00:00Z", successCount=41, failureCount=2)


class ExecutionEnvironmentSpec(Structure):
    kind = "ExecutionEnvironmentSpec"
    image: str
    runtime: Literal["python", "node", "rust"]
    isolation: Literal["container", "vm", "microvm"]
    toolRefs: list[str]


class ExecutionEnvironmentStatus(Structure):
    kind = "ExecutionEnvironmentStatus"
    phase: Literal["Ready", "Building", "Failed"]
    warmPools: int
    averageStartupMs: int


class ExecutionEnvironment(ResourceDocument):
    kind = "ExecutionEnvironment"
    metadata: ObjectMeta = ObjectMeta(name="python-sandbox")
    spec: ExecutionEnvironmentSpec = ExecutionEnvironmentSpec(
        image="ghcr.io/xenage/python-sandbox:0.1.0",
        runtime="python",
        isolation="microvm",
        toolRefs=["browser", "shell"],
    )
    status: ExecutionEnvironmentStatus = ExecutionEnvironmentStatus(phase="Ready", warmPools=12, averageStartupMs=180)


class InterfaceSpec(Structure):
    kind = "InterfaceSpec"
    transport: Literal["chat", "voice", "api", "workflow"]
    authMode: Literal["rbac", "api-key", "sso"]
    routes: list[str]
    audience: str


class InterfaceStatus(Structure):
    kind = "InterfaceStatus"
    phase: Literal["Online", "Limited", "Offline"]
    sessionsActive: int
    p95LatencyMs: int


class Interface(ResourceDocument):
    kind = "Interface"
    metadata: ObjectMeta = ObjectMeta(name="desktop")
    spec: InterfaceSpec = InterfaceSpec(transport="chat", authMode="sso", routes=["/desktop", "/desktop/agents"], audience="operators")
    status: InterfaceStatus = InterfaceStatus(phase="Online", sessionsActive=12, p95LatencyMs=280)


class UsageSpec(Structure):
    kind = "UsageSpec"
    scope: str
    period: str
    metrics: MetricsWindow


class UsageStatus(Structure):
    kind = "UsageStatus"
    phase: Literal["Current", "Archived"]
    activeUsers: int
    activeAgents: int


class Usage(ResourceDocument):
    kind = "Usage"
    metadata: ObjectMeta = ObjectMeta(name="cluster-usage")
    spec: UsageSpec = UsageSpec(scope="cluster/demo-cluster", period="rolling", metrics=MetricsWindow(lastHour=18421, lastDay=322184, lastWeek=2219192))
    status: UsageStatus = UsageStatus(phase="Current", activeUsers=18, activeAgents=23)
