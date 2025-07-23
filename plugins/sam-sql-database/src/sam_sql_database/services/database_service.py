"""Service for handling SQL database operations."""

from abc import ABC, abstractmethod
from contextlib import contextmanager
import yaml
from typing import List, Dict, Any, Generator, Optional

import sqlalchemy as sa
from sqlalchemy.engine import Engine, Connection
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import inspect, text

try:
    from solace_ai_connector.common.log import log
except ImportError:
    import logging

    log = logging.getLogger(__name__)

from .csv_import_service import CsvImportService


class DatabaseService(ABC):
    """Abstract base class for database services."""

    def __init__(self, connection_params: Dict[str, Any], query_timeout: int = 30):
        """Initialize the database service.

        Args:
            connection_params: Database connection parameters.
            query_timeout: Query timeout in seconds.
        """
        self.connection_params = connection_params
        self.query_timeout = query_timeout
        self.engine: Optional[Engine] = None
        try:
            self.engine = self._create_engine()
            log.info(
                "Database engine created successfully for type: %s",
                self.__class__.__name__,
            )
        except Exception as e:
            log.error("Failed to create database engine: %s", e, exc_info=True)

        if self.engine:
            self.csv_import_service = CsvImportService(self)
            log.info("CsvImportService initialized.")
        else:
            self.csv_import_service = None
            log.warning(
                "CsvImportService not initialized due to missing database engine."
            )

    def import_csv_data(
        self, files: Optional[List[str]] = None, directories: Optional[List[str]] = None
    ) -> None:
        """Import CSV files into database tables using CsvImportService."""
        if self.csv_import_service:
            try:
                self.csv_import_service.import_csv_files(files, directories)
            except Exception as e:
                log.error("Error during CSV import process: %s", e, exc_info=True)
        else:
            log.error(
                "Cannot import CSV data: CsvImportService is not available (likely due to engine init failure)."
            )

    @abstractmethod
    def _create_engine(self) -> Engine:
        """Create SQLAlchemy engine for database connection.

        Returns:
            SQLAlchemy Engine instance.
        """
        pass

    def close(self) -> None:
        """Dispose of the engine and its connection pool."""
        if self.engine:
            try:
                self.engine.dispose()
                log.info("Database engine disposed successfully.")
            except Exception as e:
                log.error("Error disposing database engine: %s", e, exc_info=True)
        else:
            log.warning("No database engine to dispose.")

    @contextmanager
    def get_connection(self) -> Generator[Connection, None, None]:
        """Get a database connection from the pool.

        Yields:
            Active database connection.

        Raises:
            SQLAlchemyError: If connection fails.
            RuntimeError: If the engine was not initialized.
        """
        if not self.engine:
            raise RuntimeError("Database engine is not initialized.")

        connection: Optional[Connection] = None
        try:
            connection = self.engine.connect()
            yield connection
        except SQLAlchemyError as e:
            log.error("Database connection error: %s", str(e), exc_info=True)
            raise
        finally:
            if connection:
                connection.close()

    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """Execute a SQL query.

        Args:
            query: SQL query to execute.

        Returns:
            List of dictionaries containing query results.

        Raises:
            SQLAlchemyError: If query execution fails.
            RuntimeError: If the engine was not initialized.
        """
        if not self.engine:
            raise RuntimeError("Database engine is not initialized.")
        try:
            with self.get_connection() as conn:
                result = conn.execute(text(query))
                if result.returns_rows:
                    return list(result.mappings())
                else:
                    log.info(
                        "Query executed successfully, affected rows: %s",
                        result.rowcount,
                    )
                    return [
                        {
                            "status": "success",
                            "affected_rows": (
                                result.rowcount if result.rowcount is not None else 0
                            ),
                        }
                    ]
        except SQLAlchemyError as e:
            log.error("Query execution error: %s", str(e), exc_info=True)
            raise

    def get_tables(self) -> List[str]:
        """Get all table names in the database."""
        if not self.engine:
            raise RuntimeError("Database engine is not initialized.")
        inspector = inspect(self.engine)
        return inspector.get_table_names()

    def get_columns(self, table_name: str) -> List[Dict[str, Any]]:
        """Get detailed column information for a table."""
        if not self.engine:
            raise RuntimeError("Database engine is not initialized.")
        inspector = inspect(self.engine)
        return inspector.get_columns(table_name)

    def get_primary_keys(self, table_name: str) -> List[str]:
        """Get primary key columns for a table."""
        if not self.engine:
            raise RuntimeError("Database engine is not initialized.")
        inspector = inspect(self.engine)
        pk_constraint = inspector.get_pk_constraint(table_name)
        return pk_constraint["constrained_columns"] if pk_constraint else []

    def get_foreign_keys(self, table_name: str) -> List[Dict[str, Any]]:
        """Get foreign key relationships for a table."""
        if not self.engine:
            raise RuntimeError("Database engine is not initialized.")
        inspector = inspect(self.engine)
        return inspector.get_foreign_keys(table_name)

    def get_indexes(self, table_name: str) -> List[Dict[str, Any]]:
        """Get indexes for a table."""
        if not self.engine:
            raise RuntimeError("Database engine is not initialized.")
        inspector = inspect(self.engine)
        return inspector.get_indexes(table_name)

    def get_unique_values(
        self, table_name: str, column_name: str, limit: int = 3
    ) -> List[Any]:
        """Get a sample of unique values from a column."""
        if not self.engine:
            raise RuntimeError("Database engine is not initialized.")

        if self.engine.name == "mysql":
            query = f"SELECT DISTINCT `{column_name}` FROM `{table_name}` WHERE `{column_name}` IS NOT NULL ORDER BY RAND() LIMIT {limit}"
        elif self.engine.name == "postgresql":
            query = f'SELECT DISTINCT "{column_name}" FROM "{table_name}" WHERE "{column_name}" IS NOT NULL ORDER BY RANDOM() LIMIT {limit}'
        elif self.engine.name == "sqlite":
            query = f'SELECT DISTINCT "{column_name}" FROM "{table_name}" WHERE "{column_name}" IS NOT NULL ORDER BY RANDOM() LIMIT {limit}'
        else:
            query = f'SELECT DISTINCT "{column_name}" FROM "{table_name}" WHERE "{column_name}" IS NOT NULL LIMIT {limit}'

        try:
            results = self.execute_query(query)
            return [row[column_name] for row in results]
        except Exception as e:
            log.warning(
                "Could not fetch unique values for %s.%s: %s",
                table_name,
                column_name,
                e,
            )
            return []

    def get_column_stats(self, table_name: str, column_name: str) -> Dict[str, Any]:
        """Get basic statistics for a column (count, unique_count, min, max)."""
        if not self.engine:
            raise RuntimeError("Database engine is not initialized.")

        quoted_column = f'"{column_name}"'
        quoted_table = f'"{table_name}"'
        if self.engine.name == "mysql":
            quoted_column = f"`{column_name}`"
            quoted_table = f"`{table_name}`"

        query = f"""
            SELECT 
                COUNT(*) as count,
                COUNT(DISTINCT {quoted_column}) as unique_count
            FROM {quoted_table}
            WHERE {quoted_column} IS NOT NULL
        """
        try:
            results = self.execute_query(query)
            return results[0] if results else {}
        except Exception as e:
            log.warning(
                "Could not fetch column stats for %s.%s: %s", table_name, column_name, e
            )
            return {}

    def get_detailed_schema_representation(self) -> Dict[str, Any]:
        """Detect database schema including tables, columns, relationships and sample data.

        Returns:
            Dictionary containing detailed schema information.
        """
        if not self.engine:
            raise RuntimeError("Database engine is not initialized.")

        schema_info: Dict[str, Any] = {}
        tables = self.get_tables()

        for table_name in tables:
            table_details: Dict[str, Any] = {
                "columns": {},
                "primary_keys": self.get_primary_keys(table_name),
                "foreign_keys": self.get_foreign_keys(table_name),
                "indexes": self.get_indexes(table_name),
            }

            columns_data = self.get_columns(table_name)
            for col_data in columns_data:
                col_name = col_data["name"]
                col_info: Dict[str, Any] = {
                    "type": str(col_data["type"]),
                    "nullable": col_data.get("nullable", True),
                    "default": col_data.get("default"),
                    "comment": col_data.get("comment"),
                }

                try:
                    unique_vals = self.get_unique_values(table_name, col_name)
                    if unique_vals:
                        col_info["sample_values"] = unique_vals

                except Exception as sample_err:
                    log.debug(
                        "Could not get sample data/stats for %s.%s: %s",
                        table_name,
                        col_name,
                        sample_err,
                    )

                table_details["columns"][col_name] = col_info
            schema_info[table_name] = table_details
        return schema_info

    def get_schema_summary_for_llm(self) -> str:
        """Gets a YAML formatted summary of the database schema for LLM prompting."""
        if not self.engine:
            raise RuntimeError("Database engine is not initialized.")

        schema_dict = self.get_detailed_schema_representation()

        simplified_schema: Dict[str, Any] = {}
        for table_name, table_data in schema_dict.items():
            simplified_columns: Dict[str, str] = {}
            for col_name, col_details in table_data.get("columns", {}).items():
                simplified_columns[col_name] = col_details.get("type", "UNKNOWN")

            table_summary = {"columns": simplified_columns}
            if table_data.get("primary_keys"):
                table_summary["primary_keys"] = table_data["primary_keys"]

            simplified_schema[table_name] = table_summary

        try:
            return yaml.dump(
                simplified_schema,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )
        except Exception as e:
            log.error("Failed to dump schema to YAML: %s", e)
            summary_lines = []
            for table_name, table_data in simplified_schema.items():
                col_str = ", ".join(
                    [f"{cn} ({ct})" for cn, ct in table_data.get("columns", {}).items()]
                )
                summary_lines.append(f"{table_name}: {col_str}")
            return "\n".join(summary_lines)


