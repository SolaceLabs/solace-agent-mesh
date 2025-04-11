import json

from .base_history_provider import BaseHistoryProvider
from ....common.postgres_database import PostgreSQLDatabase
from ....common.mysql_database import MySQLDatabase


class DatabaseFactory:
    """
    Factory class to create database instances.
    """
    DATABASE_PROVIDERS = {
        "postgres": PostgreSQLDatabase,
        "mysql": MySQLDatabase,
    }

    @staticmethod
    def get_database(db_type, **kwargs):
        if db_type not in DatabaseFactory.DATABASE_PROVIDERS:
            raise ValueError(f"Unsupported database type: {db_type}")
        return DatabaseFactory.DATABASE_PROVIDERS[db_type](**kwargs)

class SQLHistoryProvider(BaseHistoryProvider):
    """
    A history provider that stores session history in a SQL database.
    """
    def __init__(self, config=None):
        super().__init__(config)
        self.db_type = self.config.get("db_type", "postgres")
        self.table_name = self.config.get("table_name", "session_history")
        self.db = DatabaseFactory.get_database(
            self.db_type,
            host=self.config.get("sql_host"),
            user=self.config.get("sql_user"),
            password=self.config.get("sql_password"),
            database=self.config.get("sql_database"),
        )
        self._ensure_table_exists()
    
    def _ensure_table_exists(self):
        """
        Ensures the required table exists in the database.
        """
        query = f"""
        CREATE TABLE IF NOT EXISTS {self.table_name} (
            session_id TEXT PRIMARY KEY,
            data JSON
        )
        """
        self.db.execute(query)
    
    def store_session(self, session_id: str, data: dict):
        """
        Store or update session metadata.
        """
        query = f"""
        INSERT INTO {self.table_name} (session_id, data) 
        VALUES (%s, %s) 
        ON CONFLICT (session_id) DO UPDATE 
        SET data = EXCLUDED.data
        """ if self.db_type == "postgres" else f"""
        INSERT INTO {self.table_name} (session_id, data) 
        VALUES (%s, %s) 
        ON DUPLICATE KEY UPDATE data = VALUES(data)
        """
        self.db.execute(query, (session_id, json.dumps(data)))
    
    def get_session(self, session_id: str) -> dict:
        """
        Retrieve a session by ID.
        """
        query = f"SELECT data FROM {self.table_name} WHERE session_id = %s"
        cursor = self.db.execute(query, (session_id,))
        row = cursor.fetchone()
        if not row.get("data"):
            return {}
        data = row["data"] if isinstance(row["data"], dict) else json.loads(row["data"])
        return data
    
    def get_all_sessions(self) -> list[str]:
        """
        Retrieve all session identifiers.
        """
        query = f"SELECT session_id FROM {self.table_name}"
        cursor = self.db.execute(query)
        return [row["session_id"] for row in cursor.fetchall()]
    
    def delete_session(self, session_id: str):
        """
        Delete a session by ID, ensuring only one row is deleted.
        """
        query = f"DELETE FROM {self.table_name} WHERE session_id = %s LIMIT 1"
        self.db.execute(query, (session_id,))