"""
Service for handling all interactions with a MongoDB database.
"""

from typing import Any, Dict, List, Optional, Tuple
import pymongo
from pymongo.errors import ConnectionFailure, OperationFailure
from solace_ai_connector.common.log import log
import yaml


class MongoDatabaseService:
    """A service to manage MongoDB connections and operations."""

    def __init__(self, connection_params: Dict[str, Any], query_timeout: int = 30):
        """
        Initializes the MongoDB service and establishes a connection.

        Args:
            connection_params: Dictionary with connection details ('host', 'port', 'user', 'password', 'database').
            query_timeout: The timeout in seconds for database operations.
        """
        self.client: Optional[pymongo.MongoClient] = None
        self.db: Optional[pymongo.database.Database] = None
        self.query_timeout = query_timeout
        self._connect(connection_params)

    def _connect(self, params: Dict[str, Any]):
        """Establishes the connection to the MongoDB server."""
        log_identifier = "[MongoDatabaseService:_connect]"
        try:
            host = params.get("host", "localhost")
            port = params.get("port", 27017)
            user = params.get("user")
            password = params.get("password")
            db_name = params.get("database")

            if not db_name:
                raise ValueError("Database name is required.")

            self.client = pymongo.MongoClient(
                host,
                port,
                username=user,
                password=password,
                serverSelectionTimeoutMS=self.query_timeout * 1000,
            )
            self.client.admin.command("ismaster")
            self.db = self.client[db_name]
            log.info(
                "%s Successfully connected to MongoDB at %s:%s.",
                log_identifier,
                host,
                port,
            )
        except ConnectionFailure as e:
            log.error(f"{log_identifier} MongoDB connection failed: {e}")
            raise
        except Exception as e:
            log.error(
                f"{log_identifier} An unexpected error occurred during connection: {e}"
            )
            raise

    def close(self):
        """Closes the MongoDB connection."""
        if self.client:
            self.client.close()
            log.info("[MongoDatabaseService:close] MongoDB connection closed.")

    def get_collections(self) -> List[str]:
        """Returns a list of all collection names in the database."""
        if self.db is None:
            raise RuntimeError("Database not connected.")
        return self.db.list_collection_names()

    def get_fields(
        self, collection_name: str, num_docs_to_sample: int = 5
    ) -> List[str]:
        """
        Gets a comprehensive list of fields for a collection by sampling documents.
        """
        if self.db is None:
            raise RuntimeError("Database not connected.")
        collection = self.db[collection_name]
        fields = set()
        for doc in collection.find().limit(num_docs_to_sample):
            for key in doc.keys():
                fields.add(key)
        return sorted(list(fields))

    def get_sample_values(
        self, collection_name: str, field: str, limit: int = 5
    ) -> Tuple[List[Any], bool]:
        """Gets a sample of unique values for a given field."""
        if self.db is None:
            raise RuntimeError("Database not connected.")
        collection = self.db[collection_name]
        try:
            distinct_values = collection.distinct(field)
            if len(distinct_values) > limit:
                return distinct_values[:limit], False
            return distinct_values, True
        except OperationFailure as e:
            log.warning("Could not get distinct values for field '%s': %s", field, e)
            return [], False

    def execute_query(self, collection_name: str, pipeline: List[Dict]) -> List[Dict]:
        """Executes a MongoDB aggregation pipeline."""
        if self.db is None:
            raise RuntimeError("Database not connected.")
        log.debug(f"Executing pipeline on collection '{collection_name}': {pipeline}")
        collection = self.db[collection_name]
        return list(collection.aggregate(pipeline))

    def get_schema_summary_for_llm(
        self, collections_to_scan: Optional[List[str]] = None
    ) -> str:
        """
        Detects the database schema and generates a YAML summary for the LLM.
        """
        log_identifier = "[MongoDatabaseService:get_schema_summary_for_llm]"
        log.info("%s Starting schema detection...", log_identifier)

        schema_representation = {}
        collections = collections_to_scan or self.get_collections()

        for collection_name in collections:
            log.debug(f"{log_identifier} Analyzing collection: {collection_name}")
            fields = self.get_fields(collection_name)
            field_details = {}
            for field in fields:
                sample_values, all_values_included = self.get_sample_values(
                    collection_name, field
                )
                safe_sample_values = [str(v) for v in sample_values]

                note = "all unique values" if all_values_included else "examples"
                field_details[field] = f"({note}: {', '.join(safe_sample_values)})"

            schema_representation[collection_name] = field_details

        log.info(f"{log_identifier} Schema detection complete.")
        return yaml.dump(schema_representation, sort_keys=False, allow_unicode=True)
