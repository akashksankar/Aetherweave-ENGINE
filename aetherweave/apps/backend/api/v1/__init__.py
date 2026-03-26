"""
AetherWeave Backend — API v1 Router (Updated for Part 7)
=========================================================

Aggregates all /api/v1/* route modules.
"""

from fastapi import APIRouter

from apps.backend.api.v1.status       import router as status_router
from apps.backend.api.v1.architecture import router as architecture_router
from apps.backend.api.v1.evolution    import router as evolution_router
from apps.backend.api.v1.analytics    import router as analytics_router

# ── Aggregate router ──────────────────────────────────────────────────────────

router = APIRouter()

router.include_router(status_router,       tags=["System"])
router.include_router(architecture_router, tags=["Architecture"])
router.include_router(evolution_router,    tags=["Evolution"])
router.include_router(analytics_router,    tags=["Analytics"])
