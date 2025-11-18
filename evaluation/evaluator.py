"""
Refactored evaluator with improved structure and readability.
This module evaluates AI model performance against test cases using multiple evaluation strategies.
"""

import concurrent.futures
import json
import logging
import re
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import litellm
import numpy as np
from rouge import Rouge

from .shared import (
    EvaluationConfigLoader,
    EvaluationOptions,
    TestSuiteConfiguration,
    load_test_case,
)

log = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """Represents the evaluation result for a single run."""

    run_number: int
    test_case_id: str
    test_case_path: str
    tool_match_score: float | None = None
    response_match_score: float | None = None
    llm_eval_score: float | None = None
    llm_eval_reasoning: str | None = None
    duration_seconds: float | None = None
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, any]:
        """Convert to dictionary format for JSON serialization."""
        result = {
            "run": self.run_number,
            "test_case_id": self.test_case_id,
            "test_case_path": self.test_case_path,
            "duration_seconds": self.duration_seconds,
        }

        if self.tool_match_score is not None:
            result["tool_match"] = self.tool_match_score

        if self.response_match_score is not None:
            result["response_match"] = self.response_match_score

        if self.llm_eval_score is not None:
            result["llm_eval"] = {
                "score": self.llm_eval_score,
                "reasoning": self.llm_eval_reasoning,
            }

        if self.errors:
            result["errors"] = self.errors

        return result


@dataclass
class ScoreStatistics:
    """Statistical summary of evaluation scores."""

    average: float
    distribution: dict[str, float]

    @classmethod
    def from_scores(cls, scores: list[float]) -> "ScoreStatistics":
        """Create statistics from a list of scores."""
        if not scores:
            return cls(
                average=0.0,
                distribution={"min": 0.0, "q1": 0.0, "q2": 0.0, "q3": 0.0, "max": 0.0},
            )

        return cls(
            average=float(np.mean(scores)),
            distribution={
                "min": float(np.min(scores)),
                "q1": float(np.percentile(scores, 25)),
                "q2": float(np.median(scores)),
                "q3": float(np.percentile(scores, 75)),
                "max": float(np.max(scores)),
            },
        )


@dataclass
class TestCaseResults:
    """Aggregated results for a test case across multiple runs."""

    test_case_id: str
    category: str
    runs: list[EvaluationResult]
    average_duration: float
    tool_match_scores: ScoreStatistics
    response_match_scores: ScoreStatistics
    llm_eval_scores: ScoreStatistics

    def to_dict(self) -> dict[str, any]:
        """Convert to dictionary format for JSON serialization."""
        return {
            "test_case_id": self.test_case_id,
            "category": self.category,
            "runs": [run.to_dict() for run in self.runs],
            "average_duration": self.average_duration,
            "tool_match_scores": {
                "average": self.tool_match_scores.average,
                "distribution": self.tool_match_scores.distribution,
            },
            "response_match_scores": {
                "average": self.response_match_scores.average,
                "distribution": self.response_match_scores.distribution,
            },
            "llm_eval_scores": {
                "average": self.llm_eval_scores.average,
                "distribution": self.llm_eval_scores.distribution,
            },
        }


@dataclass
class ModelResults:
    """Complete evaluation results for a model."""

    model_name: str
    total_execution_time: float | None
    test_cases: list[TestCaseResults]

    def to_dict(self) -> dict[str, any]:
        """Convert to dictionary format for JSON serialization."""
        return {
            "model_name": self.model_name,
            "total_execution_time": self.total_execution_time,
            "test_cases": [tc.to_dict() for tc in self.test_cases],
        }


class ConfigurationService:
    """Handles configuration loading and validation."""

    def __init__(self, config_path: str):
        self.config_loader = EvaluationConfigLoader(config_path)
        self._config_cache = None
        self._evaluation_settings_cache = None

    def get_config(self) -> TestSuiteConfiguration:
        """Get the main configuration."""
        if self._config_cache is None:
            self._config_cache = self.config_loader.load_configuration()
        return self._config_cache

    def get_evaluation_settings(self) -> EvaluationOptions:
        """Get evaluation settings."""
        if self._evaluation_settings_cache is None:
            self._evaluation_settings_cache = self.config_loader.get_evaluation_options()
        return self._evaluation_settings_cache


