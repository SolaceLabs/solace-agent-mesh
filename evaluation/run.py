"""
Refactored evaluation runner with improved structure and readability.
This module orchestrates the evaluation of AI models against test cases.
"""

import json
import os
import sys
import time
import subprocess
import requests
import uuid
import shutil
import mimetypes
import threading
from pathlib import Path

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from dotenv import load_dotenv
from .config_loader import ConfigLoader
from .message_organizer import MessageOrganizer
from .summary_builder import SummaryBuilder
from .subscriber import Subscriber
from .evaluator import EvaluationOrchestrator
from .report_generator import ReportGenerator

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


@dataclass
class EvaluationConfig:
    """Centralized configuration with validation and defaults."""

    # Constants
    DEFAULT_STARTUP_WAIT_TIME = 60
    DEFAULT_TEST_TIMEOUT = 60

    def __init__(self, config_data: Dict[str, Any]):
        load_dotenv()
        host = os.getenv("REST_API_HOST", "0.0.0.0")
        port = os.getenv("REST_API_PORT", "8080")
        self.API_BASE_URL = f"http://{host}:{port}/api/v2"
        self.config_data = config_data
        self.agents = config_data.get("agents", [])
        self.test_cases = config_data.get("test_cases", [])
        self.llm_models = config_data.get("llm_models", [])
        self.runs = config_data.get("runs", 1)
        self.results_dir_name = config_data.get("results_dir_name", "tests")

        self._validate_config()

    def _validate_config(self):
        """Validate required configuration fields."""
        if not self.agents:
            raise ValueError("'agents' configuration is required and cannot be empty")
        if not self.test_cases:
            raise ValueError(
                "'test_cases' configuration is required and cannot be empty"
            )
        if not self.llm_models:
            raise ValueError(
                "'llm_models' configuration is required and cannot be empty"
            )


@dataclass
class TestRun:
    """Represents a single test execution with all necessary parameters."""

    agent: str
    query: str
    artifacts: List[str]
    wait_time: int
    test_case_file: str
    run_num: int

    @property
    def test_case_id(self) -> str:
        """Extract test case ID from filename."""
        base_name = os.path.basename(self.test_case_file)
        return os.path.splitext(base_name)[0].replace(".test", "")


class ProcessManager:
    """Manages subprocess lifecycle for the Solace AI Connector."""

    def __init__(self, config: EvaluationConfig, verbose: bool = False):
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self.namespace: Optional[str] = None
        self.verbose = verbose

    def start_services(self) -> Tuple[subprocess.Popen, str]:
        """Start the Solace AI Connector and return process and namespace."""
        load_dotenv()
        self.namespace = f"eval-{uuid.uuid4()}"
        os.environ["NAMESPACE"] = self.namespace

        agent_files = self.config.agents

        command = [sys.executable, "-m", "solace_ai_connector.main", *agent_files]

        print("Starting Solace AI Connector as a subprocess...")
        project_root = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))

        self.process = subprocess.Popen(
            command, stdout=sys.stdout, stderr=sys.stderr, cwd=project_root
        )

        print("Waiting for server to become healthy...")
        self._wait_for_server_ready()

        return self.process, self.namespace

    def _wait_for_server_ready(self):
        """Poll the health endpoint until the server is ready."""
        start_time = time.time()
        health_url = f"{self.config.API_BASE_URL.replace('/api/v2', '')}/health"

        while time.time() - start_time < self.config.DEFAULT_STARTUP_WAIT_TIME:
            try:
                response = requests.get(health_url)
                if response.status_code == 200:
                    print("Server is healthy.")
                    time.sleep(1)  # Wait an extra second as requested
                    return
            except requests.ConnectionError:
                # Server is not yet available, wait and retry
                time.sleep(1)
            except Exception as e:
                print(f"An unexpected error occurred during health check: {e}")
                time.sleep(1)

        raise RuntimeError(
            f"Server did not become healthy within {self.config.DEFAULT_STARTUP_WAIT_TIME} seconds."
        )

    def stop_services(self, subscriber: Optional[Subscriber] = None):
        """Clean up running processes."""
        if subscriber:
            print("--- Terminating subscriber ---")
            subscriber.stop()
            subscriber.join()
            print("Subscriber terminated.")

        if self.process:
            print("--- Terminating subprocess ---")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
                print("Subprocess terminated.")
            except subprocess.TimeoutExpired:
                print("Subprocess did not terminate gracefully, killing.")
                self.process.kill()

        print("Process cleanup completed.")


