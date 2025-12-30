/**
 * ModelFinOps Subscription Plans
 *
 * AI Cost Optimization platform tiers:
 * - Starter: $49/mo - Basic cost tracking
 * - Pro: $149/mo - Advanced optimization
 * - Enterprise: $399/mo - Full platform access
 */

export type PlanId = 'free' | 'starter' | 'pro' | 'enterprise';

export interface Plan {
  id: PlanId;
  name: string;
  description: string;
  priceMonthly: number; // cents
  priceAnnual: number; // cents
  features: string[];
  apiCallsMonthly: number;
  popular?: boolean;
  contactSales?: boolean;
}

export const PLANS: Record<PlanId, Plan> = {
  free: {
    id: 'free',
    name: 'Free',
    description: 'Get started with basic features',
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
    description: 'Essential cost tracking',
    priceMonthly: 4900, // $49
    priceAnnual: 49000, // $490 (2 months free)
    apiCallsMonthly: 5000,
    features: [
      '5,000 API calls/month',
      'Multi-provider cost tracking',
      'Basic cost optimization',
      'Usage alerts',
      'CSV export',
      'Email support',
    ],
  },
  pro: {
    id: 'pro',
    name: 'Pro',
    description: 'Advanced cost optimization',
    priceMonthly: 14900, // $149
    priceAnnual: 149000, // $1,490 (2 months free)
    apiCallsMonthly: 50000,
    popular: true,
    features: [
      '50,000 API calls/month',
      'Everything in Starter',
      'AI-powered routing',
      'Semantic caching',
      'Real-time analytics',
      'Team management (5 seats)',
      'API access',
      'Priority support',
    ],
  },
  enterprise: {
    id: 'enterprise',
    name: 'Enterprise',
    description: 'Full platform access',
    priceMonthly: 39900, // $399
    priceAnnual: 399000, // $3,990 (2 months free)
    apiCallsMonthly: 500000,
    features: [
      '500,000 API calls/month',
      'Everything in Pro',
      'Unlimited team seats',
      'Custom integrations',
      'SLA guarantees',
      'Dedicated support',
      'On-premise option',
      'Custom model routing',
    ],
  },
};

// Stripe Price IDs from environment
export const STRIPE_PRICES = {
  starter_monthly: process.env.STRIPE_PRICE_STARTER_MONTHLY || '',
  starter_annual: process.env.STRIPE_PRICE_STARTER_ANNUAL || '',
  pro_monthly: process.env.STRIPE_PRICE_PRO_MONTHLY || '',
  pro_annual: process.env.STRIPE_PRICE_PRO_ANNUAL || '',
  enterprise_monthly: process.env.STRIPE_PRICE_ENTERPRISE_MONTHLY || '',
  enterprise_annual: process.env.STRIPE_PRICE_ENTERPRISE_ANNUAL || '',
};

export function getPlan(planId: PlanId): Plan {
  return PLANS[planId] || PLANS.free;
}

export function getPlanMetadata(planId: PlanId): Record<string, string> {
  const plan = getPlan(planId);
  return {
    plan_id: planId,
    plan_name: plan.name,
    site: 'modelfinops',
  };
}

export function formatPrice(cents: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(cents / 100);
}

export function getMonthlyPrice(planId: PlanId): number {
  return getPlan(planId).priceMonthly;
}

export function getAnnualPrice(planId: PlanId): number {
  return getPlan(planId).priceAnnual;
}
