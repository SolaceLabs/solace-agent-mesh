"""
Skill search service for finding relevant skills.

This service provides unified search across:
- Database skills (learned and authored)
- Static skill files
- Vector similarity search
"""

import logging
from typing import Optional, List, Dict, Any, Tuple

from ..entities import (
    Skill,
    SkillType,
    SkillScope,
)
from ..repository import SkillRepository
from .embedding_service import EmbeddingService
from .static_skill_loader import StaticSkillLoader

logger = logging.getLogger(__name__)


class SkillSearchService:
    """
    Unified skill search service.
    
    Combines multiple search strategies:
    - Text-based search in database
    - Vector similarity search
    - Static skill file search
    
    Results are merged and ranked by relevance.
    """
    
    def __init__(
        self,
        repository: SkillRepository,
        embedding_service: Optional[EmbeddingService] = None,
        static_loader: Optional[StaticSkillLoader] = None,
        enable_vector_search: bool = True,
        vector_search_weight: float = 0.6,
        text_search_weight: float = 0.4,
    ):
        """
        Initialize the skill search service.
        
        Args:
            repository: Skill repository for database access
            embedding_service: Optional embedding service for vector search
            static_loader: Optional static skill loader
            enable_vector_search: Whether to use vector search
            vector_search_weight: Weight for vector search results (0-1)
            text_search_weight: Weight for text search results (0-1)
        """
        self.repository = repository
        self.embedding_service = embedding_service
        self.static_loader = static_loader
        self.enable_vector_search = enable_vector_search and embedding_service is not None
        self.vector_search_weight = vector_search_weight
        self.text_search_weight = text_search_weight
        
        # Cache for static skills
        self._static_skills_cache: Dict[str, Skill] = {}
        self._static_skills_loaded = False
    
    def search(
        self,
        query: str,
        agent_name: Optional[str] = None,
        user_id: Optional[str] = None,
        skill_type: Optional[SkillType] = None,
        scope: Optional[SkillScope] = None,
        include_global: bool = True,
        include_static: bool = True,
        limit: int = 10,
        min_similarity: float = 0.3,
    ) -> List[Tuple[Skill, float]]:
        """
        Search for skills matching a query.
        
        Args:
            query: Search query (natural language)
            agent_name: Optional agent name for filtering
            user_id: Optional user ID for filtering
            skill_type: Optional skill type filter
            scope: Optional scope filter
            include_global: Whether to include global skills
            include_static: Whether to include static skills
            limit: Maximum results to return
            min_similarity: Minimum similarity threshold for vector search
            
        Returns:
            List of (skill, score) tuples, sorted by relevance
        """
        results: Dict[str, Tuple[Skill, float]] = {}
        
        # Text-based database search
        db_skills = self._text_search(
            query=query,
            agent_name=agent_name,
            user_id=user_id,
            skill_type=skill_type,
            scope=scope,
            include_global=include_global,
            limit=limit * 2,  # Get more for merging
        )
        
        for skill in db_skills:
            # Simple text match scoring
            score = self._compute_text_score(query, skill)
            results[skill.id] = (skill, score * self.text_search_weight)
        
        # Vector similarity search
        if self.enable_vector_search and self.embedding_service:
            vector_results = self._vector_search(
                query=query,
                agent_name=agent_name,
                user_id=user_id,
                scope=scope,
                include_global=include_global,
                limit=limit * 2,
                min_similarity=min_similarity,
            )
            
            for skill, similarity in vector_results:
                if skill.id in results:
                    # Combine scores
                    existing_skill, existing_score = results[skill.id]
                    combined_score = existing_score + (similarity * self.vector_search_weight)
                    results[skill.id] = (existing_skill, combined_score)
                else:
                    results[skill.id] = (skill, similarity * self.vector_search_weight)
        
        # Static skill search
        if include_static and self.static_loader:
            static_skills = self._search_static_skills(
                query=query,
                agent_name=agent_name,
                user_id=user_id,
            )
            
            for skill in static_skills:
                if skill.id not in results:
                    score = self._compute_text_score(query, skill)
                    results[skill.id] = (skill, score * self.text_search_weight)
        
        # Sort by score and limit
        sorted_results = sorted(
            results.values(),
            key=lambda x: x[1],
            reverse=True,
        )
        
        return sorted_results[:limit]
    
    def get_skills_for_agent(
        self,
        agent_name: str,
        user_id: Optional[str] = None,
        include_global: bool = True,
        include_static: bool = True,
        limit: int = 50,
    ) -> List[Skill]:
        """
        Get all skills available to an agent.
        
        Args:
            agent_name: The agent name
            user_id: Optional user ID
            include_global: Whether to include global skills
            include_static: Whether to include static skills
            limit: Maximum results
            
        Returns:
            List of available skills
        """
        skills: Dict[str, Skill] = {}
        
        # Database skills
        db_skills = self.repository.get_skills_for_agent(
            agent_name=agent_name,
            user_id=user_id,
            include_global=include_global,
            limit=limit,
        )
        
        for skill in db_skills:
            skills[skill.id] = skill
        
        # Static skills
        if include_static and self.static_loader:
            # Load agent-specific static skills
            agent_static = self.static_loader.load_agent_skills(agent_name)
            for skill in agent_static:
                if skill.id not in skills:
                    skills[skill.id] = skill
            
            # Load global static skills
            if include_global:
                global_static = self.static_loader.load_global_skills()
                for skill in global_static:
                    if skill.id not in skills:
                        skills[skill.id] = skill
            
            # Load user static skills
            if user_id:
                user_static = self.static_loader.load_user_skills(user_id)
                for skill in user_static:
                    if skill.id not in skills:
                        skills[skill.id] = skill
        
        return list(skills.values())[:limit]
    
    def find_similar_skills(
        self,
        skill: Skill,
        limit: int = 5,
        min_similarity: float = 0.5,
    ) -> List[Tuple[Skill, float]]:
        """
        Find skills similar to a given skill.
        
        Args:
            skill: The reference skill
            limit: Maximum results
            min_similarity: Minimum similarity threshold
            
        Returns:
            List of (skill, similarity) tuples
        """
        if not self.enable_vector_search or not self.embedding_service:
            # Fall back to text search
            return self.search(
                query=f"{skill.name} {skill.description}",
                limit=limit + 1,  # +1 to exclude self
            )[1:]  # Skip first (self)
        
        # Get or compute embedding for reference skill
        if skill.embedding:
            query_embedding = skill.embedding
        else:
            query_embedding = self.embedding_service.get_skill_embedding(
                skill.name,
                skill.description,
                skill.summary,
            )
        
        # Get all skills with embeddings
        candidates = self.repository.get_skills_with_embeddings()
        
        # Filter out the reference skill
        candidates = [s for s in candidates if s.id != skill.id]
        
        # Compute similarities
        results = []
        for candidate in candidates:
            if candidate.embedding:
                similarity = self.embedding_service.compute_similarity(
                    query_embedding,
                    candidate.embedding,
                )
                if similarity >= min_similarity:
                    results.append((candidate, similarity))
        
        # Sort by similarity
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results[:limit]
    
    def _text_search(
        self,
        query: str,
        agent_name: Optional[str] = None,
        user_id: Optional[str] = None,
        skill_type: Optional[SkillType] = None,
        scope: Optional[SkillScope] = None,
        include_global: bool = True,
        limit: int = 20,
    ) -> List[Skill]:
        """Perform text-based search in database."""
        return self.repository.search_skills(
            query=query,
            skill_type=skill_type,
            scope=scope,
            owner_agent_name=agent_name,
            owner_user_id=user_id,
            limit=limit,
        )
    
    def _vector_search(
        self,
        query: str,
        agent_name: Optional[str] = None,
        user_id: Optional[str] = None,
        scope: Optional[SkillScope] = None,
        include_global: bool = True,
        limit: int = 20,
        min_similarity: float = 0.3,
    ) -> List[Tuple[Skill, float]]:
        """Perform vector similarity search."""
        if not self.embedding_service:
            return []
        
        # Get query embedding
        query_embedding = self.embedding_service.get_query_embedding(query)
        
        # Get candidate skills with embeddings
        candidates = self.repository.get_skills_with_embeddings(
            scope=scope,
            owner_agent_name=agent_name,
        )
        
        # Build candidate list
        candidate_embeddings = [
            (skill.id, skill.embedding)
            for skill in candidates
            if skill.embedding
        ]
        
        # Find similar
        similar_ids = self.embedding_service.find_similar(
            query_embedding,
            candidate_embeddings,
            top_k=limit,
            min_similarity=min_similarity,
        )
        
        # Map back to skills
        skill_map = {s.id: s for s in candidates}
        results = [
            (skill_map[skill_id], similarity)
            for skill_id, similarity in similar_ids
            if skill_id in skill_map
        ]
        
        return results
    
    def _search_static_skills(
        self,
        query: str,
        agent_name: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> List[Skill]:
        """Search static skill files."""
        if not self.static_loader:
            return []
        
        # Ensure static skills are loaded
        if not self._static_skills_loaded:
            self._load_static_skills()
        
        # Simple text matching
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        matches = []
        for skill in self._static_skills_cache.values():
            # Check scope
            if agent_name and skill.scope == SkillScope.AGENT:
                if skill.owner_agent_name != agent_name:
                    continue
            if user_id and skill.scope == SkillScope.USER:
                if skill.owner_user_id != user_id:
                    continue
            
            # Text matching
            skill_text = f"{skill.name} {skill.description}".lower()
            if skill.summary:
                skill_text += f" {skill.summary}".lower()
            
            # Check for word matches
            skill_words = set(skill_text.split())
            common_words = query_words & skill_words
            
            if common_words or query_lower in skill_text:
                matches.append(skill)
        
        return matches
    
    def _load_static_skills(self) -> None:
        """Load all static skills into cache."""
        if not self.static_loader:
            return
        
        skills = self.static_loader.load_all_skills()
        self._static_skills_cache = {s.id: s for s in skills}
        self._static_skills_loaded = True
    
    def _compute_text_score(self, query: str, skill: Skill) -> float:
        """
        Compute a simple text relevance score.
        
        Args:
            query: Search query
            skill: Skill to score
            
        Returns:
            Relevance score (0-1)
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        # Build skill text
        skill_text = f"{skill.name} {skill.description}".lower()
        if skill.summary:
            skill_text += f" {skill.summary}".lower()
        
        skill_words = set(skill_text.split())
        
        # Exact match bonus
        if query_lower in skill_text:
            return 1.0
        
        # Word overlap score
        if not query_words:
            return 0.0
        
        common_words = query_words & skill_words
        overlap_score = len(common_words) / len(query_words)
        
        # Name match bonus
        if query_lower in skill.name.lower():
            overlap_score = min(1.0, overlap_score + 0.3)
        
        return overlap_score
    
    def refresh_static_skills(self) -> None:
        """Refresh the static skills cache."""
        self._static_skills_loaded = False
        self._static_skills_cache.clear()
        self._load_static_skills()
    
    def get_skill_summaries(
        self,
        skills: List[Skill],
    ) -> List[Dict[str, Any]]:
        """
        Get summary dictionaries for skills (Level 1 disclosure).
        
        Args:
            skills: List of skills
            
        Returns:
            List of summary dictionaries
        """
        return [skill.to_summary_dict() for skill in skills]