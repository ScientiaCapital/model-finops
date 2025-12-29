'use client'

import { useState, useMemo } from 'react'
import { EmployeeWithUsage } from '@/lib/api'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { User, ChevronUp, ChevronDown, Filter } from 'lucide-react'

interface EmployeeUsageTableProps {
  employees: EmployeeWithUsage[]
  onEmployeeClick?: (employee: EmployeeWithUsage) => void
  flaggedProviders?: string[]
}

type SortColumn = 'name' | 'department' | 'usage' | 'role'
type SortDirection = 'asc' | 'desc'

export function EmployeeUsageTable({
  employees,
  onEmployeeClick,
  flaggedProviders: _flaggedProviders = ['deepseek', 'qwen', 'baidu'],
}: EmployeeUsageTableProps) {
  const [sortColumn, setSortColumn] = useState<SortColumn>('usage')
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc')
  const [departmentFilter, setDepartmentFilter] = useState<string>('all')

  const departments = useMemo(() => {
    const depts = new Set(
      employees
        .map((e) => e.department_name)
        .filter((d): d is string => Boolean(d))
    )
    return ['all', ...Array.from(depts).sort()]
  }, [employees])

  const handleSort = (column: SortColumn) => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
    } else {
      setSortColumn(column)
      setSortDirection('desc')
    }
  }

  const sortedAndFilteredEmployees = useMemo(() => {
    let filtered = employees

    if (departmentFilter !== 'all') {
      filtered = filtered.filter(
        (e) => e.department_name === departmentFilter
      )
    }

    const sorted = [...filtered].sort((a, b) => {
      let aVal: string | number = ''
      let bVal: string | number = ''

      switch (sortColumn) {
        case 'name':
          aVal = a.name || a.email
          bVal = b.name || b.email
          break
        case 'department':
          aVal = a.department_name || ''
          bVal = b.department_name || ''
          break
        case 'usage':
          aVal = a.usage?.total_spend_usd || 0
          bVal = b.usage?.total_spend_usd || 0
          break
        case 'role':
          aVal = a.role
          bVal = b.role
          break
      }

      if (typeof aVal === 'number' && typeof bVal === 'number') {
        return sortDirection === 'asc' ? aVal - bVal : bVal - aVal
      }

      const strA = String(aVal).toLowerCase()
      const strB = String(bVal).toLowerCase()
      if (sortDirection === 'asc') {
        return strA.localeCompare(strB)
      }
      return strB.localeCompare(strA)
    })

    return sorted
  }, [employees, sortColumn, sortDirection, departmentFilter])

  const SortIcon = ({ column }: { column: SortColumn }) => {
    if (sortColumn !== column) return null
    return sortDirection === 'asc' ? (
      <ChevronUp className="inline h-4 w-4 ml-1" />
    ) : (
      <ChevronDown className="inline h-4 w-4 ml-1" />
    )
  }

  const getPersonalAccountBadge = (employee: EmployeeWithUsage) => {
    if (employee.personal_linked_at) {
      return (
        <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
          Personal Linked
        </Badge>
      )
    }
    return (
      <Badge variant="outline" className="bg-gray-50 text-gray-600">
        Work Only
      </Badge>
    )
  }

  const getRoleBadge = (role: string) => {
    const roleColors: Record<string, string> = {
      admin: 'bg-purple-50 text-purple-700 border-purple-200',
      hr_admin: 'bg-blue-50 text-blue-700 border-blue-200',
      manager: 'bg-indigo-50 text-indigo-700 border-indigo-200',
      employee: 'bg-gray-50 text-gray-600 border-gray-200',
    }

    return (
      <Badge variant="outline" className={roleColors[role] || roleColors.employee}>
        {role.replace('_', ' ')}
      </Badge>
    )
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <User className="h-5 w-5" />
            Employee Usage ({sortedAndFilteredEmployees.length})
          </CardTitle>
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-muted-foreground" />
            <select
              value={departmentFilter}
              onChange={(e) => setDepartmentFilter(e.target.value)}
              className="border rounded-md px-3 py-1 text-sm"
            >
              {departments.map((dept) => (
                <option key={dept} value={dept}>
                  {dept === 'all' ? 'All Departments' : dept}
                </option>
              ))}
            </select>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleSort('name')}
                  className="font-medium"
                >
                  Name
                  <SortIcon column="name" />
                </Button>
              </TableHead>
              <TableHead>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleSort('department')}
                  className="font-medium"
                >
                  Department
                  <SortIcon column="department" />
                </Button>
              </TableHead>
              <TableHead>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleSort('role')}
                  className="font-medium"
                >
                  Role
                  <SortIcon column="role" />
                </Button>
              </TableHead>
              <TableHead>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleSort('usage')}
                  className="font-medium"
                >
                  Monthly Usage
                  <SortIcon column="usage" />
                </Button>
              </TableHead>
              <TableHead>Work/Personal</TableHead>
              <TableHead>Account Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sortedAndFilteredEmployees.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                  No employees found
                </TableCell>
              </TableRow>
            ) : (
              sortedAndFilteredEmployees.map((employee) => {
                const usage = employee.usage
                const _hasPersonalAccount = Boolean(employee.personal_linked_at)

                return (
                  <TableRow
                    key={employee.id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => onEmployeeClick?.(employee)}
                  >
                    <TableCell>
                      <div>
                        <div className="font-medium">
                          {employee.name || 'No Name'}
                        </div>
                        <div className="text-sm text-muted-foreground">
                          {employee.email}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      {employee.department_name || (
                        <span className="text-muted-foreground">Unassigned</span>
                      )}
                    </TableCell>
                    <TableCell>{getRoleBadge(employee.role)}</TableCell>
                    <TableCell>
                      <div>
                        <div className="font-medium">
                          ${usage?.total_spend_usd.toFixed(2) || '0.00'}
                        </div>
                        {usage && (usage.work_spend_usd > 0 || usage.personal_spend_usd > 0) && (
                          <div className="text-xs text-muted-foreground">
                            Work: ${usage.work_spend_usd.toFixed(2)} | Personal:{' '}
                            ${usage.personal_spend_usd.toFixed(2)}
                          </div>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      {usage && usage.personal_spend_usd > 0 ? (
                        <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200">
                          ${usage.personal_spend_usd.toFixed(2)} Personal
                        </Badge>
                      ) : (
                        <span className="text-sm text-muted-foreground">Work only</span>
                      )}
                    </TableCell>
                    <TableCell>{getPersonalAccountBadge(employee)}</TableCell>
                  </TableRow>
                )
              })
            )}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}
