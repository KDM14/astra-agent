"""Configuration management for Astra Agent."""

from __future__ import annotations

import os
import pathlib
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class AstraConfig(BaseSettings):
    """Central configuration for Astra Agent system."""

    model_config = SettingsConfigDict(
        env_prefix="ASTRA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Core environment
    app_name: str = "Astra Agent"
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"

    # Workspace & Filesystem
    workspace_dir: str = str(pathlib.Path("./workspace").resolve())
    enforce_workspace_jail: bool = True
    max_file_size_bytes: int = 10 * 1024 * 1024  # 10 MB

    # Database & Persistence
    database_url: str = "sqlite+aiosqlite:///astra_agent.db"
    enable_persistence: bool = True

    # Execution limits
    default_task_timeout_seconds: float = 180.0
    default_step_timeout_seconds: float = 30.0
    default_max_steps: int = 25
    default_max_retries: int = 3
    retry_backoff_base: float = 1.5
    retry_jitter: bool = True

    # Security & Guardrails
    enable_secret_redaction: bool = True
    require_approval_for_sensitive: bool = True
    allow_network_tools: bool = False
    allowed_subprocess_executables: list[str] = ["python", "python3", "pytest", "cat", "ls", "grep"]

    # LLM Provider Configuration
    provider: str = "mock"  # "mock", "deterministic", "openai", "anthropic", "gemini", "ollama"
    model_name: str = "mock-gpt-4o"
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    ollama_base_url: str = "http://localhost:11434"

    # API Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_auth_token: Optional[str] = None  # If set, required in Bearer auth


# Global default configuration instance
settings = AstraConfig()
