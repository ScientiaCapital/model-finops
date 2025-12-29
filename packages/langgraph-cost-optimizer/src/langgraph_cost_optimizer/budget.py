"""
Budget enforcement for LangGraph cost tracking.
"""

from dataclasses import dataclass
from typing import Optional
from collections import defaultdict

from langgraph_cost_optimizer.tracker import CostTracker


class BudgetExceededError(Exception):
    """Raised when a budget limit is exceeded."""

    def __init__(
        self,
        message: str,
        budget_type: str,
        budget_limit: float,
        current_cost: float,
        entity_name: Optional[str] = None,
    ):
        super().__init__(message)
        self.budget_type = budget_type
        self.budget_limit = budget_limit
        self.current_cost = current_cost
        self.entity_name = entity_name


@dataclass
class BudgetConfig:
    """Budget configuration."""
    total_budget_usd: Optional[float] = None
    per_agent_budget_usd: Optional[float] = None
    per_node_budget_usd: Optional[float] = None
    per_model_budget_usd: Optional[float] = None
    warning_threshold: float = 0.8  # Warn at 80% of budget


class BudgetEnforcer:
    """
    Enforces budget limits for LangGraph cost tracking.

    Example:
        tracker = CostTracker()
        enforcer = BudgetEnforcer(
            tracker=tracker,
            total_budget_usd=10.0,
            per_agent_budget_usd=2.0,
        )

        # Check before LLM call
        enforcer.check_budget(agent_name="researcher")

        # Record cost
        tracker.record(model_id="claude-sonnet-4-5", ...)

        # Check again (will raise if exceeded)
        enforcer.check_budget(agent_name="researcher")
    """

    def __init__(
        self,
        tracker: CostTracker,
        total_budget_usd: Optional[float] = None,
        per_agent_budget_usd: Optional[float] = None,
        per_node_budget_usd: Optional[float] = None,
        per_model_budget_usd: Optional[float] = None,
        warning_threshold: float = 0.8,
        on_warning: Optional[callable] = None,
        on_exceeded: Optional[callable] = None,
    ):
        """
        Initialize budget enforcer.

        Args:
            tracker: CostTracker instance to monitor
            total_budget_usd: Maximum total budget
            per_agent_budget_usd: Maximum budget per agent
            per_node_budget_usd: Maximum budget per node
            per_model_budget_usd: Maximum budget per model
            warning_threshold: Threshold (0-1) to trigger warning
            on_warning: Callback when warning threshold reached
            on_exceeded: Callback when budget exceeded (before raising)
        """
        self.tracker = tracker
        self.config = BudgetConfig(
            total_budget_usd=total_budget_usd,
            per_agent_budget_usd=per_agent_budget_usd,
            per_node_budget_usd=per_node_budget_usd,
            per_model_budget_usd=per_model_budget_usd,
            warning_threshold=warning_threshold,
        )
        self.on_warning = on_warning
        self.on_exceeded = on_exceeded
        self._warnings_sent: set[str] = set()

    def check_budget(
        self,
        agent_name: Optional[str] = None,
        node_name: Optional[str] = None,
        model_id: Optional[str] = None,
        raise_on_exceeded: bool = True,
    ) -> dict:
        """
        Check if any budget limits are exceeded.

        Args:
            agent_name: Optional agent to check
            node_name: Optional node to check
            model_id: Optional model to check
            raise_on_exceeded: Whether to raise BudgetExceededError

        Returns:
            Dict with status and any warnings/errors

        Raises:
            BudgetExceededError: If budget exceeded and raise_on_exceeded=True
        """
        result = {
            "ok": True,
            "warnings": [],
            "errors": [],
            "usage": {},
        }

        # Check total budget
        if self.config.total_budget_usd is not None:
            current = self.tracker.total_cost
            self._check_limit(
                result,
                budget_type="total",
                limit=self.config.total_budget_usd,
                current=current,
                raise_on_exceeded=raise_on_exceeded,
            )
            result["usage"]["total"] = {
                "current": current,
                "limit": self.config.total_budget_usd,
                "percent": (current / self.config.total_budget_usd) * 100,
            }

        # Check per-agent budget
        if self.config.per_agent_budget_usd is not None and agent_name:
            agent_costs = self.tracker.get_cost_by_agent()
            current = agent_costs.get(agent_name, 0.0)
            self._check_limit(
                result,
                budget_type="agent",
                limit=self.config.per_agent_budget_usd,
                current=current,
                entity_name=agent_name,
                raise_on_exceeded=raise_on_exceeded,
            )
            result["usage"][f"agent:{agent_name}"] = {
                "current": current,
                "limit": self.config.per_agent_budget_usd,
                "percent": (current / self.config.per_agent_budget_usd) * 100,
            }

        # Check per-node budget
        if self.config.per_node_budget_usd is not None and node_name:
            node_costs = self.tracker.get_cost_by_node()
            current = node_costs.get(node_name, 0.0)
            self._check_limit(
                result,
                budget_type="node",
                limit=self.config.per_node_budget_usd,
                current=current,
                entity_name=node_name,
                raise_on_exceeded=raise_on_exceeded,
            )
            result["usage"][f"node:{node_name}"] = {
                "current": current,
                "limit": self.config.per_node_budget_usd,
                "percent": (current / self.config.per_node_budget_usd) * 100,
            }

        # Check per-model budget
        if self.config.per_model_budget_usd is not None and model_id:
            model_costs = self.tracker.get_cost_by_model()
            current = model_costs.get(model_id, 0.0)
            self._check_limit(
                result,
                budget_type="model",
                limit=self.config.per_model_budget_usd,
                current=current,
                entity_name=model_id,
                raise_on_exceeded=raise_on_exceeded,
            )
            result["usage"][f"model:{model_id}"] = {
                "current": current,
                "limit": self.config.per_model_budget_usd,
                "percent": (current / self.config.per_model_budget_usd) * 100,
            }

        return result

    def _check_limit(
        self,
        result: dict,
        budget_type: str,
        limit: float,
        current: float,
        entity_name: Optional[str] = None,
        raise_on_exceeded: bool = True,
    ):
        """Check a single budget limit."""
        percent = current / limit if limit > 0 else 0

        # Check warning threshold
        warning_key = f"{budget_type}:{entity_name or 'total'}"
        if (
            percent >= self.config.warning_threshold
            and percent < 1.0
            and warning_key not in self._warnings_sent
        ):
            self._warnings_sent.add(warning_key)
            warning_msg = (
                f"Budget warning: {budget_type} "
                f"{'(' + entity_name + ') ' if entity_name else ''}"
                f"at {percent:.1%} (${current:.4f} / ${limit:.4f})"
            )
            result["warnings"].append(warning_msg)
            if self.on_warning:
                self.on_warning(budget_type, entity_name, current, limit)

        # Check exceeded
        if current >= limit:
            result["ok"] = False
            error_msg = (
                f"Budget exceeded: {budget_type} "
                f"{'(' + entity_name + ') ' if entity_name else ''}"
                f"${current:.4f} >= ${limit:.4f}"
            )
            result["errors"].append(error_msg)

            if self.on_exceeded:
                self.on_exceeded(budget_type, entity_name, current, limit)

            if raise_on_exceeded:
                raise BudgetExceededError(
                    message=error_msg,
                    budget_type=budget_type,
                    budget_limit=limit,
                    current_cost=current,
                    entity_name=entity_name,
                )

    def get_remaining_budget(self) -> dict:
        """
        Get remaining budget for all configured limits.

        Returns:
            Dict with remaining budgets
        """
        remaining = {}

        if self.config.total_budget_usd is not None:
            remaining["total"] = max(
                0, self.config.total_budget_usd - self.tracker.total_cost
            )

        if self.config.per_agent_budget_usd is not None:
            agent_costs = self.tracker.get_cost_by_agent()
            remaining["by_agent"] = {
                agent: max(0, self.config.per_agent_budget_usd - cost)
                for agent, cost in agent_costs.items()
            }

        if self.config.per_node_budget_usd is not None:
            node_costs = self.tracker.get_cost_by_node()
            remaining["by_node"] = {
                node: max(0, self.config.per_node_budget_usd - cost)
                for node, cost in node_costs.items()
            }

        if self.config.per_model_budget_usd is not None:
            model_costs = self.tracker.get_cost_by_model()
            remaining["by_model"] = {
                model: max(0, self.config.per_model_budget_usd - cost)
                for model, cost in model_costs.items()
            }

        return remaining

    def reset_warnings(self):
        """Reset warning flags to re-enable warning callbacks."""
        self._warnings_sent.clear()
