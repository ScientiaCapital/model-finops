# Phase 1 Learning Intelligence - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build 4 learning-powered agent tools and CLI dashboard that analyze historical LLM performance data to provide smart routing recommendations with black-box abstraction.

**Architecture:** Add model abstraction layer for competitive protection, enhance existing QueryPatternAnalyzer for model-level tracking, create 4 new agent tools with black-box conversion, and build CLI dashboard for visualization.

**Tech Stack:** Python 3.13, Claude Agent SDK, SQLite, existing QueryPatternAnalyzer

---

## Task 1: Model Abstraction Layer

**Files:**

- Create: `agent/model_abstraction.py`
- Test: `agent/test_model_abstraction.py`

**Step 1: Write the failing test**

Create `agent/test_model_abstraction.py`:

```python
"""Tests for model abstraction layer."""
import pytest
from model_abstraction import get_public_label, get_internal_models, MODEL_TIERS


def test_get_public_label_openrouter():
    """OpenRouter models map to correct tiers."""
    assert get_public_label("openrouter/deepseek-chat") == "Economy Tier"
    assert get_public_label("openrouter/qwen-2-72b") == "Premium Tier"


def test_get_public_label_claude():
    """Claude models map to Premium Tier."""
    assert get_public_label("claude/claude-3-haiku") == "Premium Tier"


def test_get_public_label_unknown():
    """Unknown models return Unknown Tier."""
    assert get_public_label("unknown/model") == "Unknown Tier"


def test_get_internal_models():
    """Reverse lookup from tier to models."""
    economy = get_internal_models("Economy Tier")
    assert "openrouter/deepseek-chat" in economy
    assert "openrouter/deepseek-coder" in economy


def test_tier_mapping_completeness():
    """All expected models have tier mappings."""
    required_models = [
        "claude/claude-3-haiku",
        "openrouter/qwen-2-72b",
        "openrouter/deepseek-chat",
        "openrouter/deepseek-coder",
        "google/gemini-flash",
        "openrouter/qwen-2.5-math"
    ]
    for model in required_models:
        assert model in MODEL_TIERS
```

**Step 2: Run test to verify it fails**

Run: `cd agent && source .venv/bin/activate && pytest test_model_abstraction.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'model_abstraction'"

**Step 3: Write minimal implementation**

Create `agent/model_abstraction.py`:

```python
"""Model abstraction layer for black-box competitive protection.

Maps internal model names (e.g., openrouter/deepseek-chat) to public tier labels
(e.g., Economy Tier) to hide implementation details from external users.
"""
from typing import List, Dict


# Tier mapping: internal model -> public label
MODEL_TIERS: Dict[str, str] = {
    # Premium Tier: High quality, established providers
    "claude/claude-3-haiku": "Premium Tier",
    "openrouter/qwen-2-72b": "Premium Tier",

    # Economy Tier: Cost-effective alternatives
    "openrouter/deepseek-chat": "Economy Tier",
    "openrouter/deepseek-coder": "Economy Tier",

    # Standard Tier: Balanced quality/cost
    "google/gemini-flash": "Standard Tier",

    # Specialty Tier: Domain-specific models
    "openrouter/qwen-2.5-math": "Specialty Tier",
}


def get_public_label(internal_model: str) -> str:
    """Convert internal model name to public tier label.

    Args:
        internal_model: Provider/model string (e.g., "openrouter/deepseek-chat")

    Returns:
        Public tier label (e.g., "Economy Tier")
    """
    return MODEL_TIERS.get(internal_model, "Unknown Tier")


def get_internal_models(public_label: str) -> List[str]:
    """Reverse lookup: get all internal models for a tier.

    Args:
        public_label: Tier label (e.g., "Economy Tier")

    Returns:
        List of internal model names matching the tier
    """
    return [model for model, tier in MODEL_TIERS.items() if tier == public_label]
```

**Step 4: Run test to verify it passes**

Run: `pytest test_model_abstraction.py -v`

Expected: PASS (6 tests)

**Step 5: Commit**

```bash
git add model_abstraction.py test_model_abstraction.py
git commit -m "feat: add model abstraction layer for black-box protection

Implements two-tier architecture:
- Internal view: Full model names (openrouter/deepseek-chat)
- External view: Tier labels (Economy Tier)

Protects competitive intelligence while delivering customer value."
```

---

## Task 2: Enhance QueryPatternAnalyzer for Model-Level Tracking

**Files:**

- Modify: `app/learning.py` (enhance existing QueryPatternAnalyzer)
- Test: Create `tests/test_learning_enhanced.py`

**Step 1: Write the failing test**

Create `tests/test_learning_enhanced.py`:

```python
"""Tests for enhanced learning.py with model-level tracking."""
import pytest
import sqlite3
import os
from app.learning import QueryPatternAnalyzer


