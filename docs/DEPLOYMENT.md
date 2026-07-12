# AI Cost Optimizer - Production Deployment Guide

Complete guide for deploying the AI Cost Optimizer to production environments (RunPod, AWS, GCP, Azure, etc.)

## 📋 Prerequisites

### 1. Supabase Account & Configuration

- Sign up at [supabase.com](https://supabase.com)
- Create a new project
- Run database migrations (see [Supabase Setup](#supabase-setup))
- Get your credentials:
  - `SUPABASE_URL`
  - `SUPABASE_ANON_KEY`
  - `SUPABASE_SERVICE_KEY`
  - `SUPABASE_JWT_SECRET`

### 2. AI Provider API Keys

At least one provider is required:

- **Google Gemini** (recommended for free tier): [makersuite.google.com](https://makersuite.google.com/app/apikey)
- **Anthropic Claude**: [console.anthropic.com](https://console.anthropic.com)
- **Cerebras**: [cloud.cerebras.ai](https://cloud.cerebras.ai)
- **OpenRouter** (fallback): [openrouter.ai](https://openrouter.ai)

### 3. Docker & BuildX

```bash
# Verify Docker is installed
docker --version

# Enable BuildX (for multi-platform builds)
docker buildx create --use
```

---

## 🚀 Quick Start (RunPod Deployment)

### Step 1: Build Multi-Platform Docker Image

```bash
# Build for linux/amd64 (RunPod, AWS, most cloud platforms)
docker buildx build \
  --platform linux/amd64 \
  --tag your-dockerhub-username/ai-cost-optimizer:latest \
  --push \
  .

# Alternative: Build without pushing (for testing)
docker buildx build \
  --platform linux/amd64 \
  --tag ai-cost-optimizer:latest \
  --load \
  .
```

### Step 2: Test Locally

```bash
# Run with environment variables
docker run -p 8000:8000 \
  -e SUPABASE_URL="https://your-project.supabase.co" \
  -e SUPABASE_ANON_KEY="your-anon-key" \
  -e SUPABASE_SERVICE_KEY="your-service-key" \
  -e SUPABASE_JWT_SECRET="your-jwt-secret" \
  -e GOOGLE_API_KEY="your-gemini-key" \
  -e ANTHROPIC_API_KEY="your-claude-key" \
  ai-cost-optimizer:latest

# Test health endpoint
curl http://localhost:8000/health
```

### Step 3: Deploy to RunPod

1. **Create RunPod Account**: [runpod.io](https://www.runpod.io/)

2. **Deploy Container**:
   - Go to "My Pods" → "Deploy"
   - Container Image: `your-dockerhub-username/ai-cost-optimizer:latest`
   - Container Disk: 10GB
   - Exposed HTTP Ports: `8000`
   - Environment Variables:
     ```
     SUPABASE_URL=https://your-project.supabase.co
     SUPABASE_ANON_KEY=eyJhbGc...
     SUPABASE_SERVICE_KEY=eyJhbGc...
     SUPABASE_JWT_SECRET=your-jwt-secret
     GOOGLE_API_KEY=your-gemini-key
     ANTHROPIC_API_KEY=your-claude-key
     LOG_LEVEL=INFO
     ```

3. **Access Your API**:
   - RunPod will provide a public URL (e.g., `https://xxx-8000.proxy.runpod.net`)
   - Test: `curl https://xxx-8000.proxy.runpod.net/health`

---

## 🗄️ Supabase Setup

### Run Database Migrations

1. **Login to Supabase Dashboard**: [supabase.com/dashboard](https://supabase.com/dashboard)

2. **Navigate to SQL Editor**: Your Project → SQL Editor

3. **Run Migrations in Order**:

   **Migration 1: Extensions**

   ```bash
   # Copy contents of migrations/supabase_part1_extensions.sql
   # Paste into SQL Editor → Run
   ```

   **Migration 2: Tables**

   ```bash
   # Copy contents of migrations/supabase_create_tables.sql
   # Paste into SQL Editor → Run
   ```

   **Migration 3: RLS Policies**

   ```bash
   # Copy contents of migrations/supabase_part2_schema_fixed.sql
   # Paste into SQL Editor → Run
   ```

4. **Enable Realtime** (for live metrics):
   - Go to Database → Replication
   - Find `routing_metrics` table
   - Toggle "Enable Realtime"
   - Select "INSERT" events
   - Save

5. **Verify Setup**:
   ```sql
   -- Check tables were created
   SELECT tablename FROM pg_tables WHERE schemaname = 'public';

   -- Check RLS is enabled
   SELECT tablename, rowsecurity FROM pg_tables
   WHERE schemaname = 'public' AND rowsecurity = true;
   ```

---

## 🔐 Environment Variables Reference

### Required Variables

| Variable               | Description                            | Example                      |
| ---------------------- | -------------------------------------- | ---------------------------- |
| `SUPABASE_URL`         | Your Supabase project URL              | `https://abc123.supabase.co` |
| `SUPABASE_ANON_KEY`    | Public anon key (respects RLS)         | `eyJhbGc...`                 |
| `SUPABASE_SERVICE_KEY` | Admin key (bypasses RLS)               | `eyJhbGc...`                 |
| `SUPABASE_JWT_SECRET`  | JWT signing secret                     | `your-jwt-secret`            |
| `GOOGLE_API_KEY`       | Gemini API key (at least one provider) | `AIzaSy...`                  |

### Optional Variables

| Variable               | Description                | Default                                  |
| ---------------------- | -------------------------- | ---------------------------------------- |
| `ANTHROPIC_API_KEY`    | Claude API key             | -                                        |
| `OPENROUTER_API_KEY`   | OpenRouter API key         | -                                        |
| `CEREBRAS_API_KEY`     | Cerebras API key           | -                                        |
| `LOG_LEVEL`            | Logging level              | `INFO`                                   |
| `PORT`                 | Server port                | `8000`                                   |
| `EMBEDDING_MODEL_NAME` | Sentence transformer model | `sentence-transformers/all-MiniLM-L6-v2` |
| `EMBEDDING_DEVICE`     | Device for embeddings      | `cpu` (or `cuda`)                        |
| `SIMILARITY_THRESHOLD` | Cache similarity threshold | `0.95`                                   |

---

## 🌐 Frontend Integration

### Option 1: Use Provided Dashboard

```bash
# Serve the frontend
cd frontend
python3 -m http.server 8080

# Open in browser
open http://localhost:8080/realtime-dashboard.html
```

**Configuration**:

1. Edit `frontend/realtime-dashboard.html`
2. Replace `YOUR_ANON_KEY_HERE` with your Supabase anon key
3. Deploy to any static host (Vercel, Netlify, GitHub Pages)

### Option 2: Custom Integration

```javascript
import { createClient } from '@supabase/supabase-js'

const supabase = createClient('https://your-project.supabase.co', 'your-anon-key')

// Subscribe to routing metrics
const channel = supabase
  .channel('my-app')
  .on(
    'postgres_changes',
    {
      event: 'INSERT',
      schema: 'public',
      table: 'routing_metrics',
    },
    payload => {
      console.log('New metric:', payload.new)
      // Update your UI
    }
  )
  .subscribe()
```

See `docs/REALTIME_SETUP.md` for complete guide.

---

## 🧪 Testing Deployment

### 1. Health Check

```bash
curl https://your-deployment-url/health
# Expected: {"status": "healthy"}
```

### 2. List Providers

```bash
curl https://your-deployment-url/providers
# Expected: List of configured providers
```

### 3. Test Completion (requires authentication)

```bash
# Get JWT token from Supabase Auth first
curl -X POST https://your-deployment-url/complete \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is Python?", "max_tokens": 100}'
```

---

## 📊 Monitoring & Logs

### View Logs (RunPod)

```bash
# Via RunPod Dashboard
# Pods → Your Pod → Logs tab

# Via API
curl -X GET https://api.runpod.io/v1/pods/{POD_ID}/logs \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### Health Metrics

```bash
# Check application health
curl https://your-deployment-url/health

# Check cache stats
curl https://your-deployment-url/cache/stats

# Check routing metrics (requires auth)
curl https://your-deployment-url/routing/metrics \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

## 🔧 Troubleshooting

### Issue: "Module not found" errors

**Solution**: Ensure all dependencies in `requirements.txt` are installed

```bash
docker build --no-cache -t ai-cost-optimizer:latest .
```

### Issue: Supabase connection fails

**Solution**: Verify environment variables

```bash
docker run ai-cost-optimizer:latest env | grep SUPABASE
```

### Issue: "No providers configured"

**Solution**: Add at least one AI provider API key

```bash
docker run -e GOOGLE_API_KEY=your-key ai-cost-optimizer:latest
```

### Issue: JWT authentication fails

**Solution**: Ensure `SUPABASE_JWT_SECRET` matches your Supabase project settings

- Dashboard → Settings → API → JWT Secret

---

## 🚀 Production Best Practices

### 1. Use Secrets Management

```bash
# AWS Secrets Manager
aws secretsmanager get-secret-value --secret-id ai-cost-optimizer/prod

# GCP Secret Manager
gcloud secrets versions access latest --secret="ai-cost-optimizer-env"

# RunPod Environment Variables
# Use RunPod's secure environment variable storage
```

### 2. Enable HTTPS

```bash
# Use reverse proxy (nginx, Caddy, Traefik)
# Or use RunPod's built-in HTTPS endpoints
```

### 3. Set Resource Limits

```yaml
# docker-compose.yml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

### 4. Configure Auto-Scaling

```bash
# RunPod Auto-Scaling
# Min Pods: 1
# Max Pods: 5
# Scale metric: CPU > 70%
```

---

## 📚 Additional Resources

- [Supabase Realtime Guide](./REALTIME_SETUP.md)
- [Authentication Setup](../app/auth.py)
- [API Documentation](http://your-deployment-url/docs)
- [RunPod Documentation](https://docs.runpod.io/)

---

**Ready for production!** 🎉

Need help? Open an issue on GitHub or check the documentation.
