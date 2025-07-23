"""
Lifecycle functions (initialization and cleanup) and Pydantic configuration model
for the MongoDB Agent Plugin.
"""

from typing import Any, Dict, List, Optional, Literal

from pydantic import BaseModel, Field, SecretStr, model_validator

try:
    from solace_ai_connector.common.log import log
except ImportError:
    import logging

    log = logging.getLogger(__name__)

from .services.database_service import MongoDatabaseService


class MongoAgentInitConfigModel(BaseModel):
    """
    Pydantic model for the configuration of the MongoDB Agent's
    initialize_mongo_agent function.
    """

    db_host: str = Field(description="MongoDB host.")
    db_port: int = Field(description="MongoDB port.")
    db_user: Optional[str] = Field(default=None, description="MongoDB user.")
    db_password: Optional[SecretStr] = Field(
        default=None, description="MongoDB password."
    )
    db_name: str = Field(description="Database name.")
    database_collection: Optional[str] = Field(
        default=None,
        description="Specific collection to target. If omitted, agent can query across all collections.",
    )
    query_timeout: int = Field(
        default=30, description="Query timeout in seconds.", ge=5
    )
    database_purpose: str = Field(
        description="A clear description of the purpose of this database."
    )
    data_description: str = Field(
        description="A detailed description of the data stored in the database/collections."
    )
    auto_detect_schema: bool = Field(
        default=True, description="If true, automatically detect schema."
    )
    max_inline_results: int = Field(
        default=10,
        description="Maximum number of results to return inline before using a file.",
    )


def initialize_mongo_agent(host_component: Any, init_config: MongoAgentInitConfigModel):
    """
    Initializes the MongoDB Agent.
    - Connects to the database.
    - Detects or loads schema information.
    - Stores necessary objects and info in host_component.agent_specific_state.
    """
    log_identifier = f"[{host_component.agent_name}:init_mongo_agent]"
    log.info("%s Starting MongoDB Agent initialization...", log_identifier)

    connection_params = {
        "host": init_config.db_host,
        "port": init_config.db_port,
        "user": init_config.db_user,
        "password": (
            init_config.db_password.get_secret_value()
            if init_config.db_password
            else None
        ),
        "database": init_config.db_name,
    }

    try:
        db_service = MongoDatabaseService(connection_params, init_config.query_timeout)
        log.info(
            "%s DatabaseService for MongoDB initialized successfully.", log_identifier
        )
    except Exception as e:
        log.exception("%s Failed to initialize DatabaseService: %s", log_identifier, e)
        raise RuntimeError(f"DatabaseService initialization failed: {e}") from e

    schema_summary_for_llm = ""
    if init_config.auto_detect_schema:
        log.info("%s Auto-detecting database schema...", log_identifier)
        collections_to_scan = (
            [init_config.database_collection]
            if init_config.database_collection
            else None
        )
        schema_summary_for_llm = db_service.get_schema_summary_for_llm(
            collections_to_scan
        )
        log.info("%s Schema auto-detection complete.", log_identifier)
    else:
        log.warning(
            "%s Schema auto-detection is disabled. The LLM will rely solely on the data description.",
            log_identifier,
        )

    try:
        host_component.set_agent_specific_state("db_handler", db_service)
        host_component.set_agent_specific_state(
            "db_schema_summary_for_prompt", schema_summary_for_llm
        )
        host_component.set_agent_specific_state(
            "max_inline_results", init_config.max_inline_results
        )
        log.info(
            "%s Stored database handler and schema information in agent_specific_state.",
            log_identifier,
        )
    except Exception as e:
        log.exception(
            "%s Failed to store data in agent_specific_state: %s", log_identifier, e
        )
        raise

    try:
        instruction_parts = [
            "You are a MongoDB expert assistant.",
            "Your primary goal is to translate user questions into accurate MongoDB aggregation pipelines.",
            "When asked to query the database, generate the pipeline and call the query tool.",
            "\nDATABASE CONTEXT:",
            f"Purpose: {init_config.database_purpose}",
            f"Data Description: {init_config.data_description}",
        ]
        if schema_summary_for_llm:
            instruction_parts.extend(
                [
                    "\nDATABASE SCHEMA:",
                    "---",
                    schema_summary_for_llm,
                    "---",
                ]
            )

        final_system_instruction = "\n".join(instruction_parts)
        host_component.set_agent_system_instruction_string(final_system_instruction)
        log.info(
            "%s System instruction string for MongoDB agent has been set.",
            log_identifier,
        )

    except Exception as e:
        log.error(
            f"{log_identifier} Failed to construct or set system instruction for MongoDB agent: {e}",
            exc_info=True,
        )

    log.info("%s MongoDB Agent initialization completed successfully.", log_identifier)


def cleanup_mongo_agent_resources(host_component: Any):
    """
    Cleans up resources used by the MongoDB Agent, primarily closing the database connection.
    """
    log_identifier = f"[{host_component.agent_name}:cleanup_mongo_agent]"
    log.info("%s Cleaning up MongoDB Agent resources...", log_identifier)

    db_service: Optional[MongoDatabaseService] = (
        host_component.get_agent_specific_state("db_handler")
    )

    if db_service:
        try:
            db_service.close()
            log.info("%s DatabaseService closed successfully.", log_identifier)
        except Exception as e:
            log.error(
                f"{log_identifier} Error closing DatabaseService: {e}", exc_info=True
            )
    else:
        log.info(
            "%s No DatabaseService instance found in agent_specific_state to clean up.",
            log_identifier,
        )

    log.info("%s MongoDB Agent resource cleanup finished.", log_identifier)
