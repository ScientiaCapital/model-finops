'use client'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Key, Plus } from 'lucide-react'

export default function ApiKeysPage() {
  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">API Keys</h1>
          <p className="text-muted-foreground">Manage your API keys for authentication</p>
        </div>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          Create Key
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Your API Keys</CardTitle>
          <CardDescription>
            API keys allow you to authenticate requests to the AI Cost Optimizer API.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {/* Empty state */}
            <div className="text-center py-12">
              <Key className="h-12 w-12 mx-auto text-muted-foreground" />
              <h3 className="mt-4 text-lg font-medium">No API keys yet</h3>
              <p className="mt-2 text-sm text-muted-foreground">
                Create your first API key to start using the AI Cost Optimizer API.
              </p>
              <Button className="mt-4">
                <Plus className="mr-2 h-4 w-4" />
                Create Your First Key
              </Button>
            </div>

            {/* Example key (commented out for now) */}
            {/*
            <div className="flex items-center justify-between p-4 border rounded-lg">
              <div className="flex items-center gap-4">
                <Key className="h-5 w-5 text-muted-foreground" />
                <div>
                  <p className="font-mono text-sm">sk-aco_••••••••••••abcd</p>
                  <p className="text-xs text-muted-foreground">Created Dec 1, 2024</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="success">Active</Badge>
                <Button variant="ghost" size="icon">
                  <Copy className="h-4 w-4" />
                </Button>
                <Button variant="ghost" size="icon" className="text-destructive">
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
            */}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Usage</CardTitle>
          <CardDescription>How to use your API key</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div>
              <h4 className="font-medium mb-2">Authentication Header</h4>
              <pre className="p-4 bg-muted rounded-lg text-sm overflow-x-auto">
                {`curl -X POST https://api.ai-cost-optimizer.com/complete \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"prompt": "Hello, world!"}'`}
              </pre>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
