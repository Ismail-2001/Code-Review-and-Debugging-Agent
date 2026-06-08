"""Celery tasks for async review processing — production-grade background execution."""

from __future__ import annotations

import os
import time
import json
from typing import Optional

from celery import Celery
from celery.signals import task_failure, task_success

from src.di.container import create_app_context
from src.agents.graph import build_code_review_graph
from src.agents.state import CodeReviewState

celery_app = Celery(
    "codeguardian",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,  # Re-queue on worker failure
    worker_prefetch_multiplier=1,
    task_soft_time_limit=600,  # 10 min soft limit
    task_time_limit=900,  # 15 min hard limit
    task_max_retries=3,
    task_default_retry_delay=60,
)


@celery_app.task(bind=True, name="codeguardian.run_review", max_retries=3, default_retry_delay=60)
def run_review(
    self,
    review_id: str,
    repo_url: str,
    branch: str,
    config_path: Optional[str] = None,
    auto_fix: bool = False,
    files: Optional[list[str]] = None,
):
    """Run a code review as an async Celery task.

    This is the primary entry point for production usage.
    Queue this task via Celery from the API layer.
    """
    ctx = create_app_context(config_path)
    graph = build_code_review_graph(ctx)

    initial_state: CodeReviewState = _build_initial_state(
        review_id, repo_url, branch, ctx.config, auto_fix, files,
    )

    try:
        config = {"configurable": {"thread_id": review_id}}
        final_state = graph.invoke(initial_state, config)

        findings = final_state.get("prioritized_issues", [])

        return {
            "status": "completed",
            "review_id": review_id,
            "quality_score": final_state.get("quality_score"),
            "total_findings": len(findings),
            "severity_counts": {
                "critical": sum(1 for f in findings if f.get("severity") == "critical"),
                "high": sum(1 for f in findings if f.get("severity") == "high"),
                "medium": sum(1 for f in findings if f.get("severity") == "medium"),
                "low": sum(1 for f in findings if f.get("severity") == "low"),
                "info": sum(1 for f in findings if f.get("severity") == "info"),
            },
            "duration_ms": int((time.time() - initial_state.get("analysis_start_time", time.time())) * 1000),
        }

    except Exception as exc:
        self.retry(exc=exc)
        return {
            "status": "failed",
            "review_id": review_id,
            "error": str(exc),
        }


@celery_app.task(name="codeguardian.health_check")
def health_check():
    """Simple health check task."""
    return {"status": "ok", "timestamp": time.time()}


@task_success.connect(sender=run_review)
def on_review_success(sender=None, result=None, **kwargs):
    """Log successful reviews for monitoring."""
    if result:
        _log_metrics("review.success", result)


@task_failure.connect(sender=run_review)
def on_review_failure(sender=None, exception=None, **kwargs):
    """Log failed reviews for alerting."""
    _log_metrics("review.failure", {"error": str(exception)})


def _build_initial_state(
    review_id: str,
    repo_url: str,
    branch: str,
    config: dict,
    auto_fix: bool,
    files: Optional[list[str]],
) -> CodeReviewState:
    return {
        "repository_url": repo_url,
        "local_path": "",
        "review_scope": "full",
        "target_branch": branch or "main",
        "target_files": files,
        "severity_threshold": config.get("severity_threshold", "medium"),
        "auto_fix_enabled": auto_fix,
        "config": config,
        "messages": [],
        "errors": [],
        "primary_languages": [],
        "project_type": "unknown",
        "frameworks": [],
        "build_tools": [],
        "repo_size_bytes": 0,
        "static_analysis_findings": [],
        "pattern_analysis_findings": [],
        "security_findings": [],
        "performance_findings": [],
        "testing_findings": [],
        "logic_findings": [],
        "policy_findings": [],
        "files_analyzed": 0,
        "total_files": 0,
        "all_findings": [],
        "prioritized_issues": [],
        "quick_wins": [],
        "quality_score": 100.0,
        "generated_fixes": [],
        "fix_branch_name": None,
        "markdown_report": "",
        "json_report": {},
        "html_report": "",
        "github_issues": [],
        "current_step": "started",
        "analysis_start_time": time.time(),
        "llm_tokens_used": 0,
        "llm_cost_cents": 0.0,
        "user_feedback": [],
        "skip_categories": [],
    }


def _log_metrics(event: str, data: dict):
    """Log metrics for observability."""
    import logging
    logger = logging.getLogger("codeguardian.metrics")
    logger.info(json.dumps({"event": event, "data": data}))
