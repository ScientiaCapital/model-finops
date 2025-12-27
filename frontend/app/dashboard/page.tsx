'use client'

import { useEffect, useState, useCallback } from 'react'
import { MetricsCard } from '@/components/MetricsCard'
import { ProviderChart } from '@/components/ProviderChart'
import { RecentRequests } from '@/components/RecentRequests'
import { RealtimeIndicator } from '@/components/RealtimeIndicator'
import { BudgetStatus } from '@/components/BudgetStatus'
import { ArbitrageOpportunities } from '@/components/ArbitrageOpportunities'
import { ForecastChart } from '@/components/ForecastChart'
import { AnomalyAlerts } from '@/components/AnomalyAlerts'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import {
  getStats,
  getCacheStats,
  getRoutingMetrics,
  getHealth,
  getBudgetStatus,
  getArbitrageOpportunities,
  getArbitrageSavingsReport,
  getForecast,
  getBudgetExhaustion,
  getAnomalies,
  acknowledgeAnomaly,
  type Stats,
  type CacheStats,
  type RoutingMetrics,
  type HealthStatus,
  type BudgetStatusData,
  type ArbitrageOpportunity,
  type SavingsReport,
  type ForecastResponse,
  type BudgetExhaustionResponse,
  type CostAnomaly,
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
  // New Sprint Dec 27 features
  const [arbitrageOpportunities, setArbitrageOpportunities] = useState<ArbitrageOpportunity[]>([])
  const [savingsReport, setSavingsReport] = useState<SavingsReport | null>(null)
  const [forecast, setForecast] = useState<ForecastResponse | null>(null)
  const [budgetExhaustion, setBudgetExhaustion] = useState<BudgetExhaustionResponse | null>(null)
  const [anomalies, setAnomalies] = useState<CostAnomaly[]>([])
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
    console.log('[Dashboard] Refresh button clicked - fetching data...')
    try {
      setLoading(true)
      setError(null)

      // Fetch core metrics and new Sprint Dec 27 features in parallel
      const [
        statsData, cacheData, routingData, healthData, budgetData,
        arbitrageData, savingsData, forecastData, exhaustionData, anomalyData
      ] = await Promise.all([
        getStats().catch(() => null),
        getCacheStats().catch(() => null),
        getRoutingMetrics().catch(() => null),
        getHealth().catch(() => null),
        getBudgetStatus().catch(() => null),
        // Sprint Dec 27 features
        getArbitrageOpportunities(10).catch(() => []),
        getArbitrageSavingsReport(30).catch(() => null),
        getForecast(7).catch(() => null),
        getBudgetExhaustion(budgetStatus?.monthly_budget || 100).catch(() => null),
        getAnomalies(30, 2.0).catch(() => ({ anomalies: [] })),
      ])

      console.log('[Dashboard] Data fetched:', { statsData, cacheData, healthData, arbitrageData, forecastData })
      setStats(statsData)
      setCacheStats(cacheData)
      setRoutingMetrics(routingData)
      setHealth(healthData)
      setBudgetStatus(budgetData)
      // Sprint Dec 27 features
      setArbitrageOpportunities(arbitrageData || [])
      setSavingsReport(savingsData)
      setForecast(forecastData)
      setBudgetExhaustion(exhaustionData)
      setAnomalies(anomalyData?.anomalies || [])
      setLastUpdated(new Date())
    } catch (err) {
      console.error('[Dashboard] Fetch error:', err)
      setError('Failed to fetch data. Is the API server running?')
    } finally {
      setLoading(false)
    }
  }, [budgetStatus?.monthly_budget])

  // Handler to acknowledge anomalies
  const handleAcknowledgeAnomaly = useCallback(async (anomalyId: string) => {
    try {
      await acknowledgeAnomaly(anomalyId, 'Acknowledged from dashboard')
      setAnomalies(prev => prev.map(a =>
        a.id === anomalyId ? { ...a, acknowledged: true, acknowledged_at: new Date().toISOString() } : a
      ))
    } catch (err) {
      console.error('[Dashboard] Failed to acknowledge anomaly:', err)
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
          <Button onClick={fetchData} variant="outline" size="sm" disabled={loading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            {loading ? 'Refreshing...' : 'Refresh'}
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
          value={stats ? (stats.overall.total_tokens_in + stats.overall.total_tokens_out).toLocaleString() : '0'}
          description="Tokens processed"
          icon={Database}
        />
        <MetricsCard
          title="Avg Cost/Request"
          value={stats ? `$${stats.overall.avg_cost_per_request.toFixed(6)}` : '$0.00'}
          description="Average cost per request"
          icon={TrendingUp}
        />
        <MetricsCard
          title="Cache Entries"
          value={cacheStats?.total_entries.toLocaleString() || '0'}
          description={`${cacheStats ? (cacheStats.cache_size_bytes / (1024 * 1024)).toFixed(2) : '0'} MB used`}
          icon={Database}
        />
        <MetricsCard
          title="High Confidence"
          value={
            routingMetrics
              ? `${routingMetrics.confidence_distribution.high}%`
              : 'N/A'
          }
          description="High confidence decisions"
          icon={Brain}
        />
      </div>

      {/* Charts and Budget */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {stats && stats.by_provider.length > 0 && (
          <>
            <ProviderChart
              data={Object.fromEntries(stats.by_provider.map(p => [p.provider, p.request_count]))}
              title="Requests by Provider"
              type="requests"
            />
            <ProviderChart
              data={Object.fromEntries(stats.by_provider.map(p => [p.provider, p.total_cost]))}
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

      {/* Sprint Dec 27: Cost Intelligence Features */}
      <div className="space-y-4">
        <h2 className="text-xl font-semibold flex items-center gap-2">
          <Brain className="h-5 w-5 text-purple-500" />
          Cost Intelligence (Sprint Dec 27)
        </h2>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {/* Arbitrage Opportunities */}
          <ArbitrageOpportunities
            opportunities={arbitrageOpportunities}
            loading={loading}
          />

          {/* Cost Forecast */}
          <ForecastChart
            forecast={forecast}
            budgetExhaustion={budgetExhaustion}
            loading={loading}
          />

          {/* Anomaly Alerts */}
          <AnomalyAlerts
            anomalies={anomalies}
            onAcknowledge={handleAcknowledgeAnomaly}
            loading={loading}
          />
        </div>

        {/* Savings Report Summary */}
        {savingsReport && (
          <Card>
            <CardContent className="pt-6">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
                <div>
                  <p className="text-sm text-muted-foreground">Potential Savings</p>
                  <p className="text-2xl font-bold text-green-600">
                    ${savingsReport.total_potential_savings.toFixed(2)}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Actual Savings</p>
                  <p className="text-2xl font-bold text-blue-600">
                    ${savingsReport.actual_savings.toFixed(2)}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Opportunities Found</p>
                  <p className="text-2xl font-bold">{savingsReport.opportunities_found}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Savings Rate</p>
                  <p className="text-2xl font-bold text-purple-600">
                    {(savingsReport.savings_rate * 100).toFixed(1)}%
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Recent Activity - Now with real-time data */}
      <RecentRequests
        requests={realtimeStats.recentMetrics.map((m) => ({
          id: m.id,
          prompt_text: `${m.selected_provider} request`,
          provider: m.selected_provider,
          tokens_used: 0,
          cost_cents: Math.round((m.cost_usd || 0) * 100),
          response_time_ms: m.response_time_ms,
          created_at: m.created_at,
        }))}
      />
    </div>
  )
}
