# Phase 2: Auto-Routing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform learning intelligence from advisory to operational by implementing pluggable routing strategies that automatically route requests to optimal models based on learned performance data.

**Architecture:** Strategy Pattern with three routing strategies (ComplexityStrategy, LearningStrategy, HybridStrategy) orchestrated by RoutingEngine. Query parameter `?auto_route=true` toggles between complexity-based baseline and learning-powered routing. Comprehensive metrics track cost savings, quality, and confidence evolution.

**Tech Stack:** FastAPI, Pydantic, SQLite, Python 3.8+, QueryPatternAnalyzer (Phase 1)

**Estimated Time:** 6-7 hours (7 tasks, ~1 hour each)

---

## Task 1: Create Data Structures

**Goal:** Define RoutingDecision and RoutingContext data classes

**Files:**

- Create: `app/routing/models.py`
- Test: `tests/test_routing_models.py`

### Step 1: Write the failing test

Create `tests/test_routing_models.py`:

```python
"""Tests for routing data models."""
import pytest
from app.routing.models import RoutingDecision, RoutingContext


def test_routing_decision_creation():
    """Test RoutingDecision can be created with required fields."""
    decision = RoutingDecision(
        provider="gemini",
        model="gemini-flash",
        confidence="high",
        strategy_used="learning",
        reasoning="Test reasoning",
        fallback_used=False,
        metadata={"pattern": "code"}
    )

    assert decision.provider == "gemini"
    assert decision.model == "gemini-flash"
    assert decision.confidence == "high"
    assert decision.strategy_used == "learning"
    assert decision.fallback_used is False
    assert decision.metadata["pattern"] == "code"


def test_routing_context_defaults():
    """Test RoutingContext has sensible defaults."""
    context = RoutingContext(prompt="Test prompt")

    assert context.prompt == "Test prompt"
    assert context.user_id is None
    assert context.available_providers == ["gemini", "claude", "openrouter"]
    assert context.max_cost is None


def test_routing_context_custom_providers():
    """Test RoutingContext accepts custom provider list."""
    context = RoutingContext(
        prompt="Test",
        available_providers=["gemini"]
    )

    assert context.available_providers == ["gemini"]
```

### Step 2: Run test to verify it fails

```bash
pytest tests/test_routing_models.py -v
```

**Expected:** FAIL with `ModuleNotFoundError: No module named 'app.routing.models'`

### Step 3: Write minimal implementation

Create `app/routing/models.py`:

```python
"""Data models for routing system."""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class RoutingDecision:
    """Represents a routing decision with metadata.

    Attributes:
        provider: Provider name (e.g., "gemini", "claude", "openrouter")
        model: Full model name (e.g., "gemini-flash", "openrouter/deepseek-chat")
        confidence: Confidence level ("high", "medium", "low")
        strategy_used: Strategy that made decision ("learning", "complexity", "hybrid")
        reasoning: Human-readable explanation of decision
        fallback_used: True if strategy failed and used fallback
        metadata: Additional context (pattern, quality_score, cost_estimate, etc.)
    """

    provider: str
    model: str
    confidence: str
    strategy_used: str
    reasoning: str
    fallback_used: bool
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RoutingContext:
    """Context passed to routing strategies.

    Attributes:
        prompt: User's query text
        user_id: Optional user identifier
        session_id: Optional session identifier
        available_providers: List of providers available for routing
        max_cost: Optional maximum cost constraint
        min_quality: Optional minimum quality constraint
    """

    prompt: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    available_providers: List[str] = field(
        default_factory=lambda: ["gemini", "claude", "openrouter"]
    )
    max_cost: Optional[float] = None
    min_quality: Optional[float] = None
```

### Step 4: Run test to verify it passes

```bash
pytest tests/test_routing_models.py -v
```

**Expected:** PASS (3 tests)

### Step 5: Commit

```bash
git add app/routing/models.py tests/test_routing_models.py
git commit -m "feat: add RoutingDecision and RoutingContext data models

- RoutingDecision: Encapsulates routing choice with metadata
- RoutingContext: Provides context for routing strategies
- Full test coverage for both models"
```

---

## Task 2: Create RoutingStrategy Interface

**Goal:** Define abstract base class for routing strategies

**Files:**

- Create: `app/routing/strategy.py`
- Test: `tests/test_routing_strategy.py`

### Step 1: Write the failing test

Create `tests/test_routing_strategy.py`:

