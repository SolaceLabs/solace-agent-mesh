"""
Service layer for versioned skill operations.

This service provides business logic for:
- Creating and managing skill groups
- Creating new versions
- Setting production versions
- Rollback functionality
- Searching skills
"""

import logging
import uuid
from typing import Optional, List, Tuple

from ..repository.versioned_repository import VersionedSkillRepository
from ..entities.versioned_entities import (
    SkillGroup,
    SkillVersion,
    SkillGroupUser,
    SkillType,
    SkillScope,
    SkillGroupRole,
    AgentChainNode,
    AgentToolStep,
    CreateSkillGroupRequest,
    CreateVersionRequest,
    now_epoch_ms,
)

log = logging.getLogger(__name__)


class VersionedSkillService:
    """
    Service for versioned skill operations.
    
    Provides high-level business logic for skill management with versioning.
    """
    
    def __init__(
        self,
        repository: VersionedSkillRepository,
        embedding_service=None,
        static_loader=None,
    ):
        """
        Initialize the service.
        
        Args:
            repository: The versioned skill repository
            embedding_service: Optional service for generating embeddings
            static_loader: Optional static skill loader for filesystem skills
        """
        self.repository = repository
        self.embedding_service = embedding_service
        self.static_loader = static_loader
        
        # Cache for static skills
        self._static_skills_cache = {}
        self._static_skills_loaded = False
    
    # =========================================================================
    # Skill Group Operations
    # =========================================================================
    
    def create_skill(
        self,
        name: str,
        description: str,
        skill_type: SkillType = SkillType.AUTHORED,
        scope: SkillScope = SkillScope.USER,
        category: Optional[str] = None,
        owner_agent_name: Optional[str] = None,
        owner_user_id: Optional[str] = None,
        markdown_content: Optional[str] = None,
        agent_chain: Optional[List[AgentChainNode]] = None,
        tool_steps: Optional[List[AgentToolStep]] = None,
        summary: Optional[str] = None,
        source_task_id: Optional[str] = None,
        involved_agents: Optional[List[str]] = None,
        created_by_user_id: Optional[str] = None,
    ) -> SkillGroup:
        """
        Create a new skill (group + initial version).
        
        This creates both a skill group and its first version (v1),
        setting v1 as the production version.
        
        Args:
            name: Skill name
            description: Full description
            skill_type: Type of skill (learned/authored)
            scope: Visibility scope
            category: Optional category
            owner_agent_name: Owning agent
            owner_user_id: Owning user
            markdown_content: Human-readable content
            agent_chain: Agent chain nodes
            tool_steps: Tool steps
            summary: Brief summary
            source_task_id: Source task ID
            involved_agents: List of involved agents
            created_by_user_id: User creating the skill
            
        Returns:
            The created skill group with production version set
            
        Raises:
            ValueError: If a skill with the same name already exists for the agent
        """
        # Check for existing skill with same name
        existing = self.repository.get_group_by_name(
            name=name,
            agent_name=owner_agent_name,
            user_id=owner_user_id,
        )
        if existing:
            raise ValueError(f"Skill '{name}' already exists")
        
        now = now_epoch_ms()
        
        # Create group
        group_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())
        
        group = SkillGroup(
            id=group_id,
            name=name,
            description=description[:500] if description else None,  # Truncate for group
            category=category,
            type=skill_type,
            scope=scope,
            owner_agent_name=owner_agent_name,
            owner_user_id=owner_user_id,
            production_version_id=version_id,
            is_archived=False,
            created_at=now,
            updated_at=now,
        )
        
        # Create initial version
        version = SkillVersion(
            id=version_id,
            group_id=group_id,
            version=1,
            description=description,
            markdown_content=markdown_content,
            agent_chain=agent_chain,
            tool_steps=tool_steps,
            summary=summary,
            source_task_id=source_task_id,
            involved_agents=involved_agents,
            created_by_user_id=created_by_user_id or owner_user_id,
            creation_reason="Initial version",
            created_at=now,
        )
        
        # Generate embedding if service available
        if self.embedding_service and description:
            try:
                embedding = self.embedding_service.generate_embedding(description)
                version.embedding = embedding
            except Exception as e:
                log.warning(f"Failed to generate embedding: {e}")
        
        # Save to database
        created_group = self.repository.create_group(group)
        created_version = self.repository.create_version(version)
        
        # Set production version
        self.repository.set_production_version(group_id, version_id)
        
        # Return group with version attached
        created_group.production_version = created_version
        created_group.version_count = 1
        
        log.info(f"Created skill '{name}' (group={group_id}, version={version_id})")
        return created_group
    
    def get_skill(self, group_id: str, include_versions: bool = False) -> Optional[SkillGroup]:
        """
        Get a skill group by ID.
        
        Checks both database and static skills cache.
        
        Args:
            group_id: The group ID
            include_versions: Whether to load all versions
            
        Returns:
            The skill group or None
        """
        # First check database
        group = self.repository.get_group(group_id, include_versions=include_versions)
        if group:
            return group
        
        # Check static skills cache
        if self.static_loader:
            if not self._static_skills_loaded:
                self._load_static_skills()
            
            if group_id in self._static_skills_cache:
                log.debug(f"Found skill {group_id} in static skills cache")
                return self._static_skills_cache[group_id]
        
        return None
    
    def get_skill_by_name(
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
        return self.repository.get_group_by_name(name, agent_name, user_id)
    
    def update_skill(
        self,
        group_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Optional[SkillGroup]:
        """
        Update skill group metadata.
        
        Note: This only updates group-level metadata, not version content.
        To update content, create a new version.
        
        Args:
            group_id: The group ID
            name: New name
            description: New description
            category: New category
            
        Returns:
            The updated skill group or None
        """
        updates = {}
        if name is not None:
            updates["name"] = name
        if description is not None:
            updates["description"] = description[:500] if description else None
        if category is not None:
            updates["category"] = category
        
        if not updates:
            return self.repository.get_group(group_id)
        
        return self.repository.update_group(group_id, updates)
    
    def delete_skill(self, group_id: str) -> bool:
        """
        Delete a skill group (and all its versions).
        
        Args:
            group_id: The group ID
            
        Returns:
            True if deleted, False if not found
        """
        return self.repository.delete_group(group_id)
    
    def archive_skill(self, group_id: str) -> Optional[SkillGroup]:
        """
        Archive a skill (soft delete).
        
        Args:
            group_id: The group ID
            
        Returns:
            The archived skill group or None
        """
        return self.repository.archive_group(group_id)
    
    def list_skills(
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
        
        Includes both database skills and static filesystem skills.
        
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
        # Get database skills
        db_groups = self.repository.list_groups(
            agent_name=agent_name,
            user_id=user_id,
            scope=scope,
            skill_type=skill_type,
            include_archived=include_archived,
            include_global=include_global,
            limit=limit,
            offset=offset,
        )
        
        log.info(f"Database returned {len(db_groups)} skill groups")
        
        # Load and add static skills if loader is configured
        if self.static_loader:
            if not self._static_skills_loaded:
                self._load_static_skills()
            
            # Convert static skills to groups and add them
            static_groups = list(self._static_skills_cache.values())
            log.info(f"Static cache has {len(static_groups)} skills")
            
            # Apply filters to static skills
            filtered_static = self._filter_static_skills(
                static_groups,
                agent_name=agent_name,
                user_id=user_id,
                scope=scope,
                skill_type=skill_type,
            )
            
            log.info(f"After filtering: {len(filtered_static)} static skills")
            
            # Combine and limit
            all_groups = db_groups + filtered_static
            log.info(f"Returning {len(all_groups[:limit])} total skills (limit={limit})")
            return all_groups[:limit]
        
        log.info(f"No static loader, returning {len(db_groups)} database skills")
        return db_groups
    
    def _load_static_skills(self):
        """Load static skills from filesystem and cache them as groups."""
        if not self.static_loader:
            return
        
        try:
            static_skills = self.static_loader.load_all_skills()
            log.info(f"StaticSkillLoader returned {len(static_skills)} skills")
            
            # Convert legacy Skill entities to SkillGroup entities
            for skill in static_skills:
                try:
                    # Create a pseudo-group for each static skill
                    group = SkillGroup(
                        id=skill.id,
                        name=skill.name,
                        description=skill.description,
                        type=skill.type,
                        scope=skill.scope,
                        owner_agent_name=getattr(skill, 'owner_agent_name', None),
                        owner_user_id=getattr(skill, 'owner_user_id', None),
                        is_archived=False,
                        created_at=getattr(skill, 'created_at', now_epoch_ms()),
                        updated_at=getattr(skill, 'updated_at', now_epoch_ms()),
                        version_count=1,
                        production_version_id=skill.id,
                    )
                    
                    # Create a pseudo-version for the static skill
                    version = SkillVersion(
                        id=skill.id,
                        group_id=skill.id,
                        version=1,
                        description=skill.description,
                        markdown_content=getattr(skill, 'markdown_content', None),
                        agent_chain=getattr(skill, 'agent_chain', None),
                        tool_steps=getattr(skill, 'tool_steps', None),
                        summary=getattr(skill, 'summary', None),
                        source_task_id=getattr(skill, 'source_task_id', None),
                        related_task_ids=getattr(skill, 'related_task_ids', None),
                        involved_agents=getattr(skill, 'involved_agents', None),
                        complexity_score=getattr(skill, 'complexity_score', 0) or 0,
                        created_at=getattr(skill, 'created_at', now_epoch_ms()),
                        creation_reason="Static skill from filesystem",
                    )
                    
                    group.production_version = version
                    self._static_skills_cache[skill.id] = group
                    log.debug(f"Loaded static skill: {skill.name}")
                    
                except Exception as e:
                    log.warning(f"Failed to convert static skill {skill.name}: {e}")
                    continue
            
            self._static_skills_loaded = True
            log.info(f"Successfully loaded {len(self._static_skills_cache)} static skills from filesystem")
            
        except Exception as e:
            log.error(f"Failed to load static skills: {e}", exc_info=True)
    
    def _filter_static_skills(
        self,
        skills: List[SkillGroup],
        agent_name: Optional[str] = None,
        user_id: Optional[str] = None,
        scope: Optional[SkillScope] = None,
        skill_type: Optional[SkillType] = None,
    ) -> List[SkillGroup]:
        """
        Filter static skills based on criteria.
        
        Note: Static skills are generally available to all users, so we don't
        filter by user_id. We only filter by explicit scope/type/agent filters.
        """
        filtered = skills
        
        if scope:
            filtered = [s for s in filtered if s.scope == scope]
        if agent_name:
            # Only filter by agent if the skill is agent-scoped
            filtered = [s for s in filtered if s.scope != SkillScope.AGENT or s.owner_agent_name == agent_name]
        # Don't filter by user_id - static skills are available to all users
        if skill_type:
            filtered = [s for s in filtered if s.type == skill_type]
        
        return filtered
    
    def get_skills_for_agent(
        self,
        agent_name: str,
        user_id: Optional[str] = None,
        include_global: bool = True,
        limit: int = 50,
    ) -> List[SkillGroup]:
        """
        Get skills available to an agent.
        
        Args:
            agent_name: The agent name
            user_id: Optional user ID for user-scoped skills
            include_global: Include global skills
            limit: Maximum results
            
        Returns:
            List of skill groups
        """
        return self.repository.list_groups(
            agent_name=agent_name,
            user_id=user_id,
            include_global=include_global,
            limit=limit,
        )
    
    # =========================================================================
    # Version Operations
    # =========================================================================
    
    def create_version(
        self,
        group_id: str,
        description: str,
        creation_reason: str,
        created_by_user_id: Optional[str] = None,
        markdown_content: Optional[str] = None,
        agent_chain: Optional[List[AgentChainNode]] = None,
        tool_steps: Optional[List[AgentToolStep]] = None,
        summary: Optional[str] = None,
        source_task_id: Optional[str] = None,
        related_task_ids: Optional[List[str]] = None,
        involved_agents: Optional[List[str]] = None,
        set_as_production: bool = True,
    ) -> SkillVersion:
        """
        Create a new version of an existing skill.
        
        Args:
            group_id: The skill group ID
            description: Updated description
            creation_reason: Why this version was created
            created_by_user_id: Who created it
            markdown_content: Updated content
            agent_chain: Updated agent chain
            tool_steps: Updated tool steps
            summary: Updated summary
            source_task_id: Source task ID
            related_task_ids: Related task IDs
            involved_agents: Involved agents
            set_as_production: Whether to make this the active version
            
        Returns:
            The new skill version
            
        Raises:
            ValueError: If the group doesn't exist
        """
        group = self.repository.get_group(group_id)
        if not group:
            raise ValueError(f"Skill group {group_id} not found")
        
        # Get next version number
        next_version = self.repository.get_next_version_number(group_id)
        
        now = now_epoch_ms()
        version_id = str(uuid.uuid4())
        
        version = SkillVersion(
            id=version_id,
            group_id=group_id,
            version=next_version,
            description=description,
            markdown_content=markdown_content,
            agent_chain=agent_chain,
            tool_steps=tool_steps,
            summary=summary,
            source_task_id=source_task_id,
            related_task_ids=related_task_ids,
            involved_agents=involved_agents,
            created_by_user_id=created_by_user_id,
            creation_reason=creation_reason,
            created_at=now,
        )
        
        # Generate embedding if service available
        if self.embedding_service and description:
            try:
                embedding = self.embedding_service.generate_embedding(description)
                version.embedding = embedding
            except Exception as e:
                log.warning(f"Failed to generate embedding: {e}")
        
        # Save version
        created_version = self.repository.create_version(version)
        
        # Set as production if requested
        if set_as_production:
            self.repository.set_production_version(group_id, version_id)
            self.repository.update_group(group_id, {"updated_at": now})
        
        log.info(
            f"Created version {next_version} for skill '{group.name}' "
            f"(group={group_id}, version={version_id})"
        )
        return created_version
    
    def improve_skill(
        self,
        group_id: str,
        new_description: str,
        improvement_reason: str,
        source_task_id: Optional[str] = None,
        additional_task_ids: Optional[List[str]] = None,
        created_by_user_id: Optional[str] = None,
    ) -> SkillVersion:
        """
        Improve an existing skill based on new task execution.
        
        Creates a new version with improvements while preserving history.
        
        Args:
            group_id: The skill group ID
            new_description: Improved description
            improvement_reason: Why this improvement was made
            source_task_id: Task that triggered the improvement
            additional_task_ids: Additional related tasks
            created_by_user_id: User who triggered the improvement
            
        Returns:
            The new improved version
        """
        group = self.repository.get_group(group_id)
        if not group:
            raise ValueError(f"Skill group {group_id} not found")
        
        # Get current production version to copy content from
        current_version = None
        if group.production_version_id:
            current_version = self.repository.get_version(group.production_version_id)
        
        # Build related task IDs
        related_task_ids = []
        if current_version and current_version.related_task_ids:
            related_task_ids.extend(current_version.related_task_ids)
        if source_task_id and source_task_id not in related_task_ids:
            related_task_ids.append(source_task_id)
        if additional_task_ids:
            for task_id in additional_task_ids:
                if task_id not in related_task_ids:
                    related_task_ids.append(task_id)
        
        return self.create_version(
            group_id=group_id,
            description=new_description,
            creation_reason=improvement_reason,
            created_by_user_id=created_by_user_id,
            markdown_content=current_version.markdown_content if current_version else None,
            agent_chain=current_version.agent_chain if current_version else None,
            tool_steps=current_version.tool_steps if current_version else None,
            summary=current_version.summary if current_version else None,
            source_task_id=source_task_id,
            related_task_ids=related_task_ids,
            involved_agents=current_version.involved_agents if current_version else None,
            set_as_production=True,
        )
    
    def get_version(self, version_id: str) -> Optional[SkillVersion]:
        """
        Get a skill version by ID.
        
        Args:
            version_id: The version ID
            
        Returns:
            The skill version or None
        """
        return self.repository.get_version(version_id)
    
    def get_version_by_number(self, group_id: str, version_number: int) -> Optional[SkillVersion]:
        """
        Get a specific version by number.
        
        Args:
            group_id: The group ID
            version_number: The version number
            
        Returns:
            The skill version or None
        """
        return self.repository.get_version_by_number(group_id, version_number)
    
    def list_versions(self, group_id: str) -> List[SkillVersion]:
        """
        List all versions of a skill.
        
        Args:
            group_id: The group ID
            
        Returns:
            List of versions, ordered by version number descending
        """
        return self.repository.list_versions(group_id)
    
    def rollback_to_version(self, group_id: str, version_id: str) -> SkillGroup:
        """
        Rollback a skill to a previous version.
        
        This simply changes the production_version_id pointer.
        The current version is preserved in history.
        
        Args:
            group_id: The group ID
            version_id: The version ID to rollback to
            
        Returns:
            The updated skill group
            
        Raises:
            ValueError: If the version doesn't belong to the group
        """
        version = self.repository.get_version(version_id)
        if not version:
            raise ValueError(f"Version {version_id} not found")
        
        if version.group_id != group_id:
            raise ValueError(f"Version {version_id} does not belong to group {group_id}")
        
        self.repository.set_production_version(group_id, version_id)
        self.repository.update_group(group_id, {"updated_at": now_epoch_ms()})
        
        log.info(f"Rolled back skill group {group_id} to version {version.version}")
        return self.repository.get_group(group_id)
    
    # =========================================================================
    # Search Operations
    # =========================================================================
    
    def search_skills(
        self,
        query: str,
        agent_name: Optional[str] = None,
        user_id: Optional[str] = None,
        scope: Optional[SkillScope] = None,
        skill_type: Optional[SkillType] = None,
        include_global: bool = True,
        limit: int = 20,
    ) -> List[Tuple[SkillGroup, float]]:
        """
        Search for skills.
        
        Uses text search on name and description.
        For semantic search, use semantic_search.
        
        Args:
            query: Search query
            agent_name: Filter by agent name
            user_id: Filter by user ID
            scope: Filter by scope
            skill_type: Filter by type
            include_global: Include global skills
            limit: Maximum results
            
        Returns:
            List of (skill_group, score) tuples
        """
        return self.repository.search_groups(
            query=query,
            agent_name=agent_name,
            user_id=user_id,
            scope=scope,
            limit=limit,
        )
    
    def semantic_search(
        self,
        query: str,
        agent_name: Optional[str] = None,
        user_id: Optional[str] = None,
        scope: Optional[SkillScope] = None,
        limit: int = 10,
        threshold: float = 0.5,
    ) -> List[Tuple[SkillGroup, float]]:
        """
        Semantic search for skills using embeddings.
        
        Args:
            query: Search query
            agent_name: Filter by agent name
            user_id: Filter by user ID
            scope: Filter by scope
            limit: Maximum results
            threshold: Minimum similarity threshold
            
        Returns:
            List of (skill_group, similarity_score) tuples
        """
        if not self.embedding_service:
            log.warning("Embedding service not available, falling back to text search")
            return self.search_skills(query, agent_name, user_id, scope, limit=limit)
        
        try:
            # Generate query embedding
            query_embedding = self.embedding_service.generate_embedding(query)
            
            return self.repository.search_by_embedding(
                embedding=query_embedding,
                agent_name=agent_name,
                user_id=user_id,
                scope=scope,
                limit=limit,
                threshold=threshold,
            )
        except Exception as e:
            log.warning(f"Semantic search failed, falling back to text search: {e}")
            return self.search_skills(query, agent_name, user_id, scope, limit=limit)
    
    def find_similar_skills(
        self,
        description: str,
        agent_name: Optional[str] = None,
        threshold: float = 0.7,
        limit: int = 5,
    ) -> List[Tuple[SkillGroup, float]]:
        """
        Find skills similar to a given description.
        
        Used to detect duplicates before creating new skills.
        
        Args:
            description: Description to match
            agent_name: Filter by agent name
            threshold: Minimum similarity threshold
            limit: Maximum results
            
        Returns:
            List of (skill_group, similarity_score) tuples
        """
        return self.semantic_search(
            query=description,
            agent_name=agent_name,
            limit=limit,
            threshold=threshold,
        )
    
    def get_skill_summaries_for_prompt(
        self,
        agent_name: str,
        user_id: Optional[str] = None,
        task_context: Optional[str] = None,
        limit: int = 10,
    ) -> List[dict]:
        """
        Get skill summaries for prompt injection (Level 1 disclosure).
        
        If task_context is provided, returns skills most relevant to the task
        using semantic search. Otherwise, returns top skills.
        
        This method provides compatibility with AgentSkillInjector.
        
        Args:
            agent_name: The agent name
            user_id: Optional user ID
            task_context: Optional task context for relevance filtering (semantic search)
            limit: Maximum skills to return
            
        Returns:
            List of skill summary dictionaries
        """
        if task_context:
            # Use semantic search to find relevant skills
            results = self.semantic_search(
                query=task_context,
                agent_name=agent_name,
                user_id=user_id,
                limit=limit,
                threshold=0.3,  # Lower threshold for broader results
            )
            groups = [group for group, _ in results]
        else:
            # Get top skills for the agent
            groups = self.list_skills(
                agent_name=agent_name,
                user_id=user_id,
                include_global=True,
                limit=limit,
            )
        
        # Convert to summary dictionaries
        summaries = []
        for group in groups:
            summary = {
                "id": group.id,
                "name": group.name,
                "description": group.description or "",
            }
            
            # Add success rate if we have metrics (future enhancement)
            # For now, we don't track success rate in versioned skills
            
            summaries.append(summary)
        
        return summaries
    
    # =========================================================================
    # User Access Operations
    # =========================================================================
    
    def share_skill(
        self,
        group_id: str,
        shared_with_user_id: str,
        shared_by_user_id: str,
        role: SkillGroupRole = SkillGroupRole.VIEWER,
    ) -> SkillGroupUser:
        """
        Share a skill with another user.
        
        Args:
            group_id: The skill group ID
            shared_with_user_id: User to share with
            shared_by_user_id: User doing the sharing
            role: Role to assign
            
        Returns:
            The created skill group user
        """
        return self.repository.add_user_to_group(
            group_id=group_id,
            user_id=shared_with_user_id,
            role=role,
            added_by_user_id=shared_by_user_id,
        )
    
    def unshare_skill(self, group_id: str, user_id: str) -> bool:
        """
        Remove a user's access to a skill.
        
        Args:
            group_id: The skill group ID
            user_id: User to remove
            
        Returns:
            True if removed, False if not found
        """
        return self.repository.remove_user_from_group(group_id, user_id)
    
    def get_user_role(self, group_id: str, user_id: str) -> Optional[SkillGroupRole]:
        """
        Get a user's role in a skill group.
        
        Args:
            group_id: The skill group ID
            user_id: The user ID
            
        Returns:
            The user's role or None if not a member
        """
        return self.repository.get_user_role(group_id, user_id)
    
    def can_user_edit(self, group_id: str, user_id: str) -> bool:
        """
        Check if a user can edit a skill.
        
        Args:
            group_id: The skill group ID
            user_id: The user ID
            
        Returns:
            True if the user can edit
        """
        group = self.repository.get_group(group_id)
        if not group:
            return False
        
        # Owner can always edit
        if group.owner_user_id == user_id:
            return True
        
        # Check role
        role = self.repository.get_user_role(group_id, user_id)
        return role in (SkillGroupRole.OWNER, SkillGroupRole.EDITOR)
    
    # =========================================================================
    # Bundled Resources Operations
    # =========================================================================
    
    def update_version_resources(
        self,
        version_id: str,
        bundled_resources_uri: Optional[str] = None,
        bundled_resources_manifest: Optional[dict] = None,
    ) -> Optional[SkillVersion]:
        """
        Update a version's bundled resources reference.
        
        This is called after storing bundled resources to object storage
        to update the version with the storage URI and manifest.
        
        Args:
            version_id: The version ID
            bundled_resources_uri: URI to the stored resources (s3:// or file://)
            bundled_resources_manifest: Manifest of included files
            
        Returns:
            The updated version or None if not found
        """
        updates = {}
        if bundled_resources_uri is not None:
            updates["bundled_resources_uri"] = bundled_resources_uri
        if bundled_resources_manifest is not None:
            updates["bundled_resources_manifest"] = bundled_resources_manifest
        
        if not updates:
            return self.repository.get_version(version_id)
        
        updated = self.repository.update_version(version_id, updates)
        if updated:
            log.info(f"Updated version {version_id} with bundled resources: {bundled_resources_uri}")
        return updated