#!/usr/bin/env python3
"""
RunPod Auto-Retry Deployment Script
Keeps trying to deploy until a GPU becomes available.
Usage: python3 scripts/runpod_deploy_retry.py
"""

import os
import sys
import time
import urllib.request
import urllib.error
import json
from datetime import datetime

# Load environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API_KEY = os.environ.get('RUNPOD_API_KEY')
if not API_KEY:
    print("ERROR: Set RUNPOD_API_KEY environment variable")
    print("Run: source ~/.zshrc")
    sys.exit(1)

# Environment variables for the pod
ENV_VARS = {
    "PORT": "8000",
    "LOG_LEVEL": "INFO",
    "EMBEDDING_DEVICE": "cpu",
    "TORCH_HOME": "/runpod-volume/model_cache",
    "CORS_ORIGINS": "https://ai-cost-optimizer-scientia-capital.vercel.app",
    "SUPABASE_URL": os.environ.get("SUPABASE_URL", ""),
    "SUPABASE_ANON_KEY": os.environ.get("SUPABASE_ANON_KEY", ""),
    "SUPABASE_SERVICE_KEY": os.environ.get("SUPABASE_SERVICE_KEY", ""),
    "SUPABASE_JWT_SECRET": os.environ.get("SUPABASE_JWT_SECRET", ""),
    "GOOGLE_API_KEY": os.environ.get("GOOGLE_API_KEY", ""),
    "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", ""),
}

# GPU types to try (cheapest first)
GPU_TYPES = [
    "RTX A4000", "RTX A5000", "RTX 3080", "RTX 3090",
    "RTX 4090", "A40", "L4", "RTX A6000"
]

def graphql_query(query, variables=None):
    url = 'https://api.runpod.io/graphql'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {API_KEY}'
    }
    payload = {'query': query}
    if variables:
        payload['variables'] = variables

    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": e.read().decode()}
    except Exception as e:
        return {"error": str(e)}

def try_deploy():
    """Try to deploy to any available GPU."""
    env_list = [{"key": k, "value": v} for k, v in ENV_VARS.items() if v]

    create_query = '''
    mutation CreatePod($input: PodFindAndDeployOnDemandInput!) {
      podFindAndDeployOnDemand(input: $input) {
        id
        name
        costPerHr
        machine { gpuDisplayName }
      }
    }
    '''

    for gpu in GPU_TYPES:
        vars = {
            "input": {
                "name": "ai-cost-optimizer",
                "imageName": "ghcr.io/scientiacapital/ai-cost-optimizer:latest",
                "gpuTypeId": gpu,
                "gpuCount": 1,
                "cloudType": "ALL",
                "volumeInGb": 10,
                "containerDiskInGb": 20,
                "volumeMountPath": "/runpod-volume",
                "ports": "8000/http",
                "env": env_list,
            }
        }

        result = graphql_query(create_query, vars)

        if 'data' in result and result['data'].get('podFindAndDeployOnDemand'):
            pod = result['data']['podFindAndDeployOnDemand']
            return pod

    return None

def main():
    print("=" * 60)
    print("AI Cost Optimizer - RunPod Auto-Retry Deployment")
    print("=" * 60)
    print(f"Image: ghcr.io/scientiacapital/ai-cost-optimizer:latest")
    print(f"Trying GPUs: {', '.join(GPU_TYPES)}")
    print("\nPress Ctrl+C to stop\n")

    attempt = 0
    while True:
        attempt += 1
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] Attempt {attempt}...", end=" ", flush=True)

        pod = try_deploy()

        if pod:
            pod_id = pod['id']
            gpu = pod.get('machine', {}).get('gpuDisplayName', 'Unknown')
            cost = pod.get('costPerHr', '?')

            print(f"\n\n{'='*60}")
            print("🎉 SUCCESS! Pod deployed!")
            print(f"{'='*60}")
            print(f"Pod ID:  {pod_id}")
            print(f"GPU:     {gpu}")
            print(f"Cost:    ${cost}/hr")
            print(f"\n📍 URLs (wait 2-3 min for startup):")
            print(f"Health:  https://{pod_id}-8000.proxy.runpod.net/health")
            print(f"API:     https://{pod_id}-8000.proxy.runpod.net/docs")
            print(f"{'='*60}\n")

            # Save pod info
            with open("/tmp/runpod_pod_info.txt", "w") as f:
                f.write(f"POD_ID={pod_id}\n")
                f.write(f"POD_URL=https://{pod_id}-8000.proxy.runpod.net\n")

            return 0

        print("No GPUs available. Retrying in 60s...")
        time.sleep(60)

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nStopped by user.")
        sys.exit(1)