```python
"""Tests for routing strategy interface."""
import pytest
from app.routing.strategy import RoutingStrategy
from app.routing.models import RoutingDecision, RoutingContext


class ConcreteStrategy(RoutingStrategy):
    """Concrete implementation for testing."""

    def route(self, prompt: str, context: RoutingContext) -> RoutingDecision:
        return RoutingDecision(
            provider="test",
            model="test-model",
            confidence="high",
            strategy_used="test",
            reasoning="test routing",
            fallback_used=False,
            metadata={}
        )

    def get_name(self) -> str:
        return "test_strategy"


def test_routing_strategy_abstract():
    """Test RoutingStrategy cannot be instantiated directly."""
    with pytest.raises(TypeError):
        RoutingStrategy()


def test_concrete_strategy_implementation():
    """Test concrete strategy can be instantiated and used."""
    strategy = ConcreteStrategy()
    context = RoutingContext(prompt="test")

    decision = strategy.route("test prompt", context)

    assert decision.provider == "test"
    assert decision.strategy_used == "test"
    assert strategy.get_name() == "test_strategy"
```

### Step 2: Run test to verify it fails

```bash
pytest tests/test_routing_strategy.py -v
```

**Expected:** FAIL with `ModuleNotFoundError: No module named 'app.routing.strategy'`

### Step 3: Write minimal implementation

Create `app/routing/strategy.py`:

```python
"""Abstract base class for routing strategies."""
from abc import ABC, abstractmethod
from app.routing.models import RoutingDecision, RoutingContext


class RoutingStrategy(ABC):
    """Abstract base for routing strategies.

    All routing strategies must implement:
    - route(): Make routing decision for a prompt
    - get_name(): Return strategy identifier for logging
    """

    @abstractmethod
    def route(self, prompt: str, context: RoutingContext) -> RoutingDecision:
        """Route prompt to optimal provider/model.

        Args:
            prompt: User's query text
            context: Additional routing context

        Returns:
            RoutingDecision with provider, model, and metadata

        Raises:
            RoutingError: If strategy cannot make decision
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Return strategy identifier for logging.

        Returns:
            Strategy name (e.g., "complexity", "learning", "hybrid")
        """
        pass
```

### Step 4: Run test to verify it passes

```bash
pytest tests/test_routing_strategy.py -v
```

**Expected:** PASS (2 tests)

### Step 5: Commit

```bash
git add app/routing/strategy.py tests/test_routing_strategy.py
git commit -m "feat: add RoutingStrategy abstract base class

- Define interface for all routing strategies
- Requires route() and get_name() methods
- Tests verify abstract behavior"
```

---

## Task 3: Implement ComplexityStrategy

**Goal:** Port existing complexity-based routing logic into strategy pattern

**Files:**

- Modify: `app/routing/strategy.py` (add ComplexityStrategy)
- Read: `app/routing/router.py` (for existing complexity logic)
- Test: `tests/test_complexity_strategy.py`

### Step 1: Write the failing test

Create `tests/test_complexity_strategy.py`:

```python
"""Tests for ComplexityStrategy."""
import pytest
from app.routing.strategy import ComplexityStrategy
from app.routing.models import RoutingContext


def test_complexity_strategy_simple_prompt():
    """Test simple prompt routes to Gemini."""
    strategy = ComplexityStrategy()
    context = RoutingContext(prompt="Hello")

    decision = strategy.route("Hello", context)

    assert decision.provider == "gemini"
    assert decision.model == "gemini-flash"
    assert decision.confidence == "medium"
    assert decision.strategy_used == "complexity"
    assert "complexity" in decision.metadata


def test_complexity_strategy_moderate_prompt():
    """Test moderate prompt routes to Claude Haiku."""
    strategy = ComplexityStrategy()
    context = RoutingContext(prompt="Explain how HTTP works")

    decision = strategy.route("Explain how HTTP works", context)

    assert decision.provider == "claude"
    assert decision.model == "claude-3-haiku"
    assert decision.confidence == "medium"


def test_complexity_strategy_complex_prompt():
    """Test complex prompt routes to Claude Sonnet."""
    strategy = ComplexityStrategy()
    long_prompt = "Analyze the architectural trade-offs between " * 10
    context = RoutingContext(prompt=long_prompt)

    decision = strategy.route(long_prompt, context)

    assert decision.provider == "claude"
    assert decision.model == "claude-3-sonnet"
    assert decision.fallback_used is False


def test_complexity_strategy_name():
    """Test strategy returns correct name."""
    strategy = ComplexityStrategy()
    assert strategy.get_name() == "complexity"
```

### Step 2: Run test to verify it fails

```bash
pytest tests/test_complexity_strategy.py -v
```

**Expected:** FAIL with `ImportError: cannot import name 'ComplexityStrategy'`

### Step 3: Write minimal implementation

Modify `app/routing/strategy.py` to add ComplexityStrategy:

