'use client'

import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'
import {
  Calendar,
  DollarSign,
  AlertTriangle,
  Plus,
  Trash2,
  Edit2,
  RefreshCw,
  Loader2,
  Cpu,
  Mic,
  Database,
  Activity,
  CreditCard,
  Video,
  Package,
  Check,
  X,
} from 'lucide-react'
import {
  getSubscriptions,
  getSpendSummary,
  getUpcomingAlerts,
  createSubscription,
  deleteSubscription,
  updateSubscription,
  type Subscription,
  type SpendSummary,
  type UpcomingAlert,
  type CreateSubscriptionData,
  type UpdateSubscriptionData,
  type SubscriptionStatus,
  type SubscriptionCategory,
} from '@/lib/api'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

interface SubscriptionTrackerProps {
  className?: string
}

const categoryIcons: Record<SubscriptionCategory, React.ReactNode> = {
  'LLM Providers': <Cpu className="h-4 w-4" />,
  'Voice AI (TTS)': <Mic className="h-4 w-4" />,
  'Voice AI (STT)': <Mic className="h-4 w-4" />,
  Infrastructure: <Database className="h-4 w-4" />,
  'AI Media': <Video className="h-4 w-4" />,
  Observability: <Activity className="h-4 w-4" />,
  Billing: <CreditCard className="h-4 w-4" />,
  Other: <Package className="h-4 w-4" />,
}

const statusConfig: Record<SubscriptionStatus, { label: string; variant: 'default' | 'secondary' | 'destructive' | 'outline'; color: string }> = {
  active: { label: 'Active', variant: 'default', color: 'text-green-500' },
  trial: { label: 'Trial', variant: 'secondary', color: 'text-blue-500' },
  cancelled: { label: 'Cancelled', variant: 'destructive', color: 'text-red-500' },
  paused: { label: 'Paused', variant: 'outline', color: 'text-yellow-500' },
  past_due: { label: 'Past Due', variant: 'destructive', color: 'text-orange-500' },
}

const categoryOptions: SubscriptionCategory[] = [
  'LLM Providers',
  'Voice AI (TTS)',
  'Voice AI (STT)',
  'Infrastructure',
  'AI Media',
  'Observability',
  'Billing',
  'Other',
]

function getDaysUntilBilling(nextBillingDate: string | null): number | null {
  if (!nextBillingDate) return null
  const today = new Date()
  const billing = new Date(nextBillingDate)
  const diff = Math.ceil((billing.getTime() - today.getTime()) / (1000 * 60 * 60 * 24))
  return diff
}

function getBillingUrgency(daysUntil: number | null): 'low' | 'medium' | 'high' {
  if (daysUntil === null) return 'low'
  if (daysUntil <= 3) return 'high'
  if (daysUntil <= 7) return 'medium'
  return 'low'
}

interface SubscriptionCardProps {
  subscription: Subscription
  onEdit: () => void
  onDelete: () => void
}

function SubscriptionCard({ subscription, onEdit, onDelete }: SubscriptionCardProps) {
  const statusInfo = statusConfig[subscription.status]
  const daysUntil = getDaysUntilBilling(subscription.next_billing_date)
  const urgency = getBillingUrgency(daysUntil)

  const urgencyColors = {
    low: 'text-green-500 border-green-500/20',
    medium: 'text-yellow-500 border-yellow-500/20',
    high: 'text-red-500 border-red-500/20',
  }

  return (
    <div
      className={cn(
        'flex items-center justify-between p-4 rounded-lg border transition-colors',
        urgencyColors[urgency]
      )}
    >
      <div className="flex items-start gap-3 flex-1">
        <div className={cn('mt-1', statusInfo.color)}>
          {categoryIcons[subscription.category]}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <p className="font-medium text-sm truncate">{subscription.service_name}</p>
            <Badge variant={statusInfo.variant} className="text-xs">
              {statusInfo.label}
            </Badge>
          </div>
          {subscription.service_provider && (
            <p className="text-xs text-muted-foreground mb-1">{subscription.service_provider}</p>
          )}
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <DollarSign className="h-3 w-3" />
              ${subscription.monthly_cost.toFixed(2)}/mo
            </span>
            {subscription.next_billing_date && (
              <span className="flex items-center gap-1">
                <Calendar className="h-3 w-3" />
                {new Date(subscription.next_billing_date).toLocaleDateString('en-US', {
                  month: 'short',
                  day: 'numeric',
                })}
                {daysUntil !== null && daysUntil >= 0 && (
                  <span className={cn('ml-1 font-medium', urgencyColors[urgency])}>
                    ({daysUntil}d)
                  </span>
                )}
              </span>
            )}
          </div>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onEdit}>
          <Edit2 className="h-3 w-3" />
        </Button>
        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onDelete}>
          <Trash2 className="h-3 w-3 text-red-500" />
        </Button>
      </div>
    </div>
  )
}

