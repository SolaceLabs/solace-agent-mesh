from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from ...application.services.agent_service import AgentService
from ...dependencies import get_test_agent_service
from ..dto.requests.agent_requests import CreateAgentRequest, UpdateAgentRequest
from ..dto.responses.agent_responses import AgentResponse

router = APIRouter()


@router.post("/test/agents", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    request: CreateAgentRequest,
    agent_service: AgentService = Depends(get_test_agent_service),
):
    try:
        new_agent = agent_service.create_agent(
            display_name=request.display_name,
            prompt=request.prompt,
            agent_card_data=request.agent_card.dict(),
        )
        return AgentResponse.from_entity(new_agent)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create agent: {e}",
        )


@router.get("/test/agents", response_model=List[AgentResponse])
async def get_all_agents(
    agent_service: AgentService = Depends(get_test_agent_service),
):
    try:
        agents = agent_service.get_all_agents()
        return [AgentResponse.from_entity(agent) for agent in agents]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get agents: {e}",
        )


@router.get("/test/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: UUID,
    agent_service: AgentService = Depends(get_test_agent_service),
):
    try:
        agent = agent_service.get_agent(agent_id)
        if agent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found"
            )
        return AgentResponse.from_entity(agent)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get agent: {e}",
        )


@router.patch("/test/agents/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: UUID,
    request: UpdateAgentRequest,
    agent_service: AgentService = Depends(get_test_agent_service),
):
    try:
        agent_card_data = request.agent_card.dict(exclude_unset=True) if request.agent_card else None
        updated_agent = agent_service.update_agent(
            agent_id=agent_id,
            display_name=request.display_name,
            prompt=request.prompt,
            agent_card_data=agent_card_data,
        )
        if updated_agent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found"
            )
        return AgentResponse.from_entity(updated_agent)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update agent: {e}",
        )


@router.delete("/test/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: UUID,
    agent_service: AgentService = Depends(get_test_agent_service),
):
    try:
        if not agent_service.delete_agent(agent_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete agent: {e}",
        )