@pytest.fixture
def test_db():
    """Create temporary test database."""
    db_path = "test_learning.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create schema
    cursor.execute("""
        CREATE TABLE requests (
            id INTEGER PRIMARY KEY,
            prompt_preview TEXT,
            complexity TEXT,
            provider TEXT,
            model TEXT,
            tokens_in INTEGER,
            tokens_out INTEGER,
            cost REAL,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE response_feedback (
            id INTEGER PRIMARY KEY,
            request_id INTEGER,
            rating INTEGER,
            FOREIGN KEY (request_id) REFERENCES requests(id)
        )
    """)

    # Insert test data
    test_requests = [
        ("Debug Python code", "complex", "openrouter", "openrouter/deepseek-coder", 100, 300, 0.00024, "2025-01-01 10:00:00"),
        ("Explain microservices", "simple", "claude", "claude/claude-3-haiku", 50, 200, 0.00095, "2025-01-01 10:05:00"),
        ("Write a function", "complex", "openrouter", "openrouter/deepseek-coder", 80, 250, 0.00020, "2025-01-01 10:10:00"),
        ("What is Docker?", "simple", "google", "google/gemini-flash", 30, 150, 0.00008, "2025-01-01 10:15:00"),
    ]

    for req in test_requests:
        cursor.execute(
            "INSERT INTO requests (prompt_preview, complexity, provider, model, tokens_in, tokens_out, cost, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            req
        )

    # Add feedback
    cursor.execute("INSERT INTO response_feedback (request_id, rating) VALUES (1, 5)")
    cursor.execute("INSERT INTO response_feedback (request_id, rating) VALUES (2, 4)")
    cursor.execute("INSERT INTO response_feedback (request_id, rating) VALUES (3, 5)")

    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


def test_get_provider_performance_model_level(test_db):
    """Provider performance tracks model-level granularity."""
    analyzer = QueryPatternAnalyzer(db_path=test_db)

    performance = analyzer.get_provider_performance()

    # Should have model-level entries
    models = [p['model'] for p in performance]
    assert "openrouter/deepseek-coder" in models
    assert "claude/claude-3-haiku" in models
    assert "google/gemini-flash" in models


def test_recommend_provider_with_confidence(test_db):
    """Recommendations include confidence levels."""
    analyzer = QueryPatternAnalyzer(db_path=test_db)

    recommendation = analyzer.recommend_provider(
        "Debug my Python code",
        "complex",
        ["openrouter", "claude", "google"]
    )

    assert 'model' in recommendation
    assert 'confidence' in recommendation
    assert recommendation['confidence'] in ['high', 'medium', 'low']


def test_pattern_confidence_levels(test_db):
    """Pattern confidence levels based on sample count."""
    analyzer = QueryPatternAnalyzer(db_path=test_db)

    confidence = analyzer.get_pattern_confidence_levels()

    assert 'code' in confidence
    assert confidence['code']['sample_count'] >= 0
    assert confidence['code']['confidence'] in ['high', 'medium', 'low']
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_learning_enhanced.py -v`

Expected: FAIL with "AttributeError: 'QueryPatternAnalyzer' object has no attribute 'get_pattern_confidence_levels'"

**Step 3: Read current learning.py implementation**

Run: `head -100 app/learning.py` to understand existing structure

**Step 4: Write minimal implementation**

Modify `app/learning.py`:

```python
# Add at the end of QueryPatternAnalyzer class

def get_provider_performance(self) -> List[Dict[str, Any]]:
    """Get provider performance metrics with model-level granularity.

    Returns:
        List of dicts with provider, model, quality_score, avg_cost, request_count
    """
    cursor = self.conn.cursor()

    # Query with model-level grouping
    cursor.execute("""
        SELECT
            r.provider,
            r.model,
            AVG(CASE WHEN rf.rating IS NOT NULL THEN rf.rating / 5.0 ELSE 0.5 END) as quality_score,
            AVG(r.cost) as avg_cost,
            COUNT(*) as request_count
        FROM requests r
        LEFT JOIN response_feedback rf ON r.id = rf.request_id
        WHERE r.model IS NOT NULL AND r.model != ''
        GROUP BY r.provider, r.model
        ORDER BY quality_score DESC, avg_cost ASC
    """)

    results = []
    for row in cursor.fetchall():
        results.append({
            'provider': row[0],
            'model': row[1],
            'quality_score': round(row[2], 3),
            'avg_cost': row[3],
            'request_count': row[4]
        })

    return results


def recommend_provider(
    self,
    prompt: str,
    complexity: str,
    available_providers: List[str]
) -> Dict[str, Any]:
    """Recommend optimal provider/model based on historical data.

    Args:
        prompt: User's query text
        complexity: Prompt complexity level
        available_providers: List of available provider names

    Returns:
        Dict with model, confidence, quality_score, avg_cost, reason
    """
    pattern = self.identify_pattern(prompt)

    cursor = self.conn.cursor()

    # Get best model for this pattern
    cursor.execute("""
        SELECT
            r.model,
            AVG(CASE WHEN rf.rating IS NOT NULL THEN rf.rating / 5.0 ELSE 0.5 END) as quality,
            AVG(r.cost) as cost,
            COUNT(*) as count
        FROM requests r
        LEFT JOIN response_feedback rf ON r.id = rf.request_id
        WHERE r.model IS NOT NULL
          AND r.model != ''
          AND r.prompt_preview LIKE ?
        GROUP BY r.model
        HAVING count >= 3
        ORDER BY quality DESC, cost ASC
        LIMIT 1
    """, (f"%{pattern}%",))

    row = cursor.fetchone()

    if row and row[3] >= 10:
        confidence = "high"
    elif row and row[3] >= 5:
        confidence = "medium"
    else:
        confidence = "low"
        # Fallback to best overall model
        cursor.execute("""
            SELECT model, AVG(CASE WHEN rf.rating IS NOT NULL THEN rf.rating / 5.0 ELSE 0.5 END) as quality,
                   AVG(r.cost) as cost, COUNT(*) as count
            FROM requests r
            LEFT JOIN response_feedback rf ON r.id = rf.request_id
            WHERE r.model IS NOT NULL AND r.model != ''
            GROUP BY model
            ORDER BY quality DESC, cost ASC
            LIMIT 1
        """)
        row = cursor.fetchone()

    if row:
        return {
            'model': row[0],
            'quality_score': round(row[1], 3),
            'avg_cost': row[2],
            'request_count': row[3],
            'confidence': confidence,
            'reason': f"Based on {row[3]} historical {pattern} queries"
        }

    # Ultimate fallback
    return {
        'model': 'google/gemini-flash',
        'confidence': 'low',
        'reason': 'Insufficient historical data, using default'
    }


