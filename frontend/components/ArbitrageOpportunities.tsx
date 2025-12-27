'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ArrowRight, TrendingDown, Sparkles } from 'lucide-react'
import type { ArbitrageOpportunity } from '@/lib/api'

interface ArbitrageOpportunitiesProps {
  opportunities: ArbitrageOpportunity[]
  onAnalyze?: () => void
  loading?: boolean
}

export function ArbitrageOpportunities({
  opportunities,
  onAnalyze,
  loading = false,
}: ArbitrageOpportunitiesProps) {
  const getSavingsBadgeVariant = (percent: number) => {
    if (percent >= 70) return 'success'
    if (percent >= 40) return 'warning'
    return 'secondary'
  }

  const getQualityBadgeVariant = (score: number) => {
    if (score >= 0.9) return 'success'
    if (score >= 0.8) return 'warning'
    return 'destructive'
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-yellow-500" />
          <CardTitle className="text-lg">Arbitrage Opportunities</CardTitle>
        </div>
        {onAnalyze && (
          <Button size="sm" variant="outline" onClick={onAnalyze} disabled={loading}>
            {loading ? 'Analyzing...' : 'Find Savings'}
          </Button>
        )}
      </CardHeader>
      <CardContent>
        {opportunities.length === 0 ? (
          <div className="text-center py-6 text-muted-foreground">
            <TrendingDown className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">No arbitrage opportunities found</p>
            <p className="text-xs mt-1">Try analyzing a prompt to find cost savings</p>
          </div>
        ) : (
          <div className="space-y-4">
            {opportunities.slice(0, 5).map((opp, index) => (
              <div
                key={opp.id || index}
                className="flex items-center justify-between p-3 rounded-lg border bg-muted/50"
              >
                <div className="flex items-center gap-3">
                  <div className="flex flex-col">
                    <div className="flex items-center gap-2 text-sm">
                      <span className="font-medium">{opp.current_model}</span>
                      <ArrowRight className="h-3 w-3 text-muted-foreground" />
                      <span className="font-medium text-green-600">{opp.alternative_model}</span>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground mt-1">
                      <span>{opp.current_provider}</span>
                      <ArrowRight className="h-2 w-2" />
                      <span>{opp.alternative_provider}</span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={getSavingsBadgeVariant(opp.savings_percent)}>
                    -{opp.savings_percent.toFixed(0)}%
                  </Badge>
                  <Badge variant={getQualityBadgeVariant(opp.quality_score)}>
                    Q: {(opp.quality_score * 100).toFixed(0)}%
                  </Badge>
                </div>
              </div>
            ))}
            {opportunities.length > 5 && (
              <p className="text-xs text-center text-muted-foreground">
                +{opportunities.length - 5} more opportunities
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
