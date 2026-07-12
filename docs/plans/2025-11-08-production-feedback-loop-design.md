# Production Deployment with Automated Feedback Loop

**Date**: November 8, 2025
**Status**: Design Approved
**Goal**: Deploy AI Cost Optimizer locally with PostgreSQL and implement automated learning pipeline that improves routing from user feedback

---

## Context

**Current State**: Phase 2 complete - Auto-routing with learning intelligence working, 42 tests passing, SQLite database

**Target State**: Production-ready local deployment with automated feedback loop that retrains routing weekly based on quality ratings

**User Journey**: Personal use initially, architected for future SaaS growth

**Timeline**: 2-3 weeks

---

## Architecture Overview

### Three-Component System

**1. Production API Service** (FastAPI + PostgreSQL)

- Docker container running uvicorn
- PostgreSQL replaces SQLite for production persistence
- New `/feedback` endpoint captures quality ratings
- Existing endpoints unchanged: `/complete`, `/recommendation`, `/routing/metrics`

**2. Learning Pipeline** (Background retraining)

- Python script: `app/learning/feedback_trainer.py`
- Runs weekly via cron or scheduler
- Analyzes feedback, computes confidence-weighted quality scores
- Updates routing recommendations when confidence thresholds met
- Logs all retraining runs with before/after metrics

**3. Docker Compose Orchestration**

- PostgreSQL container with persistent volume
- FastAPI container with health checks and auto-restart
- pgAdmin container for database management (optional)
- Networked services, environment-based configuration

**Data Flow**: User submits prompt → RoutingEngine decides → Provider responds → User rates quality → Feedback stored → Weekly retraining updates routing → Improved decisions for similar prompts

---

## Database Schema

### New Tables

**1. response_feedback**

Stores user quality ratings linked to routing decisions.

```sql
CREATE TABLE response_feedback (
    id SERIAL PRIMARY KEY,
    request_id TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,

    -- User ratings
    quality_score INTEGER NOT NULL,     -- 1-5 stars
    is_correct BOOLEAN,                 -- Response correctness
    is_helpful BOOLEAN,

    -- Context for learning
    prompt_pattern TEXT,
    selected_provider TEXT,
    selected_model TEXT,
    complexity_score REAL,

    -- Metadata
    user_id TEXT,
    session_id TEXT,
    comment TEXT,

    FOREIGN KEY (request_id) REFERENCES routing_metrics(request_id)
);

CREATE INDEX idx_feedback_pattern ON response_feedback(prompt_pattern);
CREATE INDEX idx_feedback_model ON response_feedback(selected_model);
CREATE INDEX idx_feedback_timestamp ON response_feedback(timestamp);
```

**2. model_performance_history**

Tracks learned performance metrics over time.

```sql
CREATE TABLE model_performance_history (
    id SERIAL PRIMARY KEY,
    pattern TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,

    -- Computed from feedback
    avg_quality_score REAL,
    correctness_rate REAL,
    sample_count INTEGER,
    confidence_level TEXT,

    -- Cost tracking
    avg_cost REAL,
    total_cost REAL,

    -- Metadata
    updated_at TIMESTAMP NOT NULL,
    retraining_run_id TEXT,

    UNIQUE(pattern, provider, model, retraining_run_id)
);
```

### Migration Strategy

1. Export SQLite data: `requests`, `routing_metrics`, `response_cache`
2. Start PostgreSQL container
3. Run Alembic migrations to create new schema
4. Import SQLite data with schema conversion script
5. Add new feedback tables
6. Verify data integrity

---

## Feedback Collection

### API Endpoint

```
POST /feedback
Content-Type: application/json

{
    "request_id": "abc123",
    "quality_score": 4,        # Required: 1-5
    "is_correct": true,        # Required: boolean
    "comment": "Good but verbose"  # Optional
}

Response:
{
    "status": "recorded",
    "feedback_id": 789,
    "message": "Thank you for feedback"
}
```

### Feedback Types Collected

- **Quality score** (1-5 stars): Granular rating for learning
- **Response correctness** (boolean): Critical for model-topic matching
- Optional comment field for qualitative insights

---

## Automated Learning Pipeline

### Core Component: FeedbackTrainer

**File**: `app/learning/feedback_trainer.py`

**Purpose**: Retrain routing recommendations from user feedback with confidence-based thresholds

**Confidence Thresholds**:

