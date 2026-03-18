"""Debug script to test alembic configuration."""
from pathlib import Path
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, inspect

# Setup paths
script_location = str(
    Path(__file__).parent.parent.parent.parent.parent
    / "src" / "solace_agent_mesh" / "gateway" / "http_sse" / "alembic"
)

print(f"Script location: {script_location}")
print(f"Exists: {Path(script_location).exists()}")

# Create config
config = Config()
config.set_main_option("script_location", script_location)

# Test with SQLite
db_url = "sqlite:///test_debug.db"
config.set_main_option("sqlalchemy.url", db_url)

print(f"\nAttempting to run migrations...")
print(f"Database URL: {db_url}")

try:
    # Run upgrade
    command.upgrade(config, "head")
    print("✅ Migration succeeded!")

    # Inspect database
    engine = create_engine(db_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"\nTables created: {tables}")

except Exception as e:
    print(f"❌ Migration failed: {e}")
    import traceback
    traceback.print_exc()