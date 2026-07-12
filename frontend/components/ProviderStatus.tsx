'use client'

import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { cn } from '@/lib/utils'
import {
  CheckCircle2,
  XCircle,
  AlertCircle,
  ExternalLink,
  RefreshCw,
  Loader2,
  Cpu,
  Mic,
  Database,
  Activity,
  CreditCard,
  Video,
} from 'lucide-react'
import {
  getProvidersStatus,
  type ProviderInfo,
  type ProvidersStatusResponse,
  type ProviderStatus as ProviderStatusType,
} from '@/lib/api'

interface ProviderStatusProps {
  className?: string
  onSetupClick?: (provider: ProviderInfo) => void
}

const categoryIcons: Record<string, React.ReactNode> = {
  'LLM Providers': <Cpu className="h-4 w-4" />,
  'Voice AI (TTS)': <Mic className="h-4 w-4" />,
  'Voice AI (STT)': <Mic className="h-4 w-4" />,
  Infrastructure: <Database className="h-4 w-4" />,
  'AI Media': <Video className="h-4 w-4" />,
  Observability: <Activity className="h-4 w-4" />,
  Billing: <CreditCard className="h-4 w-4" />,
}

const statusConfig: Record<
  ProviderStatusType,
  { icon: React.ReactNode; color: string; bgColor: string }
> = {
  connected: {
    icon: <CheckCircle2 className="h-4 w-4 text-green-500" />,
    color: 'text-green-500',
    bgColor: 'bg-green-500/10',
  },
  invalid: {
    icon: <XCircle className="h-4 w-4 text-red-500" />,
    color: 'text-red-500',
    bgColor: 'bg-red-500/10',
  },
  not_configured: {
    icon: <AlertCircle className="h-4 w-4 text-yellow-500" />,
    color: 'text-yellow-500',
    bgColor: 'bg-yellow-500/10',
  },
  error: {
    icon: <XCircle className="h-4 w-4 text-red-500" />,
    color: 'text-red-500',
    bgColor: 'bg-red-500/10',
  },
}

function ProviderCard({
  provider,
  onSetupClick,
}: {
  provider: ProviderInfo
  onSetupClick?: (p: ProviderInfo) => void
}) {
  const config = statusConfig[provider.status]

  return (
    <div
      className={cn(
        'flex items-center justify-between p-3 rounded-lg border',
        provider.status === 'connected' ? 'border-green-500/20' : 'border-border'
      )}
    >
      <div className="flex items-center gap-3">
        {config.icon}
        <div>
          <p className="font-medium text-sm">{provider.display_name}</p>
          <p className="text-xs text-muted-foreground">
            {provider.status === 'connected' && provider.models_available
              ? `${provider.models_available} models`
              : provider.message}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        {provider.status === 'connected' ? (
          <Badge variant="outline" className="text-green-500 border-green-500/50">
            Connected
          </Badge>
        ) : (
          <Button
            variant="ghost"
            size="sm"
            className="h-8 gap-1 text-xs"
            onClick={() => {
              if (onSetupClick) {
                onSetupClick(provider)
              } else {
                window.open(provider.setup_url, '_blank')
              }
            }}
          >
            Set up <ExternalLink className="h-3 w-3" />
          </Button>
        )}
      </div>
    </div>
  )
}

export function ProviderStatus({ className, onSetupClick }: ProviderStatusProps) {
  const [data, setData] = useState<ProvidersStatusResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchData = async () => {
    try {
      setLoading(true)
      setError(null)
      const result = await getProvidersStatus()
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch provider status')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  if (loading && !data) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle>Provider Status</CardTitle>
        </CardHeader>
        <CardContent className="flex justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    )
  }

  if (error) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle>Provider Status</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-4">
            <p className="text-red-500 mb-2">{error}</p>
            <Button variant="outline" size="sm" onClick={fetchData}>
              <RefreshCw className="h-4 w-4 mr-2" /> Retry
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (!data) return null

  // Group providers by category
  const providersByCategory = data.providers.reduce(
    (acc, provider) => {
      if (!acc[provider.category]) {
        acc[provider.category] = []
      }
      acc[provider.category].push(provider)
      return acc
    },
    {} as Record<string, ProviderInfo[]>
  )

  return (
    <Card className={className}>
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle>Provider Status</CardTitle>
          <CardDescription>
            {data.summary.connected} of {data.summary.total} providers connected
          </CardDescription>
        </div>
        <Button variant="ghost" size="icon" onClick={fetchData} disabled={loading}>
          <RefreshCw className={cn('h-4 w-4', loading && 'animate-spin')} />
        </Button>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Progress Bar */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Setup Progress</span>
            <span className="font-medium">{data.setup_progress.toFixed(0)}%</span>
          </div>
          <Progress value={data.setup_progress} className="h-2" />
        </div>

        {/* Summary Stats */}
        <div className="grid grid-cols-3 gap-4">
          <div className="text-center p-3 rounded-lg bg-green-500/10">
            <p className="text-2xl font-bold text-green-500">{data.summary.connected}</p>
            <p className="text-xs text-muted-foreground">Connected</p>
          </div>
          <div className="text-center p-3 rounded-lg bg-yellow-500/10">
            <p className="text-2xl font-bold text-yellow-500">{data.summary.not_configured}</p>
            <p className="text-xs text-muted-foreground">Not Set</p>
          </div>
          <div className="text-center p-3 rounded-lg bg-muted">
            <p className="text-2xl font-bold">{data.summary.total}</p>
            <p className="text-xs text-muted-foreground">Total</p>
          </div>
        </div>

        {/* Providers by Category */}
        <div className="space-y-4">
          {Object.entries(providersByCategory).map(([category, providers]) => (
            <div key={category} className="space-y-2">
              <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                {categoryIcons[category]}
                <span>{category}</span>
              </div>
              <div className="space-y-2">
                {providers.map(provider => (
                  <ProviderCard
                    key={provider.name}
                    provider={provider}
                    onSetupClick={onSetupClick}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
