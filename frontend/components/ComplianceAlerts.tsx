'use client'

import { useState, useMemo } from 'react'
import { ComplianceAlert, resolveComplianceAlert } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { AlertTriangle, CheckCircle2, Info, XCircle, Filter } from 'lucide-react'

interface ComplianceAlertsProps {
  alerts: ComplianceAlert[]
  onAlertResolved?: (alertId: string) => void
  loading?: boolean
}

export function ComplianceAlerts({
  alerts,
  onAlertResolved,
  loading = false,
}: ComplianceAlertsProps) {
  const [severityFilter, setSeverityFilter] = useState<string>('all')
  const [resolving, setResolving] = useState<string | null>(null)

  const filteredAlerts = useMemo(() => {
    if (severityFilter === 'all') return alerts
    return alerts.filter((a) => a.severity === severityFilter)
  }, [alerts, severityFilter])

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'critical':
        return <XCircle className="h-4 w-4 text-red-500" />
      case 'warning':
        return <AlertTriangle className="h-4 w-4 text-amber-500" />
      case 'info':
        return <Info className="h-4 w-4 text-blue-500" />
      default:
        return <Info className="h-4 w-4 text-gray-500" />
    }
  }

  const getSeverityBadge = (severity: string) => {
    const variants: Record<string, string> = {
      critical: 'bg-red-50 text-red-700 border-red-200',
      warning: 'bg-amber-50 text-amber-700 border-amber-200',
      info: 'bg-blue-50 text-blue-700 border-blue-200',
    }

    return (
      <Badge variant="outline" className={variants[severity] || variants.info}>
        {severity}
      </Badge>
    )
  }

  const getAlertTypeLabel = (alertType: string) => {
    const labels: Record<string, string> = {
      blocked_provider: 'Blocked Provider',
      chinese_provider: 'Chinese AI',
      unapproved_model: 'Unapproved Model',
      budget_warning: 'Budget Warning',
      budget_exceeded: 'Budget Exceeded',
      personal_high_usage: 'High Personal Usage',
      data_residency: 'Data Residency',
      new_api_key: 'New API Key',
    }
    return labels[alertType] || alertType
  }

  const handleResolve = async (alertId: string) => {
    try {
      setResolving(alertId)
      await resolveComplianceAlert(alertId, 'Acknowledged from dashboard')
      onAlertResolved?.(alertId)
    } catch (error) {
      console.error('Failed to resolve alert:', error)
    } finally {
      setResolving(null)
    }
  }

  const unacknowledgedAlerts = alerts.filter((a) => !a.resolved)

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-amber-500" />
            Compliance Alerts
            {unacknowledgedAlerts.length > 0 && (
              <Badge variant="destructive" className="ml-2">
                {unacknowledgedAlerts.length}
              </Badge>
            )}
          </CardTitle>
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-muted-foreground" />
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="border rounded-md px-3 py-1 text-sm"
            >
              <option value="all">All Severity</option>
              <option value="critical">Critical</option>
              <option value="warning">Warning</option>
              <option value="info">Info</option>
            </select>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {loading ? (
            <div className="text-center text-muted-foreground py-8">
              Loading alerts...
            </div>
          ) : filteredAlerts.length === 0 ? (
            <div className="text-center text-muted-foreground py-8">
              <CheckCircle2 className="h-12 w-12 mx-auto mb-2 text-green-500" />
              <div className="font-medium">All clear!</div>
              <div className="text-sm">No compliance alerts to display</div>
            </div>
          ) : (
            filteredAlerts.map((alert) => (
              <div
                key={alert.id}
                className={`border rounded-lg p-4 ${
                  alert.resolved ? 'bg-gray-50 opacity-60' : 'bg-white'
                } ${
                  alert.severity === 'critical'
                    ? 'border-red-200'
                    : alert.severity === 'warning'
                    ? 'border-amber-200'
                    : 'border-gray-200'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-3 flex-1">
                    <div className="mt-1">{getSeverityIcon(alert.severity)}</div>
                    <div className="flex-1 space-y-2">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-medium">{alert.title}</span>
                        {getSeverityBadge(alert.severity)}
                        <Badge variant="outline" className="text-xs">
                          {getAlertTypeLabel(alert.alert_type)}
                        </Badge>
                        {alert.provider && (
                          <Badge variant="outline" className="text-xs capitalize">
                            {alert.provider}
                          </Badge>
                        )}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        {alert.message}
                      </div>
                      {alert.details && Object.keys(alert.details).length > 0 && (
                        <div className="text-xs text-muted-foreground bg-gray-50 p-2 rounded">
                          {Object.entries(alert.details).map(([key, value]) => (
                            <div key={key}>
                              <span className="font-medium">{key}:</span>{' '}
                              {String(value)}
                            </div>
                          ))}
                        </div>
                      )}
                      <div className="flex items-center gap-4 text-xs text-muted-foreground">
                        <span>
                          {new Date(alert.created_at).toLocaleDateString()}{' '}
                          {new Date(alert.created_at).toLocaleTimeString()}
                        </span>
                        {alert.resolved && alert.resolved_at && (
                          <span className="text-green-600">
                            Resolved {new Date(alert.resolved_at).toLocaleDateString()}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  {!alert.resolved && (
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleResolve(alert.id)}
                        disabled={resolving === alert.id}
                      >
                        {resolving === alert.id ? 'Resolving...' : 'Acknowledge'}
                      </Button>
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Summary stats */}
        {filteredAlerts.length > 0 && (
          <div className="mt-6 pt-4 border-t grid grid-cols-3 gap-4 text-center">
            <div>
              <div className="text-2xl font-bold text-red-600">
                {filteredAlerts.filter((a) => !a.resolved && a.severity === 'critical').length}
              </div>
              <div className="text-xs text-muted-foreground">Critical</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-amber-600">
                {filteredAlerts.filter((a) => !a.resolved && a.severity === 'warning').length}
              </div>
              <div className="text-xs text-muted-foreground">Warnings</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-green-600">
                {filteredAlerts.filter((a) => a.resolved).length}
              </div>
              <div className="text-xs text-muted-foreground">Resolved</div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