```python
"""Routing strategies."""
from abc import ABC, abstractmethod
from app.routing.models import RoutingDecision, RoutingContext
from app.routing.complexity import score_complexity  # Import existing function


class RoutingStrategy(ABC):
    """Abstract base for routing strategies."""
    # ... (keep existing code)


class ComplexityStrategy(RoutingStrategy):
    """Complexity-based routing strategy (baseline).

    Routes based on prompt complexity analysis:
    - Simple (<0.3): Gemini Flash (cheap, fast)
    - Moderate (0.3-0.7): Claude Haiku (balanced)
    - Complex (>0.7): Claude Sonnet (high quality)
    """

    def route(self, prompt: str, context: RoutingContext) -> RoutingDecision:
        """Route based on prompt complexity."""
        complexity_score = score_complexity(prompt)

        # Simple prompts → Gemini
        if complexity_score < 0.3:
            provider, model = "gemini", "gemini-flash"

        # Moderate prompts → Claude Haiku
        elif complexity_score < 0.7:
            provider, model = "claude", "claude-3-haiku"

        # Complex prompts → Claude Sonnet
        else:
            provider, model = "claude", "claude-3-sonnet"

        return RoutingDecision(
            provider=provider,
            model=model,
            confidence="medium",  # Complexity has medium confidence
            strategy_used="complexity",
            reasoning=f"Complexity score: {complexity_score:.2f}",
            fallback_used=False,
            metadata={
                "complexity": complexity_score,
                "pattern": "unknown"
            }
        )

    def get_name(self) -> str:
        """Return strategy name."""
        return "complexity"
```

### Step 4: Run test to verify it passes

```bash
pytest tests/test_complexity_strategy.py -v
```

**Expected:** PASS (4 tests)

### Step 5: Commit

```bash
git add app/routing/strategy.py tests/test_complexity_strategy.py
git commit -m "feat: implement ComplexityStrategy

- Port existing complexity-based routing to strategy pattern
- Three tiers: simple (Gemini), moderate (Haiku), complex (Sonnet)
- Full test coverage for all complexity levels"
```

---

## Task 4: Implement LearningStrategy

**Goal:** Create pure learning-based routing using QueryPatternAnalyzer

**Files:**

- Modify: `app/routing/strategy.py` (add LearningStrategy)
- Test: `tests/test_learning_strategy.py`

### Step 1: Write the failing test

Create `tests/test_learning_strategy.py`:

```python
"""Tests for LearningStrategy."""
import pytest
from app.routing.strategy import LearningStrategy
from app.routing.models import RoutingContext


def test_learning_strategy_uses_analyzer(tmp_path):
    """Test LearningStrategy queries QueryPatternAnalyzer."""
    db_path = tmp_path / "test.db"
    strategy = LearningStrategy(db_path=str(db_path))
    context = RoutingContext(prompt="Debug Python code")

    decision = strategy.route("Debug Python code", context)

    assert decision.strategy_used == "learning"
    assert decision.confidence in ["high", "medium", "low"]
    assert "pattern" in decision.metadata
    assert "complexity" in decision.metadata


def test_learning_strategy_includes_quality_cost(tmp_path):
    """Test decision includes quality and cost metadata."""
    db_path = tmp_path / "test.db"
    strategy = LearningStrategy(db_path=str(db_path))
    context = RoutingContext(prompt="Test query")

    decision = strategy.route("Test query", context)

    # May be None if no training data, but key should exist
    assert "quality_score" in decision.metadata
    assert "cost_estimate" in decision.metadata


def test_learning_strategy_name():
    """Test strategy returns correct name."""
    strategy = LearningStrategy()
    assert strategy.get_name() == "learning"
```

### Step 2: Run test to verify it fails

```bash
pytest tests/test_learning_strategy.py -v
```

**Expected:** FAIL with `ImportError: cannot import name 'LearningStrategy'`

### Step 3: Write minimal implementation

Modify `app/routing/strategy.py` to add LearningStrategy:

```python
# Add to imports at top
from app.learning import QueryPatternAnalyzer
from app.routing.complexity import score_complexity

# Add after ComplexityStrategy class

class LearningStrategy(RoutingStrategy):
    """Pure learning-based routing using QueryPatternAnalyzer.

    Routes based on learned patterns from historical performance data.
    Confidence depends on sample count for detected pattern.
    """

    def __init__(self, db_path: str = "optimizer.db"):
        """Initialize with database path.

        Args:
            db_path: Path to SQLite database with training data
        """
        self.analyzer = QueryPatternAnalyzer(db_path=db_path)

    def route(self, prompt: str, context: RoutingContext) -> RoutingDecision:
        """Route based purely on learned patterns.

        Args:
            prompt: User's query text
            context: Routing context with available providers

        Returns:
            RoutingDecision based on historical performance
        """
        # Identify pattern and get recommendation
        pattern = self.analyzer.identify_pattern(prompt)
        complexity = score_complexity(prompt)

        recommendation = self.analyzer.recommend_provider(
            prompt=prompt,
            complexity=complexity,
            available_providers=context.available_providers
        )

        return RoutingDecision(
            provider=recommendation['provider'],
            model=recommendation['model'],
            confidence=recommendation['confidence'],
            strategy_used="learning",
            reasoning=recommendation.get('reasoning', 'Based on learned patterns'),
            fallback_used=False,
            metadata={
                "pattern": pattern,
                "quality_score": recommendation.get('quality_score'),
                "cost_estimate": recommendation.get('avg_cost'),
                "complexity": complexity
            }
        )

    def get_name(self) -> str:
        """Return strategy name."""
        return "learning"
```

