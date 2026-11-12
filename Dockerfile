# AI Cost Optimizer - Production Dockerfile (Supabase Edition)
# Optimized for linux/amd64 deployment (RunPod, AWS, GCP, etc.)

FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Copy requirements first for better Docker layer caching
COPY --chown=appuser:appuser requirements.txt requirements-embeddings.txt ./

# Set to 1 to add semantic-cache embeddings (sentence-transformers with CPU-only PyTorch).
# The default image leaves them out: the NVIDIA CUDA wheels alone are several GB.
ARG WITH_EMBEDDINGS=0

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt
RUN if [ "$WITH_EMBEDDINGS" = "1" ]; then \
      TORCH_VERSION="$(sed -n 's/^torch==\([^ ;]*\).*/\1/p' requirements-embeddings.txt)" && \
      pip install --no-cache-dir "torch==${TORCH_VERSION}" \
        --index-url https://download.pytorch.org/whl/cpu && \
      grep -vE '^(torch|triton|nvidia-)' requirements-embeddings.txt > /tmp/requirements-rest.txt && \
      pip install --no-cache-dir -r /tmp/requirements-rest.txt && \
      rm /tmp/requirements-rest.txt; \
    fi

# Copy application code
COPY --chown=appuser:appuser pyproject.toml ./
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser migrations/ ./migrations/
COPY --chown=appuser:appuser .env.example ./

# Switch to non-root user
USER appuser

# Health check - increased timeouts for ML model loading
HEALTHCHECK --interval=30s --timeout=30s --start-period=120s --retries=5 \
  CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Environment variables (override these in production)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LOG_LEVEL=INFO \
    PORT=8000

# Default command
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
