"""
Cost tracking core - Records and aggregates LLM costs.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from collections import defaultdict
import threading
import uuid

from langgraph_cost_optimizer.providers import calculate_cost, get_model_pricing


@dataclass
class CostRecord:
    """Individual cost record for an LLM call."""
    id: str
    model_id: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    timestamp: datetime
    agent_name: Optional[str] = None
    node_name: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        agent_name: Optional[str] = None,
        node_name: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> "CostRecord":
        """Create a new cost record with calculated cost."""
        cost = calculate_cost(model_id, input_tokens, output_tokens)
        return cls(
            id=str(uuid.uuid4()),
            model_id=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            timestamp=datetime.now(timezone.utc),
            agent_name=agent_name,
            node_name=node_name,
            metadata=metadata or {},
        )


class CostTracker:
    """
    Thread-safe cost tracker for LangGraph applications.

    Tracks costs per agent, per node, and globally. Supports both
    synchronous and async usage patterns.

    Example:
        tracker = CostTracker()

        # Record a cost
        tracker.record(
            model_id="claude-sonnet-4-5",
            input_tokens=1000,
            output_tokens=500,
            agent_name="researcher"
        )

        # Get summary
        print(tracker.get_summary())
        # {"total_cost": 0.0225, "total_tokens": 1500, "by_agent": {...}}
    """

    def __init__(self):
        self._records: list[CostRecord] = []
        self._lock = threading.Lock()
        self._by_agent: dict[str, list[CostRecord]] = defaultdict(list)
        self._by_node: dict[str, list[CostRecord]] = defaultdict(list)
        self._by_model: dict[str, list[CostRecord]] = defaultdict(list)

    def record(
        self,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        agent_name: Optional[str] = None,
        node_name: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> CostRecord:
        """
        Record a cost event.

        Args:
            model_id: The model identifier (e.g., "claude-sonnet-4-5")
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            agent_name: Optional agent/worker name
            node_name: Optional LangGraph node name
            metadata: Optional additional metadata

        Returns:
            The created CostRecord
        """
        record = CostRecord.create(
            model_id=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            agent_name=agent_name,
            node_name=node_name,
            metadata=metadata,
        )

        with self._lock:
            self._records.append(record)
            self._by_model[model_id].append(record)
            if agent_name:
                self._by_agent[agent_name].append(record)
            if node_name:
                self._by_node[node_name].append(record)

        return record

    @property
    def total_cost(self) -> float:
        """Total cost across all records."""
        with self._lock:
            return sum(r.cost_usd for r in self._records)

    @property
    def total_tokens(self) -> int:
        """Total tokens (input + output) across all records."""
        with self._lock:
            return sum(r.input_tokens + r.output_tokens for r in self._records)

    @property
    def total_input_tokens(self) -> int:
        """Total input tokens across all records."""
        with self._lock:
            return sum(r.input_tokens for r in self._records)

    @property
    def total_output_tokens(self) -> int:
        """Total output tokens across all records."""
        with self._lock:
            return sum(r.output_tokens for r in self._records)

    def get_cost_by_agent(self) -> dict[str, float]:
        """Get cost breakdown by agent."""
        with self._lock:
            return {
                agent: sum(r.cost_usd for r in records)
                for agent, records in self._by_agent.items()
            }

    def get_cost_by_node(self) -> dict[str, float]:
        """Get cost breakdown by LangGraph node."""
        with self._lock:
            return {
                node: sum(r.cost_usd for r in records)
                for node, records in self._by_node.items()
            }

    def get_cost_by_model(self) -> dict[str, float]:
        """Get cost breakdown by model."""
        with self._lock:
            return {
                model: sum(r.cost_usd for r in records)
                for model, records in self._by_model.items()
            }

    def get_summary(self) -> dict:
        """
        Get comprehensive cost summary.

        Returns:
            Dict with total_cost, total_tokens, and breakdowns by agent/node/model
        """
        with self._lock:
            return {
                "total_cost_usd": sum(r.cost_usd for r in self._records),
                "total_input_tokens": sum(r.input_tokens for r in self._records),
                "total_output_tokens": sum(r.output_tokens for r in self._records),
                "total_tokens": sum(r.input_tokens + r.output_tokens for r in self._records),
                "num_calls": len(self._records),
                "by_agent": {
                    agent: {
                        "cost_usd": sum(r.cost_usd for r in records),
                        "calls": len(records),
                        "tokens": sum(r.input_tokens + r.output_tokens for r in records),
                    }
                    for agent, records in self._by_agent.items()
                },
                "by_node": {
                    node: {
                        "cost_usd": sum(r.cost_usd for r in records),
                        "calls": len(records),
                    }
                    for node, records in self._by_node.items()
                },
                "by_model": {
                    model: {
                        "cost_usd": sum(r.cost_usd for r in records),
                        "calls": len(records),
                        "input_tokens": sum(r.input_tokens for r in records),
                        "output_tokens": sum(r.output_tokens for r in records),
                    }
                    for model, records in self._by_model.items()
                },
            }

    def get_records(
        self,
        agent_name: Optional[str] = None,
        node_name: Optional[str] = None,
        model_id: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> list[CostRecord]:
        """
        Get filtered list of cost records.

        Args:
            agent_name: Filter by agent name
            node_name: Filter by node name
            model_id: Filter by model ID
            since: Filter records after this timestamp

        Returns:
            List of matching CostRecord objects
        """
        with self._lock:
            records = self._records.copy()

        if agent_name:
            records = [r for r in records if r.agent_name == agent_name]
        if node_name:
            records = [r for r in records if r.node_name == node_name]
        if model_id:
            records = [r for r in records if r.model_id == model_id]
        if since:
            records = [r for r in records if r.timestamp >= since]

        return records

    def reset(self):
        """Clear all records."""
        with self._lock:
            self._records.clear()
            self._by_agent.clear()
            self._by_node.clear()
            self._by_model.clear()

    def __len__(self) -> int:
        """Number of records."""
        with self._lock:
            return len(self._records)
