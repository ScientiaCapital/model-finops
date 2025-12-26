'use client'

import { useEffect, useState, useCallback } from 'react'
import { MetricsCard } from '@/components/MetricsCard'
import { ProviderChart } from '@/components/ProviderChart'
import { RecentRequests } from '@/components/RecentRequests'
import { RealtimeIndicator } from '@/components/RealtimeIndicator'
import { BudgetStatus } from '@/components/BudgetStatus'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import {
  getStats,
  getCacheStats,
  getRoutingMetrics,
  getHealth,
  getBudgetStatus,
  type Stats,
  type CacheStats,
  type RoutingMetrics,
  type HealthStatus,
  type BudgetStatusData,
} from '@/lib/api'
import { useRealtimeMetrics } from '@/hooks/useRealtimeMetrics'
import {
  DollarSign,
  Activity,
  Zap,
  Database,
  RefreshCw,
  TrendingUp,
  Server,
  Brain,
} from 'lucide-react'

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [cacheStats, setCacheStats] = useState<CacheStats | null>(null)
  const [routingMetrics, setRoutingMetrics] = useState<RoutingMetrics | null>(null)
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [budgetStatus, setBudgetStatus] = useState<BudgetStatusData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  // Real-time metrics subscription
  const {
    isConnected: realtimeConnected,
    error: realtimeError,
    stats: realtimeStats,
  } = useRealtimeMetrics({
    onNewMetric: (metric) => {
      // Update stats when new metric arrives
      setStats((prev) => prev ? {
        ...prev,
        overall: {
          ...prev.overall,
          total_requests: prev.overall.total_requests + 1,
          total_cost: prev.overall.total_cost + metric.cost_usd,
        },
      } : prev)
    },
  })

  const fetchData = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      const [statsData, cacheData, routingData, healthData, budgetData] = await Promise.all([
        getStats().catch(() => null),
        getCacheStats().catch(() => null),
        getRoutingMetrics().catch(() => null),
        getHealth().catch(() => null),
        getBudgetStatus().catch(() => null),
      ])

      setStats(statsData)
      setCacheStats(cacheData)
      setRoutingMetrics(routingData)
      setHealth(healthData)
      setBudgetStatus(budgetData)
      setLastUpdated(new Date())
    } catch {
      setError('Failed to fetch data. Is the API server running?')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
    // Auto-refresh every 30 seconds (fallback when realtime not connected)
    const interval = setInterval(fetchData, realtimeConnected ? 60000 : 30000)
    return () => clearInterval(interval)
  }, [fetchData, realtimeConnected])

  if (loading && !stats) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <RefreshCw className="h-8 w-8 animate-spin mx-auto text-primary" />
          <p className="mt-2 text-sm text-muted-foreground">Loading dashboard...</p>
        </div>
      </div>
    )
  }

  if (error && !stats) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <Server className="h-8 w-8 mx-auto text-destructive" />
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
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground">
            Real-time AI cost optimization metrics
          </p>
        </div>
        <div className="flex items-center gap-4">
          <RealtimeIndicator isConnected={realtimeConnected} error={realtimeError} />
          {lastUpdated && (
            <span className="text-xs text-muted-foreground">
              Updated {lastUpdated.toLocaleTimeString()}
            </span>
          )}
          <Button onClick={fetchData} variant="outline" size="sm">
            <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Service Status */}
      {health && (
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <Badge variant="success" className="text-xs">
                  {health.status}
                </Badge>
                <span className="text-sm text-muted-foreground">
                  v{health.version}
                </span>
                <span className="text-sm text-muted-foreground">
                  Auto-Route: {health.auto_route_enabled ? 'On' : 'Off'}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Providers:</span>
                {health.providers_available?.map((provider) => (
                  <Badge key={provider} variant="outline" className="capitalize">
                    {provider}
                  </Badge>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Key Metrics */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <MetricsCard
          title="Total Cost"
          value={stats ? `$${stats.overall.total_cost.toFixed(4)}` : '$0.00'}
          description="All time spending"
          icon={DollarSign}
        />
        <MetricsCard
          title="Total Requests"
          value={stats?.overall.total_requests.toLocaleString() || '0'}
          description="API calls processed"
          icon={Activity}
        />
        <MetricsCard
          title="Cache Hit Rate"
          value={cacheStats && cacheStats.total_entries > 0
            ? `${((cacheStats.total_hits / cacheStats.total_entries) * 100).toFixed(1)}%`
            : '0%'}
          description={`${cacheStats?.total_hits.toLocaleString() || 0} cache hits`}
          icon={Zap}
          badge={
            cacheStats && cacheStats.total_entries > 0 && (cacheStats.total_hits / cacheStats.total_entries) > 0.7
              ? { text: 'Excellent', variant: 'success' }
              : cacheStats && cacheStats.total_entries > 0 && (cacheStats.total_hits / cacheStats.total_entries) > 0.4
              ? { text: 'Good', variant: 'warning' }
              : { text: 'Low', variant: 'destructive' }
          }
        />
        <MetricsCard
          title="Cost Savings"
          value={
            routingMetrics
              ? `${routingMetrics.cost_savings.percent_saved.toFixed(1)}%`
              : '0%'
          }
          description={`${routingMetrics?.total_decisions.toLocaleString() || 0} decisions`}
          icon={Brain}
        />
      </div>

      {/* Secondary Metrics */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <MetricsCard
          title="Total Tokens"
          value={stats?.total_tokens.toLocaleString() || '0'}
          description="Tokens processed"
          icon={Database}
        />
        <MetricsCard
          title="Avg Response Time"
          value={stats ? `${stats.avg_response_time_ms.toFixed(0)}ms` : '0ms'}
          description="Average latency"
          icon={TrendingUp}
        />
        <MetricsCard
          title="Cache Entries"
          value={cacheStats?.total_entries.toLocaleString() || '0'}
          description={`${cacheStats?.storage_used_mb.toFixed(2) || 0} MB used`}
          icon={Database}
        />
        <MetricsCard
          title="Avg Confidence"
          value={
            routingMetrics
              ? `${(routingMetrics.avg_confidence * 100).toFixed(0)}%`
              : 'N/A'
          }
          description="Routing confidence"
          icon={Brain}
        />
      </div>

      {/* Charts and Budget */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {stats && stats.by_provider.length > 0 && (
          <>
            <ProviderChart
              data={Object.fromEntries(stats.by_provider.map(p => [p.provider, p.count]))}
              title="Requests by Provider"
              type="requests"
            />
            <ProviderChart
              data={Object.fromEntries(stats.by_provider.map(p => [p.provider, p.cost]))}
              title="Cost by Provider"
              type="cost"
            />
          </>
        )}
        {budgetStatus && (
          <BudgetStatus
            currentSpend={budgetStatus.current_spend}
            monthlyBudget={budgetStatus.monthly_budget}
            percentageUsed={budgetStatus.percentage_used}
            remaining={budgetStatus.remaining}
            daysRemaining={budgetStatus.days_remaining}
            projectedMonthly={budgetStatus.projected_monthly}
            status={budgetStatus.status}
          />
        )}
      </div>

      {/* Recent Activity - Now with real-time data */}
      <RecentRequests
        requests={realtimeStats.recentMetrics.map((m) => ({
          id: m.id,
          prompt: `${m.selected_provider} request`,
          provider: m.selected_provider,
          tokens: 0,
          responseTime: m.response_time_ms,
          timestamp: m.created_at,
        }))}
      />
    </div>
  )
}
