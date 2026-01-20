import uuid
import logging
from typing import List, Optional, Dict, Any
from fastapi import UploadFile
from datetime import datetime, timezone

log = logging.getLogger(__name__)

class ProjectUploadService:
    """Service for managing project file uploads with SSE progress tracking."""
    
    def __init__(self, sse_manager, project_service):
        self.sse_manager = sse_manager
        self.project_service = project_service
        self.logger = log
    
    async def initiate_upload(self, project_id: str, user_id: str) -> str:
        """
        Initiate a new file upload session.
        
        Returns:
            upload_id: Unique ID for this upload session
        """
        upload_id = str(uuid.uuid4())
        self.logger.info(f"Initiated upload session {upload_id} for project {project_id}")
        
        # Send initial event
        await self.sse_manager.send_event(
            upload_id,
            {
                "type": "upload_initiated",
                "upload_id": upload_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            event_type="upload_status"
        )
        
        return upload_id
    
    async def process_upload(
        self,
        db,
        upload_id: str,
        project_id: str,
        user_id: str,
        files: List[UploadFile],
        file_metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Process uploaded files with SSE progress updates.
        
        Sends progress events for:
        - File validation
        - Artifact saving
        - BM25 index creation
        """
        try:
            # Step 1: Validate files
            await self.sse_manager.send_event(
                upload_id,
                {
                    "type": "validation_started",
                    "file_count": len(files),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                event_type="upload_progress"
            )
            
            validated_files = await self.project_service._validate_files(files)
            
            await self.sse_manager.send_event(
                upload_id,
                {
                    "type": "validation_completed",
                    "file_count": len(validated_files),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                event_type="upload_progress"
            )
            
            # Step 2: Add artifacts to project
            await self.sse_manager.send_event(
                upload_id,
                {
                    "type": "artifact_saving_started",
                    "file_count": len(validated_files),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                event_type="upload_progress"
            )
            
            results = await self.project_service.add_artifacts_to_project(
                db=db,
                project_id=project_id,
                user_id=user_id,
                files=files,
                file_metadata=file_metadata
            )
            
            # Send per-file progress
            for idx, result in enumerate(results):
                await self.sse_manager.send_event(
                    upload_id,
                    {
                        "type": "artifact_saved",
                        "filename": result.get("data_filename"),
                        "version": result.get("data_version"),
                        "progress": f"{idx + 1}/{len(results)}",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                    event_type="upload_progress"
                )
            
            # Step 3: Create BM25 indexes
            await self.sse_manager.send_event(
                upload_id,
                {
                    "type": "indexing_started",
                    "artifact_count": len(results),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                event_type="upload_progress"
            )
            
            for idx, result in enumerate(results):
                filename = result.get("data_filename")
                version = result.get("data_version")
                mime_type = result.get("mime_type")
                description = file_metadata.get(filename, "") if file_metadata else ""
                
                if filename and version is not None:
                    try:
                        await self.sse_manager.send_event(
                            upload_id,
                            {
                                "type": "index_creation_started",
                                "filename": filename,
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            },
                            event_type="upload_progress"
                        )
                        
                        index_version = await self.project_service.create_bm25_index_to_project(
                            source_filename=filename,
                            source_version=version,
                            source_mime_type=mime_type or "application/octet-stream",
                            source_description=description,
                            user_id=user_id,
                            project_id=project_id,
                        )
                        
                        await self.sse_manager.send_event(
                            upload_id,
                            {
                                "type": "index_creation_completed",
                                "filename": filename,
                                "index_version": index_version,
                                "progress": f"{idx + 1}/{len(results)}",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            },
                            event_type="upload_progress"
                        )
                    except Exception as e:
                        self.logger.error(f"Error creating index for {filename}: {e}")
                        await self.sse_manager.send_event(
                            upload_id,
                            {
                                "type": "index_creation_failed",
                                "filename": filename,
                                "error": str(e),
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            },
                            event_type="upload_error"
                        )
            
            # Step 4: Complete
            await self.sse_manager.send_event(
                upload_id,
                {
                    "type": "upload_completed",
                    "total_files": len(results),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                event_type="upload_success"
            )
            
            return {
                "success": True,
                "upload_id": upload_id,
                "files_processed": len(results),
                "results": results,
            }
        
        except Exception as e:
            self.logger.error(f"Upload failed: {e}", exc_info=True)
            await self.sse_manager.send_event(
                upload_id,
                {
                    "type": "upload_failed",
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                event_type="upload_error"
            )
            raise