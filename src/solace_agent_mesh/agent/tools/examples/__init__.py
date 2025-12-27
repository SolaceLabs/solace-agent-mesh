"""
Example tools demonstrating migration patterns.

This package contains example tools that demonstrate how to migrate existing
tools to use the new patterns:

- ToolResult with DataObject for automatic artifact handling
- ArtifactContent type hint for artifact pre-loading
- ToolContextFacade for simplified context access

See MIGRATION_GUIDE.md for detailed documentation.

Examples:
- migrated_jmespath_tool.py: Uses ArtifactContent for automatic pre-loading
- migrated_sql_tool.py: Uses ctx.load_artifact() for dynamic loading
"""

from .migrated_jmespath_tool import transform_data_with_jmespath
from .migrated_sql_tool import query_data_with_sql

__all__ = [
    "transform_data_with_jmespath",
    "query_data_with_sql",
]