### Step 4: Run test to verify it passes

```bash
pytest tests/test_learning_strategy.py -v
```

**Expected:** PASS (3 tests)

### Step 5: Commit

```bash
git add app/routing/strategy.py tests/test_learning_strategy.py
git commit -m "feat: implement LearningStrategy

- Pure learning-based routing using QueryPatternAnalyzer
- Returns confidence based on training data volume
- Includes pattern, quality, and cost metadata"
```

---

## Task 5: Implement HybridStrategy

**Goal:** Create hybrid strategy combining learning + complexity validation

**Files:**

- Modify: `app/routing/strategy.py` (add HybridStrategy)
- Test: `tests/test_hybrid_strategy.py`

### Step 1: Write the failing test

Create `tests/test_hybrid_strategy.py`:

```python
"""Tests for HybridStrategy."""
import pytest
from app.routing.strategy import HybridStrategy
from app.routing.models import RoutingContext


def test_hybrid_strategy_high_confidence_validated(tmp_path):
    """Test high confidence learning recommendation validated by complexity."""
    db_path = tmp_path / "test.db"
    strategy = HybridStrategy(db_path=str(db_path))
    context = RoutingContext(prompt="Test prompt")

    decision = strategy.route("Test prompt", context)

    assert decision.strategy_used == "hybrid"
    assert decision.confidence in ["high", "medium", "low"]


def test_hybrid_strategy_low_confidence_experimental(tmp_path):
    """Test low confidence marked as experimental."""
    db_path = tmp_path / "test.db"
    strategy = HybridStrategy(db_path=str(db_path))
    context = RoutingContext(prompt="Unusual query pattern")

    decision = strategy.route("Unusual query pattern", context)

    # Low confidence routes should be marked experimental
    if decision.confidence == "low":
        assert decision.metadata.get("experimental") is True


def test_hybrid_strategy_fallback_on_error(tmp_path, monkeypatch):
    """Test fallback to complexity when learning fails."""
    db_path = tmp_path / "test.db"
    strategy = HybridStrategy(db_path=str(db_path))

    # Mock learning to raise error
    def mock_route(*args, **kwargs):
        raise ValueError("Learning failed")

    monkeypatch.setattr(strategy.learning_strategy, "route", mock_route)

    context = RoutingContext(prompt="Test")
    decision = strategy.route("Test", context)

    assert decision.fallback_used is True
    assert decision.strategy_used == "complexity"  # Fell back


def test_hybrid_strategy_name():
    """Test strategy returns correct name."""
    strategy = HybridStrategy()
    assert strategy.get_name() == "hybrid"
```

### Step 2: Run test to verify it fails

```bash
pytest tests/test_hybrid_strategy.py -v
```

**Expected:** FAIL with `ImportError: cannot import name 'HybridStrategy'`

### Step 3: Write minimal implementation

Modify `app/routing/strategy.py` to add HybridStrategy:

