"""
Refactored evaluation runner with improved structure and readability.
This module orchestrates the evaluation of AI models against test cases.
"""

import json
import logging
import mimetypes
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

import click
import requests
from dotenv import load_dotenv

from .evaluator import EvaluationOrchestrator
from .message_organizer import MessageOrganizer
from .report_generator import ReportGenerator
from .shared import (
    DEFAULT_STARTUP_WAIT_TIME,
    DEFAULT_TEST_TIMEOUT,
    EVALUATION_DIR,
    MAX_ARTIFACT_SIZE_MB,
    EvaluationConfigLoader,
    TestSuiteConfiguration,
    get_local_base_url,
)
from .subscriber import Subscriber
from .summary_builder import SummaryBuilder

log = logging.getLogger(__name__)


def _error_exit(message: str):
    """Logs an error message and exits."""
    log.error(message)
    sys.exit(1)


def _ensure_eval_backend_config_exists():
    """Checks for eval_backend.yaml and creates it from a template if missing."""
    project_root = Path.cwd()
    configs_dir = project_root / "configs"
    eval_backend_config_path = configs_dir / "eval_backend.yaml"

    if eval_backend_config_path.exists():
        return

    click.echo(
        f"'{eval_backend_config_path.relative_to(project_root)}' not found. Creating it..."
    )

    if not (configs_dir / "shared_config.yaml").exists():
        _error_exit(
            "Error: 'configs/shared_config.yaml' not found. Please run 'sam init' first."
        )

    try:
        # This is a simplified way to get the template content.
        # In a real CLI, you'd use a more robust method like `importlib.resources`.
        template_path = Path(__file__).parent.parent / "templates" / "eval_backend_template.yaml"
        with open(template_path, encoding="utf-8") as f:
            template_content = f.read()

        with open(eval_backend_config_path, "w", encoding="utf-8") as f:
            f.write(template_content)
        click.echo(
            click.style(
                f"Successfully created '{eval_backend_config_path.relative_to(project_root)}'.",
                fg="green",
            )
        )
    except Exception as e:
        _error_exit(f"Failed to create eval_backend.yaml: {e}")


def _ensure_sam_rest_gateway_installed():
    """Checks if the sam-rest-gateway package is installed for local evaluation."""
    try:
        metadata.distribution("sam-rest-gateway")
    except metadata.PackageNotFoundError:
        _error_exit(
            "Error: 'sam-rest-gateway' is not installed. "
            "Please install it using: "
            'pip install "sam-rest-gateway @ git+https://github.com/SolaceLabs/solace-agent-mesh-core-plugins#subdirectory=sam-rest-gateway"'
        )


@dataclass
class TestRun:
    """Represents a single test execution with all necessary parameters."""

    agent: str
    query: str
    artifacts: list[str]
    wait_time: int
    test_case_file: str
    run_num: int

    @property
    def test_case_id(self) -> str:
        """Extract test case ID from filename."""
        return Path(self.test_case_file).stem.replace(".test", "")


