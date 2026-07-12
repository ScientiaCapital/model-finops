/**
 * ModelFinOps Subscription Plans
 *
 * AI Cost Optimization platform tiers:
 * - Starter: $49/mo - Basic routing, 10K requests
 * - Pro: $149/mo - Semantic caching, 100K requests
 * - Enterprise: $399/mo - Custom models, unlimited requests
 */

export type PlanId = 'free' | 'starter' | 'pro' | 'enterprise'

export interface Plan {
  id: PlanId
  name: string
  description: string
  priceMonthly: number // cents
  priceAnnual: number // cents
  features: string[]
  apiCallsMonthly: number
  popular?: boolean
  contactSales?: boolean
}

export const PLANS: Record<PlanId, Plan> = {
  free: {
    id: 'free',
    name: 'Free',
    description: 'Try before you buy',
    priceMonthly: 0,
    priceAnnual: 0,
    apiCallsMonthly: 100,
    features: [
      'Basic cost dashboard',
      '100 API calls/month',
      'Single provider support',
      'Community support',
    ],
  },
  starter: {
    id: 'starter',
    name: 'Starter',
    description: 'Perfect for individuals and small projects',
    priceMonthly: 4900, // $49
    priceAnnual: 47000, // $470 (~20% off)
    apiCallsMonthly: 10000,
    features: [
      '10,000 requests/month',
      'Basic intelligent routing',
      'Multi-provider cost tracking',
      'Usage analytics dashboard',
      'Email alerts & notifications',
      'CSV data export',
      'Email support',
    ],
  },
  pro: {
    id: 'pro',
    name: 'Pro',
    description: 'Best for growing teams and businesses',
    priceMonthly: 14900, // $149
    priceAnnual: 143000, // $1,430 (~20% off)
    apiCallsMonthly: 100000,
    popular: true,
    features: [
      '100,000 requests/month',
      'Everything in Starter',
      'Semantic caching (3x cost savings)',
      'AI-powered routing optimization',
      'Real-time analytics & forecasting',
      'Team management (10 seats)',
      'Full API access',
      'Priority support',
    ],
  },
  enterprise: {
    id: 'enterprise',
    name: 'Enterprise',
    description: 'For organizations needing full control',
    priceMonthly: 39900, // $399
    priceAnnual: 383000, // $3,830 (~20% off)
    apiCallsMonthly: -1, // unlimited
    features: [
      'Unlimited requests',
      'Everything in Pro',
      'Custom model routing rules',
      'Unlimited team seats',
      'Advanced security & compliance',
      'Custom integrations & webhooks',
      'SLA guarantees (99.9% uptime)',
      'Dedicated account manager',
      'On-premise deployment option',
    ],
  },
}

// Stripe Price IDs from environment
export const STRIPE_PRICES = {
  starter_monthly: process.env.STRIPE_PRICE_STARTER_MONTHLY || '',
  starter_annual: process.env.STRIPE_PRICE_STARTER_ANNUAL || '',
  pro_monthly: process.env.STRIPE_PRICE_PRO_MONTHLY || '',
  pro_annual: process.env.STRIPE_PRICE_PRO_ANNUAL || '',
  enterprise_monthly: process.env.STRIPE_PRICE_ENTERPRISE_MONTHLY || '',
  enterprise_annual: process.env.STRIPE_PRICE_ENTERPRISE_ANNUAL || '',
}

export function getPlan(planId: PlanId): Plan {
  return PLANS[planId] || PLANS.free
}

export function getPlanMetadata(planId: PlanId): Record<string, string> {
  const plan = getPlan(planId)
  return {
    plan_id: planId,
    plan_name: plan.name,
    site: 'modelfinops',
  }
}

export function formatPrice(cents: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(cents / 100)
}

export function getMonthlyPrice(planId: PlanId): number {
  return getPlan(planId).priceMonthly
}

export function getAnnualPrice(planId: PlanId): number {
  return getPlan(planId).priceAnnual
}
