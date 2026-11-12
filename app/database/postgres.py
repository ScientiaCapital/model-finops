"""
PostgreSQL connection utilities (DEPRECATED).

This module is deprecated in favor of Supabase client (app/database/supabase_client.py).
Stub implementations provided for backward compatibility.
"""

import logging

logger = logging.getLogger(__name__)


def get_connection() -> None:
    """
    Get PostgreSQL connection (deprecated).

    This function is deprecated. Use Supabase client instead:
        from app.database import get_supabase_client
        supabase = get_supabase_client()

    Returns:
        None (stub implementation)
    """
    logger.warning("get_connection() is deprecated. Use Supabase client instead.")
    return None


def get_cursor(connection: object = None) -> None:
    """
    Get database cursor (deprecated).

    This function is deprecated. Use Supabase client instead:
        from app.database import get_supabase_client
        supabase = get_supabase_client()
        result = await supabase.query("table_name").execute()

    Args:
        connection: Database connection (unused)

    Returns:
        None (stub implementation)
    """
    logger.warning("get_cursor() is deprecated. Use Supabase client instead.")
    return None


__all__ = ["get_connection", "get_cursor"]
