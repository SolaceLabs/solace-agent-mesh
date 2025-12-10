#!/usr/bin/env python3
"""
Backfill script to migrate existing filesystem-based apps into the database.

This script scans the workspace directory for existing apps and creates
database entries for any apps that don't already have them.

Usage:
    python scripts/backfill_apps.py
"""

import json
import os
import sys
import uuid
from pathlib import Path

# Add parent directory to path so we can import from src
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.solace_agent_mesh.gateway.http_sse.repository.app_repository import AppRepository
from src.solace_agent_mesh.gateway.http_sse.repository.models.app_model import AppModel


def get_workspace_base() -> str:
    """Get workspace base directory from environment or default."""
    return os.getenv("WORKSPACE_BASE", os.path.expanduser("~/.claude-workspaces"))


def scan_existing_apps(workspace_base: Path) -> list[dict]:
    """
    Scan workspace directory for existing apps.

    Returns list of app metadata dictionaries.
    """
    apps = []

    if not workspace_base.exists():
        print(f"Workspace base directory does not exist: {workspace_base}")
        return apps

    # Iterate through user directories
    for user_dir in workspace_base.iterdir():
        if not user_dir.is_dir():
            continue

        user_id = user_dir.name
        apps_dir = user_dir / "apps"

        if not apps_dir.exists():
            continue

        # Iterate through app directories
        for app_dir in apps_dir.iterdir():
            if not app_dir.is_dir():
                continue

            app_id = app_dir.name
            package_json_path = app_dir / "package.json"

            if not package_json_path.exists():
                print(f"  Skipping {app_dir}: no package.json")
                continue

            # Read package.json for app metadata
            try:
                with open(package_json_path) as f:
                    package_json = json.load(f)

                # Extract name from description or use app_id
                description = package_json.get("description", "")
                if description.startswith("SAM App: "):
                    name = description.replace("SAM App: ", "")
                else:
                    name = app_id.replace("-", " ").title()

                # Get timestamps from directory
                created_time = int(app_dir.stat().st_ctime * 1000)
                updated_time = int(app_dir.stat().st_mtime * 1000)

                apps.append({
                    "user_id": user_id,
                    "app_id": app_id,
                    "name": name,
                    "description": description if description else None,
                    "workspace_id": app_id,
                    "created_time": created_time,
                    "updated_time": updated_time,
                })

                print(f"  Found app: {user_id}/{app_id} - {name}")

            except Exception as e:
                print(f"  Error reading {package_json_path}: {e}")
                continue

    return apps


def backfill_apps(db_url: str):
    """
    Backfill existing apps from filesystem into database.
    """
    print("Starting app backfill...")

    # Create database connection
    engine = create_engine(db_url)
    session = Session(engine)

    # Initialize repository
    app_repository = AppRepository()

    # Scan filesystem for existing apps
    workspace_base = Path(get_workspace_base())
    print(f"\nScanning workspace directory: {workspace_base}")
    apps = scan_existing_apps(workspace_base)

    if not apps:
        print("\nNo apps found to backfill.")
        return

    print(f"\nFound {len(apps)} app(s) on filesystem")
    print("\nBackfilling into database...")

    created_count = 0
    skipped_count = 0

    for app_data in apps:
        try:
            # Check if app already exists in database
            existing = app_repository.get_by_id(
                session,
                app_data["app_id"],
                app_data["user_id"]
            )

            if existing:
                print(f"  Skipped (already in DB): {app_data['user_id']}/{app_data['app_id']}")
                skipped_count += 1
                continue

            # Create database entry
            app_repository.create(
                session,
                app_id=app_data["app_id"],
                user_id=app_data["user_id"],
                name=app_data["name"],
                workspace_id=app_data["workspace_id"],
                description=app_data["description"],
                status="draft",
            )

            print(f"  Created: {app_data['user_id']}/{app_data['app_id']} - {app_data['name']}")
            created_count += 1

        except Exception as e:
            print(f"  Error creating {app_data['app_id']}: {e}")
            continue

    session.close()

    print(f"\n✅ Backfill complete!")
    print(f"   Created: {created_count}")
    print(f"   Skipped: {skipped_count}")
    print(f"   Total:   {len(apps)}")


if __name__ == "__main__":
    # Get database URL from environment or use default
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql://localhost/solace_agent_mesh"
    )

    print(f"Database URL: {db_url}")

    try:
        backfill_apps(db_url)
    except Exception as e:
        print(f"\n❌ Error during backfill: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
