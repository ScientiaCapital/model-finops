'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { AlertTriangle, CheckCircle, XCircle, AlertCircle, Info } from 'lucide-react'
import type { CostAnomaly } from '@/lib/api'

interface AnomalyAlertsProps {
  anomalies: CostAnomaly[]
  onAcknowledge?: (id: string) => void
  loading?: boolean
}

export function AnomalyAlerts({ anomalies, onAcknowledge, loading = false }: AnomalyAlertsProps) {
  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'critical':
        return <XCircle className="h-4 w-4 text-red-500" />
      case 'high':
        return <AlertTriangle className="h-4 w-4 text-orange-500" />
      case 'medium':
        return <AlertCircle className="h-4 w-4 text-yellow-500" />
      default:
        return <Info className="h-4 w-4 text-blue-500" />
    }
  }

  const getSeverityBadgeVariant = (severity: string) => {
    switch (severity) {
      case 'critical':
        return 'destructive'
      case 'high':
        return 'destructive'
      case 'medium':
        return 'warning'
      default:
        return 'secondary'
    }
  }

  const unacknowledged = anomalies.filter(a => !a.acknowledged)
  const acknowledged = anomalies.filter(a => a.acknowledged)

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-amber-500" />
            Cost Anomalies
          </CardTitle>
          {unacknowledged.length > 0 && (
            <Badge variant="destructive">{unacknowledged.length} new</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {anomalies.length === 0 ? (
          <div className="text-center py-6 text-muted-foreground">
            <CheckCircle className="h-8 w-8 mx-auto mb-2 text-green-500 opacity-70" />
            <p className="text-sm">No anomalies detected</p>
            <p className="text-xs mt-1">Your costs are within expected ranges</p>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Unacknowledged anomalies first */}
            {unacknowledged.slice(0, 5).map(anomaly => (
              <div
                key={anomaly.id}
                className="flex items-start justify-between p-3 rounded-lg border bg-red-50 dark:bg-red-900/10 border-red-200 dark:border-red-800"
              >
                <div className="flex gap-3">
                  {getSeverityIcon(anomaly.severity)}
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">
                        {new Date(anomaly.anomaly_date).toLocaleDateString()}
                      </span>
                      <Badge variant={getSeverityBadgeVariant(anomaly.severity)}>
                        {anomaly.severity}
                      </Badge>
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      <span>Expected: ${anomaly.expected_cost.toFixed(2)}</span>
                      <span className="mx-2">→</span>
                      <span className="text-red-600 font-medium">
                        Actual: ${anomaly.actual_cost.toFixed(2)}
                      </span>
                      <span className="ml-2">(+{anomaly.deviation_percent.toFixed(0)}%)</span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      Z-score: {anomaly.z_score.toFixed(2)}
                    </p>
                  </div>
                </div>
                {onAcknowledge && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => onAcknowledge(anomaly.id)}
                    disabled={loading}
                  >
                    Acknowledge
                  </Button>
                )}
              </div>
            ))}

            {/* Acknowledged anomalies (collapsed) */}
            {acknowledged.length > 0 && (
              <div className="pt-2 border-t">
                <p className="text-xs text-muted-foreground mb-2">
                  Previously acknowledged ({acknowledged.length})
                </p>
                {acknowledged.slice(0, 3).map(anomaly => (
                  <div
                    key={anomaly.id}
                    className="flex items-center justify-between py-2 text-xs text-muted-foreground"
                  >
                    <div className="flex items-center gap-2">
                      <CheckCircle className="h-3 w-3 text-green-500" />
                      <span>{new Date(anomaly.anomaly_date).toLocaleDateString()}</span>
                      <Badge variant="outline" className="text-xs">
                        {anomaly.severity}
                      </Badge>
                    </div>
                    <span>+{anomaly.deviation_percent.toFixed(0)}%</span>
                  </div>
                ))}
              </div>
            )}

            {anomalies.length > 8 && (
              <p className="text-xs text-center text-muted-foreground">
                +{anomalies.length - 8} more anomalies
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
