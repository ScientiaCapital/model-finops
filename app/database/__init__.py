"""Database utilities package (Supabase-based)."""

# Import Supabase modules
from .cost_tracker_async import AsyncCostTracker
from .supabase_client import SupabaseClient, close_supabase_client, get_supabase_client


# Legacy stub for backward compatibility
# If you need CostTracker, it has been replaced with AsyncCostTracker
class CostTracker:
    """
    Deprecated: Use AsyncCostTracker instead.

    This is a stub class for backward compatibility.
    All methods have been migrated to AsyncCostTracker with Supabase backend.
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        import logging

        logging.warning(
            "CostTracker is deprecated. Use AsyncCostTracker instead.\n"
            "Example: from app.database import AsyncCostTracker\n"
            "         tracker = AsyncCostTracker(user_id='your-user-id')"
        )


def create_routing_metrics_table(*args: object, **kwargs: object) -> None:
    """
    Deprecated: Routing metrics table is now in Supabase.

    This function is no longer needed. Tables are created via SQL migrations
    in migrations/supabase_*.sql files.
    """
    import logging

    logging.warning(
        "create_routing_metrics_table() is deprecated.\n"
        "Tables are created via Supabase SQL migrations (migrations/supabase_*.sql)."
    )


__all__ = [
    # Legacy stubs
    "CostTracker",
    "create_routing_metrics_table",
    # Supabase async modules
    "SupabaseClient",
    "get_supabase_client",
    "close_supabase_client",
    "AsyncCostTracker",
]
