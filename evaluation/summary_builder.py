"""
Refactored summarization module with improved structure and readability.
This module processes test run messages and generates comprehensive summaries.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import requests
import yaml

from .shared import TestSuiteConfiguration, load_test_case

log = logging.getLogger(__name__)


@dataclass
class ToolCall:
    """Structured representation of a tool call."""

    call_id: str
    agent: str
    tool_name: str
    arguments: dict[str, any]
    timestamp: str


@dataclass
class ArtifactInfo:
    """Comprehensive artifact information with categorization."""

    artifact_name: str
    directory: str
    versions: list[dict[str, any]]
    artifact_type: str | None = None
    source_path: str | None = None
    created_by_tool: str | None = None
    created_by_call_id: str | None = None
    creation_timestamp: str | None = None


@dataclass
class TimeMetrics:
    """Time-related metrics for a test run."""

    start_time: str | None = None
    end_time: str | None = None
    duration_seconds: float | None = None


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
    tool_calls: list[ToolCall] = field(default_factory=list)
    input_artifacts: list[ArtifactInfo] = field(default_factory=list)
    output_artifacts: list[ArtifactInfo] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, any]:
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

    _config_cache: dict[str, any] = {}

    @classmethod
    def load_yaml_with_includes(cls, file_path: str) -> dict[str, any]:
        """Load YAML file with !include directive processing and caching."""
        if file_path in cls._config_cache:
            return cls._config_cache[file_path]

        try:
            with open(file_path) as f:
                content = f.read()

            content = cls._process_includes(content, file_path)
            config = yaml.safe_load(content)
            cls._config_cache[file_path] = config
            return config

        except (FileNotFoundError, yaml.YAMLError) as e:
            raise ValueError(f"Failed to load YAML config from {file_path}: {e}") from e

    @staticmethod
    def _process_includes(content: str, base_file_path: str) -> str:
        """Process !include directives in YAML content."""
        include_pattern = re.compile(r"^\s*!include\s+(.*)$", re.MULTILINE)
        base_dir = Path(base_file_path).parent

        def replacer(match):
            include_path_str = match.group(1).strip()
            include_path = base_dir / include_path_str
            with include_path.open() as inc_f:
                return inc_f.read()

        # Repeatedly replace includes until none are left
        while include_pattern.search(content):
            content = include_pattern.sub(replacer, content)

        return content

    @classmethod
    def get_local_artifact_config(cls) -> tuple[str, str]:
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
            raise ValueError(f"Failed to load artifact configuration: {e}") from e


class FileService:
    """Handles file operations and path management."""

    @staticmethod
    def load_json(filepath: Path) -> any:
        """Load JSON data from file."""
        try:
            with filepath.open() as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            raise ValueError(f"Failed to load JSON from {filepath}: {e}") from e

    @staticmethod
    def save_json(data: any, filepath: Path):
        """Save data as JSON to file."""
        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with filepath.open("w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            raise ValueError(f"Failed to save JSON to {filepath}: {e}") from e


class TestCaseService:
    """Handles test case loading and validation."""

    @staticmethod
    def load_test_case(test_case_id: str) -> dict[str, any] | None:
        """Load test case definition with error handling."""
        try:
            return load_test_case(test_case_id)
        except Exception:
            return None

    @staticmethod
    def extract_input_artifact_names(test_case: dict[str, any]) -> set[str]:
        """Extract input artifact names from test case definition."""
        input_artifact_names = set()
        test_case_artifacts = test_case.get("artifacts", [])

        for tc_artifact in test_case_artifacts:
            if tc_artifact.get("type") == "file" and "path" in tc_artifact:
                # Extract filename from path (e.g., "artifacts/sample.csv" -> "sample.csv")
                artifact_name = Path(tc_artifact["path"]).name
                input_artifact_names.add(artifact_name)

        return input_artifact_names


class TimeProcessor:
    """Handles timestamp parsing and duration calculations."""

    @staticmethod
    def extract_start_time(first_message: dict[str, any]) -> str | None:
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
    def extract_end_time(last_message: dict[str, any]) -> str | None:
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
    ) -> tuple[float | None, str | None]:
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
        first_message: dict[str, any],
    ) -> tuple[str | None, str | None]:
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
    def extract_context_id(first_message: dict[str, any]) -> str | None:
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
        last_message: dict[str, any],
    ) -> tuple[str | None, str | None]:
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
    def extract_tool_calls(messages: list[dict[str, any]]) -> list[ToolCall]:
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

    def __init__(self, config: TestSuiteConfiguration):
        self.config = config
        self.is_remote = config.remote is not None
        if self.is_remote:
            self.base_url = config.remote.environment.get("EVAL_REMOTE_URL")
            self.auth_token = config.remote.environment.get("EVAL_AUTH_TOKEN")
        else:
            self.base_path, self.user_identity = (
                ConfigService.get_local_artifact_config()
            )

    def get_artifacts(
        self, namespace: str, context_id: str
    ) -> list[ArtifactInfo]:
        """Retrieve artifact information, either locally or from a remote API."""
        if self.is_remote:
            return self._get_remote_artifacts(context_id)
        else:
            return self._get_local_artifacts(namespace, context_id)

    def _get_remote_artifacts(self, context_id: str) -> list[ArtifactInfo]:
        """Fetch artifacts from the remote API."""
        if not self.base_url:
            return []

        url = f"{self.base_url}/api/v2/artifacts"
        params = {"session_id": context_id}

        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
            log.info("Auth token found and added to headers.")
        else:
            log.warning("No auth token found for remote artifact request.")

        log.info(f"Fetching remote artifacts from URL: {url} with params: {params}")

        try:
            with requests.Session() as session:
                session.headers.update(headers)
                response = session.get(url, params=params, allow_redirects=False)

            log.info(f"Initial response status: {response.status_code}")

            # Handle 307 Temporary Redirect manually
            if response.status_code == 307:
                redirect_url = response.headers.get("Location")
                if not redirect_url:
                    log.error(
                        f"Server sent 307 redirect without a Location header. Full headers: {response.headers}"
                    )
                    response.raise_for_status()  # Re-raise the error to halt execution

                log.info(f"Handling 307 redirect to: {redirect_url}")
                with requests.Session() as redirect_session:
                    redirect_session.headers.update(headers)
                    # The redirected URL from the server should be complete, so no params needed.
                    response = redirect_session.get(redirect_url)

            response.raise_for_status()

            # Handle empty response body after potential redirect
            if not response.text:
                log.info("Received empty response from artifact API, assuming no artifacts.")
                return []

            artifacts_data = response.json()

            artifact_infos = []
            for data in artifacts_data:
                # The API returns a flat list of latest versions, so we reconstruct
                # the version list to match the structure ArtifactInfo expects.
                version_info = {
                    "version": data.get("version", 0),
                    "metadata": {
                        "mime_type": data.get("mime_type"),
                        "size": data.get("size"),
                        "last_modified": data.get("last_modified"),
                        "description": data.get("description"),
                        "schema": data.get("schema"),
                    },
                }
                info = ArtifactInfo(
                    artifact_name=data.get("filename"),
                    directory="",  # Not applicable for remote
                    versions=[version_info],
                )
                artifact_infos.append(info)
            return artifact_infos

        except requests.RequestException as e:
            log.error(f"Failed to fetch remote artifacts: {e}")
            return []
        except json.JSONDecodeError:
            log.error("Failed to decode JSON response from artifact API")
            return []

    def _get_local_artifacts(
        self, namespace: str, context_id: str
    ) -> list[ArtifactInfo]:
        """Retrieve information about artifacts from the local session directory."""
        artifact_info = []
        session_dir = (
            Path(self.base_path) / namespace / self.user_identity / context_id
        )

        if not session_dir.is_dir():
            return artifact_info

        for item_path in session_dir.iterdir():
            if item_path.is_dir() and not item_path.name.endswith(".metadata.json"):
                artifact_info.append(
                    self._process_artifact_directory(
                        session_dir, item_path.name, item_path
                    )
                )

        return artifact_info

    def _process_artifact_directory(
        self, session_dir: Path, artifact_name: str, item_path: Path
    ) -> ArtifactInfo:
        """Process a single artifact directory and extract metadata."""
        metadata_dir = session_dir / f"{artifact_name}.metadata.json"
        versions = []

        if metadata_dir.is_dir():
            for version_path in item_path.iterdir():
                if not version_path.name.endswith(".meta"):
                    version_metadata_path = metadata_dir / version_path.name
                    if version_metadata_path.exists():
                        try:
                            with version_metadata_path.open() as f:
                                metadata = json.load(f)
                            versions.append(
                                {"version": version_path.name, "metadata": metadata}
                            )
                        except (json.JSONDecodeError, FileNotFoundError):
                            continue

        return ArtifactInfo(
            artifact_name=artifact_name, directory=str(item_path), versions=versions
        )

    def categorize_artifacts(
        self,
        artifacts: list[ArtifactInfo],
        test_case: dict[str, any],
        tool_calls: list[ToolCall],
    ) -> tuple[list[ArtifactInfo], list[ArtifactInfo]]:
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
        self, tool_calls: list[ToolCall]
    ) -> dict[str, ToolCall]:
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
        self, artifact: ArtifactInfo, test_case: dict[str, any]
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
                and Path(tc_artifact["path"]).name == artifact.artifact_name
            ):
                enhanced_artifact.artifact_type = tc_artifact["type"]
                enhanced_artifact.source_path = tc_artifact["path"]
                break

        return enhanced_artifact

    def _enhance_output_artifact(
        self, artifact: ArtifactInfo, tool_output_mapping: dict[str, ToolCall]
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

    def __init__(self, config: TestSuiteConfiguration):
        self.config = config
        self.file_service = FileService()
        self.test_case_service = TestCaseService()
        self.time_processor = TimeProcessor()
        self.message_processor = MessageProcessor()
        self.artifact_service = ArtifactService(self.config)

    def summarize_run(self, messages_file_path: str) -> dict[str, any]:
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

            run_path = Path(messages_file_path).parent
            test_case_info_path = run_path / "test_case_info.json"
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
            run_path = Path(messages_file_path).parent
            return {
                "test_case_id": run_path.parent.name,
                "run_id": run_path.name,
                "errors": [f"Failed to process summary: {str(e)}"],
            }

    def _load_and_validate_messages(
        self, messages_file_path: str
    ) -> list[dict[str, any]]:
        """Load and validate messages from file."""
        try:
            messages = self.file_service.load_json(Path(messages_file_path))
            return messages if isinstance(messages, list) else []
        except Exception:
            return []

    def _initialize_summary(
        self, messages_file_path: str, test_case_path: str
    ) -> RunSummary:
        """Initialize summary with basic path-derived information."""
        run_path = Path(messages_file_path).parent
        run_id = run_path.name
        test_case_id = Path(test_case_path).stem.replace(".test", "")

        return RunSummary(test_case_id=test_case_id, run_id=run_id)

    def _load_test_case(
        self, summary: RunSummary, test_case_path: str
    ) -> dict[str, any]:
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
        messages: list[dict[str, any]],
        summary: RunSummary,
        test_case: dict[str, any],
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
        first_message: dict[str, any],
        last_message: dict[str, any],
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

    def _add_artifact_information(self, summary: RunSummary, test_case: dict[str, any]):
        """Add artifact information if configuration is available."""
        if not summary.context_id:
            return

        try:
            # Get and categorize artifacts
            all_artifacts = self.artifact_service.get_artifacts(
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


def summarize_run(
    messages_file_path: str, config: TestSuiteConfiguration
) -> dict[str, any]:
    """
    Main entry point for summarizing a test run.

    This function maintains compatibility with the original API while using
    the refactored implementation.

    Args:
        messages_file_path: Path to the messages.json file
        config: The test suite configuration.

    Returns:
        Dictionary containing the summarized metrics
    """
    builder = SummaryBuilder(config)
    return builder.summarize_run(messages_file_path)


def main():
    """Main entry point for command-line usage."""
    import sys

    from .shared import EvaluationConfigLoader

    if len(sys.argv) != 2:
        log.info("Usage: python summarize_refactored.py <messages_file_path>")
        sys.exit(1)

    messages_file_path = Path(sys.argv[1])

    if not messages_file_path.exists():
        log.info(f"Error: Messages file not found at: {messages_file_path}")
        sys.exit(1)

    try:
        # This main function is for standalone testing. It needs a config.
        # We'll assume a default config for this purpose.
        config_path = Path.cwd() / "tests" / "evaluation" / "config.json"
        if not config_path.exists():
            log.error(f"Default test config not found at {config_path}")
            return
        config_loader = EvaluationConfigLoader(str(config_path))
        config = config_loader.load_configuration()

        # Generate summary
        summary_data = summarize_run(str(messages_file_path), config)

        # Save summary file
        output_dir = messages_file_path.parent
        summary_file_path = output_dir / "summary.json"

        FileService.save_json(summary_data, summary_file_path)
        log.info(f"Summary file created at: {summary_file_path}")

    except Exception as e:
        log.error(f"Error generating summary: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
