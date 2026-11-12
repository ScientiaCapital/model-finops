"""Quality validation and scoring for cached responses."""


class QualityValidator:
    """Validates and scores cached response quality based on user feedback."""

    # Quality thresholds
    MIN_VOTES_FOR_INVALIDATION = 3
    POOR_QUALITY_THRESHOLD = 0.3
    ACCEPTABLE_QUALITY_THRESHOLD = 0.6
    GOOD_QUALITY_THRESHOLD = 0.8

    @staticmethod
    def calculate_quality_score(upvotes: int, downvotes: int) -> float | None:
        """
        Calculate quality score from vote counts.

        Quality score ranges from -1.0 (all downvotes) to 1.0 (all upvotes).
        Formula: (upvotes - downvotes) / (upvotes + downvotes)

        Args:
            upvotes: Number of positive votes
            downvotes: Number of negative votes

        Returns:
            Quality score between -1.0 and 1.0, or None if no votes
        """
        total_votes = upvotes + downvotes

        if total_votes == 0:
            return None

        # Normalize to range [-1, 1]
        score = (upvotes - downvotes) / total_votes
        return round(score, 3)

    @classmethod
    def should_invalidate(cls, quality_score: float | None, total_votes: int) -> bool:
        """
        Determine if a cached response should be invalidated.

        Invalidation criteria:
        - Must have minimum votes (prevent early invalidation)
        - Quality score must be below threshold

        Args:
            quality_score: Current quality score (or None if no votes)
            total_votes: Total number of votes received

        Returns:
            True if response should be invalidated
        """
        # Need minimum votes before invalidating
        if total_votes < cls.MIN_VOTES_FOR_INVALIDATION:
            return False

        # No votes = don't invalidate
        if quality_score is None:
            return False

        # Check if quality is below threshold
        return quality_score < cls.POOR_QUALITY_THRESHOLD

    @classmethod
    def get_quality_category(cls, quality_score: float | None) -> str:
        """
        Categorize quality score into human-readable labels.

        Args:
            quality_score: Quality score between -1.0 and 1.0

        Returns:
            Category string: "excellent", "good", "acceptable", "poor", or "unknown"
        """
        if quality_score is None:
            return "unknown"

        if quality_score >= cls.GOOD_QUALITY_THRESHOLD:
            return "excellent"
        elif quality_score >= cls.ACCEPTABLE_QUALITY_THRESHOLD:
            return "good"
        elif quality_score >= cls.POOR_QUALITY_THRESHOLD:
            return "acceptable"
        else:
            return "poor"

    @staticmethod
    def get_invalidation_reason(
        quality_score: float, total_votes: int, feedback_comments: list[str]
    ) -> str:
        """
        Generate human-readable invalidation reason.

        Args:
            quality_score: Quality score that triggered invalidation
            total_votes: Total votes received
            feedback_comments: List of user feedback comments

        Returns:
            Human-readable invalidation reason
        """
        # Count negative comments
        has_comments = len(feedback_comments) > 0
        comment_summary = (
            f" User feedback: {'; '.join(feedback_comments[:3])}" if has_comments else ""
        )

        return (
            f"Low quality score ({quality_score:.2f}) based on {total_votes} votes."
            f"{comment_summary}"
        )

    @classmethod
    def analyze_provider_quality(cls, provider_stats: list[dict]) -> dict[str, dict]:
        """
        Analyze quality metrics by provider.

        Args:
            provider_stats: List of dicts with provider quality data

        Returns:
            Dictionary mapping provider name to quality analysis
        """
        analysis = {}

        for stat in provider_stats:
            provider = stat["provider"]
            quality_score = stat.get("avg_quality_score")
            total_votes = stat.get("total_votes", 0)

            analysis[provider] = {
                "quality_score": quality_score,
                "quality_category": cls.get_quality_category(quality_score),
                "total_votes": total_votes,
                "confidence": "high"
                if total_votes >= 10
                else "medium"
                if total_votes >= 5
                else "low",
            }

        return analysis

    @staticmethod
    def recommend_action(
        quality_score: float | None, total_votes: int, hit_count: int
    ) -> tuple[str, str]:
        """
        Recommend action for a cached response.

        Args:
            quality_score: Current quality score
            total_votes: Number of votes received
            hit_count: Number of times response was used

        Returns:
            Tuple of (action, reason)
            Actions: "keep", "monitor", "invalidate", "request_feedback"
        """
        # No votes yet but used frequently
        if total_votes == 0 and hit_count >= 5:
            return ("request_feedback", "Popular response needs quality validation")

        # Not enough votes to judge
        if total_votes < 3:
            return ("monitor", "Insufficient feedback to make decision")

        # Good quality - keep it
        if quality_score is not None and quality_score >= 0.6:
            return ("keep", f"High quality score ({quality_score:.2f})")

        # Poor quality - invalidate
        if quality_score is not None and quality_score < 0.3:
            return ("invalidate", f"Low quality score ({quality_score:.2f})")

        # Borderline - monitor
        return ("monitor", f"Acceptable quality ({quality_score:.2f}) but needs more data")
