-- CodeGuardian Database Schema
-- PostgreSQL 16+
-- FAANG-grade schema: audit logging, multi-tenant, high-performance

-- ============================================================
-- EXTENSIONS
-- ============================================================
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- TENANTS (Multi-tenant isolation)
-- ============================================================
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    plan VARCHAR(50) NOT NULL DEFAULT 'free',  -- 'free', 'pro', 'enterprise'
    settings JSONB DEFAULT '{}',
    sso_enabled BOOLEAN DEFAULT FALSE,
    sso_provider VARCHAR(50),
    audit_log_enabled BOOLEAN DEFAULT FALSE,
    stripe_customer_id VARCHAR(100),
    stripe_subscription_id VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    max_reviews_per_day INTEGER DEFAULT 10,
    max_concurrent_reviews INTEGER DEFAULT 1,
    max_files_per_review INTEGER DEFAULT 1000,
    max_monthly_cost_cents INTEGER DEFAULT 5000,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_tenants_slug ON tenants(slug) WHERE deleted_at IS NULL;

-- ============================================================
-- USERS
-- ============================================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255),
    roles TEXT[] DEFAULT '{developer}',  -- 'admin', 'developer', 'viewer'
    sso_subject VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_users_tenant ON users(tenant_id);
CREATE INDEX idx_users_email ON users(email) WHERE deleted_at IS NULL;

-- ============================================================
-- API KEYS
-- ============================================================
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    user_id UUID NOT NULL REFERENCES users(id),
    key_hash VARCHAR(128) NOT NULL,
    name VARCHAR(255) NOT NULL,
    permissions TEXT[] DEFAULT '{review:read}',
    revoked BOOLEAN DEFAULT FALSE,
    last_used_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_tenant ON api_keys(tenant_id);

-- ============================================================
-- PROJECTS
-- ============================================================
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    owner_id UUID NOT NULL REFERENCES users(id),
    name VARCHAR(255) NOT NULL,
    repository_url TEXT NOT NULL,
    provider VARCHAR(50) NOT NULL DEFAULT 'github',  -- 'github', 'gitlab', 'bitbucket', 'local'
    default_branch VARCHAR(255) DEFAULT 'main',
    settings JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    last_reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_projects_tenant ON projects(tenant_id);
CREATE INDEX idx_projects_owner ON projects(owner_id);

-- ============================================================
-- REVIEWS
-- ============================================================
CREATE TABLE reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    trigger VARCHAR(50) NOT NULL DEFAULT 'manual',  -- 'manual', 'push', 'pull_request', 'schedule', 'webhook'
    commit_sha VARCHAR(40),
    branch VARCHAR(255),
    pull_request_id INTEGER,
    author_id UUID REFERENCES users(id),
    status VARCHAR(50) NOT NULL DEFAULT 'pending',  -- 'pending', 'running', 'completed', 'failed', 'cancelled'
    quality_score DECIMAL(5,1),
    total_findings INTEGER DEFAULT 0,
    critical_count INTEGER DEFAULT 0,
    high_count INTEGER DEFAULT 0,
    medium_count INTEGER DEFAULT 0,
    low_count INTEGER DEFAULT 0,
    info_count INTEGER DEFAULT 0,
    duration_ms INTEGER,
    llm_tokens_used INTEGER DEFAULT 0,
    llm_cost_cents DECIMAL(10,4) DEFAULT 0,
    files_scanned INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_reviews_project ON reviews(project_id);
CREATE INDEX idx_reviews_tenant ON reviews(tenant_id);
CREATE INDEX idx_reviews_status ON reviews(status);
CREATE INDEX idx_reviews_created ON reviews(created_at DESC);

-- ============================================================
-- FINDINGS
-- ============================================================
CREATE TABLE findings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    review_id UUID NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    file_path TEXT NOT NULL,
    line_start INTEGER,
    line_end INTEGER,
    column_start INTEGER,
    column_end INTEGER,
    severity VARCHAR(20) NOT NULL,  -- 'critical', 'high', 'medium', 'low', 'info'
    category VARCHAR(50) NOT NULL,  -- 'security', 'performance', 'logic', 'pattern', 'testing', 'policy'
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    recommendation TEXT,
    code_snippet TEXT,
    cwe_id VARCHAR(20),
    cvss_score DECIMAL(3,1),
    effort_minutes INTEGER,
    auto_fixable BOOLEAN DEFAULT FALSE,
    fix_generated BOOLEAN DEFAULT FALSE,
    fix_diff TEXT,
    fix_status VARCHAR(50),  -- 'pending', 'applied', 'rejected', 'failed'
    dismissed BOOLEAN DEFAULT FALSE,
    dismissed_by UUID REFERENCES users(id),
    dismissed_reason TEXT,
    dismissed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_findings_review ON findings(review_id);
CREATE INDEX idx_findings_tenant ON findings(tenant_id);
CREATE INDEX idx_findings_severity ON findings(severity);
CREATE INDEX idx_findings_category ON findings(category);
CREATE INDEX idx_findings_file ON findings(file_path);

-- ============================================================
-- DAILY USAGE (for billing)
-- ============================================================
CREATE TABLE daily_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    date DATE NOT NULL,
    reviews_count INTEGER DEFAULT 0,
    files_scanned INTEGER DEFAULT 0,
    llm_tokens_used INTEGER DEFAULT 0,
    llm_cost_cents DECIMAL(10,4) DEFAULT 0,
    storage_bytes BIGINT DEFAULT 0,
    UNIQUE(tenant_id, date)
);

CREATE INDEX idx_daily_usage_tenant ON daily_usage(tenant_id, date);

-- ============================================================
-- AUDIT LOG (immutable, tamper-evident)
-- ============================================================
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    user_id UUID REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id UUID,
    details JSONB,
    ip_address INET,
    user_agent TEXT,
    previous_hash VARCHAR(64),  -- SHA-256 of previous entry for tamper evidence
    hash VARCHAR(64) NOT NULL,  -- SHA-256 of this entry
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_tenant ON audit_log(tenant_id, created_at DESC);

-- ============================================================
-- MATERIALIZED VIEWS (for dashboards)
-- ============================================================
CREATE MATERIALIZED VIEW mv_review_trends AS
SELECT
    tenant_id,
    project_id,
    DATE_TRUNC('day', created_at) AS day,
    COUNT(*) AS review_count,
    SUM(critical_count) AS total_critical,
    SUM(high_count) AS total_high,
    SUM(medium_count) AS total_medium,
    AVG(duration_ms)::INTEGER AS avg_duration_ms,
    SUM(llm_cost_cents) AS total_cost_cents,
    AVG(quality_score)::DECIMAL(5,1) AS avg_quality_score
FROM reviews
WHERE status = 'completed'
GROUP BY tenant_id, project_id, DATE_TRUNC('day', created_at);

CREATE INDEX idx_mv_trends_tenant ON mv_review_trends(tenant_id, day DESC);

-- Refresh function
CREATE OR REPLACE FUNCTION refresh_review_trends()
RETURNS TRIGGER AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_review_trends;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- TRIGGERS
-- ============================================================
CREATE TRIGGER trg_reviews_refresh_trends
AFTER INSERT OR UPDATE ON reviews
FOR EACH STATEMENT EXECUTE FUNCTION refresh_review_trends();

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_projects_updated_at
BEFORE UPDATE ON projects
FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_tenants_updated_at
BEFORE UPDATE ON tenants
FOR EACH ROW EXECUTE FUNCTION update_updated_at();
