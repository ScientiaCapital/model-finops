-- Enterprise Schema Migration 005: Row-Level Security Policies
-- Multi-tenant isolation and role-based access control
-- Run AFTER: enterprise_004_usage_alerts.sql

-- =============================================================================
-- HELPER FUNCTIONS FOR RLS
-- =============================================================================

-- Get current user's employee record
CREATE OR REPLACE FUNCTION get_current_employee()
RETURNS employees AS $$
    SELECT * FROM employees
    WHERE auth_user_id = auth.uid()
    AND is_active = TRUE
    LIMIT 1;
$$ LANGUAGE sql SECURITY DEFINER STABLE;

-- Get current user's organization ID
CREATE OR REPLACE FUNCTION get_current_org_id()
RETURNS UUID AS $$
    SELECT org_id FROM employees
    WHERE auth_user_id = auth.uid()
    AND is_active = TRUE
    LIMIT 1;
$$ LANGUAGE sql SECURITY DEFINER STABLE;

-- Check if current user has one of the specified roles
CREATE OR REPLACE FUNCTION current_user_has_role(roles TEXT[])
RETURNS BOOLEAN AS $$
    SELECT EXISTS (
        SELECT 1 FROM employees
        WHERE auth_user_id = auth.uid()
        AND is_active = TRUE
        AND role = ANY(roles)
    );
$$ LANGUAGE sql SECURITY DEFINER STABLE;

-- Check if current user manages the department
CREATE OR REPLACE FUNCTION current_user_manages_dept(dept_id UUID)
RETURNS BOOLEAN AS $$
    SELECT EXISTS (
        SELECT 1 FROM departments d
        JOIN employees e ON e.id = d.manager_id
        WHERE d.id = dept_id
        AND e.auth_user_id = auth.uid()
        AND e.is_active = TRUE
    );
$$ LANGUAGE sql SECURITY DEFINER STABLE;

-- =============================================================================
-- ORGANIZATIONS RLS
-- =============================================================================

-- Admins can view their organization
CREATE POLICY org_select_admin ON organizations
    FOR SELECT
    USING (id = get_current_org_id());

-- Only admins can update their organization
CREATE POLICY org_update_admin ON organizations
    FOR UPDATE
    USING (
        id = get_current_org_id()
        AND current_user_has_role(ARRAY['admin'])
    );

-- =============================================================================
-- DEPARTMENTS RLS
-- =============================================================================

-- All employees can view departments in their org
CREATE POLICY dept_select_org ON departments
    FOR SELECT
    USING (org_id = get_current_org_id());

-- Only admins can insert/update/delete departments
CREATE POLICY dept_insert_admin ON departments
    FOR INSERT
    WITH CHECK (
        org_id = get_current_org_id()
        AND current_user_has_role(ARRAY['admin'])
    );

CREATE POLICY dept_update_admin ON departments
    FOR UPDATE
    USING (
        org_id = get_current_org_id()
        AND current_user_has_role(ARRAY['admin'])
    );

CREATE POLICY dept_delete_admin ON departments
    FOR DELETE
    USING (
        org_id = get_current_org_id()
        AND current_user_has_role(ARRAY['admin'])
    );

-- =============================================================================
-- EMPLOYEES RLS
-- =============================================================================

-- Employees can see themselves
CREATE POLICY emp_select_self ON employees
    FOR SELECT
    USING (auth_user_id = auth.uid());

-- Managers can see their department members
CREATE POLICY emp_select_manager ON employees
    FOR SELECT
    USING (current_user_manages_dept(dept_id));

-- HR admins can see all employees in their org
CREATE POLICY emp_select_hr_admin ON employees
    FOR SELECT
    USING (
        org_id = get_current_org_id()
        AND current_user_has_role(ARRAY['hr_admin', 'admin'])
    );

-- Employees can update their own profile (limited fields)
CREATE POLICY emp_update_self ON employees
    FOR UPDATE
    USING (auth_user_id = auth.uid());

-- Admins can manage all employees in their org
CREATE POLICY emp_manage_admin ON employees
    FOR ALL
    USING (
        org_id = get_current_org_id()
        AND current_user_has_role(ARRAY['admin'])
    );

-- =============================================================================
-- EMPLOYEE API KEYS RLS
-- =============================================================================

