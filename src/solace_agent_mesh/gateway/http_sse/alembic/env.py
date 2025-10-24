from logging.config import fileConfig
import os

from alembic import context
from sqlalchemy import engine_from_config, pool

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Override sqlalchemy.url from environment variable if set
# This allows alembic to use the same database URL as the application
db_url = os.getenv("WEB_UI_GATEWAY_DATABASE_URL")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
from solace_agent_mesh.gateway.http_sse.repository.models.base import Base

# Import all models here to ensure they are registered with the Base
from solace_agent_mesh.gateway.http_sse.repository.models.task_model import TaskModel
from solace_agent_mesh.gateway.http_sse.repository.models.task_event_model import (
    TaskEventModel,
)
from solace_agent_mesh.gateway.http_sse.repository.models.feedback_model import (
    FeedbackModel,
)
from solace_agent_mesh.gateway.http_sse.repository.models.session_model import (
    SessionModel,
)
from solace_agent_mesh.gateway.http_sse.repository.models.chat_task_model import (
    ChatTaskModel,
)
from solace_agent_mesh.gateway.http_sse.repository.models.project_model import (
    ProjectModel,
)
from solace_agent_mesh.gateway.http_sse.repository.models.project_user_model import (
    ProjectUserModel,
)

target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Check if a connection was provided in config attributes (for testing)
    connectable = config.attributes.get('connection', None)
    
    if connectable is None:
        # Get the database URL from the Alembic config
        url = config.get_main_option("sqlalchemy.url")
        if not url:
            raise ValueError(
                "Database URL is not set. Please set sqlalchemy.url in alembic.ini or via command line."
            )

        # Create a configuration dictionary for the engine
        # This ensures that the URL is correctly picked up by engine_from_config
        engine_config = {"sqlalchemy.url": url}

        connectable = engine_from_config(
            engine_config,
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

    if connectable is None:
        raise ValueError("No connection or database URL available for migrations")
    
    # If connectable is a connection, use it directly; otherwise connect to the engine
    if hasattr(connectable, 'execute'):
        # It's already a connection
        context.configure(connection=connectable, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    else:
        # It's an engine, so we need to connect
        with connectable.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
