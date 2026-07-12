'use client'

import { Badge } from '@/components/ui/badge'
import { Wifi, WifiOff } from 'lucide-react'

interface RealtimeIndicatorProps {
  isConnected: boolean
  error?: string | null
}

export function RealtimeIndicator({ isConnected, error }: RealtimeIndicatorProps) {
  if (error) {
    return (
      <Badge variant="destructive" className="gap-1">
        <WifiOff className="h-3 w-3" />
        Error
      </Badge>
    )
  }

  return (
    <Badge variant={isConnected ? 'success' : 'secondary'} className="gap-1">
      {isConnected ? (
        <>
          <Wifi className="h-3 w-3" />
          Live
        </>
      ) : (
        <>
          <WifiOff className="h-3 w-3" />
          Connecting...
        </>
      )}
    </Badge>
  )
}
