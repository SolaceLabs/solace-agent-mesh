"""
Skill Learning Initialization Function for Agents.

This module provides an init function that sets up the database session factory
required for skill learning features including semantic search.
"""

import logging
import os
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from ..sac.component import SamAgentComponent

log = logging.getLogger(__name__)


class SkillLearningInitConfig(BaseModel):
    """Configuration for skill learning initialization."""
    
    database_url: Optional[str] = Field(
        default=None,
        description="Database URL for skill learning. If not provided, uses SKILL_LEARNING_DATABASE_URL env var or falls back to ORCHESTRATOR_DATABASE_URL."
    )


def init_skill_learning(
    host_component: "SamAgentComponent",
    config: Optional[SkillLearningInitConfig] = None,
) -> None:
    """
    Initialize skill learning for an agent.
    
    This function sets up the database session factory required for:
    - Semantic search of relevant skills
    - Skill retrieval and injection into prompts
    - Skill learning nominations
    
    Args:
        host_component: The host component instance
        config: Optional configuration for skill learning (can be dict or Pydantic model)
    """
    log_identifier = f"[SkillLearningInit:{host_component.agent_name}]"
    
    # Check if skill learning is enabled
    skill_config = host_component.get_config("skill_learning", {})
    if not skill_config.get("enabled", False):
        log.info(
            "%s Skill learning not enabled, skipping database setup.",
            log_identifier,
        )
        return
    
    # Handle config being either a dict or Pydantic model
    database_url = None
    if config:
        if isinstance(config, dict):
            database_url = config.get("database_url")
        elif hasattr(config, "database_url"):
            database_url = config.database_url
    
    # Determine database URL from config or environment
    if database_url:
        pass  # Use the provided database_url
    else:
        # Try environment variables
        database_url = os.environ.get(
            "SKILL_LEARNING_DATABASE_URL",
            os.environ.get("ORCHESTRATOR_DATABASE_URL", "sqlite:///skill_learning.db")
        )
    
    log.info(
        "%s Setting up skill learning database connection...",
        log_identifier,
    )
    
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        
        # Create engine with appropriate settings
        engine_kwargs = {}
        if database_url.startswith("sqlite"):
            engine_kwargs["connect_args"] = {"check_same_thread": False}
        
        engine = create_engine(database_url, **engine_kwargs)
        
        # Create session factory
        session_factory = sessionmaker(bind=engine)
        
        # Store in agent state
        host_component.set_agent_specific_state("db_session_factory", session_factory)
        host_component.set_agent_specific_state("db_engine", engine)
        
        log.info(
            "%s Skill learning database session factory initialized successfully.",
            log_identifier,
        )
        
        # Initialize database tables if needed
        try:
            # Import Base which includes both legacy and versioned models
            from ...services.skill_learning.repository.models import Base
            # Also import versioned models to ensure they're registered with Base
            from ...services.skill_learning.repository.versioned_models import (
                SkillGroupModel,
                SkillVersionModel,
                SkillGroupUserModel,
            )
            Base.metadata.create_all(engine)
            log.info(
                "%s Skill learning database tables created/verified (including versioned tables).",
                log_identifier,
            )
        except ImportError as e:
            log.warning(
                "%s Could not import skill learning models to create tables: %s",
                log_identifier,
                e,
            )
        except Exception as e:
            log.warning(
                "%s Error creating skill learning tables (may already exist): %s",
                log_identifier,
                e,
            )
            
    except ImportError as e:
        log.error(
            "%s SQLAlchemy not available. Install with: pip install sqlalchemy. Error: %s",
            log_identifier,
            e,
        )
    except Exception as e:
        log.error(
            "%s Failed to initialize skill learning database: %s",
            log_identifier,
            e,
        )


def cleanup_skill_learning(host_component: "SamAgentComponent") -> None:
    """
    Cleanup skill learning resources.
    
    Args:
        host_component: The host component instance
    """
    log_identifier = f"[SkillLearningCleanup:{host_component.agent_name}]"
    
    engine = host_component.get_agent_specific_state("db_engine")
    if engine:
        try:
            engine.dispose()
            log.info(
                "%s Skill learning database engine disposed.",
                log_identifier,
            )
        except Exception as e:
            log.warning(
                "%s Error disposing skill learning database engine: %s",
                log_identifier,
                e,
            )