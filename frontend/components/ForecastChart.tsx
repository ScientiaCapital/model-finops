'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { TrendingUp, AlertTriangle, Calendar, DollarSign } from 'lucide-react'
import type { ForecastResponse, BudgetExhaustionResponse } from '@/lib/api'

interface ForecastChartProps {
  forecast: ForecastResponse | null
  budgetExhaustion: BudgetExhaustionResponse | null
  loading?: boolean
}

export function ForecastChart({
  forecast,
  budgetExhaustion,
  loading = false,
}: ForecastChartProps) {
  const getWarningVariant = (level: string) => {
    switch (level) {
      case 'safe': return 'success'
      case 'caution': return 'warning'
      case 'warning': return 'warning'
      case 'critical': return 'destructive'
      default: return 'secondary'
    }
  }

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <TrendingUp className="h-5 w-5" />
            Cost Forecast
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <div className="animate-pulse text-muted-foreground">Loading forecast...</div>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-blue-500" />
            Cost Forecast
          </CardTitle>
          {forecast && (
            <Badge variant="outline">{forecast.method_used}</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {forecast && (
          <>
            {/* Predicted Cost Summary */}
            <div className="grid grid-cols-2 gap-4">
              <div className="p-3 rounded-lg bg-muted/50">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <DollarSign className="h-4 w-4" />
                  Predicted ({forecast.horizon_days}d)
                </div>
                <div className="text-2xl font-bold mt-1">
                  ${forecast.total_predicted_cost.toFixed(2)}
                </div>
              </div>
              <div className="p-3 rounded-lg bg-muted/50">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Calendar className="h-4 w-4" />
                  Data Points
                </div>
                <div className="text-2xl font-bold mt-1">
                  {forecast.data_points_used}
                </div>
              </div>
            </div>

            {/* Daily Forecast Preview */}
            {forecast.daily_forecasts.length > 0 && (
              <div className="space-y-2">
                <p className="text-sm font-medium">Daily Breakdown</p>
                <div className="flex gap-1 h-16 items-end">
                  {forecast.daily_forecasts.slice(0, 7).map((day, i) => {
                    const maxCost = Math.max(...forecast.daily_forecasts.map(d => d.predicted_cost))
                    const height = maxCost > 0 ? (day.predicted_cost / maxCost) * 100 : 0
                    return (
                      <div
                        key={i}
                        className="flex-1 bg-blue-500/80 rounded-t hover:bg-blue-600 transition-colors"
                        style={{ height: `${Math.max(height, 5)}%` }}
                        title={`${day.date}: $${day.predicted_cost.toFixed(2)}`}
                      />
                    )
                  })}
                </div>
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>{forecast.daily_forecasts[0]?.date}</span>
                  <span>{forecast.daily_forecasts[Math.min(6, forecast.daily_forecasts.length - 1)]?.date}</span>
                </div>
              </div>
            )}
          </>
        )}

        {/* Budget Exhaustion Warning */}
        {budgetExhaustion && (
          <div className="p-3 rounded-lg border bg-muted/30">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4" />
                <span className="text-sm font-medium">Budget Status</span>
              </div>
              <Badge variant={getWarningVariant(budgetExhaustion.warning_level)}>
                {budgetExhaustion.warning_level}
              </Badge>
            </div>
            <Progress value={budgetExhaustion.percentage_used} className="h-2" />
            <div className="flex justify-between text-xs text-muted-foreground mt-2">
              <span>${budgetExhaustion.current_spend.toFixed(2)} used</span>
              <span>${budgetExhaustion.monthly_budget.toFixed(2)} budget</span>
            </div>
            {budgetExhaustion.days_until_exhaustion && (
              <p className="text-xs mt-2 text-amber-600">
                ⚠️ Budget projected to exhaust in {budgetExhaustion.days_until_exhaustion} days
              </p>
            )}
            <p className="text-xs mt-1 text-muted-foreground">
              {budgetExhaustion.recommendation}
            </p>
          </div>
        )}

        {!forecast && !budgetExhaustion && (
          <div className="text-center py-6 text-muted-foreground">
            <TrendingUp className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">No forecast data available</p>
            <p className="text-xs mt-1">Need more usage data to generate predictions</p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
