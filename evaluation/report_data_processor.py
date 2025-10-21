"""
Refactored report data processor with improved structure and readability.
This module extracts and processes evaluation data for HTML report generation.
"""

import json
import logging
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .shared import load_test_case

log = logging.getLogger(__name__)


@dataclass
class EvaluationMetrics:
    """Core evaluation data structure."""

    models: list[str] = field(default_factory=list)
    total_execution_time: float | None = None
    total_execution_time_formatted: str = "Not available"
    generation_time: str = field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    timestamp: str = field(
        default_factory=lambda: datetime.now().strftime("%B %d, %Y at %I:%M %p")
    )
    runs: str = "Not available"
    total_tests: int = 0
    duration: str = "Not available"
    test_case_names: list[str] = field(default_factory=list)


@dataclass
class ModelPerformance:
    """Individual model performance data."""

    model_name: str
    average_score: float = 0.0
    success_rate: float = 0.0
    test_count: int = 0
    estimated_cost: float = 0.0
    scores: list[float] = field(default_factory=list)


@dataclass
class TestCaseResult:
    """Test case specific results."""

    test_case_id: str
    category: str
    description: str = ""
    model_results: dict[str, any] = field(default_factory=dict)
    average_score: float = 0.0


@dataclass
class ChartConfiguration:
    """Chart and visualization data."""

    categories: list[str] = field(default_factory=list)
    datasets: list[dict[str, any]] = field(default_factory=list)
    category_scores: dict[str, dict[str, float]] = field(default_factory=dict)


@dataclass
class CategoryStatistics:
    """Category-based statistics."""

    category_name: str
    test_cases: list[str] = field(default_factory=list)
    model_scores: dict[str, float] = field(default_factory=dict)


class FileService:
    """Handles file I/O operations with proper error handling."""

    @staticmethod
    def load_json(filepath: Path) -> any:
        """Load JSON data from file."""
        try:
            with open(filepath) as f:
                return json.load(f)
        except FileNotFoundError:
            log.warning(f"File not found: {filepath}")
            return None
        except json.JSONDecodeError as e:
            log.error(f"Invalid JSON in file {filepath}: {e}")
            return None
        except Exception as e:
            log.error(f"Error reading file {filepath}: {e}")
            return None

    @staticmethod
    def file_exists(filepath: Path) -> bool:
        """Check if file exists."""
        return filepath.exists() and filepath.is_file()

    @staticmethod
    def list_directories(path: Path) -> list[str]:
        """List directories in the given path."""
        try:
            return [
                item.name
                for item in path.iterdir()
                if item.is_dir() and not item.name.startswith(".")
            ]
        except Exception as e:
            log.error(f"Error listing directories in {path}: {e}")
            return []


class ResultsExtractionService:
    """Extracts raw data from results directories."""

    def __init__(self, file_service: FileService):
        self.file_service = file_service

    def extract_model_results(self, results_dir: Path) -> dict[str, any]:
        """Extract results for all models."""
        model_results = {}

        for model_name in self.file_service.list_directories(results_dir):
            model_path = results_dir / model_name
            results_file = model_path / "results.json"

            if self.file_service.file_exists(results_file):
                results_data = self.file_service.load_json(results_file)
                if results_data:
                    model_results[model_name] = results_data
                    log.debug(f"Loaded results for model: {model_name}")

        log.info(f"Extracted results for {len(model_results)} models")
        return model_results

    def extract_execution_stats(self, results_dir: Path) -> dict[str, any] | None:
        """Extract execution statistics."""
        stats_file = results_dir / "stats.json"

        if self.file_service.file_exists(stats_file):
            stats_data = self.file_service.load_json(stats_file)
            if stats_data:
                log.debug("Loaded execution statistics")
                return stats_data

        log.warning("No execution statistics found")
        return None


