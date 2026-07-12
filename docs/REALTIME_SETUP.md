# Supabase Realtime Setup for AI Cost Optimizer

This guide explains how to use Supabase Realtime to replace the custom WebSocket implementation for real-time metrics streaming.

## 📡 What is Supabase Realtime?

Supabase Realtime is a built-in pub/sub system that allows you to:

- Listen to database changes in real-time
- Subscribe to INSERT, UPDATE, DELETE events
- Filter subscriptions by row-level security (RLS)
- Scale to millions of concurrent connections

**Benefits over custom WebSocket:**

- ✅ No custom connection management code
- ✅ Automatic reconnection handling
- ✅ RLS filtering (users only see their own data)
- ✅ Built-in presence and broadcast features
- ✅ Managed infrastructure (no WebSocket server to maintain)

## 🔧 Step 1: Enable Realtime in Supabase Dashboard

1. Go to your Supabase project: https://supabase.com/dashboard/project/nhjhzzkcqtsmfgvairos

2. Navigate to **Database** → **Replication**

3. Find the `routing_metrics` table

4. Click the toggle to enable Realtime

5. Choose which events to broadcast:
   - ✅ **INSERT** - New routing decisions
   - ❌ UPDATE - Not needed for metrics
   - ❌ DELETE - Not needed for metrics

6. Click **Save**

**Alternative: Enable via SQL**

```sql
-- Enable Realtime for routing_metrics table
ALTER PUBLICATION supabase_realtime ADD TABLE routing_metrics;

-- Verify it's enabled
SELECT * FROM pg_publication_tables
WHERE pubname = 'supabase_realtime';
```

## 📦 Step 2: Install Supabase JavaScript Client (Frontend)

For your frontend application (React, Vue, etc.):

```bash
npm install @supabase/supabase-js
# or
yarn add @supabase/supabase-js
```

## 💻 Step 3: Subscribe to Realtime Updates (Frontend)

### React Example

```javascript
import { createClient } from '@supabase/supabase-js'
import { useEffect, useState } from 'react'

const supabase = createClient(
  'https://nhjhzzkcqtsmfgvairos.supabase.co',
  'YOUR_ANON_KEY' // Use anon key (respects RLS)
)

function MetricsDashboard() {
  const [metrics, setMetrics] = useState([])

  useEffect(() => {
    // Subscribe to routing_metrics inserts
    const channel = supabase
      .channel('routing-metrics')
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'routing_metrics',
        },
        payload => {
          console.log('New routing decision:', payload.new)

          // Add new metric to state
          setMetrics(prev => [payload.new, ...prev].slice(0, 100))
        }
      )
      .subscribe()

    // Cleanup on unmount
    return () => {
      supabase.removeChannel(channel)
    }
  }, [])

  return (
    <div>
      <h1>Real-Time Routing Metrics</h1>
      {metrics.map(m => (
        <div key={m.id}>
          {m.timestamp}: {m.provider}/{m.model} - ${m.cost}
        </div>
      ))}
    </div>
  )
}
```

### Vanilla JavaScript Example (Secure)

```html
<!DOCTYPE html>
<html>
  <head>
    <title>Real-Time Metrics</title>
    <script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
  </head>
  <body>
    <div id="metrics"></div>

    <script>
      const { createClient } = supabase

      const client = createClient('https://nhjhzzkcqtsmfgvairos.supabase.co', 'YOUR_ANON_KEY')

      // Subscribe to routing_metrics
      const channel = client
        .channel('routing-metrics')
        .on(
          'postgres_changes',
          {
            event: 'INSERT',
            schema: 'public',
            table: 'routing_metrics',
          },
          payload => {
            const metric = payload.new
            const metricsDiv = document.getElementById('metrics')

            // Create element safely (no XSS vulnerability)
            const p = document.createElement('p')
            p.textContent = `${metric.timestamp}: ${metric.provider}/${metric.model} - $${metric.cost}`

            // Insert at beginning
            metricsDiv.insertBefore(p, metricsDiv.firstChild)
          }
        )
        .subscribe()
    </script>
  </body>
</html>
```

## 🔐 Step 4: Authentication with RLS

When users are authenticated, Realtime automatically filters rows based on RLS policies:

```javascript
import { createClient } from '@supabase/supabase-js'

const supabase = createClient('https://nhjhzzkcqtsmfgvairos.supabase.co', 'YOUR_ANON_KEY')

// User logs in
const { data, error } = await supabase.auth.signInWithPassword({
  email: 'user@example.com',
  password: 'password',
})

// Now subscriptions automatically filter by user_id!
const channel = supabase
  .channel('my-metrics')
  .on(
    'postgres_changes',
    {
      event: 'INSERT',
      schema: 'public',
      table: 'routing_metrics',
      // No need to filter by user_id - RLS does it automatically!
    },
    payload => {
      // Only sees their own metrics thanks to RLS
      console.log('My routing decision:', payload.new)
    }
  )
  .subscribe()
```

