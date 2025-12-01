"""
SAM Skill Learning System.

A gateway-agnostic service that enables agents to learn from successful task executions
and improve future task planning through skill extraction, storage, and retrieval.

Main components:
- SkillLearningService: Standalone service runner
- SkillService: Main service for skill operations
- SkillRepository: Database access layer
- SkillExtractor: LLM-based skill extraction
- FeedbackProcessor: Human feedback handling
- EmbeddingService: Vector embeddings for search
- StaticSkillLoader: SKILL.md file loading
- SkillMessageHandler: Message broker integration

Usage:
    # Run as standalone service
    python -m solace_agent_mesh.services.skill_learning.main
    
    # Or import and use programmatically
    from solace_agent_mesh.services.skill_learning import SkillLearningService
    service = SkillLearningService(config)
    service.run_forever()
"""

from .entities import (
    Skill,
    SkillType,
    SkillScope,
    StepType,
    AgentToolStep,
    AgentChainNode,
    SkillShare,
    SkillFeedback,
    SkillUsage,
    LearningQueueItem,
)

from .repository import (
    SkillRepository,
    Base,
    SkillModel,
)

from .services import (
    SkillService,
    EmbeddingService,
    StaticSkillLoader,
    SkillSearchService,
)

from .extraction import (
    SkillExtractor,
    TaskAnalyzer,
)

from .feedback import (
    FeedbackProcessor,
)

from .broker import (
    SkillMessageHandler,
    SkillTopics,
    SolaceBrokerConfig,
    SolaceSkillLearningClient,
    MockSolaceClient,
    create_solace_client,
)

from .tools import (
    SkillReadTool,
    create_skill_read_tool,
)

from .integration import (
    AgentSkillInjector,
    PromptEnhancer,
    TaskContextAnalyzer,
)

from .config import SkillLearningConfig

# Import main service (lazy to avoid circular imports)
def _get_skill_learning_service():
    from .main import SkillLearningService
    return SkillLearningService

__all__ = [
    # Entities
    "Skill",
    "SkillType",
    "SkillScope",
    "StepType",
    "AgentToolStep",
    "AgentChainNode",
    "SkillShare",
    "SkillFeedback",
    "SkillUsage",
    "LearningQueueItem",
    # Repository
    "SkillRepository",
    "Base",
    "SkillModel",
    # Services
    "SkillService",
    "EmbeddingService",
    "StaticSkillLoader",
    "SkillSearchService",
    # Extraction
    "SkillExtractor",
    "TaskAnalyzer",
    # Feedback
    "FeedbackProcessor",
    # Broker
    "SkillMessageHandler",
    "SkillTopics",
    "SolaceBrokerConfig",
    "SolaceSkillLearningClient",
    "MockSolaceClient",
    "create_solace_client",
    # Tools
    "SkillReadTool",
    "create_skill_read_tool",
    # Integration
    "AgentSkillInjector",
    "PromptEnhancer",
    "TaskContextAnalyzer",
    # Config
    "SkillLearningConfig",
]