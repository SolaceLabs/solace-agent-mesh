"""
Feedback processor for handling human feedback on skills.

This module processes various types of feedback:
- Thumbs up/down on task results
- Explicit corrections
- User edits to skills
- Explicit skill saves

Feedback is used to:
- Update skill success/failure metrics
- Trigger skill refinement
- Create new skills from corrections
"""

import logging
from typing import Optional, List, Dict, Any
from enum import Enum

from ..entities import (
    Skill,
    SkillFeedback,
    SkillScope,
    generate_id,
    now_epoch_ms,
)
from ..repository import SkillRepository
from ..extraction import SkillExtractor

logger = logging.getLogger(__name__)


class FeedbackType(str, Enum):
    """Types of feedback that can be processed."""
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    CORRECTION = "correction"
    EXPLICIT_SAVE = "explicit_save"
    USER_EDIT = "user_edit"


class FeedbackProcessor:
    """
    Processes human feedback to improve skills.
    
    Handles:
    - Recording feedback in the database
    - Updating skill metrics
    - Triggering skill refinement when needed
    - Creating new skills from explicit saves
    """
    
    # Thresholds for automatic actions
    REFINEMENT_THRESHOLD = 3  # Number of corrections before refinement
    DEPRECATION_THRESHOLD = 0.3  # Success rate below which to deprecate
    
    def __init__(
        self,
        repository: SkillRepository,
        skill_extractor: Optional[SkillExtractor] = None,
        auto_refine: bool = True,
        refinement_threshold: int = 3,
        deprecation_threshold: float = 0.3,
    ):
        """
        Initialize the feedback processor.
        
        Args:
            repository: Skill repository
            skill_extractor: Optional skill extractor for refinement
            auto_refine: Whether to auto-refine skills
            refinement_threshold: Corrections before refinement
            deprecation_threshold: Success rate for deprecation
        """
        self.repository = repository
        self.skill_extractor = skill_extractor
        self.auto_refine = auto_refine
        self.refinement_threshold = refinement_threshold
        self.deprecation_threshold = deprecation_threshold
    
    def process_feedback(
        self,
        task_id: str,
        feedback_type: FeedbackType,
        user_id: Optional[str] = None,
        skill_id: Optional[str] = None,
        correction_text: Optional[str] = None,
        task_events: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[SkillFeedback]:
        """
        Process feedback for a task or skill.
        
        Args:
            task_id: The task ID
            feedback_type: Type of feedback
            user_id: Optional user ID
            skill_id: Optional skill ID (if known)
            correction_text: Optional correction details
            task_events: Optional task events for context
            
        Returns:
            The created feedback record
        """
        # Find associated skill if not provided
        if not skill_id:
            skill_id = self._find_skill_for_task(task_id)
        
        if not skill_id:
            logger.info(f"No skill found for task {task_id}, feedback not recorded")
            return None
        
        # Create feedback record
        feedback = SkillFeedback(
            id=generate_id(),
            skill_id=skill_id,
            task_id=task_id,
            user_id=user_id,
            feedback_type=feedback_type.value,
            correction_text=correction_text,
            created_at=now_epoch_ms(),
        )
        
        # Record in database
        self.repository.add_feedback(feedback)
        
        # Process based on feedback type
        if feedback_type == FeedbackType.THUMBS_UP:
            self._handle_thumbs_up(skill_id)
        elif feedback_type == FeedbackType.THUMBS_DOWN:
            self._handle_thumbs_down(skill_id)
        elif feedback_type == FeedbackType.CORRECTION:
            self._handle_correction(skill_id, correction_text)
        elif feedback_type == FeedbackType.EXPLICIT_SAVE:
            self._handle_explicit_save(task_id, user_id, task_events)
        elif feedback_type == FeedbackType.USER_EDIT:
            self._handle_user_edit(skill_id, correction_text)
        
        logger.info(f"Processed {feedback_type.value} feedback for skill {skill_id}")
        return feedback
    
    def _find_skill_for_task(self, task_id: str) -> Optional[str]:
        """Find a skill associated with a task."""
        skills = self.repository.get_skills_by_task(task_id)
        if skills:
            return skills[0].id
        return None
    
    def _handle_thumbs_up(self, skill_id: str) -> None:
        """Handle thumbs up feedback."""
        # Success count is updated in repository.add_feedback
        logger.debug(f"Thumbs up recorded for skill {skill_id}")
    
    def _handle_thumbs_down(self, skill_id: str) -> None:
        """Handle thumbs down feedback."""
        # Failure count is updated in repository.add_feedback
        # Check if skill should be deprecated
        skill = self.repository.get_skill(skill_id)
        if skill:
            success_rate = skill.get_success_rate()
            if success_rate is not None and success_rate < self.deprecation_threshold:
                total_uses = skill.success_count + skill.failure_count
                if total_uses >= 5:  # Minimum uses before deprecation
                    logger.warning(
                        f"Skill {skill_id} has low success rate ({success_rate:.2%}), "
                        "consider deprecation"
                    )
    
    def _handle_correction(
        self,
        skill_id: str,
        correction_text: Optional[str],
    ) -> None:
        """Handle correction feedback."""
        skill = self.repository.get_skill(skill_id)
        if not skill:
            return
        
        # Check if refinement is needed
        if self.auto_refine and skill.user_corrections >= self.refinement_threshold:
            self._trigger_refinement(skill, correction_text)
    
    def _handle_explicit_save(
        self,
        task_id: str,
        user_id: Optional[str],
        task_events: Optional[List[Dict[str, Any]]],
    ) -> None:
        """Handle explicit save request."""
        # This would trigger skill extraction for the task
        # Implementation depends on having task events available
        logger.info(f"Explicit save requested for task {task_id}")
    
    def _handle_user_edit(
        self,
        skill_id: str,
        edit_content: Optional[str],
    ) -> None:
        """Handle user edit to a skill."""
        if not edit_content:
            return
        
        skill = self.repository.get_skill(skill_id)
        if not skill:
            return
        
        # Update skill with user edits
        # This is a simplified implementation - in practice,
        # you'd parse the edit content and update specific fields
        skill.markdown_content = edit_content
        skill.updated_at = now_epoch_ms()
        self.repository.update_skill(skill)
        
        logger.info(f"User edit applied to skill {skill_id}")
    
    def _trigger_refinement(
        self,
        skill: Skill,
        correction_text: Optional[str],
    ) -> Optional[Skill]:
        """Trigger skill refinement based on feedback."""
        if not self.skill_extractor:
            logger.warning("Skill extractor not configured for refinement")
            return None
        
        # Get recent feedback for context
        feedback_list = self.repository.get_feedback_for_skill(skill.id, limit=10)
        
        # Build feedback summary
        feedback_summary = self._build_feedback_summary(feedback_list)
        
        # Refine skill
        refined = self.skill_extractor.refine_skill(
            skill=skill,
            feedback=feedback_summary,
            correction=correction_text,
        )
        
        if refined:
            # Save refined skill
            self.repository.create_skill(refined)
            logger.info(f"Created refined skill {refined.id} from {skill.id}")
            return refined
        
        return None
    
    def _build_feedback_summary(
        self,
        feedback_list: List[SkillFeedback],
    ) -> str:
        """Build a summary of feedback for refinement."""
        lines = ["Recent feedback:"]
        
        for fb in feedback_list:
            lines.append(f"- {fb.feedback_type}")
            if fb.correction_text:
                lines.append(f"  Correction: {fb.correction_text}")
        
        return "\n".join(lines)
    
    def process_task_completion(
        self,
        task_id: str,
        success: bool,
        skill_ids_used: Optional[List[str]] = None,
        user_id: Optional[str] = None,
    ) -> None:
        """
        Process task completion to update skill metrics.
        
        Called when a task completes to update success/failure
        counts for any skills that were used.
        
        Args:
            task_id: The task ID
            success: Whether the task succeeded
            skill_ids_used: Skills that were used in the task
            user_id: Optional user ID
        """
        if not skill_ids_used:
            return
        
        feedback_type = FeedbackType.THUMBS_UP if success else FeedbackType.THUMBS_DOWN
        
        for skill_id in skill_ids_used:
            self.process_feedback(
                task_id=task_id,
                feedback_type=feedback_type,
                user_id=user_id,
                skill_id=skill_id,
            )
    
    def get_skill_health(self, skill_id: str) -> Dict[str, Any]:
        """
        Get health metrics for a skill.
        
        Args:
            skill_id: The skill ID
            
        Returns:
            Dictionary with health metrics
        """
        skill = self.repository.get_skill(skill_id)
        if not skill:
            return {"error": "Skill not found"}
        
        success_rate = skill.get_success_rate()
        total_uses = skill.success_count + skill.failure_count
        
        # Determine health status
        if success_rate is None:
            status = "new"
        elif success_rate >= 0.8:
            status = "healthy"
        elif success_rate >= 0.5:
            status = "needs_attention"
        else:
            status = "unhealthy"
        
        # Check if refinement is recommended
        needs_refinement = skill.user_corrections >= self.refinement_threshold
        
        return {
            "skill_id": skill_id,
            "skill_name": skill.name,
            "status": status,
            "success_rate": success_rate,
            "total_uses": total_uses,
            "success_count": skill.success_count,
            "failure_count": skill.failure_count,
            "user_corrections": skill.user_corrections,
            "needs_refinement": needs_refinement,
            "last_feedback_at": skill.last_feedback_at,
        }
    
    def get_skills_needing_attention(
        self,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get skills that need attention based on feedback.
        
        Args:
            limit: Maximum skills to return
            
        Returns:
            List of skill health reports
        """
        # Get skills with low success rates or many corrections
        all_skills = self.repository.search_skills(limit=100)
        
        attention_needed = []
        for skill in all_skills:
            health = self.get_skill_health(skill.id)
            if health.get("status") in ("needs_attention", "unhealthy"):
                attention_needed.append(health)
            elif health.get("needs_refinement"):
                attention_needed.append(health)
        
        # Sort by urgency (unhealthy first, then by success rate)
        attention_needed.sort(
            key=lambda x: (
                0 if x.get("status") == "unhealthy" else 1,
                x.get("success_rate") or 1.0,
            )
        )
        
        return attention_needed[:limit]