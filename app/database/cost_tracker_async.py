"""Async CostTracker for Supabase with semantic caching and multi-tenancy."""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from app.database.supabase_client import get_supabase_client
from app.embeddings import get_embedding_generator

logger = logging.getLogger(__name__)


class AsyncCostTracker:
    """
    Async cost tracker with Supabase backend and semantic caching.

    Key Features:
    - Async database operations (non-blocking)
    - Semantic cache matching with pgvector
    - Multi-tenant RLS support via user_id
    - Embedding generation for prompts
    - Quality tracking and feedback

    Architecture:
    - Uses SupabaseClient for all database operations
    - Uses EmbeddingGenerator for semantic search
    - All methods are async (await required)
    """

    def __init__(self, user_id: Optional[str] = None):
        """
        Initialize async cost tracker.

        Args:
            user_id: Optional user ID for RLS context (UUID string)
                    If None, operates in admin mode (bypasses RLS)
        """
        self.user_id = user_id
        self.db = get_supabase_client()
        self.embeddings = get_embedding_generator()

        logger.info(f"AsyncCostTracker initialized (user_id={user_id})")

    def set_user_context(self, user_id: str) -> None:
        """
        Set user context for RLS.

        Args:
            user_id: User ID (UUID string)
        """
        self.user_id = user_id
        logger.debug(f"User context set to {user_id}")

    # ==================== GROUP 1: CORE LOGGING ====================

    async def log_request(
        self,
        prompt: str,
        complexity: str,
        provider: str,
        model: str,
        tokens_in: int,
        tokens_out: int,
        cost: float
    ) -> Dict[str, Any]:
        """
        Log a completed request to the database.

        Args:
            prompt: User's prompt (will be truncated for storage)
            complexity: Classification (simple/complex)
            provider: Provider name (gemini/claude/openrouter)
            model: Model identifier
            tokens_in: Input token count
            tokens_out: Output token count
            cost: Total cost in USD

        Returns:
            Inserted row data
        """
        # Truncate prompt for preview (first 100 chars)
        prompt_preview = prompt[:100] + "..." if len(prompt) > 100 else prompt

        data = {
            "timestamp": datetime.now().isoformat(),
            "prompt_preview": prompt_preview,
            "complexity": complexity,
            "provider": provider,
            "model": model,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost": cost,
            "user_id": self.user_id  # For RLS
        }

        # Use admin mode if no user_id (backward compatibility)
        use_admin = self.user_id is None

        result = await self.db.insert("requests", data, use_admin=use_admin)

        logger.info(
            f"Logged request: {provider}/{model}, "
            f"{tokens_in}→{tokens_out} tokens, ${cost:.6f}"
        )

        return result

    async def get_total_cost(self) -> float:
        """
        Get total cost across all requests for current user.

        Returns:
            Total cost in USD
        """
        # Build filter for user-scoped query
        filters = {}
        if self.user_id:
            filters["user_id"] = self.user_id

        # Use admin mode if no user_id
        use_admin = self.user_id is None

        # Supabase doesn't have SUM in select, so fetch all and sum in Python
        rows = await self.db.select(
            "requests",
            columns="cost",
            filters=filters,
            use_admin=use_admin
        )

        total = sum(row.get("cost", 0.0) for row in rows)

        logger.debug(f"Total cost: ${total:.6f} ({len(rows)} requests)")

        return total

    # ==================== GROUP 2: SEMANTIC CACHING ====================

    def _normalize_prompt(self, prompt: str) -> str:
        """
        Normalize prompt for consistent caching.

        Normalization rules:
        - Strip leading/trailing whitespace
        - Normalize internal whitespace (multiple spaces → single space)
        - Preserve case (embeddings are case-aware)

        Args:
            prompt: Raw user prompt

        Returns:
            Normalized prompt string
        """
        return " ".join(prompt.split())

    async def check_cache(
        self,
        prompt: str,
        max_tokens: int,
        similarity_threshold: float = 0.95
    ) -> Optional[Dict[str, Any]]:
        """
        Check if semantically similar response exists in cache.

        This is the BIG difference from old hash-based caching!

        OLD APPROACH (exact match):
        - hash("What is Python?") = abc123
        - hash("what is python?") = def456  ← Different hash, cache miss!

        NEW APPROACH (semantic match):
        - embedding("What is Python?") ≈ [0.1, -0.2, 0.5, ...]
        - embedding("what is python?") ≈ [0.1, -0.2, 0.5, ...]  ← Similar vectors!
        - cosine_similarity = 0.98 > 0.95 threshold ← Cache HIT! 🎉

        Args:
            prompt: User prompt
            max_tokens: Maximum response tokens (not used yet, for future)
            similarity_threshold: Minimum similarity score (0.0-1.0)

        Returns:
            Dictionary with cached response data if found, None otherwise
        """
        # Step 1: Normalize the prompt
        normalized_prompt = self._normalize_prompt(prompt)

        # Step 2: Generate embedding for the query prompt
        logger.debug(f"Generating embedding for cache lookup: '{normalized_prompt[:50]}...'")
        try:
            query_embedding = self.embeddings.generate_embedding(normalized_prompt)
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return None  # Fall back to API call if embeddings fail

        # Step 3: Perform semantic search using pgvector
        logger.debug(
            f"Searching cache with threshold={similarity_threshold}, "
            f"embedding_dim={len(query_embedding)}"
        )

        try:
            matches = await self.db.semantic_search(
                query_embedding=query_embedding,
                match_threshold=similarity_threshold,
                match_count=1,  # Only need the best match
                user_id=self.user_id  # RLS filtering
            )

            if not matches:
                logger.debug("No semantic cache matches found")
                return None

            # We found a match! 🎉
            best_match = matches[0]
            similarity = best_match.get("similarity", 0.0)

            logger.info(
                f"✅ Cache HIT! Similarity={similarity:.3f}, "
                f"Original: '{best_match['prompt_normalized'][:50]}...'"
            )

            return {
                "cache_key": best_match["cache_key"],
                "response": best_match["response"],
                "provider": best_match["provider"],
                "model": best_match["model"],
                "tokens_in": best_match.get("tokens_in", 0),
                "tokens_out": best_match.get("tokens_out", 0),
                "cost": best_match.get("cost", 0.0),
                "hit_count": best_match.get("hit_count", 0),
                "quality_score": best_match.get("quality_score"),
                "similarity": similarity  # NEW! How similar was the match
            }

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return None

    async def store_in_cache(
        self,
        prompt: str,
        max_tokens: int,
        response: str,
        provider: str,
        model: str,
        complexity: str,
        tokens_in: int,
        tokens_out: int,
        cost: float
    ) -> Dict[str, Any]:
        """
        Store response in cache with semantic embedding.

        This generates a 384-dimensional vector representation of the prompt
        and stores it alongside the response for future semantic matching.

        Args:
            prompt: User prompt
            max_tokens: Maximum response tokens
            response: LLM response text
            provider: Provider name
            model: Model identifier
            complexity: Complexity classification
            tokens_in: Input token count
            tokens_out: Output token count
            cost: Total cost in USD

        Returns:
            Inserted cache entry
        """
        # Step 1: Normalize prompt
        normalized_prompt = self._normalize_prompt(prompt)

        # Step 2: Generate embedding
        logger.debug(f"Generating embedding for cache storage: '{normalized_prompt[:50]}...'")
        embedding = self.embeddings.generate_embedding(normalized_prompt)

        # Step 3: Generate cache key (still used as primary key)
        # We'll use a hash for the cache_key, but the REAL magic is the embedding!
        import hashlib
        cache_input = f"{normalized_prompt}|{max_tokens}"
        cache_key = hashlib.sha256(cache_input.encode()).hexdigest()

        now = datetime.now().isoformat()

        # Step 4: Store in Supabase with embedding
        data = {
            "cache_key": cache_key,
            "prompt_normalized": normalized_prompt,
            "max_tokens": max_tokens,
            "response": response,
            "provider": provider,
            "model": model,
            "complexity": complexity,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost": cost,
            "created_at": now,
            "last_accessed": now,
            "hit_count": 0,
            "embedding": embedding,  # ← The magic 384-dimensional vector! ✨
            "user_id": self.user_id,  # Multi-tenant RLS
            "upvotes": 0,
            "downvotes": 0,
            "invalidated": 0
        }

        use_admin = self.user_id is None

        result = await self.db.upsert(
            "response_cache",
            data,
            on_conflict="cache_key",
            use_admin=use_admin
        )

        logger.info(
            f"Stored in cache: {cache_key[:16]}..., "
            f"embedding_dim={len(embedding)}"
        )

        return result[0] if result else {}

    async def record_cache_hit(self, cache_key: str) -> None:
        """
        Record that a cached response was used.

        Increments hit_count and updates last_accessed timestamp.

        Args:
            cache_key: Cache key of used response
        """
        now = datetime.now().isoformat()

        # We need to increment hit_count, but Supabase doesn't have ++ syntax
        # Solution: Fetch current count, increment, update
        # (In production, you'd use a PostgreSQL function for atomicity)

        use_admin = self.user_id is None

        # Fetch current entry
        rows = await self.db.select(
            "response_cache",
            columns="hit_count",
            filters={"cache_key": cache_key},
            use_admin=use_admin
        )

        if not rows:
            logger.warning(f"Cache key not found for hit recording: {cache_key}")
            return

        current_hits = rows[0].get("hit_count", 0)
        new_hits = current_hits + 1

        # Update with incremented count
        await self.db.update(
            "response_cache",
            data={
                "hit_count": new_hits,
                "last_accessed": now
            },
            filters={"cache_key": cache_key},
            use_admin=use_admin
        )

        logger.debug(f"Cache hit recorded: {cache_key[:16]}... (hits={new_hits})")

    async def batch_store_in_cache(
        self,
        entries: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Batch store multiple responses in cache with embeddings.

        This is more efficient than calling store_in_cache() multiple times
        because it generates embeddings in a single batch operation and
        performs a single database upsert.

        Args:
            entries: List of cache entry dictionaries, each containing:
                - prompt: User prompt
                - max_tokens: Maximum response tokens
                - response: LLM response text
                - provider: Provider name
                - model: Model identifier
                - complexity: Complexity classification
                - tokens_in: Input token count
                - tokens_out: Output token count
                - cost: Total cost in USD

        Returns:
            List of inserted cache entries

        Example:
            entries = [
                {"prompt": "What is Python?", "max_tokens": 100, ...},
                {"prompt": "Explain React hooks", "max_tokens": 200, ...},
            ]
            results = await tracker.batch_store_in_cache(entries)
        """
        import hashlib

        if not entries:
            return []

        # Step 1: Normalize all prompts
        normalized_prompts = [
            self._normalize_prompt(e["prompt"]) for e in entries
        ]

        # Step 2: Batch generate embeddings (much more efficient!)
        logger.info(f"Generating {len(entries)} embeddings in batch...")
        embeddings = self.embeddings.generate_embeddings(normalized_prompts)

        # Step 3: Prepare cache data
        now = datetime.now().isoformat()
        cache_data = []

        for i, entry in enumerate(entries):
            normalized_prompt = normalized_prompts[i]
            embedding = embeddings[i]

            # Generate cache key
            cache_input = f"{normalized_prompt}|{entry['max_tokens']}"
            cache_key = hashlib.sha256(cache_input.encode()).hexdigest()

            cache_data.append({
                "cache_key": cache_key,
                "prompt_normalized": normalized_prompt,
                "max_tokens": entry["max_tokens"],
                "response": entry["response"],
                "provider": entry["provider"],
                "model": entry["model"],
                "complexity": entry["complexity"],
                "tokens_in": entry["tokens_in"],
                "tokens_out": entry["tokens_out"],
                "cost": entry["cost"],
                "created_at": now,
                "last_accessed": now,
                "hit_count": 0,
                "embedding": embedding,
                "user_id": self.user_id,
                "upvotes": 0,
                "downvotes": 0,
                "invalidated": 0
            })

        # Step 4: Batch upsert to database
        use_admin = self.user_id is None

        result = await self.db.upsert(
            "response_cache",
            cache_data,
            on_conflict="cache_key",
            use_admin=use_admin
        )

        logger.info(f"Batch stored {len(cache_data)} cache entries")

        return result

    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics using Supabase function.

        Returns:
            Dictionary with:
            - total_entries: Number of cached responses
            - total_hits: Sum of all hit counts
            - avg_quality_score: Average quality
            - cache_size_bytes: Total storage used
        """
        if not self.user_id:
            # Admin mode - need to aggregate manually
            logger.warning("get_cache_stats in admin mode - manual aggregation")
            rows = await self.db.select(
                "response_cache",
                columns="hit_count,quality_score,response",
                use_admin=True
            )

            total_entries = len(rows)
            total_hits = sum(r.get("hit_count", 0) for r in rows)
            scores = [r.get("quality_score", 0) for r in rows if r.get("quality_score")]
            avg_quality = sum(scores) / len(scores) if scores else 0.0
            cache_size = sum(len(r.get("response", "")) for r in rows)

            return {
                "total_entries": total_entries,
                "total_hits": total_hits,
                "avg_quality_score": avg_quality,
                "cache_size_bytes": cache_size
            }

        # User mode - use Supabase function
        stats = await self.db.get_cache_stats(self.user_id)
        return stats

    # ==================== GROUP 3: STATISTICS ====================

    async def get_usage_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive usage statistics for current user.

        Returns:
            Dictionary with request counts, costs, and breakdowns
        """
        filters = {}
        if self.user_id:
            filters["user_id"] = self.user_id

        use_admin = self.user_id is None

        # Fetch all requests for user
        requests = await self.db.select(
            "requests",
            columns="provider,complexity,cost,tokens_in,tokens_out,timestamp,prompt_preview,model",
            filters=filters,
            order_by="-timestamp",
            use_admin=use_admin
        )

        if not requests:
            return {
                "overall": {
                    "total_requests": 0,
                    "total_cost": 0.0,
                    "total_tokens_in": 0,
                    "total_tokens_out": 0,
                    "avg_cost_per_request": 0.0
                },
                "by_provider": [],
                "by_complexity": [],
                "recent_requests": []
            }

        # Calculate overall stats
        total_requests = len(requests)
        total_cost = sum(r.get("cost", 0.0) for r in requests)
        total_tokens_in = sum(r.get("tokens_in", 0) for r in requests)
        total_tokens_out = sum(r.get("tokens_out", 0) for r in requests)
        avg_cost = total_cost / total_requests if total_requests > 0 else 0.0

        # Group by provider
        by_provider = {}
        for req in requests:
            provider = req.get("provider", "unknown")
            if provider not in by_provider:
                by_provider[provider] = {
                    "provider": provider,
                    "request_count": 0,
                    "total_cost": 0.0,
                    "avg_cost": 0.0
                }
            by_provider[provider]["request_count"] += 1
            by_provider[provider]["total_cost"] += req.get("cost", 0.0)

        # Calculate averages
        for provider_stats in by_provider.values():
            count = provider_stats["request_count"]
            provider_stats["avg_cost"] = provider_stats["total_cost"] / count if count > 0 else 0.0

        # Group by complexity
        by_complexity = {}
        for req in requests:
            complexity = req.get("complexity", "unknown")
            if complexity not in by_complexity:
                by_complexity[complexity] = {
                    "complexity": complexity,
                    "request_count": 0,
                    "total_cost": 0.0,
                    "avg_cost": 0.0
                }
            by_complexity[complexity]["request_count"] += 1
            by_complexity[complexity]["total_cost"] += req.get("cost", 0.0)

        # Calculate averages
        for complexity_stats in by_complexity.values():
            count = complexity_stats["request_count"]
            complexity_stats["avg_cost"] = complexity_stats["total_cost"] / count if count > 0 else 0.0

        # Recent requests (already sorted by timestamp DESC)
        recent_requests = requests[:10]

        return {
            "overall": {
                "total_requests": total_requests,
                "total_cost": total_cost,
                "total_tokens_in": total_tokens_in,
                "total_tokens_out": total_tokens_out,
                "avg_cost_per_request": avg_cost
            },
            "by_provider": list(by_provider.values()),
            "by_complexity": list(by_complexity.values()),
            "recent_requests": recent_requests
        }

    async def get_request_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent request history for current user.

        Args:
            limit: Maximum number of requests to return

        Returns:
            List of request dictionaries
        """
        filters = {}
        if self.user_id:
            filters["user_id"] = self.user_id

        use_admin = self.user_id is None

        requests = await self.db.select(
            "requests",
            columns="id,timestamp,prompt_preview,complexity,provider,model,tokens_in,tokens_out,cost",
            filters=filters,
            order_by="-timestamp",
            limit=limit,
            use_admin=use_admin
        )

        logger.debug(f"Fetched {len(requests)} request history entries")

        return requests

    async def clear_history(self) -> int:
        """
        Clear all request history for current user.

        WARNING: This is destructive! Use with caution.

        Returns:
            Number of deleted requests
        """
        if not self.user_id:
            logger.error("Cannot clear_history in admin mode (safety check)")
            raise ValueError("clear_history requires user_id to be set")

        # Get count before deletion
        existing = await self.db.select(
            "requests",
            columns="id",
            filters={"user_id": self.user_id},
            use_admin=False
        )

        count = len(existing)

        # Delete all user's requests
        await self.db.delete(
            "requests",
            filters={"user_id": self.user_id},
            use_admin=False
        )

        logger.warning(f"Cleared {count} requests for user {self.user_id}")

        return count

    async def clear_cache(self) -> int:
        """
        Clear all cached responses for current user.

        WARNING: This is destructive! Use with caution.

        Returns:
            Number of deleted cache entries
        """
        if not self.user_id:
            logger.error("Cannot clear_cache in admin mode (safety check)")
            raise ValueError("clear_cache requires user_id to be set")

        # Get count before deletion
        existing = await self.db.select(
            "response_cache",
            columns="cache_key",
            filters={"user_id": self.user_id},
            use_admin=False
        )

        count = len(existing)

        # Delete all user's cache
        await self.db.delete(
            "response_cache",
            filters={"user_id": self.user_id},
            use_admin=False
        )

        logger.warning(f"Cleared {count} cache entries for user {self.user_id}")

        return count

    # ==================== GROUP 4: QUALITY & FEEDBACK ====================

    async def add_feedback(
        self,
        cache_key: str,
        rating: int,
        comment: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """
        Add user feedback for a cached response.

        Args:
            cache_key: Cache key of response being rated
            rating: 1 for upvote, -1 for downvote
            comment: Optional user comment
            user_agent: Optional user agent string

        Returns:
            True if feedback was recorded successfully

        Raises:
            ValueError: If rating is not 1 or -1
        """
        if rating not in [1, -1]:
            raise ValueError("Rating must be 1 (upvote) or -1 (downvote)")

        use_admin = self.user_id is None

        # Step 1: Store feedback in response_feedback table
        feedback_data = {
            "cache_key": cache_key,
            "rating": rating,
            "comment": comment,
            "user_agent": user_agent,
            "timestamp": datetime.now().isoformat()
        }

        await self.db.insert("response_feedback", feedback_data, use_admin=use_admin)

        # Step 2: Update vote counts on cache entry
        # Fetch current cache entry
        cache_entries = await self.db.select(
            "response_cache",
            columns="upvotes,downvotes",
            filters={"cache_key": cache_key},
            use_admin=use_admin
        )

        if not cache_entries:
            logger.warning(f"Cache key not found for feedback: {cache_key}")
            return False

        current_upvotes = cache_entries[0].get("upvotes", 0)
        current_downvotes = cache_entries[0].get("downvotes", 0)

        # Increment appropriate counter
        if rating == 1:
            await self.db.update(
                "response_cache",
                data={"upvotes": current_upvotes + 1},
                filters={"cache_key": cache_key},
                use_admin=use_admin
            )
            logger.info(f"Upvote recorded for {cache_key[:16]}...")
        else:
            await self.db.update(
                "response_cache",
                data={"downvotes": current_downvotes + 1},
                filters={"cache_key": cache_key},
                use_admin=use_admin
            )
            logger.info(f"Downvote recorded for {cache_key[:16]}...")

        return True

    async def update_quality_score(self, cache_key: str) -> Optional[float]:
        """
        Recalculate and update quality score for a cached response.

        Uses Wilson score confidence interval for quality calculation.

        Args:
            cache_key: Cache key to update

        Returns:
            New quality score (0.0-1.0), or None if no votes
        """
        use_admin = self.user_id is None

        # Fetch current vote counts
        cache_entries = await self.db.select(
            "response_cache",
            columns="upvotes,downvotes",
            filters={"cache_key": cache_key},
            use_admin=use_admin
        )

        if not cache_entries:
            logger.warning(f"Cache key not found: {cache_key}")
            return None

        upvotes = cache_entries[0].get("upvotes", 0)
        downvotes = cache_entries[0].get("downvotes", 0)
        total_votes = upvotes + downvotes

        if total_votes == 0:
            return None

        # Calculate quality score (Wilson score confidence interval)
        quality_score = self._calculate_quality_score(upvotes, downvotes)

        # Update database
        await self.db.update(
            "response_cache",
            data={"quality_score": quality_score},
            filters={"cache_key": cache_key},
            use_admin=use_admin
        )

        # Check if should be invalidated (< 0.3 score with 5+ votes)
        if quality_score < 0.3 and total_votes >= 5:
            await self.invalidate_cache_entry(
                cache_key,
                f"Low quality score: {quality_score:.2f} ({upvotes}↑ {downvotes}↓)"
            )
            logger.warning(f"Cache entry invalidated due to low quality: {cache_key[:16]}...")

        logger.debug(f"Quality score updated: {cache_key[:16]}... = {quality_score:.3f}")

        return quality_score

    def _calculate_quality_score(self, upvotes: int, downvotes: int) -> float:
        """
        Calculate quality score using Wilson score confidence interval.

        This is the same algorithm used by Reddit for comment ranking!

        Args:
            upvotes: Number of upvotes
            downvotes: Number of downvotes

        Returns:
            Quality score (0.0-1.0)
        """
        import math

        total = upvotes + downvotes
        if total == 0:
            return 0.0

        # Wilson score with 95% confidence
        z = 1.96  # 95% confidence
        p = upvotes / total

        numerator = p + (z * z) / (2 * total) - z * math.sqrt((p * (1 - p) + (z * z) / (4 * total)) / total)
        denominator = 1 + (z * z) / total

        score = numerator / denominator

        return max(0.0, min(1.0, score))  # Clamp to [0, 1]

    async def get_feedback_for_response(self, cache_key: str) -> List[Dict[str, Any]]:
        """
        Get all feedback for a specific cached response.

        Args:
            cache_key: Cache key to get feedback for

        Returns:
            List of feedback dictionaries
        """
        use_admin = self.user_id is None

        feedback = await self.db.select(
            "response_feedback",
            columns="id,rating,comment,user_agent,timestamp",
            filters={"cache_key": cache_key},
            order_by="-timestamp",
            use_admin=use_admin
        )

        logger.debug(f"Fetched {len(feedback)} feedback entries for {cache_key[:16]}...")

        return feedback

    async def invalidate_cache_entry(self, cache_key: str, reason: str) -> None:
        """
        Manually invalidate a cache entry.

        Invalidated entries won't be returned by check_cache().

        Args:
            cache_key: Cache key to invalidate
            reason: Reason for invalidation
        """
        use_admin = self.user_id is None

        await self.db.update(
            "response_cache",
            data={
                "invalidated": 1,
                "invalidation_reason": reason
            },
            filters={"cache_key": cache_key},
            use_admin=use_admin
        )

        logger.warning(f"Cache entry invalidated: {cache_key[:16]}... - {reason}")

    async def get_quality_stats(self) -> Dict[str, Any]:
        """
        Get quality statistics across all cached responses for current user.

        Returns:
            Dictionary with quality metrics by provider and overall
        """
        filters = {}
        if self.user_id:
            filters["user_id"] = self.user_id

        use_admin = self.user_id is None

        # Fetch all cache entries
        cache_entries = await self.db.select(
            "response_cache",
            columns="provider,model,upvotes,downvotes,quality_score,invalidated,invalidation_reason,prompt_normalized",
            filters=filters,
            use_admin=use_admin
        )

        if not cache_entries:
            return {
                "overall": {
                    "total_entries": 0,
                    "total_upvotes": 0,
                    "total_downvotes": 0,
                    "invalidated_count": 0,
                    "avg_quality_score": 0.0
                },
                "by_provider": [],
                "top_rated": [],
                "worst_rated": [],
                "invalidated_responses": []
            }

        # Calculate overall stats
        total_entries = len(cache_entries)
        total_upvotes = sum(e.get("upvotes", 0) for e in cache_entries)
        total_downvotes = sum(e.get("downvotes", 0) for e in cache_entries)
        invalidated_count = sum(1 for e in cache_entries if e.get("invalidated"))

        scores = [e.get("quality_score", 0) for e in cache_entries if e.get("quality_score") is not None]
        avg_quality_score = sum(scores) / len(scores) if scores else 0.0

        # Group by provider
        by_provider = {}
        for entry in cache_entries:
            if entry.get("invalidated"):
                continue  # Skip invalidated for provider stats

            provider = entry.get("provider", "unknown")
            if provider not in by_provider:
                by_provider[provider] = {
                    "provider": provider,
                    "entry_count": 0,
                    "total_upvotes": 0,
                    "total_downvotes": 0,
                    "total_votes": 0,
                    "avg_quality_score": 0.0
                }

            by_provider[provider]["entry_count"] += 1
            by_provider[provider]["total_upvotes"] += entry.get("upvotes", 0)
            by_provider[provider]["total_downvotes"] += entry.get("downvotes", 0)
            by_provider[provider]["total_votes"] += entry.get("upvotes", 0) + entry.get("downvotes", 0)

        # Calculate provider averages
        for provider_stats in by_provider.values():
            provider_entries = [e for e in cache_entries
                              if e.get("provider") == provider_stats["provider"]
                              and not e.get("invalidated")
                              and e.get("quality_score") is not None]

            if provider_entries:
                scores = [e["quality_score"] for e in provider_entries]
                provider_stats["avg_quality_score"] = sum(scores) / len(scores)

        # Top rated (valid entries with quality scores)
        scored_entries = [e for e in cache_entries
                         if e.get("quality_score") is not None
                         and not e.get("invalidated")]

        top_rated = sorted(scored_entries, key=lambda x: x.get("quality_score", 0), reverse=True)[:5]
        worst_rated = sorted(scored_entries, key=lambda x: x.get("quality_score", 0))[:5]

        # Invalidated entries
        invalidated = [e for e in cache_entries if e.get("invalidated")]

        return {
            "overall": {
                "total_entries": total_entries,
                "total_upvotes": total_upvotes,
                "total_downvotes": total_downvotes,
                "invalidated_count": invalidated_count,
                "avg_quality_score": avg_quality_score
            },
            "by_provider": list(by_provider.values()),
            "top_rated": top_rated,
            "worst_rated": worst_rated,
            "invalidated_responses": invalidated
        }


# ==================== BACKWARD COMPATIBILITY ====================

# For gradual migration, we'll keep a compatibility wrapper
# that mimics the old sync interface but calls async methods

class CostTrackerCompat:
    """
    Compatibility wrapper for sync code during migration.

    WARNING: This uses asyncio.run() which is inefficient!
    Migrate to AsyncCostTracker as soon as possible.
    """

    def __init__(self, db_path: str = "optimizer.db"):
        """Initialize (db_path ignored, for compatibility only)."""
        import asyncio
        self._tracker = AsyncCostTracker()
        self._loop = asyncio.new_event_loop()
        logger.warning(
            "Using CostTrackerCompat sync wrapper. "
            "Migrate to AsyncCostTracker for better performance!"
        )

    def log_request(self, prompt, complexity, provider, model,
                    tokens_in, tokens_out, cost):
        """Sync wrapper for log_request."""
        import asyncio
        return asyncio.run(
            self._tracker.log_request(
                prompt, complexity, provider, model,
                tokens_in, tokens_out, cost
            )
        )

    def get_total_cost(self) -> float:
        """Sync wrapper for get_total_cost."""
        import asyncio
        return asyncio.run(self._tracker.get_total_cost())
