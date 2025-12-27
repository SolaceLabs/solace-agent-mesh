"""
Defines the ToolResult abstraction for structured tool responses with automatic
artifact handling.

Tools can return either a raw dict (backward compatible) or a ToolResult for
enhanced handling where the framework automatically manages artifact storage
based on DataObject disposition.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class DataDisposition(str, Enum):
    """
    Defines how a DataObject should be handled by the framework.

    - AUTO: Framework decides based on content size and type
    - ARTIFACT: Always store as artifact, return reference to LLM
    - INLINE: Always return content inline (may be truncated if too large)
    - ARTIFACT_WITH_PREVIEW: Store as artifact and include preview for LLM
    """
    AUTO = "auto"
    ARTIFACT = "artifact"
    INLINE = "inline"
    ARTIFACT_WITH_PREVIEW = "artifact_with_preview"


class DataObject(BaseModel):
    """
    Represents a single piece of data produced by a tool that can be returned
    inline or stored as an artifact.

    The framework will process DataObjects based on their disposition, handling
    artifact storage, preview generation, and response formatting automatically.

    Examples:
        # Text content with auto disposition (framework decides):
        DataObject(
            name="analysis_results.json",
            content='{"key": "value"}',
            mime_type="application/json",
            description="Analysis results"
        )

        # Binary content requiring artifact storage:
        DataObject(
            name="generated_chart.png",
            content=chart_bytes,
            mime_type="image/png",
            disposition=DataDisposition.ARTIFACT,
            description="Generated chart"
        )

        # Large content with explicit preview:
        DataObject(
            name="large_dataset.csv",
            content=csv_string,
            mime_type="text/csv",
            disposition=DataDisposition.ARTIFACT_WITH_PREVIEW,
            preview="col1,col2,col3\\n1,2,3\\n4,5,6\\n...(1000 more rows)",
            description="Full dataset"
        )
    """
    name: str = Field(
        ...,
        description="Filename for the data object. Used as artifact filename if stored."
    )
    content: Union[str, bytes] = Field(
        ...,
        description="The actual content - string or bytes."
    )
    mime_type: str = Field(
        default="text/plain",
        description="MIME type of the content."
    )
    disposition: DataDisposition = Field(
        default=DataDisposition.AUTO,
        description="How the framework should handle this data object."
    )
    description: Optional[str] = Field(
        default=None,
        description="Human-readable description stored in artifact metadata."
    )
    preview: Optional[str] = Field(
        default=None,
        description="Custom preview text for ARTIFACT_WITH_PREVIEW disposition. "
                    "If not provided, framework generates a preview automatically."
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata to store with the artifact."
    )

    class Config:
        use_enum_values = True


class ToolResult(BaseModel):
    """
    Structured result type for tools, enabling automatic artifact handling.

    Tools can return either a raw dict (backward compatible) or a ToolResult
    for enhanced handling. The framework detects ToolResult instances and
    processes them through the ToolResultProcessor.

    Examples:
        # Simple success with inline message:
        ToolResult(
            status="success",
            message="Operation completed successfully",
            data={"count": 42, "items": ["a", "b", "c"]}
        )

        # Success with auto-artifact handling:
        ToolResult(
            status="success",
            message="Generated report with 1000 rows",
            data_objects=[
                DataObject(
                    name="report.csv",
                    content=csv_content,
                    mime_type="text/csv",
                    description="Analysis report"
                )
            ]
        )

        # Error result:
        ToolResult.error("File not found: data.csv", code="FILE_NOT_FOUND")

        # Multiple outputs:
        ToolResult(
            status="success",
            message="Analysis complete",
            data={"summary": "3 files processed"},
            data_objects=[
                DataObject(name="output1.json", content=json1, mime_type="application/json"),
                DataObject(name="output2.json", content=json2, mime_type="application/json"),
            ]
        )
    """
    status: str = Field(
        default="success",
        description="Status of the tool execution: 'success', 'error', or 'partial'."
    )
    message: Optional[str] = Field(
        default=None,
        description="Human-readable message describing the result."
    )
    data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Inline data to return directly to the LLM. "
                    "Use for small, structured results that don't need artifact storage."
    )
    data_objects: List[DataObject] = Field(
        default_factory=list,
        description="Data objects that may be stored as artifacts based on disposition."
    )
    error_code: Optional[str] = Field(
        default=None,
        description="Machine-readable error code for programmatic error handling."
    )

    class Config:
        use_enum_values = True

    @classmethod
    def ok(
        cls,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        data_objects: Optional[List[DataObject]] = None,
    ) -> "ToolResult":
        """
        Convenience constructor for successful results.

        Args:
            message: Human-readable success message
            data: Optional inline data dict
            data_objects: Optional list of DataObjects

        Returns:
            ToolResult with status="success"
        """
        return cls(
            status="success",
            message=message,
            data=data,
            data_objects=data_objects or [],
        )

    @classmethod
    def error(
        cls,
        message: str,
        code: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> "ToolResult":
        """
        Convenience constructor for error results.

        Args:
            message: Human-readable error message
            code: Optional machine-readable error code
            data: Optional additional error details

        Returns:
            ToolResult with status="error"
        """
        return cls(
            status="error",
            message=message,
            error_code=code,
            data=data,
        )

    @classmethod
    def partial(
        cls,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        data_objects: Optional[List[DataObject]] = None,
        error_code: Optional[str] = None,
    ) -> "ToolResult":
        """
        Convenience constructor for partial success results.

        Use when some operations succeeded but others failed.

        Args:
            message: Human-readable message explaining partial success
            data: Optional inline data dict
            data_objects: Optional list of successfully created DataObjects
            error_code: Optional error code for the failures

        Returns:
            ToolResult with status="partial"
        """
        return cls(
            status="partial",
            message=message,
            data=data,
            data_objects=data_objects or [],
            error_code=error_code,
        )
