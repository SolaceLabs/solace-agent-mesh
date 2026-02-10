"""
SAM lifecycle manager for running SAM programmatically.
"""
import logging
from pathlib import Path
from typing import List, Optional

from dotenv import find_dotenv, load_dotenv

from cli.utils import discover_config_files  # noqa: F401 - re-exported for backwards compat


log = logging.getLogger(__name__)


class SAMRunner:
    """
    Manages the SolaceAiConnector lifecycle for task execution.

    Provides a context manager interface for guaranteed cleanup.
    """

    def __init__(
        self,
        config_files: List[str],
        log_file: Optional[Path] = None,
        load_env: bool = True,
    ):
        """
        Initialize the SAM runner.

        Args:
            config_files: List of YAML config file paths to load
            log_file: Optional path to write SAM logs (keeps terminal clean)
            load_env: Whether to load .env file
        """
        self.config_files = config_files
        self.log_file = log_file
        self.load_env = load_env
        self.connector = None
        self._started = False

    def start(self) -> None:
        """
        Start SAM by loading configs and creating the SolaceAiConnector.

        This method:
        1. Optionally loads .env file
        2. Loads and merges all config files
        3. Creates SolaceAiConnector instance
        4. Calls connector.run() to start background threads
        """
        from solace_ai_connector.main import load_config, merge_config
        from solace_ai_connector.solace_ai_connector import SolaceAiConnector

        # Load environment variables
        if self.load_env:
            env_path = find_dotenv(usecwd=True)
            if env_path:
                load_dotenv(dotenv_path=env_path, override=True)
                log.debug("Loaded .env from: %s", env_path)

        # Load and merge all config files
        full_config = {}
        for config_file in self.config_files:
            config = load_config(config_file)
            full_config = merge_config(full_config, config)
            log.debug("Loaded config: %s", config_file)

        # Configure logging to file if specified
        if self.log_file:
            self._configure_file_logging(full_config)

        # Create and start the connector
        self.connector = SolaceAiConnector(
            config=full_config,
            config_filenames=self.config_files,
        )
        self.connector.run()
        self._started = True
        log.debug("SolaceAiConnector started")

    def _configure_file_logging(self, config: dict) -> None:
        """
        Configure SAM to log to file instead of stdout.

        This keeps the terminal clean for task output.
        """
        config.setdefault("log", {})
        # Reduce stdout noise
        config["log"]["stdout_log_level"] = "WARNING"
        # Write detailed logs to file
        config["log"]["log_file"] = str(self.log_file)
        config["log"]["log_file_level"] = "INFO"

    def stop(self) -> None:
        """
        Stop SAM gracefully.

        Calls stop() and cleanup() on the connector.
        """
        if self.connector and self._started:
            log.debug("Stopping SolaceAiConnector...")
            try:
                self.connector.stop()
            except Exception as e:
                log.warning("Error during connector.stop(): %s", e)

            try:
                self.connector.cleanup()
            except Exception as e:
                log.warning("Error during connector.cleanup(): %s", e)

            self._started = False
            log.debug("SolaceAiConnector stopped")

    def __enter__(self):
        """Context manager entry - starts SAM."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - stops SAM (guaranteed cleanup)."""
        self.stop()
        return False  # Don't suppress exceptions