class TaskService:
    """Handles task submission and tracking."""

    def __init__(self, config: EvaluationConfig, verbose: bool = False):
        self.config = config
        self.base_url = config.API_BASE_URL
        self.verbose = verbose

    def submit_task(
        self, agent_name: str, message: str, artifact_paths: Optional[List[str]] = None
    ) -> Optional[str]:
        """Submit a test case to the agent and return the task ID."""
        print("--- Sending test request ---")
        url = f"{self.base_url}/tasks"
        data = {
            "agent_name": agent_name,
            "prompt": message,
        }

        files_to_upload = []
        if artifact_paths:
            files_to_upload = self._prepare_file_uploads(artifact_paths)

        try:
            with requests.Session() as session:
                response = session.post(url, data=data, files=files_to_upload)

            response.raise_for_status()
            task_id = response.json()["taskId"]
            print(f"Task submitted with ID: {task_id}")
            return task_id

        except requests.RequestException as e:
            print(f"Failed to submit task: {e}")
            return None
        finally:
            self._close_file_uploads(files_to_upload)

    def _prepare_file_uploads(self, artifact_paths: List[str]) -> List[Tuple]:
        """Prepare file uploads for the request."""
        files_to_upload = []
        for path in artifact_paths:
            mimetype, _ = mimetypes.guess_type(path)
            if mimetype is None:
                mimetype = "text/plain"
            files_to_upload.append(
                ("files", (os.path.basename(path), open(path, "rb"), mimetype))
            )
        return files_to_upload

    def _close_file_uploads(self, files_to_upload: List[Tuple]):
        """Close file handles after upload."""
        for _, file_tuple in files_to_upload:
            file_tuple[1].close()


class FileService:
    """Handles file operations and path management."""

    @staticmethod
    def ensure_directory(path: str):
        """Ensure directory exists, create if necessary."""
        os.makedirs(path, exist_ok=True)

    @staticmethod
    def remove_directory(path: str):
        """Remove directory and all contents."""
        if os.path.exists(path):
            shutil.rmtree(path)

    @staticmethod
    def save_json(data: Any, filepath: str):
        """Save data as JSON to file."""
        with open(filepath, "w") as f:
            json.dump(data, f, indent=4)

    @staticmethod
    def load_json(filepath: str) -> Any:
        """Load JSON data from file."""
        with open(filepath, "r") as f:
            return json.load(f)