- **HIGH**: ≥10 samples, avg quality ≥4.0, correctness ≥80%
- **MEDIUM**: ≥5 samples, avg quality ≥3.5, correctness ≥70%
- **LOW**: <5 samples or poor metrics → No routing change

**Retraining Logic**:

```python
class FeedbackTrainer:
    HIGH_CONFIDENCE_THRESHOLD = 10
    MEDIUM_CONFIDENCE_THRESHOLD = 5
    MIN_QUALITY_SCORE = 3.5
    MIN_CORRECTNESS_RATE = 0.7

    def retrain(self):
        """Run weekly retraining cycle."""
        # 1. Aggregate feedback by pattern + model
        performance_data = self._aggregate_feedback()

        # 2. Compute confidence levels
        for pattern, model_stats in performance_data.items():
            confidence = self._calculate_confidence(
                sample_count=model_stats['count'],
                quality_score=model_stats['avg_quality'],
                correctness_rate=model_stats['correctness']
            )

            # 3. Update routing only if meets threshold
            if confidence in ['high', 'medium']:
                self._update_routing_weights(pattern, model_stats)

        # 4. Log retraining metrics
        self._log_retraining_run(before_metrics, after_metrics)
```

**What Updates**:

- `QueryPatternAnalyzer` internal weights and scores
- `model_performance_history` table with new computed metrics
- Routing recommendations for each pattern-model pair

**Safety Mechanisms**:

- Never degrade confidence without evidence
- Keep last 3 retraining snapshots for rollback
- Alert if quality drops >10% after retraining
- Dry-run mode for testing before applying

**Scheduling Options**:

1. Cron job: `0 2 * * 0` (Sundays at 2 AM)
2. Python APScheduler: Background thread in FastAPI
3. Manual trigger: `/admin/retrain` endpoint for testing

---

## Docker Deployment

### docker-compose.yml

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: optimizer-db
    environment:
      POSTGRES_DB: optimizer
      POSTGRES_USER: optimizer_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./migrations:/docker-entrypoint-initdb.d
    ports:
      - '5432:5432'
    healthcheck:
      test: ['CMD-READY', 'pg_isready', '-U', 'optimizer_user']
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  api:
    build: .
    container_name: optimizer-api
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://optimizer_user:${DB_PASSWORD}@postgres:5432/optimizer
      GOOGLE_API_KEY: ${GOOGLE_API_KEY}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      OPENROUTER_API_KEY: ${OPENROUTER_API_KEY}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    ports:
      - '8000:8000'
    volumes:
      - ./app:/app/app
    restart: unless-stopped
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000

  pgadmin:
    image: dpage/pgadmin4:latest
    container_name: optimizer-pgadmin
    environment:
      PGADMIN_DEFAULT_EMAIL: ${PGADMIN_EMAIL:-admin@optimizer.local}
      PGADMIN_DEFAULT_PASSWORD: ${PGADMIN_PASSWORD}
    ports:
      - '5050:80'
    depends_on:
      - postgres
    restart: unless-stopped

volumes:
  postgres_data:
    driver: local
```

### Updated Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY migrations/ ./migrations/

HEALTHCHECK --interval=30s --timeout=3s \
  CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Configuration

**.env.production**:

```bash
# Database
DB_PASSWORD=your_secure_password
DATABASE_URL=postgresql://optimizer_user:${DB_PASSWORD}@localhost:5432/optimizer

# API Keys
GOOGLE_API_KEY=your_key
ANTHROPIC_API_KEY=your_key
OPENROUTER_API_KEY=your_key

# Optional
PGADMIN_EMAIL=admin@optimizer.local
PGADMIN_PASSWORD=admin_password
LOG_LEVEL=INFO
```

### Startup Commands

```bash
# First time setup
docker-compose up -d postgres
./scripts/migrate_to_postgres.sh
docker-compose up -d

# Daily use
docker-compose up -d          # Start all services
docker-compose logs -f api    # Watch logs
docker-compose down           # Stop all services
```

---

## New API Endpoints

### Feedback Submission

```
POST /feedback
Body: {request_id, quality_score, is_correct, comment}
Response: {status, feedback_id, message}
```

### Admin Monitoring

```
GET /admin/feedback/summary
Returns: Feedback stats (avg quality per model, sample counts)

GET /admin/learning/status
Returns: Last retraining run, next scheduled run, confidence levels

POST /admin/learning/retrain?dry_run=true
Returns: Preview of routing changes before applying

