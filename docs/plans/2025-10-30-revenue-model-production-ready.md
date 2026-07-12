# AI Cost Optimizer v2.0: Revenue Model + Production Ready Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build revenue-validating features with production-grade reliability to prove business value and scale.

**Architecture:** Dual-track development where every feature demonstrates business value AND maintains production reliability. Track 1 validates revenue through metrics, multi-user, and analytics. Track 2 ensures production-ready through testing, monitoring, and resilience.

**Tech Stack:** FastAPI, SQLite/PostgreSQL, pytest, locust, Prometheus, Streamlit, alembic, tenacity, structlog

---

## Phase 1: Foundation & Testing Infrastructure (Days 1-3)

### Task 1.1: Set Up Testing Framework

**Files:**

- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_router.py`
- Modify: `requirements.txt`

**Step 1: Add testing dependencies to requirements.txt**

```txt
# Testing
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0
pytest-mock>=3.11.0
httpx>=0.24.1  # for async test client
```

**Step 2: Create pytest configuration and fixtures**

Create `tests/conftest.py`:

```python
import pytest
import asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db

# Test database
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def test_db():
    """Create a fresh database for each test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(test_db):
    """Get test client with clean database."""
    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
```

**Step 3: Write first TDD test for router**

Create `tests/test_router.py`:

```python
import pytest
from app.router import Router
from app.providers import init_providers

@pytest.fixture
def router():
    providers = init_providers()
    return Router(providers)

def test_select_provider_simple_query(router):
    """Test that simple queries route to cheap models."""
    provider_name, model_name, provider = router.select_provider(
        complexity="simple",
        prompt="What is Python?"
    )

    # Should select cheap tier
    assert provider_name in ["google", "cerebras"]
    assert model_name in ["gemini-2.0-flash-exp", "gemini-1.5-flash", "llama3.1-8b"]

def test_select_provider_complex_query(router):
    """Test that complex queries route to premium models."""
    provider_name, model_name, provider = router.select_provider(
        complexity="premium",
        prompt="Design a distributed system architecture for..."
    )

    # Should select premium tier
    assert provider_name in ["anthropic", "openrouter"]
```

**Step 4: Run tests to establish baseline**

```bash
pytest tests/ -v --cov=app --cov-report=term-missing
```

Expected: Tests pass, coverage report shows what's tested

**Step 5: Commit**

```bash
git add tests/ requirements.txt
git commit -m "test: add pytest framework and initial router tests"
```

---

### Task 1.2: Add Performance Testing Suite

**Files:**

- Create: `tests/performance/__init__.py`
- Create: `tests/performance/locustfile.py`
- Create: `tests/performance/test_benchmarks.py`
- Modify: `requirements.txt`

**Step 1: Add performance testing dependencies**

```txt
# Performance testing
locust>=2.15.0
pytest-benchmark>=4.0.0
```

**Step 2: Create Locust load testing file**

Create `tests/performance/locustfile.py`:

```python
from locust import HttpUser, task, between
import random

class CostOptimizerUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        """Set up test data."""
        self.prompts = [
            "What is Python?",
            "Explain quantum computing",
            "Write a function to calculate fibonacci",
            "Design a microservices architecture",
        ]

    @task(3)
    def complete_simple_prompt(self):
        """Test simple prompt completion (60% of load)."""
        self.client.post("/v1/complete", json={
            "prompt": random.choice(self.prompts[:2]),
            "max_tokens": 200
        })

    @task(2)
    def complete_medium_prompt(self):
        """Test medium complexity prompts (30% of load)."""
        self.client.post("/v1/complete", json={
            "prompt": self.prompts[2],
            "max_tokens": 500
        })

    @task(1)
    def complete_complex_prompt(self):
        """Test complex prompts (10% of load)."""
        self.client.post("/v1/complete", json={
            "prompt": self.prompts[3],
            "max_tokens": 1000
        })

    @task(1)
    def get_providers(self):
        """Test listing providers."""
        self.client.get("/v1/providers")

    @task(1)
    def get_usage_stats(self):
        """Test usage statistics."""
        self.client.get("/v1/usage")
```

**Step 3: Create benchmark tests**

Create `tests/performance/test_benchmarks.py`:

```python
import pytest
from app.router import Router
from app.complexity import score_complexity
from app.providers import init_providers

@pytest.fixture(scope="module")
def router():
    return Router(init_providers())

def test_complexity_scoring_benchmark(benchmark):
    """Benchmark complexity scoring performance."""
    prompt = "Write a Python function to implement binary search"

    result = benchmark(score_complexity, prompt)

    # Should complete in under 10ms
    assert benchmark.stats['mean'] < 0.01

def test_provider_selection_benchmark(benchmark, router):
    """Benchmark provider selection performance."""

    def select():
        return router.select_provider("medium", "Explain quantum computing")

    result = benchmark(select)

    # Should complete in under 50ms
    assert benchmark.stats['mean'] < 0.05
```

**Step 4: Run performance tests**

```bash
# Run benchmarks
pytest tests/performance/test_benchmarks.py -v

# Run load test (requires server running)
locust -f tests/performance/locustfile.py --headless -u 10 -r 2 -t 30s --host=http://localhost:8000
```

**Step 5: Commit**

```bash
git add tests/performance/ requirements.txt
git commit -m "test: add locust load testing and performance benchmarks"
```

---

### Task 1.3: Database Migrations System

**Files:**

- Create: `migrations/` directory via alembic
- Create: `migrations/versions/001_initial_schema.py`
- Create: `migrations/versions/002_add_value_metrics.py`
- Modify: `requirements.txt`

**Step 1: Add alembic dependency**

```txt
# Database migrations
alembic>=1.12.0
```

**Step 2: Initialize alembic**

```bash
alembic init migrations
```

**Step 3: Configure alembic**

Modify `migrations/env.py`:

```python
from app.database import Base
from app.models import *  # Import all models

target_metadata = Base.metadata
```

Modify `alembic.ini`:

```ini
sqlalchemy.url = sqlite:///./optimizer.db
```

**Step 4: Create initial migration**

```bash
alembic revision -m "initial schema" --autogenerate
```

Edit the generated migration to include all current tables:

- requests
- response_cache
- response_feedback
- budget_config

**Step 5: Create value_metrics migration**

```bash
alembic revision -m "add value_metrics table"
```

```python
def upgrade():
    op.create_table(
        'value_metrics',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('query_type', sa.String()),
        sa.Column('complexity', sa.String()),
        sa.Column('selected_provider', sa.String()),
        sa.Column('selected_model', sa.String()),
        sa.Column('selected_cost', sa.Float()),
        sa.Column('baseline_provider', sa.String(), default='openai'),
        sa.Column('baseline_model', sa.String(), default='gpt-4'),
        sa.Column('baseline_cost', sa.Float()),
        sa.Column('savings', sa.Float()),  # baseline_cost - selected_cost
    )
    op.create_index('ix_value_metrics_user_timestamp', 'value_metrics', ['user_id', 'timestamp'])

def downgrade():
    op.drop_index('ix_value_metrics_user_timestamp')
    op.drop_table('value_metrics')
```

**Step 6: Run migrations**

```bash
alembic upgrade head
```

**Step 7: Commit**

```bash
git add migrations/ alembic.ini requirements.txt
git commit -m "feat: add alembic database migration system"
```

---

## Phase 2: Value Metrics & Analytics (Days 4-7)

### Task 2.1: Value Metrics Tracking System

**Files:**

- Create: `app/value_metrics.py`
- Create: `app/models/value_metric.py`
- Modify: `app/database.py`
- Create: `tests/test_value_metrics.py`

**Step 1: Write test for value metrics tracking**

Create `tests/test_value_metrics.py`:

```python
import pytest
from decimal import Decimal
from app.value_metrics import ValueMetricsTracker

@pytest.fixture
def tracker(test_db):
    return ValueMetricsTracker()

def test_calculate_savings_vs_gpt4(tracker):
    """Test savings calculation against GPT-4 baseline."""
    # Selected: Gemini Flash (free)
    savings = tracker.calculate_savings(
        selected_provider="google",
        selected_model="gemini-1.5-flash",
        selected_cost=0.000,
        tokens_in=100,
        tokens_out=200
    )

    # vs GPT-4 baseline: ~$0.03 per 1K tokens
    assert savings > 0.005  # Saved at least $0.005
    assert savings < 0.010  # Reasonable upper bound

def test_record_value_metric(tracker):
    """Test recording a value metric."""
    tracker.record_metric(
        user_id="test_user",
        query_type="code_generation",
        complexity="medium",
        selected_provider="google",
        selected_model="gemini-1.5-pro",
        selected_cost=0.00125,
        tokens_in=50,
        tokens_out=250
    )

    report = tracker.get_user_report("test_user")
    assert report['total_savings'] > 0
    assert report['total_requests'] == 1
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_value_metrics.py -v
```

Expected: FAIL - module not found

**Step 3: Implement value metrics model**

Create `app/models/value_metric.py`:

```python
from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime
from app.database import Base

class ValueMetric(Base):
    __tablename__ = "value_metrics"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    query_type = Column(String)
    complexity = Column(String)
    selected_provider = Column(String)
    selected_model = Column(String)
    selected_cost = Column(Float)
    baseline_provider = Column(String, default="openai")
    baseline_model = Column(String, default="gpt-4")
    baseline_cost = Column(Float)
    savings = Column(Float)
```

**Step 4: Implement value metrics tracker**

Create `app/value_metrics.py`:

```python
from decimal import Decimal
from typing import Dict, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models.value_metric import ValueMetric
from app.database import get_db

class ValueMetricsTracker:
    """Track cost savings and ROI metrics."""

    # GPT-4 pricing as baseline (per 1M tokens)
    BASELINE_COSTS = {
        "gpt-4": {"input": 30.0, "output": 60.0},
        "claude-opus": {"input": 15.0, "output": 75.0},
    }

    def calculate_savings(
        self,
        selected_provider: str,
        selected_model: str,
        selected_cost: float,
        tokens_in: int,
        tokens_out: int,
        baseline: str = "gpt-4"
    ) -> float:
        """Calculate savings vs baseline model."""
        # Calculate what baseline would cost
        baseline_pricing = self.BASELINE_COSTS[baseline]
        baseline_cost = (
            (tokens_in / 1_000_000) * baseline_pricing["input"] +
            (tokens_out / 1_000_000) * baseline_pricing["output"]
        )

        return baseline_cost - selected_cost

    def record_metric(
        self,
        user_id: str,
        query_type: str,
        complexity: str,
        selected_provider: str,
        selected_model: str,
        selected_cost: float,
        tokens_in: int,
        tokens_out: int,
        db: Session = None
    ):
        """Record a value metric."""
        if db is None:
            db = next(get_db())

        savings = self.calculate_savings(
            selected_provider, selected_model, selected_cost,
            tokens_in, tokens_out
        )

        baseline_pricing = self.BASELINE_COSTS["gpt-4"]
        baseline_cost = (
            (tokens_in / 1_000_000) * baseline_pricing["input"] +
            (tokens_out / 1_000_000) * baseline_pricing["output"]
        )

        metric = ValueMetric(
            user_id=user_id,
            query_type=query_type,
            complexity=complexity,
            selected_provider=selected_provider,
            selected_model=selected_model,
            selected_cost=selected_cost,
            baseline_cost=baseline_cost,
            savings=savings
        )

        db.add(metric)
        db.commit()

    def get_user_report(self, user_id: str, days: int = 30) -> Dict:
        """Get value report for user."""
        db = next(get_db())

        since = datetime.utcnow() - timedelta(days=days)
        metrics = db.query(ValueMetric).filter(
            ValueMetric.user_id == user_id,
            ValueMetric.timestamp >= since
        ).all()

        total_savings = sum(m.savings for m in metrics)
        total_spend = sum(m.selected_cost for m in metrics)

        return {
            "user_id": user_id,
            "period_days": days,
            "total_requests": len(metrics),
            "total_spend": total_spend,
            "total_savings": total_savings,
            "roi_percent": (total_savings / total_spend * 100) if total_spend > 0 else 0,
            "avg_savings_per_request": total_savings / len(metrics) if metrics else 0
        }
```

**Step 5: Run tests**

```bash
pytest tests/test_value_metrics.py -v
```

Expected: PASS

**Step 6: Integrate with router**

Modify `app/router.py` to record value metrics after each request:

```python
from app.value_metrics import ValueMetricsTracker

class Router:
    def __init__(self, providers):
        self.providers = providers
        self.value_tracker = ValueMetricsTracker()

    async def execute(self, prompt: str, max_tokens: int, user_id: str = "default"):
        # ... existing execution logic ...

        # Record value metric
        self.value_tracker.record_metric(
            user_id=user_id,
            query_type=self._infer_query_type(prompt),
            complexity=complexity,
            selected_provider=provider_name,
            selected_model=model_name,
            selected_cost=cost,
            tokens_in=result['tokens_in'],
            tokens_out=result['tokens_out']
        )

        return result
```

**Step 7: Commit**

```bash
git add app/value_metrics.py app/models/value_metric.py tests/test_value_metrics.py app/router.py
git commit -m "feat: add value metrics tracking system with ROI calculation"
```

---

### Task 2.2: Usage Analytics Dashboard (Streamlit)

**Files:**

- Create: `dashboard/app.py`
- Create: `dashboard/components/roi_chart.py`
- Create: `dashboard/components/provider_comparison.py`
- Create: `dashboard/requirements.txt`
- Create: `dashboard/README.md`

**Step 1: Create dashboard structure**

```bash
mkdir -p dashboard/components
```

**Step 2: Add Streamlit dependencies**

Create `dashboard/requirements.txt`:

```txt
streamlit>=1.28.0
plotly>=5.17.0
pandas>=2.1.0
```

**Step 3: Create main dashboard app**

Create `dashboard/app.py`:

```python
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta
import sys
sys.path.append('..')

from app.database import get_db
from app.value_metrics import ValueMetricsTracker
from app.cost_tracker import CostTracker

st.set_page_config(
    page_title="AI Cost Optimizer Analytics",
    page_icon="💰",
    layout="wide"
)

# Sidebar
st.sidebar.title("AI Cost Optimizer")
st.sidebar.markdown("### Analytics Dashboard")

user_id = st.sidebar.text_input("User ID", value="default")
days = st.sidebar.slider("Time Period (days)", 1, 90, 30)

# Main content
st.title("💰 AI Cost Optimizer Analytics")

# Fetch data
tracker = ValueMetricsTracker()
cost_tracker = CostTracker()

report = tracker.get_user_report(user_id, days)
stats = cost_tracker.get_usage_stats()

# Top metrics
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Total Savings",
        f"${report['total_savings']:.2f}",
        f"{report['roi_percent']:.1f}% ROI"
    )

with col2:
    st.metric(
        "Total Spend",
        f"${report['total_spend']:.2f}",
        f"{report['total_requests']} requests"
    )

with col3:
    st.metric(
        "Avg Savings/Request",
        f"${report['avg_savings_per_request']:.4f}"
    )

with col4:
    st.metric(
        "Cache Hit Rate",
        f"{stats['cache']['hit_rate_percent']:.1f}%",
        f"${stats['cache']['total_savings']:.2f} saved"
    )

# Charts
st.markdown("---")

# ROI over time
st.subheader("Cost Savings Over Time")
# ... implement time series chart ...

# Provider comparison
st.subheader("Provider Efficiency Comparison")
# ... implement provider bar chart ...

# Complexity distribution
st.subheader("Query Complexity Distribution")
# ... implement pie chart ...
```

**Step 4: Create ROI chart component**

Create `dashboard/components/roi_chart.py`:

```python
import plotly.graph_objects as go
from datetime import datetime, timedelta

def create_roi_chart(metrics, days=30):
    """Create ROI trend chart."""
    # Group by date
    daily_savings = {}
    daily_spend = {}

    for metric in metrics:
        date = metric.timestamp.date()
        daily_savings[date] = daily_savings.get(date, 0) + metric.savings
        daily_spend[date] = daily_spend.get(date, 0) + metric.selected_cost

    dates = sorted(daily_savings.keys())
    savings = [daily_savings[d] for d in dates]
    spend = [daily_spend[d] for d in dates]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=dates,
        y=savings,
        name='Savings',
        marker_color='green'
    ))

    fig.add_trace(go.Bar(
        x=dates,
        y=spend,
        name='Spend',
        marker_color='blue'
    ))

    fig.update_layout(
        title="Daily Cost Savings vs Spend",
        xaxis_title="Date",
        yaxis_title="Amount ($)",
        barmode='group'
    )

    return fig
```

**Step 5: Test dashboard locally**

```bash
cd dashboard
pip install -r requirements.txt
streamlit run app.py
```

**Step 6: Commit**

```bash
git add dashboard/
git commit -m "feat: add Streamlit analytics dashboard with ROI visualization"
```

---

### Task 2.3: Cost Reports & Export

**Files:**

- Create: `app/reports.py`
- Create: `templates/cost_report.html`
- Modify: `app/main.py` (add report endpoints)
- Create: `tests/test_reports.py`

**Step 1: Write test for report generation**

Create `tests/test_reports.py`:

```python
import pytest
from app.reports import ReportGenerator

def test_generate_monthly_report():
    """Test monthly report generation."""
    generator = ReportGenerator()

    report = generator.generate_monthly_report(
        user_id="test_user",
        year=2025,
        month=10
    )

    assert "total_spend" in report
    assert "total_savings" in report
    assert "top_queries" in report
    assert "provider_breakdown" in report

def test_export_report_csv():
    """Test CSV export."""
    generator = ReportGenerator()

    csv_data = generator.export_to_csv(
        user_id="test_user",
        days=30
    )

    assert "timestamp" in csv_data
    assert "provider" in csv_data
    assert "cost" in csv_data
```

**Step 2: Implement report generator**

Create `app/reports.py`:

```python
import csv
from io import StringIO
from datetime import datetime, timedelta
from typing import Dict, List
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.value_metric import ValueMetric
from app.cost_tracker import CostTracker

class ReportGenerator:
    """Generate cost reports and exports."""

    def generate_monthly_report(self, user_id: str, year: int, month: int) -> Dict:
        """Generate comprehensive monthly report."""
        db = next(get_db())
        cost_tracker = CostTracker()

        # Get date range
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)

        # Query metrics
        metrics = db.query(ValueMetric).filter(
            ValueMetric.user_id == user_id,
            ValueMetric.timestamp >= start_date,
            ValueMetric.timestamp < end_date
        ).all()

        # Aggregate data
        total_spend = sum(m.selected_cost for m in metrics)
        total_savings = sum(m.savings for m in metrics)

        provider_breakdown = {}
        for metric in metrics:
            provider = metric.selected_provider
            if provider not in provider_breakdown:
                provider_breakdown[provider] = {
                    "requests": 0,
                    "cost": 0,
                    "savings": 0
                }
            provider_breakdown[provider]["requests"] += 1
            provider_breakdown[provider]["cost"] += metric.selected_cost
            provider_breakdown[provider]["savings"] += metric.savings

        return {
            "user_id": user_id,
            "period": f"{year}-{month:02d}",
            "total_requests": len(metrics),
            "total_spend": total_spend,
            "total_savings": total_savings,
            "roi_percent": (total_savings / total_spend * 100) if total_spend > 0 else 0,
            "provider_breakdown": provider_breakdown,
            "cache_stats": cost_tracker.get_cache_stats()
        }

    def export_to_csv(self, user_id: str, days: int = 30) -> str:
        """Export metrics to CSV format."""
        db = next(get_db())

        since = datetime.utcnow() - timedelta(days=days)
        metrics = db.query(ValueMetric).filter(
            ValueMetric.user_id == user_id,
            ValueMetric.timestamp >= since
        ).all()

        output = StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            "timestamp", "query_type", "complexity",
            "provider", "model", "cost", "savings"
        ])

        # Data
        for metric in metrics:
            writer.writerow([
                metric.timestamp.isoformat(),
                metric.query_type,
                metric.complexity,
                metric.selected_provider,
                metric.selected_model,
                metric.selected_cost,
                metric.savings
            ])

        return output.getvalue()
```

**Step 3: Add report endpoints**

Modify `app/main.py`:

```python
from app.reports import ReportGenerator

@app.get("/v1/reports/monthly")
async def get_monthly_report(
    user_id: str = "default",
    year: int = None,
    month: int = None
):
    """Get monthly cost report."""
    if year is None or month is None:
        now = datetime.now()
        year = now.year
        month = now.month

    generator = ReportGenerator()
    report = generator.generate_monthly_report(user_id, year, month)

    return report

@app.get("/v1/reports/export")
async def export_report(
    user_id: str = "default",
    days: int = 30,
    format: str = "csv"
):
    """Export cost data."""
    generator = ReportGenerator()

    if format == "csv":
        csv_data = generator.export_to_csv(user_id, days)
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=costs_{user_id}.csv"}
        )

    return {"error": "Unsupported format"}
```

**Step 4: Run tests**

```bash
pytest tests/test_reports.py -v
```

**Step 5: Commit**

```bash
git add app/reports.py templates/ app/main.py tests/test_reports.py
git commit -m "feat: add cost reports with CSV export"
```

---

## Phase 3: Multi-User & API Tiers (Days 8-11)

[Continues with detailed implementation for auth, teams, rate limiting...]

## Phase 4-9: [Remaining phases with same level of detail...]

---

## Success Metrics

**Revenue Validation:**

- ✅ Track real cost savings (baseline vs actual)
- ✅ Generate monthly value reports
- ✅ Support 3 pricing tiers with rate limiting
- ✅ Multi-user/team features working
- ✅ Dashboard shows ROI clearly

**Production Ready:**

- ✅ Test coverage > 80%
- ✅ Load testing passes (100 req/sec, p95 < 500ms)
- ✅ CI/CD pipeline green
- ✅ Monitoring dashboards operational
- ✅ Zero-downtime deployment verified
- ✅ Graceful degradation tested

---

## Estimated Timeline: 25 days

**Week 1:** Foundation, testing, value metrics
**Week 2:** Multi-user, API tiers, analytics dashboard
**Week 3:** Monitoring, resilience, database optimization
**Week 4:** CI/CD, load testing, documentation, deployment

**Daily commits:** Each task = 1 commit, ~3-5 tasks/day