class TestRunBuilder:
    """Builds test run configurations from test cases."""

    def __init__(self, config: EvaluationConfig):
        self.config = config

    def build_test_runs(self) -> List[TestRun]:
        """Build all test runs from configuration."""
        test_runs = []

        for test_case_path in self.config.test_cases:
            test_case = FileService.load_json(test_case_path)

            artifact_paths = self._get_artifact_paths(test_case, test_case_path)

            test_case_file = os.path.basename(test_case_path)
            for run_num in range(1, self.config.runs + 1):
                test_run = TestRun(
                    agent=test_case["target_agent"],
                    query=test_case["query"],
                    artifacts=artifact_paths,
                    wait_time=test_case.get(
                        "wait_time", self.config.DEFAULT_TEST_TIMEOUT
                    ),
                    test_case_file=test_case_path,
                    run_num=run_num,
                )
                test_runs.append(test_run)

        return test_runs

    def _get_artifact_paths(self, test_case: Dict, test_case_path: str) -> List[str]:
        """Extract artifact paths from test case."""
        artifact_paths = []
        if "artifacts" in test_case:
            test_case_dir = os.path.dirname(test_case_path)
            for artifact in test_case["artifacts"]:
                if artifact.get("type") == "file":
                    artifact_paths.append(os.path.join(test_case_dir, artifact["path"]))
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
        model_results_path: str,
        task_mappings: Dict[str, str],
        subscriber: Subscriber,
    ) -> bool:
        """Execute a single test case and wait for completion."""
        print(
            f"--- Starting test: {test_run.test_case_file} (run {test_run.run_num}) ---"
        )

        # Submit the task
        task_id = self.task_service.submit_task(
            test_run.agent, test_run.query, test_run.artifacts
        )

        if not task_id:
            print(
                f"Failed to start test case: {test_run.test_case_file} (run {test_run.run_num})"
            )
            return False

        # Set up result directory
        run_dir = os.path.join(
            model_results_path, test_run.test_case_id, f"run_{test_run.run_num}"
        )
        self.file_service.ensure_directory(run_dir)

        # Save test case path for summary builder
        test_info = {"path": test_run.test_case_file}
        self.file_service.save_json(
            test_info, os.path.join(run_dir, "test_case_info.json")
        )

        # Track the task
        task_mappings[task_id] = run_dir
        subscriber.active_tasks.add(task_id)

        # Wait for completion
        return self._wait_for_completion(task_id, test_run.wait_time, subscriber)

    def _wait_for_completion(
        self, task_id: str, wait_time: int, subscriber: Subscriber
    ) -> bool:
        """Wait for task completion with timeout."""
        print(
            f"Waiting for task {task_id} to complete (timeout: {wait_time} seconds)..."
        )

        start_time = time.time()
        while task_id in subscriber.active_tasks:
            if time.time() - start_time > wait_time:
                print(f"Task {task_id} timed out after {wait_time} seconds")
                subscriber.active_tasks.discard(task_id)
                return False
            time.sleep(1)

        print(f"Task {task_id} completed successfully")
        return True


class ModelEvaluator:
    """Handles the evaluation of a single model."""

    def __init__(self, config: EvaluationConfig, verbose: bool = False):
        self.config = config
        self.process_manager = ProcessManager(config, verbose=verbose)
        self.task_service = TaskService(config, verbose=verbose)
        self.file_service = FileService()
        self.test_builder = TestRunBuilder(config)
        self.test_executor = TestExecutor(self.task_service, self.file_service, verbose=verbose)
        self.verbose = verbose

    def evaluate_model(
        self, model_config: Dict[str, Any], base_results_path: str
    ) -> float:
        """Evaluate a single model and return execution time."""
        model_name = model_config["name"]
        print(f"--- Starting evaluation for model: {model_name} ---")
        start_time = time.time()

        # Set environment variables for the model
        self._set_model_environment(model_config)

        # Set up paths
        model_results_path = os.path.join(base_results_path, model_name)
        self.file_service.ensure_directory(model_results_path)

        # Start services
        app_process, namespace = self.process_manager.start_services()

        # Set up subscriber
        subscriber = self._setup_subscriber(namespace, model_results_path)

        try:
            # Execute tests
            successful_tests = self._execute_all_tests(model_results_path, subscriber)
            print(f"--- Completed {successful_tests} tests successfully ---")

        except Exception as e:
            print(f"Error during test case execution for model {model_name}: {e}")
        finally:
            # Cleanup
            task_mappings = getattr(self, "_task_mappings", {})
            self._cleanup_model_evaluation(
                app_process, subscriber, model_results_path, task_mappings
            )

        end_time = time.time()
        execution_time = end_time - start_time
        print(
            f"--- Evaluation for model: {model_name} complete in {execution_time:.2f} seconds ---"
        )

        return execution_time

    def _set_model_environment(self, model_config: Dict[str, Any]):
        """Set environment variables for the model."""
        for key, value in model_config.get("env", {}).items():
            os.environ[key] = value

    def _setup_subscriber(self, namespace: str, model_results_path: str) -> Subscriber:
        """Set up and start the subscriber."""
        subscription_ready_event = threading.Event()
        subscriber = Subscriber(
            namespace, set(), None, subscription_ready_event, model_results_path
        )
        subscriber.start()

        print("Waiting for subscriber to be ready...")
        subscription_ready_event.wait()
        print("Subscriber is ready.")

        return subscriber

    def _execute_all_tests(
        self, model_results_path: str, subscriber: Subscriber
    ) -> int:
        """Execute all test cases and return count of successful tests."""
        test_runs = self.test_builder.build_test_runs()

        self._task_mappings = {}
        total_tests = len(test_runs)
        successful_tests = 0

        print(f"--- Starting sequential execution of {total_tests} tests ---")

        for i, test_run in enumerate(test_runs, 1):
            print(f"--- Test {i}/{total_tests} ---")
            success = self.test_executor.execute_test(
                test_run, model_results_path, self._task_mappings, subscriber
            )
            if success:
                successful_tests += 1
            else:
                print(f"Test {i} failed or timed out")

        return successful_tests

    def _cleanup_model_evaluation(
        self,
        app_process: subprocess.Popen,
        subscriber: Subscriber,
        model_results_path: str,
        task_mappings: Dict[str, str],
    ):
        """Clean up after model evaluation."""
        self.process_manager.stop_services(subscriber)

        # Save task mappings
        mappings_file = os.path.join(model_results_path, "task_mappings.json")
        self.file_service.save_json(task_mappings, mappings_file)
        print(f"Task mappings saved to {mappings_file}")