def get_pattern_confidence_levels(self) -> Dict[str, Dict[str, Any]]:
    """Get confidence levels for each query pattern.

    Returns:
        Dict mapping pattern name to confidence info:
        {
            'code': {'sample_count': 23, 'confidence': 'high', 'best_model': '...'},
            'explanation': {'sample_count': 8, 'confidence': 'medium', ...}
        }
    """
    results = {}

    for pattern in self.QUERY_PATTERNS.keys():
        cursor = self.conn.cursor()

        # Count samples matching this pattern
        keywords = "|".join(self.QUERY_PATTERNS[pattern][:5])  # Use first 5 keywords
        cursor.execute("""
            SELECT COUNT(*), r.model, AVG(CASE WHEN rf.rating IS NOT NULL THEN rf.rating / 5.0 ELSE 0.5 END) as quality
            FROM requests r
            LEFT JOIN response_feedback rf ON r.id = rf.request_id
            WHERE r.prompt_preview REGEXP ?
            GROUP BY r.model
            ORDER BY quality DESC
            LIMIT 1
        """, (keywords,))

        row = cursor.fetchone()
        count = row[0] if row else 0
        best_model = row[1] if row and count > 0 else None

        # Confidence thresholds
        if count >= 20:
            confidence = "high"
        elif count >= 10:
            confidence = "medium"
        else:
            confidence = "low"

        results[pattern] = {
            'sample_count': count,
            'confidence': confidence,
            'best_model': best_model,
            'samples_needed': max(0, 20 - count)
        }

    return results
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_learning_enhanced.py -v`

Expected: PASS (3 tests)

**Step 6: Commit**

```bash
git add app/learning.py tests/test_learning_enhanced.py
git commit -m "feat: enhance QueryPatternAnalyzer with model-level tracking

- Update get_provider_performance() to group by (provider, model)
- Add recommend_provider() with confidence levels
- Add get_pattern_confidence_levels() for learning maturity

Enables smart routing based on model-specific historical performance."
```

---

## Task 3: Add 4 Learning-Powered Agent Tools

**Files:**

- Modify: `agent/tools.py`
- Test: `agent/test_learning_tools.py`

**Step 1: Write the failing test**

Create `agent/test_learning_tools.py`:

```python
"""Tests for learning-powered agent tools."""
import pytest
import json
from tools import (
    get_smart_recommendation,
    get_pattern_analysis,
    get_provider_performance,
    calculate_potential_savings
)


@pytest.mark.asyncio
async def test_get_smart_recommendation_format():
    """Smart recommendation returns proper format."""
    result = await get_smart_recommendation({"prompt": "Debug Python code"})

    assert "content" in result
    assert len(result["content"]) > 0
    assert result["content"][0]["type"] == "text"

    # Should mention tier (not internal model)
    text = result["content"][0]["text"]
    assert "Tier" in text
    assert "Confidence" in text


@pytest.mark.asyncio
async def test_get_pattern_analysis_format():
    """Pattern analysis returns all 6 patterns."""
    result = await get_pattern_analysis({})

    text = result["content"][0]["text"]

    # Should list all patterns
    patterns = ["code", "analysis", "creative", "explanation", "factual", "reasoning"]
    for pattern in patterns:
        assert pattern in text.lower()


@pytest.mark.asyncio
async def test_get_provider_performance_black_boxed():
    """Provider performance hides internal models in external mode."""
    result = await get_provider_performance({"mode": "external"})

    text = result["content"][0]["text"]

    # Should show tiers, not models
    assert "Tier" in text
    # Should NOT leak internal model names
    assert "openrouter" not in text.lower()
    assert "deepseek" not in text.lower()


@pytest.mark.asyncio
async def test_get_provider_performance_internal():
    """Provider performance shows models in internal mode."""
    result = await get_provider_performance({"mode": "internal"})

    text = result["content"][0]["text"]

    # Internal mode shows actual models
    # (Will contain model names if data exists)
    assert "Model" in text or "No data" in text


@pytest.mark.asyncio
async def test_calculate_potential_savings_format():
    """Savings calculation shows current vs optimized."""
    result = await calculate_potential_savings({"days": 7})

    text = result["content"][0]["text"]

    assert "current" in text.lower() or "optimized" in text.lower()
    assert "$" in text or "cost" in text.lower()
```

**Step 2: Run test to verify it fails**

Run: `cd agent && source .venv/bin/activate && pytest test_learning_tools.py -v`

Expected: FAIL with "ImportError: cannot import name 'get_smart_recommendation'"

**Step 3: Write minimal implementation**

Modify `agent/tools.py` - add at the end:

```python
# Import model abstraction
import sys
import os
sys.path.append(os.path.dirname(__file__))
from model_abstraction import get_public_label, get_internal_models

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from app.learning import QueryPatternAnalyzer
from app.complexity import score_complexity


