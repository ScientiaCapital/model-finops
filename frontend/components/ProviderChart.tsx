'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

interface ProviderChartProps {
  data: Record<string, number>
  title: string
  type: 'requests' | 'cost'
}

const providerColors: Record<string, string> = {
  gemini: 'bg-blue-500',
  claude: 'bg-orange-500',
  cerebras: 'bg-green-500',
  openrouter: 'bg-purple-500',
}

export function ProviderChart({ data, title, type }: ProviderChartProps) {
  const total = Object.values(data).reduce((sum, val) => sum + val, 0)
  const sorted = Object.entries(data).sort(([, a], [, b]) => b - a)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {/* Bar chart */}
        <div className="space-y-3">
          {sorted.map(([provider, value]) => {
            const percentage = total > 0 ? (value / total) * 100 : 0
            return (
              <div key={provider} className="space-y-1">
                <div className="flex items-center justify-between text-sm">
                  <span className="capitalize font-medium">{provider}</span>
                  <span className="text-muted-foreground">
                    {type === 'cost' ? `$${(value / 100).toFixed(2)}` : value.toLocaleString()}
                    <span className="ml-1 text-xs">({percentage.toFixed(1)}%)</span>
                  </span>
                </div>
                <div className="h-2 rounded-full bg-secondary overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${
                      providerColors[provider] || 'bg-gray-500'
                    }`}
                    style={{ width: `${percentage}%` }}
                  />
                </div>
              </div>
            )
          })}
        </div>

        {/* Legend */}
        <div className="mt-4 flex flex-wrap gap-2">
          {sorted.map(([provider]) => (
            <Badge key={provider} variant="outline" className="capitalize">
              <span
                className={`mr-1 inline-block h-2 w-2 rounded-full ${
                  providerColors[provider] || 'bg-gray-500'
                }`}
              />
              {provider}
            </Badge>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
