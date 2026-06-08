"""Dependency injection container — single source of truth for all services."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MetricsClient:
    """Lightweight metrics client. In production, replace with OpenTelemetry/Prometheus."""

    def increment(self, metric: str, value: int = 1):
        pass

    def gauge(self, metric: str, value: float):
        pass

    def histogram(self, metric: str, value: float):
        pass

    @property
    def timer(self):
        return self


@dataclass
class CacheClient:
    """Lightweight cache. In production, replace with Redis."""
    _store: dict = field(default_factory=dict)

    async def get(self, key: str) -> Optional[dict]:
        return self._store.get(key)

    async def set(self, key: str, value: dict, ttl: int = 86400):
        self._store[key] = value


@dataclass
class AppContext:
    """Single source of truth for all services used across agents."""
    llm: object = None
    config: dict = field(default_factory=dict)
    vector_store: Optional[object] = None
    cache: CacheClient = field(default_factory=CacheClient)
    metrics: MetricsClient = field(default_factory=MetricsClient)
    checkpointer: object = None

    def child(self, **overrides) -> AppContext:
        kwargs = {
            "llm": self.llm,
            "config": self.config,
            "vector_store": self.vector_store,
            "cache": self.cache,
            "metrics": self.metrics,
            "checkpointer": self.checkpointer,
        }
        kwargs.update(overrides)
        return AppContext(**kwargs)


def _create_llm(config: dict):
    """Create LLM based on configuration with lazy imports."""
    provider = config.get("llm_provider", os.getenv("LLM_PROVIDER", "google")).lower()
    temperature = config.get("llm_temperature", 0.1)

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=config.get("llm_model", "gpt-4o"),
            temperature=temperature,
            api_key=os.getenv("OPENAI_API_KEY"),
        )
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=config.get("llm_model", "claude-3-5-sonnet-20241022"),
            temperature=temperature,
            api_key=os.getenv("ANTHROPIC_API_KEY"),
        )
    else:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=config.get("llm_model", "gemini-2.0-flash-exp"),
            temperature=temperature,
            google_api_key=os.getenv("GOOGLE_API_KEY"),
        )


def _create_checkpointer():
    """Create checkpoint saver with lazy import."""
    from langgraph.checkpoint.memory import MemorySaver
    return MemorySaver()


def create_app_context(config_path: str | None = None) -> AppContext:
    """Factory — single source of truth for creating the app context."""
    from src.utils.config_loader import load_config

    config = load_config(config_path)
    llm = None
    checkpointer = None

    # Only create LLM if dependencies are available
    try:
        llm = _create_llm(config)
    except ImportError:
        pass

    try:
        checkpointer = _create_checkpointer()
    except ImportError:
        pass

    return AppContext(
        llm=llm,
        config=config,
        cache=CacheClient(),
        metrics=MetricsClient(),
        checkpointer=checkpointer,
    )