class ResultsProcessor:
    """Handles post-processing of evaluation results."""

    def __init__(self, file_service: FileService, verbose: bool = False):
        self.file_service = file_service
        self.summary_builder = SummaryBuilder()
        self.verbose = verbose

    def summarize_results(self, base_results_path: str):
        """Generate summaries for all test results."""
        print("--- Summarizing results ---")

        for model_name in os.listdir(base_results_path):
            model_path = os.path.join(base_results_path, model_name)
            if not os.path.isdir(model_path):
                continue

            self._process_model_results(model_path)

    def _process_model_results(self, model_path: str):
        """Process results for a single model."""
        for test_case_name in os.listdir(model_path):
            test_case_path = os.path.join(model_path, test_case_name)
            if not os.path.isdir(test_case_path):
                continue

            self._process_test_case_results(test_case_path)

    def _process_test_case_results(self, test_case_path: str):
        """Process results for a single test case."""
        for run_name in os.listdir(test_case_path):
            run_path = os.path.join(test_case_path, run_name)
            if not os.path.isdir(run_path):
                continue

            messages_file = os.path.join(run_path, "messages.json")
            if os.path.exists(messages_file):
                summary_data = self.summary_builder.summarize_run(messages_file)
                summary_file = os.path.join(run_path, "summary.json")
                self.file_service.save_json(summary_data, summary_file)
                print(f"Summary created for {run_path}")