class FileService:
    """Handles file I/O operations."""

    @staticmethod
    def load_json(filepath: Path) -> any:
        """Load JSON data from file."""
        try:
            with filepath.open() as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            log.error(f"Failed to load JSON from {filepath}: {e}")
            raise

    @staticmethod
    def save_json(data: any, filepath: Path):
        """Save data as JSON to file."""
        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with filepath.open("w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            log.error(f"Failed to save JSON to {filepath}: {e}")
            raise

    @staticmethod
    def file_exists(filepath: Path) -> bool:
        """Check if file exists."""
        return filepath.exists()


class StatisticsService:
    """Handles statistical calculations and aggregations."""

    @staticmethod
    def calculate_score_statistics(scores: list[float]) -> ScoreStatistics:
        """Calculate statistical summary for a list of scores."""
        return ScoreStatistics.from_scores(scores)

    @staticmethod
    def calculate_average_duration(durations: list[float]) -> float:
        """Calculate average duration from a list of durations."""
        if not durations:
            return 0.0
        return float(np.mean(durations))


class EvaluationStrategy(ABC):
    """Abstract base class for evaluation strategies."""

    @abstractmethod
    def evaluate(
        self, test_case: dict[str, any], summary_data: dict[str, any]
    ) -> float | None:
        """Evaluate a test case run and return a score."""
        pass


class ToolMatchEvaluator(EvaluationStrategy):
    """Evaluates tool usage against expected tools."""

    def evaluate(
        self, test_case: dict[str, any], summary_data: dict[str, any]
    ) -> float | None:
        """Evaluate tool matching score."""
        try:
            expected_tools = test_case["evaluation"]["expected_tools"]
            actual_tools = [
                tool["tool_name"] for tool in summary_data.get("tool_calls", [])
            ]

            expected_set = set(expected_tools)
            actual_set = set(actual_tools)

            if not expected_set:
                return 1.0

            found_tools = expected_set.intersection(actual_set)
            return len(found_tools) / len(expected_set)

        except (KeyError, TypeError) as e:
            log.warning(f"Error in tool match evaluation: {e}")
            return None


class ResponseMatchEvaluator(EvaluationStrategy):
    """Evaluates response quality using ROUGE metrics."""

    def __init__(self):
        self.rouge = Rouge()

    def evaluate(
        self, test_case: dict[str, any], summary_data: dict[str, any]
    ) -> float | None:
        """Evaluate response matching score using a weighted ROUGE average."""
        try:
            expected_response = test_case["evaluation"]["expected_response"]
            actual_response = summary_data.get("final_message", "")

            if not actual_response or not expected_response:
                return 0.0

            scores = self.rouge.get_scores(actual_response, expected_response)[0]

            # Weighted average of ROUGE-1, ROUGE-2, and ROUGE-L f-scores
            rouge_1_f = scores.get("rouge-1", {}).get("f", 0.0)
            rouge_2_f = scores.get("rouge-2", {}).get("f", 0.0)
            rouge_l_f = scores.get("rouge-l", {}).get("f", 0.0)

            weighted_score = (0.2 * rouge_1_f) + (0.3 * rouge_2_f) + (0.5 * rouge_l_f)

            return weighted_score

        except (ValueError, KeyError, TypeError) as e:
            log.warning(f"Error in response match evaluation: {e}")
            return 0.0


class LLMEvaluator(EvaluationStrategy):
    """Evaluates responses using an LLM judge."""

    def __init__(self, llm_config: dict[str, any]):
        self.model = llm_config.get("LLM_SERVICE_PLANNING_MODEL_NAME")
        self.api_key = llm_config.get("LLM_SERVICE_API_KEY")
        self.api_base = llm_config.get("LLM_SERVICE_ENDPOINT")

        if not all([self.model, self.api_key, self.api_base]):
            raise ValueError(
                "LLM evaluator requires model, api_key, and api_base configuration"
            )

    def evaluate(
        self, test_case: dict[str, any], summary_data: dict[str, any]
    ) -> dict[str, any] | None:
        """Evaluate response using LLM and return score with reasoning."""
        try:
            query = test_case["query"]
            expected_response = test_case["evaluation"]["expected_response"]
            actual_response = summary_data.get("final_message", "")
            criterion = test_case["evaluation"]["criterion"]
            input_artifacts = summary_data.get("input_artifacts", [])
            output_artifacts = summary_data.get("output_artifacts", [])

            prompt = self._build_evaluation_prompt(
                query,
                expected_response,
                actual_response,
                criterion,
                input_artifacts,
                output_artifacts,
            )

            response = litellm.completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                api_key=self.api_key,
                base_url=self.api_base,
            )

            response_content = response.choices[0].message.content.strip()
            score = self._extract_score(response_content)
            reasoning = self._extract_reasoning(response_content)

            return {"score": score, "reasoning": reasoning}

        except Exception as e:
            log.error(f"Error in LLM evaluation: {e}")
            return None

    def _build_evaluation_prompt(
        self,
        query: str,
        expected_response: str,
        actual_response: str,
        criterion: str,
        input_artifacts: list[dict],
        output_artifacts: list[dict],
    ) -> str:
        """Build the evaluation prompt for the LLM."""
        return f"""
        Original Query: {query}
        Expected Response: {expected_response}
        Actual Response: {actual_response}
        Criterion: {criterion}
        Input Artifacts: {input_artifacts}
        Output Artifacts: {output_artifacts}

        Based on the criterion, please evaluate the actual response.
        Format your response exactly as:
        Score: [0.0-1.0]
        Reasoning: [Your detailed explanation of why you gave this score, considering both the response and any artifacts created]

        Provide a score from 0.0 to 1.0 where:
        - 1.0 = Excellent: Fully meets the criterion and expectations
        - 0.8-0.9 = Good: Mostly meets the criterion with minor issues
        - 0.6-0.7 = Adequate: Partially meets the criterion but has notable gaps
        - 0.4-0.5 = Poor: Minimally meets the criterion with significant issues
        - 0.0-0.3 = Very Poor: Fails to meet the criterion
        """

    def _extract_score(self, llm_response: str) -> float:
        """Extract numerical score from LLM response."""
        # Try to find "Score: X.X" pattern first
        score_match = re.search(
            r"Score:\s*([0-9]*\.?[0-9]+)", llm_response, re.IGNORECASE
        )
        if score_match:
            try:
                score = float(score_match.group(1))
                return max(0.0, min(1.0, score))
            except ValueError:
                pass

        # Fallback: look for any number between 0 and 1
        number_match = re.search(r"\b([0-1]\.?[0-9]*)\b", llm_response)
        if number_match:
            try:
                score = float(number_match.group(1))
                if 0.0 <= score <= 1.0:
                    return score
            except ValueError:
                pass

        return 0.0

    def _extract_reasoning(self, llm_response: str) -> str:
        """Extract reasoning from LLM response."""
        reasoning_match = re.search(
            r"Reasoning:\s*(.+)", llm_response, re.IGNORECASE | re.DOTALL
        )
        if reasoning_match:
            return reasoning_match.group(1).strip()

        return llm_response.strip()