class ProcessManager:
    """Manages subprocess lifecycle for the Solace AI Connector."""

    def __init__(self, config: TestSuiteConfiguration, verbose: bool = False):
        self.config = config
        self.process: subprocess.Popen | None = None
        self.namespace: str | None = None
        self.verbose = verbose

    def start_services(self) -> tuple[subprocess.Popen, str]:
        """Start the Solace AI Connector and return process and namespace."""
        load_dotenv()
        self.namespace = f"eval-{uuid.uuid4()}"
        os.environ["NAMESPACE"] = self.namespace

        # Set broker environment variables from the required configuration
        log.info("Setting broker configuration from test suite...")
        for key, value in self.config.broker.dict().items():
            if value is not None:
                env_key = f"SOLACE_BROKER_{key.upper()}"
                os.environ[env_key] = str(value)
                log.info(f"  - Set {env_key}")

        agent_files = self.config.agent_configs

        command = [sys.executable, "-m", "solace_ai_connector.main", *agent_files]

        log.info("Starting Solace AI Connector as a subprocess...")
        project_root = Path(EVALUATION_DIR).parent.resolve()

        self.process = subprocess.Popen(
            command, stdout=sys.stdout, stderr=sys.stderr, cwd=project_root
        )

        log.info("Waiting for server to become healthy...")
        self._wait_for_server_ready(get_local_base_url())

        return self.process, self.namespace

    def _wait_for_server_ready(self, base_url: str):
        """Poll the health endpoint until the server is ready."""
        start_time = time.time()
        health_url = f"{base_url}/health"

        while time.time() - start_time < DEFAULT_STARTUP_WAIT_TIME:
            try:
                response = requests.get(health_url)
                if response.status_code == 200:
                    log.info("Server is healthy.")
                    time.sleep(5)
                    return
            except requests.ConnectionError:
                # Server is not yet available, wait and retry
                time.sleep(1)
            except Exception as e:
                log.error(f"An unexpected error occurred during health check: {e}")
                time.sleep(1)

        raise RuntimeError(
            f"Server did not become healthy within {DEFAULT_STARTUP_WAIT_TIME} seconds."
        )

    def stop_services(self, subscriber: Subscriber | None = None):
        """Clean up running processes."""
        if subscriber:
            log.info("Terminating subscriber")
            subscriber.stop()
            subscriber.join()
            log.info("Subscriber terminated.")

        if self.process:
            log.info("Terminating subprocess")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
                log.info("Subprocess terminated.")
            except subprocess.TimeoutExpired:
                log.info("Subprocess did not terminate gracefully, killing.")
                self.process.kill()

        log.info("Process cleanup completed.")


class TaskService:
    """Handles task submission and tracking."""

    def __init__(self, config: TestSuiteConfiguration, verbose: bool = False):
        self.verbose = verbose
        self.config = config
        if config.remote:
            self.base_url = config.remote.environment.get("EVAL_REMOTE_URL")
        else:
            self.base_url = get_local_base_url()

    def submit_task(
        self, agent_name: str, message: str, artifact_paths: list[str] | None = None
    ) -> str | None:
        """Submit a test case to the agent and return the task ID."""
        log.info("Sending test request")
        url = f"{self.base_url}/api/v2/tasks"
        data = {
            "agent_name": agent_name,
            "prompt": message,
        }

        headers = {}
        if self.config.remote:
            auth_token = self.config.remote.environment.get("EVAL_AUTH_TOKEN")
            if auth_token:
                headers["Authorization"] = f"Bearer {auth_token}"

        files_to_upload = []
        if artifact_paths:
            files_to_upload = self._prepare_file_uploads(artifact_paths)

        try:
            with requests.Session() as session:
                response = session.post(url, data=data, files=files_to_upload, headers=headers)

            response.raise_for_status()
            task_id = response.json()["taskId"]
            log.info(f"Task submitted with ID: {task_id}")
            return task_id

        except requests.RequestException as e:
            log.error(f"Failed to submit task: {e}")
            return None
        finally:
            self._close_file_uploads(files_to_upload)

    def _prepare_file_uploads(self, artifact_paths: list[str]) -> list[tuple]:
        """Prepare file uploads for the request."""
        files_to_upload = []
        for path_str in artifact_paths:
            path = Path(path_str)
            # Check file size before reading
            try:
                file_size_mb = path.stat().st_size / (1024 * 1024)
                if file_size_mb > MAX_ARTIFACT_SIZE_MB:
                    log.warning(
                        f"Artifact '{path.name}' is {file_size_mb:.2f} MB, "
                        f"which is larger than the recommended maximum of {MAX_ARTIFACT_SIZE_MB} MB. "
                        "This may cause memory issues."
                    )
            except OSError as e:
                log.error(f"Could not get size of artifact {path}: {e}")
                continue

            mimetype, _ = mimetypes.guess_type(path)
            if mimetype is None:
                mimetype = "text/plain"
            # Read file content with context manager
            with path.open("rb") as f:
                file_content = f.read()
            files_to_upload.append(("files", (path.name, file_content, mimetype)))
        return files_to_upload

    def _close_file_uploads(self, files_to_upload: list[tuple]):
        """Close file handles after upload (no longer needed)."""
        # No longer needed
        pass