@tool(
    "get_smart_recommendation",
    "Get AI-powered routing recommendation based on historical performance for similar queries. Returns recommended tier with confidence level.",
    {
        "prompt": {
            "type": "string",
            "description": "The query text to analyze"
        }
    }
)
async def get_smart_recommendation(args: dict[str, Any]) -> dict[str, Any]:
    """Get smart routing recommendation with black-box tier labels."""
    try:
        prompt = args.get("prompt", "")

        # Get database path (relative to agent directory)
        db_path = os.path.join(os.path.dirname(__file__), '..', 'optimizer.db')
        analyzer = QueryPatternAnalyzer(db_path=db_path)

        # Analyze prompt
        complexity = score_complexity(prompt)
        pattern = analyzer.identify_pattern(prompt)

        # Get recommendation
        rec = analyzer.recommend_provider(
            prompt,
            complexity,
            available_providers=["gemini", "claude", "openrouter"]
        )

        # Convert to public tier
        public_tier = get_public_label(rec['model'])

        # Format response
        response = f"""**Recommended:** {public_tier}
**Confidence:** {rec['confidence']}
**Quality Score:** {rec.get('quality_score', 'N/A')}
**Estimated Cost:** ${rec.get('avg_cost', 0):.6f}

**Reason:** {rec['reason']}

**Pattern Detected:** {pattern}
**Complexity:** {complexity}"""

        return {
            "content": [{
                "type": "text",
                "text": response
            }]
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error generating recommendation: {str(e)}"
            }],
            "is_error": True
        }


@tool(
    "get_pattern_analysis",
    "Analyze learning progress across all 6 query patterns (code, analysis, creative, explanation, factual, reasoning). Shows confidence levels and best models per pattern.",
    {}
)
async def get_pattern_analysis(args: dict[str, Any]) -> dict[str, Any]:
    """Show learning maturity by pattern."""
    try:
        db_path = os.path.join(os.path.dirname(__file__), '..', 'optimizer.db')
        analyzer = QueryPatternAnalyzer(db_path=db_path)

        confidence_data = analyzer.get_pattern_confidence_levels()

        # Build response
        lines = ["# Query Pattern Analysis\n"]

        for pattern, data in confidence_data.items():
            lines.append(f"\n## {pattern.title()} Queries")
            lines.append(f"- Sample Count: {data['sample_count']}")
            lines.append(f"- Confidence: {data['confidence']}")

            if data['best_model']:
                # Black-box the model
                public_label = get_public_label(data['best_model'])
                lines.append(f"- Best Performer: {public_label}")

            if data['samples_needed'] > 0:
                lines.append(f"- *Need {data['samples_needed']} more samples for high confidence*")

        return {
            "content": [{
                "type": "text",
                "text": "\n".join(lines)
            }]
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error analyzing patterns: {str(e)}"
            }],
            "is_error": True
        }


@tool(
    "get_provider_performance",
    "Compare model performance across quality and cost. Supports 'internal' mode (shows actual models) and 'external' mode (shows tier labels only).",
    {
        "mode": {
            "type": "string",
            "description": "View mode: 'internal' or 'external' (default: external)",
            "enum": ["internal", "external"]
        }
    }
)
async def get_provider_performance(args: dict[str, Any]) -> dict[str, Any]:
    """Provider performance with black-box abstraction."""
    try:
        mode = args.get("mode", "external")

        db_path = os.path.join(os.path.dirname(__file__), '..', 'optimizer.db')
        analyzer = QueryPatternAnalyzer(db_path=db_path)

        performance = analyzer.get_provider_performance()

        if not performance:
            return {
                "content": [{
                    "type": "text",
                    "text": "No performance data available yet. Generate some queries first!"
                }]
            }

        # Calculate composite scores
        for p in performance:
            p['composite_score'] = (
                p['quality_score'] * 0.5 +  # Quality weight: 50%
                (1 - min(p['avg_cost'] / 0.01, 1)) * 0.3 +  # Cost weight: 30% (inverted)
                min(p['request_count'] / 100, 1) * 0.2  # Volume weight: 20%
            )

        performance.sort(key=lambda x: x['composite_score'], reverse=True)

        # Format table
        lines = ["# Provider Performance Rankings\n"]

        if mode == "internal":
            lines.append("Rank | Model | Score | Quality | Cost | Requests")
            lines.append("-----|-------|-------|---------|------|----------")

            for i, p in enumerate(performance[:10], 1):
                lines.append(
                    f"{i} | {p['model']} | {p['composite_score']:.3f} | "
                    f"{p['quality_score']:.2f} | ${p['avg_cost']:.5f} | {p['request_count']}"
                )
        else:
            # External: black-box models
            lines.append("Rank | Tier | Score | Quality | Cost | Requests")
            lines.append("-----|------|-------|---------|------|----------")

            for i, p in enumerate(performance[:10], 1):
                tier = get_public_label(p['model'])
                lines.append(
                    f"{i} | {tier} | {p['composite_score']:.3f} | "
                    f"{p['quality_score']:.2f} | ${p['avg_cost']:.5f} | {p['request_count']}"
                )

        return {
            "content": [{
                "type": "text",
                "text": "\n".join(lines)
            }]
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error getting performance data: {str(e)}"
            }],
            "is_error": True
        }


