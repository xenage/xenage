from __future__ import annotations

from typing import Literal

from ..base import Structure
from ..common import ObjectMeta
from .base import ResourceDocument


class ToolSpec(Structure):
    kind = "ToolSpec"
    driver: str
    permissions: list[str]
    timeoutSeconds: int
    cacheTtlSeconds: int = 0


class ToolStatus(Structure):
    kind = "ToolStatus"
    phase: Literal["Available", "Degraded", "Disabled"]
    version: str
    invocationsLastHour: int


class Tool(ResourceDocument):
    kind = "Tool"
    metadata: ObjectMeta = ObjectMeta(name="browser")
    spec: ToolSpec = ToolSpec(driver="builtin.web", permissions=["net.read"], timeoutSeconds=60, cacheTtlSeconds=30)
    status: ToolStatus = ToolStatus(phase="Available", version="1.2.0", invocationsLastHour=1420)


class MCPSpec(Structure):
    kind = "MCPSpec"
    transport: Literal["stdio", "http", "websocket"]
    endpoint: str
    capabilities: list[str]
    authSecretRef: str | None = None


class MCPStatus(Structure):
    kind = "MCPStatus"
    phase: Literal["Connected", "Pending", "Error"]
    latencyMs: int
    toolsExposed: int


class MCP(ResourceDocument):
    kind = "MCP"
    metadata: ObjectMeta = ObjectMeta(name="github")
    spec: MCPSpec = MCPSpec(transport="http", endpoint="https://mcp.github.internal", capabilities=["issues", "prs", "search"])
    status: MCPStatus = MCPStatus(phase="Connected", latencyMs=92, toolsExposed=17)


class ModelSpec(Structure):
    kind = "ModelSpec"
    provider: str
    contextWindow: int
    supportsTools: bool
    supportsVision: bool


class ModelStatus(Structure):
    kind = "ModelStatus"
    phase: Literal["Available", "Preview", "Disabled"]
    averageCostPer1MInput: float
    successRatePct: int


class Model(ResourceDocument):
    kind = "Model"
    metadata: ObjectMeta = ObjectMeta(name="gpt-5.4")
    spec: ModelSpec = ModelSpec(provider="OpenAI", contextWindow=256000, supportsTools=True, supportsVision=True)
    status: ModelStatus = ModelStatus(phase="Available", averageCostPer1MInput=5.0, successRatePct=99)


class APIAccessSpec(Structure):
    kind = "APIAccessSpec"
    owner: str
    rateLimitPerMinute: int
    allowedInterfaces: list[str]
    expiresAt: str | None = None


class APIAccessStatus(Structure):
    kind = "APIAccessStatus"
    phase: Literal["Issued", "Rotating", "Revoked"]
    lastUsedAt: str
    requestsLastHour: int


class APIAccess(ResourceDocument):
    kind = "APIAccess"
    metadata: ObjectMeta = ObjectMeta(name="partner-api")
    spec: APIAccessSpec = APIAccessSpec(owner="integration-team", rateLimitPerMinute=600, allowedInterfaces=["api-gateway"], expiresAt="2026-06-01T00:00:00Z")
    status: APIAccessStatus = APIAccessStatus(phase="Issued", lastUsedAt="2026-03-14T12:28:00Z", requestsLastHour=9211)
