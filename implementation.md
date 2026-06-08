# CodeGuardian — FAANG-Grade Implementation Plan

> *Authored by a Principal Engineer with 50+ years of combined experience at Google, Meta, Amazon, Stripe, and OpenAI.*

---

## Table of Contents

1. [Executive Architecture](#1-executive-architecture)
2. [Phase 1 — Foundation (Weeks 1-2)](#2-phase-1--foundation-weeks-1-2)
3. [Phase 2 — Agent Intelligence (Weeks 3-6)](#3-phase-2--agent-intelligence-weeks-3-6)
4. [Phase 3 — Production Infrastructure (Weeks 7-10)](#4-phase-3--production-infrastructure-weeks-7-10)
5. [Phase 4 — Enterprise & Scale (Weeks 11-16)](#5-phase-4--enterprise--scale-weeks-11-16)
6. [Data Model](#6-data-model)
7. [API Design](#7-api-design)
8. [LLM Architecture](#8-llm-architecture)
9. [Observability](#9-observability)
10. [Security Model](#10-security-model)
11. [Cost Engineering](#11-cost-engineering)
12. [Testing Strategy](#12-testing-strategy)
13. [Deployment Topology](#13-deployment-topology)
14. [Operational Runbooks](#14-operational-runbooks)

---

## 1. Executive Architecture

### Core Principle

CodeGuardian is not a "linter wrapper." It is a **distributed reasoning system** that combines static analysis with LLM-based cognition. Each "agent" is a specialized reasoning microservice that communicates via an event bus. The orchestration layer (LangGraph) manages the DAG of analysis steps, but each step can be horizontally scaled independently.

```
                    ┌─────────────────────────────────────┐
                    │         API Gateway (Envoy)          │
                    │  Auth · Rate Limit · Observability   │
                    └──────────┬──────────────────────────┘
                               │
                    ┌──────────▼──────────────────────────┐
                    │        Orchestrator (LangGraph)      │
                    │  State Machine · DAG Scheduler       │
                    │  Checkpointing · Human-in-the-Loop   │
                    └──────────┬──────────────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
 ┌────────▼──────┐   ┌────────▼──────┐   ┌────────▼──────┐
 │  Ingestion    │   │  Analysis     │   │  Synthesis    │
 │  Service      │   │  Pipeline     │   │  Engine       │
 │               │   │               │   │               │
 │  Clone Repos  │   │  Static       │   │  Dedup        │
 │  Diff Parsing │   │  Security     │   │  Prioritize   │
 │  File Mapping │   │  Performance  │   │  Classify     │
 │  AST Cache    │   │  Logic (LLM)  │   │  Score        │
 └───────────────┘   └───────────────┘   └───────────────┘
                               │                    │
                               └────────┬───────────┘
                                        │
                               ┌────────▼───────────┐
                               │   Output Service    │
                               │                     │
                               │  GitHub Issues      │
                               │  PR Comments        │
                               │  Slack Notifications│
                               │  Email Reports      │
                               └─────────────────────┘
```

---

## 2. Phase 1 — Foundation (Weeks 1-2)

### Goal: Eliminate technical debt, establish single canonical codebase, make the tool **actually run** and produce real output.

### 2.1 Consolidate Codebase

**Action**: Delete root-level `main.py`, `graph.py`, `state.py`, `agents/`. Canonicalize on `src/`.

**Files to remove**:
- `main.py` (root)
- `graph.py` (root)
- `state.py` (root)
- `agents/` (root)
- `utils/config.py` (root)

**Files to update**:
- `src/main.py` — make it the single entry point
- `src/agents/__init__.py` — clean exports
- `src/agents/nodes.py` — remove all dead code

### 2.2 Dependency Injection Architecture

Replace the current pattern of global LLM/variable instantiation with a proper DI container.

```python
# src/di/container.py
from dataclasses import dataclass, field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from typing import Optional

@dataclass
class AppContext:
    llm: ChatGoogleGenerativeAI | ChatOpenAI
    config: dict
    vector_store: Optional[VectorStore] = None
    cache: Optional[CacheClient] = None
    metrics: Optional[MetricsClient] = None

# Factory — single source of truth
def create_app_context(config_path: str) -> AppContext:
    config = load_config(config_path)
    
    provider = config.get("llm_provider", "google")
    if provider == "google":
        llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp", temperature=0.1)
    elif provider == "openai":
        llm = ChatOpenAI(model="gpt-4o", temperature=0.1)
    
    return AppContext(
        llm=llm,
        config=config,
        vector_store=create_vector_store(config),
        cache=create_cache(config),
        metrics=create_metrics_client(config),
    )
```

### 2.3 Real LLM Integration in Static Analysis

Replace the dead chain in `run_static_analysis_node`:

```python
# src/agents/nodes.py
def run_static_analysis_node(state: CodeReviewState, ctx: AppContext) -> CodeReviewState:
    files = state.get("target_files", [])
    findings = []
    
    for file_path in files:
        # 1. Run pylint (synchronous, deterministic)
        lint_results = run_pylint(file_path)
        
        # 2. Read file content
        with open(file_path) as f:
            content = f.read()
        
        # 3. LLM reasoning — this is the value-add
        prompt = ChatPromptTemplate.from_messages([
            ("system", STATIC_ANALYSIS_SYSTEM_PROMPT),
            ("human", "File: {file_path}\n\n```python\n{content}\n```\n\nPylint output:\n{lint_output}")
        ])
        
        chain = prompt | ctx.llm.with_structured_output(FindingList)
        llm_findings = chain.invoke({
            "file_path": file_path,
            "content": content,
            "lint_output": json.dumps(lint_results, indent=2)
        })
        
        findings.extend(llm_findings.findings)
    
    state["static_analysis_findings"] = findings
    state["current_step"] = "static_analysis_complete"
    return state
```

### 2.4 System Prompt Engineering

```python
# src/prompts/static_analysis.py
STATIC_ANALYSIS_SYSTEM_PROMPT = """You are a senior staff engineer conducting a code review.
Analyze the provided code and pylint output for issues a human reviewer would catch.

Focus on:
1. **Logic errors** — conditions that are always true/false, off-by-one errors, race conditions
2. **Type safety** — implicit type conversions, unhandled None/optional values
3. **API misuse** — incorrect library/framework usage patterns
4. **Dead code** — unreachable branches, unused returns
5. **Error handling** — uncaught exceptions, swallowed errors, missing rollbacks
6. **Concurrency** — shared mutable state, missing locks, thread safety

Rules:
- Do NOT report pylint issues (they're already listed above)
- Do NOT suggest style changes (import order, naming, formatting)
- Do NOT report anything that pylint already covers
- Assign severity: critical = will cause incorrect behavior in production
- Assign severity: high = likely to cause bugs under edge cases
- Assign severity: medium = potential issue, depends on context

Output a JSON array of findings with: file, line, severity, category, title, description, recommendation
"""
```

### 2.5 Deliverables Checklist — Phase 1

- [ ] Single canonical codebase at `src/`
- [ ] Dependency injection container
- [ ] Static analysis node calls LLM and returns real findings
- [ ] All stub nodes raise `NotImplementedError`
- [ ] Severity sorting fixed
- [ ] 10-file limit removed
- [ ] Tests for static analysis node
- [ ] README updated to reflect current state

---

## 3. Phase 2 — Agent Intelligence (Weeks 3-6)

### Goal: Implement all 11 nodes with real LLM reasoning. Build the agent architecture properly.

### 3.1 Agent Base Class

```python
# src/agents/base.py
from abc import ABC, abstractmethod
from typing import Any
from di.container import AppContext
from state import CodeReviewState

class AnalysisAgent(ABC):
    """Base class for all analysis agents."""
    
    def __init__(self, ctx: AppContext):
        self.ctx = ctx
        self.llm = ctx.llm
        self.cache = ctx.cache
        self.metrics = ctx.metrics
    
    @abstractmethod
    async def analyze(self, state: CodeReviewState) -> CodeReviewState:
        ...
    
    @abstractmethod
    def category(self) -> str:
        ...
    
    async def __call__(self, state: CodeReviewState) -> CodeReviewState:
        with self.metrics.timer(f"agent.{self.category()}.duration"):
            try:
                result = await self.analyze(state)
                self.metrics.increment(f"agent.{self.category()}.success")
                return result
            except Exception as e:
                self.metrics.increment(f"agent.{self.category()}.failure")
                state["errors"].append(f"{self.category()}: {str(e)}")
                return state

class SecurityAgent(AnalysisAgent):
    def category(self) -> str:
        return "security"
    
    async def analyze(self, state: CodeReviewState) -> CodeReviewState:
        files = state.get("target_files", [])
        findings = []
        
        for file_path in files:
            # Run bandit
            bandit_results = await run_bandit(file_path)
            
            # Run semgrep
            semgrep_results = await run_semgrep(file_path)
            
            # LLM reasoning for CWE detection
            content = read_file(file_path)
            prompt = ChatPromptTemplate.from_messages([
                ("system", SECURITY_SYSTEM_PROMPT),
                ("human", "File: {path}\n\n{content}")
            ])
            
            llm_findings = await (prompt | self.llm.with_structured_output(FindingList)).ainvoke({
                "path": file_path,
                "content": content
            })
            
            # Merge and deduplicate
            findings.extend(self._merge_findings(bandit_results, semgrep_results, llm_findings))
        
        state["security_findings"] = findings
        return state
```

### 3.2 Node Registry

```python
# src/agents/registry.py
from agents.base import AnalysisAgent
from agents.security_agent import SecurityAgent
from agents.performance_agent import PerformanceAgent
from agents.logic_agent import LogicAgent
from agents.testing_agent import TestingAgent
from agents.pattern_agent import PatternAgent

AGENT_REGISTRY: dict[str, type[AnalysisAgent]] = {
    "static_analysis": StaticAnalysisAgent,
    "pattern_analysis": PatternAgent,
    "security_audit": SecurityAgent,
    "performance_analysis": PerformanceAgent,
    "testing_assessment": TestingAgent,
    "logic_verification": LogicAgent,
}

def get_enabled_agents(config: dict, ctx: AppContext) -> list[AnalysisAgent]:
    enabled = config.get("enabled_checks", list(AGENT_REGISTRY.keys()))
    return [AGENT_REGISTRY[name](ctx) for name in enabled if name in AGENT_REGISTRY]
```

### 3.3 Parallel Execution (Async Graph)

Replace sequential subprocess calls with async concurrency:

```python
# src/core/graph_builder.py
from langgraph.graph import StateGraph
from agents.registry import get_enabled_agents

def build_parallel_graph(ctx: AppContext, config: dict) -> StateGraph:
    agents = get_enabled_agents(config, ctx)
    
    workflow = StateGraph(CodeReviewState)
    
    # Add all agent nodes
    for agent in agents:
        workflow.add_node(agent.category(), agent)
    
    # Parallel fan-out from scope_definition
    workflow.add_node("scope_definition", define_scope_node)
    workflow.set_entry_point("scope_definition")
    
    agent_nodes = [agent.category() for agent in agents]
    for node in agent_nodes:
        workflow.add_edge("scope_definition", node)
    
    # Fan-in to synthesis
    workflow.add_node("synthesis", synthesis_node)
    for node in agent_nodes:
        workflow.add_edge(node, "synthesis")
    
    # Conditional: fix generation or skip
    workflow.add_conditional_edges(
        "synthesis",
        should_generate_fixes,
        {"generate_fixes": "fix_generation", "skip_fixes": "reporting"}
    )
    
    workflow.add_edge("fix_generation", "reporting")
    workflow.add_edge("reporting", END)
    
    return workflow.compile(checkpointer=ctx.checkpointer)
```

### 3.4 Security Agent Implementation

```python
# src/agents/security_agent.py
class SecurityAgent(AnalysisAgent):
    SECURITY_CATEGORIES = {
        "injection": ["CWE-77", "CWE-89", "CWE-94"],
        "xss": ["CWE-79"],
        "secret_leak": ["CWE-798"],
        "insecure_deserialization": ["CWE-502"],
        "path_traversal": ["CWE-22"],
        "ssrf": ["CWE-918"],
    }
    
    async def analyze(self, state: CodeReviewState) -> CodeReviewState:
        files = state.get("target_files", [])
        all_findings = []
        
        async def analyze_file(file_path: str) -> list[Finding]:
            content = read_file(file_path)
            
            # Bandit scan (fast, deterministic)
            try:
                bandit_result = subprocess.run(
                    ["bandit", "-f", "json", "-q", file_path],
                    capture_output=True, text=True, timeout=30
                )
                bandit_findings = parse_bandit_output(bandit_result.stdout)
            except subprocess.TimeoutExpired:
                bandit_findings = []
            
            # Semgrep scan (rule-based SAST)
            try:
                semgrep_result = subprocess.run(
                    ["semgrep", "--json", "--config", "auto", file_path],
                    capture_output=True, text=True, timeout=60
                )
                semgrep_findings = parse_semgrep_output(semgrep_result.stdout)
            except subprocess.TimeoutExpired:
                semgrep_findings = []
            
            # LLM reasoning for semantic security issues
            prompt = ChatPromptTemplate.from_messages([
                ("system", SECURITY_SYSTEM_PROMPT),
                ("human", FILE_CONTENT_TEMPLATE.format(path=file_path, content=content))
            ])
            
            llm_findings = await (prompt | self.llm.with_structured_output(SecurityFindingList)).ainvoke({
                "path": file_path,
                "content": content
            })
            
            return deduplicate_findings(bandit_findings + semgrep_findings + llm_findings.findings)
        
        # Parallel file analysis
        results = await asyncio.gather(*[analyze_file(f) for f in files], return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                state["errors"].append(f"Security analysis error: {result}")
            else:
                all_findings.extend(result)
        
        state["security_findings"] = all_findings
        return state
```

### 3.5 Logic Verification Agent (The Crown Jewel)

This is the agent that differentiates CodeGuardian from any existing tool:

```python
# src/agents/logic_agent.py
class LogicAgent(AnalysisAgent):
    async def analyze(self, state: CodeReviewState) -> CodeReviewState:
        files = state.get("target_files", [])
        findings = []
        
        for file_path in files:
            content = read_file(file_path)
            
            # Parse AST to understand function boundaries
            tree = ast.parse(content)
            functions = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
            
            for func in functions:
                func_code = ast.get_source_segment(content, func)
                
                # Extract function signature and docstring
                docstring = ast.get_docstring(func) or "No documentation"
                args = [(a.arg, a.annotation.id if isinstance(a.annotation, ast.Name) else "Any") 
                        for a in func.args.args]
                
                prompt = ChatPromptTemplate.from_messages([
                    ("system", LOGIC_VERIFICATION_SYSTEM_PROMPT),
                    ("human", f"""
Function: {func.name}
Parameters: {args}
Return type: {get_return_annotation(func)}
Docstring: {docstring}

Implementation:
```python
{func_code}
```

Analyze:
1. Does the implementation match the documented intent?
2. Are there edge cases not handled?
3. Are there race conditions or TOCTOU bugs?
4. Is the error handling correct?
5. Could this function produce incorrect results under any input?
                    """)
                ])
                
                result = await (prompt | self.llm.with_structured_output(LogicFinding)).ainvoke({})
                
                if result.severity != "none":
                    findings.append(Finding(
                        id=str(uuid.uuid4()),
                        file=file_path,
                        line=func.lineno,
                        severity=result.severity,
                        category="logic",
                        title=result.title,
                        description=result.description,
                        recommendation=result.recommendation,
                        auto_fixable=result.auto_fixable,
                    ))
        
        state["logic_findings"] = findings
        return state
```

### 3.6 Auto-Fix Generation (Real, Not Mock)

```python
# src/agents/fix_agent.py
class FixAgent:
    def __init__(self, ctx: AppContext):
        self.llm = ctx.llm
        self.cache = ctx.cache
    
    async def generate_fix(self, finding: Finding, file_content: str) -> FixResult | None:
        """Generate a surgical code fix for a specific finding."""
        
        cache_key = f"fix:{finding.id}:{hashlib.md5(file_content.encode()).hexdigest()}"
        cached = await self.cache.get(cache_key)
        if cached:
            return FixResult(**cached)
        
        context_lines = get_context_window(file_content, finding.line, window=10)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", FIX_GENERATION_SYSTEM_PROMPT),
            ("human", f"""
Issue: {finding.title}
Severity: {finding.severity}
Description: {finding.description}
File: {finding.file}
Line: {finding.line}

Code context (lines {finding.line - 10}–{finding.line + 10}):
```python
{context_lines}
```

Generate a minimal, safe fix that:
1. Changes only what's necessary to fix the issue
2. Preserves existing behavior for non-issue cases
3. Follows the codebase's existing patterns
4. Is syntactically valid Python

Output the fix as a unified diff format.
            """)
        ])
        
        result = await (self.llm.with_structured_output(FixResult)).ainvoke({})
        
        # Validate the fix
        if not self.validate_fix(result, file_content):
            return None
        
        # Cache the validated fix
        await self.cache.set(cache_key, result.dict(), ttl=86400)
        
        return result
    
    def validate_fix(self, fix: FixResult, original_content: str) -> bool:
        """Validate that the fix is safe to apply."""
        try:
            # Apply the diff
            patched = apply_diff(original_content, fix.diff)
            
            # Parse to ensure valid syntax
            ast.parse(patched)
            
            # TODO: Run the patched code's tests
            # TODO: Type-check the patched code
            
            return True
        except (SyntaxError, DiffError):
            return False
```

### 3.7 RAG Engine (Real Implementation)

```python
# src/rag/policy_engine.py
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.document_loaders import DirectoryLoader, TextLoader

class PolicyRAGEngine:
    def __init__(self, standards_dir: str, persist_dir: str = "./.rag_cache"):
        self.standards_dir = standards_dir
        self.persist_dir = persist_dir
        self.embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
        
        # Load or create vector store
        if os.path.exists(persist_dir) and os.listdir(persist_dir):
            self.vector_store = Chroma(
                embedding_function=self.embeddings,
                persist_directory=persist_dir
            )
        else:
            self.vector_store = self._index_documents()
    
    def _index_documents(self) -> Chroma:
        """Load, split, and index policy documents."""
        loader = DirectoryLoader(
            self.standards_dir,
            glob="**/*.{txt,md,pdf}",
            loader_cls=TextLoader,
            loader_kwargs={"encoding": "utf-8"},
            recursive=True
        )
        documents = loader.load()
        
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        chunks = text_splitter.split_documents(documents)
        
        return Chroma.from_documents(
            documents=chunks,
            embedding=self.embeddings,
            persist_directory=self.persist_dir
        )
    
    def query(self, query: str, k: int = 3) -> list[Document]:
        """Retrieve relevant policy sections."""
        return self.vector_store.similarity_search(query, k=k)
    
    def verify_code_against_policy(self, file_path: str, content: str) -> list[Dict]:
        """Compare code against relevant policies using LLM."""
        # Retrieve relevant policies
        policies = self.query(f"Coding standards for {file_path}")
        policy_context = "\n\n".join([p.page_content for p in policies])
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", POLICY_VERIFICATION_PROMPT),
            ("human", f"File: {file_path}\n\n{content}\n\nRelevant Policies:\n{policy_context}")
        ])
        
        chain = prompt | self.llm.with_structured_output(PolicyFindingList)
        return chain.invoke({})
```

### 3.8 Prompts Directory

Organize all prompts as immutable, tested modules:

```
src/prompts/
├── __init__.py
├── static_analysis.py     # System prompt for static analysis node
├── security.py            # Security audit prompts (injection, XSS, secrets)
├── performance.py         # Performance analysis prompts
├── logic_verification.py  # Deep logic reasoning prompt
├── fix_generation.py      # Code fix generation prompt
├── policy_verification.py # RAG-augmented policy check prompt
├── synthesis.py           # Finding prioritization and dedup prompt
├── system.py              # Global system prompt (shared context)
└── examples/
    ├── finding_output.json    # Example structured output
    └── fix_diff_output.diff   # Example fix output
```

### 3.9 Deliverables Checklist — Phase 2

- [ ] All 6 agent types implemented with real LLM integration
- [ ] Async parallel file processing across agents
- [ ] Real RAG engine with Chroma/vector store
- [ ] Auto-fix generation with diff output and syntax validation
- [ ] Prompts extracted to `src/prompts/` with tests
- [ ] Agent base class with error handling, metrics, caching

---

## 4. Phase 3 — Production Infrastructure (Weeks 7-10)

### Goal: Make this deployable, reliable, and observable.

### 4.1 Database Schema

```sql
-- PostgreSQL schema

CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    repository_url TEXT NOT NULL,
    provider VARCHAR(50) NOT NULL, -- 'github', 'gitlab', 'local'
    owner_id UUID NOT NULL REFERENCES users(id),
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE TABLE reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id),
    trigger VARCHAR(50) NOT NULL, -- 'manual', 'push', 'pull_request', 'schedule'
    commit_sha VARCHAR(40),
    branch VARCHAR(255),
    status VARCHAR(50) NOT NULL DEFAULT 'pending', -- pending, running, completed, failed
    total_findings INT DEFAULT 0,
    critical_count INT DEFAULT 0,
    high_count INT DEFAULT 0,
    medium_count INT DEFAULT 0,
    low_count INT DEFAULT 0,
    duration_ms INT,
    llm_tokens_used INT DEFAULT 0,
    llm_cost_cents INT DEFAULT 0,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE findings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    review_id UUID NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    line_start INT,
    line_end INT,
    column_start INT,
    column_end INT,
    severity VARCHAR(20) NOT NULL, -- critical, high, medium, low, info
    category VARCHAR(50) NOT NULL, -- security, performance, logic, style, etc.
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    recommendation TEXT,
    cwe_id VARCHAR(20),
    cvss_score DECIMAL(3,1),
    code_snippet TEXT,
    suggested_fix TEXT,
    auto_fixable BOOLEAN DEFAULT FALSE,
    fix_applied BOOLEAN DEFAULT FALSE,
    dismissed BOOLEAN DEFAULT FALSE,
    dismissed_by UUID REFERENCES users(id),
    dismissed_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_findings_review_id ON findings(review_id);
CREATE INDEX idx_findings_severity ON findings(severity);
CREATE INDEX idx_findings_category ON findings(category);
CREATE INDEX idx_reviews_project_id ON reviews(project_id);
CREATE INDEX idx_reviews_status ON reviews(status);

-- Historical trending
CREATE MATERIALIZED VIEW review_trends AS
SELECT
    project_id,
    DATE_TRUNC('day', created_at) AS day,
    COUNT(*) AS review_count,
    SUM(critical_count) AS total_critical,
    SUM(high_count) AS total_high,
    AVG(duration_ms) AS avg_duration_ms,
    SUM(llm_cost_cents) AS total_cost_cents
FROM reviews
GROUP BY project_id, DATE_TRUNC('day', created_at);
```

### 4.2 Queue Layer (Celery + Redis)

```python
# src/queue/tasks.py
from celery import Celery
from di.container import create_app_context
from core.graph_builder import build_parallel_graph

celery_app = Celery("codeguardian", broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"))

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60, acks_late=True)
def run_review(self, review_id: str, repo_url: str, branch: str, config_path: str):
    """Run a complete review as an async background task."""
    ctx = create_app_context(config_path)
    graph = build_parallel_graph(ctx, ctx.config)
    
    initial_state = build_initial_state(review_id, repo_url, branch, ctx.config)
    
    try:
        final_state = graph.invoke(initial_state, {"configurable": {"thread_id": review_id}})
        
        # Persist results
        persist_results(review_id, final_state)
        
        # Send notifications
        notify_completion(review_id, final_state)
        
        return {"status": "completed", "review_id": review_id}
    
    except Exception as e:
        self.retry(exc=e)
        return {"status": "failed", "review_id": review_id, "error": str(e)}
```

### 4.3 API Layer (FastAPI)

```python
# src/api/main.py
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="CodeGuardian API", version="1.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Dependency injection
async def get_current_user(token: str = Header(...)) -> User:
    return await authenticate_token(token)

@app.post("/v1/reviews", status_code=202)
async def create_review(
    repo_url: str = Body(...),
    branch: str = Body("main"),
    scope: str = Body("full"),
    auto_fix: bool = Body(False),
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
):
    """Trigger a new code review."""
    project = await get_or_create_project(user, repo_url)
    review = await create_review_record(project.id, user.id, branch)
    
    # Enqueue async task
    background_tasks.add_task(
        run_review_task,
        review_id=str(review.id),
        repo_url=repo_url,
        branch=branch,
        config_path=f"projects/{project.id}/.codeguardian.yml",
    )
    
    return {"review_id": str(review.id), "status": "queued"}

@app.get("/v1/reviews/{review_id}")
async def get_review(
    review_id: str,
    user: User = Depends(get_current_user),
):
    """Get review results."""
    review = await get_review_by_id(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    return ReviewResponse(
        id=str(review.id),
        status=review.status,
        summary=FindingSummary(
            total=review.total_findings,
            critical=review.critical_count,
            high=review.high_count,
            medium=review.medium_count,
            low=review.low_count,
        ),
        findings=await get_findings_for_review(review_id),
        duration_ms=review.duration_ms,
        llm_cost_cents=review.llm_cost_cents,
    )

@app.get("/v1/projects/{project_id}/trends")
async def get_trends(
    project_id: str,
    days: int = Query(30, le=365),
    user: User = Depends(get_current_user),
):
    """Get code quality trends over time."""
    return await get_review_trends(project_id, days)
```

### 4.4 Observability Stack

```python
# src/observability/metrics.py
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from contextlib import contextmanager

# Metrics definitions
REVIEW_DURATION = Histogram(
    'codeguardian_review_duration_seconds',
    'Time to complete a review',
    ['status'],
    buckets=[10, 30, 60, 120, 300, 600, 1800]
)

FINDINGS_COUNT = Counter(
    'codeguardian_findings_total',
    'Total findings by severity and category',
    ['severity', 'category']
)

LLM_TOKENS = Counter(
    'codeguardian_llm_tokens_total',
    'Total LLM tokens used',
    ['model', 'operation']
)

ACTIVE_REVIEWS = Gauge(
    'codeguardian_active_reviews',
    'Number of reviews currently in progress'
)

AGENT_DURATION = Histogram(
    'codeguardian_agent_duration_seconds',
    'Time per agent node execution',
    ['agent', 'status'],
    buckets=[1, 5, 10, 30, 60, 120]
)

@contextmanager
def track_agent_execution(agent_name: str):
    start = time.time()
    try:
        yield
        AGENT_DURATION.labels(agent=agent_name, status="success").observe(time.time() - start)
    except Exception:
        AGENT_DURATION.labels(agent=agent_name, status="failure").observe(time.time() - start)
        raise

# Structured logging
import structlog
logger = structlog.get_logger()

# Tracing with OpenTelemetry
from opentelemetry import trace
tracer = trace.get_tracer(__name__)
```

### 4.5 Caching Strategy

```python
# src/cache/analysis_cache.py
import hashlib
import json
from redis import Redis
from typing import Optional

class AnalysisCache:
    """Cache analysis results by file hash to avoid re-analyzing unchanged files."""
    
    def __init__(self, redis_client: Redis, ttl: int = 86400):
        self.redis = redis_client
        self.ttl = ttl
    
    def file_hash(self, file_path: str) -> str:
        with open(file_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()
    
    def get_cached_result(self, file_path: str, agent: str) -> Optional[list[dict]]:
        content_hash = self.file_hash(file_path)
        key = f"analysis:{content_hash}:{agent}"
        
        data = self.redis.get(key)
        if data:
            return json.loads(data)
        return None
    
    def set_cached_result(self, file_path: str, agent: str, findings: list[dict]):
        content_hash = self.file_hash(file_path)
        key = f"analysis:{content_hash}:{agent}"
        
        self.redis.setex(key, self.ttl, json.dumps(findings))
    
    def invalidate_for_project(self, project_id: str, changed_files: list[str]):
        """Invalidate cache for changed files after a git pull."""
        for file_path in changed_files:
            # Can't hash the new version yet, just invalidate all patterns for this file
            pattern = f"analysis:*:{project_id}:*"
            # In practice, use Redis SCAN to find and delete matching keys
```

### 4.6 Deliverables Checklist — Phase 3

- [ ] PostgreSQL schema with migrations
- [ ] Celery worker for async review processing
- [ ] FastAPI server with auth, rate limiting
- [ ] Prometheus metrics endpoint
- [ ] Structured logging with structlog
- [ ] OpenTelemetry distributed tracing
- [ ] Redis-based caching layer
- [ ] GitHub webhook endpoint for automatic reviews
- [ ] Dockerfile + docker-compose.yml

---

## 5. Phase 4 — Enterprise & Scale (Weeks 11-16)

### Goal: Multi-tenant, horizontally scalable, compliant, profitable.

### 5.1 Multi-Tenancy Architecture

```python
# src/enterprise/tenant.py
from sqlalchemy import Column, String, Integer, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base

class Tenant(Base):
    """Organization-level isolation."""
    __tablename__ = "tenants"
    
    id = Column(UUID, primary_key=True)
    name = Column(String(255), nullable=False)
    plan = Column(String(50), default="free")  # free, pro, enterprise
    settings = Column(JSON, default={})
    
    # Rate limits
    reviews_per_day = Column(Integer, default=10)
    concurrent_reviews = Column(Integer, default=1)
    max_files_per_review = Column(Integer, default=1000)
    
    # Security
    sso_enabled = Column(Boolean, default=False)
    sso_provider = Column(String(50))
    audit_log_enabled = Column(Boolean, default=False)
    
    # Billing
    stripe_customer_id = Column(String(100))
    stripe_subscription_id = Column(String(100))
    
    # Data isolation
    database_schema = Column(String(50))  # For multi-schema isolation
    storage_bucket = Column(String(100))  # S3 bucket per tenant
```

### 5.2 Horizontal Scaling

```
                    ┌──────────────────────────────────────────┐
                    │           Global Load Balancer           │
                    │           (AWS ALB / GCP HTTP LB)         │
                    └──────────┬───────────────────────────────┘
                               │
                    ┌──────────▼───────────────────────────────┐
                    │          API Gateway (Kong)              │
                    │  Auth · Rate Limit · Tenant Routing      │
                    └──────────┬───────────────────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
 ┌────────▼────────┐  ┌───────▼────────┐  ┌────────▼────────┐
 │  API Pod        │  │  API Pod       │  │  API Pod        │
 │  (FastAPI)      │  │  (FastAPI)     │  │  (FastAPI)      │
 └────────┬────────┘  └───────┬────────┘  └────────┬────────┘
          │                    │                    │
          └────────────────────┼────────────────────┘
                               │
                    ┌──────────▼───────────────────────────────┐
                    │        Message Queue (Kafka)             │
                    │  Topics: reviews, findings, notifications │
                    └──────────┬───────────────────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
 ┌────────▼────────┐  ┌───────▼────────┐  ┌────────▼────────┐
 │  Worker Pool    │  │  Worker Pool   │  │  Worker Pool    │
 │  (Celery/K8s)   │  │  (Celery/K8s)  │  │  (Celery/K8s)   │
 │  autoscaled by  │  │  autoscaled by │  │  autoscaled by  │
 │  queue depth    │  │  queue depth   │  │  queue depth    │
 └────────┬────────┘  └───────┬────────┘  └────────┬────────┘
          │                    │                    │
          └────────────────────┼────────────────────┘
                               │
                    ┌──────────▼───────────────────────────────┐
                    │         Data Layer                       │
                    │                                          │
                    │  PostgreSQL (Primary + Read Replicas)    │
                    │  Redis (Cache + Queue + Session)         │
                    │  S3/GCS (Reports + Artifacts)            │
                    │  Elasticsearch (Full-text search)        │
                    └──────────────────────────────────────────┘
```

### 5.3 Billing & Usage Tracking

```python
# src/billing/tracker.py
class UsageTracker:
    """Track usage per tenant for billing."""
    
    METRICS = {
        "reviews": {"unit": "review", "free_allowance": 10},
        "files_analyzed": {"unit": "file", "free_allowance": 1000},
        "llm_tokens": {"unit": "token", "free_allowance": 100000},
        "storage_gb": {"unit": "gb_month", "free_allowance": 1},
    }
    
    async def check_quota(self, tenant_id: str, metric: str) -> bool:
        """Check if tenant has quota remaining."""
        allowance = self.METRICS[metric]["free_allowance"]
        # Check current usage
        current = await self.get_current_usage(tenant_id, metric)
        
        if current >= allowance:
            # Check if tenant has paid plan with higher limit
            tenant = await get_tenant(tenant_id)
            if tenant.plan == "enterprise":
                return True  # No hard limit for enterprise
            return False
        return True
    
    async def record_usage(self, tenant_id: str, metric: str, amount: int):
        """Record usage for billing."""
        await self.redis.incrby(f"usage:{tenant_id}:{metric}:{date.today()}", amount)
        await self.redis.expire(f"usage:{tenant_id}:{metric}:{date.today()}", 86400 * 31)
    
    async def generate_invoice(self, tenant_id: str, period_start: date, period_end: date) -> Invoice:
        """Generate invoice based on usage."""
        usage = await self.get_period_usage(tenant_id, period_start, period_end)
        
        line_items = []
        for metric, amount in usage.items():
            overage = max(0, amount - self.METRICS[metric]["free_allowance"])
            if overage > 0:
                line_items.append(LineItem(
                    description=f"{metric} overage",
                    quantity=overage,
                    unit_price=self.METRICS[metric]["overage_price"],
                    total=overage * self.METRICS[metric]["overage_price"],
                ))
        
        return Invoice(tenant_id=tenant_id, line_items=line_items, total=sum(li.total for li in line_items))
```

### 5.4 Compliance Readiness

```python
# src/enterprise/audit.py
class AuditLogger:
    """Immutable audit trail for enterprise compliance (SOC2, SOX)."""
    
    async def log_event(self, event: AuditEvent):
        """Write audit event to append-only log."""
        event_hash = self._compute_hash(event)
        
        # Write to PostgreSQL (audit schema)
        await self.db.execute(
            "INSERT INTO audit.events (id, tenant_id, user_id, action, resource, details, hash, timestamp) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
            event.id, event.tenant_id, event.user_id, event.action,
            event.resource, event.details, event_hash, event.timestamp
        )
        
        # Also write to S3/GCS for immutable backup
        await self.storage.append(
            f"audit/{event.tenant_id}/{event.timestamp:%Y/%m/%d}/events.jsonl",
            event.json() + "\n"
        )
    
    def _compute_hash(self, event: AuditEvent) -> str:
        """Chain hash with previous event for tamper evidence."""
        prev_hash = self.get_latest_hash(event.tenant_id)
        return hashlib.sha256(f"{prev_hash}{event.json()}".encode()).hexdigest()

# GDPR compliance
class DataDeletionService:
    async def delete_user_data(self, user_id: str):
        """GDPR right to erasure."""
        async with self.db.transaction():
            await self.db.execute("DELETE FROM users WHERE id = $1", user_id)
            await self.db.execute("UPDATE findings SET dismissed_by = NULL WHERE dismissed_by = $1", user_id)
            await self.db.execute("UPDATE reviews SET owner_id = 'deleted' WHERE owner_id = $1", user_id)
        # Log the deletion for compliance
        await self.audit.log_event(AuditEvent(
            action="data_deletion",
            resource=f"user:{user_id}",
            details="GDPR Article 17 erasure request",
        ))
```

### 5.5 Deliverables Checklist — Phase 4

- [ ] Multi-tenant isolation (schema-per-tenant)
- [ ] Kubernetes deployment manifests
- [ ] Horizontal pod autoscaling (CPU + queue depth)
- [ ] Usage tracking and billing system
- [ ] Stripe integration for subscriptions
- [ ] Audit logging (immutable, tamper-evident)
- [ ] GDPR data deletion service
- [ ] SOC2 compliance documentation
- [ ] SLA monitoring and uptime dashboard
- [ ] Penetration testing completed

---

## 6. Data Model

### 6.1 Core Entities

```
User ──1:N── Project ──1:N── Review ──1:N── Finding
  │                │
  │                └──1:1── Config (.codeguardian.yml)
  │
  └──M:N── Tenant (Organization)
```

### 6.2 Finding Severity Classification

| Severity | Definition | SLA | Action |
|---|---|---|---|
| Critical | Causes data loss, security breach, or incorrect production behavior | Fix within 24h | Auto-created P0 incident |
| High | Likely to cause bugs in edge cases, potential security vulnerability | Fix within 72h | PR must-fix label |
| Medium | Code smell, minor performance issue, potential future bug | Fix within 2 weeks | Added to backlog |
| Low | Style inconsistency, minor optimization | Nice to have | Ignore or batch |
| Info | Informational only, not actionable | No SLA | Reference only |

### 6.3 Scoring Algorithm

```python
# src/scoring/quality_score.py
def calculate_quality_score(findings: list[Finding], total_files: int) -> float:
    """Calculate a 0-100 code quality score."""
    
    WEIGHTS = {
        "critical": -15,
        "high": -8,
        "medium": -3,
        "low": -1,
        "info": 0,
    }
    
    CATEGORY_MULTIPLIERS = {
        "security": 2.0,     # Security issues weighted double
        "logic": 1.8,        # Logic bugs weighted heavily
        "performance": 1.2,
        "testing": 1.0,
        "pattern": 0.8,
        "style": 0.5,
    }
    
    score = 100.0
    for finding in findings:
        weight = WEIGHTS.get(finding.severity, -1)
        multiplier = CATEGORY_MULTIPLIERS.get(finding.category, 1.0)
        score += weight * multiplier
    
    # Normalize by file count
    score = max(0, min(100, score * (1 + math.log10(max(total_files, 1)) * 0.1)))
    
    return round(score, 1)
```

---

## 7. API Design

### 7.1 REST Endpoints

```
POST   /v1/reviews                              # Trigger a new review
GET    /v1/reviews/{id}                         # Get review results
GET    /v1/reviews/{id}/findings                # Paginated findings list
PATCH  /v1/reviews/{id}/findings/{fid}          # Dismiss/acknowledge finding
POST   /v1/reviews/{id}/findings/{fid}/fix      # Generate auto-fix

POST   /v1/projects                             # Register a project
GET    /v1/projects/{id}                        # Project details
PATCH  /v1/projects/{id}                        # Update project settings
GET    /v1/projects/{id}/trends                 # Quality trends over time

GET    /v1/users/me                             # Current user profile
GET    /v1/users/me/usage                       # Usage statistics

POST   /v1/webhooks/github                      # GitHub webhook receiver
POST   /v1/webhooks/gitlab                      # GitLab webhook receiver

GET    /v1/admin/tenants                        # (Admin) List tenants
GET    /v1/admin/tenants/{id}/usage             # (Admin) Tenant usage
GET    /v1/admin/metrics                        # Prometheus metrics
```

### 7.2 WebSocket for Live Updates

```python
# src/api/websocket.py
@app.websocket("/v1/reviews/{review_id}/stream")
async def review_stream(websocket: WebSocket, review_id: str):
    await websocket.accept()
    
    # Subscribe to Redis pub/sub for this review
    pubsub = await redis.subscribe(f"review:{review_id}:progress")
    
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_json(json.loads(message["data"]))
                
                # Check if review is complete
                data = json.loads(message["data"])
                if data.get("status") == "completed":
                    break
    except WebSocketDisconnect:
        await redis.unsubscribe(f"review:{review_id}:progress")
```

---

## 8. LLM Architecture

### 8.1 Model Selection Strategy

| Task | Model | Rationale | Cost/Task |
|---|---|---|---|
| Static analysis | Gemini 2.0 Flash | Fast, cheap, good at code | $0.0003/file |
| Security audit | GPT-4o | Best at security reasoning | $0.002/file |
| Logic verification | Claude 3.5 Sonnet | Superior at deep reasoning | $0.003/file |
| Fix generation | GPT-4o | Best code generation | $0.005/fix |
| Policy RAG | Gemini Embedding | Cheapest embeddings | $0.0001/query |
| Synthesis | Gemini 2.0 Flash | Simple aggregation | $0.0005/review |

### 8.2 Fallback Chain

```python
# src/llm/router.py
class LLMRouter:
    """Route to best model with fallback chain."""
    
    FALLBACK_CHAIN = {
        "gpt-4o": ["gpt-4o-mini", "gemini-2.0-flash"],
        "claude-3.5-sonnet": ["claude-3-haiku", "gemini-2.0-flash"],
        "gemini-2.0-flash": [],  # No fallback (cheapest)
    }
    
    async def generate(self, task: str, prompt: BasePrompt, 
                       preferred_model: str, max_retries: int = 3) -> BaseMessage:
        """Generate with automatic fallback."""
        
        models = [preferred_model] + self.FALLBACK_CHAIN.get(preferred_model, [])
        
        for model_name in models:
            for attempt in range(max_retries):
                try:
                    llm = self.get_llm(model_name)
                    
                    with self.metrics.timer(f"llm.{model_name}.duration"):
                        response = await (prompt | llm).ainvoke({})
                    
                    tokens = self.count_tokens(prompt, response)
                    self.metrics.increment(f"llm.{model_name}.tokens", tokens)
                    self.metrics.increment(f"llm.{model_name}.cost", tokens * self.get_cost_per_token(model_name))
                    
                    return response
                    
                except (RateLimitError, ServerError) as e:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    # Fall through to next model
                    break
                    
                except InvalidRequestError:
                    # Don't retry bad requests
                    break
        
        raise AllModelsFailedError(f"All models failed for task: {task}")
```

### 8.3 Token Budget Management

```python
# src/llm/token_budget.py
class TokenBudget:
    """Track and cap token usage per review."""
    
    MAX_TOKENS_PER_FILE = 8000
    MAX_TOKENS_PER_REVIEW = 200000
    MAX_COST_PER_REVIEW_CENTS = 50  # $0.50 max per review
    
    def __init__(self, review_id: str):
        self.review_id = review_id
        self.usage: dict[str, int] = defaultdict(int)
    
    def can_process(self, file_path: str) -> bool:
        """Check if we can afford to process this file."""
        current_total = sum(self.usage.values())
        return current_total < self.MAX_TOKENS_PER_REVIEW
    
    def estimate_file_cost(self, file_path: str) -> int:
        """Estimate tokens needed for a file."""
        with open(file_path) as f:
            content = f.read()
        return min(len(content) * 1.3, self.MAX_TOKENS_PER_FILE)
    
    def record(self, model: str, tokens: int):
        self.usage[model] += tokens
    
    def cost_cents(self) -> float:
        return sum(
            tokens * self.COST_PER_TOKEN[model]
            for model, tokens in self.usage.items()
        )
```

---

## 9. Observability

### 9.1 Dashboard (Grafana)

```json
{
  "title": "CodeGuardian Production Dashboard",
  "panels": [
    {
      "title": "Reviews Per Minute",
      "type": "timeseries",
      "targets": ["rate(codeguardian_review_duration_seconds_count[5m])"]
    },
    {
      "title": "P99 Review Duration",
      "type": "timeseries",
      "targets": ["histogram_quantile(0.99, codeguardian_review_duration_seconds_bucket)"]
    },
    {
      "title": "Findings by Severity",
      "type": "pie",
      "targets": ["sum(codeguardian_findings_total) by (severity)"]
    },
    {
      "title": "LLM Cost Per Day",
      "type": "bar",
      "targets": ["sum(codeguardian_llm_cost_cents_total[$__range])"]
    },
    {
      "title": "Active Reviews",
      "type": "stat",
      "targets": ["codeguardian_active_reviews"]
    },
    {
      "title": "Agent Error Rate",
      "type": "timeseries",
      "targets": ["rate(codeguardian_agent_duration_seconds_count{status='failure'}[5m]) / rate(codeguardian_agent_duration_seconds_count[5m])"]
    }
  ]
}
```

### 9.2 Alerts (Prometheus + PagerDuty)

```yaml
# alerts.yaml
groups:
  - name: codeguardian
    rules:
      - alert: ReviewFailureRateHigh
        expr: rate(codeguardian_review_duration_seconds_count{status="failure"}[5m]) / rate(codeguardian_review_duration_seconds_count[5m]) > 0.1
        for: 5m
        labels: { severity: critical }
        annotations:
          summary: "Review failure rate > 10%"
          
      - alert: LLMCostSpike
        expr: rate(codeguardian_llm_cost_cents_total[1h]) > 1000
        for: 10m
        labels: { severity: warning }
        annotations:
          summary: "LLM cost exceeding $10/hour"
          
      - alert: QueueBacklogGrowing
        expr: celery_queue_depth > 100
        for: 5m
        labels: { severity: warning }
        annotations:
          summary: "Review queue backlog > 100 items"
          
      - alert: CriticalFindingThreshold
        expr: sum(codeguardian_findings_total{severity="critical"}) > 10
        for: 1m
        labels: { severity: info }
        annotations:
          summary: "More than 10 critical findings in latest review"
```

---

## 10. Security Model

### 10.1 Authentication & Authorization

```python
# src/security/auth.py
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

security = HTTPBearer()

async def authenticate(credentials: HTTPAuthorizationCredentials = Security(security)) -> User:
    """Authenticate user via JWT."""
    try:
        payload = jwt.decode(
            credentials.credentials,
            os.getenv("JWT_SECRET"),
            algorithms=["RS256"],
            options={
                "verify_exp": True,
                "verify_aud": True,
                "aud": "codeguardian-api",
            }
        )
        
        user = await get_user_by_id(payload["sub"])
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="Invalid user")
        
        return user
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def require_role(user: User = Depends(authenticate), role: str = None) -> User:
    """Role-based access control."""
    if role and role not in user.roles:
        raise HTTPException(status_code=403, detail=f"Requires role: {role}")
    return user
```

### 10.2 API Key Management

```python
# src/security/api_keys.py
class APIKeyManager:
    """Securely manage API keys for external integrations."""
    
    KEY_PREFIX = "cg_"
    
    async def create_key(self, user_id: str, name: str, permissions: list[str]) -> str:
        """Generate a new API key."""
        raw_key = f"{self.KEY_PREFIX}{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha384(raw_key.encode()).hexdigest()
        
        await self.db.execute(
            "INSERT INTO api_keys (id, key_hash, user_id, name, permissions, created_at) "
            "VALUES ($1, $2, $3, $4, $5, $6)",
            str(uuid.uuid4()), key_hash, user_id, name, permissions, datetime.utcnow()
        )
        
        return raw_key  # Return raw key only at creation time
    
    async def validate_key(self, raw_key: str) -> Optional[APIKey]:
        """Validate an API key."""
        if not raw_key.startswith(self.KEY_PREFIX):
            return None
        
        key_hash = hashlib.sha384(raw_key.encode()).hexdigest()
        return await self.db.fetchrow(
            "SELECT * FROM api_keys WHERE key_hash = $1 AND revoked = false",
            key_hash
        )
```

### 10.3 Input Sanitization

```python
# src/security/sanitize.py
import shlex
from pathlib import Path

def sanitize_repo_url(url: str) -> str:
    """Validate and sanitize repository URL."""
    parsed = urlparse(url)
    
    # Only allow git://, https://, ssh://
    if parsed.scheme not in ("git", "https", "ssh"):
        raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")
    
    # Block file:// and other dangerous schemes
    if parsed.scheme in ("file", "data", "local"):
        raise ValueError("Local file URLs not allowed")
    
    # Ensure no shell metacharacters
    if any(c in url for c in [";", "|", "`", "$", "(", ")", "{", "}"]):
        raise ValueError("URL contains shell metacharacters")
    
    return url

def sanitize_file_path(path: str) -> str:
    """Prevent path traversal."""
    resolved = Path(path).resolve()
    
    # Ensure path is within the cloned repo
    base = Path.cwd() / "repos"
    if not str(resolved).startswith(str(base)):
        raise ValueError("Path traversal detected")
    
    return str(resolved)

def sanitize_shell_command(cmd: list[str]) -> list[str]:
    """Safely quote shell command arguments."""
    return [shlex.quote(arg) for arg in cmd]
```

---

## 11. Cost Engineering

### 11.1 Cost Projections (1000 reviews/day)

| Component | Unit Cost | Monthly | Annual |
|---|---|---|---|
| Gemini API (static analysis) | $0.0003/file × 100 files | $900 | $10,800 |
| GPT-4o (security) | $0.002/file × 100 files | $6,000 | $72,000 |
| Claude (logic) | $0.003/file × 50 files | $4,500 | $54,000 |
| GPT-4o (fixes) | $0.005/fix × 5 fixes | $750 | $9,000 |
| Redis (cache + queue) | $50/month (managed) | $50 | $600 |
| PostgreSQL | $200/month (RDS) | $200 | $2,400 |
| S3 storage | $0.023/GB × 50GB | $1.15 | $13.80 |
| EC2/K8s compute | $500/month (8 cores, 32GB) | $500 | $6,000 |
| **Total** | | **$12,901** | **$154,814** |

### 11.2 Optimization Strategies

1. **Context caching**: Cache file analysis results. Same file = same result. 50% savings.
2. **Batch LLM calls**: Send 5 files per LLM call instead of 1. 80% fewer API calls.
3. **Cheap model for easy files**: Route low-complexity files to Gemini Flash. ~60% savings.
4. **Incremental analysis**: Only analyze changed files. ~80% savings after initial review.
5. **Token compression**: Strip comments, minify before sending to LLM. ~30% token reduction.
6. **Result deduplication**: Don't send same error patterns repeatedly. ~10% savings.

### 11.3 Estimated Optimized Monthly Cost

| Optimization | Savings | Optimized Monthly |
|---|---|---|
| Context caching | -50% | $6,450 |
| Batch LLM calls | -20% (additional) | $5,160 |
| Cheap model routing | -60% (of LLM costs) | $3,870 |
| Incremental analysis | -80% (after initial) | $2,580 |
| **Total optimized** | | **~$2,580/month** |
| **Per review** | | **~$0.086/review** |

---

## 12. Testing Strategy

### 12.1 Test Pyramid

```
         ╱─────╲
        ╱  E2E  ╲         2 tests (full review workflow)
       ╱─────────╲
      ╱ Integration╲      10 tests (DB, API, queue)
     ╱───────────────╲
    ╱    Component    ╲    20 tests (each agent in isolation)
   ╱─────────────────────╲
  ╱      Unit Tests       ╲  100+ tests (tools, prompts, state, scoring)
 ╱───────────────────────────╲
```

### 12.2 Unit Tests

```python
# tests/unit/test_security_agent.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from agents.security_agent import SecurityAgent
from di.container import AppContext

@pytest.fixture
def mock_ctx():
    ctx = MagicMock(spec=AppContext)
    ctx.llm = AsyncMock()
    ctx.llm.with_structured_output.return_value = ctx.llm
    ctx.llm.ainvoke.return_value = SecurityFindingList(findings=[])
    ctx.cache = AsyncMock()
    ctx.cache.get.return_value = None
    ctx.metrics = MagicMock()
    return ctx

@pytest.mark.asyncio
async def test_security_agent_detects_sql_injection(mock_ctx, tmp_path):
    """Security agent should detect raw SQL in Python files."""
    test_file = tmp_path / "db.py"
    test_file.write_text("""
import sqlite3
def get_user(user_id):
    conn = sqlite3.connect('users.db')
    query = f"SELECT * FROM users WHERE id = {user_id}"
    return conn.execute(query).fetchall()
""")
    
    # Mock LLM to return SQL injection finding
    mock_ctx.llm.ainvoke.return_value = SecurityFindingList(findings=[
        Finding(
            id="test-1",
            file=str(test_file),
            line=4,
            severity="critical",
            category="security",
            title="SQL Injection via f-string",
            description="User input directly interpolated into SQL query",
            recommendation="Use parameterized query with ? placeholders",
            cwe_id="CWE-89",
            cvss_score=9.8,
        )
    ])
    
    agent = SecurityAgent(mock_ctx)
    state = CodeReviewState(target_files=[str(test_file)], config={})
    result = await agent.analyze(state)
    
    assert len(result["security_findings"]) == 1
    assert result["security_findings"][0]["cwe_id"] == "CWE-89"
    assert result["security_findings"][0]["severity"] == "critical"
```

### 12.3 Integration Tests

```python
# tests/integration/test_review_api.py
import pytest
from httpx import AsyncClient
from api.main import app

@pytest.mark.asyncio
async def test_full_review_workflow(test_db, test_redis, auth_headers):
    """Test complete review lifecycle via API."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # 1. Create review
        response = await client.post(
            "/v1/reviews",
            json={"repo_url": "https://github.com/test/demo.git", "branch": "main"},
            headers=auth_headers,
        )
        assert response.status_code == 202
        review_id = response.json()["review_id"]
        
        # 2. Poll until complete
        for _ in range(30):
            response = await client.get(f"/v1/reviews/{review_id}", headers=auth_headers)
            if response.json()["status"] == "completed":
                break
            await asyncio.sleep(1)
        
        assert response.json()["status"] == "completed"
        assert response.json()["summary"]["total"] > 0
        
        # 3. Get findings
        response = await client.get(f"/v1/reviews/{review_id}/findings", headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json()["findings"]) > 0
```

### 12.4 Prompt Tests

```python
# tests/prompts/test_security_prompt.py
from langchain_core.pydantic_v1 import BaseModel, Field
from prompts.security import SECURITY_SYSTEM_PROMPT

class TestSecurityPrompt:
    """Validate security prompt quality."""
    
    def test_prompt_mentions_all_cwe_categories(self):
        """Security prompt should reference all OWASP Top 10."""
        assert "CWE-89" in SECURITY_SYSTEM_PROMPT  # SQL Injection
        assert "CWE-79" in SECURITY_SYSTEM_PROMPT  # XSS
        assert "CWE-78" in SECURITY_SYSTEM_PROMPT  # OS Injection
        assert "CWE-22" in SECURITY_SYSTEM_PROMPT  # Path Traversal
        assert "CWE-502" in SECURITY_SYSTEM_PROMPT  # Deserialization
        assert "CWE-918" in SECURITY_SYSTEM_PROMPT  # SSRF
        assert "CWE-798" in SECURITY_SYSTEM_PROMPT  # Hardcoded Credentials
    
    def test_prompt_has_output_format_definition(self):
        """Prompt should specify structured output format."""
        assert "JSON" in SECURITY_SYSTEM_PROMPT
        assert "severity" in SECURITY_SYSTEM_PROMPT
        assert "cwe_id" in SECURITY_SYSTEM_PROMPT
        assert "recommendation" in SECURITY_SYSTEM_PROMPT
    
    def test_prompt_has_severity_scale(self):
        """Prompt should define severity levels."""
        assert "critical" in SECURITY_SYSTEM_PROMPT
        assert "high" in SECURITY_SYSTEM_PROMPT
        assert "medium" in SECURITY_SYSTEM_PROMPT
        assert "low" in SECURITY_SYSTEM_PROMPT
    
    def test_prompt_has_false_positive_guardrails(self):
        """Prompt should include instructions to avoid false positives."""
        assert any(phrase in SECURITY_SYSTEM_PROMPT for phrase in [
            "Do NOT report",
            "Ignore",
            "Only report if",
            "False positive",
        ])
```

### 12.5 Load Tests

```python
# tests/load/locustfile.py
from locust import HttpUser, task, between

class CodeGuardianUser(HttpUser):
    wait_time = between(1, 5)
    
    @task
    def trigger_review(self):
        self.client.post("/v1/reviews", json={
            "repo_url": "https://github.com/test/demo.git",
            "branch": "main",
        }, headers={"Authorization": "Bearer test-key"})
    
    @task
    def get_results(self):
        self.client.get("/v1/reviews/some-id", headers={"Authorization": "Bearer test-key"})

# Target: 100 concurrent users, < 2s p99 response time
```

---

## 13. Deployment Topology

### 13.1 Docker Compose (Development)

```yaml
# docker-compose.yml
version: "3.9"

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: codeguardian
      POSTGRES_USER: cg_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./migrations:/docker-entrypoint-initdb.d
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  api:
    build: .
    command: uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - postgres
      - redis
    volumes:
      - .:/app
      - repos:/app/repos

  worker:
    build: .
    command: celery -A src.queue.tasks worker --concurrency=4 --loglevel=info
    env_file: .env
    depends_on:
      - postgres
      - redis
    volumes:
      - .:/app
      - repos:/app/repos

  metrics:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  dashboard:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - grafana-data:/var/lib/grafana
```

### 13.2 Kubernetes (Production)

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: codeguardian-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: codeguardian-api
  template:
    metadata:
      labels:
        app: codeguardian-api
    spec:
      containers:
      - name: api
        image: codeguardian/api:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: codeguardian-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: codeguardian-secrets
              key: redis-url
        resources:
          requests:
            cpu: "500m"
            memory: "512Mi"
          limits:
            cpu: "2"
            memory: "2Gi"
        livenessProbe:
          httpGet:
            path: /v1/health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 15
        readinessProbe:
          httpGet:
            path: /v1/ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: codeguardian-api
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: codeguardian-api
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Pods
    pods:
      metric:
        name: celery_queue_depth
      target:
        type: AverageValue
        averageValue: 10
```

---

## 14. Operational Runbooks

### Runbook: Review Failure

```
ALERT: ReviewFailureRateHigh

1. CHECK: Grafana dashboard → Reviews panel
   - Is there a spike in 5xx errors?
   - Is the LLM API returning errors?

2. IF LLM API ERROR:
   - Check https://status.openai.com or https://status.cloud.google.com
   - Fallback model chain should auto-handle
   - If not: `kubectl edit configmap codeguardian-config` → set preferred_model to fallback

3. IF DATABASE ERROR:
   - `kubectl exec -it postgres-0 -- pg_isready`
   - Check connection pool: `kubectl logs deployment/codeguardian-api | grep "connection pool"`
   - Restart pool: `kubectl rollout restart deployment/codeguardian-api`

4. IF QUEUE BACKLOG:
   - Scale workers: `kubectl scale deployment/codeguardian-worker --replicas=20`
   - Check queue depth: `redis-cli LLEN review_queue`
   - Clear stale messages if needed
```

### Runbook: Cost Spike

```
ALERT: LLMCostSpike

1. CHECK: Cost dashboard → Cost per model per hour
   - Which model is spiking?
   - Is there a specific tenant/project?

2. IF MALICIOUS TENANT:
   - Suspend tenant: `UPDATE tenants SET active = false WHERE id = '...'`
   - Block API key: `UPDATE api_keys SET revoked = true WHERE id = '...'`

3. IF LEGITIMATE SPIKE:
   - Check if a large repo was scanned (>10K files)
   - Enable aggressive caching
   - Reduce max_files_per_review for this tenant
   - Send usage alert to tenant

4. PREVENTATIVE:
   - Add hard cap: `UPDATE tenants SET max_daily_cost_cents = 500 WHERE plan = 'pro'`
   - Enable token budget enforcement
```

### Runbook: Security Incident

```
ALERT: Possible data exposure

1. IMMEDIATE: Revoke exposed API keys
   `UPDATE api_keys SET revoked = true WHERE ...`

2. INVESTIGATE:
   - Check audit logs for unauthorized access
   - Check S3 bucket for exposed report data
   - Rotate database credentials

3. CONTAIN:
   - Block tenant: `UPDATE tenants SET active = false`
   - Isolate affected database schema

4. REMEDIATE:
   - Patch vulnerability
   - Run penetration test
   - Update security documentation

5. POST-MORTEM:
   - Root cause analysis within 24h
   - Update runbooks
   - Implement preventive measures
```

---

## Final Implementation Priority Matrix

```
                    High Impact                  Low Impact
                  ┌─────────────────┬─────────────────────────┐
   Easy to Do     │  P0 (Do Now)    │    P2 (Do Later)        │
                  │                 │                         │
                  │  • Consolidate  │  • Dashboard UI         │
                  │    codebases    │  • IDE plugin           │
                  │  • Call LLM     │  • Custom rule engine   │
                  │  • Fix sorting  │  • Trend analysis       │
                  │  • Remove stubs │                         │
                  ├─────────────────┼─────────────────────────┤
   Hard to Do     │  P1 (Do Next)   │    P3 (Maybe Never)     │
                  │                 │                         │
                  │  • DB schema    │  • Multi-region HA      │
                  │  • API server   │  • On-premise deploy    │
                  │  • Async queue  │  • ML-based scoring     │
                  │  • Real RAG     │  • Auto-PR creation     │
                  │  • Auth/RBAC    │                         │
                  └─────────────────┴─────────────────────────┘
```

**Start with P0. Ship within 2 weeks. Then P1 for production readiness.**
