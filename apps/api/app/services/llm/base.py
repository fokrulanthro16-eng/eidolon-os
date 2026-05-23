"""
Abstract brain interface.

Every brain implementation — rule-based, Ollama, remote API — satisfies
this contract. The rest of the system only imports BaseBrain and BrainMode;
swapping the concrete implementation requires zero changes outside this package.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Generator


class BrainMode(str, Enum):
    LOCAL_SEMANTIC = "local_semantic"  # default — semantic search + synthesis, zero deps
    LOCAL_LLM      = "local_llm"      # optional — Ollama running locally
    REMOTE_LLM     = "remote_llm"     # future — cloud API (opt-in, not implemented)
    RULE_BASED     = "rule_based"     # legacy alias kept for backwards compat


class MemoryEntry(dict):
    """
    dict subclass documenting expected keys:
        score       float   relevance score from search_service
        item        dict    the raw MemoryItem dict from the store
    """


class BaseBrain(ABC):
    # ------------------------------------------------------------------
    # Required — every implementation must override
    # ------------------------------------------------------------------

    @abstractmethod
    def generate_response(
        self,
        user_message: str,
        memories: list[MemoryEntry],
        context: dict[str, Any] | None = None,
    ) -> str:
        """Non-streaming, no history — original interface, always supported."""
        ...

    @abstractmethod
    def mode(self) -> BrainMode: ...

    @abstractmethod
    def is_llm_active(self) -> bool: ...

    # ------------------------------------------------------------------
    # Optional — override for richer behaviour
    # ------------------------------------------------------------------

    def generate_with_history(
        self,
        user_message: str,
        context: dict[str, Any],
        history: list[dict] | None = None,
    ) -> str:
        """
        Non-streaming with session history.
        Default: ignore history, delegate to generate_response.
        """
        return self.generate_response(
            user_message,
            context.get("raw_matches", []),  # type: ignore[arg-type]
            context,
        )

    def generate_stream(
        self,
        user_message: str,
        context: dict[str, Any],
        history: list[dict] | None = None,
    ) -> Generator[str, None, None]:
        """
        Streaming variant — yields text delta strings.
        Default: yields the full answer as a single chunk.
        Override for true token-by-token streaming.
        """
        yield self.generate_with_history(user_message, context, history)
