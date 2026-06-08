"""Base agent class — all analysis agents inherit from this."""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field

from src.di.container import AppContext, CacheClient, MetricsClient
from src.agents.state import CodeReviewState, Finding


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
    """

    def __init__(self, ctx: AppContext):
        self.ctx = ctx
        self.llm: BaseChatModel = ctx.llm
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
            state.setdefault("errors", []).append(
                f"{self.category()} agent failed after {elapsed:.1f}s: {e}"
            )
            return state

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
        # Check cache
        if file_path and self.cache:
            cached = await self.cache.get(f"llm:{self.category()}:{file_path}")
            if cached:
                self.metrics.increment(f"agent.{self.category()}.cache_hit")
                return [Finding(**f) for f in cached]

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", human_template),
        ])

        try:
            chain = prompt | self.llm.with_structured_output(StagedFindingList)
            result: StagedFindingList = await chain.ainvoke(template_vars)

            self._total_llm_calls += 1
            self.metrics.increment(f"agent.{self.category()}.llm_calls")

            findings = []
            for sf in result.findings:
                if sf.confidence < 0.3:
                    continue
                findings.append(Finding(
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
                ))

            # Write to cache
            if file_path and self.cache:
                await self.cache.set(
                    f"llm:{self.category()}:{file_path}",
                    [dict(f) for f in findings],
                )

            return findings

        except Exception as e:
            self.metrics.increment(f"agent.{self.category()}.llm_error")
            return []