class RunEvaluator:
    """Evaluates individual test runs."""

    def __init__(self, evaluation_settings: dict[str, any]):
        self.evaluation_settings = evaluation_settings
        self.file_service = FileService()

        # Initialize evaluators based on settings
        self.tool_evaluator = (
            ToolMatchEvaluator()
            if evaluation_settings["tool_match"]["enabled"]
            else None
        )
        self.response_evaluator = (
            ResponseMatchEvaluator()
            if evaluation_settings["response_match"]["enabled"]
            else None
        )

        self.llm_evaluator = None
        if evaluation_settings["llm_evaluator"]["enabled"]:
            try:
                llm_config = evaluation_settings["llm_evaluator"]["env"]
                self.llm_evaluator = LLMEvaluator(llm_config)
            except Exception as e:
                log.error(f"Failed to initialize LLM evaluator: {e}")

    def evaluate_run(
        self,
        run_number: int,
        run_path: Path,
        test_case: dict[str, any],
        test_case_path: str,
    ) -> EvaluationResult | None:
        """Evaluate a single test run."""
        log.info(
            f"    - Evaluating run {run_number} for test case {test_case['test_case_id']}"
        )

        # Load summary data
        summary_path = run_path / "summary.json"
        log.info(f"Summary file path: {summary_path}")
        if not self.file_service.file_exists(summary_path):
            log.warning(
                f"      Summary file not found for run {run_number}, skipping."
            )
            return None

        try:
            summary_data = self.file_service.load_json(summary_path)
        except Exception as e:
            log.error(f"      Error loading summary.json for run {run_number}: {e}")
            return None

        # Create evaluation result
        result = EvaluationResult(
            run_number=run_number,
            test_case_id=test_case["test_case_id"],
            test_case_path=test_case_path,
            duration_seconds=summary_data.get("duration_seconds"),
        )

        # Run evaluations
        if self.tool_evaluator:
            result.tool_match_score = self.tool_evaluator.evaluate(
                test_case, summary_data
            )

        if self.response_evaluator:
            result.response_match_score = self.response_evaluator.evaluate(
                test_case, summary_data
            )

        if self.llm_evaluator:
            llm_result = self.llm_evaluator.evaluate(test_case, summary_data)
            if llm_result:
                result.llm_eval_score = llm_result["score"]
                result.llm_eval_reasoning = llm_result["reasoning"]

        return result


