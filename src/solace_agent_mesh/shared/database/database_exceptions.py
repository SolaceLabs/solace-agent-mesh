"""
Database Exception Handling

Provides centralized handling for converting SQLAlchemy exceptions to domain exceptions.
This handler translates low-level database errors into meaningful business exceptions
that can be properly handled by the API layer.
"""

from typing import Optional, Dict, List
from sqlalchemy.exc import IntegrityError, SQLAlchemyError, OperationalError, DatabaseError
from ..exceptions.exceptions import ValidationError, DataIntegrityError, EntityAlreadyExistsError


class DatabaseExceptionHandler:
    """
    Centralized handler for converting SQLAlchemy exceptions to domain exceptions.

    This handler translates low-level database errors into meaningful business exceptions
    that can be properly handled by the API layer.
    """

    @staticmethod
    def handle_integrity_error(e: IntegrityError, entity_type: str = "Resource") -> ValidationError:
        """
        Convert SQLAlchemy integrity constraint violations to domain exceptions.

        Args:
            e: The SQLAlchemy IntegrityError
            entity_type: The type of entity being operated on

        Returns:
            ValidationError with appropriate message and validation details
        """
        # Try to get the most descriptive error message for constraint matching
        full_message = str(e)
        orig_message = str(e.orig) if hasattr(e, 'orig') and e.orig else ""

        # Use the message that contains constraint information
        if any(keyword in full_message for keyword in ['constraint', 'UNIQUE', 'NULL', 'CHECK', 'FOREIGN']):
            # Extract the most specific constraint line from the full message
            lines = full_message.split('\n')

            # Prioritize SQL lines that contain actual constraint details
            for line in lines:
                if '[SQL:' in line and any(keyword in line for keyword in ['UNIQUE', 'NULL', 'CHECK', 'FOREIGN']):
                    # Extract just the SQL part without the [SQL: ] wrapper
                    if '[SQL:' in line and ']' in line:
                        error_message = line.split('[SQL:')[1].split(']')[0].strip()
                        break
                    error_message = line.strip()
                    break
            else:
                # Fallback to any line with constraint keywords
                for line in lines:
                    if any(keyword in line for keyword in ['constraint', 'UNIQUE', 'NULL', 'CHECK', 'FOREIGN']):
                        error_message = line.strip()
                        break
                else:
                    error_message = full_message
        else:
            # Fallback to orig if no constraint info in main message
            error_message = orig_message or full_message

        # Handle UNIQUE constraint violations and concurrent modifications
        if ("UNIQUE constraint failed" in error_message or
            "duplicate key value" in error_message.lower() or
            "concurrent modification" in error_message.lower() or
            "row was updated or deleted by another transaction" in error_message.lower()):
            field_name = DatabaseExceptionHandler._extract_field_from_unique_error(error_message)
            return EntityAlreadyExistsError(
                entity_type=entity_type,
                identifier=field_name,
                value="provided value"
            )

        # Handle NOT NULL constraint violations
        if "NOT NULL constraint failed" in error_message or "null value in column" in error_message.lower():
            field_name = DatabaseExceptionHandler._extract_field_from_null_error(error_message)
            return ValidationError(
                message="Required field is missing",
                validation_details={field_name: ["This field is required"]},
                entity_type=entity_type
            )

        # Handle CHECK constraint violations
        if "CHECK constraint failed" in error_message or "check constraint" in error_message.lower():
            constraint_name = DatabaseExceptionHandler._extract_constraint_name(error_message)
            field_name = DatabaseExceptionHandler._map_constraint_to_field(constraint_name)
            return ValidationError(
                message="Field validation failed",
                validation_details={field_name: ["Value violates validation rules"]},
                entity_type=entity_type
            )

        # Handle FOREIGN KEY constraint violations
        if "FOREIGN KEY constraint failed" in error_message or "foreign key constraint" in error_message.lower():
            return ValidationError(
                message="Referenced resource does not exist",
                validation_details={"reference": ["Invalid reference to related resource"]},
                entity_type=entity_type
            )

        # Generic integrity error fallback
        return DataIntegrityError(
            constraint="integrity_violation",
            message=f"Database constraint violation: {error_message}"
        )

    @staticmethod
    def handle_operational_error(e: OperationalError, entity_type: str = "Resource") -> DataIntegrityError:
        """
        Handle SQLAlchemy operational errors (connection issues, timeouts, etc.).

        Args:
            e: The SQLAlchemy OperationalError
            entity_type: The type of entity being operated on

        Returns:
            DataIntegrityError with appropriate message
        """
        error_message = str(e.orig) if hasattr(e, 'orig') else str(e)

        if "timeout" in error_message.lower():
            return DataIntegrityError(
                constraint="timeout",
                message="Database operation timed out. Please try again."
            )

        if "connection" in error_message.lower():
            return DataIntegrityError(
                constraint="connection_error",
                message="Database connection failed. Please try again later."
            )

        return DataIntegrityError(
            constraint="operational_error",
            message="Database operation failed. Please contact support if this persists."
        )

    @staticmethod
    def handle_database_error(e: DatabaseError, entity_type: str = "Resource") -> DataIntegrityError:
        """
        Handle general SQLAlchemy database errors.

        Args:
            e: The SQLAlchemy DatabaseError
            entity_type: The type of entity being operated on

        Returns:
            DataIntegrityError with appropriate message
        """
        error_message = str(e.orig) if hasattr(e, 'orig') else str(e)

        return DataIntegrityError(
            constraint="database_error",
            message="A database error occurred. Please contact support."
        )

    @staticmethod
    def handle_sqlalchemy_error(e: SQLAlchemyError, entity_type: str = "Resource") -> DataIntegrityError:
        """
        Handle any other SQLAlchemy errors not caught by specific handlers.

        Args:
            e: The SQLAlchemy error
            entity_type: The type of entity being operated on

        Returns:
            DataIntegrityError with generic message
        """
        error_message = str(e)

        return DataIntegrityError(
            constraint="sqlalchemy_error",
            message="An unexpected database error occurred. Please contact support."
        )

    @staticmethod
    def _extract_field_from_unique_error(error_message: str) -> str:
        """Extract field name from UNIQUE constraint error message."""
        # Try to extract field name from common formats
        if "agents.name" in error_message:
            return "name"
        elif "agents.id" in error_message:
            return "id"
        elif "." in error_message:
            # Extract field after table.field pattern
            parts = error_message.split(".")
            if len(parts) > 1:
                field_part = parts[1].split()[0]  # Get first word after dot
                return field_part.strip('()"\'')

        return "field"  # Generic fallback

    @staticmethod
    def _extract_field_from_null_error(error_message: str) -> str:
        """Extract field name from NOT NULL constraint error message."""
        # Common patterns: "NOT NULL constraint failed: agents.name"
        if ":" in error_message:
            field_part = error_message.split(":")[-1].strip()
            if "." in field_part:
                return field_part.split(".")[-1]
            return field_part

        return "field"  # Generic fallback

    @staticmethod
    def _extract_constraint_name(error_message: str) -> str:
        """Extract constraint name from CHECK constraint error message."""
        # Common patterns: "CHECK constraint failed: check_name_length"
        if ":" in error_message:
            constraint_part = error_message.split(":")[-1].strip()
            return constraint_part

        return "unknown_constraint"

    @staticmethod
    def _map_constraint_to_field(constraint_name: str) -> str:
        """Map database constraint names to user-friendly field names."""
        constraint_field_map = {
            "check_name_length": "name",
            "check_description_length": "description",
            "check_system_prompt_length": "systemPrompt",
            "check_created_by_length": "createdBy",
            "check_updated_by_length": "updatedBy",
            "check_id_length": "id"
        }

        return constraint_field_map.get(constraint_name, "field")


class DatabaseErrorDecorator:
    """
    Decorator class for wrapping repository methods with database exception handling.
    """

    def __init__(self, entity_type: str = "Resource"):
        self.entity_type = entity_type

    def __call__(self, func):
        """
        Decorator that wraps repository methods with database exception handling.

        Args:
            func: The repository method to wrap

        Returns:
            Wrapped function with exception handling
        """
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except IntegrityError as e:
                raise DatabaseExceptionHandler.handle_integrity_error(e, self.entity_type)
            except OperationalError as e:
                raise DatabaseExceptionHandler.handle_operational_error(e, self.entity_type)
            except DatabaseError as e:
                raise DatabaseExceptionHandler.handle_database_error(e, self.entity_type)
            except SQLAlchemyError as e:
                raise DatabaseExceptionHandler.handle_sqlalchemy_error(e, self.entity_type)

        return wrapper


def handle_database_errors(entity_type: str = "Resource"):
    """
    Convenience decorator for database exception handling.

    Usage:
        @handle_database_errors("Agent")
        def create_agent(self, ...):
            # Repository method implementation
    """
    return DatabaseErrorDecorator(entity_type)