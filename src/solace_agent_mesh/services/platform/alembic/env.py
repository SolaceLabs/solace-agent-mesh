from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.ext.declarative import declarative_base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Create a placeholder Base for future community platform models
# When community models are added, import them here to ensure they are registered
Base = declarative_base()

# Import all models here to ensure they are registered with the Base
# Example:
# from solace_agent_mesh.services.platform.models.example_model import ExampleModel

target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

SQLALCHEMY_URL_KEY = "sqlalchemy.url"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option(SQLALCHEMY_URL_KEY)
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
    # Get the database URL from the Alembic config
    url = config.get_main_option(SQLALCHEMY_URL_KEY)
    if not url:
        raise ValueError(
            f"Database URL is not set. Please set {SQLALCHEMY_URL_KEY} in alembic.ini or via command line."
        )

    # Create a configuration dictionary for the engine
    # This ensures that the URL is correctly picked up by engine_from_config
    engine_config = {SQLALCHEMY_URL_KEY: url}

    connectable = engine_from_config(
        engine_config,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