@tool(
    "calculate_potential_savings",
    "Calculate ROI of learning-powered routing vs current usage. Shows cost reduction opportunities with quality impact analysis.",
    {
        "days": {
            "type": "integer",
            "description": "Number of days to analyze (default: 30)"
        }
    }
)
async def calculate_potential_savings(args: dict[str, Any]) -> dict[str, Any]:
    """Calculate savings from smart routing."""
    try:
        days = args.get("days", 30)

        db_path = os.path.join(os.path.dirname(__file__), '..', 'optimizer.db')

        # Query actual costs
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                SUM(cost) as total_cost,
                COUNT(*) as request_count,
                AVG(cost) as avg_cost
            FROM requests
            WHERE date(timestamp) >= date('now', ?)
        """, (f'-{days} days',))

        row = cursor.fetchone()
        current_cost = row[0] or 0
        request_count = row[1] or 0
        avg_cost = row[2] or 0

        if request_count == 0:
            conn.close()
            return {
                "content": [{
                    "type": "text",
                    "text": "Insufficient data for savings calculation. Need at least 1 request in the specified period."
                }]
            }

        # Get cheapest model for each pattern
        analyzer = QueryPatternAnalyzer(db_path=db_path)
        performance = analyzer.get_provider_performance()

        if not performance:
            conn.close()
            return {
                "content": [{
                    "type": "text",
                    "text": "No performance data available for savings calculation."
                }]
            }

        # Find best cheap model (quality >= 0.7, lowest cost)
        cheap_model = min(
            [p for p in performance if p['quality_score'] >= 0.7],
            key=lambda x: x['avg_cost'],
            default=None
        )

        if not cheap_model:
            cheap_model = min(performance, key=lambda x: x['avg_cost'])

        optimized_cost = cheap_model['avg_cost'] * request_count
        savings = current_cost - optimized_cost
        savings_pct = (savings / current_cost * 100) if current_cost > 0 else 0

        # Format response
        response = f"""# Potential Savings Analysis ({days} days)

**Current Usage:**
- Total Cost: ${current_cost:.4f}
- Requests: {request_count}
- Avg Cost/Request: ${avg_cost:.6f}

**Optimized Routing:**
- Projected Cost: ${optimized_cost:.4f}
- Using: {get_public_label(cheap_model['model'])} (Quality: {cheap_model['quality_score']:.2f})
- Avg Cost/Request: ${cheap_model['avg_cost']:.6f}

**Savings Opportunity:**
- **${savings:.4f} ({savings_pct:.1f}% reduction)**
- Annualized: ${savings * (365/days):.2f}/year

**Quality Impact:** {'Maintained' if cheap_model['quality_score'] >= 0.75 else 'Minor reduction'}
"""

        conn.close()

        return {
            "content": [{
                "type": "text",
                "text": response
            }]
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error calculating savings: {str(e)}"
            }],
            "is_error": True
        }
```

**Step 4: Run test to verify it passes**

Run: `pytest test_learning_tools.py -v`

Expected: PASS (5 tests)

**Step 5: Commit**

```bash
git add tools.py test_learning_tools.py
git commit -m "feat: add 4 learning-powered agent tools

Tools:
1. get_smart_recommendation - Smart routing with confidence
2. get_pattern_analysis - Learning maturity by pattern
3. get_provider_performance - Model comparison (internal/external)
4. calculate_potential_savings - ROI calculator

All tools use black-box abstraction for competitive protection."
```

---

## Task 4: Register New Tools with Agent

**Files:**

- Modify: `agent/cost_optimizer_agent.py`

**Step 1: Import new tools**

Add to imports at top of `agent/cost_optimizer_agent.py`:

```python
from tools import (
    get_usage_stats,
    analyze_cost_patterns,
    get_recommendations,
    query_recent_requests,
    check_cache_effectiveness,
    compare_providers,
    # New learning tools
    get_smart_recommendation,
    get_pattern_analysis,
    get_provider_performance,
    calculate_potential_savings
)
```

**Step 2: Register tools with MCP server**

Modify the `cost_analyzer_server` creation (around line 78):

```python
cost_analyzer_server = create_sdk_mcp_server(
    name="cost_analyzer",
    version="1.0.0",
    tools=[
        get_usage_stats,
        analyze_cost_patterns,
        get_recommendations,
        query_recent_requests,
        check_cache_effectiveness,
        compare_providers,
        # New learning-powered tools
        get_smart_recommendation,
        get_pattern_analysis,
        get_provider_performance,
        calculate_potential_savings
    ]
)
```

**Step 3: Update allowed tools list**

Modify `agent_options` (around line 97):

```python
agent_options = ClaudeAgentOptions(
    system_prompt=SYSTEM_PROMPT,
    model="claude-3-5-sonnet-20241022",
    mcp_servers={"cost_analyzer": cost_analyzer_server},
    allowed_tools=[
        "get_usage_stats",
        "analyze_cost_patterns",
        "get_recommendations",
        "query_recent_requests",
        "check_cache_effectiveness",
        "compare_providers",
        # New learning-powered tools
        "get_smart_recommendation",
        "get_pattern_analysis",
        "get_provider_performance",
        "calculate_potential_savings"
    ]
)
```

**Step 4: Update system prompt**

Modify `SYSTEM_PROMPT` to mention new tools (around line 24):

```python
SYSTEM_PROMPT = """You are a Cost Optimization Agent, an expert AI spending analyst.

