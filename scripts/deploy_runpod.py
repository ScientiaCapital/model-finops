#!/usr/bin/env python3
"""
RunPod Deployment Script for AI Cost Optimizer
Deploys the FastAPI backend to RunPod with all required environment variables.
"""

import os
import sys
from dotenv import load_dotenv

# Load .env from project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)

import runpod

# Configure RunPod API key
runpod.api_key = os.getenv("RUNPOD_API_KEY")

if not runpod.api_key:
    print("ERROR: RUNPOD_API_KEY not found in .env")
    sys.exit(1)

# Configuration
IMAGE_NAME = "ghcr.io/scientiacapital/ai-cost-optimizer:latest"
POD_NAME = "ai-cost-optimizer"
VERCEL_URL = "https://ai-cost-optimizer-scientia-capital.vercel.app"

# GPU Configuration
# Options: "NVIDIA GeForce RTX 4090", "NVIDIA RTX 4000 Ada", "NVIDIA L40"
GPU_TYPE = "NVIDIA GeForce RTX 4090"  # 24GB VRAM, latest consumer GPU

# Environment variables for the pod
env_vars = {
    # Configuration
    "PORT": "8000",
    "LOG_LEVEL": "INFO",
    "EMBEDDING_DEVICE": "cpu",  # Docker image uses python:3.11-slim without CUDA
    "TORCH_HOME": "/app/model_cache",
    "HF_HOME": "/app/model_cache",  # HuggingFace cache
    "SENTENCE_TRANSFORMERS_HOME": "/app/model_cache",  # sentence-transformers cache
    "CORS_ORIGINS": VERCEL_URL,

    # Supabase
    "SUPABASE_URL": os.getenv("SUPABASE_URL", ""),
    "SUPABASE_ANON_KEY": os.getenv("SUPABASE_ANON_KEY", ""),
    "SUPABASE_SERVICE_KEY": os.getenv("SUPABASE_SERVICE_KEY", ""),
    "SUPABASE_JWT_SECRET": os.getenv("SUPABASE_JWT_SECRET", ""),

    # AI Providers
    "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY", ""),
    "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY", ""),
}

# Validate required env vars
missing = [k for k, v in env_vars.items() if not v and k not in ["LOG_LEVEL", "PORT", "EMBEDDING_DEVICE", "TORCH_HOME", "CORS_ORIGINS"]]
if missing:
    print(f"ERROR: Missing required environment variables: {missing}")
    sys.exit(1)

def list_gpus():
    """List available GPU types on RunPod."""
    print("\n=== Available GPU Types ===")
    gpus = runpod.get_gpus()
    for gpu in gpus[:10]:  # Show first 10
        print(f"  {gpu['id']}: {gpu.get('displayName', 'N/A')} - {gpu.get('memoryInGb', '?')}GB")
    print("  ... (more available)")

def deploy_pod():
    """Deploy the AI Cost Optimizer to RunPod."""
    print(f"\n=== Deploying {POD_NAME} ===")
    print(f"Image: {IMAGE_NAME}")
    print(f"GPU: {GPU_TYPE} (~$0.20/hr)")
    print(f"CORS: {VERCEL_URL}")

    try:
        # Create GPU pod (RunPod SDK requires GPU selection)
        pod = runpod.create_pod(
            name=POD_NAME,
            image_name=IMAGE_NAME,
            gpu_type_id=GPU_TYPE,  # Cheapest GPU option
            cloud_type="ALL",  # Try any available cloud type
            container_disk_in_gb=20,
            volume_in_gb=10,
            volume_mount_path="/app/model_cache",
            ports="8000/http",
            env=env_vars,
        )

        pod_id = pod['id']
        pod_url = f"https://{pod_id}-8000.proxy.runpod.net"

        print(f"\n=== SUCCESS ===")
        print(f"Pod ID: {pod_id}")
        print(f"Pod URL: {pod_url}")
        print(f"Health Check: {pod_url}/health")
        print(f"API Docs: {pod_url}/docs")
        print(f"\n=== Next Steps ===")
        print(f"1. Wait 1-2 minutes for pod to start")
        print(f"2. Test: curl {pod_url}/health")
        print(f"3. Update Vercel NEXT_PUBLIC_API_URL to: {pod_url}")
        print(f"\n=== Management Commands ===")
        print(f"Stop pod:      runpod.stop_pod('{pod_id}')")
        print(f"Resume pod:    runpod.resume_pod('{pod_id}')")
        print(f"Terminate pod: runpod.terminate_pod('{pod_id}')")

        return pod_id, pod_url

    except Exception as e:
        print(f"\nERROR: Failed to deploy pod: {e}")
        print("\nTroubleshooting:")
        print("  1. Check RUNPOD_API_KEY is valid")
        print("  2. Check RunPod account has credits")
        print("  3. Try deploying via RunPod web UI first")
        sys.exit(1)

def main():
    print("=" * 50)
    print("AI Cost Optimizer - RunPod Deployment")
    print("=" * 50)

    if len(sys.argv) > 1 and sys.argv[1] == "--list-gpus":
        list_gpus()
        return

    deploy_pod()

if __name__ == "__main__":
    main()
