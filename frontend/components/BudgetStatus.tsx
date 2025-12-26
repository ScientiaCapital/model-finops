'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { AlertTriangle, CheckCircle, XCircle, DollarSign } from 'lucide-react'

interface BudgetStatusProps {
  currentSpend: number
  monthlyBudget: number
  percentageUsed: number
  remaining: number
  daysRemaining: number
  projectedMonthly: number
  status: 'healthy' | 'warning' | 'critical'
}

export function BudgetStatus({
  currentSpend,
  monthlyBudget,
  percentageUsed,
  remaining,
  daysRemaining,
  projectedMonthly,
  status,
}: BudgetStatusProps) {
  const statusConfig = {
    healthy: {
      icon: CheckCircle,
      color: 'text-green-500',
      bgColor: 'bg-green-500',
      badge: 'success' as const,
      label: 'On Track',
    },
    warning: {
      icon: AlertTriangle,
      color: 'text-yellow-500',
      bgColor: 'bg-yellow-500',
      badge: 'warning' as const,
      label: 'Warning',
    },
    critical: {
      icon: XCircle,
      color: 'text-red-500',
      bgColor: 'bg-red-500',
      badge: 'destructive' as const,
      label: 'Critical',
    },
  }

  const config = statusConfig[status]
  const StatusIcon = config.icon

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium">Budget Status</CardTitle>
        <Badge variant={config.badge} className="gap-1">
          <StatusIcon className="h-3 w-3" />
          {config.label}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Progress Bar */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">
              ${currentSpend.toFixed(2)} / ${monthlyBudget.toFixed(2)}
            </span>
            <span className={config.color}>{percentageUsed.toFixed(1)}%</span>
          </div>
          <Progress value={Math.min(percentageUsed, 100)} className="h-2" />
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <p className="text-muted-foreground">Remaining</p>
            <p className="font-medium flex items-center gap-1">
              <DollarSign className="h-3 w-3" />
              {remaining.toFixed(2)}
            </p>
          </div>
          <div>
            <p className="text-muted-foreground">Days Left</p>
            <p className="font-medium">{daysRemaining}</p>
          </div>
          <div className="col-span-2">
            <p className="text-muted-foreground">Projected Monthly</p>
            <p className={`font-medium ${projectedMonthly > monthlyBudget ? 'text-red-500' : 'text-green-500'}`}>
              ${projectedMonthly.toFixed(2)}
              {projectedMonthly > monthlyBudget && (
                <span className="text-xs ml-1">(over budget)</span>
              )}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
