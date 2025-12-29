#!/bin/bash
# AI Cost Optimizer - Railway Deployment Script
# Deploys the FastAPI backend to Railway with all required environment variables.

set -e

echo "=============================================="
echo "AI Cost Optimizer - Railway Deployment"
echo "=============================================="

# Check if Railway CLI is authenticated
if ! railway whoami 2>/dev/null; then
    echo "ERROR: Not logged in to Railway. Run 'railway login' first."
    exit 1
fi

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

# Load environment variables from .env
if [ -f ".env" ]; then
    echo "Loading environment variables from .env..."
    export $(grep -v '^#' .env | xargs)
else
    echo "WARNING: No .env file found. You'll need to set environment variables manually."
fi

# Create new Railway project or link existing
echo ""
echo "=== Setting up Railway project ==="
if [ ! -f ".railway/config.json" ]; then
    echo "Creating new Railway project: ai-cost-optimizer"
    railway init --name ai-cost-optimizer
else
    echo "Using existing Railway project configuration"
fi

# Set environment variables
echo ""
echo "=== Setting environment variables ==="
VERCEL_URL="https://ai-cost-optimizer-scientia-capital.vercel.app"

# Core configuration
railway variables set PORT=8000
railway variables set LOG_LEVEL=INFO
railway variables set EMBEDDING_DEVICE=cpu
railway variables set CORS_ORIGINS="$VERCEL_URL"

# Model cache paths
railway variables set TORCH_HOME=/app/model_cache
railway variables set HF_HOME=/app/model_cache
railway variables set SENTENCE_TRANSFORMERS_HOME=/app/model_cache

# Supabase (from environment)
if [ -n "$SUPABASE_URL" ]; then
    railway variables set SUPABASE_URL="$SUPABASE_URL"
    echo "  ✓ SUPABASE_URL set"
fi
if [ -n "$SUPABASE_ANON_KEY" ]; then
    railway variables set SUPABASE_ANON_KEY="$SUPABASE_ANON_KEY"
    echo "  ✓ SUPABASE_ANON_KEY set"
fi
if [ -n "$SUPABASE_SERVICE_KEY" ]; then
    railway variables set SUPABASE_SERVICE_KEY="$SUPABASE_SERVICE_KEY"
    echo "  ✓ SUPABASE_SERVICE_KEY set"
fi
if [ -n "$SUPABASE_JWT_SECRET" ]; then
    railway variables set SUPABASE_JWT_SECRET="$SUPABASE_JWT_SECRET"
    echo "  ✓ SUPABASE_JWT_SECRET set"
fi

# AI Providers
if [ -n "$GOOGLE_API_KEY" ]; then
    railway variables set GOOGLE_API_KEY="$GOOGLE_API_KEY"
    echo "  ✓ GOOGLE_API_KEY set"
fi
if [ -n "$ANTHROPIC_API_KEY" ]; then
    railway variables set ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY"
    echo "  ✓ ANTHROPIC_API_KEY set"
fi

# Deploy
echo ""
echo "=== Deploying to Railway ==="
railway up --detach

# Get deployment URL
echo ""
echo "=== Deployment Started ==="
echo "Waiting for deployment URL..."
sleep 5

RAILWAY_URL=$(railway status 2>/dev/null | grep -o 'https://[^[:space:]]*' | head -1)
if [ -n "$RAILWAY_URL" ]; then
    echo ""
    echo "=============================================="
    echo "SUCCESS! Deployment started."
    echo "=============================================="
    echo "Railway URL: $RAILWAY_URL"
    echo "Health Check: $RAILWAY_URL/health"
    echo "API Docs: $RAILWAY_URL/docs"
    echo ""
    echo "=== Next Steps ==="
    echo "1. Wait 2-3 minutes for build to complete"
    echo "2. Test: curl $RAILWAY_URL/health"
    echo "3. Update Vercel NEXT_PUBLIC_API_URL to: $RAILWAY_URL"
else
    echo ""
    echo "Deployment started! Check Railway dashboard for URL."
    echo "Run 'railway status' to check deployment status."
fi
