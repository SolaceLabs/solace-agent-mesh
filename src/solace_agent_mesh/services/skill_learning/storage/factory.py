"""
Factory for creating skill resource storage instances.

Creates the appropriate storage backend based on configuration.
"""

import logging
from typing import Any, Dict, Optional

from .base import BaseSkillResourceStorage
from .filesystem_storage import FilesystemSkillResourceStorage
from .s3_storage import S3SkillResourceStorage

logger = logging.getLogger(__name__)


def create_skill_resource_storage(
    config: Optional[Dict[str, Any]] = None,
) -> Optional[BaseSkillResourceStorage]:
    """
    Create a skill resource storage instance based on configuration.
    
    Configuration format:
    ```yaml
    resource_storage:
      type: filesystem  # or "s3"
      
      # Filesystem options
      filesystem:
        base_path: ./data/skill_resources
      
      # S3 options
      s3:
        bucket_name: sam-skill-resources
        prefix: ""  # Optional key prefix
        endpoint_url: null  # For MinIO: http://minio:9000
        region_name: us-east-1
    ```
    
    Args:
        config: Storage configuration dictionary. If None or empty, returns None.
        
    Returns:
        Configured storage instance, or None if storage is not configured.
        
    Raises:
        ValueError: If configuration is invalid.
    """
    if not config:
        logger.debug("No resource storage configuration provided")
        return None
    
    storage_type = config.get("type", "filesystem").lower()
    
    if storage_type == "filesystem":
        return _create_filesystem_storage(config.get("filesystem", {}))
    elif storage_type == "s3":
        return _create_s3_storage(config.get("s3", {}))
    else:
        raise ValueError(f"Unknown storage type: {storage_type}. Must be 'filesystem' or 's3'.")


def _create_filesystem_storage(config: Dict[str, Any]) -> FilesystemSkillResourceStorage:
    """Create filesystem storage from configuration."""
    base_path = config.get("base_path")
    
    if not base_path:
        # Default to ./data/skill_resources
        base_path = "./data/skill_resources"
        logger.info("Using default filesystem storage path: %s", base_path)
    
    return FilesystemSkillResourceStorage(base_path=base_path)


def _create_s3_storage(config: Dict[str, Any]) -> S3SkillResourceStorage:
    """Create S3 storage from configuration."""
    bucket_name = config.get("bucket_name")
    
    if not bucket_name:
        raise ValueError("S3 storage requires 'bucket_name' configuration")
    
    # Build kwargs for boto3 client
    kwargs = {}
    
    if config.get("endpoint_url"):
        kwargs["endpoint_url"] = config["endpoint_url"]
    
    if config.get("region_name"):
        kwargs["region_name"] = config["region_name"]
    
    if config.get("aws_access_key_id"):
        kwargs["aws_access_key_id"] = config["aws_access_key_id"]
    
    if config.get("aws_secret_access_key"):
        kwargs["aws_secret_access_key"] = config["aws_secret_access_key"]
    
    return S3SkillResourceStorage(
        bucket_name=bucket_name,
        prefix=config.get("prefix", ""),
        **kwargs,
    )


def create_storage_from_uri(uri: str) -> Optional[BaseSkillResourceStorage]:
    """
    Create a storage instance from a URI.
    
    This is useful for loading resources when you only have the URI.
    
    Args:
        uri: Storage URI (e.g., "s3://bucket/prefix/" or "file:///path/")
        
    Returns:
        Storage instance configured for the URI, or None if URI is invalid.
    """
    if not uri:
        return None
    
    if uri.startswith("file://"):
        # Extract base path from file:// URI
        # URI format: file:///path/to/skills/{group_id}/{version_id}/
        path = uri[7:]  # Remove "file://"
        
        # Find the skills directory to use as base path
        if "/skills/" in path:
            base_path = path.split("/skills/")[0]
            return FilesystemSkillResourceStorage(base_path=base_path)
        else:
            logger.warning("Invalid file:// URI format: %s", uri)
            return None
    
    elif uri.startswith("s3://"):
        # Extract bucket and prefix from s3:// URI
        # URI format: s3://bucket/prefix/skills/{group_id}/{version_id}/
        path = uri[5:]  # Remove "s3://"
        parts = path.split("/", 1)
        
        if len(parts) < 1:
            logger.warning("Invalid s3:// URI format: %s", uri)
            return None
        
        bucket_name = parts[0]
        prefix = ""
        
        if len(parts) > 1:
            # Extract prefix (everything before /skills/)
            remaining = parts[1]
            if "/skills/" in remaining:
                prefix = remaining.split("/skills/")[0]
        
        return S3SkillResourceStorage(bucket_name=bucket_name, prefix=prefix)
    
    else:
        logger.warning("Unknown URI scheme: %s", uri)
        return None