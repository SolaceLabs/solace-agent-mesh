"""
Repository for versioned skill operations.

This repository handles CRUD operations for skill groups and versions,
following the pattern established by the prompt repository.
"""

import logging
import uuid
from typing import Optional, List, Tuple

from sqlalchemy import and_, or_, desc, func
from sqlalchemy.orm import Session, joinedload

from .versioned_models import SkillGroupModel, SkillVersionModel, SkillGroupUserModel, SkillGroupRole
from ..entities.versioned_entities import (
    SkillGroup,
    SkillVersion,
    SkillGroupUser,
    SkillType,
    SkillScope,
    AgentChainNode,
    AgentToolStep,
    now_epoch_ms,
)

log = logging.getLogger(__name__)


class VersionedSkillRepository:
    """
    Repository for versioned skill operations.
    
    Provides methods for:
    - Creating and managing skill groups
    - Creating and managing skill versions
    - Setting production versions
    - Searching skills
    - Managing user access
    """
    
    def __init__(self, session_factory):
        """
        Initialize the repository.
        
        Args:
            session_factory: SQLAlchemy session factory
        """
        self.session_factory = session_factory
    
    def _get_session(self) -> Session:
        """Get a database session."""
        return self.session_factory()
    
    # =========================================================================
    # Skill Group Operations
    # =========================================================================
    
    def create_group(self, group: SkillGroup) -> SkillGroup:
        """
        Create a new skill group.
        
        Args:
            group: The skill group to create
            
        Returns:
            The created skill group
        """
        with self._get_session() as session:
            model = SkillGroupModel(
                id=group.id,
                name=group.name,
                description=group.description,
                category=group.category,
                type=group.type.value if isinstance(group.type, SkillType) else group.type,
                scope=group.scope.value if isinstance(group.scope, SkillScope) else group.scope,
                owner_agent_name=group.owner_agent_name,
                owner_user_id=group.owner_user_id,
                production_version_id=group.production_version_id,
                is_archived=group.is_archived,
                created_at=group.created_at,
                updated_at=group.updated_at,
            )
            session.add(model)
            session.commit()
            session.refresh(model)
            return self._model_to_group(model)
    
    def get_group(self, group_id: str, include_versions: bool = False) -> Optional[SkillGroup]:
        """
        Get a skill group by ID.
        
        Args:
            group_id: The group ID
            include_versions: Whether to load all versions
            
        Returns:
            The skill group or None
        """
        with self._get_session() as session:
            query = session.query(SkillGroupModel).filter(
                SkillGroupModel.id == group_id
            )
            
            if include_versions:
                query = query.options(joinedload(SkillGroupModel.versions))
            
            model = query.first()
            if not model:
                return None
            
            group = self._model_to_group(model)
            
            # Load production version if set
            if model.production_version_id:
                prod_version = session.query(SkillVersionModel).filter(
                    SkillVersionModel.id == model.production_version_id
                ).first()
                if prod_version:
                    group.production_version = self._model_to_version(prod_version)
            
            # Load versions if requested
            if include_versions and model.versions:
                group.versions = [self._model_to_version(v) for v in model.versions]
            
            # Get version count
            group.version_count = session.query(func.count(SkillVersionModel.id)).filter(
                SkillVersionModel.group_id == group_id
            ).scalar() or 0
            
            return group
    
    def get_group_by_name(
        self,
        name: str,
        agent_name: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Optional[SkillGroup]:
        """
        Get a skill group by name.
        
        Args:
            name: The skill name
            agent_name: Optional agent name filter
            user_id: Optional user ID filter
            
        Returns:
            The skill group or None
        """
        with self._get_session() as session:
            query = session.query(SkillGroupModel).filter(
                SkillGroupModel.name == name,
                SkillGroupModel.is_archived == False,
            )
            
            if agent_name:
                query = query.filter(SkillGroupModel.owner_agent_name == agent_name)
            if user_id:
                query = query.filter(SkillGroupModel.owner_user_id == user_id)
            
            model = query.first()
            if not model:
                return None
            
            return self._model_to_group(model)
    
    def update_group(self, group_id: str, updates: dict) -> Optional[SkillGroup]:
        """
        Update a skill group.
        
        Args:
            group_id: The group ID
            updates: Dictionary of fields to update
            
        Returns:
            The updated skill group or None
        """
        with self._get_session() as session:
            model = session.query(SkillGroupModel).filter(
                SkillGroupModel.id == group_id
            ).first()
            
            if not model:
                return None
            
            # Apply updates
            for key, value in updates.items():
                if hasattr(model, key):
                    if key in ('type', 'scope') and isinstance(value, (SkillType, SkillScope)):
                        value = value.value
                    setattr(model, key, value)
            
            model.updated_at = now_epoch_ms()
            session.commit()
            session.refresh(model)
            return self._model_to_group(model)
    
    def delete_group(self, group_id: str) -> bool:
        """
        Delete a skill group (and all its versions).
        
        Args:
            group_id: The group ID
            
        Returns:
            True if deleted, False if not found
        """
        with self._get_session() as session:
            model = session.query(SkillGroupModel).filter(
                SkillGroupModel.id == group_id
            ).first()
            
            if not model:
                return False
            
            session.delete(model)
            session.commit()
            return True
    
    def archive_group(self, group_id: str) -> Optional[SkillGroup]:
        """
        Archive a skill group (soft delete).
        
        Args:
            group_id: The group ID
            
        Returns:
            The archived skill group or None
        """
        return self.update_group(group_id, {"is_archived": True})
    
    def list_groups(
        self,
        agent_name: Optional[str] = None,
        user_id: Optional[str] = None,
        scope: Optional[SkillScope] = None,
        skill_type: Optional[SkillType] = None,
        include_archived: bool = False,
        include_global: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SkillGroup]:
        """
        List skill groups with filters.
        
        Args:
            agent_name: Filter by agent name
            user_id: Filter by user ID
            scope: Filter by scope
            skill_type: Filter by type
            include_archived: Include archived groups
            include_global: Include global skills
            limit: Maximum results
            offset: Offset for pagination
            
        Returns:
            List of skill groups
        """
        with self._get_session() as session:
            query = session.query(SkillGroupModel)
            
            if not include_archived:
                query = query.filter(SkillGroupModel.is_archived == False)
            
            # Apply explicit scope filter if provided
            if scope:
                query = query.filter(SkillGroupModel.scope == scope.value)
            else:
                # Build scope filter based on context
                scope_filters = []
                
                if agent_name:
                    # Agent-specific: return agent-scoped skills for this agent + optionally global
                    scope_filters.append(
                        and_(
                            SkillGroupModel.scope == SkillScope.AGENT.value,
                            SkillGroupModel.owner_agent_name == agent_name
                        )
                    )
                    if include_global:
                        scope_filters.append(SkillGroupModel.scope == SkillScope.GLOBAL.value)
                    query = query.filter(or_(*scope_filters))
                elif user_id:
                    # User-specific: return user-scoped skills + shared + agent + optionally global
                    # Users should see all skills they have access to, including agent skills
                    scope_filters.append(
                        and_(
                            SkillGroupModel.scope == SkillScope.USER.value,
                            SkillGroupModel.owner_user_id == user_id
                        )
                    )
                    scope_filters.append(SkillGroupModel.scope == SkillScope.SHARED.value)
                    scope_filters.append(SkillGroupModel.scope == SkillScope.AGENT.value)  # Include all agent skills
                    if include_global:
                        scope_filters.append(SkillGroupModel.scope == SkillScope.GLOBAL.value)
                    query = query.filter(or_(*scope_filters))
                # else: no agent or user filter - return ALL skills (no scope filter applied)
            
            if skill_type:
                query = query.filter(SkillGroupModel.type == skill_type.value)
            
            query = query.order_by(desc(SkillGroupModel.updated_at))
            query = query.limit(limit).offset(offset)
            
            models = query.all()
            
            groups = []
            for model in models:
                group = self._model_to_group(model)
                # Get version count
                group.version_count = session.query(func.count(SkillVersionModel.id)).filter(
                    SkillVersionModel.group_id == model.id
                ).scalar() or 0
                groups.append(group)
            
            return groups
    
    # =========================================================================
    # Skill Version Operations
    # =========================================================================
    
    def create_version(self, version: SkillVersion) -> SkillVersion:
        """
        Create a new skill version.
        
        Args:
            version: The skill version to create
            
        Returns:
            The created skill version
        """
        with self._get_session() as session:
            model = SkillVersionModel(
                id=version.id,
                group_id=version.group_id,
                version=version.version,
                description=version.description,
                markdown_content=version.markdown_content,
                agent_chain=self._chain_to_json(version.agent_chain),
                tool_steps=self._steps_to_json(version.tool_steps),
                summary=version.summary,
                source_task_id=version.source_task_id,
                related_task_ids=version.related_task_ids,
                involved_agents=version.involved_agents,
                embedding=version.embedding,
                complexity_score=version.complexity_score,
                created_by_user_id=version.created_by_user_id,
                creation_reason=version.creation_reason,
                created_at=version.created_at,
            )
            session.add(model)
            session.commit()
            session.refresh(model)
            return self._model_to_version(model)
    
    def get_version(self, version_id: str) -> Optional[SkillVersion]:
        """
        Get a skill version by ID.
        
        Args:
            version_id: The version ID
            
        Returns:
            The skill version or None
        """
        with self._get_session() as session:
            model = session.query(SkillVersionModel).filter(
                SkillVersionModel.id == version_id
            ).first()
            
            if not model:
                return None
            
            return self._model_to_version(model)
    
    def get_latest_version(self, group_id: str) -> Optional[SkillVersion]:
        """
        Get the latest version of a skill group.
        
        Args:
            group_id: The group ID
            
        Returns:
            The latest skill version or None
        """
        with self._get_session() as session:
            model = session.query(SkillVersionModel).filter(
                SkillVersionModel.group_id == group_id
            ).order_by(desc(SkillVersionModel.version)).first()
            
            if not model:
                return None
            
            return self._model_to_version(model)
    
    def get_version_by_number(self, group_id: str, version_number: int) -> Optional[SkillVersion]:
        """
        Get a specific version by number.
        
        Args:
            group_id: The group ID
            version_number: The version number
            
        Returns:
            The skill version or None
        """
        with self._get_session() as session:
            model = session.query(SkillVersionModel).filter(
                SkillVersionModel.group_id == group_id,
                SkillVersionModel.version == version_number
            ).first()
            
            if not model:
                return None
            
            return self._model_to_version(model)
    
    def list_versions(self, group_id: str) -> List[SkillVersion]:
        """
        List all versions of a skill group.
        
        Args:
            group_id: The group ID
            
        Returns:
            List of skill versions, ordered by version number descending
        """
        with self._get_session() as session:
            models = session.query(SkillVersionModel).filter(
                SkillVersionModel.group_id == group_id
            ).order_by(desc(SkillVersionModel.version)).all()
            
            return [self._model_to_version(m) for m in models]
    
    def get_next_version_number(self, group_id: str) -> int:
        """
        Get the next version number for a group.
        
        Args:
            group_id: The group ID
            
        Returns:
            The next version number
        """
        with self._get_session() as session:
            max_version = session.query(func.max(SkillVersionModel.version)).filter(
                SkillVersionModel.group_id == group_id
            ).scalar()
            
            return (max_version or 0) + 1
    
    def set_production_version(self, group_id: str, version_id: str) -> Optional[SkillGroup]:
        """
        Set the production version for a skill group.
        
        Args:
            group_id: The group ID
            version_id: The version ID to set as production
            
        Returns:
            The updated skill group or None
        """
        return self.update_group(group_id, {"production_version_id": version_id})
    
    def update_version_embedding(self, version_id: str, embedding: List[float]) -> bool:
        """
        Update the embedding for a skill version.
        
        Args:
            version_id: The version ID
            embedding: The embedding vector
            
        Returns:
            True if updated, False if not found
        """
        with self._get_session() as session:
            model = session.query(SkillVersionModel).filter(
                SkillVersionModel.id == version_id
            ).first()
            
            if not model:
                return False
            
            model.embedding = embedding
            session.commit()
            return True
    
    def update_version(self, version_id: str, updates: dict) -> Optional[SkillVersion]:
        """
        Update a skill version.
        
        Args:
            version_id: The version ID
            updates: Dictionary of fields to update
            
        Returns:
            The updated skill version or None
        """
        with self._get_session() as session:
            model = session.query(SkillVersionModel).filter(
                SkillVersionModel.id == version_id
            ).first()
            
            if not model:
                return None
            
            # Apply updates
            for key, value in updates.items():
                if hasattr(model, key):
                    setattr(model, key, value)
            
            session.commit()
            session.refresh(model)
            return self._model_to_version(model)
    
    # =========================================================================
    # Search Operations
    # =========================================================================
    
    def search_groups(
        self,
        query: str,
        agent_name: Optional[str] = None,
        user_id: Optional[str] = None,
        scope: Optional[SkillScope] = None,
        limit: int = 20,
    ) -> List[Tuple[SkillGroup, float]]:
        """
        Search skill groups by text query.
        
        This performs a simple text search on name and description.
        For semantic search, use search_by_embedding.
        
        Args:
            query: Search query
            agent_name: Filter by agent name
            user_id: Filter by user ID
            scope: Filter by scope
            limit: Maximum results
            
        Returns:
            List of (skill_group, score) tuples
        """
        with self._get_session() as session:
            # Simple text search on name and description
            search_pattern = f"%{query}%"
            
            db_query = session.query(SkillGroupModel).filter(
                SkillGroupModel.is_archived == False,
                or_(
                    SkillGroupModel.name.ilike(search_pattern),
                    SkillGroupModel.description.ilike(search_pattern),
                )
            )
            
            if agent_name:
                db_query = db_query.filter(SkillGroupModel.owner_agent_name == agent_name)
            if user_id:
                db_query = db_query.filter(
                    or_(
                        SkillGroupModel.owner_user_id == user_id,
                        SkillGroupModel.scope == SkillScope.GLOBAL.value,
                        SkillGroupModel.scope == SkillScope.SHARED.value,
                    )
                )
            if scope:
                db_query = db_query.filter(SkillGroupModel.scope == scope.value)
            
            db_query = db_query.limit(limit)
            models = db_query.all()
            
            # Calculate simple relevance score
            results = []
            query_lower = query.lower()
            for model in models:
                score = 0.0
                if model.name and query_lower in model.name.lower():
                    score += 0.6
                if model.description and query_lower in model.description.lower():
                    score += 0.4
                results.append((self._model_to_group(model), score))
            
            # Sort by score
            results.sort(key=lambda x: x[1], reverse=True)
            return results
    
    def search_by_embedding(
        self,
        embedding: List[float],
        agent_name: Optional[str] = None,
        user_id: Optional[str] = None,
        scope: Optional[SkillScope] = None,
        limit: int = 10,
        threshold: float = 0.5,
    ) -> List[Tuple[SkillGroup, float]]:
        """
        Search skill groups by embedding similarity.
        
        Searches production versions' embeddings and returns matching groups.
        
        Args:
            embedding: Query embedding vector
            agent_name: Filter by agent name
            user_id: Filter by user ID
            scope: Filter by scope
            limit: Maximum results
            threshold: Minimum similarity threshold
            
        Returns:
            List of (skill_group, similarity_score) tuples
        """
        with self._get_session() as session:
            # Get all groups with their production versions
            query = session.query(SkillGroupModel).filter(
                SkillGroupModel.is_archived == False,
                SkillGroupModel.production_version_id.isnot(None),
            )
            
            if agent_name:
                query = query.filter(SkillGroupModel.owner_agent_name == agent_name)
            if user_id:
                query = query.filter(
                    or_(
                        SkillGroupModel.owner_user_id == user_id,
                        SkillGroupModel.scope == SkillScope.GLOBAL.value,
                        SkillGroupModel.scope == SkillScope.SHARED.value,
                    )
                )
            if scope:
                query = query.filter(SkillGroupModel.scope == scope.value)
            
            groups = query.all()
            
            # Calculate similarity for each group's production version
            results = []
            for group_model in groups:
                version = session.query(SkillVersionModel).filter(
                    SkillVersionModel.id == group_model.production_version_id
                ).first()
                
                if version and version.embedding:
                    similarity = self._cosine_similarity(embedding, version.embedding)
                    if similarity >= threshold:
                        group = self._model_to_group(group_model)
                        group.production_version = self._model_to_version(version)
                        results.append((group, similarity))
            
            # Sort by similarity
            results.sort(key=lambda x: x[1], reverse=True)
            return results[:limit]
    
    # =========================================================================
    # User Access Operations
    # =========================================================================
    
    def add_user_to_group(
        self,
        group_id: str,
        user_id: str,
        role: SkillGroupRole,
        added_by_user_id: str,
    ) -> SkillGroupUser:
        """
        Add a user to a skill group.
        
        Args:
            group_id: The group ID
            user_id: The user ID to add
            role: The role to assign
            added_by_user_id: The user who is adding
            
        Returns:
            The created skill group user
        """
        with self._get_session() as session:
            model = SkillGroupUserModel(
                id=str(uuid.uuid4()),
                skill_group_id=group_id,
                user_id=user_id,
                role=role,
                added_at=now_epoch_ms(),
                added_by_user_id=added_by_user_id,
            )
            session.add(model)
            session.commit()
            session.refresh(model)
            return self._model_to_group_user(model)
    
    def remove_user_from_group(self, group_id: str, user_id: str) -> bool:
        """
        Remove a user from a skill group.
        
        Args:
            group_id: The group ID
            user_id: The user ID to remove
            
        Returns:
            True if removed, False if not found
        """
        with self._get_session() as session:
            model = session.query(SkillGroupUserModel).filter(
                SkillGroupUserModel.skill_group_id == group_id,
                SkillGroupUserModel.user_id == user_id,
            ).first()
            
            if not model:
                return False
            
            session.delete(model)
            session.commit()
            return True
    
    def get_user_role(self, group_id: str, user_id: str) -> Optional[SkillGroupRole]:
        """
        Get a user's role in a skill group.
        
        Args:
            group_id: The group ID
            user_id: The user ID
            
        Returns:
            The user's role or None if not a member
        """
        with self._get_session() as session:
            model = session.query(SkillGroupUserModel).filter(
                SkillGroupUserModel.skill_group_id == group_id,
                SkillGroupUserModel.user_id == user_id,
            ).first()
            
            if not model:
                return None
            
            return model.role
    
    def list_group_users(self, group_id: str) -> List[SkillGroupUser]:
        """
        List all users with access to a skill group.
        
        Args:
            group_id: The group ID
            
        Returns:
            List of skill group users
        """
        with self._get_session() as session:
            models = session.query(SkillGroupUserModel).filter(
                SkillGroupUserModel.skill_group_id == group_id
            ).all()
            
            return [self._model_to_group_user(m) for m in models]
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _model_to_group(self, model: SkillGroupModel) -> SkillGroup:
        """Convert SQLAlchemy model to domain entity."""
        return SkillGroup(
            id=model.id,
            name=model.name,
            description=model.description,
            category=model.category,
            type=SkillType(model.type) if model.type else SkillType.LEARNED,
            scope=SkillScope(model.scope) if model.scope else SkillScope.AGENT,
            owner_agent_name=model.owner_agent_name,
            owner_user_id=model.owner_user_id,
            production_version_id=model.production_version_id,
            is_archived=model.is_archived,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
    
    def _model_to_version(self, model: SkillVersionModel) -> SkillVersion:
        """Convert SQLAlchemy model to domain entity."""
        version = SkillVersion(
            id=model.id,
            group_id=model.group_id,
            version=model.version,
            description=model.description,
            markdown_content=model.markdown_content,
            agent_chain=self._json_to_chain(model.agent_chain),
            tool_steps=self._json_to_steps(model.tool_steps),
            summary=model.summary,
            source_task_id=model.source_task_id,
            related_task_ids=model.related_task_ids,
            involved_agents=model.involved_agents,
            embedding=model.embedding,
            complexity_score=model.complexity_score or 0,
            created_by_user_id=model.created_by_user_id,
            creation_reason=model.creation_reason,
            created_at=model.created_at,
        )
        # Add bundled resources fields if they exist on the model
        if hasattr(model, 'bundled_resources_uri'):
            version.bundled_resources_uri = model.bundled_resources_uri
        if hasattr(model, 'bundled_resources_manifest'):
            version.bundled_resources_manifest = model.bundled_resources_manifest
        return version
    
    def _model_to_group_user(self, model: SkillGroupUserModel) -> SkillGroupUser:
        """Convert SQLAlchemy model to domain entity."""
        return SkillGroupUser(
            id=model.id,
            skill_group_id=model.skill_group_id,
            user_id=model.user_id,
            role=model.role if isinstance(model.role, SkillGroupRole) else SkillGroupRole(model.role),
            added_at=model.added_at,
            added_by_user_id=model.added_by_user_id,
        )
    
    def _chain_to_json(self, chain: Optional[List[AgentChainNode]]) -> Optional[List[dict]]:
        """Convert agent chain to JSON-serializable format."""
        if not chain:
            return None
        return [
            {
                "agent_name": node.agent_name,
                "task_id": node.task_id,
                "role": node.role,
                "tools_used": node.tools_used,
            }
            for node in chain
        ]
    
    def _json_to_chain(self, data: Optional[List[dict]]) -> Optional[List[AgentChainNode]]:
        """Convert JSON to agent chain."""
        if not data:
            return None
        return [
            AgentChainNode(
                agent_name=item.get("agent_name", ""),
                task_id=item.get("task_id", ""),
                role=item.get("role", "specialist"),
                tools_used=item.get("tools_used", []),
            )
            for item in data
        ]
    
    def _steps_to_json(self, steps: Optional[List[AgentToolStep]]) -> Optional[List[dict]]:
        """Convert tool steps to JSON-serializable format."""
        if not steps:
            return None
        return [
            {
                "step_type": step.step_type,
                "agent_name": step.agent_name,
                "tool_name": step.tool_name,
                "action": step.action,
                "parameters_template": step.parameters_template,
                "sequence_number": step.sequence_number,
            }
            for step in steps
        ]
    
    def _json_to_steps(self, data: Optional[List[dict]]) -> Optional[List[AgentToolStep]]:
        """Convert JSON to tool steps."""
        if not data:
            return None
        return [
            AgentToolStep(
                step_type=item.get("step_type", "tool_call"),
                agent_name=item.get("agent_name", ""),
                tool_name=item.get("tool_name", ""),
                action=item.get("action", ""),
                parameters_template=item.get("parameters_template"),
                sequence_number=item.get("sequence_number", 1),
            )
            for item in data
        ]
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)