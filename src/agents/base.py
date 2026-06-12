"""Base agent class — all analysis agents inherit from this."""

from __future__ import annotations

import asyncio
import time
import uuid
from abc import ABC, abstractmethod
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts.chat import ChatPromptTemplate
from pydantic import BaseModel

from src.agents.state import CodeReviewState, Finding
from src.di.container import AppContext, CacheClient, MetricsClient


class StagedFinding(BaseModel):
    """Structured finding output from LLM agents."""

    file: str
    line: int = 0
    severity: str = "medium"
    category: str = "general"
    title: str = ""
    description: str = ""
    recommendation: str = ""
    cwe_id: str | None = None
    cvss_score: float | None = None
    auto_fixable: bool = False
    confidence: float = 1.0


class StagedFindingList(BaseModel):
    """List wrapper for structured LLM output."""

    findings: list[StagedFinding]


class AnalysisAgent(ABC):
    """Base class for all analysis agents.

    Provides:
    - LLM access with structured output
    - Caching of results per file hash
    - Metrics collection
    - Error handling with graceful degradation
    - Progress tracking
    - Retry with exponential backoff
    """

    MAX_RETRIES = 3
    BASE_DELAY = 1.0
    TIMEOUT_SECONDS = 60.0

    def __init__(self, ctx: AppContext):
        self.ctx = ctx
        self.llm: BaseChatModel = ctx.llm  # type: ignore[assignment]
        self.cache: CacheClient = ctx.cache
        self.metrics: MetricsClient = ctx.metrics
        self._total_llm_calls = 0
        self._total_tokens = 0

    @abstractmethod
    def category(self) -> str:
        """Return the category string for this agent (e.g., 'security', 'performance')."""
        ...

    @abstractmethod
    async def analyze(self, state: CodeReviewState) -> CodeReviewState:
        """Execute the analysis. Must be implemented by subclasses."""
        ...

    async def __call__(self, state: CodeReviewState) -> CodeReviewState:
        """Run the agent with error handling and metrics."""
        start = time.monotonic()
        try:
            result = await self.analyze(state)
            elapsed = time.monotonic() - start
            self.metrics.histogram(f"agent.{self.category()}.duration", elapsed)
            self.metrics.increment(f"agent.{self.category()}.success")
            return result
        except Exception as e:
            elapsed = time.monotonic() - start
            self.metrics.increment(f"agent.{self.category()}.failure")
            state.setdefault("errors", []).append(f"{self.category()} agent failed after {elapsed:.1f}s: {e}")
            return state

    async def _llm_call_with_retry(self, chain: Any, template_vars: dict) -> StagedFindingList:
        """Call LLM with exponential backoff retry and timeout."""
        last_exc = None
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                return await asyncio.wait_for(
                    chain.ainvoke(template_vars),
                    timeout=self.TIMEOUT_SECONDS,
                )
            except (TimeoutError, Exception) as e:
                last_exc = e
                if attempt < self.MAX_RETRIES:
                    delay = self.BASE_DELAY * (2 ** (attempt - 1))
                    self.metrics.increment(f"agent.{self.category()}.retry")
                    await asyncio.sleep(delay)
        raise last_exc or RuntimeError("LLM call failed after retries")

    async def analyze_with_llm(
        self,
        system_prompt: str,
        human_template: str,
        template_vars: dict[str, Any],
        file_path: str | None = None,
    ) -> list[Finding]:
        """Run LLM analysis with caching and structured output.

        Args:
            system_prompt: System prompt text.
            human_template: Human message template.
            template_vars: Variables to fill into template.
            file_path: Optional file path for caching.

        Returns:
            List of findings from the LLM.
        """
        if not self.llm:
            return []

        # Check cache
        if file_path and self.cache:
            cached = await self.cache.get(f"llm:{self.category()}:{file_path}")
            if cached:
                self.metrics.increment(f"agent.{self.category()}.cache_hit")
                return [Finding(**f) for f in cached]

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("human", human_template),
            ]
        )

        try:
            chain = prompt | self.llm.with_structured_output(StagedFindingList)
            result: StagedFindingList = await self._llm_call_with_retry(chain, template_vars)

            self._total_llm_calls += 1
            self.metrics.increment(f"agent.{self.category()}.llm_calls")

            findings = []
            for sf in result.findings:
                if sf.confidence < 0.3:
                    continue
                findings.append(
                    Finding(
                        id=str(uuid.uuid4()),
                        file=sf.file or file_path or "",
                        line=sf.line,
                        severity=sf.severity,
                        category=self.category(),
                        title=sf.title,
                        description=sf.description,
                        recommendation=sf.recommendation,
                        cwe_id=sf.cwe_id,
                        cvss_score=sf.cvss_score,
                        auto_fixable=sf.auto_fixable,
                    )
                )

            # Write to cache
            if file_path and self.cache:
                await self.cache.set(
                    f"llm:{self.category()}:{file_path}",
                    [dict(f) for f in findings],  # type: ignore[arg-type]
                )

            return findings

        except Exception:
            self.metrics.increment(f"agent.{self.category()}.llm_error")
            return []