GET /admin/performance/trends
Returns: Quality trends over time by pattern/model
```

---

## Monitoring & Observability

### Learning Dashboard (CLI)

**File**: `scripts/learning_dashboard.py`

Displays current learning state:

- Total feedback collected
- Average quality score across all models
- Confidence level distribution (high/medium/low)
- Top performing models per pattern
- Cost savings from learning-based routing

### Backup Strategy

**Automated daily backups** via cron:

```bash
#!/bin/bash
# scripts/backup_db.sh
# crontab: 0 3 * * * /app/scripts/backup_db.sh

BACKUP_DIR=/backups
DATE=$(date +%Y%m%d_%H%M%S)

docker exec optimizer-db pg_dump -U optimizer_user optimizer \
  | gzip > $BACKUP_DIR/optimizer_$DATE.sql.gz

# Retain 30 days
find $BACKUP_DIR -name "optimizer_*.sql.gz" -mtime +30 -delete
```

---

## Testing Strategy

### Integration Tests

**Test feedback loop end-to-end**:

```python
def test_feedback_loop_end_to_end():
    # 1. Submit request, get routing decision
    response = client.post("/complete", json={
        "prompt": "Debug Python code",
        "auto_route": True
    })
    request_id = response.json()["request_id"]

    # 2. Submit positive feedback
    client.post("/feedback", json={
        "request_id": request_id,
        "quality_score": 5,
        "is_correct": True
    })

    # 3. Run retraining (dry run)
    retrain_result = client.post("/admin/learning/retrain?dry_run=true")

    # 4. Verify routing weights would update
    assert retrain_result.json()["changes_preview"] is not None
```

### Unit Tests

**Test confidence threshold enforcement**:

```python
def test_confidence_threshold_enforcement():
    trainer = FeedbackTrainer()

    # Add only 3 samples (below threshold of 5)
    add_feedback_samples(count=3, quality=5.0)

    before_weights = get_routing_weights("code")
    trainer.retrain()
    after_weights = get_routing_weights("code")

    # Should NOT change with insufficient samples
    assert before_weights == after_weights
```

---

## Gradual Rollout Plan

**Week 1: Deploy with collection only**

- Deploy Docker setup with PostgreSQL
- Enable `/feedback` endpoint
- Collect feedback, no retraining yet
- Verify feedback data looks correct

**Week 2: Manual retraining**

- Run first retraining in dry-run mode
- Review proposed routing changes
- Manually approve and apply if reasonable
- Monitor quality metrics

**Week 3: Automated retraining**

- Enable weekly automated retraining
- Monitor for quality degradation
- Tune confidence thresholds if needed

**Week 4+: Production operation**

- Monitor quality improvements
- Adjust thresholds based on data volume
- Prepare for multi-user features

---

## Success Metrics

| Metric                           | Baseline | Target           | Timeline |
| -------------------------------- | -------- | ---------------- | -------- |
| Feedback collection rate         | 0%       | 50%+ of requests | Week 1   |
| High-confidence patterns         | 0        | 5+ patterns      | Week 3   |
| Avg quality score                | N/A      | 4.0+ / 5.0       | Week 4   |
| Learning-based cost savings      | 0%       | 10%+ additional  | Week 6   |
| Routing accuracy (correct model) | TBD      | 80%+             | Week 8   |

---

## Future Enhancements (SaaS Preparation)

After initial deployment proves stable:

1. **Multi-tenant support**: User isolation, per-user tracking
2. **A/B testing framework**: Compare routing strategies statistically
3. **Real-time quality monitoring**: Drift detection, automatic alerts
4. **Advanced caching**: Redis for distributed caching
5. **Rate limiting**: Per-user quotas and cost controls

---

## Dependencies

### New Python Packages

Add to `requirements.txt`:

```
psycopg2-binary>=2.9.9    # PostgreSQL adapter
APScheduler>=3.10.4       # Background job scheduling
```

### New System Requirements

- Docker 20.10+
- Docker Compose 2.0+
- PostgreSQL 15+ (via Docker)

---

## Implementation Handoff

Ready to implement? Next steps:

1. **Create git worktree**: Isolated workspace for development
2. **Write implementation plan**: Detailed task breakdown with TDD approach
3. **Execute in batches**: Implement with code review checkpoints

Estimated implementation time: **2 weeks** (6-8 tasks at ~2 days each)