```python
# Add import
import logging

logger = logging.getLogger(__name__)

# Add after LearningStrategy class

class HybridStrategy(RoutingStrategy):
    """Hybrid strategy combining learning with complexity validation.

    Behavior:
    - HIGH confidence: Use learning, validate against complexity
    - MEDIUM/LOW confidence: Use learning with experimental flag
    - ERROR: Fallback to complexity strategy
    """

    def __init__(self, db_path: str = "optimizer.db"):
        """Initialize with learning and complexity strategies.

        Args:
            db_path: Path to SQLite database
        """
        self.learning_strategy = LearningStrategy(db_path)
        self.complexity_strategy = ComplexityStrategy()

    def route(self, prompt: str, context: RoutingContext) -> RoutingDecision:
        """Route using learning, validated by complexity.

        Args:
            prompt: User's query text
            context: Routing context

        Returns:
            RoutingDecision from learning (validated) or fallback to complexity
        """
        try:
            # Get learning recommendation
            learning_decision = self.learning_strategy.route(prompt, context)

            # HIGH confidence: Validate against complexity
            if learning_decision.confidence == "high":
                complexity_decision = self.complexity_strategy.route(prompt, context)

                # Check if recommendations are compatible
                if self._validate_match(learning_decision, complexity_decision):
                    learning_decision.strategy_used = "hybrid"
                    learning_decision.reasoning += " (validated by complexity)"
                    return learning_decision
                else:
                    # Mismatch - use complexity as safety
                    complexity_decision.metadata['learning_mismatch'] = True
                    return complexity_decision

            # MEDIUM/LOW confidence: Use learning with experimental flag
            else:
                learning_decision.strategy_used = "hybrid"
                learning_decision.metadata['experimental'] = True
                learning_decision.reasoning += " (experimental - gathering data)"
                return learning_decision

        except Exception as e:
            # Fallback to complexity
            logger.warning(f"HybridStrategy failed: {e}")
            fallback_decision = self.complexity_strategy.route(prompt, context)
            fallback_decision.fallback_used = True
            fallback_decision.metadata['fallback_reason'] = str(e)
            return fallback_decision

    def _validate_match(
        self,
        learning: RoutingDecision,
        complexity: RoutingDecision
    ) -> bool:
        """Check if learning and complexity recommendations are compatible.

        Args:
            learning: Learning strategy decision
            complexity: Complexity strategy decision

        Returns:
            True if recommendations are compatible
        """
        # Define tier mapping
        tier_map = {
            "gemini-flash": "simple",
            "claude-3-haiku": "moderate",
            "claude-3-sonnet": "complex",
            "openrouter/deepseek-chat": "moderate",
            "openrouter/qwen-2-72b": "complex"
        }

        learning_tier = tier_map.get(learning.model, "moderate")
        complexity_tier = tier_map.get(complexity.model, "moderate")

        # Allow same tier or one tier difference
        tier_order = ["simple", "moderate", "complex"]
        learning_idx = tier_order.index(learning_tier)
        complexity_idx = tier_order.index(complexity_tier)

        return abs(learning_idx - complexity_idx) <= 1

    def get_name(self) -> str:
        """Return strategy name."""
        return "hybrid"
```

### Step 4: Run test to verify it passes

```bash
pytest tests/test_hybrid_strategy.py -v
```

**Expected:** PASS (4 tests)

### Step 5: Commit

```bash
git add app/routing/strategy.py tests/test_hybrid_strategy.py
git commit -m "feat: implement HybridStrategy with validation

- Combines learning intelligence with complexity validation
- High confidence: validates before using
- Low/medium confidence: uses with experimental flag
- Automatic fallback to complexity on errors"
```

---

## Task 6: Implement RoutingEngine

**Goal:** Create orchestrator that selects and executes strategies

**Files:**

- Create: `app/routing/engine.py`
- Test: `tests/test_routing_engine.py`

### Step 1: Write the failing test

Create `tests/test_routing_engine.py`:

```python
"""Tests for RoutingEngine."""
import pytest
from app.routing.engine import RoutingEngine
from app.routing.models import RoutingContext


def test_routing_engine_auto_route_false_uses_complexity(tmp_path):
    """Test auto_route=False uses ComplexityStrategy."""
    db_path = tmp_path / "test.db"
    engine = RoutingEngine(db_path=str(db_path))

    decision = engine.route("Test prompt", auto_route=False)

    assert decision.strategy_used == "complexity"


def test_routing_engine_auto_route_true_uses_hybrid(tmp_path):
    """Test auto_route=True uses HybridStrategy."""
    db_path = tmp_path / "test.db"
    engine = RoutingEngine(db_path=str(db_path))

    decision = engine.route("Test prompt", auto_route=True)

    assert decision.strategy_used in ["hybrid", "learning", "complexity"]


def test_routing_engine_validates_decision(tmp_path, monkeypatch):
    """Test engine validates decisions before returning."""
    db_path = tmp_path / "test.db"
    engine = RoutingEngine(db_path=str(db_path))

    # Mock strategy to return invalid decision
    from app.routing.models import RoutingDecision

    def mock_route(*args, **kwargs):
        return RoutingDecision(
            provider="invalid_provider",  # Invalid!
            model="test",
            confidence="high",
            strategy_used="test",
            reasoning="test",
            fallback_used=False,
            metadata={}
        )

    monkeypatch.setattr(
        engine.strategies['complexity'],
        'route',
        mock_route
    )

    # Should fallback due to validation failure
    decision = engine.route("Test", auto_route=False)
    assert decision.fallback_used is True


def test_routing_engine_with_custom_context(tmp_path):
    """Test engine accepts custom RoutingContext."""
    db_path = tmp_path / "test.db"
    engine = RoutingEngine(db_path=str(db_path))

    context = RoutingContext(
        prompt="Test",
        available_providers=["gemini"]
    )

    decision = engine.route("Test", auto_route=False, context=context)

    # Should respect context constraints
    assert decision.provider in context.available_providers
```

### Step 2: Run test to verify it fails

```bash
pytest tests/test_routing_engine.py -v
```

**Expected:** FAIL with `ModuleNotFoundError: No module named 'app.routing.engine'`

### Step 3: Write minimal implementation

Create `app/routing/engine.py`:

