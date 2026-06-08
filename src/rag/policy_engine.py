"""Real RAG engine for policy-based code review — uses vector store for retrieval."""

from __future__ import annotations

import os
import uuid

from pydantic import BaseModel

from src.agents.base import AnalysisAgent
from src.agents.state import CodeReviewState, Finding
from src.di.container import AppContext


class PolicyFinding(BaseModel):
    """Finding from policy verification."""
    file: str = ""
    line: int = 0
    severity: str = "medium"
    title: str = ""
    description: str = ""
    recommendation: str = ""
    policy_reference: str = ""


class PolicyFindingList(BaseModel):
    """List of policy findings."""
    findings: list[PolicyFinding]


POLICY_VERIFICATION_PROMPT = """You are verifying code against a set of company engineering policies.

Given the code and the relevant policies, determine if the code violates any policies.

## Policies to check:
{policy_context}

## Code:
File: {file_path}

```python
{content}
```

For each violation found, specify:
1. Which policy is violated
2. The exact line(s) where the violation occurs
3. How to fix it to comply with the policy
"""


class PolicyRAGEngine:
    """RAG engine that indexes policy documents and retrieves relevant context for code review."""

    def __init__(
        self,
        standards_dir: str = "./standards",
        persist_dir: str = "./.rag_cache",
    ):
        self.standards_dir = standards_dir
        self.persist_dir = persist_dir
        self._initialized = False
        self.vector_store = None

    def _lazy_imports(self):
        """Lazy-load heavy langchain dependencies only when needed."""
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        from langchain_community.vectorstores import Chroma
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        from langchain_community.document_loaders import DirectoryLoader, TextLoader
        from langchain_core.documents import Document
        return RecursiveCharacterTextSplitter, Chroma, GoogleGenerativeAIEmbeddings, DirectoryLoader, TextLoader, Document

    def ensure_initialized(self):
        """Lazily initialize the vector store."""
        if self._initialized:
            return

        RecursiveCharacterTextSplitter, Chroma, GoogleGenerativeAIEmbeddings, DirectoryLoader, TextLoader, Document = self._lazy_imports()
        self.embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")

        if os.path.exists(self.persist_dir) and os.listdir(self.persist_dir):
            try:
                self.vector_store = Chroma(
                    embedding_function=self.embeddings,
                    persist_directory=self.persist_dir,
                )
                self._initialized = True
                return
            except Exception:
                pass

        # Index documents
        if os.path.exists(self.standards_dir):
            self._index_documents()

        if not self.vector_store:
            # Create empty vector store
            self.vector_store = Chroma(
                embedding_function=self.embeddings,
                persist_directory=self.persist_dir,
            )

        self._initialized = True

    def _index_documents(self):
        """Load, split, and index policy documents from standards directory."""
        RecursiveCharacterTextSplitter, Chroma, GoogleGenerativeAIEmbeddings, DirectoryLoader, TextLoader, Document = self._lazy_imports()

        loader = DirectoryLoader(
            self.standards_dir,
            glob="**/*.{txt,md,pdf}",
            loader_cls=TextLoader,
            loader_kwargs={"encoding": "utf-8"},
            recursive=True,
        )

        documents = loader.load()
        if not documents:
            return

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        chunks = text_splitter.split_documents(documents)

        self.vector_store = Chroma.from_documents(
            documents=chunks,
            embedding=self.embeddings,
            persist_directory=self.persist_dir,
        )

    def query(self, query: str, k: int = 3) -> list:
        """Retrieve relevant policy sections for a given code context."""
        self.ensure_initialized()
        try:
            return self.vector_store.similarity_search(query, k=k)
        except Exception:
            return []

    def query_as_context(self, query: str) -> str:
        """Get relevant policy context as a formatted string."""
        docs = self.query(query)
        if not docs:
            return "No relevant policies found."

        return "\n\n".join([
            f"--- Policy: {doc.metadata.get('source', 'Unknown')} ---\n{doc.page_content}"
            for doc in docs
        ])


class PolicyVerificationAgent(AnalysisAgent):
    """Verifies code against company policies using RAG."""

    def __init__(self, ctx: AppContext, rag_engine: PolicyRAGEngine | None = None):
        super().__init__(ctx)
        self.rag = rag_engine or PolicyRAGEngine()

    def category(self) -> str:
        return "policy_verification"

    async def analyze(self, state: CodeReviewState) -> CodeReviewState:
        from langchain_core.prompts.chat import ChatPromptTemplate

        files = state.get("target_files", [])
        findings: list[Finding] = []

        for file_path in files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue

            # Retrieve relevant policies
            policy_context = self.rag.query_as_context(f"Coding standards for {file_path}")

            if policy_context == "No relevant policies found.":
                continue

            # Verify code against policies using LLM
            prompt = ChatPromptTemplate.from_messages([
                ("system", POLICY_VERIFICATION_PROMPT),
            ])

            try:
                chain = prompt | self.llm.with_structured_output(PolicyFindingList)
                result: PolicyFindingList = await chain.ainvoke({
                    "policy_context": policy_context,
                    "file_path": file_path,
                    "content": content,
                })

                for pf in result.findings:
                    findings.append(Finding(
                        id=str(uuid.uuid4()),
                        file=pf.file or file_path,
                        line=pf.line,
                        severity=pf.severity,
                        category="policy",
                        title=pf.title,
                        description=pf.description,
                        recommendation=pf.recommendation,
                        auto_fixable=False,
                    ))

            except Exception:
                continue

        state["policy_findings"] = findings
        state["current_step"] = "policy_verification_complete"
        return state