class MetricsCalculationService:
    """Calculates performance statistics and aggregations."""

    @staticmethod
    def calculate_model_performance(
        model_name: str, results_data: dict[str, any]
    ) -> ModelPerformance:
        """Calculate performance metrics for a single model."""
        performance = ModelPerformance(model_name=model_name)

        scores = []
        test_count = 0

        # Handle new data structure with test_cases array
        if "test_cases" in results_data:
            for test_case in results_data["test_cases"]:
                if "runs" in test_case:
                    for run_data in test_case["runs"]:
                        if isinstance(run_data, dict):
                            # Use llm_eval score if available, otherwise use response_match
                            score = run_data.get("llm_eval", {}).get("score")
                            if score is None:
                                score = run_data.get("response_match", 0)

                            # Ensure score is valid
                            if score is not None and isinstance(score, (int, float)):
                                scores.append(score)

                            test_count += 1

        # Calculate metrics
        if scores:
            performance.scores = scores
            performance.average_score = sum(scores) / len(scores)
            performance.success_rate = (
                len([s for s in scores if s >= 0.7]) / len(scores) * 100
            )

        performance.test_count = test_count
        performance.estimated_cost = test_count * 0.02  # Rough estimate

        return performance

    @staticmethod
    def format_execution_time(total_time: float) -> tuple[str, str]:
        """Format execution time into readable strings."""
        minutes = int(total_time // 60)
        seconds = int(total_time % 60)
        formatted = f"{minutes}m {seconds}s"
        duration = f"{minutes} minutes {seconds} seconds"
        return formatted, duration

    @staticmethod
    def calculate_run_statistics(model_results: dict[str, any]) -> tuple[int, str]:
        """Calculate run statistics from model results."""
        test_cases = set()
        all_run_counts = []

        for _model_name, results in model_results.items():
            if "test_cases" in results:
                for test_case in results["test_cases"]:
                    test_case_id = test_case.get("test_case_id")
                    if test_case_id:
                        test_cases.add(test_case_id)

                        # Count unique runs
                        if "runs" in test_case:
                            unique_runs = set()
                            for run in test_case["runs"]:
                                if isinstance(run, dict) and "run" in run:
                                    unique_runs.add(run["run"])
                            if unique_runs:
                                all_run_counts.append(len(unique_runs))

        total_tests = len(test_cases)

        # Determine run count description
        if all_run_counts:
            run_count_mode = Counter(all_run_counts).most_common(1)[0][0]
            runs_description = f"{run_count_mode} run{'s' if run_count_mode != 1 else ''} per test case"
        else:
            runs_description = "Not available"

        return total_tests, runs_description


class ChartDataService:
    """Generates chart and visualization data."""

    def __init__(self, file_service: FileService):
        self.file_service = file_service

    def generate_chart_configuration(
        self, model_results: dict[str, any], test_cases: dict[str, dict[str, any]]
    ) -> ChartConfiguration:
        """Generate chart configuration data."""
        chart_config = ChartConfiguration()

        # Extract categories and organize test cases
        category_test_mapping = self._extract_category_mapping(model_results)

        # Calculate category scores for each model
        category_scores = self._calculate_category_scores(
            category_test_mapping, test_cases, model_results
        )

        # Prepare chart data
        if category_scores:
            chart_config.categories = sorted(category_scores.keys())
            chart_config.category_scores = category_scores
            chart_config.datasets = self._generate_chart_datasets(
                category_scores, model_results
            )

        return chart_config

    def _extract_category_mapping(
        self, model_results: dict[str, any]
    ) -> dict[str, set[str]]:
        """Extract category to test case mapping."""
        category_test_mapping = defaultdict(set)

        for _model_name, results in model_results.items():
            if "test_cases" in results:
                for test_case in results["test_cases"]:
                    test_id = test_case.get("test_case_id")
                    category = test_case.get("category")
                    if test_id and category:
                        category_test_mapping[category].add(test_id)

        # Convert sets to sorted lists
        return {
            cat: sorted(tests) for cat, tests in category_test_mapping.items()
        }

    def _calculate_category_scores(
        self,
        category_test_mapping: dict[str, list[str]],
        test_cases: dict[str, dict[str, any]],
        model_results: dict[str, any],
    ) -> dict[str, dict[str, float]]:
        """Calculate average scores by category for each model."""
        category_scores = {}

        for category, test_names in category_test_mapping.items():
            category_scores[category] = {}

            for model_name in model_results:
                scores = []

                # Collect scores for this category and model
                for test_name in test_names:
                    if test_name in test_cases and model_name in test_cases[test_name]:
                        test_data = test_cases[test_name][model_name]
                        if isinstance(test_data, dict) and "runs" in test_data:
                            for run in test_data["runs"]:
                                if isinstance(run, dict):
                                    # Prioritize llm_eval score over response_match
                                    score = run.get("llm_eval", {}).get("score")
                                    if score is not None and isinstance(
                                        score, (int, float)
                                    ):
                                        scores.append(score)
                                    else:
                                        score = run.get("response_match", 0)
                                        if score is not None and isinstance(
                                            score, (int, float)
                                        ):
                                            scores.append(score)

                # Calculate average score for this category and model
                category_scores[category][model_name] = (
                    sum(scores) / len(scores) if scores else 0
                )

        return category_scores

    def _generate_chart_datasets(
        self,
        category_scores: dict[str, dict[str, float]],
        model_results: dict[str, any],
    ) -> list[dict[str, any]]:
        """Generate chart datasets for visualization."""
        # Enhanced model colors with better contrast
        model_colors = {
            "gpt-4": "#059669",
            "gpt-4-1": "#10b981",
            "claude-3-sonnet": "#0ea5e9",
            "gemini-pro": "#f59e0b",
            "gemini-2.5-pro": "#f59e0b",
            "gemini-flash": "#8b5cf6",
            "gemini-2.5-flash": "#a855f7",
            "gpt-3.5-turbo": "#ef4444",
            "claude-3-haiku": "#84cc16",
        }

        chart_datasets = []
        categories = sorted(category_scores.keys())

        for model_name in sorted(model_results.keys()):
            model_data = []
            for category in categories:
                score = category_scores[category].get(model_name, 0)
                model_data.append(round(score, 3))

            color = model_colors.get(model_name)
            if color is None:
                # Generate a random color if not in the predefined list
                def generate_random_component():
                    return random.randint(0, 255)

                color = f"#{generate_random_component():02x}{generate_random_component():02x}{generate_random_component():02x}"

            chart_datasets.append(
                {
                    "label": model_name,
                    "data": model_data,
                    "backgroundColor": color,
                    "borderColor": color,
                    "borderWidth": 1,
                    "borderRadius": 4,
                    "borderSkipped": False,
                }
            )

        return chart_datasets


class ModalDataService:
    """Generates data specifically for modal functionality."""

    def __init__(self, file_service: FileService):
        self.file_service = file_service

    def generate_modal_test_data(
        self, test_case_id: str, model_results: dict[str, any]
    ) -> dict[str, any]:
        """Generate test data for modal JavaScript consumption."""
        modal_data = {"model_scores": {}, "tool_scores": {}, "individual_runs": {}}

        # Extract data for this specific test case
        for model_name, results in model_results.items():
            if "test_cases" in results:
                for test_case in results["test_cases"]:
                    if test_case.get("test_case_id") == test_case_id:
                        # Extract model scores
                        runs = test_case.get("runs", [])
                        if runs:
                            response_scores = []
                            tool_scores = []
                            individual_runs = []

                            for run_data in runs:
                                if isinstance(run_data, dict):
                                    # Get response score (prioritize llm_eval)
                                    response_score = run_data.get("response_match", 0)
                                    llm_score = run_data.get("llm_eval", {}).get(
                                        "score"
                                    )

                                    # Get tool score
                                    tool_score = run_data.get("tool_match", 1.0)

                                    # Get other data
                                    duration = run_data.get("duration_seconds", 0)
                                    run_number = run_data.get("run", 1)
                                    reasoning = run_data.get("llm_eval", {}).get(
                                        "reasoning", "No reasoning provided"
                                    )

                                    if response_score is not None:
                                        response_scores.append(response_score)
                                        tool_scores.append(tool_score)

                                        individual_runs.append(
                                            {
                                                "run_number": run_number,
                                                "response_score": response_score,
                                                "tool_score": tool_score,
                                                "llm_eval": llm_score,
                                                "llm_reasoning": reasoning,
                                                "execution_time": duration,
                                                "query": "",
                                                "actual_response": "",
                                                "expected_response": "",
                                            }
                                        )

                            # Calculate averages
                            if response_scores:
                                modal_data["model_scores"][model_name] = sum(
                                    response_scores
                                ) / len(response_scores)
                                modal_data["tool_scores"][model_name] = sum(
                                    tool_scores
                                ) / len(tool_scores)
                                modal_data["individual_runs"][
                                    model_name
                                ] = individual_runs

        return modal_data


class TemplateDataService:
    """Formats data for template consumption."""

    def __init__(self, file_service: FileService):
        self.file_service = file_service
        self.modal_service = ModalDataService(file_service)

    def generate_performance_metrics_table(
        self, model_performances: dict[str, ModelPerformance]
    ) -> str:
        """Generate HTML table rows for performance metrics."""
        metrics_rows = []

        for model_name, performance in model_performances.items():
            if performance.scores:
                score_class = self._get_score_class(performance.average_score)

                metrics_rows.append(
                    f"""
                    <tr>
                        <td class="model-name">{model_name}</td>
                        <td class="metric-value {score_class}">{performance.average_score:.2f}</td>
                        <td class="metric-value {score_class}">{performance.success_rate:.0f}%</td>
                        <td class="metric-value">{performance.test_count}</td>
                        <td class="estimated-cost">${performance.estimated_cost:.2f}</td>
                    </tr>
                """
                )

        return "".join(metrics_rows)

    def generate_breakdown_content(
        self,
        test_case_results: list[TestCaseResult],
        model_performances: dict[str, ModelPerformance],
        model_results: dict[str, any] = None,
    ) -> str:
        """Generate detailed breakdown content by category with modal support."""
        # Group test cases by category
        categories_with_tests = defaultdict(list)
        for test_result in test_case_results:
            categories_with_tests[test_result.category].append(test_result)

        breakdown_sections = []

        for category, test_results in sorted(categories_with_tests.items()):
            category_tests = []

            for test_result in test_results:
                test_scores = []

                for model_name, _performance in model_performances.items():
                    if test_result.test_case_id in test_result.model_results:
                        model_data = test_result.model_results[
                            test_result.test_case_id
                        ].get(model_name, {})

                        if isinstance(model_data, dict) and "runs" in model_data:
                            scores = []
                            durations = []
                            success_count = 0

                            for run in model_data["runs"]:
                                if isinstance(run, dict):
                                    # Use llm_eval score if available, otherwise use response_match
                                    score = run.get("llm_eval", {}).get("score")
                                    if score is not None and isinstance(
                                        score, (int, float)
                                    ):
                                        scores.append(score)
                                    else:
                                        score = run.get("response_match", 0)
                                        if score is not None and isinstance(
                                            score, (int, float)
                                        ):
                                            scores.append(score)

                                    # Track duration and success
                                    duration = run.get("duration_seconds", 0)
                                    if duration is not None and isinstance(
                                        duration, (int, float)
                                    ):
                                        durations.append(duration)
                                    if (
                                        score is not None
                                        and isinstance(score, (int, float))
                                        and score >= 0.7
                                    ):
                                        success_count += 1

                            if scores:
                                avg_score = sum(scores) / len(scores)
                                avg_duration = (
                                    sum(durations) / len(durations) if durations else 0
                                )
                                score_class = self._get_score_class(avg_score)

                                test_scores.append(
                                    f"""
                                    <div class="model-result {score_class}">
                                        <span class="model-score">{model_name}</span>
                                        <span class="score-value">LLM Eval: {avg_score:.3f}</span>
                                        <span class="avg-duration">Avg time: {avg_duration:.1f}s</span>
                                    </div>
                                """
                                )

                if test_scores:
                    # Generate modal data for this test case
                    modal_data = {}
                    if model_results:
                        modal_data = self.modal_service.generate_modal_test_data(
                            test_result.test_case_id, model_results
                        )

                    # Escape JSON for HTML attribute
                    modal_data_json = json.dumps(modal_data).replace('"', "&quot;")

                    category_tests.append(
                        f"""
                        <div class="test-item"
                             data-test-name="{test_result.test_case_id}"
                             data-test-description="{test_result.description}"
                             data-test-data="{modal_data_json}">
                            <div class="test-header">
                                <span class="test-name">{test_result.test_case_id}</span>
                                <span class="test-description">{test_result.description}</span>
                            </div>
                            <div class="model-results">
                                {''.join(test_scores)}
                            </div>
                        </div>
                    """
                    )

            if category_tests:
                test_count = len(category_tests)
                breakdown_sections.append(
                    f"""
                    <div class="category-section">
                        <div class="category-header">
                            <h3 class="category-title">{category} ({test_count} test case{'s' if test_count != 1 else ''})</h3>
                            <span class="category-toggle">▶</span>
                        </div>
                        <div class="category-content">
                            {''.join(category_tests)}
                        </div>
                    </div>
                """
                )

        return "".join(breakdown_sections)

    def generate_model_execution_times(self, model_results: dict[str, any]) -> str:
        """Generate model execution times HTML."""
        execution_times_html = []

        # Model colors for consistency
        model_colors = {
            "gpt-4": "#059669",
            "gpt-4-1": "#10b981",
            "claude-3-sonnet": "#0ea5e9",
            "gemini-pro": "#f59e0b",
            "gemini-2.5-pro": "#f59e0b",
            "gemini-flash": "#8b5cf6",
            "gpt-3.5-turbo": "#ef4444",
            "claude-3-haiku": "#84cc16",
        }

        for model_name in sorted(model_results.keys()):
            results = model_results[model_name]
            execution_time = results.get("total_execution_time")

            if execution_time is not None:
                # Format time as minutes and seconds
                minutes = int(execution_time // 60)
                seconds = int(execution_time % 60)
                time_formatted = f"{minutes}m {seconds}s"

                color = model_colors.get(model_name, "#6b7280")
                execution_times_html.append(
                    f"""
                    <div style="background: #f9fafb; padding: 15px; border-radius: 8px; border-left: 4px solid {color}; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                        <div style="font-weight: 600; color: #1f2937; margin-bottom: 5px; font-size: 1rem;">{model_name}</div>
                        <div style="color: {color}; font-weight: 700; font-size: 1.25rem; font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace;">{time_formatted}</div>
                        <div style="color: #6b7280; font-size: 0.85rem; margin-top: 2px;">Total execution time</div>
                    </div>
                """
                )

        return "".join(execution_times_html)

    def calculate_best_worst_tests(
        self, test_case_results: list[TestCaseResult]
    ) -> tuple[str, str]:
        """Calculate best and worst performing tests."""
        test_averages = {}

        for test_result in test_case_results:
            if test_result.average_score > 0:
                test_averages[test_result.test_case_id] = test_result.average_score

        if test_averages:
            best_test = max(test_averages, key=test_averages.get)
            worst_test = min(test_averages, key=test_averages.get)

            best_result = f"{best_test} (avg: {test_averages[best_test]:.2f})"
            worst_result = f"{worst_test} (avg: {test_averages[worst_test]:.2f})"

            return best_result, worst_result

        return "Not available", "Not available"

    def calculate_average_time(
        self, model_performances: dict[str, ModelPerformance]
    ) -> str:
        """Calculate overall average time."""
        all_durations = []

        # Extract durations from model results if available
        for performance in model_performances.values():
            if hasattr(performance, "durations") and performance.durations:
                all_durations.extend(performance.durations)

        if all_durations:
            avg_duration = sum(all_durations) / len(all_durations)
            return f"{avg_duration:.1f}s"

        return "Not available"

    def _get_score_class(self, score: float) -> str:
        """Get CSS class based on score value."""
        if score >= 0.7:
            return "score-high"
        elif score >= 0.4:
            return "score-medium"
        else:
            return "score-low"


class ModelResultsProcessor:
    """Processes individual model results."""

    def __init__(self, file_service: FileService):
        self.file_service = file_service

    def organize_test_cases(
        self, model_results: dict[str, any]
    ) -> dict[str, dict[str, any]]:
        """Organize test cases by test case ID and model."""
        test_cases = {}

        for model_name, results in model_results.items():
            if "test_cases" in results:
                for test_case in results["test_cases"]:
                    test_case_id = test_case.get("test_case_id")
                    if test_case_id:
                        if test_case_id not in test_cases:
                            test_cases[test_case_id] = {}
                        test_cases[test_case_id][model_name] = test_case

        return test_cases

    def create_test_case_results(
        self, test_cases: dict[str, dict[str, any]]
    ) -> list[TestCaseResult]:
        """Create TestCaseResult objects from organized test cases."""
        test_case_results = []

        for test_case_id, models_data in test_cases.items():
            # Get test case metadata
            try:
                # Get path from the first available run data
                first_model_data = next(iter(models_data.values()))
                test_case_path = first_model_data["runs"][0]["test_case_path"]
                test_case_data = load_test_case(test_case_path)
                category = test_case_data.get("category", "Uncategorized")
                description = test_case_data.get(
                    "description", f"Test case: {test_case_id}"
                )
            except (StopIteration, IndexError, KeyError):
                category = "Uncategorized"
                description = f"Test case: {test_case_id}"

            # Calculate average score across all models and runs
            all_scores = []
            for model_data in models_data.values():
                if isinstance(model_data, dict) and "runs" in model_data:
                    for run in model_data["runs"]:
                        if isinstance(run, dict):
                            score = run.get("llm_eval", {}).get("score")
                            if score is None:
                                score = run.get("response_match", 0)
                            if score is not None and isinstance(score, (int, float)):
                                all_scores.append(score)

            average_score = sum(all_scores) / len(all_scores) if all_scores else 0

            test_result = TestCaseResult(
                test_case_id=test_case_id,
                category=category,
                description=description,
                model_results={test_case_id: models_data},
                average_score=average_score,
            )

            test_case_results.append(test_result)

        return test_case_results


class ReportDataProcessor:
    """Main processor that coordinates the entire data processing pipeline."""

    def __init__(self):
        self.file_service = FileService()
        self.extraction_service = ResultsExtractionService(self.file_service)
        self.metrics_service = MetricsCalculationService()
        self.chart_service = ChartDataService(self.file_service)
        self.template_service = TemplateDataService(self.file_service)
        self.processor = ModelResultsProcessor(self.file_service)

    def get_evaluation_data(self, results_dir: Path) -> dict[str, any]:
        """Extract and process basic evaluation data."""
        log.info("Processing evaluation data...")

        # Initialize metrics
        metrics = EvaluationMetrics()

        # Extract model results
        model_results = self.extraction_service.extract_model_results(results_dir)
        if not model_results:
            log.warning("No model results found")
            return self._metrics_to_dict(metrics)

        # Set basic model information
        metrics.models = list(model_results.keys())

        # Calculate test statistics
        total_tests, runs_description = self.metrics_service.calculate_run_statistics(
            model_results
        )
        metrics.total_tests = total_tests
        metrics.runs = runs_description
        metrics.test_case_names = self._extract_test_case_names(model_results)

        # Extract execution statistics
        stats_data = self.extraction_service.extract_execution_stats(results_dir)
        if stats_data and "total_execution_time" in stats_data:
            total_time = stats_data["total_execution_time"]
            metrics.total_execution_time = total_time
            formatted_time, duration = self.metrics_service.format_execution_time(
                total_time
            )
            metrics.total_execution_time_formatted = formatted_time
            metrics.duration = duration

        log.info(f"Processed evaluation data for {len(metrics.models)} models")
        return self._metrics_to_dict(metrics)

    def get_detailed_evaluation_data(self, results_dir: Path) -> dict[str, any]:
        """Extract and process detailed evaluation data for charts and breakdowns."""
        log.info("Processing detailed evaluation data...")

        # Extract model results
        model_results = self.extraction_service.extract_model_results(results_dir)
        if not model_results:
            log.warning("No model results found for detailed data")
            return self._empty_detailed_data()

        # Calculate model performances
        model_performances = {}
        total_evaluations = 0

        for model_name, results_data in model_results.items():
            performance = self.metrics_service.calculate_model_performance(
                model_name, results_data
            )
            model_performances[model_name] = performance
            total_evaluations += performance.test_count

        # Organize test cases
        test_cases = self.processor.organize_test_cases(model_results)
        test_case_results = self.processor.create_test_case_results(test_cases)

        # Generate chart configuration
        chart_config = self.chart_service.generate_chart_configuration(
            model_results, test_cases
        )

        # Generate template data
        performance_metrics_rows = (
            self.template_service.generate_performance_metrics_table(model_performances)
        )
        breakdown_content = self.template_service.generate_breakdown_content(
            test_case_results, model_performances, model_results
        )
        model_execution_times = self.template_service.generate_model_execution_times(
            model_results
        )

        # Calculate best/worst tests and average time
        best_test, worst_test = self.template_service.calculate_best_worst_tests(
            test_case_results
        )
        avg_time = self.template_service.calculate_average_time(model_performances)

        detailed_data = {
            "performance_metrics_rows": performance_metrics_rows,
            "breakdown_content": breakdown_content,
            "best_test": best_test,
            "worst_test": worst_test,
            "avg_time": avg_time,
            "total_evaluations": total_evaluations,
            "categories_data": json.dumps(chart_config.categories),
            "chart_datasets_data": json.dumps(chart_config.datasets),
            "model_execution_times": model_execution_times,
        }

        log.info("Processed detailed evaluation data successfully")
        return detailed_data

    def _extract_test_case_names(self, model_results: dict[str, any]) -> list[str]:
        """Extract unique test case names from model results."""
        test_case_names = set()

        for results in model_results.values():
            if "test_cases" in results:
                for test_case in results["test_cases"]:
                    test_case_id = test_case.get("test_case_id")
                    if test_case_id:
                        test_case_names.add(test_case_id)

        return sorted(test_case_names)

    def _metrics_to_dict(self, metrics: EvaluationMetrics) -> dict[str, any]:
        """Convert EvaluationMetrics to dictionary."""
        # Generate model tags HTML
        model_tags = ""
        if metrics.models:
            model_tags = "".join(
                [f'<span class="model-tag">{model}</span>' for model in metrics.models]
            )

        # Generate test cases list HTML
        test_cases_list = ""
        if metrics.test_case_names:
            test_cases_list = "".join(
                [
                    f"<li>{test_case}.test.json</li>"
                    for test_case in metrics.test_case_names
                ]
            )
        elif metrics.total_tests > 0:
            test_cases_list = "<li>Test cases available (names not loaded)</li>"

        return {
            "models": metrics.models,
            "total_execution_time": metrics.total_execution_time,
            "total_execution_time_formatted": metrics.total_execution_time_formatted,
            "generation_time": metrics.generation_time,
            "timestamp": metrics.timestamp,
            "runs": metrics.runs,
            "total_tests": metrics.total_tests,
            "duration": metrics.duration,
            "test_case_names": metrics.test_case_names,
            # Template-specific keys
            "total_models": str(len(metrics.models)),
            "model_tags": model_tags,
            "test_cases_list": test_cases_list,
        }

    def _empty_detailed_data(self) -> dict[str, any]:
        """Return empty detailed data structure."""
        return {
            "performance_metrics_rows": "",
            "breakdown_content": "",
            "best_test": "Not available",
            "worst_test": "Not available",
            "avg_time": "Not available",
            "total_evaluations": 0,
            "categories_data": "[]",
            "chart_datasets_data": "[]",
            "model_execution_times": "",
        }


def main():
    """Main entry point for testing the report data processor."""
    import sys
    from pathlib import Path

    if len(sys.argv) > 1:
        results_dir = Path(sys.argv[1])
    else:
        # Default to test results directory
        script_dir = Path(__file__).parent
        results_dir = script_dir / "results" / "tests"

    processor = ReportDataProcessor()

    log.info("Testing evaluation data extraction...")
    eval_data = processor.get_evaluation_data(results_dir)
    log.info(f"Found {len(eval_data.get('models', []))} models")

    log.info("Testing detailed evaluation data extraction...")
    detailed_data = processor.get_detailed_evaluation_data(results_dir)
    log.info(f"Total evaluations: {detailed_data.get('total_evaluations', 0)}")

    log.info("Report data processing completed successfully!")


if __name__ == "__main__":
    main()
