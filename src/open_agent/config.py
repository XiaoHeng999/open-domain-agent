"""Pydantic v2 configuration layer — YAML + env var + runtime override."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal, Optional

import yaml
from pydantic import BaseModel, Field, model_validator


class ModelConfig(BaseModel):
    """LLM model configuration."""

    provider: Literal["openai", "anthropic", "deepseek", "local"] = "openai"
    name: str = "gpt-4o"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1)
    api_key: Optional[str] = Field(default=None, repr=False)
    base_url: Optional[str] = None


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

    complexity_method: Literal["rule", "llm"] = "rule"
    domains: list[str] = Field(
        default_factory=lambda: ["coding", "search", "web", "general"]
    )
    fast_path_confidence: float = Field(default=0.9, ge=0.0, le=1.0)

    # Optional independent routing model — falls back to main model when unset
    routing_provider: Optional[Literal["openai", "anthropic", "deepseek", "local"]] = None
    routing_name: Optional[str] = None
    routing_api_key: Optional[str] = Field(default=None, repr=False)
    routing_base_url: Optional[str] = None


class CheckpointConfig(BaseModel):
    """Checkpoint configuration."""

    enabled: bool = True
    interval: int = Field(default=1, ge=1)
    storage_backend: Literal["json", "sqlite"] = "json"
    storage_path: str = ".open_agent/checkpoints"


class TraceConfig(BaseModel):
    """Trace system configuration."""

    enabled: bool = True
    store_traces: bool = True
    trace_dir: str = ".open_agent/traces"


class ToolsConfig(BaseModel):
    """Tool system configuration."""

    exec_enabled: bool = True
    brave_search_api_key: Optional[str] = Field(default=None, repr=False)
    max_tool_result_tokens: int = Field(default=2000, ge=100)


class AgentConfig(BaseModel):
    """Top-level agent configuration."""

    model: ModelConfig = Field(default_factory=ModelConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    routing: RoutingConfig = Field(default_factory=RoutingConfig)
    checkpoint: CheckpointConfig = Field(default_factory=CheckpointConfig)
    trace: TraceConfig = Field(default_factory=TraceConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)

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
    }
    for env_key, path_parts in env_map.items():
        val = os.environ.get(env_key)
        if val is not None:
            target = data
            for part in path_parts[:-1]:
                target = target.setdefault(part, {})
            target[path_parts[-1]] = val


def _deep_merge(base: dict, override: dict) -> None:
    """Merge override into base dict recursively."""
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