Your role is to help users understand and optimize their AI/LLM costs by:
1. Analyzing usage patterns and spending trends
2. Identifying cost-saving opportunities
3. Providing actionable, data-driven recommendations
4. Explaining complex cost data in clear, business-friendly language

You have access to 10 powerful tools that query the AI Cost Optimizer database:

**Analysis Tools:**
- get_usage_stats: Overall statistics (total costs, requests, breakdowns)
- analyze_cost_patterns: Spending trends over time (default: 7 days)
- query_recent_requests: Examine recent queries (up to 100)

**Optimization Tools:**
- get_recommendations: Generate prioritized optimization opportunities
- check_cache_effectiveness: Cache performance and savings analysis
- compare_providers: Cost/quality comparison across providers

**Learning Intelligence Tools (NEW):**
- get_smart_recommendation: AI-powered routing recommendations with confidence
- get_pattern_analysis: Learning progress across 6 query patterns
- get_provider_performance: Model performance rankings (internal/external view)
- calculate_potential_savings: ROI calculator for smart routing

**Your Communication Style:**
- Be concise but thorough
- Use specific numbers and metrics
- Prioritize actionable insights over raw data dumps
- Highlight savings opportunities with dollar amounts
- Use business-friendly language (avoid excessive technical jargon)

You are helpful, analytical, and focused on delivering ROI through cost optimization.
"""
```

**Step 5: Test agent with new tools**

Create quick test in `agent/test_new_tools_integration.py`:

```python
"""Integration test for new learning tools."""
import asyncio
from cost_optimizer_agent import run_agent


async def test_agent_has_learning_tools():
    """Agent should list new learning tools."""
    # This will only work with ANTHROPIC_API_KEY set
    # For now, just test imports work
    from tools import (
        get_smart_recommendation,
        get_pattern_analysis,
        get_provider_performance,
        calculate_potential_savings
    )

    print("✓ All new learning tools imported successfully")
    return True


if __name__ == "__main__":
    asyncio.run(test_agent_has_learning_tools())
```

Run: `python3 test_new_tools_integration.py`

Expected: "✓ All new learning tools imported successfully"

**Step 6: Commit**

```bash
git add cost_optimizer_agent.py test_new_tools_integration.py
git commit -m "feat: register 4 learning tools with agent

Updates:
- Import new tools
- Add to MCP server tool list
- Add to allowed_tools
- Update system prompt with tool descriptions

Agent now has 10 tools total (6 existing + 4 learning-powered)."
```

---

## Task 5: Build CLI Dashboard

**Files:**

- Create: `agent/dashboard.py`
- Test: Manual testing (visual output)

**Step 1: Create dashboard script**

Create `agent/dashboard.py`:

```python
#!/usr/bin/env python3
"""CLI Dashboard for Learning Intelligence Visualization.

Usage:
    python dashboard.py --mode internal   # Show actual models
    python dashboard.py --mode external   # Show tier labels (default)
"""
import argparse
import sys
import os
from typing import Dict, List, Any

# Add parent to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.learning import QueryPatternAnalyzer
from model_abstraction import get_public_label


def render_progress_bar(value: float, max_value: float, width: int = 40) -> str:
    """Render ASCII progress bar.

    Args:
        value: Current value
        max_value: Maximum value
        width: Bar width in characters

    Returns:
        ASCII progress bar string
    """
    if max_value == 0:
        pct = 0
    else:
        pct = min(value / max_value, 1.0)

    filled = int(pct * width)
    bar = '█' * filled + '░' * (width - filled)
    return f"[{bar}] {pct*100:.0f}%"


def render_training_overview(analyzer: QueryPatternAnalyzer) -> str:
    """Render training data overview section."""
    import sqlite3
    conn = sqlite3.connect(analyzer.db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM requests")
    total_requests = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT provider) FROM requests WHERE model IS NOT NULL")
    unique_models = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM response_feedback")
    feedback_count = cursor.fetchone()[0]

    conn.close()

    confidence_data = analyzer.get_pattern_confidence_levels()
    high_confidence = sum(1 for d in confidence_data.values() if d['confidence'] == 'high')

    return f"""
╔══════════════════════════════════════════════════════════════╗
║                   TRAINING DATA OVERVIEW                     ║
╚══════════════════════════════════════════════════════════════╝

Total Queries: {total_requests}
Unique Models: {unique_models}
User Feedback: {feedback_count}
High-Confidence Patterns: {high_confidence}/6

