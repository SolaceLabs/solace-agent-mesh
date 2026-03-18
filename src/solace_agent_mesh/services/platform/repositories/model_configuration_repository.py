"""Repository for model configuration data access."""

import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from solace_agent_mesh.services.platform.models import ModelConfiguration

log = logging.getLogger(__name__)


class ModelConfigurationRepository:
    """
    Repository for model configuration data access.

    Handles all database operations for model configurations.
    Takes db: Session as a parameter to each method (no instance state).
    """

    def get_all(self, db: Session) -> List[ModelConfiguration]:
        """
        Retrieve all model configurations from the database.

        Args:
            db: SQLAlchemy database session

        Returns:
            List of ModelConfiguration ORM models
        """
        return db.query(ModelConfiguration).all()

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

    def delete(self, db: Session, model: ModelConfiguration) -> None:
        """
        Delete a model configuration.

        Args:
            db: SQLAlchemy database session
            model: ModelConfiguration ORM model to delete
        """
        db.delete(model)
        db.flush()

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
