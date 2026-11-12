"""Tests for enhanced learning.py with pattern confidence tracking."""

import os
import sqlite3

import pytest

from app.learning import QueryPatternAnalyzer


@pytest.fixture
def test_db():
    """Create temporary test database with production schema."""
    db_path = "test_learning.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create production schema (response_cache table)
    cursor.execute("""
        CREATE TABLE response_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt_normalized TEXT NOT NULL UNIQUE,
            prompt_hash TEXT NOT NULL UNIQUE,
            complexity TEXT NOT NULL,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            response_text TEXT NOT NULL,
            tokens_in INTEGER DEFAULT 0,
            tokens_out INTEGER DEFAULT 0,
            cost REAL DEFAULT 0.0,
            quality_score REAL,
            upvotes INTEGER DEFAULT 0,
            downvotes INTEGER DEFAULT 0,
            invalidated INTEGER DEFAULT 0,
            hit_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_used_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Insert test data with various patterns
    test_data = [
        (
            "debug python code",
            "hash1",
            "complex",
            "openrouter",
            "openrouter/deepseek-coder",
            "Fixed code",
            100,
            300,
            0.00024,
            0.9,
            5,
            0,
            0,
            2,
            "2025-01-01 10:00:00",
            "2025-01-01 10:00:00",
        ),
        (
            "explain microservices architecture",
            "hash2",
            "moderate",
            "claude",
            "claude-3-haiku-20240307",
            "Explanation",
            50,
            200,
            0.00095,
            0.8,
            4,
            1,
            0,
            1,
            "2025-01-01 10:05:00",
            "2025-01-01 10:05:00",
        ),
        (
            "write a python function for sorting",
            "hash3",
            "complex",
            "openrouter",
            "openrouter/deepseek-coder",
            "Function code",
            80,
            250,
            0.00020,
            0.95,
            6,
            0,
            0,
            3,
            "2025-01-01 10:10:00",
            "2025-01-01 10:10:00",
        ),
        (
            "what is docker container",
            "hash4",
            "simple",
            "google",
            "gemini-1.5-flash-latest",
            "Docker info",
            30,
            150,
            0.00008,
            0.7,
            3,
            1,
            0,
            1,
            "2025-01-01 10:15:00",
            "2025-01-01 10:15:00",
        ),
        (
            "how does kubernetes work",
            "hash5",
            "moderate",
            "claude",
            "claude-3-haiku-20240307",
            "K8s explanation",
            60,
            220,
            0.00090,
            0.85,
            5,
            0,
            0,
            2,
            "2025-01-01 10:20:00",
            "2025-01-01 10:20:00",
        ),
    ]

    for data in test_data:
        cursor.execute(
            """INSERT INTO response_cache
            (prompt_normalized, prompt_hash, complexity, provider, model, response_text,
             tokens_in, tokens_out, cost, quality_score, upvotes, downvotes, invalidated,
             hit_count, created_at, last_used_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            data,
        )

    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


def test_pattern_confidence_levels(test_db):
    """Pattern confidence levels based on sample count."""
    analyzer = QueryPatternAnalyzer(db_path=test_db)

    confidence = analyzer.get_pattern_confidence_levels()

    # Should have all patterns
    assert "code" in confidence
    assert "explanation" in confidence
    assert "factual" in confidence

    # Verify structure
    for _pattern_name, pattern_data in confidence.items():
        assert "sample_count" in pattern_data
        assert "confidence" in pattern_data
        assert "best_model" in pattern_data
        assert "samples_needed" in pattern_data
        assert pattern_data["confidence"] in ["high", "medium", "low"]
        assert isinstance(pattern_data["sample_count"], int)
        assert isinstance(pattern_data["samples_needed"], int)

    # Code pattern should have samples (we have "debug" and "write" keywords)
    assert confidence["code"]["sample_count"] >= 2

    # Explanation pattern should have samples (we have "explain" and "how does")
    assert confidence["explanation"]["sample_count"] >= 2