class ModelEvaluator:
    """Evaluates all runs for a single model."""

    def __init__(self, config: dict[str, any], evaluation_settings: dict[str, any]):
        self.config = config
        self.evaluation_settings = evaluation_settings
        self.run_evaluator = RunEvaluator(evaluation_settings)
        self.statistics_service = StatisticsService()

    def evaluate_model(self, model_name: str, base_results_path: str) -> ModelResults:
        """Evaluate all test cases for a model."""
        log.info(f"Evaluating model: {model_name}")

        model_results_path = Path(base_results_path) / model_name

        # Collect all evaluation tasks
        tasks = self._collect_evaluation_tasks(model_results_path)

        # Run evaluations in parallel
        model_results_data = defaultdict(list)
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_run = {
                executor.submit(self.run_evaluator.evaluate_run, *task): task
                for task in tasks
            }

            for future in concurrent.futures.as_completed(future_to_run):
                try:
                    result = future.result()
                    if result:
                        model_results_data[result.test_case_id].append(result)
                except Exception as e:
                    log.error(f"An error occurred during evaluation: {e}")

        # Aggregate results by test case
        test_case_results = []
        for test_case_id, runs in model_results_data.items():
            if runs:
                test_case_result = self._aggregate_test_case_results(test_case_id, runs)
                test_case_results.append(test_case_result)

        return ModelResults(
            model_name=model_name,
            total_execution_time=None,  # Will be set by orchestrator
            test_cases=test_case_results,
        )

    def _collect_evaluation_tasks(
        self, model_results_path: Path
    ) -> list[tuple[int, Path, dict[str, any], str]]:
        """Collect all evaluation tasks for the model."""
        tasks = []

        for test_case_path in self.config["test_cases"]:
            test_case = load_test_case(test_case_path)
            test_case_name = Path(test_case_path).stem.replace(".test", "")
            test_case_results_path = model_results_path / test_case_name

            for i in range(1, self.config["runs"] + 1):
                run_path = test_case_results_path / f"run_{i}"
                tasks.append((i, run_path, test_case, test_case_path))

        return tasks

    def _aggregate_test_case_results(
        self, test_case_id: str, runs: list[EvaluationResult]
    ) -> TestCaseResults:
        """Aggregate results for a test case across multiple runs."""
        # Load test case to get category
        test_case_path = runs[0].test_case_path
        test_case = load_test_case(test_case_path)

        # Extract scores for statistics
        tool_scores = [
            r.tool_match_score for r in runs if r.tool_match_score is not None
        ]
        response_scores = [
            r.response_match_score for r in runs if r.response_match_score is not None
        ]
        llm_scores = [r.llm_eval_score for r in runs if r.llm_eval_score is not None]
        duration_scores = [
            r.duration_seconds for r in runs if r.duration_seconds is not None
        ]

        return TestCaseResults(
            test_case_id=test_case_id,
            category=test_case["category"],
            runs=runs,
            average_duration=self.statistics_service.calculate_average_duration(
                duration_scores
            ),
            tool_match_scores=self.statistics_service.calculate_score_statistics(
                tool_scores
            ),
            response_match_scores=self.statistics_service.calculate_score_statistics(
                response_scores
            ),
            llm_eval_scores=self.statistics_service.calculate_score_statistics(
                llm_scores
            ),
        )


