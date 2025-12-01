"""
Standalone Skill Learning Service.

This is the main entry point for the skill learning service that:
- Connects to Solace broker
- Subscribes to task completion and feedback events
- Processes skill learning in the background
- Responds to skill search requests

Usage:
    python -m solace_agent_mesh.services.skill_learning.main [--config config.yaml]
    
    # Run with mock broker for testing (no actual broker connection)
    USE_MOCK_BROKER=true python -m solace_agent_mesh.services.skill_learning.main
    
Environment Variables (uses same vars as SAM):
    SOLACE_BROKER_URL: Solace broker URL (default: ws://localhost:8008)
    SOLACE_BROKER_VPN: Solace VPN name (default: default)
    SOLACE_BROKER_USERNAME: Solace username (default: default)
    SOLACE_BROKER_PASSWORD: Solace password (default: default)
    SOLACE_DEV_MODE: Enable dev mode (default: false)
    NAMESPACE: SAM namespace (default: default_namespace/)
    SKILL_LEARNING_QUEUE: Queue name (default: sam/skill-learning/queue)
    SKILLS_DATABASE_URL: Skills database URL (default: sqlite:///data/skills.db)
    DATABASE_URL: Fallback database URL if SKILLS_DATABASE_URL not set
    OPENAI_API_KEY: OpenAI API key for embeddings
    LEARNING_BATCH_SIZE: Learning queue batch size (default: 10)
    LEARNING_INTERVAL_SECONDS: Learning queue processing interval (default: 60)
    USE_MOCK_BROKER: Use mock broker for testing (default: false)
"""

import argparse
import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Any

# Load .env file from project root if it exists
try:
    from dotenv import load_dotenv
    # Try to find .env in current directory or parent directories
    env_path = Path(".env")
    if not env_path.exists():
        # Try project root (assuming we're in src/solace_agent_mesh/services/skill_learning)
        project_root = Path(__file__).parent.parent.parent.parent.parent
        env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded environment from: {env_path}")
except ImportError:
    pass  # python-dotenv not installed, rely on environment variables

