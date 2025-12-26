'use client'

import { useEffect, useState, useCallback } from 'react'
import { createClient } from '@/lib/supabase'
import type { RealtimeChannel } from '@supabase/supabase-js'

export interface RealtimeMetric {
  id: string
  user_id: string
  prompt_complexity: number
  selected_provider: string
  selected_model: string
  confidence_score: number
  cost_usd: number
  response_time_ms: number
  was_cache_hit: boolean
  created_at: string
}

export interface RealtimeStats {
  totalCost: number
  totalRequests: number
  cacheHits: number
  avgResponseTime: number
  recentMetrics: RealtimeMetric[]
}

interface UseRealtimeMetricsOptions {
  maxRecentItems?: number
  onNewMetric?: (metric: RealtimeMetric) => void
}

export function useRealtimeMetrics(options: UseRealtimeMetricsOptions = {}) {
  const { maxRecentItems = 50, onNewMetric } = options

  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [stats, setStats] = useState<RealtimeStats>({
    totalCost: 0,
    totalRequests: 0,
    cacheHits: 0,
    avgResponseTime: 0,
    recentMetrics: [],
  })

  const updateStats = useCallback((newMetric: RealtimeMetric) => {
    setStats((prev) => {
      const newRecentMetrics = [newMetric, ...prev.recentMetrics].slice(0, maxRecentItems)
      const newTotalRequests = prev.totalRequests + 1
      const newTotalCost = prev.totalCost + (newMetric.cost_usd || 0)
      const newCacheHits = prev.cacheHits + (newMetric.was_cache_hit ? 1 : 0)

      // Calculate running average response time
      const newAvgResponseTime =
        (prev.avgResponseTime * prev.totalRequests + newMetric.response_time_ms) / newTotalRequests

      return {
        totalCost: newTotalCost,
        totalRequests: newTotalRequests,
        cacheHits: newCacheHits,
        avgResponseTime: newAvgResponseTime,
        recentMetrics: newRecentMetrics,
      }
    })

    onNewMetric?.(newMetric)
  }, [maxRecentItems, onNewMetric])

  useEffect(() => {
    const supabase = createClient()
    let channel: RealtimeChannel | null = null

    const setupSubscription = async () => {
      try {
        channel = supabase
          .channel('routing-metrics-realtime')
          .on(
            'postgres_changes',
            {
              event: 'INSERT',
              schema: 'public',
              table: 'routing_metrics',
            },
            (payload) => {
              const newMetric = payload.new as RealtimeMetric
              updateStats(newMetric)
            }
          )
          .subscribe((status) => {
            if (status === 'SUBSCRIBED') {
              setIsConnected(true)
              setError(null)
            } else if (status === 'CHANNEL_ERROR') {
              setIsConnected(false)
              setError('Failed to connect to real-time updates')
            } else if (status === 'TIMED_OUT') {
              setIsConnected(false)
              setError('Connection timed out')
            }
          })
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error')
        setIsConnected(false)
      }
    }

    setupSubscription()

    return () => {
      if (channel) {
        supabase.removeChannel(channel)
      }
    }
  }, [updateStats])

  const resetStats = useCallback(() => {
    setStats({
      totalCost: 0,
      totalRequests: 0,
      cacheHits: 0,
      avgResponseTime: 0,
      recentMetrics: [],
    })
  }, [])

  return {
    isConnected,
    error,
    stats,
    resetStats,
    cacheHitRate: stats.totalRequests > 0
      ? (stats.cacheHits / stats.totalRequests) * 100
      : 0,
  }
}
