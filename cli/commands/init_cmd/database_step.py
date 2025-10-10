from pathlib import Path

import click

from ...utils import (
    ask_if_not_provided,
    ask_yes_no_question,
    create_and_validate_database,
)


def prompt_for_db_credentials(
    options: dict, db_type: str, skip_interactive: bool
) -> str:
    if skip_interactive:
        db_url = options.get(f"{db_type}_database_url")
        if not db_url:
            raise ValueError(
                f"Database URL for {db_type} is required in non-interactive mode"
            )
        return db_url

    # Ask which database type to use
    db_backend = ask_if_not_provided(
        {},
        "db_backend",
        f"Which database would you like to use for {db_type}?",
        choices=["sqlite", "postgresql"],
        default="sqlite",
    )

    if db_backend == "postgresql":
        db_url = ask_if_not_provided(
            options,
            f"{db_type}_database_url",
            f"Enter the PostgreSQL URL for {db_type} (e.g., postgresql://user:pass@host:5432/dbname)",
            none_interactive=skip_interactive,
        )
    else:
        # Use SQLite as fallback/default
        return None  # Will be handled by the SQLite setup logic

    return db_url


def database_setup_step(
    project_root: Path, options: dict, skip_interactive: bool
) -> bool:
    click.echo("Setting up database(s)...")

    db_configs = []
    if options.get("add_webui_gateway"):
        db_configs.append(
            ("gateway", "web_ui_gateway_database_url", "webui_gateway.db")
        )
    if options.get("use_orchestrator_db"):
        kebab_name = options.get("agent_name", "orchestrator").lower().replace("_", "-")
        db_configs.append(
            ("orchestrator", "orchestrator_database_url", f"{kebab_name}.db")
        )

    for db_type, url_key, default_filename in db_configs:
        if options.get(url_key):
            database_url = options[url_key]
            click.echo(f"  Using provided database URL for {db_type}.")
        else:
            use_own_db = False
            if not skip_interactive:
                use_own_db = ask_yes_no_question(
                    f"Do you want to use your own database for the {db_type}?",
                    default=False,
                )

            if use_own_db:
                database_url = prompt_for_db_credentials(
                    options, db_type, skip_interactive
                )
            else:
                data_dir = project_root / "data"
                data_dir.mkdir(exist_ok=True)
                db_file = data_dir / default_filename
                database_url = f"sqlite:///{db_file.resolve()}"
                click.echo(f"  Using default SQLite database for {db_type}: {db_file}")

        options[url_key] = database_url

        # Create and validate database connection
        create_and_validate_database(database_url, f"{url_key} database")

    click.echo("  Database setup complete.")
    return True
