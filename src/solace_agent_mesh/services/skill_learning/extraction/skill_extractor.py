"""
Skill extractor using LLM to extract reusable skills from task executions.

This module uses an LLM to analyze task execution data and extract
structured skill definitions that can be reused for similar tasks.
"""

import logging
import json
from typing import Optional, List, Dict, Any

from ..entities import (
    Skill,
    SkillType,
    SkillScope,
    AgentToolStep,
    AgentChainNode,
    StepType,
    generate_id,
    now_epoch_ms,
)
from .task_analyzer import TaskAnalysis, AgentExecution, ToolInvocation

logger = logging.getLogger(__name__)


# System prompt for skill extraction
EXTRACTION_SYSTEM_PROMPT = """You are a skill extraction agent. Your job is to analyze successful task executions and extract reusable skills (Standard Operating Procedures) that can help with similar tasks in the future.

A skill should capture:
1. WHAT the task accomplishes (clear, specific goal)
2. WHEN to use it (trigger conditions, context)
3. HOW to accomplish it (step-by-step procedure)
4. WHO is involved (which agents and tools)

Guidelines:
- Extract skills that are GENERALIZABLE - they should work for similar tasks, not just this exact task
- Use CLEAR, DESCRIPTIVE names in hyphen-case (e.g., "create-jira-ticket", "search-confluence-docs")
- Write descriptions that help identify WHEN to use the skill
- Capture the ESSENTIAL steps, not every minor detail
- Note which agents and tools are involved
- Identify any parameters that would need to be filled in for reuse

Output your analysis as a JSON object with the following structure:
{
    "should_extract": true/false,
    "skip_reason": "reason if should_extract is false",
    "skill": {
        "name": "skill-name-in-hyphen-case",
        "description": "When to use this skill - the trigger conditions",
        "summary": "Brief summary of what the skill does",
        "steps": [
            {
                "step_type": "tool_call|peer_delegation|llm_reasoning",
                "agent_name": "agent that performs this step",
                "tool_name": "tool used (if tool_call)",
                "action": "description of what to do",
                "parameters_template": {"param": "value or {{placeholder}}"},
                "sequence_number": 1
            }
        ],
        "involved_agents": ["agent1", "agent2"],
        "complexity_score": 1-100
    }
}"""


