'use client'

import { useEffect, useState, useCallback } from 'react'
import { EmployeeUsageTable } from '@/components/EmployeeUsageTable'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  getEmployees,
  linkPersonalAccount,
  EmployeeWithUsage,
  LinkPersonalAccountRequest,
} from '@/lib/api'
import { Users, UserPlus, Upload, RefreshCw, X } from 'lucide-react'

const MOCK_ORG_ID = 'org_demo_001'

export default function EmployeesPage() {
  const [employees, setEmployees] = useState<EmployeeWithUsage[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedEmployee, setSelectedEmployee] = useState<EmployeeWithUsage | null>(null)
  const [showLinkModal, setShowLinkModal] = useState(false)
  const [personalEmail, setPersonalEmail] = useState('')
  const [consent, setConsent] = useState(false)
  const [linking, setLinking] = useState(false)

  const fetchData = useCallback(async () => {
    console.log('[Employees] Fetching data...')
    try {
      setLoading(true)
      setError(null)

      const empData = await getEmployees(MOCK_ORG_ID)
      console.log('[Employees] Data fetched:', empData)
      setEmployees(empData as EmployeeWithUsage[])
    } catch (err) {
      console.error('[Employees] Fetch error:', err)
      setError('Failed to fetch employees. Is the API server running?')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const handleEmployeeClick = (employee: EmployeeWithUsage) => {
    setSelectedEmployee(employee)
  }

  const handleLinkPersonalAccount = async () => {
    if (!selectedEmployee || !consent) return

    try {
      setLinking(true)
      const data: LinkPersonalAccountRequest = {
        personal_email: personalEmail,
        consent_given: consent,
      }
      await linkPersonalAccount(selectedEmployee.id, data)

      // Refresh employee data
      await fetchData()

      // Close modal
      setShowLinkModal(false)
      setPersonalEmail('')
      setConsent(false)
      setSelectedEmployee(null)
    } catch (err) {
      console.error('[Employees] Link failed:', err)
      alert('Failed to link personal account. Please check GDPR consent.')
    } finally {
      setLinking(false)
    }
  }

  const totalEmployees = employees.length
  const employeesWithPersonal = employees.filter(e => e.personal_linked_at).length
  const totalSpend = employees.reduce((sum, e) => sum + (e.usage?.total_spend_usd || 0), 0)

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Employee Management</h1>
          <p className="text-muted-foreground">
            Manage employee API keys and personal account linking
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={fetchData} disabled={loading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button size="sm" variant="outline">
            <Upload className="mr-2 h-4 w-4" />
            Import CSV
          </Button>
          <Button size="sm">
            <UserPlus className="mr-2 h-4 w-4" />
            Add Employee
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Employees
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalEmployees}</div>
            <p className="text-xs text-muted-foreground mt-1">Active employees</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Personal Accounts Linked
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{employeesWithPersonal}</div>
            <p className="text-xs text-muted-foreground mt-1">
              {totalEmployees > 0
                ? `${((employeesWithPersonal / totalEmployees) * 100).toFixed(0)}% of employees`
                : 'No employees'}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Monthly Spend
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">${totalSpend.toFixed(2)}</div>
            <p className="text-xs text-muted-foreground mt-1">All employees combined</p>
          </CardContent>
        </Card>
      </div>

      {/* Employee Table */}
      {error ? (
        <div className="text-center text-destructive py-8">
          <p>{error}</p>
          <Button onClick={fetchData} className="mt-4" variant="outline">
            Retry
          </Button>
        </div>
      ) : (
        <EmployeeUsageTable employees={employees} onEmployeeClick={handleEmployeeClick} />
      )}

      {/* Employee Detail Drawer (Simple Modal) */}
      {selectedEmployee && !showLinkModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="w-full max-w-2xl max-h-[80vh] overflow-y-auto m-4">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Employee Details</CardTitle>
                <Button variant="ghost" size="sm" onClick={() => setSelectedEmployee(null)}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-muted-foreground">Name</p>
                  <p className="font-medium">{selectedEmployee.name || 'Not set'}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Email</p>
                  <p className="font-medium">{selectedEmployee.email}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Role</p>
                  <Badge variant="outline" className="capitalize">
                    {selectedEmployee.role.replace('_', ' ')}
                  </Badge>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Department</p>
                  <p className="font-medium">{selectedEmployee.department_name || 'Unassigned'}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Work Spend</p>
                  <p className="font-medium">
                    ${selectedEmployee.usage?.work_spend_usd.toFixed(2) || '0.00'}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Personal Spend</p>
                  <p className="font-medium">
                    ${selectedEmployee.usage?.personal_spend_usd.toFixed(2) || '0.00'}
                  </p>
                </div>
              </div>

              {/* Personal Account Section */}
              <div className="pt-4 border-t">
                <h3 className="font-medium mb-3">Personal Account</h3>
                {selectedEmployee.personal_linked_at ? (
                  <div className="bg-green-50 border border-green-200 rounded-md p-4">
                    <Badge
                      variant="outline"
                      className="bg-green-50 text-green-700 border-green-200 mb-2"
                    >
                      Linked
                    </Badge>
                    <p className="text-sm">
                      <span className="font-medium">Email:</span> {selectedEmployee.personal_email}
                    </p>
                    <p className="text-sm text-muted-foreground mt-1">
                      Linked on {new Date(selectedEmployee.personal_linked_at).toLocaleDateString()}
                    </p>
                  </div>
                ) : (
                  <div className="bg-gray-50 border border-gray-200 rounded-md p-4">
                    <p className="text-sm text-muted-foreground mb-3">No personal account linked</p>
                    <Button size="sm" onClick={() => setShowLinkModal(true)}>
                      Link Personal Account
                    </Button>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Personal Account Linking Modal */}
      {showLinkModal && selectedEmployee && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="w-full max-w-md m-4">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Link Personal Account</CardTitle>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setShowLinkModal(false)
                    setPersonalEmail('')
                    setConsent(false)
                  }}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-sm font-medium mb-2 block">Personal Email</label>
                <input
                  type="email"
                  value={personalEmail}
                  onChange={e => setPersonalEmail(e.target.value)}
                  className="w-full border rounded-md px-3 py-2"
                  placeholder="employee@gmail.com"
                />
              </div>

              <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
                <p className="text-sm font-medium mb-2">GDPR Consent Required</p>
                <label className="flex items-start gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={consent}
                    onChange={e => setConsent(e.target.checked)}
                    className="mt-1"
                  />
                  <span>
                    I consent to tracking personal AI usage for expense reporting. This data will be
                    visible to HR and department managers.
                  </span>
                </label>
              </div>

              <div className="flex gap-2">
                <Button
                  onClick={handleLinkPersonalAccount}
                  disabled={!personalEmail || !consent || linking}
                  className="flex-1"
                >
                  {linking ? 'Linking...' : 'Link Account'}
                </Button>
                <Button
                  variant="outline"
                  onClick={() => {
                    setShowLinkModal(false)
                    setPersonalEmail('')
                    setConsent(false)
                  }}
                >
                  Cancel
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
