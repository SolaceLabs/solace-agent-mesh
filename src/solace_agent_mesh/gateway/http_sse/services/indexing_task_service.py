"""
Service for background conversion and indexing tasks with SSE progress updates.

Follows SAM's async pattern (similar to title_generation_service.py):
- Fire-and-forget task execution
- Stateless (no task tracking)
- SSE events for progress
- Async I/O for file operations and indexing
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
            failed_conversions = []
            total_files = len(files_to_convert)

            if files_to_convert:
                # Send conversion_started with list of all files to convert
                await self._send_event(task_id, {
                    "type": "conversion_started",
                    "files": [filename for filename, _, _ in files_to_convert]
                })

                for idx, (filename, version, mime_type) in enumerate(files_to_convert, 1):
                    try:
                        # Send per-file progress
                        await self._send_event(task_id, {
                            "type": "conversion_file_progress",
                            "file": filename,
                            "version": version,
                            "current": idx,
                            "total": total_files
                        })

                        # Convert file (CPU-intensive - run in thread pool)
                        log.debug(f"{log_prefix} Converting {filename} in thread pool")
                        result = await self._convert_file_async(project, filename, version, mime_type)

                        if result and result.get("status") == "success":
                            converted_results.append(result)
                            await self._send_event(task_id, {
                                "type": "conversion_file_completed",
                                "converted_file": f"{filename}.converted.txt",
                                "version": result.get('data_version')
                            })
                        else:
                            # Conversion failed - extract error message from result
                            error_msg = result.get("error") if result else f"Failed to convert '{filename}': Conversion returned no result"
                            failed_conversions.append(filename)
                            await self._send_event(task_id, {
                                "type": "conversion_failed",
                                "file": filename,
                                "error": error_msg
                            })

                    except Exception as e:
                        failed_conversions.append(filename)
                        log.error(f"{log_prefix} Failed to convert {filename}: {e}")
                        error_msg = f"Failed to convert '{filename}': {str(e)}"
                        await self._send_event(task_id, {
                            "type": "conversion_failed",
                            "file": filename,
                            "error": error_msg
                        })

                # Send overall conversion completion summary
                await self._send_event(task_id, {
                    "type": "conversion_completed",
                    "converted_file_success_count": len(converted_results),
                    "converted_file_fail_count": len(failed_conversions)
                })

            # 2. Build index (if text files or conversions happened)
            if is_text_based or converted_results:
                # First, get the list of ALL files that will be indexed
                # (need to do this before building to send index_started event)
                files_to_be_indexed = await self._get_files_for_indexing(project)

                # Send index_started BEFORE building
                await self._send_event(task_id, {
                    "type": "index_started",
                    "files": files_to_be_indexed
                })

                # Build index (CPU-intensive - run in thread pool)
                # This rebuilds the ENTIRE index from ALL project files, not just new ones
                log.debug(f"{log_prefix} Building index in thread pool")
                index_result = await self._rebuild_index_async(project)

                if index_result and index_result.get("status") == "success":
                    # Get ALL files that were actually indexed (should match files_to_be_indexed)
                    all_indexed_files = index_result.get('indexed_files', [])

                    # Send index_completed AFTER building
                    await self._send_event(task_id, {
                        "type": "index_completed",
                        "files": all_indexed_files
                    })

                    # Send task completion event with ALL indexed files
                    await self._send_event(task_id, {
                        "type": "task_completed",
                        "files": all_indexed_files
                    })
                else:
                    # Index build failed
                    await self._send_event(task_id, {
                        "type": "indexing_failed",
                        "error": index_result.get('message') if index_result else "Unknown error"
                    })
                    # Send task completion with empty files on failure
                    await self._send_event(task_id, {
                        "type": "task_completed",
                        "files": []
                    })
            else:
                # No indexing needed
                await self._send_event(task_id, {
                    "type": "task_completed",
                    "files": []
                })

            log.info(f"{log_prefix} Background task completed successfully")

        except Exception as e:
            log.exception(f"{log_prefix} Background task failed: {e}")
            error_msg = f"Background indexing task crashed during file upload/import: {str(e)}"
            await self._send_event(task_id, {
                "type": "task_error",
                "error": error_msg
            })

    async def rebuild_index_after_delete_async(
        self,
        task_id: str,
        project
    ):
        """
        Background task for delete: rebuild index after file deletion.

        Args:
            task_id: Unique task identifier
            project: Project entity
        """
        log_prefix = f"{self.log_identifier}[{task_id}]"
        log.info(f"{log_prefix} Starting index rebuild after deletion")

        try:
            # First, get the list of files that will remain in the index after deletion
            files_to_be_indexed = await self._get_files_for_indexing(project)

            # Send index_started BEFORE rebuilding
            await self._send_event(task_id, {
                "type": "index_started",
                "files": files_to_be_indexed
            })

            # Rebuild index (CPU-intensive - run in thread pool)
            log.debug(f"{log_prefix} Rebuilding index in thread pool")
            index_result = await self._rebuild_index_async(project)

            if index_result and index_result.get("status") == "success":
                # Get the actual indexed files after rebuild
                indexed_files = index_result.get('indexed_files', [])

                # Send index_completed AFTER rebuilding
                await self._send_event(task_id, {
                    "type": "index_completed",
                    "files": indexed_files
                })
            else:
                await self._send_event(task_id, {
                    "type": "indexing_failed",
                    "error": index_result.get('message') if index_result else "Unknown error"
                })

            # Send task completion event
            # Use the indexed files from the rebuild result
            final_indexed_files = []
            if index_result and index_result.get("status") == "success":
                final_indexed_files = index_result.get('indexed_files', [])

            await self._send_event(task_id, {
                "type": "task_completed",
                "files": final_indexed_files
            })

            log.info(f"{log_prefix} Background task completed successfully")

        except Exception as e:
            log.exception(f"{log_prefix} Background task failed: {e}")
            error_msg = f"Background indexing task crashed during file deletion/index rebuild: {str(e)}"
            await self._send_event(task_id, {
                "type": "task_error",
                "error": error_msg
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

    async def _get_files_for_indexing(self, project) -> List[str]:
        """
        Get the list of original filenames that will be included in the index.

        This is called BEFORE index building to send the index_started event.
        Returns original filenames (e.g., "document.pdf", "readme.md"),
        not converted filenames (e.g., "document.pdf.converted.txt").

        Args:
            project: Project entity

        Returns:
            List of original filenames that will be indexed
        """
        from .bm25_indexer_service import collect_project_text_files_stream

        try:
            # Stream text files (memory-efficient - only keeps filenames)
            text_files_stream = collect_project_text_files_stream(
                artifact_service=self.project_service.artifact_service,
                app_name=self.project_service.app_name,
                user_id=project.user_id,
                project_id=project.id
            )

            # Extract original filenames (remove .converted.txt suffix)
            # Only store filenames, not full content
            original_filenames = []
            async for filename, _, _, _ in text_files_stream:
                # Remove .converted.txt suffix if present
                if filename.endswith('.converted.txt'):
                    original_filename = filename[:-len('.converted.txt')]
                else:
                    original_filename = filename
                if original_filename not in original_filenames:
                    original_filenames.append(original_filename)

            return original_filenames
        except Exception as e:
            log.warning(f"Failed to get files for indexing: {e}")
            return []

    async def _convert_file_async(
        self,
        project,
        filename: str,
        version: int,
        mime_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Convert a file asynchronously.

        Args:
            project: Project entity
            filename: File to convert
            version: Version of file
            mime_type: MIME type

        Returns:
            Conversion result dict or None
        """
        from .file_converter_service import convert_and_save_artifact

        storage_session_id = f"project-{project.id}"

        try:
            # Already in async context, just await
            result = await convert_and_save_artifact(
                artifact_service=self.project_service.artifact_service,
                app_name=self.project_service.app_name,
                user_id=project.user_id,
                session_id=storage_session_id,
                source_filename=filename,
                source_version=version,
                mime_type=mime_type
            )
            return result
        except Exception as e:
            log.error(f"Conversion failed for {filename}: {e}")
            return None

    async def _rebuild_index_async(self, project) -> Optional[Dict[str, Any]]:
        """
        Rebuild index asynchronously.

        Args:
            project: Project entity

        Returns:
            Index build result dict or None
        """
        from .bm25_indexer_service import (
            collect_project_text_files_stream,
            build_bm25_index,
            save_project_index
        )

        try:
            # Stream text files (async I/O, memory-efficient)
            try:
                text_files_stream = collect_project_text_files_stream(
                    artifact_service=self.project_service.artifact_service,
                    app_name=self.project_service.app_name,
                    user_id=project.user_id,
                    project_id=project.id
                )
            except Exception as e:
                log.error(f"Failed to create text files stream for project {project.id}: {e}")
                return {
                    "status": "error",
                    "message": f"Failed to access project files from storage: {str(e)}"
                }

            # Build index (async, memory-efficient with batch processing)
            try:
                # Already in async context, just await
                index_zip_bytes, manifest = await build_bm25_index(text_files_stream, project.id)
            except ValueError as e:
                # Handle case where no documents/chunks were created
                if "No chunks created" in str(e):
                    log.info(f"No text files to index for project {project.id}, deleting index if exists")

                    try:
                        # Delete project_bm25_index.zip (all versions)
                        await self.project_service.artifact_service.delete_artifact(
                            app_name=self.project_service.app_name,
                            user_id=project.user_id,
                            session_id=f"project-{project.id}",
                            filename="project_bm25_index.zip"
                        )
                        log.info(f"Deleted empty index for project {project.id}")
                        return {
                            "status": "success",
                            "message": "Index deleted - no files to index",
                            "index_deleted": True
                        }
                    except Exception as delete_error:
                        # Index might not exist - this is fine
                        log.debug(f"No index to delete for project {project.id}: {delete_error}")
                        return {
                            "status": "success",
                            "message": "No files to index, no index exists",
                            "index_deleted": False
                        }

                log.error(f"Failed to build BM25 index for project {project.id}: {e}")
                return {
                    "status": "error",
                    "message": f"Failed to build BM25 index: {str(e)}"
                }
            except Exception as e:
                log.error(f"Failed to build BM25 index for project {project.id}: {e}")
                return {
                    "status": "error",
                    "message": f"Failed to build BM25 index: {str(e)}"
                }

            # Extract original filenames from manifest
            original_filenames = []
            for chunk in manifest.get("chunks", []):
                if chunk.get("chunk_id", -1) == 0:  # Only count each file once
                    filename = chunk.get("filename", "")
                    # Remove .converted.txt suffix if present
                    if filename.endswith('.converted.txt'):
                        original_filename = filename[:-len('.converted.txt')]
                    else:
                        original_filename = filename
                    if original_filename not in original_filenames:
                        original_filenames.append(original_filename)

            # Save index (async I/O)
            try:
                # Already in async context, just await
                result = await save_project_index(
                    artifact_service=self.project_service.artifact_service,
                    app_name=self.project_service.app_name,
                    user_id=project.user_id,
                    project_id=project.id,
                    index_zip_bytes=index_zip_bytes,
                    manifest=manifest
                )
            except Exception as e:
                log.error(f"Failed to save index artifact for project {project.id}: {e}")
                return {
                    "status": "error",
                    "message": f"Failed to save index artifact to storage: {str(e)}"
                }

            # Add manifest info and original filenames to result for SSE events
            result["manifest"] = manifest
            result["indexed_files"] = original_filenames  # Original filenames for SSE
            return result

        except Exception as e:
            # Catch-all for unexpected errors in index rebuild
            log.error(f"Unexpected error during index rebuild for project {project.id}: {e}")
            return {"status": "error", "message": f"Unexpected error during index rebuild: {str(e)}"}

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
            log.debug(f"{self.log_identifier}[{task_id}] Failed to send SSE event: {e}")
