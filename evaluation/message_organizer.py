"""
Refactored message categorization module with improved structure and readability.
This module categorizes evaluation messages into appropriate run directories.
"""

import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CategorizationError(Exception):
    """Base exception for categorization errors."""

    pass


class MissingFileError(CategorizationError):
    """Raised when required files are missing."""

    pass


class InvalidDataError(CategorizationError):
    """Raised when data format is invalid."""

    pass


@dataclass
class TaskMessage:
    """Represents a categorized task message with extracted metadata."""

    topic: str
    payload: Dict[str, Any]
    task_id: Optional[str] = None
    parent_task_id: Optional[str] = None

    @classmethod
    def from_dict(cls, message_dict: Dict[str, Any]) -> "TaskMessage":
        """Create TaskMessage from dictionary representation."""
        return cls(
            topic=message_dict.get("topic", ""), payload=message_dict.get("payload", {})
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert TaskMessage back to dictionary format."""
        return {"topic": self.topic, "payload": self.payload}


@dataclass
class TaskMapping:
    """Represents task ID to directory mappings with validation."""

    mappings: Dict[str, str]

    def get_run_directory(self, task_id: str) -> Optional[str]:
        """Get the run directory for a given task ID."""
        return self.mappings.get(task_id)

    def add_mapping(self, task_id: str, run_directory: str) -> None:
        """Add a new task ID to directory mapping."""
        self.mappings[task_id] = run_directory

    def has_task(self, task_id: str) -> bool:
        """Check if a task ID exists in the mappings."""
        return task_id in self.mappings


@dataclass
class CategorizationResult:
    """Results of the message categorization process."""

    total_messages: int
    categorized_messages: int
    uncategorized_messages: int
    updated_mappings_count: int

    @property
    def success_rate(self) -> float:
        """Calculate the success rate of categorization."""
        if self.total_messages == 0:
            return 0.0
        return self.categorized_messages / self.total_messages

    def __str__(self) -> str:
        """Human-readable summary of categorization results."""
        return (
            f"Categorization Results: {self.categorized_messages}/{self.total_messages} "
            f"messages categorized ({self.success_rate:.1%} success rate), "
            f"{self.updated_mappings_count} new mappings added"
        )


class TaskIdExtractor:
    """Handles extraction of task IDs from messages using multiple strategies."""

    def extract_task_id(
        self, message: TaskMessage
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract task ID using multiple strategies in order of preference.
        Returns (parent_task_id, sub_task_id) tuple.
        """
        if not isinstance(message.payload, dict):
            return None, None

        strategies = [
            self._extract_from_subtask_delegation,
            self._extract_from_toplevel_id,
            self._extract_from_result_object,
            self._extract_from_topic,
        ]

        for strategy in strategies:
            try:
                if strategy.__name__ == "_extract_from_topic":
                    task_id, sub_task_id = strategy(message)
                else:
                    task_id, sub_task_id = strategy(message.payload)
                if task_id:
                    return task_id, sub_task_id
            except Exception as e:
                logger.debug(f"Task ID extraction strategy failed: {e}")
                continue

        return None, None

    def _extract_from_subtask_delegation(
        self, payload: dict
    ) -> Tuple[Optional[str], Optional[str]]:
        """Strategy 1: Check for sub-task delegation (agent-to-agent calls)."""
        params = payload.get("params", {})
        if isinstance(params, dict):
            message_param = params.get("message", {})
            if isinstance(message_param, dict):
                metadata = message_param.get("metadata", {})
                if isinstance(metadata, dict):
                    parent_task_id = metadata.get("parentTaskId")
                    sub_task_id = payload.get("id")
                    if parent_task_id and sub_task_id:
                        return parent_task_id, sub_task_id
        return None, None

    def _extract_from_toplevel_id(
        self, payload: dict
    ) -> Tuple[Optional[str], Optional[str]]:
        """Strategy 2: Get the primary task ID from the top-level 'id' field."""
        task_id = payload.get("id")
        if task_id and isinstance(task_id, str):
            return task_id, None
        return None, None

    def _extract_from_result_object(
        self, payload: dict
    ) -> Tuple[Optional[str], Optional[str]]:
        """Strategy 3: Fallback for status updates which also have taskId nested."""
        result = payload.get("result", {})
        if isinstance(result, dict):
            task_id = result.get("taskId")
            if task_id and isinstance(task_id, str):
                return task_id, None
        return None, None

    def _extract_from_topic(
        self, message: TaskMessage
    ) -> Tuple[Optional[str], Optional[str]]:
        """Strategy 4: Extract from topic path (fallback method)."""
        topic = message.topic
        if not topic:
            return None, None

        # Extract the last part of the topic path
        task_id = topic.split("/")[-1]
        if task_id.startswith("gdk-task-"):
            return task_id, None

        return None, None


class FileOperations:
    """Handles file I/O operations with comprehensive error handling."""

    @staticmethod
    def load_json(filepath: str) -> Any:
        """Load JSON file with error handling and validation."""
        try:
            if not os.path.exists(filepath):
                raise MissingFileError(f"File not found: {filepath}")

            with open(filepath, "r") as f:
                data = json.load(f)

            logger.debug(f"Successfully loaded JSON from {filepath}")
            return data

        except json.JSONDecodeError as e:
            raise InvalidDataError(f"Invalid JSON in file {filepath}: {e}")
        except Exception as e:
            raise CategorizationError(f"Error loading file {filepath}: {e}")

    @staticmethod
    def save_json(data: Any, filepath: str) -> None:
        """Save data as JSON with error handling."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            with open(filepath, "w") as f:
                json.dump(data, f, indent=4)

            logger.debug(f"Successfully saved JSON to {filepath}")

        except Exception as e:
            raise CategorizationError(f"Error saving file {filepath}: {e}")

    @staticmethod
    def file_exists(filepath: str) -> bool:
        """Check if file exists."""
        return os.path.exists(filepath)

    @staticmethod
    def is_directory(path: str) -> bool:
        """Check if path is a directory."""
        return os.path.isdir(path)


class MessageCategorizer:
    """Handles categorization of messages into run directories."""

    def __init__(self, task_extractor: TaskIdExtractor, file_ops: FileOperations):
        self.task_extractor = task_extractor
        self.file_ops = file_ops

    def categorize_messages_for_model(
        self, model_path: str, model_name: str
    ) -> CategorizationResult:
        """Categorize messages for a single model with comprehensive error handling."""
        logger.info(f"Starting message categorization for model: {model_name}")

        try:
            # Validate required files exist
            self._validate_required_files(model_path, model_name)

            # Load task mappings and messages
            task_mappings = self._load_task_mappings(model_path)
            messages = self._load_messages(model_path)

            logger.info(
                f"Loaded {len(messages)} messages and {len(task_mappings.mappings)} task mappings"
            )

            # Extract task IDs from messages
            self._extract_task_ids_from_messages(messages)

            # Update task mappings with sub-task relationships
            updated_mappings_count = self._update_task_mappings(messages, task_mappings)

            # Categorize messages by run directory
            categorized_messages = self._categorize_by_task_id(messages, task_mappings)

            # Save categorized messages
            categorized_count = self._save_categorized_messages(categorized_messages)

            # Save updated task mappings
            self._save_task_mappings(task_mappings, model_path)

            # Calculate results
            uncategorized_count = len(messages) - categorized_count

            result = CategorizationResult(
                total_messages=len(messages),
                categorized_messages=categorized_count,
                uncategorized_messages=uncategorized_count,
                updated_mappings_count=updated_mappings_count,
            )

            logger.info(f"Categorization completed for {model_name}: {result}")
            return result

        except Exception as e:
            logger.error(f"Error categorizing messages for model {model_name}: {e}")
            raise

    def _validate_required_files(self, model_path: str, model_name: str) -> None:
        """Validate that required files exist for processing."""
        mappings_file = os.path.join(model_path, "task_mappings.json")
        messages_file = os.path.join(model_path, "full_messages.json")

        if not self.file_ops.file_exists(mappings_file):
            raise MissingFileError(
                f"Missing task mappings file for model {model_name}: {mappings_file}"
            )

        if not self.file_ops.file_exists(messages_file):
            raise MissingFileError(
                f"Missing messages file for model {model_name}: {messages_file}"
            )

    def _load_task_mappings(self, model_path: str) -> TaskMapping:
        """Load task mappings from file with validation."""
        mappings_file = os.path.join(model_path, "task_mappings.json")
        mappings_data = self.file_ops.load_json(mappings_file)

        if not isinstance(mappings_data, dict):
            raise InvalidDataError(
                f"Task mappings must be a dictionary, got {type(mappings_data)}"
            )

        return TaskMapping(mappings=mappings_data)

    def _load_messages(self, model_path: str) -> List[TaskMessage]:
        """Load and parse messages from file with validation."""
        messages_file = os.path.join(model_path, "full_messages.json")
        messages_data = self.file_ops.load_json(messages_file)

        if not isinstance(messages_data, list):
            raise InvalidDataError(
                f"Messages must be a list, got {type(messages_data)}"
            )

        messages = []
        for i, message_dict in enumerate(messages_data):
            try:
                message = TaskMessage.from_dict(message_dict)
                messages.append(message)
            except Exception as e:
                logger.warning(f"Skipping invalid message at index {i}: {e}")
                continue

        return messages

    def _extract_task_ids_from_messages(self, messages: List[TaskMessage]) -> None:
        """Extract task IDs from all messages and update the message objects."""
        for message in messages:
            task_id, sub_task_id = self.task_extractor.extract_task_id(message)
            message.task_id = task_id or sub_task_id
            message.parent_task_id = task_id if sub_task_id else None

    def _update_task_mappings(
        self, messages: List[TaskMessage], task_mappings: TaskMapping
    ) -> int:
        """Update task mappings with sub-task relationships."""
        updated_count = 0

        for message in messages:
            if (
                message.parent_task_id
                and message.task_id
                and task_mappings.has_task(message.parent_task_id)
                and not task_mappings.has_task(message.task_id)
            ):

                # Map sub-task to same directory as parent task
                parent_directory = task_mappings.get_run_directory(
                    message.parent_task_id
                )
                task_mappings.add_mapping(message.task_id, parent_directory)
                updated_count += 1

                logger.debug(
                    f"Mapped sub-task {message.task_id} to parent directory: {parent_directory}"
                )

        return updated_count

    def _categorize_by_task_id(
        self, messages: List[TaskMessage], task_mappings: TaskMapping
    ) -> Dict[str, List[TaskMessage]]:
        """Group messages by their target run directory."""
        categorized = {}

        for message in messages:
            if not message.task_id:
                continue

            run_directory = task_mappings.get_run_directory(message.task_id)
            if not run_directory:
                continue

            if run_directory not in categorized:
                categorized[run_directory] = []

            categorized[run_directory].append(message)

        return categorized

    def _save_categorized_messages(
        self, categorized_messages: Dict[str, List[TaskMessage]]
    ) -> int:
        """Save categorized messages to their respective directories."""
        total_saved = 0

        for run_directory, messages in categorized_messages.items():
            try:
                output_file = os.path.join(run_directory, "messages.json")

                # Convert TaskMessage objects back to dictionaries
                message_dicts = [msg.to_dict() for msg in messages]

                self.file_ops.save_json(message_dicts, output_file)
                total_saved += len(messages)

                logger.info(f"Saved {len(messages)} messages to {output_file}")

            except Exception as e:
                logger.error(f"Error saving messages to {run_directory}: {e}")
                continue

        return total_saved

    def _save_task_mappings(self, task_mappings: TaskMapping, model_path: str) -> None:
        """Save updated task mappings back to file."""
        mappings_file = os.path.join(model_path, "task_mappings.json")
        self.file_ops.save_json(task_mappings.mappings, mappings_file)
        logger.info(f"Updated task mappings saved to {mappings_file}")


class MessageOrganizer:
    """Main organizer for the message categorization process."""

    def __init__(self):
        self.task_extractor = TaskIdExtractor()
        self.file_ops = FileOperations()
        self.categorizer = MessageCategorizer(self.task_extractor, self.file_ops)

    def categorize_all_messages(
        self, base_results_path: str
    ) -> Dict[str, CategorizationResult]:
        """
        Main entry point for categorizing all messages across all models.
        Returns a dictionary mapping model names to their categorization results.
        """
        logger.info(
            f"Starting message categorization for all models in: {base_results_path}"
        )

        if not self.file_ops.is_directory(base_results_path):
            raise MissingFileError(f"Results directory not found: {base_results_path}")

        results = {}
        processed_models = 0

        try:
            for model_name in os.listdir(base_results_path):
                model_path = os.path.join(base_results_path, model_name)

                if not self.file_ops.is_directory(model_path):
                    logger.debug(f"Skipping non-directory: {model_name}")
                    continue

                try:
                    result = self._process_model_directory(model_path, model_name)
                    results[model_name] = result
                    processed_models += 1

                except (MissingFileError, InvalidDataError) as e:
                    logger.warning(f"Skipping model {model_name}: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Error processing model {model_name}: {e}")
                    continue

            logger.info(
                f"Message categorization completed. Processed {processed_models} models."
            )
            self._log_summary_statistics(results)

            return results

        except Exception as e:
            logger.error(f"Error during message categorization: {e}")
            raise

    def _process_model_directory(
        self, model_path: str, model_name: str
    ) -> CategorizationResult:
        """Process a single model directory and return categorization results."""
        logger.info(f"Processing model directory: {model_name}")

        try:
            result = self.categorizer.categorize_messages_for_model(
                model_path, model_name
            )
            logger.info(f"Successfully processed model {model_name}: {result}")
            return result

        except Exception as e:
            logger.error(f"Failed to process model {model_name}: {e}")
            raise

    def _log_summary_statistics(self, results: Dict[str, CategorizationResult]) -> None:
        """Log summary statistics for all processed models."""
        if not results:
            logger.warning("No models were successfully processed")
            return

        total_messages = sum(result.total_messages for result in results.values())
        total_categorized = sum(
            result.categorized_messages for result in results.values()
        )
        total_mappings_added = sum(
            result.updated_mappings_count for result in results.values()
        )

        overall_success_rate = (
            total_categorized / total_messages if total_messages > 0 else 0.0
        )

        logger.info("=== CATEGORIZATION SUMMARY ===")
        logger.info(f"Models processed: {len(results)}")
        logger.info(f"Total messages: {total_messages}")
        logger.info(f"Messages categorized: {total_categorized}")
        logger.info(f"Overall success rate: {overall_success_rate:.1%}")
        logger.info(f"New task mappings added: {total_mappings_added}")
        logger.info("==============================")


def main():
    """Main entry point when running the script directly."""
    try:
        # Import here to avoid circular imports
        from evaluation.config_loader import ConfigLoader

        SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
        config_loader = ConfigLoader()
        config = config_loader.load_config()
        results_dir_name = config["results_dir_name"]
        base_results_path = os.path.join(SCRIPT_DIR, "results", results_dir_name)

        orchestrator = MessageOrganizer()
        results = orchestrator.categorize_all_messages(base_results_path)

        print("Message categorization completed successfully!")
        print(f"Processed {len(results)} models")

    except Exception as e:
        logger.error(f"Script execution failed: {e}")
        raise


if __name__ == "__main__":
    main()
