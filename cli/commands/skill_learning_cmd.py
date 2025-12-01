"""
CLI command for running the Skill Learning Service.

Usage:
    sam skill-learning [OPTIONS]
    
This command starts the standalone skill learning service that:
- Connects to Solace broker
- Listens for learning nomination events from agents
- Processes skill learning in the background
- Responds to skill search requests
"""

import logging
import os
import sys

import click
from dotenv import find_dotenv, load_dotenv


@click.command(name="skill-learning")
@click.option(
    "-c",
    "--config",
    "config_path",
    type=click.Path(exists=True),
    help="Path to YAML configuration file",
)
@click.option(
    "-l",
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    default="INFO",
    help="Logging level",
)
@click.option(
    "-u",
    "--system-env",
    is_flag=True,
    default=False,
    help="Use system environment variables only; do not load .env file.",
)
@click.option(
    "--mock-broker",
    is_flag=True,
    default=False,
    help="Use mock broker for testing (no actual broker connection)",
)
@click.option(
    "--passive-learning",
    is_flag=True,
    default=False,
    help="Enable passive learning from all task completions (not just nominated)",
)
def skill_learning(
    config_path: str,
    log_level: str,
    system_env: bool,
    mock_broker: bool,
    passive_learning: bool,
):
    """
    Run the Skill Learning Service.
    
    This service listens for task completion events from agents and learns
    skills from successful task executions. It runs as a standalone service
    alongside the main SAM application.
    
    The service subscribes to:
    - sam/+/task/nominate-for-learning (agent-nominated tasks)
    - sam/+/feedback/+ (human feedback)
    - sam/skills/search/request/+ (skill search requests)
    
    Example:
        sam skill-learning
        sam skill-learning --log-level DEBUG
        sam skill-learning --mock-broker  # For testing without broker
    """
    # Set up logging
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    log = logging.getLogger(__name__)
    
    # Load .env file unless --system-env is specified
    if not system_env:
        env_path = find_dotenv(usecwd=True)
        if env_path:
            load_dotenv(dotenv_path=env_path, override=True)
            log.info("Loaded environment variables from: %s", env_path)
        else:
            log.warning(
                "Warning: .env file not found. Proceeding with system environment variables."
            )
    else:
        log.info("Using system environment variables only (--system-env flag)")
    
    # Set environment variables from CLI options
    if mock_broker:
        os.environ["USE_MOCK_BROKER"] = "true"
        log.info("Mock broker enabled")
    
    if passive_learning:
        os.environ["PASSIVE_LEARNING_ENABLED"] = "true"
        log.info("Passive learning enabled")
    
    # Set config path if provided
    if config_path:
        os.environ["SKILL_LEARNING_CONFIG"] = config_path
        log.info("Using configuration file: %s", config_path)
    
    # Import and run the skill learning service
    try:
        from solace_agent_mesh.services.skill_learning.main import (
            SkillLearningService,
            load_config,
        )
    except ImportError as e:
        log.error(
            "Failed to import skill learning service: %s\n"
            "Make sure solace-agent-mesh is installed correctly.",
            e,
        )
        sys.exit(1)
    
    try:
        # Load configuration
        config = load_config(config_path)
        
        # Create and run service
        log.info("Starting Skill Learning Service...")
        service = SkillLearningService(config)
        service.run_forever()
        
    except KeyboardInterrupt:
        log.info("Received interrupt signal, shutting down...")
        sys.exit(0)
    except Exception as e:
        log.error("Error running skill learning service: %s", e)
        sys.exit(1)