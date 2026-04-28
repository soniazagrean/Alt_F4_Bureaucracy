from typing import Any
import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies.security import RBACRole, require_roles
from app.services.graph_service import get_influence_network

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/graph", tags=["Graph"])


@router.get("/influence-network")
async def get_influence_network_view(
    min_admin_companies: int = Query(3, ge=1, le=50),
    _=Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR, RBACRole.AUDITOR)),
) -> dict[str, Any]:
    try:
        return get_influence_network(min_admin_companies=min_admin_companies)
    except Exception as exc:
        try:
            from neo4j.exceptions import ServiceUnavailable, Neo4jError
        except ImportError:
            ServiceUnavailable = Neo4jError = Exception

        if isinstance(exc, (ServiceUnavailable, Neo4jError)):
            logger.error("Neo4j unavailable while fetching influence network: %s", exc)
            raise HTTPException(
                status_code=503,
                detail="Neo4j service unavailable",
            )
        raise
