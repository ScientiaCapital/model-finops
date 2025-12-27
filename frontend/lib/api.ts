const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface Stats {
  overall: {
    total_requests: number
    total_cost: number
    total_tokens_in: number
    total_tokens_out: number
    avg_cost_per_request: number
  }
  by_provider: Array<{ provider: string; request_count: number; total_cost: number; avg_cost: number }>
  by_complexity: Array<{ complexity: string; request_count: number; total_cost: number; avg_cost: number }>
  recent_requests: Array<{ timestamp: string; provider: string; cost: number }>
}

export interface CacheStats {
  total_entries: number
  total_hits: number
  avg_quality_score: number
  cache_size_bytes: number
}

export interface RoutingMetrics {
  total_decisions: number
  strategy_performance: Record<string, unknown>
  confidence_distribution: { high: number; medium: number; low: number }
  provider_usage: Record<string, number>
  cost_savings: {
    total_saved: number
    percent_saved: number
    intelligent_cost: number
    baseline_cost: number
    period_days: number
  }
  period_days: number
  timestamp: string
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

// ==========================================
// Arbitrage APIs (Sprint Dec 27)
// ==========================================

export interface ArbitrageOpportunity {
  id: string
  current_model: string
  current_provider: string
  alternative_model: string
  alternative_provider: string
  current_cost: number
  alternative_cost: number
  savings_percent: number
  quality_score: number
  required_capabilities: string[]
}

export interface ArbitrageAnalysisResponse {
  request_id: string
  current_model: string
  current_cost: number
  opportunities: ArbitrageOpportunity[]
  max_savings_percent: number
  recommendation: ArbitrageOpportunity | null
  analyzed_at: string
}

export interface ModelProfile {
  provider: string
  model_id: string
  capabilities: Record<string, string>
  input_price_per_million: number
  output_price_per_million: number
  context_window: number
  avg_latency_ms: number | null
}

export interface SavingsReport {
  total_potential_savings: number
  actual_savings: number
  opportunities_found: number
  opportunities_applied: number
  savings_rate: number
}

export async function analyzePromptArbitrage(
  prompt: string,
  currentModel: string,
  inputTokens?: number,
  outputTokens?: number
): Promise<ArbitrageAnalysisResponse> {
  return fetchAPI<ArbitrageAnalysisResponse>('/arbitrage/analyze', {
    method: 'POST',
    body: JSON.stringify({
      prompt,
      current_model: currentModel,
      input_tokens: inputTokens,
      output_tokens: outputTokens,
    }),
  })
}

export async function getArbitrageOpportunities(limit = 20): Promise<ArbitrageOpportunity[]> {
  return fetchAPI<ArbitrageOpportunity[]>(`/arbitrage/opportunities?limit=${limit}`)
}

export async function getArbitrageSavingsReport(days = 30): Promise<SavingsReport> {
  return fetchAPI<SavingsReport>(`/arbitrage/savings-report?days=${days}`)
}

export async function getAllModels(): Promise<ModelProfile[]> {
  return fetchAPI<ModelProfile[]>('/arbitrage/models')
}

export async function getModelAlternatives(modelId: string): Promise<ModelProfile[]> {
  return fetchAPI<ModelProfile[]>(`/arbitrage/models/${encodeURIComponent(modelId)}/alternatives`)
}

export async function getCheapestModel(capability: string, minLevel?: string): Promise<ModelProfile> {
  const params = minLevel ? `?min_level=${minLevel}` : ''
  return fetchAPI<ModelProfile>(`/arbitrage/cheapest/${capability}${params}`)
}

// ==========================================
// Forecasting APIs (Sprint Dec 27)
// ==========================================

export interface DailyForecast {
  date: string
  predicted_cost: number
  lower_bound: number
  upper_bound: number
}

export interface ForecastResponse {
  user_id: string
  generated_at: string
  horizon_days: number
  method_used: string
  data_points_used: number
  total_predicted_cost: number
  daily_forecasts: DailyForecast[]
  confidence_level: number
  model_quality_score: number | null
  provider: string | null
}

export interface CostAnomaly {
  id: string
  anomaly_date: string
  actual_cost: number
  expected_cost: number
  deviation_percent: number
  z_score: number
  severity: 'low' | 'medium' | 'high' | 'critical'
  acknowledged: boolean
  acknowledged_at: string | null
  notes: string | null
}

export interface AnomalyListResponse {
  anomalies: CostAnomaly[]
  total_count: number
  unacknowledged_count: number
}

export interface BudgetExhaustionResponse {
  user_id: string
  monthly_budget: number
  current_spend: number
  percentage_used: number
  daily_burn_rate: number
  projected_exhaustion_date: string | null
  days_until_exhaustion: number | null
  confidence_percentage: number
  warning_level: 'safe' | 'caution' | 'warning' | 'critical'
  recommendation: string
}

export interface ForecastSummaryResponse {
  aggregate: ForecastResponse
  by_provider: ForecastResponse[]
  budget_projection: BudgetExhaustionResponse
  recent_anomalies: CostAnomaly[]
}

export async function getForecast(
  horizonDays = 7,
  provider?: string,
  includeConfidence = true
): Promise<ForecastResponse> {
  const params = new URLSearchParams({
    horizon_days: horizonDays.toString(),
    include_confidence: includeConfidence.toString(),
  })
  if (provider) params.set('provider', provider)
  return fetchAPI<ForecastResponse>(`/forecasting/predict?${params}`)
}

export async function getForecastSummary(monthlyBudget: number): Promise<ForecastSummaryResponse> {
  return fetchAPI<ForecastSummaryResponse>(`/forecasting/summary?monthly_budget=${monthlyBudget}`)
}

export async function getAnomalies(
  lookbackDays = 30,
  sensitivity = 2.0
): Promise<AnomalyListResponse> {
  return fetchAPI<AnomalyListResponse>(
    `/forecasting/anomalies?lookback_days=${lookbackDays}&sensitivity=${sensitivity}`
  )
}

export async function acknowledgeAnomaly(
  anomalyId: string,
  notes?: string
): Promise<{ status: string; anomaly_id: string }> {
  return fetchAPI(`/forecasting/anomalies/${anomalyId}/acknowledge`, {
    method: 'POST',
    body: JSON.stringify({ notes }),
  })
}

export async function getBudgetExhaustion(monthlyBudget: number): Promise<BudgetExhaustionResponse> {
  return fetchAPI<BudgetExhaustionResponse>(`/forecasting/budget-exhaustion?monthly_budget=${monthlyBudget}`)
}

export async function getForecastingHealth(): Promise<{
  status: string
  service: string
  capabilities: {
    forecast_methods: string[]
    max_horizon_days: number
    anomaly_detection: boolean
    budget_projection: boolean
  }
}> {
  return fetchAPI('/forecasting/health')
}
