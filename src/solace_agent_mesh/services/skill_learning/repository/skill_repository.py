"""
Skill repository for database operations.

This module provides the data access layer for skills, including
CRUD operations, search, and query methods.
"""

import logging
from typing import Optional, List, Dict, Any
from sqlalchemy import create_engine, and_, or_, desc, func, select
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

from .models import (
    Base,
    SkillModel,
    SkillShareModel,
    SkillFeedbackModel,
    SkillUsageModel,
    LearningQueueModel,
    SkillEmbeddingModel,
)
from ..entities import (
    Skill,
    SkillType,
    SkillScope,
    AgentToolStep,
    AgentChainNode,
    SkillShare,
    SkillFeedback,
    SkillUsage,
    LearningQueueItem,
    now_epoch_ms,
)

logger = logging.getLogger(__name__)


class SkillRepository:
    """
    Repository for skill database operations.
    
    Provides methods for:
    - CRUD operations on skills
    - Skill search and filtering
    - Feedback and usage tracking
    - Learning queue management
    """
    
    def __init__(self, database_url: str):
        """
        Initialize the repository with a database connection.
        
        Args:
            database_url: SQLAlchemy database URL
        """
        self.engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(bind=self.engine)
    
    def create_tables(self):
        """Create all tables if they don't exist."""
        Base.metadata.create_all(self.engine)
    
    @contextmanager
    def get_session(self) -> Session:
        """Get a database session with automatic cleanup."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    # ==================== Skill CRUD ====================
    
    def create_skill(self, skill: Skill) -> Skill:
        """
        Create a new skill in the database.
        
        Args:
            skill: The skill entity to create
            
        Returns:
            The created skill with any database-generated fields
        """
        with self.get_session() as session:
            model = self._skill_to_model(skill)
            session.add(model)
            session.flush()
            return self._model_to_skill(model)
    
    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """
        Get a skill by ID.
        
        Args:
            skill_id: The skill ID
            
        Returns:
            The skill if found, None otherwise
        """
        with self.get_session() as session:
            model = session.query(SkillModel).filter(
                SkillModel.id == skill_id
            ).first()
            return self._model_to_skill(model) if model else None
    
    def get_skill_by_name(
        self, 
        name: str, 
        scope: Optional[SkillScope] = None,
        owner_agent_name: Optional[str] = None,
        owner_user_id: Optional[str] = None
    ) -> Optional[Skill]:
        """
        Get a skill by name with optional scope filtering.
        
        Args:
            name: The skill name
            scope: Optional scope filter
            owner_agent_name: Optional agent owner filter
            owner_user_id: Optional user owner filter
            
        Returns:
            The skill if found, None otherwise
        """
        with self.get_session() as session:
            query = session.query(SkillModel).filter(SkillModel.name == name)
            
            if scope:
                scope_value = scope.value if hasattr(scope, 'value') else scope
                query = query.filter(SkillModel.scope == scope_value)
            if owner_agent_name:
                query = query.filter(SkillModel.owner_agent_name == owner_agent_name)
            if owner_user_id:
                query = query.filter(SkillModel.owner_user_id == owner_user_id)
            
            model = query.first()
            return self._model_to_skill(model) if model else None
    
    def update_skill(self, skill_id: str = None, skill: Skill = None, updates: Dict[str, Any] = None) -> Skill:
        """
        Update an existing skill.
        
        Can be called in two ways:
        1. update_skill(skill=skill_entity) - Update with full skill entity
        2. update_skill(skill_id="id", updates={"field": "value"}) - Partial update
        
        Args:
            skill_id: The skill ID (for partial updates)
            skill: The skill entity with updated fields (for full updates)
            updates: Dictionary of fields to update (for partial updates)
            
        Returns:
            The updated skill
        """
        with self.get_session() as session:
            # Determine which mode we're in
            if skill is not None:
                # Full skill entity update
                target_id = skill.id
            elif skill_id is not None:
                target_id = skill_id
            else:
                raise ValueError("Either skill or skill_id must be provided")
            
            model = session.query(SkillModel).filter(
                SkillModel.id == target_id
            ).first()
            
            if not model:
                raise ValueError(f"Skill not found: {target_id}")
            
            if skill is not None:
                # Full entity update
                skill.updated_at = now_epoch_ms()
                self._update_model_from_skill(model, skill)
            elif updates is not None:
                # Partial update
                model.updated_at = now_epoch_ms()
                for key, value in updates.items():
                    if hasattr(model, key):
                        setattr(model, key, value)
            
            session.flush()
            return self._model_to_skill(model)
    
    def delete_skill(self, skill_id: str) -> bool:
        """
        Delete a skill by ID.
        
        Args:
            skill_id: The skill ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        with self.get_session() as session:
            result = session.query(SkillModel).filter(
                SkillModel.id == skill_id
            ).delete()
            return result > 0
    
    # ==================== Skill Search ====================
    
    def search_skills(
        self,
        query: Optional[str] = None,
        skill_type: Optional[SkillType] = None,
        scope: Optional[SkillScope] = None,
        owner_agent_name: Optional[str] = None,
        owner_user_id: Optional[str] = None,
        involved_agents: Optional[List[str]] = None,
        min_success_rate: Optional[float] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Skill]:
        """
        Search skills with various filters.
        
        Args:
            query: Text search in name and description
            skill_type: Filter by skill type
            scope: Filter by scope
            owner_agent_name: Filter by agent owner
            owner_user_id: Filter by user owner
            involved_agents: Filter by involved agents
            min_success_rate: Minimum success rate filter
            limit: Maximum results to return
            offset: Offset for pagination
            
        Returns:
            List of matching skills
        """
        with self.get_session() as session:
            q = session.query(SkillModel)
            
            # Text search
            if query:
                search_pattern = f"%{query}%"
                q = q.filter(
                    or_(
                        SkillModel.name.ilike(search_pattern),
                        SkillModel.description.ilike(search_pattern),
                        SkillModel.summary.ilike(search_pattern),
                    )
                )
            
            # Type filter
            if skill_type:
                q = q.filter(SkillModel.type == skill_type.value)
            
            # Scope filter
            if scope:
                q = q.filter(SkillModel.scope == scope.value)
            
            # Owner filters
            if owner_agent_name:
                q = q.filter(SkillModel.owner_agent_name == owner_agent_name)
            if owner_user_id:
                q = q.filter(SkillModel.owner_user_id == owner_user_id)
            
            # Involved agents filter (JSON contains)
            if involved_agents:
                for agent in involved_agents:
                    q = q.filter(
                        SkillModel.involved_agents.contains([agent])
                    )
            
            # Success rate filter
            if min_success_rate is not None:
                # Calculate success rate: success / (success + failure)
                q = q.filter(
                    and_(
                        SkillModel.success_count + SkillModel.failure_count > 0,
                        SkillModel.success_count * 1.0 / 
                        (SkillModel.success_count + SkillModel.failure_count) >= min_success_rate
                    )
                )
            
            # Order by success count and recency
            q = q.order_by(
                desc(SkillModel.success_count),
                desc(SkillModel.created_at)
            )
            
            # Pagination
            q = q.limit(limit).offset(offset)
            
            return [self._model_to_skill(m) for m in q.all()]
    
    def get_skills_for_agent(
        self,
        agent_name: str,
        user_id: Optional[str] = None,
        include_global: bool = True,
        limit: int = 50,
    ) -> List[Skill]:
        """
        Get all skills available to a specific agent.
        
        This includes:
        - Agent-scoped skills owned by this agent
        - User-scoped skills if user_id provided
        - Shared skills if user_id provided
        - Global skills if include_global is True
        
        Args:
            agent_name: The agent name
            user_id: Optional user ID for user/shared skills
            include_global: Whether to include global skills
            limit: Maximum results
            
        Returns:
            List of available skills
        """
        with self.get_session() as session:
            conditions = []
            
            # Agent-scoped skills for this agent
            conditions.append(
                and_(
                    SkillModel.scope == SkillScope.AGENT.value,
                    SkillModel.owner_agent_name == agent_name
                )
            )
            
            # User-scoped skills
            if user_id:
                conditions.append(
                    and_(
                        SkillModel.scope == SkillScope.USER.value,
                        SkillModel.owner_user_id == user_id
                    )
                )
                
                # Shared skills - need to join with shares table
                shared_skill_ids = select(SkillShareModel.skill_id).where(
                    SkillShareModel.shared_with_user_id == user_id
                )
                
                conditions.append(
                    and_(
                        SkillModel.scope == SkillScope.SHARED.value,
                        SkillModel.id.in_(shared_skill_ids)
                    )
                )
            
            # Global skills
            if include_global:
                conditions.append(SkillModel.scope == SkillScope.GLOBAL.value)
            
            q = session.query(SkillModel).filter(or_(*conditions))
            q = q.order_by(
                desc(SkillModel.success_count),
                desc(SkillModel.created_at)
            )
            q = q.limit(limit)
            
            return [self._model_to_skill(m) for m in q.all()]
    
    def get_skills_by_task(self, task_id: str) -> List[Skill]:
        """
        Get skills extracted from or related to a task.
        
        Args:
            task_id: The task ID
            
        Returns:
            List of related skills
        """
        with self.get_session() as session:
            q = session.query(SkillModel).filter(
                or_(
                    SkillModel.source_task_id == task_id,
                    SkillModel.related_task_ids.contains([task_id])
                )
            )
            return [self._model_to_skill(m) for m in q.all()]
    
    # ==================== Feedback Operations ====================
    
    def add_feedback(self, feedback: SkillFeedback) -> SkillFeedback:
        """
        Add feedback for a skill.
        
        Args:
            feedback: The feedback entity
            
        Returns:
            The created feedback
        """
        with self.get_session() as session:
            model = SkillFeedbackModel(
                id=feedback.id,
                skill_id=feedback.skill_id,
                task_id=feedback.task_id,
                user_id=feedback.user_id,
                feedback_type=feedback.feedback_type,
                correction_text=feedback.correction_text,
                created_at=feedback.created_at,
            )
            session.add(model)
            
            # Update skill metrics
            skill = session.query(SkillModel).filter(
                SkillModel.id == feedback.skill_id
            ).first()
            
            if skill:
                skill.last_feedback_at = feedback.created_at
                if feedback.feedback_type == "thumbs_up":
                    skill.success_count += 1
                elif feedback.feedback_type == "thumbs_down":
                    skill.failure_count += 1
                elif feedback.feedback_type == "correction":
                    skill.user_corrections += 1
            
            session.flush()
            return feedback
    
    def get_feedback_for_skill(
        self, 
        skill_id: str, 
        limit: int = 50
    ) -> List[SkillFeedback]:
        """
        Get feedback for a skill.
        
        Args:
            skill_id: The skill ID
            limit: Maximum results
            
        Returns:
            List of feedback entries
        """
        with self.get_session() as session:
            models = session.query(SkillFeedbackModel).filter(
                SkillFeedbackModel.skill_id == skill_id
            ).order_by(
                desc(SkillFeedbackModel.created_at)
            ).limit(limit).all()
            
            return [
                SkillFeedback(
                    id=m.id,
                    skill_id=m.skill_id,
                    task_id=m.task_id,
                    user_id=m.user_id,
                    feedback_type=m.feedback_type,
                    correction_text=m.correction_text,
                    created_at=m.created_at,
                )
                for m in models
            ]
    
    # ==================== Usage Tracking ====================
    
    def record_usage(self, usage: SkillUsage) -> SkillUsage:
        """
        Record skill usage.
        
        Args:
            usage: The usage entity
            
        Returns:
            The created usage record
        """
        with self.get_session() as session:
            model = SkillUsageModel(
                id=usage.id,
                skill_id=usage.skill_id,
                task_id=usage.task_id,
                agent_name=usage.agent_name,
                user_id=usage.user_id,
                used_at=usage.used_at,
            )
            session.add(model)
            session.flush()
            return usage
    
    def get_usage_stats(
        self, 
        skill_id: str
    ) -> Dict[str, Any]:
        """
        Get usage statistics for a skill.
        
        Args:
            skill_id: The skill ID
            
        Returns:
            Dictionary with usage statistics
        """
        with self.get_session() as session:
            total_uses = session.query(func.count(SkillUsageModel.id)).filter(
                SkillUsageModel.skill_id == skill_id
            ).scalar()
            
            unique_users = session.query(
                func.count(func.distinct(SkillUsageModel.user_id))
            ).filter(
                SkillUsageModel.skill_id == skill_id
            ).scalar()
            
            unique_agents = session.query(
                func.count(func.distinct(SkillUsageModel.agent_name))
            ).filter(
                SkillUsageModel.skill_id == skill_id
            ).scalar()
            
            return {
                "total_uses": total_uses or 0,
                "unique_users": unique_users or 0,
                "unique_agents": unique_agents or 0,
            }
    
    # ==================== Sharing Operations ====================
    
    def share_skill(self, share: SkillShare) -> SkillShare:
        """
        Share a skill with another user.
        
        Args:
            share: The share entity
            
        Returns:
            The created share record
        """
        with self.get_session() as session:
            # Update skill scope to shared if it was user-scoped
            skill = session.query(SkillModel).filter(
                SkillModel.id == share.skill_id
            ).first()
            
            if skill and skill.scope == SkillScope.USER.value:
                skill.scope = SkillScope.SHARED.value
            
            model = SkillShareModel(
                skill_id=share.skill_id,
                shared_with_user_id=share.shared_with_user_id,
                shared_by_user_id=share.shared_by_user_id,
                shared_at=share.shared_at,
            )
            session.add(model)
            session.flush()
            return share
    
    def get_shared_skills(self, user_id: str) -> List[Skill]:
        """
        Get skills shared with a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            List of shared skills
        """
        with self.get_session() as session:
            skill_ids = session.query(SkillShareModel.skill_id).filter(
                SkillShareModel.shared_with_user_id == user_id
            ).all()
            
            skill_ids = [s[0] for s in skill_ids]
            
            if not skill_ids:
                return []
            
            models = session.query(SkillModel).filter(
                SkillModel.id.in_(skill_ids)
            ).all()
            
            return [self._model_to_skill(m) for m in models]
    
    # ==================== Learning Queue ====================
    
    def enqueue_for_learning(self, item: LearningQueueItem) -> LearningQueueItem:
        """
        Add a task to the learning queue.
        
        Args:
            item: The queue item
            
        Returns:
            The created queue item
        """
        with self.get_session() as session:
            model = LearningQueueModel(
                id=item.id,
                task_id=item.task_id,
                agent_name=item.agent_name,
                user_id=item.user_id,
                status=item.status,
                queued_at=item.queued_at,
                started_at=item.started_at,
                completed_at=item.completed_at,
                error_message=item.error_message,
                retry_count=item.retry_count,
            )
            session.add(model)
            session.flush()
            return item
    
    def get_pending_learning_items(
        self, 
        limit: int = 10
    ) -> List[LearningQueueItem]:
        """
        Get pending items from the learning queue.
        
        Args:
            limit: Maximum items to return
            
        Returns:
            List of pending queue items
        """
        with self.get_session() as session:
            models = session.query(LearningQueueModel).filter(
                LearningQueueModel.status == "pending"
            ).order_by(
                LearningQueueModel.queued_at
            ).limit(limit).all()
            
            return [self._queue_model_to_entity(m) for m in models]
    
    def update_learning_item(
        self, 
        item_id: str, 
        status: str,
        error_message: Optional[str] = None
    ) -> Optional[LearningQueueItem]:
        """
        Update a learning queue item status.
        
        Args:
            item_id: The queue item ID
            status: New status
            error_message: Optional error message
            
        Returns:
            The updated item if found
        """
        with self.get_session() as session:
            model = session.query(LearningQueueModel).filter(
                LearningQueueModel.id == item_id
            ).first()
            
            if not model:
                return None
            
            model.status = status
            now = now_epoch_ms()
            
            if status == "processing":
                model.started_at = now
            elif status in ("completed", "failed"):
                model.completed_at = now
                if error_message:
                    model.error_message = error_message
                    model.retry_count += 1
            
            session.flush()
            return self._queue_model_to_entity(model)
    
    # ==================== Embedding Operations ====================
    
    def update_skill_embedding(
        self,
        skill_id: str,
        embedding: List[float],
        model_name: str,
    ) -> None:
        """
        Update or create embedding for a skill.
        
        Args:
            skill_id: The skill ID
            embedding: The embedding vector
            model_name: The embedding model name
        """
        with self.get_session() as session:
            # Update skill's embedding field
            skill = session.query(SkillModel).filter(
                SkillModel.id == skill_id
            ).first()
            
            if skill:
                skill.embedding = embedding
            
            # Also store in separate embeddings table
            existing = session.query(SkillEmbeddingModel).filter(
                SkillEmbeddingModel.skill_id == skill_id
            ).first()
            
            if existing:
                existing.embedding = embedding
                existing.embedding_model = model_name
                existing.embedding_dimension = len(embedding)
                existing.created_at = now_epoch_ms()
            else:
                model = SkillEmbeddingModel(
                    skill_id=skill_id,
                    embedding_model=model_name,
                    embedding_dimension=len(embedding),
                    embedding=embedding,
                    created_at=now_epoch_ms(),
                )
                session.add(model)
    
    def get_skills_with_embeddings(
        self,
        scope: Optional[SkillScope] = None,
        owner_agent_name: Optional[str] = None,
    ) -> List[Skill]:
        """
        Get skills that have embeddings for vector search.
        
        Args:
            scope: Optional scope filter
            owner_agent_name: Optional agent filter
            
        Returns:
            List of skills with embeddings
        """
        with self.get_session() as session:
            q = session.query(SkillModel).filter(
                SkillModel.embedding.isnot(None)
            )
            
            if scope:
                q = q.filter(SkillModel.scope == scope.value)
            if owner_agent_name:
                q = q.filter(SkillModel.owner_agent_name == owner_agent_name)
            
            return [self._model_to_skill(m) for m in q.all()]
    
    # ==================== Helper Methods ====================
    
    def _skill_to_model(self, skill: Skill) -> SkillModel:
        """Convert a Skill entity to a SkillModel."""
        return SkillModel(
            id=skill.id,
            name=skill.name,
            description=skill.description,
            type=skill.type if isinstance(skill.type, str) else skill.type.value,
            scope=skill.scope if isinstance(skill.scope, str) else skill.scope.value,
            owner_agent_name=skill.owner_agent_name,
            owner_user_id=skill.owner_user_id,
            markdown_content=skill.markdown_content,
            agent_chain=[n.model_dump() for n in skill.agent_chain] if skill.agent_chain else None,
            tool_steps=[s.model_dump() for s in skill.tool_steps] if skill.tool_steps else None,
            source_task_id=skill.source_task_id,
            related_task_ids=skill.related_task_ids,
            involved_agents=skill.involved_agents,
            summary=skill.summary,
            created_at=skill.created_at,
            updated_at=skill.updated_at,
            success_count=skill.success_count,
            failure_count=skill.failure_count,
            user_corrections=skill.user_corrections,
            last_feedback_at=skill.last_feedback_at,
            parent_skill_id=skill.parent_skill_id,
            refinement_reason=skill.refinement_reason,
            complexity_score=skill.complexity_score,
            embedding=skill.embedding,
        )
    
    def _model_to_skill(self, model: SkillModel) -> Skill:
        """Convert a SkillModel to a Skill entity."""
        return Skill(
            id=model.id,
            name=model.name,
            description=model.description,
            type=SkillType(model.type),
            scope=SkillScope(model.scope),
            owner_agent_name=model.owner_agent_name,
            owner_user_id=model.owner_user_id,
            markdown_content=model.markdown_content,
            agent_chain=[AgentChainNode(**n) for n in (model.agent_chain or [])],
            tool_steps=[AgentToolStep(**s) for s in (model.tool_steps or [])],
            source_task_id=model.source_task_id,
            related_task_ids=model.related_task_ids or [],
            involved_agents=model.involved_agents or [],
            summary=model.summary,
            created_at=model.created_at,
            updated_at=model.updated_at,
            success_count=model.success_count,
            failure_count=model.failure_count,
            user_corrections=model.user_corrections,
            last_feedback_at=model.last_feedback_at,
            parent_skill_id=model.parent_skill_id,
            refinement_reason=model.refinement_reason,
            complexity_score=model.complexity_score,
            embedding=model.embedding,
        )
    
    def _update_model_from_skill(self, model: SkillModel, skill: Skill) -> None:
        """Update a SkillModel from a Skill entity."""
        model.name = skill.name
        model.description = skill.description
        model.type = skill.type if isinstance(skill.type, str) else skill.type.value
        model.scope = skill.scope if isinstance(skill.scope, str) else skill.scope.value
        model.owner_agent_name = skill.owner_agent_name
        model.owner_user_id = skill.owner_user_id
        model.markdown_content = skill.markdown_content
        model.agent_chain = [n.model_dump() for n in skill.agent_chain] if skill.agent_chain else None
        model.tool_steps = [s.model_dump() for s in skill.tool_steps] if skill.tool_steps else None
        model.source_task_id = skill.source_task_id
        model.related_task_ids = skill.related_task_ids
        model.involved_agents = skill.involved_agents
        model.summary = skill.summary
        model.updated_at = skill.updated_at
        model.success_count = skill.success_count
        model.failure_count = skill.failure_count
        model.user_corrections = skill.user_corrections
        model.last_feedback_at = skill.last_feedback_at
        model.parent_skill_id = skill.parent_skill_id
        model.refinement_reason = skill.refinement_reason
        model.complexity_score = skill.complexity_score
        model.embedding = skill.embedding
    
    def _queue_model_to_entity(self, model: LearningQueueModel) -> LearningQueueItem:
        """Convert a LearningQueueModel to a LearningQueueItem entity."""
        return LearningQueueItem(
            id=model.id,
            task_id=model.task_id,
            agent_name=model.agent_name,
            user_id=model.user_id,
            status=model.status,
            queued_at=model.queued_at,
            started_at=model.started_at,
            completed_at=model.completed_at,
            error_message=model.error_message,
            retry_count=model.retry_count,
        )