class SkillExtractor:
    """
    Extracts skills from task executions using LLM analysis.
    
    This extractor:
    1. Takes analyzed task data
    2. Formats it for LLM consumption
    3. Uses LLM to extract skill definition
    4. Validates and structures the result
    """
    
    def __init__(
        self,
        llm_client: Any = None,
        model: str = "gpt-4",
        temperature: float = 0.3,
        max_retries: int = 2,
    ):
        """
        Initialize the skill extractor.
        
        Args:
            llm_client: LLM client (OpenAI-compatible)
            model: Model to use for extraction
            temperature: Temperature for generation
            max_retries: Maximum retry attempts
        """
        self.llm_client = llm_client
        self.model = model
        self.temperature = temperature
        self.max_retries = max_retries
    
    def extract_skill(
        self,
        analysis: TaskAnalysis,
        owner_agent_name: Optional[str] = None,
        owner_user_id: Optional[str] = None,
        scope: SkillScope = SkillScope.AGENT,
    ) -> Optional[Skill]:
        """
        Extract a skill from a task analysis.
        
        Args:
            analysis: The task analysis
            owner_agent_name: Agent to own the skill
            owner_user_id: User to own the skill
            scope: Skill scope
            
        Returns:
            Extracted skill or None if extraction failed
        """
        if not analysis.is_learnable:
            logger.info(f"Task {analysis.task_id} not learnable: {analysis.skip_reason}")
            return None
        
        # Format task data for LLM
        task_context = self._format_task_for_llm(analysis)
        
        # Call LLM for extraction
        extraction_result = self._call_llm_for_extraction(task_context)
        
        if not extraction_result:
            logger.warning(f"Failed to extract skill from task {analysis.task_id}")
            return None
        
        # Parse and validate result
        skill = self._parse_extraction_result(
            extraction_result,
            analysis,
            owner_agent_name,
            owner_user_id,
            scope,
        )
        
        return skill
    
    def _format_task_for_llm(self, analysis: TaskAnalysis) -> str:
        """Format task analysis for LLM consumption."""
        lines = [
            "# Task Execution Analysis",
            "",
            f"## User Request",
            f"{analysis.user_request}",
            "",
            f"## Execution Summary",
            f"- Task ID: {analysis.task_id}",
            f"- Success: {analysis.success}",
            f"- Total Agents: {analysis.total_agents}",
            f"- Total Tool Calls: {analysis.total_tool_calls}",
            f"- Complexity Score: {analysis.complexity_score}",
            "",
            "## Agent Executions",
        ]
        
        for ae in analysis.agent_executions:
            lines.extend([
                "",
                f"### Agent: {ae.agent_name}",
                f"- Role: {ae.role}",
                f"- Tools Used: {', '.join(ae.tools_used) or 'None'}",
                f"- Delegated To: {', '.join(ae.delegated_to) or 'None'}",
            ])
            
            if ae.tool_invocations:
                lines.append("")
                lines.append("#### Tool Invocations:")
                for ti in ae.tool_invocations:
                    lines.append(f"  {ti.sequence_number + 1}. {ti.tool_name}")
                    if ti.parameters:
                        params_str = json.dumps(ti.parameters, indent=4)
                        lines.append(f"     Parameters: {params_str}")
                    lines.append(f"     Success: {ti.success}")
        
        return "\n".join(lines)
    
    def _call_llm_for_extraction(
        self,
        task_context: str,
    ) -> Optional[Dict[str, Any]]:
        """Call LLM to extract skill from task context."""
        if not self.llm_client:
            # Use mock extraction for testing
            return self._mock_extraction(task_context)
        
        for attempt in range(self.max_retries + 1):
            try:
                response = self.llm_client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                        {"role": "user", "content": task_context},
                    ],
                    temperature=self.temperature,
                    response_format={"type": "json_object"},
                )
                
                content = response.choices[0].message.content
                return json.loads(content)
                
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse LLM response (attempt {attempt + 1}): {e}")
            except Exception as e:
                logger.error(f"LLM call failed (attempt {attempt + 1}): {e}")
        
        return None
    
    def _mock_extraction(self, task_context: str) -> Dict[str, Any]:
        """Mock extraction for testing without LLM."""
        # Extract basic info from context
        lines = task_context.split("\n")
        user_request = ""
        agents = []
        tools = []
        
        for i, line in enumerate(lines):
            if line.startswith("## User Request") and i + 1 < len(lines):
                user_request = lines[i + 1].strip()
            if line.startswith("### Agent:"):
                agents.append(line.replace("### Agent:", "").strip())
            if line.startswith("- Tools Used:"):
                tool_list = line.replace("- Tools Used:", "").strip()
                if tool_list and tool_list != "None":
                    tools.extend([t.strip() for t in tool_list.split(",")])
        
        # Generate a simple skill name
        words = user_request.lower().split()[:3]
        skill_name = "-".join(words) if words else "extracted-skill"
        skill_name = "".join(c if c.isalnum() or c == "-" else "" for c in skill_name)
        
        return {
            "should_extract": True,
            "skill": {
                "name": skill_name,
                "description": f"Skill for: {user_request[:100]}",
                "summary": user_request[:200],
                "steps": [
                    {
                        "step_type": "tool_call",
                        "agent_name": agents[0] if agents else "unknown",
                        "tool_name": tools[0] if tools else "unknown",
                        "action": "Execute the task",
                        "parameters_template": {},
                        "sequence_number": 1,
                    }
                ],
                "involved_agents": agents,
                "complexity_score": 30,
            }
        }
    
    def _parse_extraction_result(
        self,
        result: Dict[str, Any],
        analysis: TaskAnalysis,
        owner_agent_name: Optional[str],
        owner_user_id: Optional[str],
        scope: SkillScope,
    ) -> Optional[Skill]:
        """Parse LLM extraction result into a Skill entity."""
        if not result.get("should_extract", True):
            logger.info(f"LLM decided not to extract: {result.get('skip_reason')}")
            return None
        
        skill_data = result.get("skill", {})
        
        if not skill_data.get("name") or not skill_data.get("description"):
            logger.warning("Invalid skill data: missing name or description")
            return None
        
        # Build tool steps
        tool_steps = []
        for step_data in skill_data.get("steps", []):
            step_type_str = step_data.get("step_type", "tool_call")
            try:
                step_type = StepType(step_type_str)
            except ValueError:
                step_type = StepType.TOOL_CALL
            
            tool_steps.append(AgentToolStep(
                id=generate_id(),
                step_type=step_type,
                agent_name=step_data.get("agent_name", "unknown"),
                tool_name=step_data.get("tool_name", "unknown"),
                action=step_data.get("action", ""),
                parameters_template=step_data.get("parameters_template"),
                sequence_number=step_data.get("sequence_number", len(tool_steps) + 1),
            ))
        
        # Build agent chain
        agent_chain = []
        for ae in analysis.agent_executions:
            agent_chain.append(AgentChainNode(
                agent_name=ae.agent_name,
                task_id=ae.task_id,
                parent_task_id=ae.parent_task_id,
                role=ae.role,
                tools_used=ae.tools_used,
                delegated_to=ae.delegated_to,
            ))
        
        # Create skill
        skill = Skill(
            id=generate_id(),
            name=skill_data["name"],
            description=skill_data["description"],
            type=SkillType.LEARNED,
            scope=scope,
            owner_agent_name=owner_agent_name,
            owner_user_id=owner_user_id,
            summary=skill_data.get("summary"),
            tool_steps=tool_steps,
            agent_chain=agent_chain,
            source_task_id=analysis.task_id,
            involved_agents=skill_data.get("involved_agents", []),
            complexity_score=skill_data.get("complexity_score", analysis.complexity_score),
            created_at=now_epoch_ms(),
            updated_at=now_epoch_ms(),
        )
        
        logger.info(f"Extracted skill: {skill.name} from task {analysis.task_id}")
        return skill
    
    def refine_skill(
        self,
        skill: Skill,
        feedback: str,
        correction: Optional[str] = None,
    ) -> Optional[Skill]:
        """
        Refine an existing skill based on feedback.
        
        Args:
            skill: The skill to refine
            feedback: Feedback about the skill
            correction: Optional correction text
            
        Returns:
            Refined skill or None if refinement failed
        """
        if not self.llm_client:
            logger.warning("LLM client not configured for refinement")
            return None
        
        # Format refinement prompt
        prompt = self._format_refinement_prompt(skill, feedback, correction)
        
        try:
            response = self.llm_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
                response_format={"type": "json_object"},
            )
            
            content = response.choices[0].message.content
            result = json.loads(content)
            
            if not result.get("should_extract", True):
                return None
            
            skill_data = result.get("skill", {})
            
            # Create refined skill
            refined = Skill(
                id=generate_id(),
                name=skill_data.get("name", skill.name),
                description=skill_data.get("description", skill.description),
                type=SkillType.LEARNED,
                scope=skill.scope,
                owner_agent_name=skill.owner_agent_name,
                owner_user_id=skill.owner_user_id,
                summary=skill_data.get("summary", skill.summary),
                tool_steps=skill.tool_steps,  # Keep original steps
                agent_chain=skill.agent_chain,
                source_task_id=skill.source_task_id,
                related_task_ids=skill.related_task_ids,
                involved_agents=skill_data.get("involved_agents", skill.involved_agents),
                complexity_score=skill_data.get("complexity_score", skill.complexity_score),
                parent_skill_id=skill.id,
                refinement_reason=feedback,
                created_at=now_epoch_ms(),
                updated_at=now_epoch_ms(),
            )
            
            return refined
            
        except Exception as e:
            logger.error(f"Skill refinement failed: {e}")
            return None
    
    def _format_refinement_prompt(
        self,
        skill: Skill,
        feedback: str,
        correction: Optional[str],
    ) -> str:
        """Format prompt for skill refinement."""
        lines = [
            "# Skill Refinement Request",
            "",
            "## Current Skill",
            f"Name: {skill.name}",
            f"Description: {skill.description}",
            f"Summary: {skill.summary or 'N/A'}",
            "",
            "## Steps",
        ]
        
        for step in skill.tool_steps:
            lines.append(f"  {step.sequence_number}. {step.action}")
            lines.append(f"     Agent: {step.agent_name}, Tool: {step.tool_name}")
        
        lines.extend([
            "",
            "## Feedback",
            feedback,
        ])
        
        if correction:
            lines.extend([
                "",
                "## Correction",
                correction,
            ])
        
        lines.extend([
            "",
            "Please refine this skill based on the feedback. Output the improved skill in the same JSON format.",
        ])
        
        return "\n".join(lines)