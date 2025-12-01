"""
Topic definitions for skill learning message broker communication.

This module defines the Solace topic patterns used for:
- Learning nomination events (agent-nominated)
- Task completion events (passive learning - optional)
- Feedback events
- Skill search requests/responses
- Skill updates
"""


class SkillTopics:
    """
    Topic patterns for skill learning system.
    
    All topics follow the SAM naming convention:
    sam/{component}/{action}/{identifier}
    """
    
    # Learning nomination events - published by agents when they want a task learned
    # This is the PRIMARY way tasks get nominated for learning
    # Subscribe: sam/*/task/nominate-for-learning (using * for SMF single-level wildcard)
    LEARNING_NOMINATION = "sam/{agent_name}/task/nominate-for-learning"
    LEARNING_NOMINATION_SUBSCRIPTION = "sam/*/task/nominate-for-learning"
    
    # Task completion events - published by agents (passive learning - optional)
    # Only used if PASSIVE_LEARNING_ENABLED is true
    # Subscribe: sam/*/task/completed
    TASK_COMPLETED = "sam/{agent_name}/task/completed"
    TASK_COMPLETED_SUBSCRIPTION = "sam/*/task/completed"
    
    # Feedback events - published by gateways
    # Subscribe: sam/*/feedback/*
    FEEDBACK = "sam/{gateway_name}/feedback/{task_id}"
    FEEDBACK_SUBSCRIPTION = "sam/*/feedback/*"
    
    # Skill search requests - published by agents
    # Subscribe: sam/skills/search/request/*
    SKILL_SEARCH_REQUEST = "sam/skills/search/request/{request_id}"
    SKILL_SEARCH_REQUEST_SUBSCRIPTION = "sam/skills/search/request/*"
    
    # Skill search responses - published by skill service
    # Subscribe: sam/skills/search/response/{request_id}
    SKILL_SEARCH_RESPONSE = "sam/skills/search/response/{request_id}"
    
    # Agent-specific learned skills - published by skill service
    # Subscribe: sam/skills/*/learned
    AGENT_SKILLS_LEARNED = "sam/skills/{agent_name}/learned"
    AGENT_SKILLS_LEARNED_SUBSCRIPTION = "sam/skills/*/learned"
    
    # Global skills - published by skill service
    GLOBAL_SKILLS = "sam/skills/global"
    
    # Skill updates - published by skill service
    SKILL_CREATED = "sam/skills/events/created"
    SKILL_UPDATED = "sam/skills/events/updated"
    SKILL_DELETED = "sam/skills/events/deleted"
    
    # Learning queue events
    LEARNING_QUEUED = "sam/skills/learning/queued"
    LEARNING_COMPLETED = "sam/skills/learning/completed"
    LEARNING_FAILED = "sam/skills/learning/failed"
    
    @classmethod
    def learning_nomination(cls, agent_name: str) -> str:
        """Get topic for learning nomination from specific agent."""
        return cls.LEARNING_NOMINATION.format(agent_name=agent_name)
    
    @classmethod
    def task_completed(cls, agent_name: str) -> str:
        """Get topic for task completion from specific agent."""
        return cls.TASK_COMPLETED.format(agent_name=agent_name)
    
    @classmethod
    def feedback(cls, gateway_name: str, task_id: str) -> str:
        """Get topic for feedback from specific gateway."""
        return cls.FEEDBACK.format(gateway_name=gateway_name, task_id=task_id)
    
    @classmethod
    def skill_search_request(cls, request_id: str) -> str:
        """Get topic for skill search request."""
        return cls.SKILL_SEARCH_REQUEST.format(request_id=request_id)
    
    @classmethod
    def skill_search_response(cls, request_id: str) -> str:
        """Get topic for skill search response."""
        return cls.SKILL_SEARCH_RESPONSE.format(request_id=request_id)
    
    @classmethod
    def agent_skills_learned(cls, agent_name: str) -> str:
        """Get topic for agent-specific learned skills."""
        return cls.AGENT_SKILLS_LEARNED.format(agent_name=agent_name)