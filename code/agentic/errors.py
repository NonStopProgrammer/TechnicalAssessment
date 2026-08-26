"""AGENT-3: error handling & ambiguity types."""


class AgentToolError(Exception):
    """AGENT-3.1: a tool call failed after exhausting its bounded retries —
    the node that raised this transitions the graph to a degraded state
    rather than letting the exception crash the whole run.
    """


class TransactionNotFoundError(AgentToolError):
    def __init__(self, transaction_id: str):
        self.transaction_id = transaction_id
        super().__init__(f"transaction '{transaction_id}' not found in the seeded store")


class StepBudgetExceeded(AgentToolError):
    """AGENT-3.4: infinite-loop guard — max step count per graph run exceeded."""
