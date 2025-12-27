-- Enterprise Schema Migration 002: Departments & Employees
-- Organizational structure with work/personal account linking
-- Run AFTER: enterprise_001_organizations.sql

-- =============================================================================
-- DEPARTMENTS TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS departments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,                          -- "Engineering", "Sales", "Marketing"
    budget_usd DECIMAL(10,2),                    -- Monthly AI budget
    manager_id UUID,                             -- References employees (added via ALTER)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(org_id, name)
);

-- Index for org lookup
CREATE INDEX IF NOT EXISTS idx_departments_org_id ON departments(org_id);

-- Enable RLS
ALTER TABLE departments ENABLE ROW LEVEL SECURITY;

-- =============================================================================
-- EMPLOYEES TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS employees (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    dept_id UUID REFERENCES departments(id) ON DELETE SET NULL,

    -- Supabase Auth integration
    auth_user_id UUID UNIQUE,                    -- Links to auth.users(id)

    -- Identity
    email TEXT NOT NULL,                         -- Work email: tim@coperniq.io
    name TEXT,
    role TEXT DEFAULT 'employee',                -- employee, manager, admin, hr_admin

    -- Personal account linking (optional, GDPR consent required)
    personal_email TEXT,                         -- Personal: tkipper@gmail.com
    personal_linked_at TIMESTAMPTZ,
    personal_consent BOOLEAN DEFAULT FALSE,      -- GDPR consent for personal tracking
    personal_consent_date TIMESTAMPTZ,

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(org_id, email)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_employees_org_id ON employees(org_id);
CREATE INDEX IF NOT EXISTS idx_employees_dept_id ON employees(dept_id);
CREATE INDEX IF NOT EXISTS idx_employees_auth_user_id ON employees(auth_user_id);
CREATE INDEX IF NOT EXISTS idx_employees_email ON employees(email);
CREATE INDEX IF NOT EXISTS idx_employees_personal_email ON employees(personal_email) WHERE personal_email IS NOT NULL;

-- Enable RLS
ALTER TABLE employees ENABLE ROW LEVEL SECURITY;

-- Now add the FK from departments.manager_id to employees.id
ALTER TABLE departments
    ADD CONSTRAINT fk_departments_manager
    FOREIGN KEY (manager_id) REFERENCES employees(id) ON DELETE SET NULL;

-- Triggers
CREATE TRIGGER update_departments_updated_at
    BEFORE UPDATE ON departments
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_employees_updated_at
    BEFORE UPDATE ON employees
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- HELPER FUNCTIONS
-- =============================================================================

-- Get employee's organization ID from auth user
CREATE OR REPLACE FUNCTION get_employee_org_id(user_id UUID)
RETURNS UUID AS $$
    SELECT org_id FROM employees WHERE auth_user_id = user_id LIMIT 1;
$$ LANGUAGE sql SECURITY DEFINER;

-- Check if user has specific role
CREATE OR REPLACE FUNCTION user_has_role(user_id UUID, required_role TEXT)
RETURNS BOOLEAN AS $$
    SELECT EXISTS (
        SELECT 1 FROM employees
        WHERE auth_user_id = user_id
        AND role = required_role
        AND is_active = TRUE
    );
$$ LANGUAGE sql SECURITY DEFINER;

-- Check if user is manager of department
CREATE OR REPLACE FUNCTION user_is_dept_manager(user_id UUID, department_id UUID)
RETURNS BOOLEAN AS $$
    SELECT EXISTS (
        SELECT 1 FROM departments d
        JOIN employees e ON e.id = d.manager_id
        WHERE d.id = department_id
        AND e.auth_user_id = user_id
        AND e.is_active = TRUE
    );
$$ LANGUAGE sql SECURITY DEFINER;

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE departments IS 'Organizational departments with budgets';
COMMENT ON TABLE employees IS 'Users with work and optional personal account linking';
COMMENT ON COLUMN employees.personal_consent IS 'GDPR consent for tracking personal AI usage';
COMMENT ON COLUMN employees.role IS 'Role: employee, manager, admin, hr_admin';
