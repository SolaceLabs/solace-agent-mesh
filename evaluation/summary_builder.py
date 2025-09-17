"""
Refactored summarization module with improved structure and readability.
This module processes test run messages and generates comprehensive summaries.
"""

import json
import os
import re
import yaml

from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from .test_case_loader import load_test_case


@dataclass
class ToolCall:
    """Structured representation of a tool call."""

    call_id: str
    agent: str
    tool_name: str
    arguments: Dict[str, Any]
    timestamp: str


@dataclass
class ArtifactInfo:
    """Comprehensive artifact information with categorization."""

    artifact_name: str
    directory: str
    versions: List[Dict[str, Any]]
    artifact_type: Optional[str] = None
    source_path: Optional[str] = None
    created_by_tool: Optional[str] = None
    created_by_call_id: Optional[str] = None
    creation_timestamp: Optional[str] = None


@dataclass
class TimeMetrics:
    """Time-related metrics for a test run."""

    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_seconds: Optional[float] = None


@dataclass
class RunSummary:
    """Complete summary of a test run with all metrics and metadata."""

    test_case_id: str
    run_id: str
    query: str = ""
    target_agent: str = ""
    namespace: str = ""
    context_id: str = ""
    final_status: str = ""
    final_message: str = ""
    time_metrics: TimeMetrics = field(default_factory=TimeMetrics)
    tool_calls: List[ToolCall] = field(default_factory=list)
    input_artifacts: List[ArtifactInfo] = field(default_factory=list)
    output_artifacts: List[ArtifactInfo] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert summary to dictionary format for JSON serialization."""
        return {
            "test_case_id": self.test_case_id,
            "run_id": self.run_id,
            "query": self.query,
            "target_agent": self.target_agent,
            "namespace": self.namespace,
            "context_id": self.context_id,
            "final_status": self.final_status,
            "final_message": self.final_message,
            "start_time": self.time_metrics.start_time,
            "end_time": self.time_metrics.end_time,
            "duration_seconds": self.time_metrics.duration_seconds,
            "tool_calls": [
                {
                    "call_id": tc.call_id,
                    "agent": tc.agent,
                    "tool_name": tc.tool_name,
                    "arguments": tc.arguments,
                    "timestamp": tc.timestamp,
                }
                for tc in self.tool_calls
            ],
            "input_artifacts": [
                {
                    "artifact_name": art.artifact_name,
                    "directory": art.directory,
                    "versions": art.versions,
                    "type": art.artifact_type,
                    "source_path": art.source_path,
                }
                for art in self.input_artifacts
            ],
            "output_artifacts": [
                {
                    "artifact_name": art.artifact_name,
                    "directory": art.directory,
                    "versions": art.versions,
                }
                for art in self.output_artifacts
            ],
            "errors": self.errors,
        }


class ConfigService:
    """Handles configuration loading and YAML processing."""

    _config_cache: Dict[str, Any] = {}

    @classmethod
    def load_yaml_with_includes(cls, file_path: str) -> Dict[str, Any]:
        """Load YAML file with !include directive processing and caching."""
        if file_path in cls._config_cache:
            return cls._config_cache[file_path]

        try:
            with open(file_path, "r") as f:
                content = f.read()

            content = cls._process_includes(content, file_path)
            config = yaml.safe_load(content)
            cls._config_cache[file_path] = config
            return config

        except (FileNotFoundError, yaml.YAMLError) as e:
            raise ValueError(f"Failed to load YAML config from {file_path}: {e}")

    @staticmethod
    def _process_includes(content: str, base_file_path: str) -> str:
        """Process !include directives in YAML content."""
        include_pattern = re.compile(r"^\s*!include\s+(.*)$", re.MULTILINE)

        def replacer(match):
            include_path = match.group(1).strip()
            include_path = os.path.join(os.path.dirname(base_file_path), include_path)
            with open(include_path, "r") as inc_f:
                return inc_f.read()

        # Repeatedly replace includes until none are left
        while include_pattern.search(content):
            content = include_pattern.sub(replacer, content)

        return content

    @classmethod
    def get_artifact_config(cls) -> Tuple[str, str]:
        """Get artifact service configuration from eval backend config."""
        try:
            webui_config = cls.load_yaml_with_includes("configs/eval_backend.yaml")

            # Find the correct app_config
            for app in webui_config.get("apps", []):
                if app.get("name") == "a2a_eval_backend_app":
                    app_config = app.get("app_config", {})
                    base_path = app_config.get("artifact_service", {}).get("base_path")
                    user_identity = app_config.get("default_user_identity")

                    if base_path and user_identity:
                        return base_path, user_identity

            raise ValueError("Could not find 'a2a_eval_backend_app' config")

        except Exception as e:
            raise ValueError(f"Failed to load artifact configuration: {e}")


class FileService:
    """Handles file operations and path management."""

    @staticmethod
    def load_json(filepath: str) -> Any:
        """Load JSON data from file."""
        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            raise ValueError(f"Failed to load JSON from {filepath}: {e}")

    @staticmethod
    def save_json(data: Any, filepath: str):
        """Save data as JSON to file."""
        try:
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            raise ValueError(f"Failed to save JSON to {filepath}: {e}")


class TestCaseService:
    """Handles test case loading and validation."""

    @staticmethod
    def load_test_case(test_case_id: str) -> Optional[Dict[str, Any]]:
        """Load test case definition with error handling."""
        try:
            return load_test_case(test_case_id)
        except Exception:
            return None

    @staticmethod
    def extract_input_artifact_names(test_case: Dict[str, Any]) -> Set[str]:
        """Extract input artifact names from test case definition."""
        input_artifact_names = set()
        test_case_artifacts = test_case.get("artifacts", [])

        for tc_artifact in test_case_artifacts:
            if tc_artifact.get("type") == "file" and "path" in tc_artifact:
                # Extract filename from path (e.g., "artifacts/sample.csv" -> "sample.csv")
                artifact_name = os.path.basename(tc_artifact["path"])
                input_artifact_names.add(artifact_name)

        return input_artifact_names


class TimeProcessor:
    """Handles timestamp parsing and duration calculations."""

    @staticmethod
    def extract_start_time(first_message: Dict[str, Any]) -> Optional[str]:
        """Extract start time from the first message."""
        try:
            payload = first_message.get("payload", {})
            params = payload.get("params", {})
            message = params.get("message", {})
            parts = message.get("parts", [])

            for part in parts:
                if "text" in part and "Request received by gateway at:" in part["text"]:
                    time_str = (
                        part["text"]
                        .split("Request received by gateway at: ")[1]
                        .strip()
                    )
                    # Validate timestamp format
                    datetime.fromisoformat(time_str)
                    return time_str
        except (KeyError, ValueError, IndexError):
            pass

        return None

    @staticmethod
    def extract_end_time(last_message: Dict[str, Any]) -> Optional[str]:
        """Extract end time from the last message."""
        try:
            payload = last_message.get("payload", {})
            result = payload.get("result", {})
            status = result.get("status", {})
            return status.get("timestamp")
        except KeyError:
            return None

    @staticmethod
    def calculate_duration(
        start_time_str: str, end_time_str: str
    ) -> Tuple[Optional[float], Optional[str]]:
        """Calculate duration and return normalized start time."""
        try:
            start_time = datetime.fromisoformat(start_time_str)
            end_time = datetime.fromisoformat(end_time_str)

            # Handle timezone differences
            if (start_time.tzinfo is not None) and (end_time.tzinfo is None):
                start_time = start_time.astimezone().replace(tzinfo=None)
            elif (end_time.tzinfo is not None) and (start_time.tzinfo is None):
                end_time = end_time.astimezone().replace(tzinfo=None)

            duration = end_time - start_time

            # Normalize start time for output
            s_time = datetime.fromisoformat(start_time_str)
            if s_time.tzinfo is not None:
                s_time = s_time.astimezone().replace(tzinfo=None)

            return duration.total_seconds(), s_time.isoformat()

        except ValueError:
            return None, None


class MessageProcessor:
    """Processes messages to extract tool calls and metadata."""

    @staticmethod
    def extract_namespace_and_agent(
        first_message: Dict[str, Any],
    ) -> Tuple[Optional[str], Optional[str]]:
        """Extract namespace and target agent from the first message topic."""
        try:
            topic = first_message.get("topic", "")
            # Regex to match the topic format and capture the namespace and target_agent
            match = re.match(r"^([^/]+)/a2a/v1/agent/request/([^/]+)$", topic)
            if match:
                return match.group(1), match.group(2)
        except Exception:
            pass

        return None, None

    @staticmethod
    def extract_context_id(first_message: Dict[str, Any]) -> Optional[str]:
        """Extract context ID from the first message."""
        try:
            payload = first_message.get("payload", {})
            params = payload.get("params", {})
            message = params.get("message", {})
            return message.get("contextId")
        except KeyError:
            return None

    @staticmethod
    def extract_final_status_info(
        last_message: Dict[str, Any],
    ) -> Tuple[Optional[str], Optional[str]]:
        """Extract final status and message from the last message."""
        try:
            payload = last_message.get("payload", {})
            result = payload.get("result", {})
            status_info = result.get("status", {})

            final_status = status_info.get("state")
            final_message = None

            message = status_info.get("message", {})
            parts = message.get("parts", [])
            for part in parts:
                if "text" in part:
                    final_message = part["text"]
                    break

            return final_status, final_message

        except KeyError:
            return None, None

    @staticmethod
    def extract_tool_calls(messages: List[Dict[str, Any]]) -> List[ToolCall]:
        """Extract all tool calls from messages."""
        tool_calls = []
        processed_tool_calls = set()

        for message in messages:
            try:
                payload = message.get("payload", {})
                result = payload.get("result", {})
                status = result.get("status", {})
                message_data = status.get("message", {})
                parts = message_data.get("parts", [])

                for part in parts:
                    data = part.get("data", {})
                    if data.get("type") == "tool_invocation_start":
                        call_id = data.get("function_call_id")
                        if call_id and call_id not in processed_tool_calls:
                            tool_call = ToolCall(
                                call_id=call_id,
                                agent=result.get("metadata", {}).get("agent_name", ""),
                                tool_name=data.get("tool_name", ""),
                                arguments=data.get("tool_args", {}),
                                timestamp=status.get("timestamp", ""),
                            )
                            tool_calls.append(tool_call)
                            processed_tool_calls.add(call_id)

            except (KeyError, IndexError):
                continue

        return tool_calls


class ArtifactService:
    """Manages artifact discovery, categorization, and metadata."""

    def __init__(self, base_path: str, user_identity: str):
        self.base_path = base_path
        self.user_identity = user_identity

    def get_artifact_info(self, namespace: str, context_id: str) -> List[ArtifactInfo]:
        """Retrieve information about artifacts from the session directory."""
        artifact_info = []
        session_dir = os.path.join(
            self.base_path, namespace, self.user_identity, context_id
        )

        if not os.path.isdir(session_dir):
            return artifact_info

        for item in os.listdir(session_dir):
            item_path = os.path.join(session_dir, item)
            if os.path.isdir(item_path) and not item.endswith(".metadata.json"):
                artifact_info.append(
                    self._process_artifact_directory(session_dir, item, item_path)
                )

        return artifact_info

    def _process_artifact_directory(
        self, session_dir: str, artifact_name: str, item_path: str
    ) -> ArtifactInfo:
        """Process a single artifact directory and extract metadata."""
        metadata_dir = os.path.join(session_dir, f"{artifact_name}.metadata.json")
        versions = []

        if os.path.isdir(metadata_dir):
            for version_file in os.listdir(item_path):
                if not version_file.endswith(".meta"):
                    version_metadata_path = os.path.join(metadata_dir, version_file)
                    if os.path.exists(version_metadata_path):
                        try:
                            with open(version_metadata_path, "r") as f:
                                metadata = json.load(f)
                            versions.append(
                                {"version": version_file, "metadata": metadata}
                            )
                        except (json.JSONDecodeError, FileNotFoundError):
                            continue

        return ArtifactInfo(
            artifact_name=artifact_name, directory=item_path, versions=versions
        )

    def categorize_artifacts(
        self,
        artifacts: List[ArtifactInfo],
        test_case: Dict[str, Any],
        tool_calls: List[ToolCall],
    ) -> Tuple[List[ArtifactInfo], List[ArtifactInfo]]:
        """Categorize artifacts into input and output based on test case and tool calls."""
        input_artifacts = []
        output_artifacts = []

        # Get input artifact names from test case
        input_artifact_names = TestCaseService.extract_input_artifact_names(test_case)

        # Create mapping of output artifacts to creating tools
        tool_output_mapping = self._create_tool_output_mapping(tool_calls)

        # Categorize each artifact
        for artifact in artifacts:
            artifact_name = artifact.artifact_name

            # Check if this is an input artifact
            if artifact_name in input_artifact_names:
                input_artifact = self._enhance_input_artifact(artifact, test_case)
                input_artifacts.append(input_artifact)

            # All artifacts also go to output (including input ones that exist in session)
            output_artifact = self._enhance_output_artifact(
                artifact, tool_output_mapping
            )
            output_artifacts.append(output_artifact)

        return input_artifacts, output_artifacts

    def _create_tool_output_mapping(
        self, tool_calls: List[ToolCall]
    ) -> Dict[str, ToolCall]:
        """Create mapping of output filenames to the tools that created them."""
        tool_output_mapping = {}

        for tool_call in tool_calls:
            args = tool_call.arguments

            # Look for output filename in tool arguments
            output_filename = None
            if "output_filename" in args:
                output_filename = args["output_filename"]
            elif "filename" in args:
                output_filename = args["filename"]

            if output_filename:
                tool_output_mapping[output_filename] = tool_call

        return tool_output_mapping

    def _enhance_input_artifact(
        self, artifact: ArtifactInfo, test_case: Dict[str, Any]
    ) -> ArtifactInfo:
        """Enhance input artifact with test case information."""
        enhanced_artifact = ArtifactInfo(
            artifact_name=artifact.artifact_name,
            directory=artifact.directory,
            versions=artifact.versions,
            artifact_type=None,
            source_path=None,
        )

        # Add test case information
        test_case_artifacts = test_case.get("artifacts", [])
        for tc_artifact in test_case_artifacts:
            if (
                tc_artifact.get("type") == "file"
                and os.path.basename(tc_artifact["path"]) == artifact.artifact_name
            ):
                enhanced_artifact.artifact_type = tc_artifact["type"]
                enhanced_artifact.source_path = tc_artifact["path"]
                break

        return enhanced_artifact

    def _enhance_output_artifact(
        self, artifact: ArtifactInfo, tool_output_mapping: Dict[str, ToolCall]
    ) -> ArtifactInfo:
        """Enhance output artifact with tool creation information."""
        enhanced_artifact = ArtifactInfo(
            artifact_name=artifact.artifact_name,
            directory=artifact.directory,
            versions=artifact.versions,
        )

        # Add tool creation information if available
        if artifact.artifact_name in tool_output_mapping:
            creating_tool = tool_output_mapping[artifact.artifact_name]
            enhanced_artifact.created_by_tool = creating_tool.tool_name
            enhanced_artifact.created_by_call_id = creating_tool.call_id
            enhanced_artifact.creation_timestamp = creating_tool.timestamp

        return enhanced_artifact


class SummaryBuilder:
    """Main orchestrator for summary creation."""

    def __init__(self):
        self.file_service = FileService()
        self.test_case_service = TestCaseService()
        self.time_processor = TimeProcessor()
        self.message_processor = MessageProcessor()
        self.artifact_service: Optional[ArtifactService] = None

    def summarize_run(self, messages_file_path: str) -> Dict[str, Any]:
        """
        Create a comprehensive summary of a test run from messages.json file.

        Args:
            messages_file_path: Path to the messages.json file

        Returns:
            Dictionary containing the summarized metrics
        """
        try:
            # Load and validate messages
            messages = self._load_and_validate_messages(messages_file_path)
            if not messages:
                return {}

            run_path = os.path.dirname(messages_file_path)
            test_case_info_path = os.path.join(run_path, "test_case_info.json")
            test_case_info = self.file_service.load_json(test_case_info_path)
            test_case_path = test_case_info["path"]

            # Initialize summary with basic info
            summary = self._initialize_summary(messages_file_path, test_case_path)

            # Load test case
            test_case = self._load_test_case(summary, test_case_path)

            # Process messages to extract data
            self._process_messages(messages, summary, test_case)

            # Add artifact information if possible
            self._add_artifact_information(summary, test_case)

            return summary.to_dict()

        except Exception as e:
            # Return minimal summary with error information
            run_path = os.path.dirname(messages_file_path)
            return {
                "test_case_id": os.path.basename(os.path.dirname(run_path)),
                "run_id": os.path.basename(run_path),
                "errors": [f"Failed to process summary: {str(e)}"],
            }

    def _load_and_validate_messages(
        self, messages_file_path: str
    ) -> List[Dict[str, Any]]:
        """Load and validate messages from file."""
        try:
            messages = self.file_service.load_json(messages_file_path)
            return messages if isinstance(messages, list) else []
        except Exception:
            return []

    def _initialize_summary(
        self, messages_file_path: str, test_case_path: str
    ) -> RunSummary:
        """Initialize summary with basic path-derived information."""
        run_path = os.path.dirname(messages_file_path)
        run_id = os.path.basename(run_path)
        test_case_id = os.path.splitext(os.path.basename(test_case_path))[0].replace(
            ".test", ""
        )

        return RunSummary(test_case_id=test_case_id, run_id=run_id)

    def _load_test_case(
        self, summary: RunSummary, test_case_path: str
    ) -> Dict[str, Any]:
        """Load test case and update summary with test case info."""
        test_case = self.test_case_service.load_test_case(test_case_path)

        if test_case:
            summary.query = test_case.get("query", "")
            summary.target_agent = test_case.get("target_agent", "")
        else:
            summary.errors.append(f"Could not load test case: {summary.test_case_id}")
            test_case = {"artifacts": []}  # Fallback

        return test_case

    def _process_messages(
        self,
        messages: List[Dict[str, Any]],
        summary: RunSummary,
        test_case: Dict[str, Any],
    ):
        """Process all messages to extract relevant information."""
        if not messages:
            return

        first_message = messages[0]
        last_message = messages[-1]

        # Extract basic metadata
        namespace, target_agent = self.message_processor.extract_namespace_and_agent(
            first_message
        )
        if namespace:
            summary.namespace = namespace
        if target_agent:
            summary.target_agent = target_agent
        else:
            summary.errors.append(
                "Could not find target agent and namespace in the first message."
            )

        context_id = self.message_processor.extract_context_id(first_message)
        if context_id:
            summary.context_id = context_id

        # Extract final status information
        final_status, final_message = self.message_processor.extract_final_status_info(
            last_message
        )
        if final_status:
            summary.final_status = final_status
        if final_message:
            summary.final_message = final_message

        # Extract time metrics
        self._process_time_metrics(first_message, last_message, summary)

        # Extract tool calls
        summary.tool_calls = self.message_processor.extract_tool_calls(messages)

    def _process_time_metrics(
        self,
        first_message: Dict[str, Any],
        last_message: Dict[str, Any],
        summary: RunSummary,
    ):
        """Process and calculate time metrics."""
        start_time = self.time_processor.extract_start_time(first_message)
        end_time = self.time_processor.extract_end_time(last_message)

        summary.time_metrics.start_time = start_time
        summary.time_metrics.end_time = end_time

        if start_time and end_time:
            duration, normalized_start = self.time_processor.calculate_duration(
                start_time, end_time
            )
            if duration is not None:
                summary.time_metrics.duration_seconds = duration
                if normalized_start:
                    summary.time_metrics.start_time = normalized_start
            else:
                summary.errors.append(
                    "Could not parse start or end time to calculate duration."
                )

    def _add_artifact_information(self, summary: RunSummary, test_case: Dict[str, Any]):
        """Add artifact information if configuration is available."""
        if not summary.namespace or not summary.context_id:
            return

        try:
            # Initialize artifact service if not already done
            if not self.artifact_service:
                base_path, user_identity = ConfigService.get_artifact_config()
                self.artifact_service = ArtifactService(base_path, user_identity)

            # Get and categorize artifacts
            all_artifacts = self.artifact_service.get_artifact_info(
                summary.namespace, summary.context_id
            )

            input_artifacts, output_artifacts = (
                self.artifact_service.categorize_artifacts(
                    all_artifacts, test_case, summary.tool_calls
                )
            )

            summary.input_artifacts = input_artifacts
            summary.output_artifacts = output_artifacts

        except Exception as e:
            summary.errors.append(f"Could not add artifact info: {str(e)}")


def summarize_run(messages_file_path: str) -> Dict[str, Any]:
    """
    Main entry point for summarizing a test run.

    This function maintains compatibility with the original API while using
    the refactored implementation.

    Args:
        messages_file_path: Path to the messages.json file

    Returns:
        Dictionary containing the summarized metrics
    """
    builder = SummaryBuilder()
    return builder.summarize_run(messages_file_path)


def main():
    """Main entry point for command-line usage."""
    import sys

    if len(sys.argv) != 2:
        print("Usage: python summarize_refactored.py <messages_file_path>")
        sys.exit(1)

    messages_file_path = sys.argv[1]

    if not os.path.exists(messages_file_path):
        print(f"Error: Messages file not found at: {messages_file_path}")
        sys.exit(1)

    try:
        # Generate summary
        summary_data = summarize_run(messages_file_path)

        # Save summary file
        output_dir = os.path.dirname(messages_file_path)
        summary_file_path = os.path.join(output_dir, "summary.json")

        FileService.save_json(summary_data, summary_file_path)
        print(f"Summary file created at: {summary_file_path}")

    except Exception as e:
        print(f"Error generating summary: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
