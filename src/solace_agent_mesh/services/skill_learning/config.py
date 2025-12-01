"""
Configuration for the SAM Skill Learning System.

This module defines the configuration options for:
- Database connection
- Embedding service
- Learning parameters
- Static skill directories
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class DatabaseConfig(BaseModel):
    """Database configuration."""
    
    url: str = Field(
        default="sqlite:///skills.db",
        description="SQLAlchemy database URL"
    )
    echo: bool = Field(
        default=False,
        description="Echo SQL statements"
    )
    pool_size: int = Field(
        default=5,
        description="Connection pool size"
    )


class EmbeddingConfig(BaseModel):
    """Embedding service configuration."""
    
    enabled: bool = Field(
        default=True,
        description="Enable embedding-based search"
    )
    provider: str = Field(
        default="openai",
        description="Embedding provider: openai, litellm"
    )
    model: str = Field(
        default="text-embedding-3-small",
        description="Embedding model name"
    )
    api_key: Optional[str] = Field(
        default=None,
        description="API key (uses env var if not set)"
    )
    api_base: Optional[str] = Field(
        default=None,
        description="API base URL for proxies"
    )


class LearningConfig(BaseModel):
    """Learning parameters configuration."""
    
    enabled: bool = Field(
        default=True,
        description="Enable automatic skill learning"
    )
    min_tool_calls: int = Field(
        default=1,
        description="Minimum tool calls for learnable task"
    )
    max_tool_calls: int = Field(
        default=50,
        description="Maximum tool calls for learnable task"
    )
    exclude_agents: List[str] = Field(
        default_factory=list,
        description="Agents to exclude from learning"
    )
    exclude_tools: List[str] = Field(
        default_factory=list,
        description="Tools to exclude from learning"
    )
    extraction_model: str = Field(
        default="gpt-4",
        description="LLM model for skill extraction"
    )
    extraction_temperature: float = Field(
        default=0.3,
        description="Temperature for extraction"
    )
    batch_size: int = Field(
        default=10,
        description="Learning queue batch size"
    )
    auto_generate_embeddings: bool = Field(
        default=True,
        description="Auto-generate embeddings for new skills"
    )


class FeedbackConfig(BaseModel):
    """Feedback processing configuration."""
    
    enabled: bool = Field(
        default=True,
        description="Enable feedback processing"
    )
    auto_refine: bool = Field(
        default=True,
        description="Auto-refine skills based on feedback"
    )
    refinement_threshold: int = Field(
        default=3,
        description="Corrections before refinement"
    )
    deprecation_threshold: float = Field(
        default=0.3,
        description="Success rate for deprecation warning"
    )


class StaticSkillsConfig(BaseModel):
    """Static skills configuration."""
    
    enabled: bool = Field(
        default=True,
        description="Enable static skill loading"
    )
    directory: str = Field(
        default="skills",
        description="Base directory for skill files"
    )
    watch_for_changes: bool = Field(
        default=False,
        description="Watch for file changes"
    )
    sync_to_database: bool = Field(
        default=True,
        description="Sync static skills to database"
    )


class BrokerConfig(BaseModel):
    """Message broker configuration."""
    
    enabled: bool = Field(
        default=True,
        description="Enable broker integration"
    )
    task_completion_subscription: str = Field(
        default="sam/+/task/completed",
        description="Topic for task completions"
    )
    feedback_subscription: str = Field(
        default="sam/+/feedback/+",
        description="Topic for feedback events"
    )
    skill_search_subscription: str = Field(
        default="sam/skills/search/request/+",
        description="Topic for skill search requests"
    )


class SearchConfig(BaseModel):
    """Search configuration."""
    
    vector_search_weight: float = Field(
        default=0.6,
        description="Weight for vector search results"
    )
    text_search_weight: float = Field(
        default=0.4,
        description="Weight for text search results"
    )
    default_limit: int = Field(
        default=10,
        description="Default search result limit"
    )
    min_similarity: float = Field(
        default=0.3,
        description="Minimum similarity threshold"
    )


class SkillLearningConfig(BaseModel):
    """
    Main configuration for the Skill Learning System.
    
    Example YAML configuration:
    ```yaml
    skill_learning:
      database:
        url: "postgresql://user:pass@localhost/skills"
      embedding:
        enabled: true
        provider: openai
        model: text-embedding-3-small
      learning:
        enabled: true
        min_tool_calls: 1
        max_tool_calls: 50
      feedback:
        enabled: true
        auto_refine: true
      static_skills:
        enabled: true
        directory: skills
      broker:
        enabled: true
      search:
        vector_search_weight: 0.6
        text_search_weight: 0.4
    ```
    """
    
    database: DatabaseConfig = Field(
        default_factory=DatabaseConfig,
        description="Database configuration"
    )
    embedding: EmbeddingConfig = Field(
        default_factory=EmbeddingConfig,
        description="Embedding service configuration"
    )
    learning: LearningConfig = Field(
        default_factory=LearningConfig,
        description="Learning parameters"
    )
    feedback: FeedbackConfig = Field(
        default_factory=FeedbackConfig,
        description="Feedback processing configuration"
    )
    static_skills: StaticSkillsConfig = Field(
        default_factory=StaticSkillsConfig,
        description="Static skills configuration"
    )
    broker: BrokerConfig = Field(
        default_factory=BrokerConfig,
        description="Message broker configuration"
    )
    search: SearchConfig = Field(
        default_factory=SearchConfig,
        description="Search configuration"
    )
    
    @classmethod
    def from_dict(cls, config_dict: dict) -> "SkillLearningConfig":
        """Create configuration from dictionary."""
        return cls(**config_dict)
    
    @classmethod
    def from_yaml_file(cls, path: str) -> "SkillLearningConfig":
        """Load configuration from YAML file."""
        import yaml
        with open(path, "r") as f:
            config_dict = yaml.safe_load(f)
        return cls.from_dict(config_dict.get("skill_learning", {}))