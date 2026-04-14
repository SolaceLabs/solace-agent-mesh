"""Repository for model configuration data access."""

import logging
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import or_
from solace_ai_connector.common.observability import DBMonitor, MonitorLatency
from solace_agent_mesh.services.platform.models import ModelConfiguration
from solace_agent_mesh.shared.database.database_exceptions import handle_database_errors
from solace_agent_mesh.shared.exceptions.exceptions import ValidationError

log = logging.getLogger(__name__)


class ModelConfigurationRepository:
    """
    Repository for model configuration data access.

    Handles all database operations for model configurations.
    Takes db: Session as a parameter to each method (no instance state).
    """

    def _validate_model_id(self, model_id: str) -> str:
        """Validate model ID."""
        if not model_id or not isinstance(model_id, str) or model_id.strip() == '':
            raise ValidationError(
                f"Model ID must be a non-empty string, got: {model_id}",
                validation_details={'model_id': ['Model ID is required and must be a valid string']},
                entity_type='ModelConfiguration'
            )
        return model_id.strip()

    @MonitorLatency(DBMonitor.query("model_configurations"))
    def get_all(self, db: Session) -> List[ModelConfiguration]:
        """
        Retrieve all model configurations from the database.

        Args:
            db: SQLAlchemy database session

        Returns:
            List of ModelConfiguration ORM models
        """
        return db.query(ModelConfiguration).all()

    @MonitorLatency(DBMonitor.query("model_configurations"))
    def get_by_alias(self, db: Session, alias: str) -> Optional[ModelConfiguration]:
        """
        Retrieve a model configuration by alias (case-sensitive exact match).

        Args:
            db: SQLAlchemy database session
            alias: Model alias to look up

        Returns:
            ModelConfiguration ORM model if found, None otherwise
        """
        return db.query(ModelConfiguration).filter(
            ModelConfiguration.alias == alias
        ).first()

    @handle_database_errors("ModelConfiguration")
    @MonitorLatency(DBMonitor.insert("model_configurations"))
    def create(self, db: Session, model: ModelConfiguration) -> ModelConfiguration:
        """
        Create a new model configuration.

        Args:
            db: SQLAlchemy database session
            model: ModelConfiguration ORM model to persist

        Returns:
            The persisted ModelConfiguration with ID populated
        """
        db.add(model)
        db.flush()

        return model

    @handle_database_errors("ModelConfiguration")
    @MonitorLatency(DBMonitor.update("model_configurations"))
    def update(self, db: Session, model: ModelConfiguration) -> ModelConfiguration:
        """
        Update an existing model configuration.

        Args:
            db: SQLAlchemy database session
            model: ModelConfiguration ORM model with updated values

        Returns:
            The updated ModelConfiguration
        """
        db.flush()

        return model

    @MonitorLatency(DBMonitor.delete("model_configurations"))
    def delete(self, db: Session, model: ModelConfiguration) -> None:
        """
        Delete a model configuration.

        Args:
            db: SQLAlchemy database session
            model: ModelConfiguration ORM model to delete
        """
        db.delete(model)
        db.flush()

    @MonitorLatency(DBMonitor.query("model_configurations"))
    def get_by_id(self, db: Session, model_id: str) -> Optional[ModelConfiguration]:
        """
        Retrieve a model configuration by ID.

        Args:
            db: SQLAlchemy database session
            model_id: Model UUID to look up

        Returns:
            ModelConfiguration ORM model if found, None otherwise
        """
        model_id = self._validate_model_id(model_id)
        return db.query(ModelConfiguration).filter(
            ModelConfiguration.id == model_id
        ).first()

    @MonitorLatency(DBMonitor.query("model_configurations"))
    def get_by_alias_or_id(self, db: Session, alias: str) -> Optional[ModelConfiguration]:
        """
        Retrieve a model configuration by alias or ID.

        Args:
            db: SQLAlchemy database session
            alias: Model alias or ID to look up

        Returns:
            ModelConfiguration ORM model if found, None otherwise
        """
        alias = self._validate_model_id(alias)
        return db.query(ModelConfiguration).filter(
            or_(
                ModelConfiguration.alias == alias,
                ModelConfiguration.id == alias,
            )
        ).first()

    def exists_by_alias(self, db: Session, alias: str) -> bool:
        """
        Check if a model configuration exists with case-sensitive alias match.

        Args:
            db: SQLAlchemy database session
            alias: Model alias to check

        Returns:
            True if configuration exists, False otherwise
        """
        return self.get_by_alias(db, alias) is not None