interface AddSubscriptionFormProps {
  onSubmit: (data: CreateSubscriptionData) => Promise<void>
  onCancel: () => void
}

function AddSubscriptionForm({ onSubmit, onCancel }: AddSubscriptionFormProps) {
  const [formData, setFormData] = useState<CreateSubscriptionData>({
    service_name: '',
    service_provider: '',
    category: 'LLM Providers',
    monthly_cost: 0,
    billing_day: new Date().getDate(),
    status: 'active',
    alert_enabled: true,
    alert_days_before: 3,
  })
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    try {
      await onSubmit(formData)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 p-4 rounded-lg border bg-muted/5">
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="service_name">Service Name *</Label>
          <Input
            id="service_name"
            value={formData.service_name}
            onChange={(e) => setFormData({ ...formData, service_name: e.target.value })}
            placeholder="e.g., OpenAI API"
            required
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="service_provider">Provider</Label>
          <Input
            id="service_provider"
            value={formData.service_provider || ''}
            onChange={(e) => setFormData({ ...formData, service_provider: e.target.value })}
            placeholder="e.g., OpenAI"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="category">Category *</Label>
          <select
            id="category"
            value={formData.category}
            onChange={(e) => setFormData({ ...formData, category: e.target.value as SubscriptionCategory })}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {categoryOptions.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="monthly_cost">Monthly Cost ($) *</Label>
          <Input
            id="monthly_cost"
            type="number"
            step="0.01"
            min="0"
            value={formData.monthly_cost}
            onChange={(e) => setFormData({ ...formData, monthly_cost: parseFloat(e.target.value) || 0 })}
            required
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="billing_day">Billing Day of Month</Label>
          <Input
            id="billing_day"
            type="number"
            min="1"
            max="31"
            value={formData.billing_day || ''}
            onChange={(e) => setFormData({ ...formData, billing_day: parseInt(e.target.value) || undefined })}
            placeholder="1-31"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="alert_days_before">Alert Days Before</Label>
          <Input
            id="alert_days_before"
            type="number"
            min="1"
            max="30"
            value={formData.alert_days_before}
            onChange={(e) => setFormData({ ...formData, alert_days_before: parseInt(e.target.value) || 3 })}
          />
        </div>
      </div>

      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="outline" onClick={onCancel} disabled={submitting}>
          Cancel
        </Button>
        <Button type="submit" disabled={submitting}>
          {submitting ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Check className="h-4 w-4 mr-2" />}
          Add Subscription
        </Button>
      </div>
    </form>
  )
}

interface EditSubscriptionDialogProps {
  subscription: Subscription | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onSave: (id: string, data: UpdateSubscriptionData) => Promise<void>
}

function EditSubscriptionDialog({ subscription, open, onOpenChange, onSave }: EditSubscriptionDialogProps) {
  const [formData, setFormData] = useState<UpdateSubscriptionData>({})
  const [submitting, setSubmitting] = useState(false)

  // Reset form when subscription changes
  useEffect(() => {
    if (subscription) {
      setFormData({
        service_name: subscription.service_name,
        service_provider: subscription.service_provider || '',
        category: subscription.category,
        monthly_cost: subscription.monthly_cost,
        billing_day: subscription.billing_day || undefined,
        status: subscription.status,
        alert_enabled: subscription.alert_enabled,
        alert_days_before: subscription.alert_days_before,
      })
    }
  }, [subscription])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!subscription) return

    setSubmitting(true)
    try {
      await onSave(subscription.id, formData)
      onOpenChange(false)
    } finally {
      setSubmitting(false)
    }
  }

  if (!subscription) return null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Edit Subscription</DialogTitle>
          <DialogDescription>
            Update the details for {subscription.service_name}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="edit_service_name">Service Name *</Label>
              <Input
                id="edit_service_name"
                value={formData.service_name || ''}
                onChange={(e) => setFormData({ ...formData, service_name: e.target.value })}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit_service_provider">Provider</Label>
              <Input
                id="edit_service_provider"
                value={formData.service_provider || ''}
                onChange={(e) => setFormData({ ...formData, service_provider: e.target.value })}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="edit_category">Category</Label>
              <select
                id="edit_category"
                value={formData.category || 'Other'}
                onChange={(e) => setFormData({ ...formData, category: e.target.value as SubscriptionCategory })}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {categoryOptions.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit_monthly_cost">Monthly Cost ($)</Label>
              <Input
                id="edit_monthly_cost"
                type="number"
                step="0.01"
                min="0"
                value={formData.monthly_cost || 0}
                onChange={(e) => setFormData({ ...formData, monthly_cost: parseFloat(e.target.value) || 0 })}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="edit_status">Status</Label>
              <select
                id="edit_status"
                value={formData.status || 'active'}
                onChange={(e) => setFormData({ ...formData, status: e.target.value as SubscriptionStatus })}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <option value="active">Active</option>
                <option value="trial">Trial</option>
                <option value="paused">Paused</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit_billing_day">Billing Day</Label>
              <Input
                id="edit_billing_day"
                type="number"
                min="1"
                max="31"
                value={formData.billing_day || ''}
                onChange={(e) => setFormData({ ...formData, billing_day: parseInt(e.target.value) || undefined })}
                placeholder="1-31"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                id="edit_alert_enabled"
                checked={formData.alert_enabled ?? true}
                onChange={(e) => setFormData({ ...formData, alert_enabled: e.target.checked })}
                className="h-4 w-4 rounded border-gray-300"
              />
              <Label htmlFor="edit_alert_enabled">Enable Alerts</Label>
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit_alert_days">Alert Days Before</Label>
              <Input
                id="edit_alert_days"
                type="number"
                min="1"
                max="30"
                value={formData.alert_days_before || 3}
                onChange={(e) => setFormData({ ...formData, alert_days_before: parseInt(e.target.value) || 3 })}
                disabled={!formData.alert_enabled}
              />
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
              Cancel
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Check className="h-4 w-4 mr-2" />}
              Save Changes
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export function SubscriptionTracker({ className }: SubscriptionTrackerProps) {
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([])
  const [summary, setSummary] = useState<SpendSummary | null>(null)
  const [alerts, setAlerts] = useState<UpcomingAlert[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showAddForm, setShowAddForm] = useState(false)
  const [editingSubscription, setEditingSubscription] = useState<Subscription | null>(null)

  const fetchData = async () => {
    try {
      setLoading(true)
      setError(null)
      const [subsData, summaryData, alertsData] = await Promise.all([
        getSubscriptions(),
        getSpendSummary(),
        getUpcomingAlerts(7),
      ])
      setSubscriptions(subsData)
      setSummary(summaryData)
      setAlerts(alertsData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch subscriptions')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  const handleAddSubscription = async (data: CreateSubscriptionData) => {
    try {
      await createSubscription(data)
      setShowAddForm(false)
      await fetchData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create subscription')
    }
  }

  const handleDeleteSubscription = async (id: string) => {
    if (!confirm('Are you sure you want to delete this subscription?')) return
    try {
      await deleteSubscription(id)
      await fetchData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete subscription')
    }
  }

  const handleUpdateSubscription = async (id: string, data: UpdateSubscriptionData) => {
    try {
      await updateSubscription(id, data)
      setEditingSubscription(null)
      await fetchData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update subscription')
    }
  }

  if (loading && !summary) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle>Subscription Tracker</CardTitle>
        </CardHeader>
        <CardContent className="flex justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    )
  }

  const groupedSubscriptions = subscriptions.reduce(
    (acc, sub) => {
      if (!acc[sub.category]) {
        acc[sub.category] = []
      }
      acc[sub.category].push(sub)
      return acc
    },
    {} as Record<SubscriptionCategory, Subscription[]>
  )

  return (
    <div className={cn('space-y-6', className)}>
      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-muted-foreground">Monthly Spend</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-bold">${summary.total_monthly_cost.toFixed(2)}</span>
                <span className="text-sm text-muted-foreground">/month</span>
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                ${summary.total_yearly_cost.toFixed(2)}/year
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-muted-foreground">Active Subscriptions</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-bold">{summary.active_subscriptions}</span>
                <span className="text-sm text-muted-foreground">services</span>
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                Across {summary.by_category.length} categories
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-muted-foreground">Upcoming Billing</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-bold">{alerts.length}</span>
                <span className="text-sm text-muted-foreground">alerts</span>
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                Next 7 days
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Upcoming Alerts */}
      {alerts.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-yellow-500" />
              Upcoming Billing Alerts
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {alerts.map((alert) => {
              const urgencyColors = {
                low: 'border-green-500/20 bg-green-500/5',
                medium: 'border-yellow-500/20 bg-yellow-500/5',
                high: 'border-red-500/20 bg-red-500/5',
              }
              return (
                <div
                  key={alert.subscription_id}
                  className={cn('flex items-center justify-between p-3 rounded-lg border', urgencyColors[alert.urgency])}
                >
                  <div>
                    <p className="font-medium text-sm">{alert.service_name}</p>
                    <p className="text-xs text-muted-foreground">
                      Bills in {alert.days_until_billing} day{alert.days_until_billing !== 1 ? 's' : ''}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="font-medium">${alert.monthly_cost.toFixed(2)}</p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(alert.next_billing_date).toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                      })}
                    </p>
                  </div>
                </div>
              )
            })}
          </CardContent>
        </Card>
      )}

      {/* Subscriptions List */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Subscriptions</CardTitle>
            <CardDescription>Manage your AI service subscriptions</CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="icon" onClick={fetchData} disabled={loading}>
              <RefreshCw className={cn('h-4 w-4', loading && 'animate-spin')} />
            </Button>
            <Button onClick={() => setShowAddForm(!showAddForm)} size="sm">
              {showAddForm ? (
                <>
                  <X className="h-4 w-4 mr-2" /> Cancel
                </>
              ) : (
                <>
                  <Plus className="h-4 w-4 mr-2" /> Add Subscription
                </>
              )}
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          {error && (
            <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/20">
              <p className="text-sm text-red-500">{error}</p>
            </div>
          )}

          {showAddForm && (
            <AddSubscriptionForm
              onSubmit={handleAddSubscription}
              onCancel={() => setShowAddForm(false)}
            />
          )}

          {subscriptions.length === 0 ? (
            <div className="text-center py-12">
              <Package className="h-12 w-12 mx-auto text-muted-foreground/50 mb-4" />
              <p className="text-muted-foreground mb-4">No subscriptions yet</p>
              <Button onClick={() => setShowAddForm(true)}>
                <Plus className="h-4 w-4 mr-2" /> Add Your First Subscription
              </Button>
            </div>
          ) : (
            <div className="space-y-6">
              {Object.entries(groupedSubscriptions).map(([category, subs]) => (
                <div key={category} className="space-y-3">
                  <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                    {categoryIcons[category as SubscriptionCategory]}
                    <span>{category}</span>
                    <span className="text-xs">({subs.length})</span>
                  </div>
                  <div className="space-y-2">
                    {subs.map((sub) => (
                      <SubscriptionCard
                        key={sub.id}
                        subscription={sub}
                        onEdit={() => setEditingSubscription(sub)}
                        onDelete={() => handleDeleteSubscription(sub.id)}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Edit Subscription Dialog */}
      <EditSubscriptionDialog
        subscription={editingSubscription}
        open={!!editingSubscription}
        onOpenChange={(open) => !open && setEditingSubscription(null)}
        onSave={handleUpdateSubscription}
      />
    </div>
  )
}