class ResultsWriter:
    """Handles writing evaluation results to files."""

    def __init__(self):
        self.file_service = FileService()

    def write_model_results(self, model_results: ModelResults, base_results_path: str):
        """Write model results to file."""
        results_path = (
            Path(base_results_path) / model_results.model_name / "results.json"
        )
        self.file_service.save_json(model_results.to_dict(), results_path)
        log.info(
            f"Results for model {model_results.model_name} written to {results_path}"
        )


class EvaluationOrchestrator:
    """Main orchestrator that coordinates the entire evaluation process."""

    def __init__(self, config_path: str):
        self.config_service = ConfigurationService(config_path)
        self.results_writer = ResultsWriter()

    def run_evaluation(
        self,
        base_results_path: str,
        model_execution_times: dict[str, float] | None = None,
    ):
        """Main entry point for the evaluation process."""
        log.info("Starting evaluation")

        # Resolve to an absolute path to ensure consistency
        base_results_path = str(Path(base_results_path).resolve())

        if model_execution_times is None:
            model_execution_times = {}

        config = self.config_service.get_config()
        evaluation_settings = self.config_service.get_evaluation_settings()

        # Convert evaluation settings to dict format for backwards compatibility
        settings_dict = {
            "tool_match": {"enabled": evaluation_settings.tool_matching_enabled},
            "response_match": {"enabled": evaluation_settings.response_matching_enabled},
            "llm_evaluator": {
                "enabled": evaluation_settings.llm_evaluation_enabled,
                "env": evaluation_settings.llm_evaluator_environment.variables if evaluation_settings.llm_evaluator_environment else {}
            }
        }

        # Convert config to dict format for backwards compatibility
        config_dict = {
            "test_cases": config.test_case_files,
            "runs": config.run_count
        }

        model_evaluator = ModelEvaluator(config_dict, settings_dict)

        if config.remote:
            # Handle remote evaluation
            model_name = "remote"
            model_results = model_evaluator.evaluate_model(model_name, base_results_path)
            execution_time = model_execution_times.get(model_name)
            if execution_time is not None:
                model_results.total_execution_time = execution_time
            self.results_writer.write_model_results(model_results, base_results_path)
        else:
            # Handle local evaluation
            for model_config in config.model_configurations:
                model_name = model_config.name

                # Evaluate the model
                model_results = model_evaluator.evaluate_model(
                    model_name, base_results_path
                )

                # Add execution time if available
                execution_time = model_execution_times.get(model_name)
                if execution_time is not None:
                    model_results.total_execution_time = execution_time

                # Write results to file
                self.results_writer.write_model_results(model_results, base_results_path)

        log.info("--- Evaluation finished ---")


def main(config_path: str):
    """Main entry point for command-line usage."""
    orchestrator = EvaluationOrchestrator(config_path)
    # Results path should be based on the current working directory, not the package location.
    # This main function is for standalone testing.
    config = orchestrator.config_service.get_config()
    results_path = Path.cwd() / "results" / config.results_directory
    results_path.mkdir(parents=True, exist_ok=True)
    orchestrator.run_evaluation(str(results_path))


if __name__ == "__main__":
    # This will be updated later to parse CLI args.
    main()