class FileService:
    """Handles file operations and path management."""

    @staticmethod
    def ensure_directory(path: Path):
        """Ensure directory exists, create if necessary."""
        path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def remove_directory(path: Path):
        """Remove directory and all contents."""
        if path.exists():
            shutil.rmtree(path)

    @staticmethod
    def save_json(data: any, filepath: Path):
        """Save data as JSON to file."""
        with filepath.open("w") as f:
            json.dump(data, f, indent=4)

    @staticmethod
    def load_json(filepath: Path) -> any:
        """Load JSON data from file."""
        with filepath.open() as f:
            return json.load(f)


class TestRunBuilder:
    """Builds test run configurations from test cases."""

    def __init__(self, config: TestSuiteConfiguration):
        self.config = config

    def build_test_runs(self) -> list[TestRun]:
        """Build all test runs from configuration."""
        test_runs = []

        for test_case_path in self.config.test_case_files:
            test_case = FileService.load_json(Path(test_case_path))

            artifact_paths = self._get_artifact_paths(test_case, test_case_path)

            for run_num in range(1, self.config.run_count + 1):
                test_run = TestRun(
                    agent=test_case["target_agent"],
                    query=test_case["query"],
                    artifacts=artifact_paths,
                    wait_time=test_case.get("wait_time", DEFAULT_TEST_TIMEOUT),
                    test_case_file=test_case_path,
                    run_num=run_num,
                )
                test_runs.append(test_run)

        return test_runs

    def _get_artifact_paths(self, test_case: dict, test_case_path: str) -> list[str]:
        """Extract artifact paths from test case."""
        artifact_paths = []
        if "artifacts" in test_case:
            test_case_dir = Path(test_case_path).parent
            for artifact in test_case["artifacts"]:
                if artifact.get("type") == "file":
                    artifact_paths.append(str(test_case_dir / artifact["path"]))
        return artifact_paths


class TestExecutor:
    """Executes individual test runs."""

    def __init__(self, task_service: TaskService, file_service: FileService, verbose: bool = False):
        self.task_service = task_service
        self.file_service = file_service
        self.verbose = verbose

    def execute_test(
        self,
        test_run: TestRun,
        model_results_path: Path,
        task_mappings: dict[str, str],
        subscriber: Subscriber,
        task_mappings_lock: threading.Lock,
    ) -> bool:
        """Execute a single test case and wait for completion."""
        log.info(
            f"Starting test: {test_run.test_case_file} (run {test_run.run_num})"
        )

        # Submit the task
        task_id = self.task_service.submit_task(
            test_run.agent, test_run.query, test_run.artifacts
        )

        if not task_id:
            log.error(
                f"Failed to start test case: {test_run.test_case_file} (run {test_run.run_num})"
            )
            return False

        # Set up result directory
        test_case_name = Path(test_run.test_case_file).stem.replace(".test", "")
        run_dir = model_results_path / test_case_name / f"run_{test_run.run_num}"
        self.file_service.ensure_directory(run_dir)

        # Save test case path for summary builder
        test_info = {"path": test_run.test_case_file}
        self.file_service.save_json(test_info, run_dir / "test_case_info.json")

        # Track the task
        with task_mappings_lock:
            task_mappings[task_id] = str(run_dir)
        subscriber.active_tasks.add(task_id)

        # Wait for completion
        return self._wait_for_completion(task_id, test_run.wait_time, subscriber)

    def _wait_for_completion(
        self, task_id: str, wait_time: int, subscriber: Subscriber
    ) -> bool:
        """Wait for task completion with timeout."""
        log.info(
            f"Waiting for task {task_id} to complete (timeout: {wait_time} seconds)..."
        )

        start_time = time.time()
        while task_id in subscriber.active_tasks:
            if time.time() - start_time > wait_time:
                log.warning(f"Task {task_id} timed out after {wait_time} seconds")
                subscriber.active_tasks.discard(task_id)
                return False
            time.sleep(1)

        log.info(f"Task {task_id} completed successfully")
        return True


