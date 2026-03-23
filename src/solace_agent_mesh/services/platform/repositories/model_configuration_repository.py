"""Repository for model configuration data access."""

import logging
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import cast, or_, String
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

    def get_by_alias_or_id(self, db: Session, alias: str) -> Optional[ModelConfiguration]:
        """
        Retrieve a model configuration by alias (case-sensitive exact match) or ID.

        Args:
            db: SQLAlchemy database session
            alias: Model alias or ID to look up

        Returns:
            ModelConfiguration ORM model if found, None otherwise
        """
        return db.query(ModelConfiguration).filter(
            or_(ModelConfiguration.alias == alias, cast(ModelConfiguration.id, String) == alias)
        ).first()
    