```python
"""Routing engine orchestrator."""
import logging
from typing import Optional

from app.routing.strategy import ComplexityStrategy, LearningStrategy, HybridStrategy
from app.routing.models import RoutingDecision, RoutingContext

logger = logging.getLogger(__name__)


class RoutingEngine:
    """Orchestrates routing strategy selection and execution.

    Responsibilities:
    - Select appropriate strategy based on auto_route parameter
    - Execute routing with selected strategy
    - Validate routing decisions
    - Fallback to complexity on errors
    """

    VALID_PROVIDERS = ['gemini', 'claude', 'openrouter']
    VALID_CONFIDENCE = ['high', 'medium', 'low']

    def __init__(self, db_path: str = "optimizer.db"):
        """Initialize routing engine with all strategies.

        Args:
            db_path: Path to SQLite database for learning strategies
        """
        self.db_path = db_path
        self.strategies = {
            'learning': LearningStrategy(db_path),
            'complexity': ComplexityStrategy(),
            'hybrid': HybridStrategy(db_path)
        }

    def route(
        self,
        prompt: str,
        auto_route: bool = False,
        context: Optional[RoutingContext] = None
    ) -> RoutingDecision:
        """Route prompt to optimal provider/model.

        Args:
            prompt: User's query text
            auto_route: Enable learning-powered routing
            context: Optional routing context

        Returns:
            RoutingDecision with provider, model, and metadata
        """
        if context is None:
            context = RoutingContext(prompt=prompt)

        # Select strategy
        strategy_name = 'hybrid' if auto_route else 'complexity'
        strategy = self.strategies[strategy_name]

        try:
            # Execute routing
            decision = strategy.route(prompt, context)

            # Validate decision
            if not self._is_valid_decision(decision):
                raise ValueError(f"Invalid routing decision: {decision}")

            return decision

        except Exception as e:
            logger.error(f"RoutingEngine failed: {e}")

            # Fallback to complexity
            fallback_decision = self.strategies['complexity'].route(prompt, context)
            fallback_decision.fallback_used = True
            fallback_decision.metadata['fallback_reason'] = str(e)

            return fallback_decision

    def _is_valid_decision(self, decision: RoutingDecision) -> bool:
        """Validate routing decision is safe to execute.

        Args:
            decision: Decision to validate

        Returns:
            True if decision is valid
        """
        checks = [
            decision.provider in self.VALID_PROVIDERS,
            decision.model is not None,
            decision.confidence in self.VALID_CONFIDENCE,
            decision.strategy_used in ['learning', 'complexity', 'hybrid']
        ]
        return all(checks)
```

### Step 4: Run test to verify it passes

```bash
pytest tests/test_routing_engine.py -v
```

**Expected:** PASS (4 tests)

### Step 5: Commit

```bash
git add app/routing/engine.py tests/test_routing_engine.py
git commit -m "feat: implement RoutingEngine orchestrator

- Selects strategy based on auto_route parameter
- Validates all routing decisions
- Automatic fallback to complexity on errors
- Supports custom routing context"
```

---

## Task 7: Add Metrics Tracking

**Goal:** Create routing_metrics table and MetricsCollector class

**Files:**

- Create: `app/routing/metrics.py`
- Create: `app/database/migrations/add_routing_metrics.sql`
- Test: `tests/test_routing_metrics.py`

### Step 1: Write the failing test

Create `tests/test_routing_metrics.py`:

```python
"""Tests for routing metrics tracking."""
import pytest
import sqlite3
from datetime import datetime
from app.routing.metrics import MetricsCollector
from app.routing.models import RoutingDecision


@pytest.fixture
def metrics_collector(tmp_path):
    """Create MetricsCollector with test database."""
    db_path = tmp_path / "test.db"
    collector = MetricsCollector(str(db_path))

    # Create table
    collector.conn.execute("""
        CREATE TABLE routing_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            strategy_used TEXT NOT NULL,
            confidence TEXT NOT NULL,
            selected_provider TEXT NOT NULL,
            selected_model TEXT NOT NULL,
            baseline_provider TEXT NOT NULL,
            baseline_model TEXT NOT NULL,
            baseline_cost REAL NOT NULL,
            actual_cost REAL NOT NULL,
            cost_savings REAL NOT NULL,
            savings_percentage REAL NOT NULL,
            pattern_detected TEXT,
            complexity_score REAL,
            experimental INTEGER DEFAULT 0,
            fallback_used INTEGER DEFAULT 0,
            fallback_reason TEXT
        )
    """)
    collector.conn.commit()

    return collector


def test_metrics_collector_logs_decision(metrics_collector):
    """Test MetricsCollector logs routing decisions."""
    decision = RoutingDecision(
        provider="openrouter",
        model="deepseek-chat",
        confidence="high",
        strategy_used="hybrid",
        reasoning="test",
        fallback_used=False,
        metadata={"cost_estimate": 0.0001, "pattern": "code", "complexity": 0.5}
    )

    baseline_decision = RoutingDecision(
        provider="claude",
        model="claude-3-haiku",
        confidence="medium",
        strategy_used="complexity",
        reasoning="baseline",
        fallback_used=False,
        metadata={"cost_estimate": 0.0005}
    )

    metrics_collector.log_routing_decision(
        decision=decision,
        baseline_decision=baseline_decision,
        auto_route=True,
        request_id="test_request_123"
    )

    # Verify logged to database
    cursor = metrics_collector.conn.cursor()
    cursor.execute("SELECT * FROM routing_metrics WHERE request_id = ?", ("test_request_123",))
    row = cursor.fetchone()

    assert row is not None
    assert row[3] == "hybrid"  # strategy_used
    assert row[4] == "high"  # confidence
    assert row[5] == "openrouter"  # selected_provider


def test_metrics_collector_calculates_savings(metrics_collector):
    """Test savings calculation."""
    decision = RoutingDecision(
        provider="openrouter",
        model="deepseek-chat",
        confidence="high",
        strategy_used="learning",
        reasoning="test",
        fallback_used=False,
        metadata={"cost_estimate": 0.0001}
    )

    baseline_decision = RoutingDecision(
        provider="claude",
        model="claude-3-sonnet",
        confidence="medium",
        strategy_used="complexity",
        reasoning="baseline",
        fallback_used=False,
        metadata={"cost_estimate": 0.001}
    )

    metrics_collector.log_routing_decision(
        decision=decision,
        baseline_decision=baseline_decision,
        auto_route=True,
        request_id="test_savings"
    )

    cursor = metrics_collector.conn.cursor()
    cursor.execute("""
        SELECT cost_savings, savings_percentage
        FROM routing_metrics
        WHERE request_id = ?
    """, ("test_savings",))
    row = cursor.fetchone()

    # Savings: 0.001 - 0.0001 = 0.0009 (90%)
    assert row[0] == pytest.approx(0.0009, rel=0.01)
    assert row[1] == pytest.approx(90.0, rel=0.1)


def test_metrics_collector_get_savings_summary(metrics_collector):
    """Test aggregate savings summary."""
    # Log multiple decisions
    for i in range(5):
        decision = RoutingDecision(
            provider="openrouter",
            model="deepseek-chat",
            confidence="high",
            strategy_used="hybrid",
            reasoning="test",
            fallback_used=False,
            metadata={"cost_estimate": 0.0001}
        )

        baseline_decision = RoutingDecision(
            provider="claude",
            model="claude-3-haiku",
            confidence="medium",
            strategy_used="complexity",
            reasoning="baseline",
            fallback_used=False,
            metadata={"cost_estimate": 0.0005}
        )

        metrics_collector.log_routing_decision(
            decision=decision,
            baseline_decision=baseline_decision,
            auto_route=True,
            request_id=f"test_{i}"
        )

    summary = metrics_collector.get_savings_summary(days=30)

    assert summary['total_requests'] == 5
    assert summary['auto_routed_count'] == 5
    assert summary['total_savings'] > 0
    assert summary['avg_savings_pct'] > 0
```

### Step 2: Run test to verify it fails

```bash
pytest tests/test_routing_metrics.py -v
```

**Expected:** FAIL with `ModuleNotFoundError: No module named 'app.routing.metrics'`

### Step 3: Write minimal implementation

Create `app/routing/metrics.py`:

