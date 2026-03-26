"""
AetherWeave Backend — SymbiosisService (DNA Sharing Engine)
============================================================

The Symbiosis Engine allows users to share partial architecture graphs
with other AetherWeave users via secure, expiring share tokens.

Security model (Part 1 foundation — ZK proof integration in future):
  - Each share generates a random UUID token (opaque, never exposes graph_id).
  - Tokens are stored in PostgreSQL with an expiry timestamp.
  - Optional bcrypt password hashing for private shares.
  - Tokens can be single-use (marked `used=True` after first redemption).

This mirrors the SymbiosisToken Pydantic model in types.py.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.models.models import SymbiosisTokenModel

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Token TTL — 24 hours by default
DEFAULT_TOKEN_TTL_HOURS = 24


class SymbiosisService:
    """
    Service for creating and redeeming symbiosis (DNA-sharing) tokens.

    Methods
    -------
    create_token(db, graph_id, shared_node_ids, password, ttl_hours)
        Generate a new share token and persist it.
    redeem_token(db, token_str, password)
        Validate a token and return the shared graph/node info.
    """

    async def create_token(
        self,
        db: AsyncSession,
        graph_id: str,
        shared_node_ids: list[str],
        password: str | None = None,
        ttl_hours: int = DEFAULT_TOKEN_TTL_HOURS,
    ) -> dict[str, Any]:
        """
        Generate a new symbiosis token granting access to a sub-graph.

        The token UUID is cryptographically random and completely decoupled
        from the graph_id so that the share recipient cannot guess or enumerate
        internal IDs.

        Args:
            db:              Database session.
            graph_id:        UUID string of the graph being shared.
            shared_node_ids: List of node UUIDs to include in this share.
            password:        Optional plaintext password to protect the token.
                             Stored as a bcrypt hash (or SHA-256 stub here).
            ttl_hours:       How long the token is valid (default 24 h).

        Returns:
            Dict matching the SymbiosisToken TypeScript interface.
        """
        token_uuid = uuid.uuid4()
        expires_at = datetime.now(tz=timezone.utc) + timedelta(hours=ttl_hours)

        # Simple hash for the demo (swap for bcrypt in production)
        password_hash: str | None = None
        if password:
            password_hash = hashlib.sha256(password.encode()).hexdigest()

        db_token = SymbiosisTokenModel(
            token=token_uuid,
            graph_id=uuid.UUID(graph_id),
            shared_node_ids=[str(n) for n in shared_node_ids],
            expires_at=expires_at,
            password_hash=password_hash,
        )
        db.add(db_token)
        await db.flush()

        logger.info("symbiosis_token_created", token=str(token_uuid), graph_id=graph_id)

        return {
            "token":          str(token_uuid),
            "graphId":        graph_id,
            "sharedNodeIds":  [str(n) for n in shared_node_ids],
            "expiresAt":      expires_at.isoformat(),
            "passwordHash":   password_hash,
        }

    async def redeem_token(
        self,
        db: AsyncSession,
        token_str: str,
        password: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Validate and redeem a symbiosis token.

        Validation steps:
        1. Look up the token UUID in the database.
        2. Check it has not expired (expires_at > now).
        3. Check it has not been used (used == False).
        4. If password-protected, verify the hash matches.
        5. Mark the token as used.

        Args:
            db:         Database session.
            token_str:  UUID string of the token to redeem.
            password:   Provided password (plaintext); compared to stored hash.

        Returns:
            Dict with graph_id and shared_node_ids if valid, else None.
        """
        try:
            token_uuid = uuid.UUID(token_str)
        except ValueError:
            return None

        result = await db.execute(
            select(SymbiosisTokenModel).where(SymbiosisTokenModel.token == token_uuid)
        )
        db_token = result.scalars().first()

        if db_token is None:
            logger.warning("symbiosis_token_not_found", token=token_str)
            return None

        if db_token.expires_at < datetime.now(tz=timezone.utc):
            logger.warning("symbiosis_token_expired", token=token_str)
            return None

        if db_token.used:
            logger.warning("symbiosis_token_already_used", token=token_str)
            return None

        if db_token.password_hash and password:
            provided_hash = hashlib.sha256(password.encode()).hexdigest()
            if provided_hash != db_token.password_hash:
                logger.warning("symbiosis_token_wrong_password", token=token_str)
                return None
        elif db_token.password_hash and not password:
            logger.warning("symbiosis_token_requires_password", token=token_str)
            return None

        # Mark as used (single-use tokens)
        db_token.used = True
        await db.flush()

        logger.info("symbiosis_token_redeemed", token=token_str, graph_id=str(db_token.graph_id))

        return {
            "graphId":       str(db_token.graph_id),
            "sharedNodeIds": db_token.shared_node_ids,
        }
