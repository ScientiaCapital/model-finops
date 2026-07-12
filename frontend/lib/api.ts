const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface Stats {
  overall: {
    total_requests: number
    total_cost: number
    total_tokens_in: number
    total_tokens_out: number
    avg_cost_per_request: number
  }
  by_provider: Array<{
    provider: string
    request_count: number
    total_cost: number
    avg_cost: number
  }>
  by_complexity: Array<{
    complexity: string
    request_count: number
    total_cost: number
    avg_cost: number
  }>
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

export async function getCheapestModel(
  capability: string,
  minLevel?: string
): Promise<ModelProfile> {
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

export async function getBudgetExhaustion(
  monthlyBudget: number
): Promise<BudgetExhaustionResponse> {
  return fetchAPI<BudgetExhaustionResponse>(
    `/forecasting/budget-exhaustion?monthly_budget=${monthlyBudget}`
  )
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

// ==========================================
// Provider Status APIs (API Setup Wizard)
// ==========================================

export type ProviderStatus = 'connected' | 'invalid' | 'not_configured' | 'error'

export interface ProviderInfo {
  name: string
  display_name: string
  status: ProviderStatus
  message: string
  category: string
  setup_url: string
  models_available: number | null
  env_vars: string[]
}

export interface ProvidersStatusResponse {
  providers: ProviderInfo[]
  summary: {
    connected: number
    configured: number
    not_configured: number
    total: number
  }
  setup_progress: number
}

export interface SetupLink {
  provider: string
  display_name: string
  category: string
  setup_url: string
  env_vars: string[]
  instructions: string
}

export interface ValidateKeyRequest {
  provider: string
  api_key: string
}

export interface ValidateKeyResponse {
  valid: boolean
  message: string
  models_available: number | null
}

export interface ProviderCategories {
  categories: string[]
  providers_by_category: Record<string, string[]>
}

export async function getProvidersStatus(): Promise<ProvidersStatusResponse> {
  return fetchAPI<ProvidersStatusResponse>('/api/status/providers')
}

export async function getProviderStatus(provider: string): Promise<ProviderInfo> {
  return fetchAPI<ProviderInfo>(`/api/status/providers/${provider}`)
}

export async function validateApiKey(request: ValidateKeyRequest): Promise<ValidateKeyResponse> {
  return fetchAPI<ValidateKeyResponse>('/api/status/validate', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

export async function getSetupLinks(category?: string): Promise<SetupLink[]> {
  const params = category ? `?category=${encodeURIComponent(category)}` : ''
  return fetchAPI<SetupLink[]>(`/api/status/setup-links${params}`)
}

export async function getProviderCategories(): Promise<ProviderCategories> {
  return fetchAPI<ProviderCategories>('/api/status/categories')
}

// ==========================================
// Enterprise APIs
// ==========================================

export interface Organization {
  id: string
  name: string
  domain: string | null
  plan: string
  settings: Record<string, unknown>
  created_at: string
  updated_at: string | null
}

export interface Employee {
  id: string
  org_id: string
  dept_id: string | null
  email: string
  name: string | null
  role: string
  personal_email: string | null
  personal_linked_at: string | null
  personal_consent: boolean
  is_active: boolean
  created_at: string
  updated_at: string | null
}

export interface EmployeeWithUsage extends Employee {
  usage?: EmployeeSpendSummary
  department_name?: string
}

export interface EmployeeSpendSummary {
  employee_name: string | null
  email: string
  work_spend_usd: number
  personal_spend_usd: number
  total_spend_usd: number
}

export interface DepartmentSpendSummary {
  department_name: string
  total_spend_usd: number
  budget_usd: number | null
  budget_percent: number
  employee_count: number
  top_provider: string | null
}

export interface ComplianceAlert {
  id: string
  org_id: string
  employee_id: string | null
  dept_id: string | null
  alert_type: string
  severity: string
  provider: string | null
  model: string | null
  title: string
  message: string
  details: Record<string, unknown>
  resolved: boolean
  resolved_by: string | null
  resolved_at: string | null
  resolution_notes: string | null
  created_at: string
}

export interface LinkPersonalAccountRequest {
  personal_email: string
  consent_given: boolean
}

export async function getOrganizations(): Promise<Organization[]> {
  // Note: In production this would list orgs the user has access to
  // For now, we'll implement a single org detail endpoint
  return fetchAPI<Organization[]>('/api/enterprise/organizations')
}

export async function getOrganization(orgId: string): Promise<Organization> {
  return fetchAPI<Organization>(`/api/enterprise/organizations/${orgId}`)
}

export async function getEmployees(orgId: string): Promise<Employee[]> {
  return fetchAPI<Employee[]>(`/api/enterprise/organizations/${orgId}/employees`)
}

export async function getEmployeeUsage(employeeId: string): Promise<EmployeeSpendSummary> {
  return fetchAPI<EmployeeSpendSummary>(`/api/enterprise/employees/${employeeId}/usage`)
}

export async function getDepartmentSpend(_orgId: string): Promise<DepartmentSpendSummary[]> {
  const response = await fetchAPI<{ departments: DepartmentSpendSummary[] }>(
    `/api/enterprise/org/spend-by-department`
  )
  return response.departments
}

export async function getComplianceAlerts(
  orgId: string,
  options?: { resolved?: boolean; alert_type?: string; limit?: number }
): Promise<ComplianceAlert[]> {
  const params = new URLSearchParams()
  if (options?.resolved !== undefined) params.set('resolved', String(options.resolved))
  if (options?.alert_type) params.set('alert_type', options.alert_type)
  if (options?.limit) params.set('limit', String(options.limit))

  const response = await fetchAPI<{ alerts: ComplianceAlert[] }>(
    `/api/enterprise/compliance/alerts?${params}`
  )
  return response.alerts
}

export async function linkPersonalAccount(
  employeeId: string,
  data: LinkPersonalAccountRequest
): Promise<Employee> {
  return fetchAPI<Employee>(`/api/enterprise/employees/me/link-personal`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function resolveComplianceAlert(
  alertId: string,
  notes?: string
): Promise<ComplianceAlert> {
  return fetchAPI<ComplianceAlert>(`/api/enterprise/compliance/alerts/${alertId}/resolve`, {
    method: 'POST',
    body: JSON.stringify({ resolution_notes: notes }),
  })
}

// ==========================================
// Subscription Tracking APIs
// ==========================================

export type SubscriptionStatus = 'active' | 'trial' | 'cancelled' | 'paused' | 'past_due'
export type SubscriptionCategory =
  | 'LLM Providers'
  | 'Voice AI (TTS)'
  | 'Voice AI (STT)'
  | 'Infrastructure'
  | 'AI Media'
  | 'Observability'
  | 'Billing'
  | 'Other'

export interface Subscription {
  id: string
  user_id: string
  service_name: string
  service_provider: string | null
  category: SubscriptionCategory
  monthly_cost: number
  billing_day: number | null
  next_billing_date: string | null
  status: SubscriptionStatus
  alert_enabled: boolean
  alert_days_before: number
  created_at: string
  updated_at: string
}

export interface CreateSubscriptionData {
  service_name: string
  service_provider?: string
  category: SubscriptionCategory
  monthly_cost: number
  billing_day?: number
  status?: SubscriptionStatus
  alert_enabled?: boolean
  alert_days_before?: number
}

export interface UpdateSubscriptionData {
  service_name?: string
  service_provider?: string
  category?: SubscriptionCategory
  monthly_cost?: number
  billing_day?: number
  next_billing_date?: string
  status?: SubscriptionStatus
  alert_enabled?: boolean
  alert_days_before?: number
}

export interface SpendSummary {
  total_monthly_cost: number
  total_yearly_cost: number
  active_subscriptions: number
  by_category: Array<{
    category: SubscriptionCategory
    count: number
    monthly_cost: number
  }>
  by_status: Array<{
    status: SubscriptionStatus
    count: number
    monthly_cost: number
  }>
}

export interface UpcomingAlert {
  subscription_id: string
  service_name: string
  monthly_cost: number
  next_billing_date: string
  days_until_billing: number
  urgency: 'low' | 'medium' | 'high'
}

export async function getSubscriptions(): Promise<Subscription[]> {
  return fetchAPI<Subscription[]>('/subscriptions')
}

export async function getSubscription(id: string): Promise<Subscription> {
  return fetchAPI<Subscription>(`/subscriptions/${id}`)
}

export async function createSubscription(data: CreateSubscriptionData): Promise<Subscription> {
  return fetchAPI<Subscription>('/subscriptions', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateSubscription(
  id: string,
  data: UpdateSubscriptionData
): Promise<Subscription> {
  return fetchAPI<Subscription>(`/subscriptions/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function deleteSubscription(id: string): Promise<void> {
  await fetchAPI(`/subscriptions/${id}`, {
    method: 'DELETE',
  })
}

export async function getSpendSummary(): Promise<SpendSummary> {
  return fetchAPI<SpendSummary>('/subscriptions/summary')
}

export async function getUpcomingAlerts(days = 7): Promise<UpcomingAlert[]> {
  return fetchAPI<UpcomingAlert[]>(`/subscriptions/upcoming-alerts?days=${days}`)
}

// ==========================================
// Billing APIs (Stripe Integration)
// ==========================================

export type BillingTier = 'free' | 'pro' | 'business' | 'enterprise'

export interface BillingSubscription {
  id: string
  user_id: string
  stripe_customer_id: string | null
  stripe_subscription_id: string | null
  tier: BillingTier
  status: 'active' | 'past_due' | 'canceled' | 'incomplete' | 'trialing'
  current_period_start: string | null
  current_period_end: string | null
  cancel_at_period_end: boolean
  created_at: string
  updated_at: string
}

export interface BillingUsage {
  user_id: string
  tier: BillingTier
  tokens_used: number
  tokens_limit: number
  percentage_used: number
  period_start: string
  period_end: string
  days_remaining: number
}

export interface BillingQuota {
  allowed: boolean
  tier: BillingTier
  tokens_used: number
  tokens_limit: number
  percentage_used: number
  upgrade_url: string | null
}

export interface BillingTierInfo {
  tier: BillingTier
  name: string
  price_monthly: number
  tokens_per_month: number
  features: string[]
  stripe_price_id: string | null
}

export interface Invoice {
  id: string
  stripe_invoice_id: string
  amount_due: number
  amount_paid: number
  currency: string
  status: 'draft' | 'open' | 'paid' | 'void' | 'uncollectible'
  invoice_pdf: string | null
  hosted_invoice_url: string | null
  period_start: string
  period_end: string
  created_at: string
}

export interface CheckoutSession {
  checkout_url: string
  session_id: string
}

export interface PortalSession {
  portal_url: string
}

export async function getBillingSubscription(): Promise<BillingSubscription> {
  return fetchAPI<BillingSubscription>('/billing/subscription')
}

export async function getBillingUsage(): Promise<BillingUsage> {
  return fetchAPI<BillingUsage>('/billing/usage')
}

export async function checkBillingQuota(): Promise<BillingQuota> {
  return fetchAPI<BillingQuota>('/billing/quota/check')
}

export async function getBillingTiers(): Promise<BillingTierInfo[]> {
  return fetchAPI<BillingTierInfo[]>('/billing/tiers')
}

export async function getInvoices(limit = 10): Promise<Invoice[]> {
  return fetchAPI<Invoice[]>(`/billing/invoices?limit=${limit}`)
}

export interface CreateCheckoutRequest {
  price_id: string
  success_url: string
  cancel_url: string
  trial_days?: number
}

export async function createCheckoutSession(tier: BillingTier): Promise<CheckoutSession> {
  // Get base URL for redirects
  const baseUrl = typeof window !== 'undefined' ? window.location.origin : ''

  // Map tier to Stripe price ID (these should match backend tier_limits table)
  const priceIdMap: Record<BillingTier, string> = {
    free: '',
    pro: process.env.NEXT_PUBLIC_STRIPE_PRICE_PRO || 'price_starter_monthly',
    business: process.env.NEXT_PUBLIC_STRIPE_PRICE_BUSINESS || 'price_pro_monthly',
    enterprise: process.env.NEXT_PUBLIC_STRIPE_PRICE_ENTERPRISE || 'price_enterprise_monthly',
  }

  const priceId = priceIdMap[tier]
  if (!priceId) {
    throw new Error('Invalid tier or free tier selected')
  }

  return fetchAPI<CheckoutSession>('/billing/checkout', {
    method: 'POST',
    body: JSON.stringify({
      price_id: priceId,
      success_url: `${baseUrl}/billing?success=true`,
      cancel_url: `${baseUrl}/pricing?canceled=true`,
    }),
  })
}

export async function createPortalSession(): Promise<PortalSession> {
  return fetchAPI<PortalSession>('/billing/portal', {
    method: 'POST',
  })
}
