"""
API endpoints for people-related features, such as user search for autocomplete.
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query

from ..dependencies import get_people_service
from ..services.people_service import PeopleService
from solace_agent_mesh.shared.api.pagination import DataResponse
from solace_agent_mesh.shared.api.response_utils import create_data_response

log = logging.getLogger(__name__)

router = APIRouter()


@router.get("/people/search", response_model=DataResponse[List[Dict[str, Any]]])
async def search_people(
    q: str = Query(
        ...,
        max_length=50,
        description="Search query for user name/email (1+ characters).",
    ),
    limit: int = Query(
        10, ge=1, le=25, description="Maximum number of results to return."
    ),
    people_service: PeopleService = Depends(get_people_service),
):
    """
    Searches for users to populate frontend autocomplete suggestions (e.g., for @mentions).
    """
    log.debug("Endpoint /people/search called with query: '%s'", q)
    results = await people_service.search_for_users(query=q, limit=limit)
    return create_data_response(results)