from .config import SkillLearningConfig
from .broker.solace_client import (
    SolaceBrokerConfig,
    create_solace_client,
    SolaceSkillLearningClient,
    MockSolaceClient,
)
from .broker.skill_message_handler import SkillMessageHandler
from .broker.topics import SkillTopics
from .services import SkillService, EmbeddingService, StaticSkillLoader
from .repository import SkillRepository, TaskEventRepository
from .extraction import TaskAnalyzer, SkillExtractor
from .feedback import FeedbackProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class SkillLearningService:
    """
    Main skill learning service.
    
    This service:
    - Connects to Solace broker
    - Listens for task completions and feedback
    - Processes the learning queue periodically
    - Responds to skill search requests
    """
    
    def __init__(self, config: SkillLearningConfig):
        """
        Initialize the skill learning service.
        
        Args:
            config: Service configuration
        """
        self.config = config
        self._running = False
        self._stop_event = threading.Event()
        self._learning_thread: Optional[threading.Thread] = None
        
        # Initialize components
        self._init_components()
    
    def _init_components(self):
        """Initialize all service components."""
        logger.info("Initializing skill learning service components...")
        
        # Initialize skill repository
        logger.info(f"Connecting to skill database: {self.config.database.url}")
        self.repository = SkillRepository(
            database_url=self.config.database.url,
        )
        
        # Create tables if they don't exist
        self.repository.create_tables()
        
        # Initialize task event repository if gateway database is configured
        self.task_event_repository = None
        gateway_db_url = os.environ.get("GATEWAY_DATABASE_URL")
        if gateway_db_url:
            logger.info(f"Connecting to gateway database for task events: {gateway_db_url}")
            try:
                self.task_event_repository = TaskEventRepository(
                    database_url=gateway_db_url,
                )
                logger.info("Task event repository initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize task event repository: {e}")
        else:
            logger.info("GATEWAY_DATABASE_URL not set - task events will be read from messages only")
        
        # Initialize embedding service if enabled
        self.embedding_service = None
        if self.config.embedding.enabled:
            logger.info(f"Initializing embedding service: {self.config.embedding.provider}")
            try:
                self.embedding_service = EmbeddingService(
                    provider_type=self.config.embedding.provider,
                    model=self.config.embedding.model,
                    api_key=self.config.embedding.api_key,
                    base_url=self.config.embedding.api_base,
                )
            except Exception as e:
                logger.warning(f"Failed to initialize embedding service: {e}")
                self.embedding_service = None
        
        # Initialize static skill loader if enabled
        self.static_loader = None
        if self.config.static_skills.enabled:
            logger.info(f"Initializing static skill loader: {self.config.static_skills.directory}")
            self.static_loader = StaticSkillLoader(
                skills_directory=self.config.static_skills.directory,
                watch_for_changes=self.config.static_skills.watch_for_changes,
            )
        
        # Initialize skill service
        self.skill_service = SkillService(
            repository=self.repository,
            embedding_service=self.embedding_service,
            static_loader=self.static_loader,
            auto_generate_embeddings=self.config.learning.auto_generate_embeddings,
        )
        
        # Initialize task analyzer
        self.task_analyzer = TaskAnalyzer(
            min_tool_calls=self.config.learning.min_tool_calls,
            max_tool_calls=self.config.learning.max_tool_calls,
            exclude_agents=self.config.learning.exclude_agents,
            exclude_tools=self.config.learning.exclude_tools,
        )
        
        # Initialize skill extractor (LLM client will be None for now - mock extraction)
        self.skill_extractor = SkillExtractor(
            llm_client=None,  # Will use mock extraction
            model=self.config.learning.extraction_model,
            temperature=self.config.learning.extraction_temperature,
        )
        
        # Initialize feedback processor
        self.feedback_processor = FeedbackProcessor(
            repository=self.repository,
            skill_extractor=self.skill_extractor,
            auto_refine=self.config.feedback.auto_refine,
            refinement_threshold=self.config.feedback.refinement_threshold,
            deprecation_threshold=self.config.feedback.deprecation_threshold,
        )
        
        # Initialize message handler
        # By default, only agent-nominated tasks are learned
        # Set PASSIVE_LEARNING_ENABLED=true to also learn from all task completions
        passive_learning = os.environ.get("PASSIVE_LEARNING_ENABLED", "false").lower() == "true"
        if passive_learning:
            logger.info("Passive learning ENABLED - will learn from all task completions")
        else:
            logger.info("Passive learning DISABLED - only agent-nominated tasks will be learned")
        
        self.message_handler = SkillMessageHandler(
            skill_service=self.skill_service,
            task_analyzer=self.task_analyzer,
            skill_extractor=self.skill_extractor,
            feedback_processor=self.feedback_processor,
            publish_callback=self._publish_message,
            task_event_repository=self.task_event_repository,
            passive_learning_enabled=passive_learning,
        )
        
        # Initialize Solace client (will be set up in start())
        self.solace_client: Optional[SolaceSkillLearningClient | MockSolaceClient] = None
        
        logger.info("Skill learning service components initialized")
    
    def _publish_message(self, topic: str, payload: Dict[str, Any]):
        """Publish a message to the broker."""
        if self.solace_client:
            self.solace_client.publish(topic, payload)
    
    def start(self):
        """Start the skill learning service."""
        if self._running:
            logger.warning("Service already running")
            return
        
        logger.info("Starting skill learning service...")
        
        # Load static skills if configured
        if self.config.static_skills.enabled and self.config.static_skills.sync_to_database:
            logger.info("Syncing static skills to database...")
            count = self.skill_service.sync_static_skills_to_database()
            logger.info(f"Synced {count} static skills")
        
        # Set up broker connection if enabled
        if self.config.broker.enabled:
            self._setup_broker()
        else:
            logger.info("Broker integration disabled")
        
        # Start learning queue processor
        if self.config.learning.enabled:
            self._start_learning_processor()
        else:
            logger.info("Learning disabled")
        
        self._running = True
        logger.info("Skill learning service started")
    
    def _setup_broker(self):
        """Set up the Solace broker connection."""
        logger.info("Setting up Solace broker connection...")
        
        # Get broker config from environment
        broker_config = SolaceBrokerConfig.from_env()
        
        # Determine if we should use mock client
        use_mock = os.environ.get("USE_MOCK_BROKER", "false").lower() == "true"
        
        # Create client
        self.solace_client = create_solace_client(
            config=broker_config,
            message_callback=self.message_handler.handle_message,
            use_mock=use_mock,
        )
        
        # Connect to broker
        if not self.solace_client.connect():
            raise RuntimeError("Failed to connect to Solace broker")
        
        # Start publisher
        if not self.solace_client.start_publishing():
            raise RuntimeError("Failed to start message publisher")
        
        # Get subscriptions from message handler
        subscriptions = self.message_handler.get_subscriptions()
        
        # Start receiving messages
        if not self.solace_client.start_receiving(subscriptions):
            raise RuntimeError("Failed to start message receiver")
        
        logger.info("Solace broker connection established")
    
    def _start_learning_processor(self):
        """Start the background learning queue processor."""
        logger.info("Starting learning queue processor...")
        
        self._learning_thread = threading.Thread(
            target=self._learning_processor_loop,
            name="LearningProcessor",
            daemon=True,
        )
        self._learning_thread.start()
        
        logger.info("Learning queue processor started")
    
    def _learning_processor_loop(self):
        """Background loop for processing the learning queue."""
        interval = int(os.environ.get("LEARNING_INTERVAL_SECONDS", "60"))
        batch_size = self.config.learning.batch_size
        
        logger.info(f"Learning processor running (interval={interval}s, batch_size={batch_size})")
        
        while not self._stop_event.is_set():
            try:
                # Process learning queue
                processed = self.message_handler.process_learning_queue(batch_size)
                
                if processed > 0:
                    logger.info(f"Processed {processed} learning queue items")
                
            except Exception as e:
                logger.error(f"Error in learning processor: {e}")
            
            # Wait for next interval or stop signal
            self._stop_event.wait(interval)
        
        logger.info("Learning processor stopped")
    
    def stop(self):
        """Stop the skill learning service."""
        if not self._running:
            return
        
        logger.info("Stopping skill learning service...")
        
        # Signal stop
        self._stop_event.set()
        
        # Stop Solace client
        if self.solace_client:
            self.solace_client.stop()
        
        # Wait for learning thread
        if self._learning_thread and self._learning_thread.is_alive():
            self._learning_thread.join(timeout=10)
        
        # Close task event repository
        if self.task_event_repository:
            self.task_event_repository.close()
        
        self._running = False
        logger.info("Skill learning service stopped")
    
    def run_forever(self):
        """Run the service until interrupted."""
        self.start()
        
        # Set up signal handlers
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            self.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        logger.info("Service running. Press Ctrl+C to stop.")
        
        # Keep main thread alive
        while self._running:
            time.sleep(1)


