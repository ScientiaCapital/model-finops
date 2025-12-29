"""
LangChain/LangGraph callbacks for automatic cost tracking.
"""

from typing import Any, Optional, Union
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from langgraph_cost_optimizer.tracker import CostTracker
from langgraph_cost_optimizer.budget import BudgetEnforcer


class CostTrackingCallback(BaseCallbackHandler):
    """
    LangChain callback handler that tracks costs automatically.

    Integrates with CostTracker to record costs from LLM calls
    and optionally enforces budgets via BudgetEnforcer.

    Example:
        from langchain_anthropic import ChatAnthropic
        from langgraph_cost_optimizer import CostTracker, CostTrackingCallback

        tracker = CostTracker()
        callback = CostTrackingCallback(
            tracker=tracker,
            agent_name="researcher",
        )

        llm = ChatAnthropic(model="claude-sonnet-4-5", callbacks=[callback])
        result = llm.invoke("Hello")

        print(tracker.get_summary())
    """

    def __init__(
        self,
        tracker: CostTracker,
        budget_enforcer: Optional[BudgetEnforcer] = None,
        agent_name: Optional[str] = None,
        node_name: Optional[str] = None,
        check_budget_before: bool = True,
        metadata: Optional[dict] = None,
    ):
        """
        Initialize callback handler.

        Args:
            tracker: CostTracker to record costs
            budget_enforcer: Optional BudgetEnforcer to check limits
            agent_name: Name of agent using this callback
            node_name: Name of LangGraph node
            check_budget_before: Check budget before LLM call
            metadata: Additional metadata to include in records
        """
        super().__init__()
        self.tracker = tracker
        self.budget_enforcer = budget_enforcer
        self.agent_name = agent_name
        self.node_name = node_name
        self.check_budget_before = check_budget_before
        self.metadata = metadata or {}

        # Track current run info
        self._current_model: Optional[str] = None
        self._current_run_id: Optional[str] = None

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when LLM starts."""
        # Extract model from serialized config
        model_id = None
        if "kwargs" in serialized:
            model_id = serialized["kwargs"].get("model") or serialized["kwargs"].get(
                "model_name"
            )
        if not model_id and metadata:
            model_id = metadata.get("ls_model_name")

        self._current_model = model_id
        self._current_run_id = str(run_id)

        # Check budget before call if configured
        if self.check_budget_before and self.budget_enforcer and model_id:
            self.budget_enforcer.check_budget(
                agent_name=self.agent_name,
                node_name=self.node_name,
                model_id=model_id,
            )

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Called when LLM ends - record the cost."""
        if response.llm_output is None:
            return

        # Extract token usage
        token_usage = response.llm_output.get("token_usage", {})
        if not token_usage:
            # Try alternative locations
            token_usage = response.llm_output.get("usage", {})

        input_tokens = token_usage.get("prompt_tokens", 0) or token_usage.get(
            "input_tokens", 0
        )
        output_tokens = token_usage.get("completion_tokens", 0) or token_usage.get(
            "output_tokens", 0
        )

        # Get model ID
        model_id = response.llm_output.get("model_name") or self._current_model
        if not model_id:
            # Try to extract from response
            model_id = response.llm_output.get("model")

        if not model_id:
            # Skip if we can't determine the model
            return

        # Combine metadata
        record_metadata = {**self.metadata}
        if self._current_run_id:
            record_metadata["run_id"] = self._current_run_id

        # Record the cost
        self.tracker.record(
            model_id=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            agent_name=self.agent_name,
            node_name=self.node_name,
            metadata=record_metadata,
        )

        # Check budget after call
        if self.budget_enforcer:
            self.budget_enforcer.check_budget(
                agent_name=self.agent_name,
                node_name=self.node_name,
                model_id=model_id,
                raise_on_exceeded=False,  # Don't raise after, just track
            )

    def on_llm_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Called on LLM error - reset state."""
        self._current_model = None
        self._current_run_id = None


def create_callback_for_agent(
    tracker: CostTracker,
    agent_name: str,
    budget_enforcer: Optional[BudgetEnforcer] = None,
    node_name: Optional[str] = None,
) -> CostTrackingCallback:
    """
    Factory function to create a callback for a specific agent.

    Args:
        tracker: Shared CostTracker instance
        agent_name: Name of the agent
        budget_enforcer: Optional shared BudgetEnforcer
        node_name: Optional node name

    Returns:
        Configured CostTrackingCallback
    """
    return CostTrackingCallback(
        tracker=tracker,
        budget_enforcer=budget_enforcer,
        agent_name=agent_name,
        node_name=node_name,
    )
