"""
Main middleware class for LangGraph cost optimization.
"""

from typing import Any, Optional, Callable
from functools import wraps

from langgraph_cost_optimizer.tracker import CostTracker
from langgraph_cost_optimizer.budget import BudgetEnforcer, BudgetExceededError
from langgraph_cost_optimizer.callbacks import CostTrackingCallback


class LangGraphCostOptimizer:
    """
    Cost tracking and budget enforcement middleware for LangGraph.

    Wraps a LangGraph CompiledGraph to automatically track costs
    and enforce budgets across all LLM calls.

    Example:
        from langgraph.graph import StateGraph
        from langgraph_cost_optimizer import LangGraphCostOptimizer

        # Build your graph
        graph = StateGraph(State)
        graph.add_node("researcher", researcher_node)
        graph.add_node("writer", writer_node)
        compiled = graph.compile()

        # Wrap with cost optimizer
        optimizer = LangGraphCostOptimizer(
            total_budget_usd=10.0,
            per_agent_budget_usd=2.0,
        )
        tracked_graph = optimizer.wrap(compiled)

        # Use normally
        result = tracked_graph.invoke({"query": "..."})

        # Get cost summary
        print(optimizer.get_summary())
    """

    def __init__(
        self,
        total_budget_usd: Optional[float] = None,
        per_agent_budget_usd: Optional[float] = None,
        per_node_budget_usd: Optional[float] = None,
        per_model_budget_usd: Optional[float] = None,
        warning_threshold: float = 0.8,
        on_warning: Optional[Callable] = None,
        on_exceeded: Optional[Callable] = None,
        on_cost_record: Optional[Callable] = None,
    ):
        """
        Initialize cost optimizer.

        Args:
            total_budget_usd: Maximum total budget in USD
            per_agent_budget_usd: Maximum budget per agent in USD
            per_node_budget_usd: Maximum budget per node in USD
            per_model_budget_usd: Maximum budget per model in USD
            warning_threshold: Threshold (0-1) to trigger warning callback
            on_warning: Callback(budget_type, entity_name, current, limit)
            on_exceeded: Callback(budget_type, entity_name, current, limit)
            on_cost_record: Callback(CostRecord) after each LLM call
        """
        self.tracker = CostTracker()
        self.enforcer = BudgetEnforcer(
            tracker=self.tracker,
            total_budget_usd=total_budget_usd,
            per_agent_budget_usd=per_agent_budget_usd,
            per_node_budget_usd=per_node_budget_usd,
            per_model_budget_usd=per_model_budget_usd,
            warning_threshold=warning_threshold,
            on_warning=on_warning,
            on_exceeded=on_exceeded,
        )
        self.on_cost_record = on_cost_record
        self._agent_callbacks: dict[str, CostTrackingCallback] = {}

    def get_callback(
        self,
        agent_name: Optional[str] = None,
        node_name: Optional[str] = None,
    ) -> CostTrackingCallback:
        """
        Get a callback for use with LangChain LLMs.

        Args:
            agent_name: Name of the agent using this callback
            node_name: Name of the LangGraph node

        Returns:
            CostTrackingCallback configured for this optimizer
        """
        key = f"{agent_name}:{node_name}"
        if key not in self._agent_callbacks:
            self._agent_callbacks[key] = CostTrackingCallback(
                tracker=self.tracker,
                budget_enforcer=self.enforcer,
                agent_name=agent_name,
                node_name=node_name,
            )
        return self._agent_callbacks[key]

    def wrap(self, graph: Any) -> Any:
        """
        Wrap a compiled LangGraph to track costs.

        This creates a wrapper that intercepts invoke/ainvoke calls
        and injects cost tracking callbacks.

        Args:
            graph: A LangGraph CompiledGraph

        Returns:
            Wrapped graph with cost tracking
        """
        return _TrackedGraph(self, graph)

    def record_manual(
        self,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        agent_name: Optional[str] = None,
        node_name: Optional[str] = None,
        metadata: Optional[dict] = None,
    ):
        """
        Manually record a cost (for non-LangChain LLM calls).

        Args:
            model_id: Model identifier (e.g., "claude-sonnet-4-5")
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            agent_name: Optional agent name
            node_name: Optional node name
            metadata: Optional metadata
        """
        record = self.tracker.record(
            model_id=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            agent_name=agent_name,
            node_name=node_name,
            metadata=metadata,
        )
        if self.on_cost_record:
            self.on_cost_record(record)
        return record

    def check_budget(
        self,
        agent_name: Optional[str] = None,
        node_name: Optional[str] = None,
        model_id: Optional[str] = None,
    ) -> dict:
        """
        Check current budget status.

        Args:
            agent_name: Optional agent to check
            node_name: Optional node to check
            model_id: Optional model to check

        Returns:
            Dict with ok, warnings, errors, and usage info

        Raises:
            BudgetExceededError: If any budget is exceeded
        """
        return self.enforcer.check_budget(
            agent_name=agent_name,
            node_name=node_name,
            model_id=model_id,
        )

    def get_summary(self) -> dict:
        """
        Get comprehensive cost summary.

        Returns:
            Dict with costs by agent, node, model, and totals
        """
        summary = self.tracker.get_summary()
        summary["remaining_budget"] = self.enforcer.get_remaining_budget()
        return summary

    @property
    def total_cost(self) -> float:
        """Total cost in USD."""
        return self.tracker.total_cost

    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.tracker.total_tokens

    def reset(self):
        """Reset all tracking data."""
        self.tracker.reset()
        self.enforcer.reset_warnings()
        self._agent_callbacks.clear()


class _TrackedGraph:
    """Wrapper around CompiledGraph that injects cost tracking."""

    def __init__(self, optimizer: LangGraphCostOptimizer, graph: Any):
        self._optimizer = optimizer
        self._graph = graph

    def invoke(self, input: Any, config: Optional[dict] = None, **kwargs) -> Any:
        """Invoke the graph with cost tracking."""
        config = self._inject_callbacks(config)
        return self._graph.invoke(input, config=config, **kwargs)

    async def ainvoke(
        self, input: Any, config: Optional[dict] = None, **kwargs
    ) -> Any:
        """Async invoke the graph with cost tracking."""
        config = self._inject_callbacks(config)
        return await self._graph.ainvoke(input, config=config, **kwargs)

    def stream(self, input: Any, config: Optional[dict] = None, **kwargs):
        """Stream the graph with cost tracking."""
        config = self._inject_callbacks(config)
        return self._graph.stream(input, config=config, **kwargs)

    async def astream(self, input: Any, config: Optional[dict] = None, **kwargs):
        """Async stream the graph with cost tracking."""
        config = self._inject_callbacks(config)
        return self._graph.astream(input, config=config, **kwargs)

    def _inject_callbacks(self, config: Optional[dict]) -> dict:
        """Inject cost tracking callbacks into config."""
        config = config or {}
        callbacks = config.get("callbacks", [])

        # Add our callback
        callback = self._optimizer.get_callback()
        if callback not in callbacks:
            callbacks = [callback] + list(callbacks)

        config["callbacks"] = callbacks
        return config

    def __getattr__(self, name: str) -> Any:
        """Forward other attributes to underlying graph."""
        return getattr(self._graph, name)