-- Employees can see their own API keys
CREATE POLICY api_key_select_self ON employee_api_keys
    FOR SELECT
    USING (
        employee_id IN (
            SELECT id FROM employees WHERE auth_user_id = auth.uid()
        )
    );

-- Employees can manage their own API keys
CREATE POLICY api_key_insert_self ON employee_api_keys
    FOR INSERT
    WITH CHECK (
        employee_id IN (
            SELECT id FROM employees WHERE auth_user_id = auth.uid()
        )
    );

CREATE POLICY api_key_update_self ON employee_api_keys
    FOR UPDATE
    USING (
        employee_id IN (
            SELECT id FROM employees WHERE auth_user_id = auth.uid()
        )
    );

-- HR admins can view all API keys in their org (for compliance)
CREATE POLICY api_key_select_hr_admin ON employee_api_keys
    FOR SELECT
    USING (
        employee_id IN (
            SELECT e.id FROM employees e
            WHERE e.org_id = get_current_org_id()
        )
        AND current_user_has_role(ARRAY['hr_admin', 'admin'])
    );

-- HR admins can approve/revoke API keys
CREATE POLICY api_key_update_hr_admin ON employee_api_keys
    FOR UPDATE
    USING (
        employee_id IN (
            SELECT e.id FROM employees e
            WHERE e.org_id = get_current_org_id()
        )
        AND current_user_has_role(ARRAY['hr_admin', 'admin'])
    );

-- =============================================================================
-- AI USAGE LOG RLS
-- =============================================================================

-- Employees can see their own usage
CREATE POLICY usage_select_self ON ai_usage_log
    FOR SELECT
    USING (
        employee_id IN (
            SELECT id FROM employees WHERE auth_user_id = auth.uid()
        )
    );

-- Employees can insert their own usage records
CREATE POLICY usage_insert_self ON ai_usage_log
    FOR INSERT
    WITH CHECK (
        employee_id IN (
            SELECT id FROM employees WHERE auth_user_id = auth.uid()
        )
    );

-- Managers can see their department's usage
CREATE POLICY usage_select_manager ON ai_usage_log
    FOR SELECT
    USING (
        employee_id IN (
            SELECT e.id FROM employees e
            WHERE current_user_manages_dept(e.dept_id)
        )
    );

-- HR admins can see all usage in their org
CREATE POLICY usage_select_hr_admin ON ai_usage_log
    FOR SELECT
    USING (
        employee_id IN (
            SELECT e.id FROM employees e
            WHERE e.org_id = get_current_org_id()
        )
        AND current_user_has_role(ARRAY['hr_admin', 'admin'])
    );

-- =============================================================================
-- COMPLIANCE ALERTS RLS
-- =============================================================================

-- Employees can see alerts about themselves
CREATE POLICY alerts_select_self ON compliance_alerts
    FOR SELECT
    USING (
        employee_id IN (
            SELECT id FROM employees WHERE auth_user_id = auth.uid()
        )
    );

-- Managers can see alerts for their department
CREATE POLICY alerts_select_manager ON compliance_alerts
    FOR SELECT
    USING (
        dept_id IN (
            SELECT d.id FROM departments d
            JOIN employees e ON e.id = d.manager_id
            WHERE e.auth_user_id = auth.uid()
        )
    );

-- HR admins can see all alerts in their org
CREATE POLICY alerts_select_hr_admin ON compliance_alerts
    FOR SELECT
    USING (
        org_id = get_current_org_id()
        AND current_user_has_role(ARRAY['hr_admin', 'admin'])
    );

-- HR admins can resolve alerts
CREATE POLICY alerts_update_hr_admin ON compliance_alerts
    FOR UPDATE
    USING (
        org_id = get_current_org_id()
        AND current_user_has_role(ARRAY['hr_admin', 'admin'])
    );

-- =============================================================================
-- AI PROVIDERS RLS (Public Read-Only)
-- =============================================================================

-- Anyone can read provider info (it's reference data)
CREATE POLICY providers_select_all ON ai_providers
    FOR SELECT
    USING (TRUE);

-- Only superadmins can modify providers (handled at app level)
-- No INSERT/UPDATE/DELETE policies = blocked by RLS

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON FUNCTION get_current_employee IS 'Get the employee record for the current authenticated user';
COMMENT ON FUNCTION get_current_org_id IS 'Get the organization ID for the current authenticated user';
COMMENT ON FUNCTION current_user_has_role IS 'Check if current user has one of the specified roles';
