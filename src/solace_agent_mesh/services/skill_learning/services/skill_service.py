"""
Main skill service for the SAM Skill Learning System.

This service provides the primary interface for:
- Skill CRUD operations
- Skill search and retrieval
- Feedback processing
- Learning queue management
"""

import logging
from typing import Optional, List, Dict, Any, Tuple

from ..entities import (
    Skill,
    SkillType,
    SkillScope,
    SkillFeedback,
    SkillUsage,
    SkillShare,
    LearningQueueItem,
    generate_id,
    now_epoch_ms,
)
from ..repository import SkillRepository
from .embedding_service import EmbeddingService
from .static_skill_loader import StaticSkillLoader
from .skill_search_service import SkillSearchService

logger = logging.getLogger(__name__)


class SkillService:
    """
    Main service for skill management.
    
    Provides a unified interface for all skill operations,
    coordinating between repository, search, and embedding services.
    """
    
    def __init__(
        self,
        repository: SkillRepository,
        embedding_service: Optional[EmbeddingService] = None,
        static_loader: Optional[StaticSkillLoader] = None,
        auto_generate_embeddings: bool = True,
    ):
        """
        Initialize the skill service.
        
        Args:
            repository: Skill repository for database access
            embedding_service: Optional embedding service
            static_loader: Optional static skill loader
            auto_generate_embeddings: Whether to auto-generate embeddings
        """
        self.repository = repository
        self.embedding_service = embedding_service
        self.static_loader = static_loader
        self.auto_generate_embeddings = auto_generate_embeddings
        
        # Initialize search service
        self.search_service = SkillSearchService(
            repository=repository,
            embedding_service=embedding_service,
            static_loader=static_loader,
        )
    
    # ==================== Skill CRUD ====================
    
    def create_skill(
        self,
        name: str,
        description: str,
        skill_type: SkillType,
        scope: SkillScope,
        owner_agent_name: Optional[str] = None,
        owner_user_id: Optional[str] = None,
        markdown_content: Optional[str] = None,
        tool_steps: Optional[List[Dict[str, Any]]] = None,
        agent_chain: Optional[List[Dict[str, Any]]] = None,
        source_task_id: Optional[str] = None,
        summary: Optional[str] = None,
        involved_agents: Optional[List[str]] = None,
        bundled_resources: Optional[Dict[str, Any]] = None,
        base_directory: Optional[str] = None,
    ) -> Skill:
        """
        Create a new skill.
        
        Args:
            name: Skill name (hyphen-case)
            description: When to use this skill
            skill_type: Type of skill (learned/authored)
            scope: Skill scope (agent/user/shared/global)
            owner_agent_name: Agent owner for agent-scoped skills
            owner_user_id: User owner for user/shared-scoped skills
            markdown_content: Markdown content for authored skills
            tool_steps: Tool steps for learned skills
            agent_chain: Agent chain for learned skills
            source_task_id: Source task ID for learned skills
            summary: Brief summary
            involved_agents: List of involved agents
            bundled_resources: OpenSkills bundled resources (references, scripts, assets)
            base_directory: Base directory for folder-based skills
            
        Returns:
            The created skill
        """
        from ..entities import AgentToolStep, AgentChainNode
        
        # Validate scope and ownership
        if scope == SkillScope.AGENT and not owner_agent_name:
            raise ValueError("Agent-scoped skills require owner_agent_name")
        if scope in (SkillScope.USER, SkillScope.SHARED) and not owner_user_id:
            raise ValueError("User/shared-scoped skills require owner_user_id")
        
        # Create skill entity
        skill = Skill(
            id=generate_id(),
            name=name,
            description=description,
            type=skill_type,
            scope=scope,
            owner_agent_name=owner_agent_name,
            owner_user_id=owner_user_id,
            markdown_content=markdown_content,
            tool_steps=[AgentToolStep(**s) for s in (tool_steps or [])],
            agent_chain=[AgentChainNode(**n) for n in (agent_chain or [])],
            source_task_id=source_task_id,
            summary=summary,
            involved_agents=involved_agents or [],
            bundled_resources=bundled_resources,
            base_directory=base_directory,
            created_at=now_epoch_ms(),
            updated_at=now_epoch_ms(),
        )
        
        # Generate embedding if enabled
        if self.auto_generate_embeddings and self.embedding_service:
            try:
                embedding = self.embedding_service.get_skill_embedding(
                    skill.name,
                    skill.description,
                    skill.summary,
                )
                skill.embedding = embedding
            except Exception as e:
                logger.warning(f"Failed to generate embedding for skill {name}: {e}")
        
        # Save to database
        created_skill = self.repository.create_skill(skill)
        
        logger.info(f"Created skill: {name} (type={skill_type}, scope={scope})")
        return created_skill
    
    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """
        Get a skill by ID.
        
        Searches both the database and static skills.
        
        Args:
            skill_id: The skill ID
            
        Returns:
            The skill if found
        """
        # First check database
        skill = self.repository.get_skill(skill_id)
        if skill:
            return skill
        
        # Then check static skills via search service
        if self.search_service and self.search_service._static_skills_cache:
            # Ensure static skills are loaded
            if not self.search_service._static_skills_loaded:
                self.search_service._load_static_skills()
            
            return self.search_service._static_skills_cache.get(skill_id)
        
        # Try loading static skills if not yet loaded
        if self.static_loader:
            static_skills = self.static_loader.load_all_skills()
            for static_skill in static_skills:
                if static_skill.id == skill_id:
                    return static_skill
        
        return None
    
    def get_skill_by_name(
        self,
        name: str,
        scope: Optional[SkillScope] = None,
        owner_agent_name: Optional[str] = None,
        owner_user_id: Optional[str] = None,
    ) -> Optional[Skill]:
        """
        Get a skill by name.
        
        Args:
            name: Skill name
            scope: Optional scope filter
            owner_agent_name: Optional agent filter
            owner_user_id: Optional user filter
            
        Returns:
            The skill if found
        """
        return self.repository.get_skill_by_name(
            name=name,
            scope=scope,
            owner_agent_name=owner_agent_name,
            owner_user_id=owner_user_id,
        )
    
    def update_skill(self, skill: Skill) -> Skill:
        """
        Update an existing skill.
        
        Args:
            skill: The skill with updated fields
            
        Returns:
            The updated skill
        """
        # Regenerate embedding if content changed
        if self.auto_generate_embeddings and self.embedding_service:
            try:
                embedding = self.embedding_service.get_skill_embedding(
                    skill.name,
                    skill.description,
                    skill.summary,
                    use_cache=False,  # Force regeneration
                )
                skill.embedding = embedding
            except Exception as e:
                logger.warning(f"Failed to regenerate embedding for skill {skill.name}: {e}")
        
        return self.repository.update_skill(skill)
    
    def delete_skill(self, skill_id: str) -> bool:
        """
        Delete a skill.
        
        Args:
            skill_id: The skill ID
            
        Returns:
            True if deleted
        """
        return self.repository.delete_skill(skill_id)
    
    # ==================== Skill Search ====================
    
    def search_skills(
        self,
        query: str,
        agent_name: Optional[str] = None,
        user_id: Optional[str] = None,
        skill_type: Optional[SkillType] = None,
        scope: Optional[SkillScope] = None,
        include_global: bool = True,
        limit: int = 10,
    ) -> List[Tuple[Skill, float]]:
        """
        Search for skills.
        
        Args:
            query: Search query
            agent_name: Optional agent filter
            user_id: Optional user filter
            skill_type: Optional type filter
            scope: Optional scope filter
            include_global: Whether to include global skills
            limit: Maximum results
            
        Returns:
            List of (skill, score) tuples
        """
        return self.search_service.search(
            query=query,
            agent_name=agent_name,
            user_id=user_id,
            skill_type=skill_type,
            scope=scope,
            include_global=include_global,
            limit=limit,
        )
    
    def get_skills_for_agent(
        self,
        agent_name: str,
        user_id: Optional[str] = None,
        include_global: bool = True,
        limit: int = 50,
    ) -> List[Skill]:
        """
        Get all skills available to an agent.
        
        Args:
            agent_name: The agent name
            user_id: Optional user ID
            include_global: Whether to include global skills
            limit: Maximum results
            
        Returns:
            List of available skills
        """
        return self.search_service.get_skills_for_agent(
            agent_name=agent_name,
            user_id=user_id,
            include_global=include_global,
            limit=limit,
        )
    
    def get_skill_summaries_for_prompt(
        self,
        agent_name: str,
        user_id: Optional[str] = None,
        task_context: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get skill summaries for prompt injection (Level 1 disclosure).
        
        If task_context is provided, returns skills most relevant to the task.
        Otherwise, returns top skills by success rate.
        
        Args:
            agent_name: The agent name
            user_id: Optional user ID
            task_context: Optional task context for relevance filtering
            limit: Maximum skills to return
            
        Returns:
            List of skill summary dictionaries
        """
        if task_context:
            # Search for relevant skills
            results = self.search_skills(
                query=task_context,
                agent_name=agent_name,
                user_id=user_id,
                limit=limit,
            )
            skills = [skill for skill, _ in results]
        else:
            # Get top skills by success rate
            skills = self.get_skills_for_agent(
                agent_name=agent_name,
                user_id=user_id,
                limit=limit,
            )
        
        return self.search_service.get_skill_summaries(skills)
    
    # ==================== Feedback Operations ====================
    
    def record_feedback(
        self,
        skill_id: str,
        task_id: str,
        feedback_type: str,
        user_id: Optional[str] = None,
        correction_text: Optional[str] = None,
    ) -> SkillFeedback:
        """
        Record feedback for a skill.
        
        Args:
            skill_id: The skill ID
            task_id: The task ID
            feedback_type: Type of feedback (thumbs_up, thumbs_down, correction)
            user_id: Optional user ID
            correction_text: Optional correction details
            
        Returns:
            The created feedback
        """
        feedback = SkillFeedback(
            id=generate_id(),
            skill_id=skill_id,
            task_id=task_id,
            user_id=user_id,
            feedback_type=feedback_type,
            correction_text=correction_text,
            created_at=now_epoch_ms(),
        )
        
        return self.repository.add_feedback(feedback)
    
    def record_usage(
        self,
        skill_id: str,
        task_id: str,
        agent_name: str,
        user_id: Optional[str] = None,
    ) -> SkillUsage:
        """
        Record skill usage.
        
        Args:
            skill_id: The skill ID
            task_id: The task ID
            agent_name: The agent that used the skill
            user_id: Optional user ID
            
        Returns:
            The created usage record
        """
        usage = SkillUsage(
            id=generate_id(),
            skill_id=skill_id,
            task_id=task_id,
            agent_name=agent_name,
            user_id=user_id,
            used_at=now_epoch_ms(),
        )
        
        return self.repository.record_usage(usage)
    
    # ==================== Sharing Operations ====================
    
    def share_skill(
        self,
        skill_id: str,
        shared_with_user_id: str,
        shared_by_user_id: str,
    ) -> SkillShare:
        """
        Share a skill with another user.
        
        Args:
            skill_id: The skill ID
            shared_with_user_id: User to share with
            shared_by_user_id: User sharing the skill
            
        Returns:
            The share record
        """
        share = SkillShare(
            skill_id=skill_id,
            shared_with_user_id=shared_with_user_id,
            shared_by_user_id=shared_by_user_id,
            shared_at=now_epoch_ms(),
        )
        
        return self.repository.share_skill(share)
    
    def get_shared_skills(self, user_id: str) -> List[Skill]:
        """
        Get skills shared with a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            List of shared skills
        """
        return self.repository.get_shared_skills(user_id)
    
    # ==================== Learning Queue ====================
    
    def enqueue_for_learning(
        self,
        task_id: str,
        agent_name: str,
        user_id: Optional[str] = None,
    ) -> LearningQueueItem:
        """
        Add a task to the learning queue.
        
        Args:
            task_id: The task ID
            agent_name: The agent that completed the task
            user_id: Optional user ID
            
        Returns:
            The queue item
        """
        item = LearningQueueItem(
            id=generate_id(),
            task_id=task_id,
            agent_name=agent_name,
            user_id=user_id,
            status="pending",
            queued_at=now_epoch_ms(),
        )
        
        return self.repository.enqueue_for_learning(item)
    
    def get_pending_learning_items(
        self,
        limit: int = 10,
    ) -> List[LearningQueueItem]:
        """
        Get pending items from the learning queue.
        
        Args:
            limit: Maximum items
            
        Returns:
            List of pending items
        """
        return self.repository.get_pending_learning_items(limit)
    
    def update_learning_item_status(
        self,
        item_id: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> Optional[LearningQueueItem]:
        """
        Update learning queue item status.
        
        Args:
            item_id: The item ID
            status: New status
            error_message: Optional error message
            
        Returns:
            The updated item
        """
        return self.repository.update_learning_item(
            item_id=item_id,
            status=status,
            error_message=error_message,
        )
    
    # ==================== Embedding Operations ====================
    
    def regenerate_embeddings(
        self,
        skill_ids: Optional[List[str]] = None,
    ) -> int:
        """
        Regenerate embeddings for skills.
        
        Args:
            skill_ids: Optional list of skill IDs (all if None)
            
        Returns:
            Number of skills updated
        """
        if not self.embedding_service:
            logger.warning("Embedding service not configured")
            return 0
        
        count = 0
        
        if skill_ids:
            skills = [self.repository.get_skill(sid) for sid in skill_ids]
            skills = [s for s in skills if s]
        else:
            # Get all skills
            skills = self.repository.search_skills(limit=10000)
        
        for skill in skills:
            try:
                embedding = self.embedding_service.get_skill_embedding(
                    skill.name,
                    skill.description,
                    skill.summary,
                    use_cache=False,
                )
                self.repository.update_skill_embedding(
                    skill.id,
                    embedding,
                    self.embedding_service.model_name,
                )
                count += 1
            except Exception as e:
                logger.error(f"Failed to regenerate embedding for {skill.id}: {e}")
        
        logger.info(f"Regenerated embeddings for {count} skills")
        return count
    
    # ==================== Static Skills ====================
    
    def load_static_skills(self) -> List[Skill]:
        """
        Load static skills from files.
        
        Returns:
            List of loaded skills
        """
        if not self.static_loader:
            return []
        
        return self.static_loader.load_all_skills()
    
    def sync_static_skills_to_database(self) -> int:
        """
        Sync static skills to the database.
        
        Creates or updates database records for static skills.
        
        Returns:
            Number of skills synced
        """
        if not self.static_loader:
            return 0
        
        static_skills = self.static_loader.load_all_skills()
        count = 0
        
        for skill in static_skills:
            existing = self.repository.get_skill_by_name(
                name=skill.name,
                scope=skill.scope,
                owner_agent_name=skill.owner_agent_name,
                owner_user_id=skill.owner_user_id,
            )
            
            if existing:
                # Update existing
                existing.description = skill.description
                existing.markdown_content = skill.markdown_content
                existing.summary = skill.summary
                self.repository.update_skill(existing)
            else:
                # Create new
                self.repository.create_skill(skill)
            
            count += 1
        
        logger.info(f"Synced {count} static skills to database")
        return count
    
    def export_skill_to_file(
        self,
        skill_id: str,
        directory: Optional[str] = None,
    ) -> Optional[str]:
        """
        Export a skill to a SKILL.md file.
        
        Args:
            skill_id: The skill ID
            directory: Optional target directory
            
        Returns:
            Path to the created file
        """
        if not self.static_loader:
            logger.warning("Static loader not configured")
            return None
        
        skill = self.repository.get_skill(skill_id)
        if not skill:
            return None
        
        return self.static_loader.create_skill_file(skill, directory)