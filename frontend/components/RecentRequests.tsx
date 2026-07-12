'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

interface Request {
  id: string
  prompt_text: string
  provider: string
  tokens_used: number
  cost_cents: number
  response_time_ms: number
  created_at: string
}

interface RecentRequestsProps {
  requests: Request[]
}

const providerVariants: Record<
  string,
  'default' | 'secondary' | 'outline' | 'success' | 'warning'
> = {
  gemini: 'default',
  claude: 'warning',
  cerebras: 'success',
  openrouter: 'secondary',
}

function formatTimeAgo(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000)

  if (seconds < 60) return 'just now'
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  return `${Math.floor(seconds / 86400)}d ago`
}

export function RecentRequests({ requests }: RecentRequestsProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium">Recent Requests</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {requests.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">
              No requests yet. Make your first API call to see activity here.
            </p>
          ) : (
            requests.map(request => (
              <div
                key={request.id}
                className="flex items-center justify-between border-b pb-3 last:border-0 last:pb-0"
              >
                <div className="flex-1 min-w-0 mr-4">
                  <p className="text-sm font-medium truncate">
                    {request.prompt_text.substring(0, 50)}
                    {request.prompt_text.length > 50 ? '...' : ''}
                  </p>
                  <div className="flex items-center gap-2 mt-1">
                    <Badge variant={providerVariants[request.provider] || 'outline'}>
                      {request.provider}
                    </Badge>
                    <span className="text-xs text-muted-foreground">
                      {request.tokens_used.toLocaleString()} tokens
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {request.response_time_ms}ms
                    </span>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-sm font-medium">${(request.cost_cents / 100).toFixed(4)}</p>
                  <p className="text-xs text-muted-foreground">
                    {formatTimeAgo(request.created_at)}
                  </p>
                </div>
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  )
}
