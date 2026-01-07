"""
Helper functions for storing BM25 indexes with folder-based structure.

Supports both filesystem and S3 storage backends.
"""

import os
import json
import asyncio
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


async def save_bm25_index_filesystem(
    artifact_service,
    app_name: str,
    user_id: str,
    session_id: str,
    index_name: str,
    index_files: Dict[str, Path],
    metadata: Dict,
) -> Optional[int]:
    """
    Save BM25 index files to filesystem with folder-based structure.
    
    Structure:
    {base_path}/{app_name}/{user_id}/{session_id}/{index_name}/
      ├── 0                     # Version 0 marker file (for list_versions detection)
      ├── 0_data/               # Version 0 data folder
      │   ├── bm25_index.pkl
      │   ├── metadata.json
      │   └── corpus.pkl
      ├── 0.meta                # Metadata for version 0
      ├── 1                     # Version 1 marker file
      ├── 1_data/               # Version 1 data folder
      │   ├── bm25_index.pkl
      │   ├── metadata.json
      │   └── corpus.pkl
      └── 1.meta                # Metadata for version 1
    
    Args:
        artifact_service: FilesystemArtifactService instance
        app_name: Application name
        user_id: User ID
        session_id: Session ID
        index_name: Name of the index artifact
        index_files: Dict mapping filenames to their Path objects
        metadata: Metadata to store with the index
    
    Returns:
        Version number of created index, or None if failed
    """
    try:
        # Get the artifact directory path
        artifact_dir = artifact_service._get_artifact_dir(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=index_name
        )
        
        # Create artifact directory if it doesn't exist
        await asyncio.to_thread(os.makedirs, artifact_dir, exist_ok=True)
        
        # Determine the next version number
        versions = await artifact_service.list_versions(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=index_name,
        )
        version = 0 if not versions else max(versions) + 1
        
        # Create a version marker file FIRST so list_versions() can detect this version
        # FilesystemArtifactService.list_versions() looks for numeric files, not directories
        # We must create this before the folder to avoid name conflict
        version_marker_path = os.path.join(artifact_dir, str(version))
        
        def _create_version_marker():
            # Create an empty marker file with the version number as filename
            with open(version_marker_path, 'w') as f:
                f.write('')  # Empty file, just a marker
                f.flush()
                os.fsync(f.fileno())
        
        await asyncio.to_thread(_create_version_marker)
        logger.debug(f"Created version marker file: {version_marker_path}")
        
        # Create version folder (use a different name to avoid conflict with marker file)
        # Use pattern: {version}_data/ instead of {version}/
        version_folder = os.path.join(artifact_dir, f"{version}_data")
        await asyncio.to_thread(os.makedirs, version_folder, exist_ok=True)
        
        # Copy all index files to the version folder
        import shutil
        files_copied = 0
        for filename, file_path in index_files.items():
            dest_file = os.path.join(version_folder, filename)
            
            def _copy_file():
                shutil.copy2(file_path, dest_file)
            
            await asyncio.to_thread(_copy_file)
            files_copied += 1
            logger.debug(f"Copied {filename} to {dest_file}")
        
        # Create metadata file for this version
        metadata_path = os.path.join(artifact_dir, f"{version}.meta")
        metadata["num_files"] = files_copied
        
        def _write_metadata():
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
        
        await asyncio.to_thread(_write_metadata)
        
        logger.info(
            f"✓ Saved BM25 index to filesystem: {index_name} v{version} "
            f"({files_copied} files) at {version_folder}"
        )
        
        return version
        
    except Exception as e:
        logger.error(f"Error saving BM25 index to filesystem: {e}", exc_info=True)
        return None


