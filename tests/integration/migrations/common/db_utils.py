"""Database utility functions for migration testing."""

from sqlalchemy import Engine, inspect


def get_table_names(engine: Engine, exclude_alembic: bool = True) -> set[str]:
    """
    Get all table names in the database.

    Args:
        engine: SQLAlchemy engine
        exclude_alembic: If True, exclude alembic_version table

    Returns:
        Set of table names
    """
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    if exclude_alembic:
        tables.discard("alembic_version")

    return tables


def get_column_names(engine: Engine, table_name: str) -> set[str]:
    """
    Get all column names for a table.

    Args:
        engine: SQLAlchemy engine
        table_name: Name of the table

    Returns:
        Set of column names
    """
    inspector = inspect(engine)
    columns = inspector.get_columns(table_name)
    return {col["name"] for col in columns}


def get_index_names(engine: Engine, table_name: str) -> set[str]:
    """
    Get all index names for a table.

    Args:
        engine: SQLAlchemy engine
        table_name: Name of the table

    Returns:
        Set of index names
    """
    inspector = inspect(engine)
    indexes = inspector.get_indexes(table_name)
    return {idx["name"] for idx in indexes if idx.get("name")}


def get_foreign_key_info(engine: Engine, table_name: str) -> list[dict]:
    """
    Get foreign key information for a table.

    Args:
        engine: SQLAlchemy engine
        table_name: Name of the table

    Returns:
        List of foreign key constraint dicts
    """
    inspector = inspect(engine)
    return inspector.get_foreign_keys(table_name)


def verify_table_exists(engine: Engine, table_name: str) -> bool:
    """
    Check if a table exists in the database.

    Args:
        engine: SQLAlchemy engine
        table_name: Name of the table to check

    Returns:
        True if table exists, False otherwise
    """
    return table_name in get_table_names(engine, exclude_alembic=False)


def verify_column_exists(engine: Engine, table_name: str, column_name: str) -> bool:
    """
    Check if a column exists in a table.

    Args:
        engine: SQLAlchemy engine
        table_name: Name of the table
        column_name: Name of the column

    Returns:
        True if column exists, False otherwise
    """
    if not verify_table_exists(engine, table_name):
        return False

    return column_name in get_column_names(engine, table_name)


def verify_index_exists(engine: Engine, table_name: str, index_name: str) -> bool:
    """
    Check if an index exists on a table.

    Args:
        engine: SQLAlchemy engine
        table_name: Name of the table
        index_name: Name of the index

    Returns:
        True if index exists, False otherwise
    """
    if not verify_table_exists(engine, table_name):
        return False

    return index_name in get_index_names(engine, table_name)