class ModelEvaluator:
    """Handles the evaluation of a single model."""

    def __init__(self, config: TestSuiteConfiguration, verbose: bool = False):
        self.config = config
        self.process_manager = ProcessManager(config, verbose=verbose)
        self.task_service = TaskService(config, verbose=verbose)
        self.file_service = FileService()
        self.test_builder = TestRunBuilder(config)
        self.test_executor = TestExecutor(self.task_service, self.file_service, verbose=verbose)
        self.verbose = verbose
        self._task_mappings_lock = threading.Lock()

    def evaluate_model(
        self, model_config: dict[str, any], base_results_path: Path
    ) -> float:
        """Evaluate a single model and return execution time."""
        model_name = model_config.name
        log.info(f"Starting evaluation for model: {model_name}")
        start_time = time.time()

        # Set environment variables for the model
        self._set_model_environment(model_config)

        # Set up paths
        model_results_path = base_results_path / model_name
        self.file_service.ensure_directory(model_results_path)

        # Start services
        app_process, namespace = self.process_manager.start_services()

        # Set up subscriber
        subscriber = self._setup_subscriber(namespace, model_results_path)

        try:
            # Execute tests
            successful_tests = self._execute_all_tests(model_results_path, subscriber)
            log.info(f"Completed {successful_tests} tests successfully")

        except Exception as e:
            log.error(f"Error during test case execution for model {model_name}: {e}")
        finally:
            # Cleanup
            task_mappings = getattr(self, "_task_mappings", {})
            self._cleanup_model_evaluation(
                app_process, subscriber, model_results_path, task_mappings
            )

        end_time = time.time()
        execution_time = end_time - start_time
        log.info(
            f"Evaluation for model: {model_name} complete in {execution_time:.2f} seconds"
        )

        return execution_time

    def _set_model_environment(self, model_config: dict[str, any]):
        """Set environment variables for the model."""
        for key, value in model_config.environment.variables.items():
            if value is not None:
                os.environ[key] = value

    def _setup_subscriber(self, namespace: str, model_results_path: Path) -> Subscriber:
        """Set up and start the subscriber."""
        subscription_ready_event = threading.Event()
        subscriber = Subscriber(
            self.config.broker,
            namespace,
            set(),
            None,
            subscription_ready_event,
            model_results_path,
        )
        subscriber.start()

        log.info("Waiting for subscriber to be ready...")
        subscription_ready_event.wait()
        log.info("Subscriber is ready.")

        return subscriber

    def _execute_all_tests(
        self, model_results_path: Path, subscriber: Subscriber
    ) -> int:
        """Execute all test cases in parallel and return count of successful tests."""
        test_runs = self.test_builder.build_test_runs()

        self._task_mappings = {}
        total_tests = len(test_runs)
        successful_tests = 0

        log.info(
            f"Starting parallel execution of {total_tests} tests with {self.config.workers} workers."
        )

        with ThreadPoolExecutor(max_workers=self.config.workers) as executor:
            # Create a dictionary to map futures to their test_run
            future_to_run = {
                executor.submit(
                    self.test_executor.execute_test,
                    test_run,
                    model_results_path,
                    self._task_mappings,
                    subscriber,
                    self._task_mappings_lock,  # Pass the lock to the worker
                ): test_run
                for test_run in test_runs
            }

            # Process results as they complete
            for i, future in enumerate(as_completed(future_to_run), 1):
                test_run = future_to_run[future]
                log.info(
                    f"Processing result for test {i}/{total_tests}: {test_run.test_case_id}"
                )
                try:
                    success = future.result()
                    if success:
                        successful_tests += 1
                    else:
                        log.warning(
                            f"Test {test_run.test_case_id} (run {test_run.run_num}) failed or timed out."
                        )
                except Exception as e:
                    log.error(
                        f"Test {test_run.test_case_id} (run {test_run.run_num}) generated an exception: {e}",
                        exc_info=True,
                    )

        return successful_tests

    def _cleanup_model_evaluation(
        self,
        app_process: subprocess.Popen,
        subscriber: Subscriber,
        model_results_path: Path,
        task_mappings: dict[str, str],
    ):
        """Clean up after model evaluation."""
        self.process_manager.stop_services(subscriber)

        # Save task mappings
        mappings_file = model_results_path / "task_mappings.json"
        self.file_service.save_json(task_mappings, mappings_file)
        log.info(f"Task mappings saved to {mappings_file}")