class MySQLService(DatabaseService):
    """MySQL database service implementation."""

    def _create_engine(self) -> Engine:
        """Create MySQL database engine."""
        connection_url = sa.URL.create(
            "mysql+mysqlconnector",
            username=self.connection_params.get("user"),
            password=self.connection_params.get("password"),
            host=self.connection_params.get("host"),
            port=self.connection_params.get("port"),
            database=self.connection_params.get("database"),
        )

        return sa.create_engine(
            connection_url,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800,
            pool_pre_ping=True,
            connect_args={"connect_timeout": self.query_timeout},
        )


class PostgresService(DatabaseService):
    """PostgreSQL database service implementation."""

    def _create_engine(self) -> Engine:
        """Create PostgreSQL database engine."""
        connection_url = sa.URL.create(
            "postgresql+psycopg2",
            username=self.connection_params.get("user"),
            password=self.connection_params.get("password"),
            host=self.connection_params.get("host"),
            port=self.connection_params.get("port"),
            database=self.connection_params.get("database"),
        )

        return sa.create_engine(
            connection_url,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800,
            pool_pre_ping=True,
            connect_args={"connect_timeout": self.query_timeout},
        )


class SQLiteService(DatabaseService):
    """SQLite database service implementation."""

    def _create_engine(self) -> Engine:
        """Create SQLite database engine."""
        db_path = self.connection_params.get("database")
        if not db_path:
            raise ValueError("SQLite database path ('database') is required.")

        if db_path == ":memory:":
            connection_url_str = "sqlite:///:memory:"
        else:
            connection_url_str = f"sqlite:///{db_path}"

        return sa.create_engine(
            connection_url_str, connect_args={"timeout": self.query_timeout}
        )
