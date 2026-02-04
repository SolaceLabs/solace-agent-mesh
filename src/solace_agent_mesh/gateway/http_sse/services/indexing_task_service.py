"""
Service for background conversion and indexing tasks with SSE progress updates.

Follows SAM's async pattern (similar to title_generation_service.py):
- Fire-and-forget task execution
- Stateless (no task tracking)
- SSE events for progress
- asyncio.to_thread() for CPU-intensive work
"""

import asyncio
import logging
import uuid
from typing import List, Tuple, Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .project_service import ProjectService
    from ..sse_manager import SSEManager

log = logging.getLogger(__name__)


class IndexingTaskService:
    """
    Stateless service for background conversion and indexing.

    Executes CPU-intensive PDF/DOCX/PPTX conversion and BM25 indexing
    in background tasks, sending SSE events for progress updates.

    No state tracking - SSEManager handles all connection/event state.
    """

    def __init__(self, sse_manager: "SSEManager", project_service: "ProjectService"):
        """
        Initialize indexing task service.

        Args:
            sse_manager: SSEManager for sending events
            project_service: ProjectService for file operations
        """
        self.sse_manager = sse_manager
        self.project_service = project_service
        self.log_identifier = "[IndexingTaskService]"
        log.info(f"{self.log_identifier} Initialized (stateless)")

    @staticmethod
    def create_task_id(operation: str, project_id: str) -> str:
        """
        Create unique task ID for SSE routing.

        Args:
            operation: Operation type (upload, delete, import)
            project_id: Project ID

        Returns:
            Unique task ID (e.g., "indexing_upload_proj123_abc12345")
        """
        return f"indexing_{operation}_{project_id}_{uuid.uuid4().hex[:8]}"

    # ==========================================
    # Public Methods - Called from Endpoints
    # ==========================================

    async def convert_and_index_upload_async(
        self,
        task_id: str,
        project,
        files_to_convert: List[Tuple[str, int, str]],
        is_text_based: List[Tuple[str, int]]
    ):
        """
        Background task for upload: convert files and build index.

        Sends SSE events for progress. Completely stateless.

        This method is fire-and-forget - called via loop.create_task().
        Exceptions are caught and sent as SSE error events.

        Args:
            task_id: Unique task identifier (for SSE routing)
            project: Project entity
            files_to_convert: List of (filename, version, mime_type)
            is_text_based: List of (filename, version)
        """
        log_prefix = f"{self.log_identifier}[{task_id}]"
        log.info(f"{log_prefix} Starting upload background task")

        try:
            # 1. Convert files (if any)
            converted_results = []
            total_files = len(files_to_convert)

            if files_to_convert:
                await self._send_event(task_id, {
                    "type": "conversion_started",
                    "total_files": total_files
                })

                for idx, (filename, version, mime_type) in enumerate(files_to_convert, 1):
                    try:
                        # Send progress
                        await self._send_event(task_id, {
                            "type": "conversion_progress",
                            "file": filename,
                            "current": idx,
                            "total": total_files,
                            "percentage": int((idx - 1) / total_files * 100)
                        })

                        # Convert file (CPU-intensive - run in thread pool)
                        log.debug(f"{log_prefix} Converting {filename} in thread pool")
                        result = await self._convert_file_async(project, filename, version, mime_type)

                        if result and result.get("status") == "success":
                            converted_results.append(result)
                            await self._send_event(task_id, {
                                "type": "conversion_completed",
                                "file": filename,
                                "converted_file": f"{filename}.converted.txt",
                                "version": result.get('data_version')
                            })
                        else:
                            await self._send_event(task_id, {
                                "type": "conversion_failed",
                                "file": filename,
                                "error": "Conversion returned no result"
                            })

                    except Exception as e:
                        log.error(f"{log_prefix} Failed to convert {filename}: {e}")
                        await self._send_event(task_id, {
                            "type": "conversion_failed",
                            "file": filename,
                            "error": str(e)
                        })

            # 2. Build index (if text files or conversions happened)
            if is_text_based or converted_results:
                await self._send_event(task_id, {
                    "type": "indexing_started",
                    "files_in_this_batch": len(is_text_based) + len(converted_results)
                })

                # Build index (CPU-intensive - run in thread pool)
                log.debug(f"{log_prefix} Building index in thread pool")
                index_result = await self._rebuild_index_async(project)

                if index_result and index_result.get("status") == "success":
                    # Extract total counts from manifest (shared index includes ALL project files)
                    manifest = index_result.get('manifest', {})
                    total_files_in_index = manifest.get('file_count', 0)
                    total_chunks_in_index = manifest.get('chunk_count', 0)

                    await self._send_event(task_id, {
                        "type": "indexing_completed",
                        "index_version": index_result.get('data_version'),
                        "total_files_indexed": total_files_in_index,  # Total files in shared index
                        "total_chunks": total_chunks_in_index,  # Total chunks in shared index
                        "files_added_this_batch": len(is_text_based) + len(converted_results)
                    })
                else:
                    await self._send_event(task_id, {
                        "type": "indexing_failed",
                        "error": index_result.get('message') if index_result else "Unknown error"
                    })

            # 3. Send completion event with total index stats
            # Get final manifest info if index was built
            final_manifest = {}
            if is_text_based or converted_results:
                final_manifest = index_result.get('manifest', {}) if index_result else {}

            task_completion_data = {
                "type": "task_completed",
                "files_converted": len(converted_results),
                "files_added_to_index": len(is_text_based) + len(converted_results)
            }

            # Add total index stats if available
            if final_manifest:
                task_completion_data["total_files_indexed"] = final_manifest.get('file_count', 0)
                task_completion_data["total_chunks"] = final_manifest.get('chunk_count', 0)
                task_completion_data["index_version"] = index_result.get('data_version') if index_result else None

            await self._send_event(task_id, task_completion_data)

            log.info(f"{log_prefix} Background task completed successfully")

        except Exception as e:
            log.exception(f"{log_prefix} Background task failed: {e}")
            await self._send_event(task_id, {
                "type": "task_error",
                "error": str(e)
            })

    async def rebuild_index_after_delete_async(
        self,
        task_id: str,
        project,
        deleted_file: str,
        was_text_file: bool,
        was_convertible: bool
    ):
        """
        Background task for delete: rebuild index after file deletion.

        Args:
            task_id: Unique task identifier
            project: Project entity
            deleted_file: Name of deleted file
            was_text_file: Whether deleted file was text-based
            was_convertible: Whether deleted file was convertible (PDF/DOCX/PPTX)
        """
        log_prefix = f"{self.log_identifier}[{task_id}]"
        log.info(f"{log_prefix} Starting index rebuild after deletion")

        try:
            # Determine file category for informational event
            file_category = "convertible" if was_convertible else ("text" if was_text_file else "other")

            await self._send_event(task_id, {
                "type": "indexing_started",
                "reason": "file_deleted",
                "deleted_file": deleted_file,
                "file_category": file_category,
                "deleted_converted": was_convertible  # If True, .converted.txt was also deleted
            })

            # Rebuild index (CPU-intensive - run in thread pool)
            log.debug(f"{log_prefix} Rebuilding index in thread pool")
            index_result = await self._rebuild_index_async(project)

            if index_result and index_result.get("status") == "success":
                # Check if index was deleted (no files left) or rebuilt
                if index_result.get('index_deleted'):
                    # Index was deleted - no files left
                    await self._send_event(task_id, {
                        "type": "indexing_completed",
                        "index_deleted": True,
                        "total_files_indexed": 0,  # No files left
                        "total_chunks": 0,
                        "message": "Index deleted - last file removed"
                    })
                else:
                    # Index was rebuilt with remaining files
                    manifest = index_result.get('manifest', {})
                    total_files_in_index = manifest.get('file_count', 0)
                    total_chunks_in_index = manifest.get('chunk_count', 0)

                    await self._send_event(task_id, {
                        "type": "indexing_completed",
                        "index_version": index_result.get('data_version'),
                        "total_files_indexed": total_files_in_index,  # Total files remaining in index
                        "total_chunks": total_chunks_in_index  # Total chunks in index
                    })
            else:
                await self._send_event(task_id, {
                    "type": "indexing_failed",
                    "error": index_result.get('message') if index_result else "Unknown error"
                })

            # Send completion with total index stats
            task_completion_data = {
                "type": "task_completed",
                "deleted_file": deleted_file,
                "deleted_category": file_category
            }

            # Add total index stats from rebuild result
            if index_result and index_result.get("status") == "success":
                if index_result.get('index_deleted'):
                    # Index was deleted - last file removed
                    task_completion_data["index_deleted"] = True
                    task_completion_data["total_files_indexed"] = 0
                    task_completion_data["total_chunks"] = 0
                else:
                    # Index still exists with remaining files
                    manifest = index_result.get('manifest', {})
                    if manifest:
                        task_completion_data["total_files_indexed"] = manifest.get('file_count', 0)
                        task_completion_data["total_chunks"] = manifest.get('chunk_count', 0)
                        task_completion_data["index_version"] = index_result.get('data_version')

            await self._send_event(task_id, task_completion_data)

            log.info(f"{log_prefix} Background task completed successfully")

        except Exception as e:
            log.exception(f"{log_prefix} Background task failed: {e}")
            await self._send_event(task_id, {
                "type": "task_error",
                "error": str(e)
            })

    async def convert_and_index_import_async(
        self,
        task_id: str,
        project,
        files_to_convert: List[Tuple[str, int, str]],
        is_text_based: List[Tuple[str, int]]
    ):
        """
        Background task for import: convert files and build initial index.

        Same as upload logic.

        Args:
            task_id: Unique task identifier
            project: Project entity
            files_to_convert: List of (filename, version, mime_type)
            is_text_based: List of (filename, version)
        """
        # Reuse upload logic
        await self.convert_and_index_upload_async(
            task_id, project, files_to_convert, is_text_based
        )

    # ==========================================
    # Helper Methods - CPU Work in Thread Pool
    # ==========================================

    async def _convert_file_async(
        self,
        project,
        filename: str,
        version: int,
        mime_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Convert a file in background thread (non-blocking).

        Uses asyncio.to_thread() to run CPU-intensive conversion
        in thread pool without blocking the main event loop.

        Args:
            project: Project entity
            filename: File to convert
            version: Version of file
            mime_type: MIME type

        Returns:
            Conversion result dict or None
        """
        # Run CPU-intensive work in thread pool
        result = await asyncio.to_thread(
            self._convert_file_sync,
            project, filename, version, mime_type
        )
        return result

    def _convert_file_sync(
        self,
        project,
        filename: str,
        version: int,
        mime_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Synchronous conversion (runs in thread pool).

        This is CPU-intensive work that runs in a background thread.
        Must call async functions using asyncio.run() or new event loop.
        """
        from .file_converter_service import convert_and_save_artifact

        storage_session_id = f"project-{project.id}"

        # Create new event loop for this thread (required for calling async from sync)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                convert_and_save_artifact(
                    artifact_service=self.project_service.artifact_service,
                    app_name=self.project_service.app_name,
                    user_id=project.user_id,
                    session_id=storage_session_id,
                    source_filename=filename,
                    source_version=version,
                    mime_type=mime_type
                )
            )
            return result
        except Exception as e:
            log.error(f"Conversion failed for {filename}: {e}")
            return None
        finally:
            loop.close()

    async def _rebuild_index_async(self, project) -> Optional[Dict[str, Any]]:
        """
        Rebuild index in background thread (non-blocking).

        Uses asyncio.to_thread() to run CPU-intensive indexing
        in thread pool without blocking the main event loop.

        Args:
            project: Project entity

        Returns:
            Index build result dict or None
        """
        # Run CPU-intensive work in thread pool
        result = await asyncio.to_thread(
            self._rebuild_index_sync,
            project
        )
        return result

    def _rebuild_index_sync(self, project) -> Optional[Dict[str, Any]]:
        """
        Synchronous index rebuild (runs in thread pool).

        This is CPU-intensive work that runs in a background thread.
        """
        from .bm25_indexer_service import (
            collect_project_text_files,
            build_bm25_index,
            save_project_index
        )

        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Collect text files (async I/O)
            text_files = loop.run_until_complete(
                collect_project_text_files(
                    artifact_service=self.project_service.artifact_service,
                    app_name=self.project_service.app_name,
                    user_id=project.user_id,
                    project_id=project.id
                )
            )

            if not text_files:
                # No files left to index - delete the existing index if it exists
                log.info(f"No text files to index for project {project.id}, deleting index if exists")

                try:
                    # Delete project_bm25_index.zip (all versions)
                    loop.run_until_complete(
                        self.project_service.artifact_service.delete_artifact(
                            app_name=self.project_service.app_name,
                            user_id=project.user_id,
                            session_id=f"project-{project.id}",
                            filename="project_bm25_index.zip"
                        )
                    )
                    log.info(f"Deleted empty index for project {project.id}")
                    return {
                        "status": "success",
                        "message": "Index deleted - no files to index",
                        "index_deleted": True
                    }
                except Exception as e:
                    # Index might not exist - this is fine
                    log.debug(f"No index to delete for project {project.id}: {e}")
                    return {
                        "status": "success",
                        "message": "No files to index, no index exists",
                        "index_deleted": False
                    }

            # Build index (CPU-intensive)
            index_zip_bytes, manifest = build_bm25_index(text_files, project.id)

            # Save index (async I/O)
            result = loop.run_until_complete(
                save_project_index(
                    artifact_service=self.project_service.artifact_service,
                    app_name=self.project_service.app_name,
                    user_id=project.user_id,
                    project_id=project.id,
                    index_zip_bytes=index_zip_bytes,
                    manifest=manifest
                )
            )

            # Add manifest info to result for SSE events
            result["manifest"] = manifest
            return result

        except Exception as e:
            log.error(f"Index rebuild failed for project {project.id}: {e}")
            return {"status": "error", "message": str(e)}
        finally:
            loop.close()

    # ==========================================
    # SSE Event Helper
    # ==========================================

    async def _send_event(self, task_id: str, data: Dict[str, Any]):
        """
        Send SSE event for task progress.

        Args:
            task_id: Task identifier (for SSE routing)
            data: Event data (will be JSON serialized)
        """
        try:
            event_type = data.get("type", "message")
            await self.sse_manager.send_event(
                task_id=task_id,
                event_data=data,
                event_type=event_type
            )
            log.debug(f"{self.log_identifier}[{task_id}] Sent SSE event: {event_type}")
        except Exception as e:
            log.warning(f"{self.log_identifier}[{task_id}] Failed to send SSE event: {e}")