Status: {'✓ Ready for smart routing' if high_confidence >= 3 else '⚠ Needs more training data'}
"""


def render_pattern_distribution(analyzer: QueryPatternAnalyzer) -> str:
    """Render pattern distribution section."""
    confidence_data = analyzer.get_pattern_confidence_levels()

    lines = [
        "",
        "╔══════════════════════════════════════════════════════════════╗",
        "║                  PATTERN DISTRIBUTION                        ║",
        "╚══════════════════════════════════════════════════════════════╝",
        ""
    ]

    max_count = max((d['sample_count'] for d in confidence_data.values()), default=1)

    for pattern, data in sorted(confidence_data.items()):
        bar = render_progress_bar(data['sample_count'], max(max_count, 20), width=30)
        confidence_icon = {
            'high': '✓',
            'medium': '~',
            'low': '✗'
        }[data['confidence']]

        lines.append(f"{confidence_icon} {pattern.ljust(12)} {bar} {data['sample_count']} samples")

    return "\n".join(lines)


def render_top_models(analyzer: QueryPatternAnalyzer, mode: str = "external") -> str:
    """Render top models section."""
    performance = analyzer.get_provider_performance()

    if not performance:
        return "\nNo performance data available yet."

    # Calculate composite scores
    for p in performance:
        p['composite_score'] = (
            p['quality_score'] * 0.5 +
            (1 - min(p['avg_cost'] / 0.01, 1)) * 0.3 +
            min(p['request_count'] / 100, 1) * 0.2
        )

    performance.sort(key=lambda x: x['composite_score'], reverse=True)
    top_10 = performance[:10]

    lines = [
        "",
        "╔══════════════════════════════════════════════════════════════╗",
        "║                    TOP PERFORMING MODELS                     ║",
        "╚══════════════════════════════════════════════════════════════╝",
        ""
    ]

    if mode == "internal":
        lines.append("Rank  Model                    Score   Quality  Cost       Requests")
        lines.append("────  ─────────────────────────────────────────────────────────────")

        for i, p in enumerate(top_10, 1):
            lines.append(
                f"{i:2}.   {p['model'][:24].ljust(24)} {p['composite_score']:.3f}   "
                f"{p['quality_score']:.2f}     ${p['avg_cost']:.5f}  {p['request_count']:4}"
            )
    else:
        lines.append("Rank  Tier              Score   Quality  Cost       Requests")
        lines.append("────  ──────────────────────────────────────────────────────")

        for i, p in enumerate(top_10, 1):
            tier = get_public_label(p['model'])
            lines.append(
                f"{i:2}.   {tier[:18].ljust(18)} {p['composite_score']:.3f}   "
                f"{p['quality_score']:.2f}     ${p['avg_cost']:.5f}  {p['request_count']:4}"
            )

    return "\n".join(lines)


def render_savings_projection(analyzer: QueryPatternAnalyzer) -> str:
    """Render savings projection section."""
    import sqlite3
    conn = sqlite3.connect(analyzer.db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT SUM(cost), COUNT(*), AVG(cost)
        FROM requests
        WHERE date(timestamp) >= date('now', '-30 days')
    """)

    row = cursor.fetchone()
    current_cost = row[0] or 0
    request_count = row[1] or 0
    avg_cost = row[2] or 0

    conn.close()

    if request_count == 0:
        return "\n(Insufficient data for savings projection)"

    performance = analyzer.get_provider_performance()
    if not performance:
        return "\n(No performance data for savings projection)"

    # Find best cheap model
    cheap_model = min(
        [p for p in performance if p['quality_score'] >= 0.7],
        key=lambda x: x['avg_cost'],
        default=min(performance, key=lambda x: x['avg_cost'])
    )

    optimized_cost = cheap_model['avg_cost'] * request_count
    savings = current_cost - optimized_cost
    savings_pct = (savings / current_cost * 100) if current_cost > 0 else 0

    return f"""
╔══════════════════════════════════════════════════════════════╗
║                   SAVINGS PROJECTION (30d)                   ║
╚══════════════════════════════════════════════════════════════╝

Current Monthly Cost:    ${current_cost:.4f}
Optimized Monthly Cost:  ${optimized_cost:.4f}
────────────────────────────────────────────────────────────────
Potential Savings:       ${savings:.4f} ({savings_pct:.1f}% reduction)
Annualized Savings:      ${savings * 12:.2f}/year

Using: {get_public_label(cheap_model['model'])} (Quality: {cheap_model['quality_score']:.2f})
"""


def render_learning_progress(analyzer: QueryPatternAnalyzer) -> str:
    """Render learning progress section."""
    confidence_data = analyzer.get_pattern_confidence_levels()

    lines = [
        "",
        "╔══════════════════════════════════════════════════════════════╗",
        "║                    LEARNING PROGRESS                         ║",
        "╚══════════════════════════════════════════════════════════════╝",
        ""
    ]

    for pattern, data in sorted(confidence_data.items()):
        progress = min(data['sample_count'] / 20, 1.0)  # 20 = high confidence threshold
        bar = render_progress_bar(data['sample_count'], 20, width=25)

        lines.append(f"{pattern.ljust(12)} {bar}")

        if data['samples_needed'] > 0:
            lines.append(f"{''.ljust(12)} Need {data['samples_needed']} more for high confidence")
        lines.append("")

    return "\n".join(lines)


def main():
    """Main dashboard entry point."""
    parser = argparse.ArgumentParser(description="Learning Intelligence Dashboard")
    parser.add_argument(
        "--mode",
        choices=["internal", "external"],
        default="external",
        help="View mode: internal (show models) or external (show tiers)"
    )
    args = parser.parse_args()

    # Initialize analyzer
    db_path = os.path.join(os.path.dirname(__file__), '..', 'optimizer.db')

    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        print("\nRun init_test_data.py first to create sample data.")
        sys.exit(1)

    analyzer = QueryPatternAnalyzer(db_path=db_path)

    # Render dashboard
    mode_label = "INTERNAL ADMIN VIEW" if args.mode == "internal" else "EXTERNAL CUSTOMER VIEW"

    print("\n")
    print("═" * 66)
    print(f"  LEARNING INTELLIGENCE DASHBOARD - {mode_label}")
    print("═" * 66)

    print(render_training_overview(analyzer))
    print(render_pattern_distribution(analyzer))
    print(render_top_models(analyzer, mode=args.mode))
    print(render_savings_projection(analyzer))
    print(render_learning_progress(analyzer))

    print("\n" + "═" * 66)
    print()


