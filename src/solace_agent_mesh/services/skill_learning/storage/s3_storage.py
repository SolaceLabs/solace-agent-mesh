"""
S3-based skill resource storage.

Stores skill bundled resources in S3-compatible object storage (AWS S3, MinIO, etc.).
"""

import asyncio
import logging
from typing import Dict, List, Optional

import boto3
from botocore.client import BaseClient
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from .base import BaseSkillResourceStorage, BundledResources

logger = logging.getLogger(__name__)


class S3SkillResourceStorage(BaseSkillResourceStorage):
    """
    Skill resource storage using S3-compatible object storage.
    
    Object key structure:
    {prefix}/skills/{skill_group_id}/{version_id}/scripts/{filename}
    {prefix}/skills/{skill_group_id}/{version_id}/resources/{filename}
    """
    
    def __init__(
        self,
        bucket_name: str,
        prefix: str = "",
        s3_client: Optional[BaseClient] = None,
        **kwargs,
    ):
        """
        Initialize S3 storage.
        
        Args:
            bucket_name: S3 bucket name
            prefix: Optional prefix for all keys (e.g., "sam" -> "sam/skills/...")
            s3_client: Optional pre-configured S3 client
            **kwargs: Additional arguments for boto3 client (endpoint_url, region_name, etc.)
        """
        if not bucket_name:
            raise ValueError("bucket_name cannot be empty")
        
        self.bucket_name = bucket_name
        self.prefix = prefix.strip("/")
        
        if s3_client is None:
            try:
                self.s3 = boto3.client("s3", **kwargs)
            except NoCredentialsError as e:
                logger.error("AWS credentials not found")
                raise ValueError(
                    "AWS credentials not found. Please set AWS_ACCESS_KEY_ID and "
                    "AWS_SECRET_ACCESS_KEY environment variables."
                ) from e
        else:
            self.s3 = s3_client
        
        # Verify bucket access
        try:
            self.s3.head_bucket(Bucket=self.bucket_name)
            logger.info(
                "S3SkillResourceStorage initialized. Bucket: %s, Prefix: %s",
                self.bucket_name,
                self.prefix or "(none)",
            )
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "404":
                raise ValueError(f"S3 bucket '{self.bucket_name}' does not exist") from e
            elif error_code == "403":
                raise ValueError(f"Access denied to S3 bucket '{self.bucket_name}'") from e
            else:
                raise ValueError(f"Failed to access S3 bucket '{self.bucket_name}': {e}") from e
    
    def _get_key_prefix(self, skill_group_id: str, version_id: str) -> str:
        """Get the S3 key prefix for a skill version's resources."""
        parts = ["skills", skill_group_id, version_id]
        if self.prefix:
            parts.insert(0, self.prefix)
        return "/".join(parts)
    
    def get_uri(self, skill_group_id: str, version_id: str) -> str:
        """Get the s3:// URI for a skill version's resources."""
        key_prefix = self._get_key_prefix(skill_group_id, version_id)
        return f"s3://{self.bucket_name}/{key_prefix}/"
    
    async def save_resources(
        self,
        skill_group_id: str,
        version_id: str,
        resources: BundledResources,
    ) -> str:
        """Save bundled resources to S3."""
        log_prefix = f"[S3SkillStorage:Save:{skill_group_id}/{version_id}] "
        
        if resources.is_empty():
            logger.debug("%sNo resources to save", log_prefix)
            return ""
        
        key_prefix = self._get_key_prefix(skill_group_id, version_id)
        saved_count = 0
        
        try:
            # Save scripts
            for filename, content in resources.scripts.items():
                key = f"{key_prefix}/scripts/{filename}"
                await self._put_object(key, content)
                saved_count += 1
                logger.debug("%sSaved script: %s", log_prefix, filename)
            
            # Save resources
            for filename, content in resources.resources.items():
                key = f"{key_prefix}/resources/{filename}"
                await self._put_object(key, content)
                saved_count += 1
                logger.debug("%sSaved resource: %s", log_prefix, filename)
            
            uri = self.get_uri(skill_group_id, version_id)
            logger.info(
                "%sSaved %d files (%d scripts, %d resources) to %s",
                log_prefix,
                saved_count,
                len(resources.scripts),
                len(resources.resources),
                uri,
            )
            return uri
            
        except (ClientError, BotoCoreError) as e:
            logger.error("%sFailed to save resources: %s", log_prefix, e)
            # Attempt cleanup on failure
            await self.delete_resources(skill_group_id, version_id)
            raise OSError(f"Failed to save skill resources to S3: {e}") from e
    
    async def load_resources(
        self,
        skill_group_id: str,
        version_id: str,
    ) -> Optional[BundledResources]:
        """Load bundled resources from S3."""
        log_prefix = f"[S3SkillStorage:Load:{skill_group_id}/{version_id}] "
        
        key_prefix = self._get_key_prefix(skill_group_id, version_id)
        
        try:
            # List all objects under this prefix
            objects = await self._list_objects(key_prefix)
            
            if not objects:
                logger.debug("%sNo resources found", log_prefix)
                return None
            
            scripts = {}
            resources = {}
            
            for obj_key in objects:
                # Parse the key to determine type and filename
                relative_key = obj_key[len(key_prefix):].lstrip("/")
                parts = relative_key.split("/", 1)
                
                if len(parts) != 2:
                    continue
                
                category, filename = parts
                content = await self._get_object(obj_key)
                
                if content is None:
                    continue
                
                if category == "scripts":
                    scripts[filename] = content
                elif category == "resources":
                    resources[filename] = content
            
            result = BundledResources(scripts=scripts, resources=resources)
            logger.info(
                "%sLoaded %d files (%d scripts, %d resources)",
                log_prefix,
                result.total_files(),
                len(scripts),
                len(resources),
            )
            return result
            
        except (ClientError, BotoCoreError) as e:
            logger.error("%sFailed to load resources: %s", log_prefix, e)
            return None
    
    async def load_file(
        self,
        skill_group_id: str,
        version_id: str,
        file_path: str,
    ) -> Optional[bytes]:
        """Load a single file from bundled resources."""
        log_prefix = f"[S3SkillStorage:LoadFile:{skill_group_id}/{version_id}] "
        
        # Validate file path
        if file_path.startswith("..") or file_path.startswith("/"):
            logger.warning("%sInvalid file path: %s", log_prefix, file_path)
            return None
        
        key_prefix = self._get_key_prefix(skill_group_id, version_id)
        key = f"{key_prefix}/{file_path}"
        
        try:
            content = await self._get_object(key)
            if content is not None:
                logger.debug("%sLoaded file: %s (%d bytes)", log_prefix, file_path, len(content))
            else:
                logger.debug("%sFile not found: %s", log_prefix, file_path)
            return content
        except (ClientError, BotoCoreError) as e:
            logger.error("%sFailed to load file %s: %s", log_prefix, file_path, e)
            return None
    
    async def delete_resources(
        self,
        skill_group_id: str,
        version_id: str,
    ) -> bool:
        """Delete all bundled resources for a skill version."""
        log_prefix = f"[S3SkillStorage:Delete:{skill_group_id}/{version_id}] "
        
        key_prefix = self._get_key_prefix(skill_group_id, version_id)
        
        try:
            # List all objects under this prefix
            objects = await self._list_objects(key_prefix)
            
            if not objects:
                logger.debug("%sNo resources to delete", log_prefix)
                return False
            
            # Delete objects in batches (S3 allows up to 1000 per request)
            deleted_count = 0
            for i in range(0, len(objects), 1000):
                batch = objects[i:i + 1000]
                delete_objects = [{"Key": key} for key in batch]
                
                def _delete_batch():
                    return self.s3.delete_objects(
                        Bucket=self.bucket_name,
                        Delete={"Objects": delete_objects},
                    )
                
                await asyncio.to_thread(_delete_batch)
                deleted_count += len(batch)
            
            logger.info("%sDeleted %d objects", log_prefix, deleted_count)
            return True
            
        except (ClientError, BotoCoreError) as e:
            logger.error("%sFailed to delete resources: %s", log_prefix, e)
            return False
    
    async def list_files(
        self,
        skill_group_id: str,
        version_id: str,
    ) -> Dict[str, List[str]]:
        """List all files in bundled resources."""
        log_prefix = f"[S3SkillStorage:List:{skill_group_id}/{version_id}] "
        
        key_prefix = self._get_key_prefix(skill_group_id, version_id)
        result = {"scripts": [], "resources": []}
        
        try:
            objects = await self._list_objects(key_prefix)
            
            for obj_key in objects:
                relative_key = obj_key[len(key_prefix):].lstrip("/")
                parts = relative_key.split("/", 1)
                
                if len(parts) != 2:
                    continue
                
                category, filename = parts
                if category == "scripts":
                    result["scripts"].append(filename)
                elif category == "resources":
                    result["resources"].append(filename)
            
            result["scripts"].sort()
            result["resources"].sort()
            
            logger.debug(
                "%sFound %d scripts, %d resources",
                log_prefix,
                len(result["scripts"]),
                len(result["resources"]),
            )
            return result
            
        except (ClientError, BotoCoreError) as e:
            logger.error("%sFailed to list files: %s", log_prefix, e)
            return result
    
    async def exists(
        self,
        skill_group_id: str,
        version_id: str,
    ) -> bool:
        """Check if bundled resources exist for a skill version."""
        key_prefix = self._get_key_prefix(skill_group_id, version_id)
        
        try:
            objects = await self._list_objects(key_prefix, max_keys=1)
            return len(objects) > 0
        except (ClientError, BotoCoreError):
            return False
    
    async def _put_object(self, key: str, content: bytes) -> None:
        """Put an object to S3."""
        def _put():
            return self.s3.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=content,
            )
        await asyncio.to_thread(_put)
    
    async def _get_object(self, key: str) -> Optional[bytes]:
        """Get an object from S3."""
        def _get():
            try:
                response = self.s3.get_object(Bucket=self.bucket_name, Key=key)
                return response["Body"].read()
            except ClientError as e:
                if e.response.get("Error", {}).get("Code") == "NoSuchKey":
                    return None
                raise
        return await asyncio.to_thread(_get)
    
    async def _list_objects(self, prefix: str, max_keys: int = 10000) -> List[str]:
        """List objects under a prefix."""
        def _list():
            keys = []
            paginator = self.s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(
                Bucket=self.bucket_name,
                Prefix=prefix,
                PaginationConfig={"MaxItems": max_keys},
            ):
                for obj in page.get("Contents", []):
                    keys.append(obj["Key"])
            return keys
        return await asyncio.to_thread(_list)