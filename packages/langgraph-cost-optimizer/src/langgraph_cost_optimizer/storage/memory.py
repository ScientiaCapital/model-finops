"""In-memory storage backend (default)."""

from typing import Optional
from datetime import datetime
from collections import defaultdict

from langgraph_cost_optimizer.tracker import CostRecord


class InMemoryStorage:
    """
    In-memory storage for cost records.

    This is the default storage backend - fast but non-persistent.
    Records are lost when the process exits.

    Example:
        storage = InMemoryStorage()
        storage.save(record)
        records = storage.get_all()
    """

    def __init__(self):
        self._records: list[CostRecord] = []
        self._by_id: dict[str, CostRecord] = {}

    def save(self, record: CostRecord) -> None:
        """Save a cost record."""
        self._records.append(record)
        self._by_id[record.id] = record

    def get(self, record_id: str) -> Optional[CostRecord]:
        """Get a record by ID."""
        return self._by_id.get(record_id)

    def get_all(
        self,
        agent_name: Optional[str] = None,
        node_name: Optional[str] = None,
        model_id: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> list[CostRecord]:
        """
        Get records with optional filtering.

        Args:
            agent_name: Filter by agent
            node_name: Filter by node
            model_id: Filter by model
            since: Filter by timestamp
            limit: Maximum records to return

        Returns:
            List of matching records
        """
        records = self._records

        if agent_name:
            records = [r for r in records if r.agent_name == agent_name]
        if node_name:
            records = [r for r in records if r.node_name == node_name]
        if model_id:
            records = [r for r in records if r.model_id == model_id]
        if since:
            records = [r for r in records if r.timestamp >= since]
        if limit:
            records = records[-limit:]

        return records

    def get_summary(self) -> dict:
        """Get aggregated summary."""
        if not self._records:
            return {
                "total_cost_usd": 0,
                "total_tokens": 0,
                "num_records": 0,
            }

        return {
            "total_cost_usd": sum(r.cost_usd for r in self._records),
            "total_tokens": sum(r.input_tokens + r.output_tokens for r in self._records),
            "num_records": len(self._records),
        }

    def clear(self) -> None:
        """Clear all records."""
        self._records.clear()
        self._by_id.clear()

    def __len__(self) -> int:
        return len(self._records)
