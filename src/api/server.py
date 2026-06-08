"""FastAPI server for CodeGuardian — production-grade API."""

from __future__ import annotations

import uuid
import asyncio
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Query, Header, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from src.di.container import create_app_context, AppContext
from src.agents.graph import build_code_review_graph
from src.agents.state import CodeReviewState

app = FastAPI(
    title="CodeGuardian API",
    description="FAANG-grade cognitive code review API",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)

# In-memory store (replace with PostgreSQL in production)
_reviews: dict[str, dict] = {}
_ctx = create_app_context()


# ============================================================
# Pydantic Models
# ============================================================

class ReviewRequest(BaseModel):
    repo_url: str = Field(..., description="Git repository URL")
    branch: str = Field("main", description="Branch to analyze")
    scope: str = Field("full", pattern="^(full|branch|files|diff)$")
    auto_fix: bool = False
    files: Optional[list[str]] = None
    severity_threshold: str = Field("medium", pattern="^(critical|high|medium|low|info)$")

class ReviewResponse(BaseModel):
    review_id: str
    status: str
    quality_score: Optional[float] = None
    summary: Optional[dict] = None
    created_at: str

class FindingResponse(BaseModel):
    id: str
    file: str
    line: int
    severity: str
    category: str
    title: str
    description: str
    recommendation: str
    cwe_id: Optional[str] = None
    auto_fixable: bool = False


# ============================================================
# Middleware / Auth
# ============================================================

async def authenticate(auth: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """Simple API key auth. Replace with JWT/OAuth in production."""
    if auth is None:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    # In production: validate against api_keys table
    if not auth.credentials.startswith("cg_"):
        raise HTTPException(status_code=401, detail="Invalid API key format")
    return {"tenant_id": "default", "user_id": "system"}


# ============================================================
# Routes
# ============================================================

@app.get("/v1/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.get("/v1/ready")
async def readiness():
    """Readiness check for Kubernetes."""
    return {"status": "ready"}

@app.post("/v1/reviews", response_model=ReviewResponse, status_code=202)
async def create_review(
    req: ReviewRequest,
    background_tasks: BackgroundTasks,
    auth: dict = Depends(authenticate),
):
    """Trigger a new code review."""
    review_id = str(uuid.uuid4())
    _reviews[review_id] = {
        "id": review_id,
        "status": "queued",
        "repo_url": req.repo_url,
        "branch": req.branch,
        "scope": req.scope,
        "auto_fix": req.auto_fix,
        "created_at": datetime.utcnow().isoformat(),
        "quality_score": None,
        "summary": None,
    }

    background_tasks.add_task(_run_review_task, review_id, req)

    return ReviewResponse(
        review_id=review_id,
        status="queued",
        created_at=_reviews[review_id]["created_at"],
    )

@app.get("/v1/reviews/{review_id}")
async def get_review(review_id: str, auth: dict = Depends(authenticate)):
    """Get review status and results."""
    review = _reviews.get(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return review

@app.get("/v1/reviews/{review_id}/findings")
async def get_findings(
    review_id: str,
    severity: Optional[str] = Query(None, pattern="^(critical|high|medium|low|info)$"),
    category: Optional[str] = None,
    limit: int = Query(50, le=200),
    auth: dict = Depends(authenticate),
):
    """Get paginated findings for a review."""
    review = _reviews.get(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    findings = review.get("findings", [])
    if severity:
        findings = [f for f in findings if f.get("severity") == severity]
    if category:
        findings = [f for f in findings if f.get("category") == category]

    return {
        "total": len(findings),
        "limit": limit,
        "findings": findings[:limit],
    }


# ============================================================
# Background Task
# ============================================================

async def _run_review_task(review_id: str, req: ReviewRequest):
    """Execute the review pipeline asynchronously."""
    try:
        _reviews[review_id]["status"] = "running"
        graph = build_code_review_graph(_ctx)

        initial_state: CodeReviewState = {
            "repository_url": req.repo_url,
            "local_path": "",
            "review_scope": req.scope,
            "target_branch": req.branch,
            "target_files": req.files,
            "severity_threshold": req.severity_threshold,
            "auto_fix_enabled": req.auto_fix,
            "config": _ctx.config,
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
            "analysis_start_time": __import__("time").time(),
            "llm_tokens_used": 0,
            "llm_cost_cents": 0.0,
            "user_feedback": [],
            "skip_categories": [],
        }

        import time
        import json

        config = {"configurable": {"thread_id": review_id}}
        final_state = initial_state.copy()

        async for event in graph.astream(initial_state, config):
            for node, delta in event.items():
                final_state.update(delta)
                _reviews[review_id]["current_step"] = delta.get("current_step", node)

        findings = final_state.get("prioritized_issues", [])
        _reviews[review_id].update({
            "status": "completed",
            "quality_score": final_state.get("quality_score"),
            "summary": {
                "total": len(findings),
                "critical": sum(1 for f in findings if f.get("severity") == "critical"),
                "high": sum(1 for f in findings if f.get("severity") == "high"),
                "medium": sum(1 for f in findings if f.get("severity") == "medium"),
                "low": sum(1 for f in findings if f.get("severity") == "low"),
            },
            "findings": findings[:100],
            "quality_score": final_state.get("quality_score"),
        })

    except Exception as e:
        _reviews[review_id]["status"] = "failed"
        _reviews[review_id]["error"] = str(e)


# ============================================================
# WebSocket for live progress
# ============================================================

@app.websocket("/v1/reviews/{review_id}/stream")
async def review_stream(websocket: WebSocket, review_id: str):
    """WebSocket endpoint for real-time review progress."""
    await websocket.accept()
    last_step = ""

    try:
        for _ in range(300):  # 5 minute timeout
            review = _reviews.get(review_id, {})
            current_step = review.get("current_step", "unknown")

            if current_step != last_step:
                await websocket.send_json({
                    "review_id": review_id,
                    "status": review.get("status", "unknown"),
                    "current_step": current_step,
                })
                last_step = current_step

            if review.get("status") in ("completed", "failed"):
                break

            await asyncio.sleep(1)
    except Exception:
        pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