class ResultsProcessor:
    """Handles post-processing of evaluation results."""

    def __init__(self, file_service: FileService, verbose: bool = False):
        self.file_service = file_service
        self.summary_builder: SummaryBuilder | None = None
        self.verbose = verbose

    def summarize_results(self, base_results_path: Path, config: TestSuiteConfiguration):
        """Generate summaries for all test results."""
        log.info("Summarizing results")

        self.summary_builder = SummaryBuilder(config)

        for model_path in base_results_path.iterdir():
            if not model_path.is_dir():
                continue
            self._process_model_results(model_path)

    def _process_model_results(self, model_path: Path):
        """Process results for a single model."""
        for test_case_path in model_path.iterdir():
            if not test_case_path.is_dir():
                continue
            self._process_test_case_results(test_case_path)

    def _process_test_case_results(self, test_case_path: Path):
        """Process results for a single test case."""
        for run_path in test_case_path.iterdir():
            if not run_path.is_dir():
                continue

            messages_file = run_path / "messages.json"
            if messages_file.exists():
                summary_data = self.summary_builder.summarize_run(messages_file)
                summary_file = run_path / "summary.json"
                self.file_service.save_json(summary_data, summary_file)
                log.info(f"Summary created for {run_path}")


class EvaluationRunner:
    """Main orchestrator that coordinates the entire evaluation process."""

    def __init__(self, verbose: bool = False):
        self.config: TestSuiteConfiguration | None = None
        self.file_service = FileService()
        self.results_processor = ResultsProcessor(self.file_service, verbose=verbose)
        self.report_generator: ReportGenerator | None = None
        self.verbose = verbose

    def run_evaluation(self, config_path: str):
        """Main entry point for the evaluation process."""
        start_time = time.time()

        try:
            # Load and validate configuration
            self._load_configuration(config_path)

            # Set up results directory in the current working directory
            base_results_path = Path.cwd() / "results" / self.config.results_directory
            self._setup_results_directory(base_results_path)

            # Run model evaluations
            if self.config.remote:
                model_execution_times = self._run_remote_evaluation(base_results_path)
            else:
                model_execution_times = self._run_local_evaluation(base_results_path)

            # Post-process results
            self._post_process_results(
                base_results_path, model_execution_times, config_path
            )

            # Save overall statistics
            self._save_execution_stats(base_results_path, start_time)

            # Generate reports
            self._generate_reports(config_path, base_results_path)

            # Display summary
            self._display_summary(base_results_path)

        except Exception as e:
            log.error(f"Evaluation failed: {e}")
            raise

    def _load_configuration(self, config_path: str):
        """Load and validate the evaluation configuration."""
        config_loader = EvaluationConfigLoader(config_path)
        self.config = config_loader.load_configuration()
        self.report_generator = ReportGenerator(config_path)
        log.info("Configuration loaded and validated successfully.")

    def _setup_results_directory(self, base_results_path: Path):
        """Set up the results directory."""
        # Clean up existing results
        self.file_service.remove_directory(base_results_path)
        self.file_service.ensure_directory(base_results_path)

        log.info(f"Results directory set up at: {base_results_path}")

    def _run_local_evaluation(self, base_results_path: Path) -> dict[str, float]:
        """Run the full local evaluation with service management."""
        _ensure_eval_backend_config_exists()
        _ensure_sam_rest_gateway_installed()
        log.info("Starting local evaluation")
        model_execution_times = {}

        # This loop iterates through the models defined in the config
        for model_config in self.config.model_configurations:
            # ModelEvaluator manages the lifecycle of local services for each model
            model_evaluator = ModelEvaluator(self.config, verbose=self.verbose)
            execution_time = model_evaluator.evaluate_model(
                model_config, base_results_path
            )
            model_execution_times[model_config.name] = execution_time

        return model_execution_times

    def _run_remote_evaluation(self, base_results_path: Path) -> dict[str, float]:
        """Run evaluation against a remote endpoint in parallel."""
        remote_url = self.config.remote.environment.get("EVAL_REMOTE_URL")
        log.info(f"Starting remote evaluation against: {remote_url}")
        start_time = time.time()

        # Check if the remote server is healthy before proceeding
        process_manager = ProcessManager(self.config, self.verbose)
        process_manager._wait_for_server_ready(remote_url)

        # Instantiate services with the remote configuration
        task_service = TaskService(self.config, self.verbose)
        test_builder = TestRunBuilder(self.config)
        test_executor = TestExecutor(task_service, self.file_service, self.verbose)

        # In remote mode, there's no model loop. We create a single "remote" results directory.
        remote_results_path = base_results_path / "remote"
        self.file_service.ensure_directory(remote_results_path)

        # The subscriber needs to be configured for remote use.
        subscriber = self._setup_remote_subscriber(str(remote_results_path))

        task_mappings = {}
        try:
            test_runs = test_builder.build_test_runs()
            successful_tests = 0
            task_mappings_lock = threading.Lock()

            log.info(
                f"Starting parallel execution of {len(test_runs)} remote tests with {self.config.workers} workers."
            )

            with ThreadPoolExecutor(max_workers=self.config.workers) as executor:
                future_to_run = {
                    executor.submit(
                        test_executor.execute_test,
                        test_run,
                        remote_results_path,
                        task_mappings,
                        subscriber,
                        task_mappings_lock,
                    ): test_run
                    for test_run in test_runs
                }

                for i, future in enumerate(as_completed(future_to_run), 1):
                    test_run = future_to_run[future]
                    log.info(
                        f"Processing result for remote test {i}/{len(test_runs)}: {test_run.test_case_id}"
                    )
                    try:
                        success = future.result()
                        if success:
                            successful_tests += 1
                    except Exception as e:
                        log.error(
                            f"Remote test {test_run.test_case_id} generated an exception: {e}",
                            exc_info=True,
                        )

            log.info(f"Completed {successful_tests} remote tests successfully")

        finally:
            if subscriber:
                subscriber.stop()
                subscriber.join()

            # Save task mappings for remote run
            mappings_file = remote_results_path / "task_mappings.json"
            self.file_service.save_json(task_mappings, mappings_file)

        execution_time = time.time() - start_time
        return {"remote": execution_time}

    def _setup_remote_subscriber(self, results_path: str) -> Subscriber:
        """Set up a subscriber for remote evaluation."""
        subscription_ready_event = threading.Event()
        namespace = self.config.remote.environment.get("EVAL_NAMESPACE")
        subscriber = Subscriber(
            self.config.broker,
            namespace,
            set(),
            None,
            subscription_ready_event,
            results_path,
        )
        subscriber.start()
        subscription_ready_event.wait()
        log.info("Remote subscriber is ready.")
        return subscriber

    def _post_process_results(
        self,
        base_results_path: Path,
        model_execution_times: dict[str, float],
        config_path: str,
    ):
        """Post-process evaluation results."""
        # Categorize messages using the refactored categorizer
        log.info("Categorizing messages")
        message_organizer = MessageOrganizer()
        message_organizer.categorize_all_messages(base_results_path)
        log.info("Message categorization finished")

        # Generate summaries
        self.results_processor.summarize_results(base_results_path, self.config)

        # Run evaluation
        log.info("Starting evaluation of results")
        evaluation_orchestrator = EvaluationOrchestrator(config_path)
        evaluation_orchestrator.run_evaluation(
            base_results_path, model_execution_times
        )
        log.info("Evaluation of results finished")

    def _generate_reports(self, config_path: str, base_results_path: Path):
        """Generate evaluation reports."""
        if self.report_generator:
            self.report_generator.generate_report(base_results_path)

    def _display_summary(self, base_results_path: Path):
        """Display a summary of the evaluation results in the terminal."""

        # Pre-process data to find column widths
        summary_data = []
        max_model_len = 0
        max_test_case_len = 0

        for model_dir in sorted(base_results_path.iterdir()):
            if not model_dir.is_dir():
                continue

            results_file = model_dir / "results.json"
            if not results_file.exists():
                continue

            try:
                results_data = self.file_service.load_json(results_file)
                model_name = results_data.get("model_name", model_dir.name)
                max_model_len = max(max_model_len, len(model_name))

                for test_case in results_data.get("test_cases", []):
                    test_case_id = test_case.get("test_case_id")
                    if not test_case_id:
                        continue

                    max_test_case_len = max(max_test_case_len, len(test_case_id))

                    scores = {}
                    tool_match = test_case.get("tool_match_scores", {}).get("average")
                    if tool_match is not None:
                        scores["Tool Match"] = f"{tool_match:.2f}"

                    response_match = test_case.get("response_match_scores", {}).get("average")
                    if response_match is not None:
                        scores["Response Match"] = f"{response_match:.2f}"

                    llm_eval = test_case.get("llm_eval_scores", {}).get("average")
                    if llm_eval is not None:
                        scores["LLM Eval"] = f"{llm_eval:.2f}"

                    if scores:
                        summary_data.append((model_name, test_case_id, scores))

            except Exception as e:
                log.error(f"Error processing results for {model_dir.name}: {e}")

        if not summary_data:
            log.warning("No summary data to display.")
            return

        # Define header line
        header_line = (
            f"{'Model':<{max_model_len}} | {'Test Case':<{max_test_case_len}} | "
            f"{'Tool Match':<12} | {'Response Match':<16} | {'LLM Eval':<10}"
        )
        click.echo(click.style(header_line, fg="white", bold=True))
        click.echo(click.style("-" * len(header_line), fg="white", bold=True))

        for model_name, test_case_id, scores in summary_data:
            tool_score = scores.get("Tool Match", "N/A")
            response_score = scores.get("Response Match", "N/A")
            llm_score = scores.get("LLM Eval", "N/A")

            click.echo(
                click.style(
                    f"{model_name:<{max_model_len}} | {test_case_id:<{max_test_case_len}} | "
                    f"{tool_score:<12} | {response_score:<16} | {llm_score:<10}",
                    fg="white",
                )
            )

    def _get_model_stats(self, model_path: Path) -> dict[str, any]:
        """Process results for a single model and return stats."""
        model_stats = {}
        results_file = model_path / "results.json"
        if not results_file.exists():
            return model_stats

        results_data = self.file_service.load_json(results_file)
        model_name = results_data.get("model_name", model_path.name)
        model_stats[model_name] = {}

        for test_case in results_data.get("test_cases", []):
            test_case_id = test_case.get("test_case_id")
            if not test_case_id:
                continue

            scores = {}
            tool_match = test_case.get("tool_match_scores", {}).get("average")
            if tool_match is not None:
                scores["avg_tool_match"] = tool_match

            response_match = test_case.get("response_match_scores", {}).get("average")
            if response_match is not None:
                scores["avg_response_match"] = response_match

            llm_eval = test_case.get("llm_eval_scores", {}).get("average")
            if llm_eval is not None:
                scores["avg_llm_eval"] = llm_eval

            if scores:
                model_stats[model_name][test_case_id] = scores
        return model_stats

    def _save_execution_stats(self, base_results_path: Path, start_time: float):
        """Save overall execution statistics."""
        end_time = time.time()
        total_execution_time = end_time - start_time
        stats = {"total_execution_time": total_execution_time, "models": {}}

        try:
            for model_path in base_results_path.iterdir():
                if not model_path.is_dir():
                    continue
                model_stats = self._get_model_stats(model_path)
                stats["models"].update(model_stats)

        except Exception as e:
            log.error(f"Error processing results for stats: {e}")

        stats_path = base_results_path / "stats.json"
        self.file_service.save_json(stats, stats_path)

        log.info(f"Overall stats written to {stats_path}")
        log.info(f"Total execution time: {total_execution_time:.2f} seconds")


def main(config_path: str, verbose: bool = False):
    """Main entry point for the evaluation script."""
    if verbose:
        logging.basicConfig(level=logging.INFO)
        log.info("Verbose logging enabled.")

    orchestrator = EvaluationRunner(verbose=verbose)
    orchestrator.run_evaluation(config_path)


if __name__ == "__main__":
    # This allows the script to be run standalone with a config path argument
    import argparse

    parser = argparse.ArgumentParser(description="Run the SAM evaluation suite.")
    parser.add_argument(
        "test_suite_config_path",
        type=str,
        help="Path to the evaluation test_suite_config.json file.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output.",
    )
    args = parser.parse_args()
    main(args.test_suite_config_path, args.verbose)
