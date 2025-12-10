#!/usr/bin/env python3
"""Quick script to add test8 app to database."""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.solace_agent_mesh.gateway.http_sse.repository.app_repository import AppRepository

# Configuration
workspace_base = Path(os.getenv("WORKSPACE_BASE", os.path.expanduser("~/.claude-workspaces")))
db_url = os.getenv("DATABASE_URL", "sqlite:///webui-gateway.db")

print(f"Workspace base: {workspace_base}")
print(f"Database URL: {db_url}")

# Find test8 app
test8_path = None
user_id = None

for user_dir in workspace_base.iterdir():
    if not user_dir.is_dir():
        continue

    apps_dir = user_dir / "apps"
    if not apps_dir.exists():
        continue

    test8_candidate = apps_dir / "test8"
    if test8_candidate.exists():
        test8_path = test8_candidate
        user_id = user_dir.name
        break

if not test8_path:
    print("❌ Could not find test8 app in workspace")
    sys.exit(1)

print(f"\n✅ Found test8 at: {test8_path}")
print(f"   User ID: {user_id}")

# Read package.json
package_json_path = test8_path / "package.json"
if not package_json_path.exists():
    print("❌ No package.json found")
    sys.exit(1)

with open(package_json_path) as f:
    package_json = json.load(f)

description = package_json.get("description", "")
if description.startswith("SAM App: "):
    name = description.replace("SAM App: ", "")
else:
    name = "Test8"

print(f"   Name: {name}")
print(f"   Description: {description}")

# Create database entry
engine = create_engine(db_url)
session = Session(engine)
app_repository = AppRepository()

# Check if already exists
existing = app_repository.get_by_id(session, "test8", user_id)
if existing:
    print("\n⚠️  test8 already exists in database")
    session.close()
    sys.exit(0)

# Create app
app_repository.create(
    session,
    app_id="test8",
    user_id=user_id,
    name=name,
    workspace_id="test8",
    description=description if description else None,
    status="draft",
)

session.close()

print("\n✅ Successfully added test8 to database!")
