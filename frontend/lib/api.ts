const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface Stats {
  total_requests: number
  total_cost_cents: number
  total_tokens: number
  cache_hits: number
  cache_misses: number
  avg_response_time_ms: number
  requests_by_provider: Record<string, number>
  cost_by_provider: Record<string, number>
}

export interface CacheStats {
  total_entries: number
  total_hits: number
  hit_rate: number
  avg_quality_score: number
  storage_used_mb: number
}

export interface RoutingMetrics {
  total_decisions: number
  avg_confidence: number
  accuracy_rate: number
  decisions_by_provider: Record<string, number>
  avg_complexity_by_provider: Record<string, number>
}

export interface HealthStatus {
  status: string
  version: string
  providers_available: string[]
  routing_engine: string
  auto_route_enabled: boolean
}

export interface BudgetStatusData {
  user_id: string
  current_spend: number
  monthly_budget: number
  percentage_used: number
  remaining: number
  days_in_month: number
  days_remaining: number
  daily_average: number
  projected_monthly: number
  threshold_alerts: Array<{
    threshold: number
    threshold_percentage: number
    status: string
  }>
  status: 'healthy' | 'warning' | 'critical'
}

export interface BudgetConfig {
  user_id: string
  monthly_budget: number
  alert_thresholds: number[]
  alert_email: string | null
  alert_webhook_url: string | null
  slack_webhook_url: string | null
  discord_webhook_url: string | null
  alert_cooldown_minutes: number
  enabled: boolean
}

async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })

  if (!res.ok) {
    throw new Error(`API Error: ${res.status} ${res.statusText}`)
  }

  return res.json()
}

export async function getHealth(): Promise<HealthStatus> {
  return fetchAPI<HealthStatus>('/health')
}

export async function getStats(): Promise<Stats> {
  return fetchAPI<Stats>('/stats')
}

export async function getCacheStats(): Promise<CacheStats> {
  return fetchAPI<CacheStats>('/cache/stats')
}

export async function getRoutingMetrics(days = 7): Promise<RoutingMetrics> {
  return fetchAPI<RoutingMetrics>(`/routing/metrics?days=${days}`)
}

export async function getProviders(): Promise<string[]> {
  return fetchAPI<string[]>('/providers')
}

export async function triggerRetrain(): Promise<{ status: string; message: string }> {
  return fetchAPI('/admin/learning/retrain', { method: 'POST' })
}

export async function getLearningStatus(): Promise<{
  model_loaded: boolean
  last_training: string | null
  training_samples: number
  accuracy: number | null
}> {
  return fetchAPI('/admin/learning/status')
}

// Budget Management APIs
export async function getBudgetStatus(): Promise<BudgetStatusData> {
  return fetchAPI<BudgetStatusData>('/budget/status')
}

export async function getBudgetConfig(): Promise<BudgetConfig> {
  return fetchAPI<BudgetConfig>('/budget/config')
}

export async function setBudgetConfig(config: Partial<BudgetConfig>): Promise<BudgetConfig> {
  return fetchAPI<BudgetConfig>('/budget/config', {
    method: 'POST',
    body: JSON.stringify(config),
  })
}

export async function testBudgetWebhook(): Promise<{
  success: boolean
  channels_notified: string[]
  message: string
}> {
  return fetchAPI('/budget/test-webhook', { method: 'POST' })
}

export async function getBudgetAlerts(limit = 50): Promise<{
  alerts: Array<{
    id: string
    threshold_percentage: number
    current_spend: number
    monthly_budget: number
    alert_channels: string[]
    status: string
    sent_at: string
  }>
  count: number
}> {
  return fetchAPI(`/budget/alerts?limit=${limit}`)
}
