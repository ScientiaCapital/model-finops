"""Intelligent routing based on historical performance data."""

import sqlite3
from datetime import datetime, timedelta


class QueryPatternAnalyzer:
    """Analyzes query patterns and recommends providers based on historical data."""

    # Query type keywords for pattern matching
    QUERY_PATTERNS = {
        "code": ["code", "function", "class", "debug", "refactor", "bug", "implement", "algorithm"],
        "analysis": ["analyze", "compare", "evaluate", "assess", "review", "critique"],
        "creative": ["write", "create", "generate", "story", "poem", "email", "draft"],
        "explanation": ["explain", "what is", "how does", "why", "describe", "teach"],
        "factual": ["who", "when", "where", "list", "define", "facts", "history"],
        "reasoning": ["solve", "calculate", "prove", "deduce", "logic", "math", "problem"],
    }

    def __init__(self, db_path: str) -> None:
        """Initialize analyzer with database connection.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def identify_pattern(self, prompt: str) -> str:
        """Identify the primary pattern/category of a query.

        Args:
            prompt: User prompt text

        Returns:
            Pattern name (e.g., "code", "analysis") or "general"
        """
        prompt_lower = prompt.lower()

        # Count keyword matches for each pattern
        pattern_scores = {}
        for pattern_name, keywords in self.QUERY_PATTERNS.items():
            score = sum(1 for keyword in keywords if keyword in prompt_lower)
            if score > 0:
                pattern_scores[pattern_name] = score

        # Return pattern with highest score
        if pattern_scores:
            return max(pattern_scores, key=pattern_scores.get)

        return "general"

    def get_provider_performance(
        self, complexity: str, pattern: str | None = None, days: int = 30
    ) -> list[dict]:
        """Get historical provider performance for a complexity level.

        Args:
            complexity: Complexity level (simple, moderate, complex)
            pattern: Optional query pattern to filter by
            days: Look back this many days (default 30)

        Returns:
            List of provider performance dicts sorted by score
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Calculate date threshold
        date_threshold = (datetime.now() - timedelta(days=days)).isoformat()

        # Query for provider stats with optional pattern filter using prompt keywords
        base_query = """
            SELECT
                provider,
                model,
                COUNT(*) as request_count,
                AVG(cost) as avg_cost,
                AVG(quality_score) as avg_quality,
                SUM(CASE WHEN quality_score IS NOT NULL THEN 1 ELSE 0 END) as rated_count,
                SUM(upvotes) as total_upvotes,
                SUM(downvotes) as total_downvotes,
                AVG(CASE WHEN invalidated = 0 THEN 1 ELSE 0 END) as validity_rate
            FROM response_cache
            WHERE complexity = ?
                AND created_at >= ?
        """

        params: list[object] = [complexity, date_threshold]

        # Apply keyword-based filter on prompt_normalized when a pattern is provided
        if pattern and pattern in self.QUERY_PATTERNS:
            keywords = self.QUERY_PATTERNS.get(pattern, [])
            if keywords:
                like_clauses = " OR ".join(["prompt_normalized LIKE ?"] * len(keywords))
                base_query += f" AND ({like_clauses})\n"
                params.extend([f"%{kw}%" for kw in keywords])

        base_query += """
            GROUP BY provider, model
            ORDER BY avg_quality DESC, avg_cost ASC
        """

        cursor.execute(base_query, params)

        results = []
        for row in cursor.fetchall():
            performance = {
                "provider": row["provider"],
                "model": row["model"],
                "request_count": row["request_count"],
                "avg_cost": round(row["avg_cost"], 6) if row["avg_cost"] else 0.0,
                "avg_quality": round(row["avg_quality"], 3) if row["avg_quality"] else None,
                "rated_count": row["rated_count"],
                "total_upvotes": row["total_upvotes"],
                "total_downvotes": row["total_downvotes"],
                "validity_rate": round(row["validity_rate"], 3),
                "confidence": self._calculate_confidence(row["request_count"], row["rated_count"]),
            }

            # Calculate composite score
            performance["score"] = self._calculate_composite_score(performance)
            results.append(performance)

        conn.close()

        # Sort by composite score
        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    def _calculate_confidence(self, request_count: int, rated_count: int) -> str:
        """Calculate confidence level based on data volume.

        Args:
            request_count: Number of requests
            rated_count: Number of rated requests

        Returns:
            Confidence level: "high", "medium", or "low"
        """
        if request_count >= 10 and rated_count >= 5:
            return "high"
        elif request_count >= 5 and rated_count >= 2:
            return "medium"
        else:
            return "low"

    def _calculate_composite_score(self, performance: dict) -> float:
        """Calculate composite score for provider ranking.

        Balances quality, cost, and reliability.

        Args:
            performance: Performance metrics dict

        Returns:
            Composite score (higher is better)
        """
        # Default weights
        quality_weight = 0.5
        cost_weight = 0.3
        validity_weight = 0.2

        # Quality score (normalize from [-1, 1] to [0, 1])
        quality = performance["avg_quality"]
        # Neutral 0.5 with no ratings; otherwise map [-1, 1] to [0, 1]
        quality_score = 0.5 if quality is None else (quality + 1) / 2

        # Cost score (inverse - lower cost is better)
        # Normalize assuming typical range $0.0001 to $0.01 per request
        cost = performance["avg_cost"]
        cost_score = 1.0 if cost <= 0 else max(0, 1 - (cost / 0.01))  # lower cost, higher score

        # Validity score (already 0-1)
        validity_score = performance["validity_rate"]

        # Calculate weighted score
        composite = (
            quality_score * quality_weight
            + cost_score * cost_weight
            + validity_score * validity_weight
        )

        # Apply confidence penalty for low data
        confidence = performance["confidence"]
        if confidence == "low":
            composite *= 0.7
        elif confidence == "medium":
            composite *= 0.85

        return round(composite, 3)

    def recommend_provider(
        self, prompt: str, complexity: str, available_providers: list[str]
    ) -> dict | None:
        """Recommend a provider based on historical performance.

        Args:
            prompt: User prompt
            complexity: Complexity score from complexity module
            available_providers: List of currently available providers

        Returns:
            Recommendation dict with provider, model, confidence, reasoning
            or None if insufficient data
        """
        # Identify query pattern
        pattern = self.identify_pattern(prompt)

        # Get historical performance
        performances = self.get_provider_performance(complexity, pattern)

        # Filter to available providers
        available_performances = [p for p in performances if p["provider"] in available_providers]

        if not available_performances:
            return None

        # Get top recommendation
        top = available_performances[0]

        # Only recommend if we have reasonable confidence
        if top["confidence"] == "low" and top["request_count"] < 3:
            return None

        # Build reasoning
        reasoning_parts = []

        if top["avg_quality"] is not None:
            quality_label = self._quality_label(top["avg_quality"])
            reasoning_parts.append(f"{quality_label} quality ({top['avg_quality']:.2f})")

        reasoning_parts.append(f"${top['avg_cost']:.6f} avg cost")
        reasoning_parts.append(f"{top['request_count']} historical requests")

        if top["rated_count"] > 0:
            reasoning_parts.append(
                f"{top['total_upvotes']} upvotes, {top['total_downvotes']} downvotes"
            )

        return {
            "provider": top["provider"],
            "model": top["model"],
            "confidence": top["confidence"],
            "score": top["score"],
            "avg_cost": top["avg_cost"],
            "avg_quality": top["avg_quality"],
            "pattern": pattern,
            "reasoning": " | ".join(reasoning_parts),
            "alternatives": available_performances[1:3] if len(available_performances) > 1 else [],
        }

    def _quality_label(self, quality_score: float) -> str:
        """Convert quality score to human label.

        Args:
            quality_score: Score from -1 to 1

        Returns:
            Label like "Excellent", "Good", etc.
        """
        if quality_score >= 0.8:
            return "Excellent"
        elif quality_score >= 0.6:
            return "Good"
        elif quality_score >= 0.3:
            return "Acceptable"
        else:
            return "Poor"

    def get_insights(self) -> dict:
        """Get learning insights and statistics.

        Returns:
            Dict with patterns, provider trends, and recommendations
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Overall stats
        cursor.execute("""
            SELECT
                COUNT(DISTINCT prompt_normalized) as unique_queries,
                COUNT(*) as total_requests,
                SUM(hit_count) as total_cache_hits,
                COUNT(CASE WHEN quality_score IS NOT NULL THEN 1 END) as rated_responses,
                AVG(quality_score) as avg_quality
            FROM response_cache
        """)
        overall = dict(cursor.fetchone())

        # Provider performance
        cursor.execute("""
            SELECT
                provider,
                COUNT(*) as requests,
                AVG(quality_score) as avg_quality,
                AVG(cost) as avg_cost,
                SUM(upvotes) as upvotes,
                SUM(downvotes) as downvotes
            FROM response_cache
            GROUP BY provider
            ORDER BY avg_quality DESC
        """)
        providers = [dict(row) for row in cursor.fetchall()]

        # Complexity breakdown
        cursor.execute("""
            SELECT
                complexity,
                COUNT(*) as requests,
                AVG(quality_score) as avg_quality,
                AVG(cost) as avg_cost
            FROM response_cache
            GROUP BY complexity
            ORDER BY
                CASE complexity
                    WHEN 'simple' THEN 1
                    WHEN 'moderate' THEN 2
                    WHEN 'complex' THEN 3
                END
        """)
        complexities = [dict(row) for row in cursor.fetchall()]

        conn.close()

        return {
            "overall": overall,
            "by_provider": providers,
            "by_complexity": complexities,
            "learning_active": overall["rated_responses"] >= 5,
        }

    def get_pattern_confidence_levels(self) -> dict[str, dict]:
        """Get confidence levels for each query pattern.

        Returns:
            Dict mapping pattern name to confidence info:
            {
                'code': {'sample_count': 23, 'confidence': 'high', 'best_model': '...'},
                'explanation': {'sample_count': 8, 'confidence': 'medium', ...}
            }
        """
        results = {}

        for pattern in self.QUERY_PATTERNS:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Build pattern filter using keywords
            keywords = self.QUERY_PATTERNS[pattern][:5]  # Use first 5 keywords
            like_conditions = " OR ".join(["prompt_normalized LIKE ?" for _ in keywords])
            params = [f"%{kw}%" for kw in keywords]

            query = f"""
                SELECT
                    COUNT(*) as count,
                    model,
                    AVG(quality_score) as quality
                FROM response_cache
                WHERE ({like_conditions})
                    AND model IS NOT NULL
                    AND model != ''
                GROUP BY model
                ORDER BY quality DESC, count DESC
                LIMIT 1
            """  # nosec B608 # constant "LIKE ?" clauses; values are bound

            cursor.execute(query, params)

            row = cursor.fetchone()
            count = row["count"] if row else 0
            best_model = row["model"] if row and count > 0 else None

            conn.close()

            # Confidence thresholds
            if count >= 20:
                confidence = "high"
            elif count >= 10:
                confidence = "medium"
            else:
                confidence = "low"

            results[pattern] = {
                "sample_count": count,
                "confidence": confidence,
                "best_model": best_model,
                "samples_needed": max(0, 20 - count),
            }

        return results
