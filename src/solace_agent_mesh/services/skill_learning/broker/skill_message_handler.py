"""
Message handler for skill learning system broker communication.

This module handles:
- Subscribing to task completion events
- Subscribing to feedback events
- Processing skill search requests
- Publishing skill updates
"""

import logging
import json
from typing import Optional, List, Dict, Any, Callable, TYPE_CHECKING
from dataclasses import dataclass

from .topics import SkillTopics
from ..entities import Skill, SkillScope
from ..services import SkillService
from ..extraction import TaskAnalyzer, SkillExtractor
from ..extraction.task_analyzer import TaskAnalysis
from ..feedback import FeedbackProcessor, FeedbackType
from ..repository import TaskEventRepository

logger = logging.getLogger(__name__)


@dataclass
class SkillSearchRequest:
    """Request for skill search."""
    request_id: str
    query: str
    agent_name: str
    user_id: Optional[str] = None
    scope: Optional[str] = None
    limit: int = 10


@dataclass
class SkillSearchResponse:
    """Response for skill search."""
    request_id: str
    skills: List[Dict[str, Any]]
    total_count: int


class SkillMessageHandler:
    """
    Handles message broker communication for skill learning.
    
    This handler:
    - Listens for learning nomination events (primary - agent-nominated)
    - Optionally listens for task completion events (passive learning)
    - Listens for feedback events
    - Responds to skill search requests
    - Publishes skill updates
    
    It is gateway-agnostic and communicates via Solace message broker.
    
    Learning Modes:
    - Agent-Nominated (default): Only tasks explicitly nominated by agents are learned
    - Passive Learning (optional): All successful tasks are considered for learning
    """
    
    def __init__(
        self,
        skill_service: SkillService,
        task_analyzer: TaskAnalyzer,
        skill_extractor: SkillExtractor,
        feedback_processor: FeedbackProcessor,
        publish_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        task_event_repository: Optional[TaskEventRepository] = None,
        passive_learning_enabled: bool = False,
    ):
        """
        Initialize the message handler.
        
        Args:
            skill_service: Skill service for operations
            task_analyzer: Task analyzer for extraction
            skill_extractor: Skill extractor
            feedback_processor: Feedback processor
            publish_callback: Callback for publishing messages
            task_event_repository: Repository for fetching task events
            passive_learning_enabled: If True, also learn from all task completions
                                     (not just nominated tasks). Default is False.
        """
        self.skill_service = skill_service
        self.task_analyzer = task_analyzer
        self.skill_extractor = skill_extractor
        self.feedback_processor = feedback_processor
        self.publish_callback = publish_callback
        self.task_event_repository = task_event_repository
        self.passive_learning_enabled = passive_learning_enabled
        
        # Cache for task events received via messages
        self._task_events_cache: Dict[str, List[Dict[str, Any]]] = {}
    
    def get_subscriptions(self) -> List[str]:
        """
        Get list of topics to subscribe to.
        
        Returns:
            List of topic subscription patterns
        """
        subscriptions = [
            # Primary: Agent-nominated learning
            SkillTopics.LEARNING_NOMINATION_SUBSCRIPTION,
            # Feedback events
            SkillTopics.FEEDBACK_SUBSCRIPTION,
            # Skill search requests
            SkillTopics.SKILL_SEARCH_REQUEST_SUBSCRIPTION,
        ]
        
        # Optional: Passive learning from all task completions
        if self.passive_learning_enabled:
            subscriptions.append(SkillTopics.TASK_COMPLETED_SUBSCRIPTION)
        
        return subscriptions
    
    def handle_message(
        self,
        topic: str,
        payload: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Handle an incoming message.
        
        Args:
            topic: The message topic
            payload: The message payload
            
        Returns:
            Optional response payload
        """
        try:
            # Determine message type from topic
            if "/task/nominate-for-learning" in topic:
                return self._handle_learning_nomination(topic, payload)
            elif "/task/completed" in topic:
                # Only process if passive learning is enabled
                if self.passive_learning_enabled:
                    return self._handle_task_completed(topic, payload)
                else:
                    logger.debug(f"Ignoring task completion (passive learning disabled): {topic}")
                    return None
            elif "/feedback/" in topic:
                return self._handle_feedback(topic, payload)
            elif "/skills/search/request/" in topic:
                return self._handle_skill_search(topic, payload)
            else:
                logger.warning(f"Unknown topic: {topic}")
                return None
        except Exception as e:
            logger.error(f"Error handling message on {topic}: {e}")
            return None
    
    def _handle_learning_nomination(
        self,
        topic: str,
        payload: Dict[str, Any],
    ) -> None:
        """
        Handle learning nomination event from an agent.
        
        This is the PRIMARY way tasks get nominated for learning.
        The agent explicitly decides this task is worth learning from.
        
        Expected payload:
        {
            "task_id": "task-123",
            "agent_name": "DataAnalystAgent",
            "user_id": "user-456",  # optional
            "events": [...],  # optional - task events
            "nomination_reason": "novel_approach",  # optional
            "metadata": {...}  # optional
        }
        """
        task_id = payload.get("task_id")
        agent_name = payload.get("agent_name")
        task_events = payload.get("events", [])
        user_id = payload.get("user_id")
        nomination_reason = payload.get("nomination_reason", "agent_nominated")
        
        if not task_id or not agent_name:
            logger.warning("Learning nomination missing required fields (task_id, agent_name)")
            return
        
        logger.info(f"Processing learning nomination: {task_id} from {agent_name} (reason: {nomination_reason})")
        
        # If events are provided in the message, cache them for later processing
        if task_events:
            self._task_events_cache[task_id] = task_events
            logger.debug(f"Cached {len(task_events)} events for task {task_id}")
        
        # Fetch events if not provided
        if not task_events:
            task_events = self._fetch_task_events(task_id)
        
        # Analyze the task (still apply basic learnability checks)
        analysis = self.task_analyzer.analyze_task(
            task_id=task_id,
            task_events=task_events,
            task_metadata=payload.get("metadata"),
        )
        
        # For nominated tasks, we're more lenient - only skip if truly not learnable
        if not analysis.is_learnable and analysis.skip_reason == "Task was not successful":
            logger.warning(f"Nominated task {task_id} was not successful - skipping")
            return
        
        # Queue for learning (agent nominated, so we trust their judgment)
        self.skill_service.enqueue_for_learning(
            task_id=task_id,
            agent_name=agent_name,
            user_id=user_id,
        )
        
        # Publish learning queued event
        if self.publish_callback:
            self.publish_callback(
                SkillTopics.LEARNING_QUEUED,
                {
                    "task_id": task_id,
                    "agent_name": agent_name,
                    "complexity_score": analysis.complexity_score,
                    "nomination_reason": nomination_reason,
                    "nominated": True,
                }
            )
    
    def _handle_task_completed(
        self,
        topic: str,
        payload: Dict[str, Any],
    ) -> None:
        """
        Handle task completion event (passive learning mode).
        
        This is only called if passive_learning_enabled is True.
        For most deployments, agent-nominated learning is preferred.
        """
        task_id = payload.get("task_id")
        agent_name = payload.get("agent_name")
        success = payload.get("success", True)
        task_events = payload.get("events", [])
        user_id = payload.get("user_id")
        
        if not task_id or not agent_name:
            logger.warning("Task completed event missing required fields")
            return
        
        logger.info(f"Processing task completion (passive learning): {task_id} from {agent_name}")
        
        # Only learn from successful tasks
        if not success:
            logger.debug(f"Skipping failed task {task_id}")
            return
        
        # If events are provided in the message, cache them for later processing
        if task_events:
            self._task_events_cache[task_id] = task_events
            logger.debug(f"Cached {len(task_events)} events for task {task_id}")
        
        # Analyze the task
        # If no events in message, try to fetch from repository
        if not task_events and self.task_event_repository:
            task_events = self._fetch_task_events(task_id)
        
        analysis = self.task_analyzer.analyze_task(
            task_id=task_id,
            task_events=task_events,
            task_metadata=payload.get("metadata"),
        )
        
        if not analysis.is_learnable:
            logger.debug(f"Task {task_id} not learnable: {analysis.skip_reason}")
            return
        
        # Queue for learning
        self.skill_service.enqueue_for_learning(
            task_id=task_id,
            agent_name=agent_name,
            user_id=user_id,
        )
        
        # Publish learning queued event
        if self.publish_callback:
            self.publish_callback(
                SkillTopics.LEARNING_QUEUED,
                {
                    "task_id": task_id,
                    "agent_name": agent_name,
                    "complexity_score": analysis.complexity_score,
                    "nominated": False,  # Passive learning, not nominated
                }
            )
    
    def _handle_feedback(
        self,
        topic: str,
        payload: Dict[str, Any],
    ) -> None:
        """Handle feedback event."""
        task_id = payload.get("task_id")
        feedback_type_str = payload.get("feedback_type")
        user_id = payload.get("user_id")
        skill_id = payload.get("skill_id")
        correction_text = payload.get("correction_text")
        
        if not task_id or not feedback_type_str:
            logger.warning("Feedback event missing required fields")
            return
        
        try:
            feedback_type = FeedbackType(feedback_type_str)
        except ValueError:
            logger.warning(f"Unknown feedback type: {feedback_type_str}")
            return
        
        logger.info(f"Processing feedback: {feedback_type.value} for task {task_id}")
        
        self.feedback_processor.process_feedback(
            task_id=task_id,
            feedback_type=feedback_type,
            user_id=user_id,
            skill_id=skill_id,
            correction_text=correction_text,
        )
    
    def _handle_skill_search(
        self,
        topic: str,
        payload: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Handle skill search request."""
        request_id = payload.get("request_id")
        query = payload.get("query", "")
        agent_name = payload.get("agent_name")
        user_id = payload.get("user_id")
        scope_str = payload.get("scope")
        limit = payload.get("limit", 10)
        
        if not request_id or not agent_name:
            logger.warning("Skill search request missing required fields")
            return None
        
        logger.info(f"Processing skill search: {request_id} from {agent_name}")
        
        # Parse scope
        scope = None
        if scope_str:
            try:
                scope = SkillScope(scope_str)
            except ValueError:
                pass
        
        # Search for skills
        results = self.skill_service.search_skills(
            query=query,
            agent_name=agent_name,
            user_id=user_id,
            scope=scope,
            limit=limit,
        )
        
        # Build response
        skills = [
            skill.to_summary_dict()
            for skill, _ in results
        ]
        
        response = {
            "request_id": request_id,
            "skills": skills,
            "total_count": len(skills),
        }
        
        # Publish response
        if self.publish_callback:
            response_topic = SkillTopics.skill_search_response(request_id)
            self.publish_callback(response_topic, response)
        
        return response
    
    def process_learning_queue(self, batch_size: int = 10) -> int:
        """
        Process items in the learning queue.
        
        This method:
        1. Fetches pending learning items
        2. Analyzes task events
        3. Searches for similar existing skills
        4. Either creates a new skill OR updates an existing one
        
        Args:
            batch_size: Number of items to process
            
        Returns:
            Number of items processed
        """
        items = self.skill_service.get_pending_learning_items(limit=batch_size)
        processed = 0
        
        for item in items:
            try:
                # Update status to processing
                self.skill_service.update_learning_item_status(
                    item.id, "processing"
                )
                
                # Get task events
                task_events = self._fetch_task_events(item.task_id)
                
                if not task_events:
                    self.skill_service.update_learning_item_status(
                        item.id, "failed", "Task events not found"
                    )
                    continue
                
                # Analyze task
                analysis = self.task_analyzer.analyze_task(
                    task_id=item.task_id,
                    task_events=task_events,
                )
                
                if not analysis.is_learnable:
                    self.skill_service.update_learning_item_status(
                        item.id, "completed"
                    )
                    continue
                
                # Search for similar existing skills BEFORE extraction
                similar_skills = self._find_similar_skills(
                    analysis=analysis,
                    agent_name=item.agent_name,
                )
                
                if similar_skills:
                    # Found similar skill(s) - decide whether to update or skip
                    best_match, similarity_score = similar_skills[0]
                    
                    if similarity_score > 0.9:
                        # Very similar - likely the same skill, just add this task as a related task
                        logger.info(
                            f"Found highly similar skill '{best_match.name}' (score={similarity_score:.2f}) "
                            f"for task {item.task_id}, adding as related task"
                        )
                        self._add_related_task_to_skill(best_match, item.task_id)
                        self.skill_service.update_learning_item_status(
                            item.id, "completed", f"Added to existing skill: {best_match.name}"
                        )
                        processed += 1
                        continue
                    
                    elif similarity_score > 0.7:
                        # Moderately similar - could be an improvement, try to merge/update
                        logger.info(
                            f"Found similar skill '{best_match.name}' (score={similarity_score:.2f}) "
                            f"for task {item.task_id}, attempting to improve it"
                        )
                        updated_skill = self._try_improve_skill(
                            existing_skill=best_match,
                            analysis=analysis,
                            agent_name=item.agent_name,
                        )
                        if updated_skill:
                            self._publish_skill_updated(updated_skill, item.agent_name)
                            self.skill_service.update_learning_item_status(
                                item.id, "completed", f"Improved existing skill: {best_match.name}"
                            )
                            processed += 1
                            continue
                        # If improvement failed, fall through to create new skill
                
                # No similar skill found (or similarity too low) - extract new skill
                skill = self.skill_extractor.extract_skill(
                    analysis=analysis,
                    owner_agent_name=item.agent_name,
                    scope=SkillScope.AGENT,
                )
                
                if skill:
                    # Double-check for exact name match (in case extraction produced same name)
                    existing_skill = self.skill_service.repository.get_skill_by_name(
                        name=skill.name,
                        scope=SkillScope.AGENT,
                        owner_agent_name=item.agent_name,
                    )
                    
                    if existing_skill:
                        logger.info(
                            f"Skill '{skill.name}' already exists for agent {item.agent_name}, "
                            f"adding task as related"
                        )
                        self._add_related_task_to_skill(existing_skill, item.task_id)
                        self.skill_service.update_learning_item_status(
                            item.id, "completed", f"Added to existing skill: {existing_skill.name}"
                        )
                        processed += 1
                        continue
                    
                    # Save new skill
                    created_skill = self.skill_service.repository.create_skill(skill)
                    
                    # Publish skill created event
                    if self.publish_callback:
                        self.publish_callback(
                            SkillTopics.SKILL_CREATED,
                            {
                                "skill_id": created_skill.id,
                                "skill_name": created_skill.name,
                                "agent_name": item.agent_name,
                            }
                        )
                        
                        # Publish to agent-specific topic
                        self.publish_callback(
                            SkillTopics.agent_skills_learned(item.agent_name),
                            created_skill.to_summary_dict()
                        )
                    
                    logger.info(f"Created new skill '{created_skill.name}' for agent {item.agent_name}")
                
                # Update status to completed
                self.skill_service.update_learning_item_status(
                    item.id, "completed"
                )
                
                # Publish learning completed event
                if self.publish_callback:
                    self.publish_callback(
                        SkillTopics.LEARNING_COMPLETED,
                        {
                            "task_id": item.task_id,
                            "skill_id": skill.id if skill else None,
                            "agent_name": item.agent_name,
                            "action": "created" if skill else "skipped",
                        }
                    )
                
                processed += 1
                
            except Exception as e:
                logger.error(f"Error processing learning item {item.id}: {e}")
                self.skill_service.update_learning_item_status(
                    item.id, "failed", str(e)
                )
                
                # Publish learning failed event
                if self.publish_callback:
                    self.publish_callback(
                        SkillTopics.LEARNING_FAILED,
                        {
                            "task_id": item.task_id,
                            "agent_name": item.agent_name,
                            "error": str(e),
                        }
                    )
        
        return processed
    
    def _find_similar_skills(
        self,
        analysis: "TaskAnalysis",
        agent_name: str,
        threshold: float = 0.5,
    ) -> List[tuple]:
        """
        Find existing skills that are similar to the task being learned.
        
        Uses semantic search based on the user request and task description.
        
        Args:
            analysis: The task analysis
            agent_name: The agent name to search within
            threshold: Minimum similarity threshold
            
        Returns:
            List of (skill, similarity_score) tuples, sorted by score descending
        """
        if not analysis.user_request:
            return []
        
        try:
            # Search for similar skills using the user request as query
            results = self.skill_service.search_skills(
                query=analysis.user_request,
                agent_name=agent_name,
                scope=SkillScope.AGENT,
                limit=5,
            )
            
            # Filter by threshold and return with scores
            similar = [
                (skill, score)
                for skill, score in results
                if score >= threshold
            ]
            
            return similar
            
        except Exception as e:
            logger.warning(f"Error searching for similar skills: {e}")
            return []
    
    def _add_related_task_to_skill(self, skill: Skill, task_id: str) -> None:
        """
        Add a task ID to a skill's related tasks list.
        
        This tracks which tasks have contributed to or used this skill.
        
        Args:
            skill: The skill to update
            task_id: The task ID to add
        """
        try:
            # Get current related tasks
            related_tasks = skill.related_task_ids or []
            
            # Add new task if not already present
            if task_id not in related_tasks:
                related_tasks.append(task_id)
                
                # Update skill in repository
                self.skill_service.repository.update_skill(
                    skill_id=skill.id,
                    updates={
                        "related_task_ids": related_tasks,
                        "usage_count": (skill.usage_count or 0) + 1,
                    }
                )
                
                logger.debug(f"Added task {task_id} to skill {skill.name} related tasks")
                
        except Exception as e:
            logger.warning(f"Failed to add related task to skill: {e}")
    
    def _try_improve_skill(
        self,
        existing_skill: Skill,
        analysis: "TaskAnalysis",
        agent_name: str,
    ) -> Optional[Skill]:
        """
        Try to improve an existing skill based on a new task execution.
        
        This is called when a task is similar but not identical to an existing skill.
        The improvement might include:
        - Adding new steps discovered in this execution
        - Updating parameters based on new examples
        - Improving the description
        
        Args:
            existing_skill: The existing skill to improve
            analysis: The new task analysis
            agent_name: The agent name
            
        Returns:
            Updated skill or None if improvement not possible
        """
        try:
            # Use the skill extractor's refine method
            # Build feedback from the new task
            feedback = (
                f"A similar task was executed successfully. "
                f"User request: {analysis.user_request}. "
                f"Tools used: {', '.join(analysis.tools_used)}. "
                f"Consider if this execution reveals improvements to the skill."
            )
            
            refined_skill = self.skill_extractor.refine_skill(
                skill=existing_skill,
                feedback=feedback,
            )
            
            if refined_skill:
                # Update the existing skill rather than creating a new one
                self.skill_service.repository.update_skill(
                    skill_id=existing_skill.id,
                    updates={
                        "description": refined_skill.description,
                        "summary": refined_skill.summary,
                        "related_task_ids": (existing_skill.related_task_ids or []) + [analysis.task_id],
                        "usage_count": (existing_skill.usage_count or 0) + 1,
                    }
                )
                
                logger.info(f"Improved skill '{existing_skill.name}' based on task {analysis.task_id}")
                return existing_skill
            
            return None
            
        except Exception as e:
            logger.warning(f"Failed to improve skill: {e}")
            return None
    
    def _publish_skill_updated(self, skill: Skill, agent_name: str) -> None:
        """Publish skill updated event."""
        if self.publish_callback:
            self.publish_callback(
                SkillTopics.SKILL_UPDATED,
                {
                    "skill_id": skill.id,
                    "skill_name": skill.name,
                    "agent_name": agent_name,
                }
            )
    
    def _fetch_task_events(self, task_id: str) -> List[Dict[str, Any]]:
        """
        Fetch task events from cache or repository.
        
        First checks the in-memory cache (populated from task completion messages),
        then falls back to the task event repository if configured.
        
        Args:
            task_id: The task ID to fetch events for
            
        Returns:
            List of task event dictionaries
        """
        # Check cache first
        if task_id in self._task_events_cache:
            events = self._task_events_cache.pop(task_id)  # Remove from cache after use
            logger.debug(f"Retrieved {len(events)} cached events for task {task_id}")
            return events
        
        # Try repository if available
        if self.task_event_repository:
            try:
                # Get events for the task and all related tasks in the hierarchy
                events = self.task_event_repository.get_related_task_events(task_id)
                logger.debug(f"Fetched {len(events)} events from repository for task {task_id}")
                return events
            except Exception as e:
                logger.error(f"Error fetching task events from repository: {e}")
                return []
        
        logger.warning(f"No task events available for {task_id} (no cache or repository)")
        return []
    
    def publish_skill_summaries_for_agent(
        self,
        agent_name: str,
        user_id: Optional[str] = None,
    ) -> None:
        """
        Publish skill summaries for an agent.
        
        Args:
            agent_name: The agent name
            user_id: Optional user ID
        """
        skills = self.skill_service.get_skills_for_agent(
            agent_name=agent_name,
            user_id=user_id,
        )
        
        summaries = [skill.to_summary_dict() for skill in skills]
        
        if self.publish_callback:
            self.publish_callback(
                SkillTopics.agent_skills_learned(agent_name),
                {
                    "agent_name": agent_name,
                    "skills": summaries,
                    "count": len(summaries),
                }
            )