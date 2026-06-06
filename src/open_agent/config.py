"""Pydantic v2 configuration layer — YAML + env var + runtime override."""

from __future__ import annotations

import os
import logging
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Optional

import yaml
from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger("open_agent.config")


class PermissionMode(str, Enum):
    """Permission decision modes."""

    CAUTIOUS = "cautious"
    CONSERVATIVE = "conservative"
    FLUENT = "fluent"
    UNRESTRICTED = "unrestricted"


class PermissionRule(BaseModel):
    """A single deny/allow rule matching tool calls."""

    tool: str
    pattern: Optional[str] = None
    path: Optional[str] = None
    domain: Optional[str] = None


class PermissionConfig(BaseModel):
    """Permission system configuration — deny/mode/allow pipeline."""

    mode: PermissionMode = PermissionMode.FLUENT
    deny: list[PermissionRule] = Field(default_factory=list)
    allow: list[PermissionRule] = Field(default_factory=list)


class ModelConfig(BaseModel):
    """LLM model configuration."""

    provider: Literal["openai", "anthropic", "deepseek"] = "openai"
    name: str = "gpt-4o"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1)
    api_key: Optional[str] = Field(default=None, repr=False)
    base_url: Optional[str] = None
    caching: bool = True


class MemoryConfig(BaseModel):
    """Memory system configuration — 4-layer architecture."""

    # Runtime layer
    runtime_token_budget: int = Field(default=8000, ge=100)
    compression_threshold: float = Field(default=0.7, ge=0.1, le=1.0)
    aggressive_threshold: float = Field(default=0.9, ge=0.1, le=1.0)
    keep_recent_turns: int = Field(default=3, ge=1)
    max_tool_result_tokens: int = Field(default=2000, ge=100)
    tool_cache_max_entries: int = Field(default=50, ge=1)

    # Profile layer
    profile_db_path: str = ".open_agent/memory/profile/profile.sqlite"
    profile_max_inject_tokens: int = Field(default=500, ge=50)

    # Retrieval layer
    retrieval_store_dir: str = ".open_agent/memory/retrieval"
    retrieval_embedding_model: str = "all-MiniLM-L6-v2"
    retrieval_top_k: int = Field(default=5, ge=1, le=20)
    retrieval_max_inject_tokens: int = Field(default=1500, ge=100)
    retrieval_score_threshold: float = Field(default=0.5, ge=0.0, le=1.0)

    # Archive layer
    archive_dir: str = ".open_agent/memory/archive"

    # Session todo
    todo_staleness_rounds: int = Field(default=3, ge=1)

    # Persistence
    persistence_enabled: bool = False
    persistence_db_path: str = ".open_agent/memory/persistence/conversation.sqlite"
    persistence_retention_days: int = Field(default=7, ge=1)

    # Backward compat aliases
    working_memory_token_limit: int = Field(default=8000, ge=100)


class SafetyConfig(BaseModel):
    """Security and safety configuration."""

    safety_level: Literal["strict", "permissive", "off"] = "strict"
    trusted_paths: list[str] = Field(default_factory=list)
    sensitive_files: list[str] = Field(
        default_factory=lambda: [".env", "credentials.json", "*.key", "*.pem"]
    )


class SandboxConfig(BaseModel):
    """Sandbox execution configuration."""

    backend: Literal["daytona", "docker", "subprocess"] = "subprocess"
    auto_timeout: int = Field(default=300, ge=1)


class RoutingConfig(BaseModel):
    """Routing layer configuration."""

    domains: list[str] = Field(
        default_factory=lambda: ["coding", "search", "web", "general"]
    )
    fast_path_confidence: float = Field(default=0.9, ge=0.0, le=1.0)

    # Optional independent routing model — falls back to main model when unset
    routing_provider: Optional[Literal["openai", "anthropic", "deepseek"]] = None
    routing_name: Optional[str] = None
    routing_api_key: Optional[str] = Field(default=None, repr=False)
    routing_base_url: Optional[str] = None


class CheckpointConfig(BaseModel):
    """Checkpoint configuration."""

    enabled: bool = True
    interval: int = Field(default=1, ge=1)
    storage_backend: Literal["json", "sqlite"] = "sqlite"
    storage_path: str = ".open_agent/checkpoints/checkpoints.sqlite"


class EvalConfig(BaseModel):
    """Eval system configuration — retention limits for JSONL storage."""

    results_retention: int = Field(default=100, ge=1)
    trajectories_retention: int = Field(default=200, ge=1)


class TraceConfig(BaseModel):
    """Trace system configuration."""

    enabled: bool = True
    store_traces: bool = True
    trace_dir: str = ".open_agent/traces"
    trace_retention: int = Field(default=100, ge=1)


class ToolsConfig(BaseModel):
    """Tool system configuration."""

    exec_enabled: bool = True
    brave_search_api_key: Optional[str] = Field(default=None, repr=False)
    search_backend: Literal["auto", "duckduckgo", "brave"] = "auto"
    max_tool_result_tokens: int = Field(default=2000, ge=100)


class HooksConfig(BaseModel):
    """Hook system configuration."""

    enabled: bool = True
    welcome_enabled: bool = True


