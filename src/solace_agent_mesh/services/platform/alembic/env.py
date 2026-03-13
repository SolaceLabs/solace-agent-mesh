from alembic import context
from sqlalchemy import engine_from_config, pool
from solace_agent_mesh.shared.database.base import Base
from solace_agent_mesh.shared.outbox.models import OutboxEventModel  # noqa: F401

config = context.config

# Import Base and all models to register them with the metadata
from solace_agent_mesh.services.platform.models.base import Base
from solace_agent_mesh.services.platform.models.model_configuration import ModelConfiguration  # noqa: F401

target_metadata = Base.metadata

SQLALCHEMY_URL_KEY = "sqlalchemy.url"


def run_migrations_offline() -> None:
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
    url = config.get_main_option(SQLALCHEMY_URL_KEY)
    if not url:
        raise ValueError(
            f"Database URL is not set. Please set {SQLALCHEMY_URL_KEY} in alembic.ini or via command line."
        )

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