```python
"""Metrics collection for routing decisions."""
import sqlite3
import logging
from datetime import datetime
from typing import Optional

from app.routing.models import RoutingDecision

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Collects and analyzes routing metrics.

    Tracks:
    - Cost savings vs baseline
    - Quality scores from user feedback
    - Confidence levels over time
    - Model selection patterns
    """

    def __init__(self, db_path: str):
        """Initialize with database connection.

        Args:
            db_path: Path to SQLite database
        """
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def log_routing_decision(
        self,
        decision: RoutingDecision,
        baseline_decision: RoutingDecision,
        auto_route: bool,
        request_id: str = None
    ):
        """Log routing decision for analysis.

        Args:
            decision: Actual routing decision
            baseline_decision: What complexity would've chosen
            auto_route: Whether auto_route was enabled
            request_id: Optional request identifier
        """
        # Calculate savings
        baseline_cost = baseline_decision.metadata.get('cost_estimate', 0)
        actual_cost = decision.metadata.get('cost_estimate', 0)
        cost_savings = baseline_cost - actual_cost
        savings_pct = (cost_savings / baseline_cost * 100) if baseline_cost > 0 else 0

        self.conn.execute("""
            INSERT INTO routing_metrics (
                request_id, timestamp, strategy_used, confidence,
                selected_provider, selected_model,
                baseline_provider, baseline_model, baseline_cost,
                actual_cost, cost_savings, savings_percentage,
                pattern_detected, complexity_score,
                experimental, fallback_used, fallback_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            request_id,
            datetime.now().isoformat(),
            decision.strategy_used,
            decision.confidence,
            decision.provider,
            decision.model,
            baseline_decision.provider,
            baseline_decision.model,
            baseline_cost,
            actual_cost,
            cost_savings,
            savings_pct,
            decision.metadata.get('pattern'),
            decision.metadata.get('complexity'),
            1 if decision.metadata.get('experimental') else 0,
            1 if decision.fallback_used else 0,
            decision.metadata.get('fallback_reason')
        ))

        self.conn.commit()

    def get_savings_summary(self, days: int = 30) -> dict:
        """Calculate aggregate savings vs baseline.

        Args:
            days: Number of days to analyze

        Returns:
            Summary dict with savings metrics
        """
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(*) as total_requests,
                SUM(cost_savings) as total_savings,
                AVG(savings_percentage) as avg_savings_pct,
                SUM(CASE WHEN strategy_used != 'complexity' THEN 1 ELSE 0 END) as auto_routed,
                SUM(CASE WHEN fallback_used = 1 THEN 1 ELSE 0 END) as fallback_count
            FROM routing_metrics
            WHERE timestamp > datetime('now', '-' || ? || ' days')
        """, (days,))

        row = cursor.fetchone()

        return {
            'total_requests': row[0] or 0,
            'total_savings': row[1] or 0,
            'avg_savings_pct': row[2] or 0,
            'auto_routed_count': row[3] or 0,
            'fallback_count': row[4] or 0
        }

    def get_confidence_distribution(self) -> dict:
        """Get confidence level distribution.

        Returns:
            Dict mapping confidence level to count
        """
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT confidence, COUNT(*) as count
            FROM routing_metrics
            WHERE strategy_used != 'complexity'
            GROUP BY confidence
        """)

        return {row[0]: row[1] for row in cursor.fetchall()}

    def get_model_selection_patterns(self) -> list:
        """Analyze which models are selected and why.

        Returns:
            List of dicts with model selection patterns
        """
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT
                selected_model,
                pattern_detected,
                COUNT(*) as selection_count,
                AVG(cost_savings) as avg_savings
            FROM routing_metrics
            WHERE strategy_used != 'complexity'
            GROUP BY selected_model, pattern_detected
            ORDER BY selection_count DESC
        """)

        return [
            {
                'model': row[0],
                'pattern': row[1],
                'count': row[2],
                'avg_savings': row[3]
            }
            for row in cursor.fetchall()
        ]
```

Also create the migration SQL:

Create `app/database/migrations/add_routing_metrics.sql`:

```sql
-- Migration: Add routing_metrics table for Phase 2 auto-routing

CREATE TABLE IF NOT EXISTS routing_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,

    -- Routing decision
    strategy_used TEXT NOT NULL,
    confidence TEXT NOT NULL,
    selected_provider TEXT NOT NULL,
    selected_model TEXT NOT NULL,

    -- Baseline comparison
    baseline_provider TEXT NOT NULL,
    baseline_model TEXT NOT NULL,
    baseline_cost REAL NOT NULL,

    -- Actual results
    actual_cost REAL NOT NULL,

    -- Savings calculation
    cost_savings REAL NOT NULL,
    savings_percentage REAL NOT NULL,

    -- Context
    pattern_detected TEXT,
    complexity_score REAL,
    experimental INTEGER DEFAULT 0,
    fallback_used INTEGER DEFAULT 0,
    fallback_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_routing_timestamp ON routing_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_routing_strategy ON routing_metrics(strategy_used);
CREATE INDEX IF NOT EXISTS idx_routing_confidence ON routing_metrics(confidence);
```

### Step 4: Run test to verify it passes

```bash
pytest tests/test_routing_metrics.py -v
```

**Expected:** PASS (3 tests)

### Step 5: Commit

```bash
git add app/routing/metrics.py app/database/migrations/add_routing_metrics.sql tests/test_routing_metrics.py
git commit -m "feat: add routing metrics tracking system

- MetricsCollector logs all routing decisions
- Tracks cost savings vs baseline
- Calculates aggregate savings summaries
- Analyzes confidence distribution and model patterns
- SQL migration for routing_metrics table"
```

---

## Execution Handoff

Plan complete and saved to `docs/plans/2025-01-11-phase2-auto-routing-implementation.md`.

**Two execution options:**

**1. Subagent-Driven (this session)**

- I dispatch fresh subagent per task
- Code review between tasks
- Fast iteration with quality gates

**2. Parallel Session (separate)**

- Open new session with executing-plans
- Batch execution with checkpoints
- Independent progress

**Which approach would you prefer?**
