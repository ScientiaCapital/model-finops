'use client'

import { useState, useMemo } from 'react'
import { DepartmentSpendSummary } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Building2, TrendingUp } from 'lucide-react'

interface DepartmentSpendChartProps {
  departments: DepartmentSpendSummary[]
  view?: 'monthly' | 'quarterly'
}

export function DepartmentSpendChart({ departments, view = 'monthly' }: DepartmentSpendChartProps) {
  const [hoveredDept, setHoveredDept] = useState<string | null>(null)

  const totalSpend = useMemo(() => {
    return departments.reduce((sum, dept) => sum + dept.total_spend_usd, 0)
  }, [departments])

  const sortedDepartments = useMemo(() => {
    return [...departments].sort((a, b) => b.total_spend_usd - a.total_spend_usd)
  }, [departments])

  const maxSpend = useMemo(() => {
    return Math.max(...departments.map(d => d.total_spend_usd), 1)
  }, [departments])

  const getPercentage = (spend: number) => {
    if (totalSpend === 0) return 0
    return (spend / totalSpend) * 100
  }

  const getBarWidth = (spend: number) => {
    return (spend / maxSpend) * 100
  }

  const getDepartmentColor = (index: number) => {
    const colors = [
      'bg-blue-500',
      'bg-purple-500',
      'bg-green-500',
      'bg-amber-500',
      'bg-rose-500',
      'bg-cyan-500',
      'bg-indigo-500',
      'bg-pink-500',
    ]
    return colors[index % colors.length]
  }

  const getDepartmentHoverColor = (index: number) => {
    const colors = [
      'bg-blue-600',
      'bg-purple-600',
      'bg-green-600',
      'bg-amber-600',
      'bg-rose-600',
      'bg-cyan-600',
      'bg-indigo-600',
      'bg-pink-600',
    ]
    return colors[index % colors.length]
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Building2 className="h-5 w-5" />
            Department Spend
          </CardTitle>
          <Badge variant="outline">{view === 'monthly' ? 'Monthly' : 'Quarterly'}</Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {sortedDepartments.length === 0 ? (
            <div className="text-center text-muted-foreground py-8">
              No department data available
            </div>
          ) : (
            <>
              {sortedDepartments.map((dept, index) => {
                const percentage = getPercentage(dept.total_spend_usd)
                const barWidth = getBarWidth(dept.total_spend_usd)
                const isHovered = hoveredDept === dept.department_name
                const color = getDepartmentColor(index)
                const hoverColor = getDepartmentHoverColor(index)

                return (
                  <div
                    key={dept.department_name}
                    className="space-y-2"
                    onMouseEnter={() => setHoveredDept(dept.department_name)}
                    onMouseLeave={() => setHoveredDept(null)}
                  >
                    <div className="flex items-center justify-between text-sm">
                      <div className="flex items-center gap-2">
                        <div className={`w-3 h-3 rounded ${color}`} />
                        <span className="font-medium">{dept.department_name}</span>
                        <span className="text-muted-foreground text-xs">
                          ({dept.employee_count}{' '}
                          {dept.employee_count === 1 ? 'employee' : 'employees'})
                        </span>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="font-semibold">${dept.total_spend_usd.toFixed(2)}</span>
                        <span className="text-muted-foreground text-xs w-12 text-right">
                          {percentage.toFixed(1)}%
                        </span>
                      </div>
                    </div>
                    <div className="relative h-8 bg-muted rounded-md overflow-hidden">
                      <div
                        className={`h-full transition-all duration-300 ${
                          isHovered ? hoverColor : color
                        }`}
                        style={{ width: `${barWidth}%` }}
                      />
                      {isHovered && (
                        <div className="absolute inset-0 flex items-center px-3 text-xs text-white font-medium">
                          <div className="flex items-center justify-between w-full">
                            <span>{dept.top_provider && `Top: ${dept.top_provider}`}</span>
                            {dept.budget_usd && (
                              <span>
                                Budget: ${dept.budget_usd.toFixed(0)} (
                                {dept.budget_percent.toFixed(0)}%)
                              </span>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}

              {/* Summary */}
              <div className="pt-4 border-t mt-6">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <TrendingUp className="h-4 w-4 text-muted-foreground" />
                    <span className="font-medium">Total Spend</span>
                  </div>
                  <span className="text-2xl font-bold">${totalSpend.toFixed(2)}</span>
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  Across {sortedDepartments.length} departments
                </div>
              </div>

              {/* Budget warnings */}
              {sortedDepartments.filter(d => d.budget_usd && d.budget_percent >= 80).length > 0 && (
                <div className="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-md">
                  <div className="text-sm font-medium text-amber-900 mb-2">Budget Warnings</div>
                  <div className="space-y-1">
                    {sortedDepartments
                      .filter(d => d.budget_usd && d.budget_percent >= 80)
                      .map(dept => (
                        <div key={dept.department_name} className="text-xs text-amber-800">
                          {dept.department_name}: {dept.budget_percent.toFixed(0)}% of budget used
                        </div>
                      ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