## 🎯 Step 5: Advanced - Filter Subscriptions

You can filter subscriptions server-side for efficiency:

```javascript
// Only get metrics for a specific provider
const channel = supabase
  .channel('gemini-metrics')
  .on(
    'postgres_changes',
    {
      event: 'INSERT',
      schema: 'public',
      table: 'routing_metrics',
      filter: 'provider=eq.gemini', // ← Server-side filter!
    },
    payload => {
      console.log('Gemini routing:', payload.new)
    }
  )
  .subscribe()

// Multiple filters
const channel2 = supabase
  .channel('high-cost-metrics')
  .on(
    'postgres_changes',
    {
      event: 'INSERT',
      schema: 'public',
      table: 'routing_metrics',
      filter: 'cost=gt.0.01', // cost > $0.01
    },
    payload => {
      console.log('High cost routing:', payload.new)
    }
  )
  .subscribe()
```

**Available Operators:**

- `eq` - equals
- `neq` - not equals
- `gt` - greater than
- `gte` - greater than or equal
- `lt` - less than
- `lte` - less than or equal
- `in` - in list
- `is` - is (null, true, false)

## 📊 Step 6: Backend Integration (Python/FastAPI)

The FastAPI backend should INSERT into `routing_metrics` table - Realtime handles the rest!

```python
from app.routing.metrics_async import AsyncMetricsCollector
from app.routing.models import RoutingDecision

# In your routing endpoint
async def route_request(...):
    # Make routing decision
    decision = engine.route(prompt, auto_route=True)

    # Track decision (inserts into routing_metrics)
    metrics_collector = AsyncMetricsCollector(user_id=user_id)
    await metrics_collector.track_decision(
        prompt=prompt,
        decision=decision,
        auto_route=True,
        request_id=request_id
    )

    # ✨ Realtime automatically broadcasts this to subscribers!
    # No WebSocket code needed!
```

## 🔄 Migration from Custom WebSocket

### Before (Custom WebSocket)

```python
# Backend - app/main.py
from fastapi import WebSocket

@app.websocket("/ws/metrics")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Poll database every 5 seconds
            metrics = get_metrics()
            await websocket.send_json(metrics)
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
```

```javascript
// Frontend
const ws = new WebSocket('ws://localhost:8000/ws/metrics')
ws.onmessage = event => {
  const metrics = JSON.parse(event.data)
  updateUI(metrics)
}
```

**Problems:**

- ❌ Manual connection management
- ❌ Polling database (inefficient)
- ❌ No automatic RLS filtering
- ❌ Have to handle reconnections
- ❌ Scale issues with many connections

### After (Supabase Realtime)

```python
# Backend - Just insert, Realtime handles the rest!
await metrics_collector.track_decision(...)
# Done! 🎉
```

```javascript
// Frontend
const channel = supabase
  .channel('metrics')
  .on(
    'postgres_changes',
    { event: 'INSERT', schema: 'public', table: 'routing_metrics' },
    payload => updateUI(payload.new)
  )
  .subscribe()
```

**Benefits:**

- ✅ Automatic connection management
- ✅ Push-based (instant updates, no polling)
- ✅ RLS filtering automatic
- ✅ Auto-reconnect built-in
- ✅ Scales to millions

## 🧹 Cleanup - Remove Custom WebSocket

Once Realtime is working, you can delete:

**Backend (app/main.py):**

- `ConnectionManager` class
- `/ws/metrics` WebSocket endpoint
- `ws_clients_cache` dictionary
- All WebSocket management code

**Frontend:**

- Old WebSocket connection code
- Polling logic
- Reconnection handling

## 🎁 Bonus: Presence (Who's Online)

Supabase Realtime includes Presence for tracking who's online:

```javascript
const channel = supabase.channel('online-users')

// Track this user as online
channel
  .on('presence', { event: 'sync' }, () => {
    const state = channel.presenceState()
    console.log('Online users:', Object.keys(state))
  })
  .subscribe(async status => {
    if (status === 'SUBSCRIBED') {
      await channel.track({ user_id: currentUser.id, online_at: new Date() })
    }
  })
```

## 📚 Resources

- [Supabase Realtime Docs](https://supabase.com/docs/guides/realtime)
- [Realtime Python Client](https://github.com/supabase-community/realtime-py)
- [JavaScript Client Docs](https://supabase.com/docs/reference/javascript/subscribe)
- [RLS with Realtime](https://supabase.com/docs/guides/realtime/postgres-changes#row-level-security)

## 🚀 Next Steps

1. ✅ Enable Realtime on `routing_metrics` table in Supabase dashboard
2. ✅ Update frontend to use Supabase client
3. ✅ Test real-time updates
4. ✅ Remove custom WebSocket code
5. ✅ Deploy and enjoy managed real-time infrastructure!

---

**Note:** The backend (FastAPI) doesn't need to change - it just inserts into routing_metrics as it already does. Supabase Realtime handles broadcasting to all subscribed clients automatically!
