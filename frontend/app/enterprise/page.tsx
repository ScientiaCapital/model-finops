'use client'

import { useEffect, useState, useCallback } from 'react'
import { MetricsCard } from '@/components/MetricsCard'
import { DepartmentSpendChart } from '@/components/DepartmentSpendChart'
import { EmployeeUsageTable } from '@/components/EmployeeUsageTable'
import { ComplianceAlerts } from '@/components/ComplianceAlerts'
import { Button } from '@/components/ui/button'
import {
  getOrganization,
  getEmployees,
  getDepartmentSpend,
  getComplianceAlerts,
  Organization,
  EmployeeWithUsage,
  DepartmentSpendSummary,
  ComplianceAlert,
} from '@/lib/api'
import { Building2, Users, DollarSign, ShieldAlert, RefreshCw } from 'lucide-react'

const MOCK_ORG_ID = 'org_demo_001' // In production, this would come from auth

export default function EnterprisePage() {
  const [organization, setOrganization] = useState<Organization | null>(null)
  const [employees, setEmployees] = useState<EmployeeWithUsage[]>([])
  const [departments, setDepartments] = useState<DepartmentSpendSummary[]>([])
  const [alerts, setAlerts] = useState<ComplianceAlert[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const fetchData = useCallback(async () => {
    console.log('[Enterprise] Fetching data...')
    try {
      setLoading(true)
      setError(null)

      const [orgData, empData, deptData, alertData] = await Promise.all([
        getOrganization(MOCK_ORG_ID).catch(() => null),
        getEmployees(MOCK_ORG_ID).catch(() => []),
        getDepartmentSpend(MOCK_ORG_ID).catch(() => []),
        getComplianceAlerts(MOCK_ORG_ID, { resolved: false, limit: 50 }).catch(() => []),
      ])

      console.log('[Enterprise] Data fetched:', { orgData, empData, deptData, alertData })
      setOrganization(orgData)
      setEmployees(empData as EmployeeWithUsage[])
      setDepartments(deptData)
      setAlerts(alertData)
      setLastUpdated(new Date())
    } catch (err) {
      console.error('[Enterprise] Fetch error:', err)
      setError('Failed to fetch data. Is the API server running?')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const handleAlertResolved = useCallback((alertId: string) => {
    setAlerts((prev) =>
      prev.map((a) =>
        a.id === alertId
          ? { ...a, resolved: true, resolved_at: new Date().toISOString() }
          : a
      )
    )
  }, [])

  // Calculate metrics
  const totalEmployees = employees.length
  const totalMonthlySpend = departments.reduce((sum, d) => sum + d.total_spend_usd, 0)
  const criticalAlerts = alerts.filter((a) => !a.resolved && a.severity === 'critical').length
  const complianceScore = Math.max(
    0,
    100 - criticalAlerts * 10 - alerts.filter((a) => !a.resolved && a.severity === 'warning').length * 3
  )

  if (loading && !organization) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <RefreshCw className="h-8 w-8 animate-spin mx-auto text-primary" />
          <p className="mt-2 text-sm text-muted-foreground">Loading dashboard...</p>
        </div>
      </div>
    )
  }

  if (error && !organization) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <Building2 className="h-8 w-8 mx-auto text-destructive" />
          <p className="mt-2 text-sm text-destructive">{error}</p>
          <Button onClick={fetchData} className="mt-4" variant="outline">
            <RefreshCw className="mr-2 h-4 w-4" />
            Retry
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            {organization?.name || 'Enterprise Dashboard'}
          </h1>
          <p className="text-muted-foreground">
            Employee AI usage tracking and compliance monitoring
          </p>
        </div>
        <div className="flex items-center gap-4">
          {lastUpdated && (
            <span className="text-xs text-muted-foreground">
              Updated {lastUpdated.toLocaleTimeString()}
            </span>
          )}
          <Button onClick={fetchData} variant="outline" size="sm" disabled={loading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            {loading ? 'Refreshing...' : 'Refresh'}
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <MetricsCard
          title="Total Employees"
          value={totalEmployees.toString()}
          description="Active employees"
          icon={Users}
        />
        <MetricsCard
          title="Monthly Spend"
          value={`$${totalMonthlySpend.toFixed(2)}`}
          description="Total AI costs"
          icon={DollarSign}
        />
        <MetricsCard
          title="Compliance Score"
          value={`${complianceScore}%`}
          description={`${criticalAlerts} critical alerts`}
          icon={ShieldAlert}
          badge={
            complianceScore >= 90
              ? { text: 'Excellent', variant: 'success' }
              : complianceScore >= 70
              ? { text: 'Good', variant: 'warning' }
              : { text: 'Needs Attention', variant: 'destructive' }
          }
        />
        <MetricsCard
          title="Departments"
          value={departments.length.toString()}
          description="Active departments"
          icon={Building2}
        />
      </div>

      {/* Main Dashboard Layout */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Department Spend Chart - Left Column */}
        <div className="lg:col-span-1">
          <DepartmentSpendChart departments={departments} />
        </div>

        {/* Employee Usage Table - Center (Larger) */}
        <div className="lg:col-span-2">
          <EmployeeUsageTable
            employees={employees}
            onEmployeeClick={(employee) => {
              console.log('Employee clicked:', employee)
              // TODO: Open detail modal
            }}
          />
        </div>
      </div>

      {/* Compliance Alerts - Full Width */}
      <div>
        <ComplianceAlerts
          alerts={alerts}
          onAlertResolved={handleAlertResolved}
          loading={loading}
        />
      </div>

      {/* Organization Settings Summary */}
      {organization && (
        <div className="mt-6 p-4 bg-muted/50 rounded-lg">
          <h3 className="font-medium mb-2">Organization Settings</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-muted-foreground">Plan:</span>{' '}
              <span className="font-medium capitalize">{organization.plan}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Domain:</span>{' '}
              <span className="font-medium">{organization.domain || 'Not set'}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Created:</span>{' '}
              <span className="font-medium">
                {new Date(organization.created_at).toLocaleDateString()}
              </span>
            </div>
            <div>
              <span className="text-muted-foreground">Settings:</span>{' '}
              <span className="font-medium">
                {Object.keys(organization.settings || {}).length} configured
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
