"""Supabase client wrapper for async database operations with RLS support."""
import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from supabase import create_client, Client
from postgrest.exceptions import APIError

logger = logging.getLogger(__name__)


class SupabaseClient:
    """
    Async wrapper for Supabase client with Row-Level Security support.

    Features:
    - Automatic user context from JWT tokens
    - Service role bypass for admin operations
    - Connection pooling via Supabase client
    - Type-safe query builders
    - Error handling and logging
    """

    def __init__(
        self,
        url: Optional[str] = None,
        anon_key: Optional[str] = None,
        service_key: Optional[str] = None
    ):
        """
        Initialize Supabase client.

        Args:
            url: Supabase project URL (defaults to SUPABASE_URL env var)
            anon_key: Anon/public key for user-scoped operations
            service_key: Service role key for admin operations (bypasses RLS)
        """
        self.url = url or os.getenv("SUPABASE_URL")
        self.anon_key = anon_key or os.getenv("SUPABASE_ANON_KEY")
        self.service_key = service_key or os.getenv("SUPABASE_SERVICE_KEY")

        if not self.url or not self.anon_key:
            raise ValueError(
                "Missing Supabase credentials. Set SUPABASE_URL and "
                "SUPABASE_ANON_KEY environment variables."
            )

        # User-scoped client (respects RLS)
        self.client: Client = create_client(self.url, self.anon_key)

        # Admin client (bypasses RLS) - only created if service key provided
        self.admin_client: Optional[Client] = None
        if self.service_key:
            self.admin_client = create_client(self.url, self.service_key)

        logger.info(f"Supabase client initialized for {self.url}")

    def set_user_context(self, access_token: str) -> None:
        """
        Set user context for RLS-protected operations.

        Call this after user authentication to ensure all subsequent
        queries are automatically filtered by user_id via RLS policies.

        Args:
            access_token: JWT access token from Supabase Auth
        """
        self.client.auth.set_session(access_token, "")
        logger.debug("User context set from JWT token")

    def clear_user_context(self) -> None:
        """Clear user context (logout)."""
        self.client.auth.sign_out()
        logger.debug("User context cleared")

    def table(self, table_name: str):
        """
        Get a table reference for direct operations.

        Uses admin client (bypasses RLS) if available, otherwise uses user client.
        This provides backwards compatibility with code using raw supabase-py interface.

        Args:
            table_name: Name of the table

        Returns:
            Table query builder from supabase-py
        """
        if self.admin_client:
            return self.admin_client.table(table_name)
        return self.client.table(table_name)

    # ==================== QUERY HELPERS ====================

    async def insert(
        self,
        table: str,
        data: Dict[str, Any],
        use_admin: bool = False
    ) -> Dict[str, Any]:
        """
        Insert a row into a table.

        Args:
            table: Table name
            data: Dictionary of column: value pairs
            use_admin: Use admin client (bypass RLS)

        Returns:
            Inserted row data

        Raises:
            APIError: If insert fails
        """
        client = self.admin_client if use_admin and self.admin_client else self.client

        try:
            response = client.table(table).insert(data).execute()
            logger.debug(f"Inserted into {table}: {data}")
            return response.data[0] if response.data else {}
        except APIError as e:
            logger.error(f"Insert failed for {table}: {e}")
            raise

    async def select(
        self,
        table: str,
        columns: str = "*",
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
        use_admin: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Select rows from a table.

        Args:
            table: Table name
            columns: Columns to select (comma-separated or "*")
            filters: Dictionary of column: value filters (equality)
            order_by: Column to order by (prefix with - for DESC)
            limit: Maximum rows to return
            use_admin: Use admin client (bypass RLS)

        Returns:
            List of row dictionaries
        """
        client = self.admin_client if use_admin and self.admin_client else self.client
        query = client.table(table).select(columns)

        # Apply filters
        if filters:
            for key, value in filters.items():
                query = query.eq(key, value)

        # Apply ordering
        if order_by:
            desc = order_by.startswith("-")
            column = order_by.lstrip("-")
            query = query.order(column, desc=desc)

        # Apply limit
        if limit:
            query = query.limit(limit)

        try:
            response = query.execute()
            return response.data
        except APIError as e:
            logger.error(f"Select failed for {table}: {e}")
            raise

    async def update(
        self,
        table: str,
        data: Dict[str, Any],
        filters: Dict[str, Any],
        use_admin: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Update rows in a table.

        Args:
            table: Table name
            data: Dictionary of columns to update
            filters: Dictionary of column: value filters
            use_admin: Use admin client (bypass RLS)

        Returns:
            List of updated row dictionaries
        """
        client = self.admin_client if use_admin and self.admin_client else self.client
        query = client.table(table).update(data)

        # Apply filters
        for key, value in filters.items():
            query = query.eq(key, value)

        try:
            response = query.execute()
            logger.debug(f"Updated {table} where {filters}: {data}")
            return response.data
        except APIError as e:
            logger.error(f"Update failed for {table}: {e}")
            raise

    async def delete(
        self,
        table: str,
        filters: Dict[str, Any],
        use_admin: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Delete rows from a table.

        Args:
            table: Table name
            filters: Dictionary of column: value filters
            use_admin: Use admin client (bypass RLS)

        Returns:
            List of deleted row dictionaries
        """
        client = self.admin_client if use_admin and self.admin_client else self.client
        query = client.table(table).delete()

        # Apply filters
        for key, value in filters.items():
            query = query.eq(key, value)

        try:
            response = query.execute()
            logger.debug(f"Deleted from {table} where {filters}")
            return response.data
        except APIError as e:
            logger.error(f"Delete failed for {table}: {e}")
            raise

    async def upsert(
        self,
        table: str,
        data: Dict[str, Any] | List[Dict[str, Any]],
        on_conflict: Optional[str] = None,
        use_admin: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Insert or update rows (upsert).

        Args:
            table: Table name
            data: Single dict or list of dicts to upsert
            on_conflict: Column name for conflict resolution
            use_admin: Use admin client (bypass RLS)

        Returns:
            List of upserted row dictionaries
        """
        client = self.admin_client if use_admin and self.admin_client else self.client

        try:
            if on_conflict:
                response = client.table(table).upsert(
                    data,
                    on_conflict=on_conflict
                ).execute()
            else:
                response = client.table(table).upsert(data).execute()

            logger.debug(f"Upserted into {table}")
            return response.data
        except APIError as e:
            logger.error(f"Upsert failed for {table}: {e}")
            raise

    # ==================== SEMANTIC SEARCH ====================

    async def semantic_search(
        self,
        query_embedding: List[float],
        match_threshold: float = 0.95,
        match_count: int = 1,
        user_id: Optional[str] = None,
        filter_providers: Optional[List[str]] = None,
        filter_models: Optional[List[str]] = None,
        min_quality_score: Optional[float] = None,
        max_age_hours: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search using pgvector with optional metadata filtering.

        Calls the match_cache_entries_v2() function for enhanced filtering,
        or falls back to match_cache_entries() for basic queries.

        Args:
            query_embedding: 384-dimensional embedding vector
            match_threshold: Minimum similarity score (0.0-1.0)
            match_count: Maximum results to return
            user_id: Optional user_id filter (for RLS)
            filter_providers: Only match responses from these providers
                              e.g., ["claude", "gemini"]
            filter_models: Only match responses from these models
                           e.g., ["claude-3-haiku", "gemini-flash"]
            min_quality_score: Only match responses with quality >= this score
            max_age_hours: Only match responses created within this many hours

        Returns:
            List of matching cache entries with similarity scores

        Example:
            # Find similar prompts from Claude with quality > 0.7
            matches = await client.semantic_search(
                query_embedding=embedding,
                match_threshold=0.90,
                filter_providers=["claude"],
                min_quality_score=0.7
            )
        """
        # Determine which function to use based on filters
        has_filters = any([
            filter_providers,
            filter_models,
            min_quality_score is not None,
            max_age_hours is not None
        ])

        try:
            if has_filters:
                # Use enhanced v2 function with metadata filtering
                params = {
                    "query_embedding": query_embedding,
                    "match_threshold": match_threshold,
                    "match_count": match_count,
                    "target_user_id": user_id
                }

                if filter_providers:
                    params["filter_providers"] = filter_providers
                if filter_models:
                    params["filter_models"] = filter_models
                if min_quality_score is not None:
                    params["min_quality_score"] = min_quality_score
                if max_age_hours is not None:
                    params["max_age_hours"] = max_age_hours

                response = self.client.rpc(
                    "match_cache_entries_v2",
                    params
                ).execute()

                logger.debug(
                    f"Enhanced semantic search found {len(response.data)} results "
                    f"(threshold={match_threshold}, providers={filter_providers}, "
                    f"min_quality={min_quality_score})"
                )
            else:
                # Use original function for basic queries (backward compatible)
                response = self.client.rpc(
                    "match_cache_entries",
                    {
                        "query_embedding": query_embedding,
                        "match_threshold": match_threshold,
                        "match_count": match_count,
                        "target_user_id": user_id
                    }
                ).execute()

                logger.debug(
                    f"Semantic search found {len(response.data)} results "
                    f"(threshold={match_threshold})"
                )

            return response.data
        except APIError as e:
            logger.error(f"Semantic search failed: {e}")
            raise

    async def get_cache_analytics(
        self,
        user_id: Optional[str] = None,
        days_back: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get cache analytics grouped by provider.

        Args:
            user_id: Optional user_id filter
            days_back: Number of days to look back (default 7)

        Returns:
            List of analytics dictionaries with:
            - provider: Provider name
            - total_entries: Number of cached responses
            - total_hits: Total cache hits
            - avg_quality: Average quality score
            - hit_rate: Hits per entry ratio
        """
        try:
            response = self.client.rpc(
                "get_cache_analytics",
                {
                    "target_user_id": user_id,
                    "days_back": days_back
                }
            ).execute()

            return response.data
        except APIError as e:
            logger.error(f"Failed to get cache analytics: {e}")
            raise

    async def get_cache_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Get cache statistics for a user.

        Calls the get_user_cache_stats() function created in Part 1.

        Args:
            user_id: User ID (UUID)

        Returns:
            Dictionary with cache statistics
        """
        try:
            response = self.client.rpc(
                "get_user_cache_stats",
                {"target_user_id": user_id}
            ).execute()

            if response.data:
                return response.data[0]
            return {
                "total_entries": 0,
                "total_hits": 0,
                "avg_quality_score": 0.0,
                "cache_size_bytes": 0
            }
        except APIError as e:
            logger.error(f"Failed to get cache stats: {e}")
            raise

    # ==================== ADMIN OPERATIONS ====================

    async def execute_sql(self, sql: str) -> Any:
        """
        Execute raw SQL (admin only).

        Args:
            sql: SQL query string

        Returns:
            Query result

        Raises:
            ValueError: If admin client not available
        """
        if not self.admin_client:
            raise ValueError("Admin client not available (no service key)")

        try:
            # Note: Supabase Python client doesn't have direct SQL execution
            # This would require using asyncpg directly via the connection string
            logger.warning("Raw SQL execution requires asyncpg, not Supabase client")
            raise NotImplementedError(
                "Use asyncpg directly for raw SQL. "
                "See app/database/async_pool.py for connection pooling."
            )
        except Exception as e:
            logger.error(f"SQL execution failed: {e}")
            raise

    # ==================== HEALTH CHECK ====================

    async def health_check(self) -> bool:
        """
        Check if Supabase connection is healthy.

        Returns:
            True if connection is working
        """
        try:
            # Simple query to verify connection
            response = self.client.table("requests").select("id").limit(1).execute()
            logger.debug("Health check passed")
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False


# ==================== GLOBAL CLIENT INSTANCE ====================

# Singleton instance (initialized once)
_supabase_client: Optional[SupabaseClient] = None


def get_supabase_client() -> SupabaseClient:
    """
    Get global Supabase client instance.

    Creates client on first call, reuses on subsequent calls.

    Returns:
        SupabaseClient instance
    """
    global _supabase_client

    if _supabase_client is None:
        _supabase_client = SupabaseClient()
        logger.info("Global Supabase client created")

    return _supabase_client


async def close_supabase_client() -> None:
    """Close global Supabase client (cleanup on shutdown)."""
    global _supabase_client

    if _supabase_client:
        # Supabase client doesn't require explicit close
        # but we clear the reference
        _supabase_client = None
        logger.info("Global Supabase client closed")