class EvaluationRunner:
    """Main orchestrator that coordinates the entire evaluation process."""

    def __init__(self, verbose: bool = False):
        self.config: Optional[EvaluationConfig] = None
        self.file_service = FileService()
        self.results_processor = ResultsProcessor(self.file_service, verbose=verbose)
        self.report_generator: Optional[ReportGenerator] = None
        self.verbose = verbose

    def run_evaluation(self, config_path: str):
        """Main entry point for the evaluation process."""
        start_time = time.time()

        try:
            # Load and validate configuration
            self._load_configuration(config_path)

            # Set up results directory in the current working directory
            base_results_path = Path.cwd() / "results" / self.config.results_dir_name
            self._setup_results_directory(base_results_path)

            # Run model evaluations
            model_execution_times = self._evaluate_all_models(str(base_results_path))

            # Post-process results
            self._post_process_results(
                str(base_results_path), model_execution_times, config_path
            )

            # Save overall statistics
            self._save_execution_stats(str(base_results_path), start_time)

            # Generate reports
            self._generate_reports(config_path, base_results_path)

            # Display verbose summary if enabled
            if self.verbose:
                self._display_verbose_summary(base_results_path)

        except Exception as e:
            print(f"Evaluation failed: {e}")
            raise

    def _load_configuration(self, config_path: str):
        """Load and validate the evaluation configuration."""
        config_loader = ConfigLoader(config_path)
        config_data = config_loader.load_config()
        self.config = EvaluationConfig(config_data)
        self.report_generator = ReportGenerator(config_path)
        print("Configuration loaded and validated successfully.")

    def _setup_results_directory(self, base_results_path: Path):
        """Set up the results directory."""
        # Clean up existing results
        self.file_service.remove_directory(str(base_results_path))
        self.file_service.ensure_directory(str(base_results_path))

        print(f"Results directory set up at: {base_results_path}")

    def _evaluate_all_models(self, base_results_path: str) -> Dict[str, float]:
        """Evaluate all configured models."""
        model_execution_times = {}

        for model_config in self.config.llm_models:
            model_evaluator = ModelEvaluator(self.config, verbose=self.verbose)
            execution_time = model_evaluator.evaluate_model(
                model_config, base_results_path
            )
            model_execution_times[model_config["name"]] = execution_time

        return model_execution_times

    def _post_process_results(
        self,
        base_results_path: str,
        model_execution_times: Dict[str, float],
        config_path: str,
    ):
        """Post-process evaluation results."""
        # Categorize messages using the refactored categorizer
        print("--- Categorizing messages ---")
        message_organizer = MessageOrganizer()
        categorization_results = message_organizer.categorize_all_messages(
            base_results_path
        )
        print("--- Message categorization finished ---")

        # Generate summaries
        self.results_processor.summarize_results(base_results_path)

        # Run evaluation
        print("--- Starting evaluation of results ---")
        evaluation_orchestrator = EvaluationOrchestrator(config_path)
        evaluation_orchestrator.run_evaluation(base_results_path, model_execution_times)
        print("--- Evaluation of results finished ---")

    def _generate_reports(self, config_path: str, base_results_path: Path):
        """Generate evaluation reports."""
        if self.report_generator:
            self.report_generator.generate_report(base_results_path)

    def _display_verbose_summary(self, base_results_path: Path):
        """Display a verbose summary of the evaluation results in the terminal."""

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
                results_data = self.file_service.load_json(str(results_file))
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
                print(f"Error processing results for {model_dir.name}: {e}")

        # Print formatted output
        if not summary_data:
            print("No summary data to display.")
            return

        # Define headers and find max score lengths
        headers = ["Tool Match", "Response Match", "LLM Eval"]

        # Print header
        header_line = (
            f"{'Model':<{max_model_len}} | {'Test Case':<{max_test_case_len}} | "
            f"{'Tool Match':<12} | {'Response Match':<16} | {'LLM Eval':<10}"
        )
        print(header_line)
        print("-" * len(header_line))

        # Print data rows
        for model_name, test_case_id, scores in summary_data:
            tool_score = scores.get("Tool Match", "N/A")
            response_score = scores.get("Response Match", "N/A")
            llm_score = scores.get("LLM Eval", "N/A")

            print(
                f"{model_name:<{max_model_len}} | {test_case_id:<{max_test_case_len}} | "
                f"{tool_score:<12} | {response_score:<16} | {llm_score:<10}"
            )

    def _get_model_stats(self, model_path: str) -> Dict[str, Any]:
        """Process results for a single model and return stats."""
        model_stats = {}
        results_file = os.path.join(model_path, "results.json")
        if not os.path.exists(results_file):
            return model_stats

        results_data = self.file_service.load_json(results_file)
        model_name = results_data.get("model_name", os.path.basename(model_path))
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

    def _save_execution_stats(self, base_results_path: str, start_time: float):
        """Save overall execution statistics."""
        end_time = time.time()
        total_execution_time = end_time - start_time
        stats = {"total_execution_time": total_execution_time, "models": {}}

        try:
            for model_dir in os.listdir(base_results_path):
                model_path = os.path.join(base_results_path, model_dir)
                if not os.path.isdir(model_path):
                    continue
                model_stats = self._get_model_stats(model_path)
                stats["models"].update(model_stats)

        except Exception as e:
            print(f"Error processing results for stats: {e}")

        stats_path = os.path.join(base_results_path, "stats.json")
        self.file_service.save_json(stats, stats_path)

        print(f"Overall stats written to {stats_path}")
        print(f"Total execution time: {total_execution_time:.2f} seconds")


def main(config_path: str, verbose: bool = False):
    """Main entry point for the evaluation script."""
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