def load_config(config_path: Optional[str] = None) -> SkillLearningConfig:
    """
    Load configuration from file or environment.
    
    Args:
        config_path: Optional path to YAML config file
        
    Returns:
        Configuration object
    """
    if config_path and os.path.exists(config_path):
        logger.info(f"Loading configuration from {config_path}")
        return SkillLearningConfig.from_yaml_file(config_path)
    
    # Build config from environment variables
    logger.info("Building configuration from environment variables")
    
    # Use SKILLS_DATABASE_URL for consistency with gateway config
    # Falls back to DATABASE_URL for backward compatibility
    db_url = os.environ.get("SKILLS_DATABASE_URL") or os.environ.get("DATABASE_URL", "sqlite:///data/skills.db")
    
    return SkillLearningConfig(
        database={"url": db_url},
        embedding={
            "enabled": os.environ.get("EMBEDDING_ENABLED", "true").lower() == "true",
            "provider": os.environ.get("EMBEDDING_PROVIDER", "openai"),
            "model": os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small"),
            "api_key": os.environ.get("OPENAI_API_KEY"),
            "api_base": os.environ.get("OPENAI_API_BASE"),
        },
        learning={
            "enabled": os.environ.get("LEARNING_ENABLED", "true").lower() == "true",
            "batch_size": int(os.environ.get("LEARNING_BATCH_SIZE", "10")),
            "extraction_model": os.environ.get("EXTRACTION_MODEL", "gpt-4"),
        },
        feedback={
            "enabled": os.environ.get("FEEDBACK_ENABLED", "true").lower() == "true",
        },
        static_skills={
            "enabled": os.environ.get("STATIC_SKILLS_ENABLED", "true").lower() == "true",
            "directory": os.environ.get("STATIC_SKILLS_DIRECTORY", "skills"),
            # Default to false - gateway already reads static skills from filesystem
            # Only enable if you want static skills persisted in database for search/metrics
            "sync_to_database": os.environ.get("SYNC_STATIC_SKILLS", "false").lower() == "true",
        },
        broker={
            "enabled": os.environ.get("BROKER_ENABLED", "true").lower() == "true",
        },
    )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="SAM Skill Learning Service",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--config", "-c",
        help="Path to YAML configuration file",
        default=os.environ.get("SKILL_LEARNING_CONFIG"),
    )
    parser.add_argument(
        "--log-level", "-l",
        help="Logging level",
        default=os.environ.get("LOG_LEVEL", "INFO"),
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    
    args = parser.parse_args()
    
    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Load configuration
    config = load_config(args.config)
    
    # Create and run service
    service = SkillLearningService(config)
    service.run_forever()


if __name__ == "__main__":
    main()