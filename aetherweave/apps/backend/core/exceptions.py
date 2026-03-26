"""
AetherWeave Backend — Custom Exceptions
========================================

Domain-specific exception classes for clean error handling in service layers.
FastAPI exception handlers translate these into HTTP responses.
"""

from __future__ import annotations


class AetherWeaveError(Exception):
    """Base exception for all AetherWeave domain errors."""
    pass


class ArchitectureNotFoundError(AetherWeaveError):
    """Raised when an ArchGraph UUID does not exist in the database."""

    def __init__(self, graph_id: str) -> None:
        self.graph_id = graph_id
        super().__init__(f"Architecture '{graph_id}' not found.")


class EvolutionAlreadyRunningError(AetherWeaveError):
    """Raised when POST /evolve is called on an already-evolving architecture."""

    def __init__(self, graph_id: str) -> None:
        self.graph_id = graph_id
        super().__init__(f"Architecture '{graph_id}' is already evolving. Wait or cancel.")


class InvalidSymbiosisTokenError(AetherWeaveError):
    """Raised when a symbiosis token is invalid, expired, or already used."""

    def __init__(self, reason: str = "invalid") -> None:
        self.reason = reason
        super().__init__(f"Symbiosis token is {reason}.")


class EvolutionTimeoutError(AetherWeaveError):
    """Raised when an evolution run exceeds the configured timeout."""

    def __init__(self, timeout_seconds: int) -> None:
        super().__init__(f"Evolution run timed out after {timeout_seconds} seconds.")


class DatabaseUnavailableError(AetherWeaveError):
    """Raised when a required backing service (PG, Neo4j, Redis) is unreachable."""

    def __init__(self, service: str) -> None:
        self.service = service
        super().__init__(f"Required service '{service}' is unavailable.")
