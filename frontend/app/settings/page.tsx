'use client'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Save, RefreshCw, Database, Zap, Brain } from 'lucide-react'

export default function SettingsPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">Configure your AI Cost Optimizer preferences</p>
      </div>

      {/* Routing Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Brain className="h-5 w-5" />
            Routing Configuration
          </CardTitle>
          <CardDescription>Configure how prompts are routed to AI providers</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between py-2">
            <div>
              <p className="font-medium">Auto Routing</p>
              <p className="text-sm text-muted-foreground">
                Automatically select the best provider based on prompt complexity
              </p>
            </div>
            <Badge variant="success">Enabled</Badge>
          </div>
          <div className="flex items-center justify-between py-2">
            <div>
              <p className="font-medium">Routing Strategy</p>
              <p className="text-sm text-muted-foreground">
                The algorithm used for provider selection
              </p>
            </div>
            <Badge variant="outline">Hybrid</Badge>
          </div>
          <div className="flex items-center justify-between py-2">
            <div>
              <p className="font-medium">Fallback Provider</p>
              <p className="text-sm text-muted-foreground">
                Provider used when primary selection fails
              </p>
            </div>
            <Badge variant="outline">OpenRouter</Badge>
          </div>
        </CardContent>
      </Card>

      {/* Cache Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-5 w-5" />
            Cache Configuration
          </CardTitle>
          <CardDescription>Configure semantic caching behavior</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between py-2">
            <div>
              <p className="font-medium">Semantic Caching</p>
              <p className="text-sm text-muted-foreground">
                Cache similar queries using embedding similarity
              </p>
            </div>
            <Badge variant="success">Enabled</Badge>
          </div>
          <div className="flex items-center justify-between py-2">
            <div>
              <p className="font-medium">Similarity Threshold</p>
              <p className="text-sm text-muted-foreground">
                Minimum similarity score for cache hits (0-100%)
              </p>
            </div>
            <Badge variant="outline">95%</Badge>
          </div>
          <div className="flex items-center justify-between py-2">
            <div>
              <p className="font-medium">Embedding Model</p>
              <p className="text-sm text-muted-foreground">
                Model used for generating query embeddings
              </p>
            </div>
            <Badge variant="outline">all-MiniLM-L6-v2</Badge>
          </div>
        </CardContent>
      </Card>

      {/* Provider Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Zap className="h-5 w-5" />
            Provider Priority
          </CardTitle>
          <CardDescription>Configure provider preferences and fallback order</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <div className="flex items-center justify-between py-2 border-b">
              <div className="flex items-center gap-3">
                <span className="text-muted-foreground">1.</span>
                <span className="font-medium">Gemini</span>
              </div>
              <Badge variant="success">Active</Badge>
            </div>
            <div className="flex items-center justify-between py-2 border-b">
              <div className="flex items-center gap-3">
                <span className="text-muted-foreground">2.</span>
                <span className="font-medium">Claude</span>
              </div>
              <Badge variant="success">Active</Badge>
            </div>
            <div className="flex items-center justify-between py-2 border-b">
              <div className="flex items-center gap-3">
                <span className="text-muted-foreground">3.</span>
                <span className="font-medium">Cerebras</span>
              </div>
              <Badge variant="success">Active</Badge>
            </div>
            <div className="flex items-center justify-between py-2">
              <div className="flex items-center gap-3">
                <span className="text-muted-foreground">4.</span>
                <span className="font-medium">OpenRouter</span>
              </div>
              <Badge variant="outline">Fallback</Badge>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Actions */}
      <div className="flex gap-4">
        <Button disabled>
          <Save className="mr-2 h-4 w-4" />
          Save Changes
        </Button>
        <Button variant="outline" disabled>
          <RefreshCw className="mr-2 h-4 w-4" />
          Reset to Defaults
        </Button>
      </div>

      <p className="text-sm text-muted-foreground">
        Note: Settings configuration is coming soon. These values are currently read-only.
      </p>
    </div>
  )
}