if __name__ == "__main__":
    main()
```

**Step 2: Make dashboard executable**

Run: `chmod +x agent/dashboard.py`

**Step 3: Test dashboard**

Run: `cd agent && python3 dashboard.py --mode internal`

Expected: Dashboard renders with ASCII tables and progress bars

Run: `python3 dashboard.py --mode external`

Expected: Dashboard shows tier labels instead of model names

**Step 4: Create dashboard README**

Create `agent/DASHBOARD.md`:

````markdown
# Learning Intelligence Dashboard

Visual CLI dashboard showing learning progress and model performance.

## Usage

```bash
# External view (black-boxed tiers)
python3 dashboard.py --mode external

# Internal view (actual models)
python3 dashboard.py --mode internal
```
````

## Sections

1. **Training Data Overview** - Total queries, models, feedback count
2. **Pattern Distribution** - Sample counts per query pattern
3. **Top Performing Models** - Ranked by composite score
4. **Savings Projection** - 30-day cost optimization opportunity
5. **Learning Progress** - Maturity progress bars per pattern

## Requirements

- Database with historical data (run `init_test_data.py` first)
- Python 3.8+
- No external dependencies (uses stdlib only)

````

**Step 5: Commit**

```bash
git add dashboard.py DASHBOARD.md
git commit -m "feat: add CLI learning intelligence dashboard

Features:
- ASCII progress bars and tables
- Two-mode operation (internal/external)
- 5 visualization sections
- No external dependencies

Provides at-a-glance view of learning maturity and savings opportunities."
````

---

## Task 6: Final Integration Testing

**Step 1: Verify all files created**

Run:

```bash
ls -la agent/model_abstraction.py
ls -la agent/dashboard.py
ls -la agent/test_model_abstraction.py
ls -la agent/test_learning_tools.py
git status
```

Expected: All new files exist and are tracked

**Step 2: Run all agent tests**

Run: `cd agent && source .venv/bin/activate && pytest -v`

Expected: All tests pass

**Step 3: Test dashboard**

Run: `python3 dashboard.py --mode external`

Expected: Dashboard renders successfully

**Step 4: Test agent with learning tools**

Run: `python3 cost_optimizer_agent.py "What's the best model for code queries?"`

Expected: Agent uses `get_smart_recommendation` or `get_pattern_analysis`

(Note: Requires ANTHROPIC_API_KEY)

**Step 5: Final commit**

```bash
git add -A
git commit -m "chore: Phase 1 implementation complete

All 5 components implemented and tested:
✓ Model abstraction layer
✓ Enhanced QueryPatternAnalyzer
✓ 4 learning-powered agent tools
✓ CLI dashboard
✓ Agent integration

Ready for Phase 2: Auto-routing integration."
```

---

## Task 7: Update Documentation

**Step 1: Update agent README**

Modify `agent/README.md` to document new tools:

Add section:

````markdown
## New: Learning Intelligence Tools

The agent now includes 4 learning-powered tools:

### 1. get_smart_recommendation

Get AI-powered routing recommendations based on historical data.

**Example:** "What's the best model for debugging Python code?"

### 2. get_pattern_analysis

View learning progress across 6 query patterns.

**Example:** "Show me learning progress by pattern"

### 3. get_provider_performance

Compare model performance (internal or external view).

**Example:** "Compare provider performance"

### 4. calculate_potential_savings

Calculate ROI of learning-powered routing.

**Example:** "How much could I save with smart routing?"

## CLI Dashboard

Visual dashboard showing learning intelligence:

```bash
python3 dashboard.py --mode external  # Customer view
python3 dashboard.py --mode internal  # Admin view
```
````

````

**Step 2: Update main README**

Modify root `README.md` to mention Phase 1:

Add to features section:

```markdown
- **Learning Intelligence (Phase 1)**: Smart routing recommendations based on historical performance
- **Model Abstraction**: Black-box tier labels protect competitive intelligence
- **CLI Dashboard**: Visual learning progress and savings projections
````

**Step 3: Commit documentation**

```bash
git add agent/README.md README.md
git commit -m "docs: update README with Phase 1 learning intelligence"
```

---

## Completion Checklist

- [ ] Task 1: Model abstraction layer (tests pass)
- [ ] Task 2: Enhanced QueryPatternAnalyzer (tests pass)
- [ ] Task 3: 4 learning-powered tools (tests pass)
- [ ] Task 4: Agent registration (imports work)
- [ ] Task 5: CLI dashboard (renders correctly)
- [ ] Task 6: Integration testing (all tests pass)
- [ ] Task 7: Documentation updated

**Success Criteria:**

1. All pytest tests pass
2. Dashboard renders in both modes
3. Agent can call all 10 tools
4. Black-box abstraction prevents model leakage
5. Documentation is complete

**Time Estimate:** 4-6 hours (as designed)

---

## Next Steps (Phase 2 Preview)

After Phase 1 is complete:

1. **Auto-Routing Integration** - Modify FastAPI router to use QueryPatternAnalyzer
2. **A/B Testing Framework** - Compare learned vs default routing
3. **Customer Dashboards** - Web UI for savings visualization

See `docs/plans/2025-01-11-learning-intelligence-moat-design.md` for full roadmap.

---

**Plan complete.** Ready for execution with @superpowers:executing-plans or @superpowers:subagent-driven-development.
