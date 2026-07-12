'use client'

import { useEffect, useState } from 'react'
import {
  getBillingSubscription,
  getBillingUsage,
  getBillingTiers,
  getInvoices,
  createCheckoutSession,
  createPortalSession,
  BillingSubscription,
  BillingUsage,
  BillingTierInfo,
  Invoice,
  BillingTier,
} from '@/lib/api'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  CreditCard,
  Zap,
  Check,
  ExternalLink,
  FileText,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Info,
  X,
} from 'lucide-react'

export default function BillingPage() {
  const [subscription, setSubscription] = useState<BillingSubscription | null>(null)
  const [usage, setUsage] = useState<BillingUsage | null>(null)
  const [tiers, setTiers] = useState<BillingTierInfo[]>([])
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [upgrading, setUpgrading] = useState<BillingTier | null>(null)
  const [openingPortal, setOpeningPortal] = useState(false)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [infoMessage, setInfoMessage] = useState<string | null>(null)

  // Handle success/canceled URL params from Stripe checkout redirect
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    if (params.get('success') === 'true') {
      setSuccessMessage('Subscription activated! Thank you for subscribing.')
      window.history.replaceState({}, '', '/billing')
    }
    if (params.get('canceled') === 'true') {
      setInfoMessage('Checkout was canceled. No charges were made.')
      window.history.replaceState({}, '', '/billing')
    }
  }, [])

  useEffect(() => {
    loadBillingData()
  }, [])

  async function loadBillingData() {
    try {
      setLoading(true)
      setError(null)
      const [subData, usageData, tiersData, invoicesData] = await Promise.all([
        getBillingSubscription().catch(() => null),
        getBillingUsage().catch(() => null),
        getBillingTiers().catch(() => []),
        getInvoices(10).catch(() => []),
      ])
      setSubscription(subData)
      setUsage(usageData)
      setTiers(tiersData)
      setInvoices(invoicesData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load billing data')
    } finally {
      setLoading(false)
    }
  }

  async function handleUpgrade(tier: BillingTier) {
    try {
      setUpgrading(tier)
      const { checkout_url } = await createCheckoutSession(tier)
      window.location.href = checkout_url
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create checkout session')
      setUpgrading(null)
    }
  }

  async function handleManageBilling() {
    try {
      setOpeningPortal(true)
      const { portal_url } = await createPortalSession()
      window.location.href = portal_url
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to open billing portal')
      setOpeningPortal(false)
    }
  }

  function formatTokens(tokens: number): string {
    if (tokens >= 1_000_000) return `${(tokens / 1_000_000).toFixed(1)}M`
    if (tokens >= 1_000) return `${(tokens / 1_000).toFixed(0)}K`
    return tokens.toLocaleString()
  }

  function formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  }

  function formatCurrency(amount: number): string {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount / 100)
  }

  function getTierBadgeVariant(
    tier: BillingTier
  ): 'default' | 'secondary' | 'destructive' | 'outline' {
    switch (tier) {
      case 'enterprise':
        return 'default'
      case 'business':
        return 'default'
      case 'pro':
        return 'secondary'
      default:
        return 'outline'
    }
  }

  function getStatusBadgeVariant(
    status: string
  ): 'default' | 'secondary' | 'destructive' | 'outline' {
    switch (status) {
      case 'active':
        return 'default'
      case 'trialing':
        return 'secondary'
      case 'past_due':
        return 'destructive'
      case 'canceled':
        return 'outline'
      default:
        return 'outline'
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // Default values for demo/free tier when no subscription exists
  const currentTier = subscription?.tier || 'free'
  const usagePercent = usage?.percentage_used || 0

  return (
    <div className="container mx-auto py-8 px-4 max-w-6xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold">Billing</h1>
        <p className="text-muted-foreground mt-1">Manage your subscription and billing details</p>
      </div>

      {/* Success message from checkout */}
      {successMessage && (
        <div className="mb-6 p-4 bg-green-500/10 border border-green-500/20 rounded-lg flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-green-500" />
            <span className="text-green-700 dark:text-green-400">{successMessage}</span>
          </div>
          <button
            onClick={() => setSuccessMessage(null)}
            className="text-green-500 hover:text-green-700"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Info message from canceled checkout */}
      {infoMessage && (
        <div className="mb-6 p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Info className="h-5 w-5 text-blue-500" />
            <span className="text-blue-700 dark:text-blue-400">{infoMessage}</span>
          </div>
          <button
            onClick={() => setInfoMessage(null)}
            className="text-blue-500 hover:text-blue-700"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {error && (
        <div className="mb-6 p-4 bg-destructive/10 border border-destructive/20 rounded-lg flex items-center gap-2">
          <AlertCircle className="h-5 w-5 text-destructive" />
          <span className="text-destructive">{error}</span>
        </div>
      )}

      {/* Current Plan & Usage */}
      <div className="grid gap-6 md:grid-cols-2 mb-8">
        {/* Current Plan Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <CreditCard className="h-5 w-5" />
              Current Plan
            </CardTitle>
            <CardDescription>Your subscription details</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Plan</span>
                <Badge variant={getTierBadgeVariant(currentTier)} className="capitalize">
                  {currentTier}
                </Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Status</span>
                <Badge variant={getStatusBadgeVariant(subscription?.status || 'active')}>
                  {subscription?.status || 'active'}
                </Badge>
              </div>
              {subscription?.current_period_end && (
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Renews</span>
                  <span>{formatDate(subscription.current_period_end)}</span>
                </div>
              )}
              {subscription?.cancel_at_period_end && (
                <div className="p-3 bg-yellow-500/10 border border-yellow-500/20 rounded-lg text-sm">
                  Your subscription will end at the current period
                </div>
              )}
              {subscription?.stripe_subscription_id && (
                <Button
                  variant="outline"
                  className="w-full mt-4"
                  onClick={handleManageBilling}
                  disabled={openingPortal}
                >
                  {openingPortal ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <ExternalLink className="h-4 w-4 mr-2" />
                  )}
                  Manage Billing
                </Button>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Usage Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Zap className="h-5 w-5" />
              Usage This Period
            </CardTitle>
            <CardDescription>{usage && `${usage.days_remaining} days remaining`}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-muted-foreground">Tokens Used</span>
                  <span>
                    {usage ? formatTokens(usage.tokens_used) : '0'} /{' '}
                    {usage ? formatTokens(usage.tokens_limit) : '10K'}
                  </span>
                </div>
                <Progress
                  value={usagePercent}
                  className={
                    usagePercent > 90 ? 'bg-red-200' : usagePercent > 75 ? 'bg-yellow-200' : ''
                  }
                />
              </div>
              <div className="text-center text-2xl font-bold">{usagePercent.toFixed(1)}%</div>
              {usagePercent > 80 && currentTier !== 'enterprise' && (
                <div className="p-3 bg-yellow-500/10 border border-yellow-500/20 rounded-lg text-sm">
                  Running low on tokens. Consider upgrading your plan.
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Pricing Tiers */}
      <div className="mb-8">
        <h2 className="text-xl font-semibold mb-4">Available Plans</h2>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {(tiers.length > 0 ? tiers : defaultTiers).map(tier => (
            <Card
              key={tier.tier}
              className={tier.tier === currentTier ? 'border-primary ring-2 ring-primary' : ''}
            >
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span className="capitalize">{tier.name}</span>
                  {tier.tier === currentTier && <Badge variant="default">Current</Badge>}
                </CardTitle>
                <CardDescription>
                  {tier.price_monthly === 0 ? (
                    <span className="text-2xl font-bold">Free</span>
                  ) : tier.tier === 'enterprise' ? (
                    <span className="text-2xl font-bold">Custom</span>
                  ) : (
                    <>
                      <span className="text-2xl font-bold">${tier.price_monthly}</span>
                      <span className="text-muted-foreground">/mo</span>
                    </>
                  )}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="text-sm text-muted-foreground">
                    {formatTokens(tier.tokens_per_month)} tokens/month
                  </div>
                  <ul className="space-y-2">
                    {tier.features.map((feature, i) => (
                      <li key={i} className="flex items-center gap-2 text-sm">
                        <Check className="h-4 w-4 text-green-500" />
                        {feature}
                      </li>
                    ))}
                  </ul>
                  {tier.tier !== currentTier && tier.tier !== 'free' && (
                    <Button
                      className="w-full"
                      variant={tier.tier === 'pro' ? 'default' : 'outline'}
                      onClick={() => handleUpgrade(tier.tier)}
                      disabled={upgrading !== null || tier.tier === 'enterprise'}
                    >
                      {upgrading === tier.tier ? (
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      ) : null}
                      {tier.tier === 'enterprise' ? 'Contact Sales' : 'Upgrade'}
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Invoice History */}
      <div>
        <h2 className="text-xl font-semibold mb-4">Invoice History</h2>
        <Card>
          <CardContent className="p-0">
            {invoices.length === 0 ? (
              <div className="p-8 text-center text-muted-foreground">
                <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>No invoices yet</p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Period</TableHead>
                    <TableHead>Amount</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Invoice</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {invoices.map(invoice => (
                    <TableRow key={invoice.id}>
                      <TableCell>{formatDate(invoice.created_at)}</TableCell>
                      <TableCell>
                        {formatDate(invoice.period_start)} - {formatDate(invoice.period_end)}
                      </TableCell>
                      <TableCell>{formatCurrency(invoice.amount_paid)}</TableCell>
                      <TableCell>
                        <Badge
                          variant={invoice.status === 'paid' ? 'default' : 'outline'}
                          className="capitalize"
                        >
                          {invoice.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        {invoice.invoice_pdf && (
                          <Button variant="ghost" size="sm" asChild>
                            <a href={invoice.invoice_pdf} target="_blank" rel="noopener noreferrer">
                              <FileText className="h-4 w-4 mr-1" />
                              PDF
                            </a>
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

// Default tiers shown when API isn't available
const defaultTiers: BillingTierInfo[] = [
  {
    tier: 'free',
    name: 'Free',
    price_monthly: 0,
    tokens_per_month: 10_000,
    features: ['Basic routing', 'Community support', 'Dashboard access'],
    stripe_price_id: null,
  },
  {
    tier: 'pro',
    name: 'Pro',
    price_monthly: 49,
    tokens_per_month: 1_000_000,
    features: ['A/B testing', 'Priority routing', 'Email support', 'API access'],
    stripe_price_id: null,
  },
  {
    tier: 'business',
    name: 'Business',
    price_monthly: 299,
    tokens_per_month: 10_000_000,
    features: ['All Pro features', 'Custom models', 'Slack support', 'SLA 99.9%'],
    stripe_price_id: null,
  },
  {
    tier: 'enterprise',
    name: 'Enterprise',
    price_monthly: 0,
    tokens_per_month: 999_999_999,
    features: ['Unlimited tokens', 'Dedicated support', 'Custom integrations', 'On-premise option'],
    stripe_price_id: null,
  },
]
