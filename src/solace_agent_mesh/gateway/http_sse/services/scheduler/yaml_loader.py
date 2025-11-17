"""
YAML configuration loader for scheduled tasks.
Allows defining scheduled tasks in YAML files for easy management and version control.
"""

import logging
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml
from sqlalchemy.orm import Session as DBSession

from ...repository.models import ScheduledTaskModel
from ...repository.scheduled_task_repository import ScheduledTaskRepository
from ...shared import now_epoch_ms

log = logging.getLogger(__name__)


class YamlTaskLoader:
    """
    Loads scheduled task definitions from YAML files.
    Supports bulk import and synchronization with database.
    """

    def __init__(
        self,
        session_factory: Callable[[], DBSession],
        namespace: str,
        default_user_id: str = "system",
    ):
        """
        Initialize YAML task loader.

        Args:
            session_factory: Factory function to create database sessions
            namespace: Namespace for tasks
            default_user_id: Default user ID for YAML-defined tasks
        """
        self.session_factory = session_factory
        self.namespace = namespace
        self.default_user_id = default_user_id
        self.log_prefix = "[YamlTaskLoader]"

        log.info(f"{self.log_prefix} Initialized for namespace '{namespace}'")

    def load_from_file(self, file_path: str) -> List[ScheduledTaskModel]:
        """
        Load scheduled tasks from a YAML file.

        Args:
            file_path: Path to YAML file

        Returns:
            List of created/updated ScheduledTaskModel instances
        """
        log.info(f"{self.log_prefix} Loading tasks from {file_path}")

        try:
            path = Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"YAML file not found: {file_path}")

            with open(path, "r") as f:
                data = yaml.safe_load(f)

            if not data or "scheduled_tasks" not in data:
                log.warning(f"{self.log_prefix} No 'scheduled_tasks' key found in {file_path}")
                return []

            tasks_data = data["scheduled_tasks"]
            if not isinstance(tasks_data, list):
                raise ValueError("'scheduled_tasks' must be a list")

            return self._process_tasks(tasks_data, file_path)

        except Exception as e:
            log.error(f"{self.log_prefix} Error loading YAML file {file_path}: {e}", exc_info=True)
            raise

    def load_from_directory(self, directory_path: str) -> List[ScheduledTaskModel]:
        """
        Load all scheduled tasks from YAML files in a directory.

        Args:
            directory_path: Path to directory containing YAML files

        Returns:
            List of all created/updated ScheduledTaskModel instances
        """
        log.info(f"{self.log_prefix} Loading tasks from directory {directory_path}")

        try:
            dir_path = Path(directory_path)
            if not dir_path.exists() or not dir_path.is_dir():
                raise ValueError(f"Directory not found: {directory_path}")

            all_tasks = []
            yaml_files = list(dir_path.glob("*.yaml")) + list(dir_path.glob("*.yml"))

            for yaml_file in yaml_files:
                try:
                    tasks = self.load_from_file(str(yaml_file))
                    all_tasks.extend(tasks)
                except Exception as e:
                    log.error(f"{self.log_prefix} Error loading {yaml_file}: {e}")
                    # Continue with other files

            log.info(f"{self.log_prefix} Loaded {len(all_tasks)} tasks from {len(yaml_files)} files")
            return all_tasks

        except Exception as e:
            log.error(f"{self.log_prefix} Error loading directory {directory_path}: {e}", exc_info=True)
            raise

    def _process_tasks(
        self, tasks_data: List[Dict[str, Any]], source_file: str
    ) -> List[ScheduledTaskModel]:
        """
        Process task definitions and create/update in database.

        Args:
            tasks_data: List of task definitions from YAML
            source_file: Source file path for logging

        Returns:
            List of created/updated tasks
        """
        repo = ScheduledTaskRepository()
        processed_tasks = []

        with self.session_factory() as session:
            for idx, task_def in enumerate(tasks_data):
                try:
                    task = self._create_or_update_task(session, task_def, source_file)
                    if task:
                        processed_tasks.append(task)
                except Exception as e:
                    log.error(
                        f"{self.log_prefix} Error processing task #{idx} from {source_file}: {e}",
                        exc_info=True,
                    )
                    # Continue with other tasks

            session.commit()

        log.info(f"{self.log_prefix} Processed {len(processed_tasks)} tasks from {source_file}")
        return processed_tasks

    def _create_or_update_task(
        self,
        session: DBSession,
        task_def: Dict[str, Any],
        source_file: str,
    ) -> Optional[ScheduledTaskModel]:
        """
        Create or update a single task from YAML definition.

        Args:
            session: Database session
            task_def: Task definition dictionary
            source_file: Source file for logging

        Returns:
            Created or updated ScheduledTaskModel
        """
        repo = ScheduledTaskRepository()

        # Validate required fields
        required_fields = ["name", "schedule_type", "schedule_expression", "target_agent_name", "task_message"]
        for field in required_fields:
            if field not in task_def:
                raise ValueError(f"Missing required field '{field}' in task definition")

        # Check if task exists by name (for updates)
        task_name = task_def["name"]
        existing_tasks = repo.find_by_namespace(
            session,
            namespace=self.namespace,
            user_id=None,  # YAML tasks are namespace-level
            include_namespace_tasks=True,
            enabled_only=False,
        )

        existing_task = next((t for t in existing_tasks if t.name == task_name and not t.deleted_at), None)

        if existing_task:
            # Update existing task
            log.info(f"{self.log_prefix} Updating existing task: {task_name}")
            update_data = self._prepare_task_data(task_def, is_update=True)
            task = repo.update_task(session, existing_task.id, update_data)
        else:
            # Create new task
            log.info(f"{self.log_prefix} Creating new task: {task_name}")
            task_data = self._prepare_task_data(task_def, is_update=False)
            task_data["id"] = str(uuid.uuid4())
            task_data["namespace"] = self.namespace
            task_data["user_id"] = None  # Namespace-level task
            task_data["created_by"] = self.default_user_id
            task_data["created_at"] = now_epoch_ms()
            task_data["updated_at"] = now_epoch_ms()
            task = repo.create_task(session, task_data)

        return task

    def _prepare_task_data(
        self, task_def: Dict[str, Any], is_update: bool = False
    ) -> Dict[str, Any]:
        """
        Prepare task data from YAML definition.

        Args:
            task_def: Task definition from YAML
            is_update: Whether this is an update operation

        Returns:
            Dictionary ready for database insertion/update
        """
        data = {
            "name": task_def["name"],
            "description": task_def.get("description"),
            "schedule_type": task_def["schedule_type"],
            "schedule_expression": task_def["schedule_expression"],
            "timezone": task_def.get("timezone", "UTC"),
            "target_agent_name": task_def["target_agent_name"],
            "task_message": task_def["task_message"],
            "task_metadata": task_def.get("task_metadata"),
            "enabled": task_def.get("enabled", True),
            "max_retries": task_def.get("max_retries", 0),
            "retry_delay_seconds": task_def.get("retry_delay_seconds", 60),
            "timeout_seconds": task_def.get("timeout_seconds", 3600),
            "notification_config": task_def.get("notification_config"),
        }

        if is_update:
            data["updated_at"] = now_epoch_ms()

        return data