async def save_bm25_index_s3(
    artifact_service,
    app_name: str,
    user_id: str,
    session_id: str,
    index_name: str,
    index_files: Dict[str, Path],
    metadata: Dict,
) -> Optional[int]:
    """
    Save BM25 index files to S3 with folder-based structure.
    
    Structure (S3 keys) - consistent with filesystem:
    {app_name}/{user_id}/{session_id}/{index_name}/0                (marker for list_versions)
    {app_name}/{user_id}/{session_id}/{index_name}/0_data/bm25_index.pkl
    {app_name}/{user_id}/{session_id}/{index_name}/0_data/metadata.json
    {app_name}/{user_id}/{session_id}/{index_name}/0_data/corpus.pkl
    {app_name}/{user_id}/{session_id}/{index_name}/0.meta
    {app_name}/{user_id}/{session_id}/{index_name}/1                (marker)
    {app_name}/{user_id}/{session_id}/{index_name}/1_data/bm25_index.pkl
    {app_name}/{user_id}/{session_id}/{index_name}/1_data/metadata.json
    {app_name}/{user_id}/{session_id}/{index_name}/1_data/corpus.pkl
    {app_name}/{user_id}/{session_id}/{index_name}/1.meta
    
    Args:
        artifact_service: S3ArtifactService instance
        app_name: Application name
        user_id: User ID
        session_id: Session ID
        index_name: Name of the index artifact
        index_files: Dict mapping filenames to their Path objects
        metadata: Metadata to store with the index
    
    Returns:
        Version number of created index, or None if failed
    """
    try:
        app_name = app_name.strip('/')
        
        # Determine the next version number
        versions = await artifact_service.list_versions(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=index_name,
        )
        version = 0 if not versions else max(versions) + 1
        
        # Base S3 key prefix for this index
        base_key = f"{app_name}/{user_id}/{session_id}/{index_name}"
        
        # Upload all index files to S3 under version_data folder (same pattern as filesystem)
        # This makes loading consistent across both storage backends
        files_uploaded = 0
        for filename, file_path in index_files.items():
            # S3 key: {base_key}/{version}_data/{filename}
            s3_key = f"{base_key}/{version}_data/{filename}"
            
            # Read file content
            def _read_file():
                with open(file_path, 'rb') as f:
                    return f.read()
            
            file_bytes = await asyncio.to_thread(_read_file)
            
            # Upload to S3
            def _put_object():
                return artifact_service.s3.put_object(
                    Bucket=artifact_service.bucket_name,
                    Key=s3_key,
                    Body=file_bytes,
                    ContentType='application/octet-stream',
                    Metadata={
                        "index_name": index_name,
                        "version": str(version),
                        "component": filename,
                    }
                )
            
            await asyncio.to_thread(_put_object)
            files_uploaded += 1
            logger.debug(f"Uploaded {filename} to s3://{artifact_service.bucket_name}/{s3_key}")
        
        # Create a version marker object so list_versions() can detect this version
        # S3ArtifactService.list_versions() looks for objects with key pattern: {base_key}/{version}
        version_marker_key = f"{base_key}/{version}"
        
        def _put_version_marker():
            return artifact_service.s3.put_object(
                Bucket=artifact_service.bucket_name,
                Key=version_marker_key,
                Body=b'',  # Empty object, just a marker
                ContentType='application/octet-stream',
                Metadata={
                    "index_name": index_name,
                    "version": str(version),
                    "marker": "true",
                }
            )
        
        await asyncio.to_thread(_put_version_marker)
        logger.debug(f"Created version marker object: s3://{artifact_service.bucket_name}/{version_marker_key}")
        
        # Create and upload metadata file
        metadata_key = f"{base_key}/{version}.meta"
        metadata["num_files"] = files_uploaded
        metadata_json = json.dumps(metadata, indent=2)
        
        def _put_metadata():
            return artifact_service.s3.put_object(
                Bucket=artifact_service.bucket_name,
                Key=metadata_key,
                Body=metadata_json.encode('utf-8'),
                ContentType='application/json',
                Metadata={
                    "index_name": index_name,
                    "version": str(version),
                }
            )
        
        await asyncio.to_thread(_put_metadata)
        
        logger.info(
            f"✓ Saved BM25 index to S3: {index_name} v{version} "
            f"({files_uploaded} files) at s3://{artifact_service.bucket_name}/{base_key}/{version}/"
        )
        
        return version
        
    except Exception as e:
        logger.error(f"Error saving BM25 index to S3: {e}", exc_info=True)
        return None


async def delete_bm25_index_filesystem(
    artifact_service,
    app_name: str,
    user_id: str,
    session_id: str,
    index_name: str,
) -> bool:
    """
    Delete BM25 index directory from filesystem.
    
    Removes all version folders, version marker files, and metadata files.
    
    Args:
        artifact_service: FilesystemArtifactService instance
        app_name: Application name
        user_id: User ID
        session_id: Session ID
        index_name: Name of the index artifact (e.g., "file.pdf.bm25_index")
    
    Returns:
        bool: True if deletion was successful, False otherwise
    """
    try:
        # Get the artifact directory path
        artifact_dir = artifact_service._get_artifact_dir(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=index_name
        )
        
        if not os.path.exists(artifact_dir):
            logger.warning(f"BM25 index directory does not exist: {artifact_dir}")
            return False
        
        # Delete the entire directory
        def _remove_directory():
            import shutil
            shutil.rmtree(artifact_dir)
        
        await asyncio.to_thread(_remove_directory)
        logger.info(f"✓ Deleted BM25 index directory: {artifact_dir}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error deleting BM25 index from filesystem: {e}", exc_info=True)
        return False


async def delete_bm25_index_s3(
    artifact_service,
    app_name: str,
    user_id: str,
    session_id: str,
    index_name: str,
) -> bool:
    """
    Delete BM25 index from S3.
    
    Removes all objects with the index prefix (all versions, data files, markers, metadata).
    
    Args:
        artifact_service: S3ArtifactService instance
        app_name: Application name
        user_id: User ID
        session_id: Session ID
        index_name: Name of the index artifact (e.g., "file.pdf.bm25_index")
    
    Returns:
        bool: True if deletion was successful, False otherwise
    """
    try:
        app_name = app_name.strip('/')
        
        # Base S3 key prefix for this index
        base_key = f"{app_name}/{user_id}/{session_id}/{index_name}"
        
        # List all objects with this prefix
        def _list_objects():
            paginator = artifact_service.s3.get_paginator("list_objects_v2")
            return paginator.paginate(
                Bucket=artifact_service.bucket_name,
                Prefix=base_key
            )
        
        pages = await asyncio.to_thread(_list_objects)
        
        # Collect all object keys to delete
        objects_to_delete = []
        for page in pages:
            for obj in page.get("Contents", []):
                objects_to_delete.append({"Key": obj["Key"]})
        
        if not objects_to_delete:
            logger.warning(f"No BM25 index objects found with prefix: {base_key}")
            return False
        
        # Delete all objects in batches (S3 allows up to 1000 objects per delete request)
        batch_size = 1000
        for i in range(0, len(objects_to_delete), batch_size):
            batch = objects_to_delete[i:i + batch_size]
            
            def _delete_objects():
                return artifact_service.s3.delete_objects(
                    Bucket=artifact_service.bucket_name,
                    Delete={"Objects": batch}
                )
            
            await asyncio.to_thread(_delete_objects)
            logger.debug(f"Deleted batch of {len(batch)} objects from S3")
        
        logger.info(
            f"✓ Deleted BM25 index from S3: {len(objects_to_delete)} objects "
            f"with prefix s3://{artifact_service.bucket_name}/{base_key}"
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Error deleting BM25 index from S3: {e}", exc_info=True)
        return False