class MCPServerConfig(BaseModel):
    """Configuration for a single MCP server."""

    server_id: str
    transport: Literal["stdio", "sse", "http"] = "stdio"
    command: Optional[str] = None
    url: Optional[str] = None
    headers: dict[str, str] = Field(default_factory=dict)
    health_check_interval: int = 30

    @model_validator(mode="after")
    def validate_transport_fields(self) -> "MCPServerConfig":
        if self.transport == "stdio" and not self.command:
            raise ValueError("stdio transport requires 'command'")
        if self.transport in ("http", "sse") and not self.url:
            raise ValueError(f"{self.transport} transport requires 'url'")
        return self


class MCPConfig(BaseModel):
    """MCP integration configuration."""

    servers: list[MCPServerConfig] = Field(default_factory=list)
    connect_timeout: int = Field(default=10, ge=1)
    tool_discovery_timeout: int = Field(default=30, ge=1)


class SubagentPresetConfig(BaseModel):
    """User-defined or overridden sub-agent preset from config."""

    name: str
    system_prompt: str = ""
    allowed_tools: list[str] = Field(default_factory=list)
    max_turns: int = 10
    description: str = ""


class SubagentConfig(BaseModel):
    """Sub-agent (agent-as-a-tool) configuration."""

    enabled: bool = True
    max_concurrent: int = Field(default=5, ge=1)
    max_children: int = Field(default=3, ge=1)
    default_max_turns: int = Field(default=10, ge=1)
    presets: list[SubagentPresetConfig] = Field(default_factory=list)


class CostTrackingConfig(BaseModel):
    """Cost tracking configuration."""

    enabled: bool = False
    budget_daily: Optional[float] = None


class AgentConfig(BaseModel):
    """Top-level agent configuration."""

    model: ModelConfig = Field(default_factory=ModelConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    routing: RoutingConfig = Field(default_factory=RoutingConfig)
    checkpoint: CheckpointConfig = Field(default_factory=CheckpointConfig)
    eval: EvalConfig = Field(default_factory=EvalConfig)
    trace: TraceConfig = Field(default_factory=TraceConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    hooks: HooksConfig = Field(default_factory=HooksConfig)
    permissions: PermissionConfig = Field(default_factory=PermissionConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    subagent: SubagentConfig = Field(default_factory=SubagentConfig)
    cost_tracking: CostTrackingConfig = Field(default_factory=CostTrackingConfig)

    workspace: str = "."

    @model_validator(mode="after")
    def resolve_workspace(self) -> "AgentConfig":
        self.workspace = str(Path(self.workspace).resolve())
        return self


def load_config(path: str | Path | None = None, **overrides: Any) -> AgentConfig:
    """Load configuration from YAML file, env vars, and runtime overrides.

    Priority (highest wins): runtime overrides > env vars > YAML > defaults.
    """
    data: dict[str, Any] = {}

    if path and Path(path).exists():
        with open(path) as f:
            data = yaml.safe_load(f) or {}

    _apply_env_overrides(data)
    _deep_merge(data, overrides)

    return AgentConfig.model_validate(data)


def _apply_env_overrides(data: dict[str, Any]) -> None:
    """Inject environment variable overrides into config dict."""
    env_map = {
        "OPEN_AGENT_MODEL_PROVIDER": ("model", "provider"),
        "OPEN_AGENT_MODEL_NAME": ("model", "name"),
        "OPEN_AGENT_MODEL_API_KEY": ("model", "api_key"),
        "OPEN_AGENT_MODEL_BASE_URL": ("model", "base_url"),
        "OPEN_AGENT_SAFETY_LEVEL": ("safety", "safety_level"),
        "OPEN_AGENT_WORKSPACE": ("workspace",),
        "OPEN_AGENT_SANDBOX_BACKEND": ("sandbox", "backend"),
        "OPEN_AGENT_PERMISSION_MODE": ("permissions", "mode"),
        "OPEN_AGENT_TRACE_DIR": ("trace", "trace_dir"),
        "OPEN_AGENT_STORE_TRACES": ("trace", "store_traces"),
        "OPEN_AGENT_TRACE_RETENTION": ("trace", "trace_retention"),
        "OPEN_AGENT_EVAL_RESULTS_RETENTION": ("eval", "results_retention"),
        "OPEN_AGENT_EVAL_TRAJECTORIES_RETENTION": ("eval", "trajectories_retention"),
    }
    for env_key, path_parts in env_map.items():
        val = os.environ.get(env_key)
        if val is not None:
            target = data
            for part in path_parts[:-1]:
                target = target.setdefault(part, {})
            target[path_parts[-1]] = val

    # MCP servers from env var (JSON format)
    mcp_servers_env = os.environ.get("OPEN_AGENT_MCP_SERVERS")
    if mcp_servers_env:
        import json as _json
        try:
            mcp_data = data.setdefault("mcp", {})
            mcp_data["servers"] = _json.loads(mcp_servers_env)
        except (ValueError, TypeError):
            logger.warning("Failed to parse OPEN_AGENT_MCP_SERVERS env var", exc_info=True)


def _deep_merge(base: dict, override: dict) -> None:
    """Merge override into base dict recursively."""
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
