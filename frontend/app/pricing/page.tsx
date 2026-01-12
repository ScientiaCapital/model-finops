'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Check, Zap, Shield, Sparkles, Loader2 } from 'lucide-react'
import { PLANS, PlanId, formatPrice } from '@/lib/stripe/plans'
import { createCheckoutSession, BillingTier } from '@/lib/api'
import { cn } from '@/lib/utils'

type BillingInterval = 'monthly' | 'annual'

export default function PricingPage() {
  const router = useRouter()
  const [interval, setInterval] = useState<BillingInterval>('monthly')
  const [loading, setLoading] = useState<PlanId | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Display order for paid plans (excluding free for pricing page)
  const displayPlans: PlanId[] = ['starter', 'pro', 'enterprise']

  const handleSelectPlan = async (planId: PlanId) => {
    if (planId === 'free') {
      router.push('/signup')
      return
    }

    if (planId === 'enterprise') {
      // Enterprise customers should contact sales
      window.location.href = 'mailto:sales@modelfinops.com?subject=Enterprise%20Inquiry'
      return
    }

    try {
      setLoading(planId)
      setError(null)
      // Map plan ID to billing tier for API
      const tierMap: Record<PlanId, BillingTier> = {
        free: 'free',
        starter: 'pro', // Starter plan maps to 'pro' tier in backend
        pro: 'business', // Pro plan maps to 'business' tier in backend
        enterprise: 'enterprise',
      }
      const { checkout_url } = await createCheckoutSession(tierMap[planId])
      window.location.href = checkout_url
    } catch (err) {
      console.error('Checkout error:', err)
      setError(err instanceof Error ? err.message : 'Failed to start checkout. Please try again.')
      setLoading(null)
    }
  }

  const getPlanIcon = (planId: PlanId) => {
    switch (planId) {
      case 'starter':
        return <Zap className="h-5 w-5" />
      case 'pro':
        return <Sparkles className="h-5 w-5" />
      case 'enterprise':
        return <Shield className="h-5 w-5" />
      default:
        return null
    }
  }

  const getPrice = (planId: PlanId): number => {
    const plan = PLANS[planId]
    if (interval === 'annual') {
      return Math.round(plan.priceAnnual / 12) // Monthly equivalent
    }
    return plan.priceMonthly
  }

  const getSavingsPercent = (planId: PlanId): number => {
    const plan = PLANS[planId]
    if (plan.priceMonthly === 0) return 0
    const monthlyTotal = plan.priceMonthly * 12
    const annualTotal = plan.priceAnnual
    return Math.round(((monthlyTotal - annualTotal) / monthlyTotal) * 100)
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-background to-muted/30">
      <div className="container mx-auto px-4 py-16 max-w-6xl">
        {/* Header */}
        <div className="text-center mb-12">
          <Badge variant="secondary" className="mb-4">
            Simple, transparent pricing
          </Badge>
          <h1 className="text-4xl md:text-5xl font-bold tracking-tight mb-4">
            Optimize your AI costs
          </h1>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
            Choose the plan that fits your needs. Save up to 60% on AI API costs with
            intelligent routing and semantic caching.
          </p>
        </div>

        {/* Billing Toggle */}
        <div className="flex items-center justify-center gap-4 mb-12">
          <span className={cn(
            "text-sm font-medium transition-colors",
            interval === 'monthly' ? 'text-foreground' : 'text-muted-foreground'
          )}>
            Monthly
          </span>
          <button
            onClick={() => setInterval(interval === 'monthly' ? 'annual' : 'monthly')}
            className={cn(
              "relative inline-flex h-6 w-11 items-center rounded-full transition-colors",
              interval === 'annual' ? 'bg-primary' : 'bg-muted'
            )}
          >
            <span
              className={cn(
                "inline-block h-4 w-4 transform rounded-full bg-white transition-transform",
                interval === 'annual' ? 'translate-x-6' : 'translate-x-1'
              )}
            />
          </button>
          <span className={cn(
            "text-sm font-medium transition-colors",
            interval === 'annual' ? 'text-foreground' : 'text-muted-foreground'
          )}>
            Annual
          </span>
          {interval === 'annual' && (
            <Badge variant="default" className="bg-green-500 hover:bg-green-600">
              Save 20%
            </Badge>
          )}
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-8 p-4 bg-destructive/10 border border-destructive/20 rounded-lg text-center text-destructive">
            {error}
          </div>
        )}

        {/* Pricing Cards */}
        <div className="grid gap-6 md:grid-cols-3">
          {displayPlans.map((planId) => {
            const plan = PLANS[planId]
            const isPopular = plan.popular
            const price = getPrice(planId)
            const savings = getSavingsPercent(planId)

            return (
              <Card
                key={planId}
                className={cn(
                  "relative flex flex-col transition-all duration-200",
                  isPopular
                    ? 'border-primary shadow-lg scale-[1.02] md:scale-105'
                    : 'hover:border-primary/50 hover:shadow-md'
                )}
              >
                {isPopular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <Badge className="bg-primary text-primary-foreground shadow-sm">
                      Most Popular
                    </Badge>
                  </div>
                )}

                <CardHeader className="text-center pb-4">
                  <div className="flex items-center justify-center gap-2 mb-2">
                    <div className={cn(
                      "p-2 rounded-lg",
                      isPopular ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground'
                    )}>
                      {getPlanIcon(planId)}
                    </div>
                  </div>
                  <CardTitle className="text-2xl">{plan.name}</CardTitle>
                  <CardDescription className="min-h-[40px]">
                    {plan.description}
                  </CardDescription>
                </CardHeader>

                <CardContent className="flex-1 space-y-6">
                  {/* Price */}
                  <div className="text-center">
                    {planId === 'enterprise' ? (
                      <>
                        <div className="text-4xl font-bold">{formatPrice(price)}</div>
                        <div className="text-muted-foreground text-sm">per month</div>
                      </>
                    ) : (
                      <>
                        <div className="text-4xl font-bold">{formatPrice(price)}</div>
                        <div className="text-muted-foreground text-sm">
                          per month{interval === 'annual' && ', billed annually'}
                        </div>
                        {interval === 'annual' && savings > 0 && (
                          <div className="text-green-600 text-sm font-medium mt-1">
                            Save {savings}% vs monthly
                          </div>
                        )}
                      </>
                    )}
                  </div>

                  {/* Requests */}
                  <div className="text-center p-3 bg-muted/50 rounded-lg">
                    <div className="font-semibold">
                      {plan.apiCallsMonthly === -1
                        ? 'Unlimited'
                        : plan.apiCallsMonthly.toLocaleString()
                      }
                    </div>
                    <div className="text-sm text-muted-foreground">requests/month</div>
                  </div>

                  {/* Features */}
                  <ul className="space-y-3">
                    {plan.features.map((feature, idx) => (
                      <li key={idx} className="flex items-start gap-3">
                        <Check className="h-5 w-5 text-green-500 flex-shrink-0 mt-0.5" />
                        <span className="text-sm">{feature}</span>
                      </li>
                    ))}
                  </ul>
                </CardContent>

                <CardFooter className="pt-4">
                  <Button
                    className="w-full"
                    size="lg"
                    variant={isPopular ? 'default' : 'outline'}
                    onClick={() => handleSelectPlan(planId)}
                    disabled={loading !== null}
                  >
                    {loading === planId ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Processing...
                      </>
                    ) : planId === 'enterprise' ? (
                      'Contact Sales'
                    ) : (
                      'Get Started'
                    )}
                  </Button>
                </CardFooter>
              </Card>
            )
          })}
        </div>

        {/* Bottom CTA */}
        <div className="mt-16 text-center">
          <p className="text-muted-foreground mb-4">
            All plans include a 14-day free trial. No credit card required to start.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-6 text-sm text-muted-foreground">
            <div className="flex items-center gap-2">
              <Check className="h-4 w-4 text-green-500" />
              <span>Cancel anytime</span>
            </div>
            <div className="flex items-center gap-2">
              <Check className="h-4 w-4 text-green-500" />
              <span>Secure payments via Stripe</span>
            </div>
            <div className="flex items-center gap-2">
              <Check className="h-4 w-4 text-green-500" />
              <span>24/7 customer support</span>
            </div>
          </div>
        </div>

        {/* FAQ Section */}
        <div className="mt-20">
          <h2 className="text-2xl font-bold text-center mb-8">Frequently Asked Questions</h2>
          <div className="grid gap-6 md:grid-cols-2 max-w-4xl mx-auto">
            <div className="space-y-2">
              <h3 className="font-semibold">What counts as a request?</h3>
              <p className="text-sm text-muted-foreground">
                Each API call to route or optimize an AI prompt counts as one request.
                Cached responses don't count against your limit.
              </p>
            </div>
            <div className="space-y-2">
              <h3 className="font-semibold">What is semantic caching?</h3>
              <p className="text-sm text-muted-foreground">
                Semantic caching identifies similar prompts and returns cached responses,
                reducing costs by up to 3x for repeated queries.
              </p>
            </div>
            <div className="space-y-2">
              <h3 className="font-semibold">Can I change plans later?</h3>
              <p className="text-sm text-muted-foreground">
                Yes! You can upgrade or downgrade at any time. Changes take effect
                immediately, and billing is prorated.
              </p>
            </div>
            <div className="space-y-2">
              <h3 className="font-semibold">What AI providers are supported?</h3>
              <p className="text-sm text-muted-foreground">
                We support Anthropic Claude, Google Gemini, Cerebras, and OpenRouter
                for multi-model routing (no OpenAI).
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
