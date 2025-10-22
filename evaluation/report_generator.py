"""
Refactored report generator with improved structure and readability.
This module generates HTML reports from evaluation results with a clean, modular architecture.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .report_data_processor import ReportDataProcessor
from .shared import EvaluationConfigLoader, TestSuiteConfiguration

log = logging.getLogger(__name__)


@dataclass
class ReportConfig:
    """Centralized configuration for report generation."""

    def __init__(self, config: TestSuiteConfiguration, results_dir: Path):
        self.config = config
        self.results_dir_name = config.results_directory

        # Calculate paths
        self.script_dir = Path(__file__).parent
        self.results_dir = results_dir
        self.templates_dir = self.script_dir / "report" / "templates"
        self.report_dir = self.script_dir / "report"
        self.output_path = self.results_dir / "report.html"

        self._validate_config()

    def _validate_config(self):
        """Validate configuration and required directories."""
        if not self.templates_dir.exists():
            raise FileNotFoundError(
                f"Templates directory not found: {self.templates_dir}"
            )
        if not self.report_dir.exists():
            raise FileNotFoundError(f"Report directory not found: {self.report_dir}")


@dataclass
class TemplateAssets:
    """Container for all template files and CSS content."""

    header: str = ""
    footer: str = ""
    benchmark_info: str = ""
    chart_section: str = ""
    detailed_breakdown: str = ""
    css_content: str = ""
    modal_html: str = ""
    modal_css: str = ""
    modal_script_js: str = ""
    modal_chart_functions_js: str = ""


@dataclass
class ReportMetadata:
    """Report generation metadata."""

    generation_time: str = field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    timestamp: str = field(
        default_factory=lambda: datetime.now().strftime("%B %d, %Y at %I:%M %p")
    )


class ConfigurationService:
    """Handles configuration loading and validation."""

    def __init__(self, config_path: str):
        self.config_loader = EvaluationConfigLoader(config_path)
        self._config_cache = None

    def get_config(self) -> TestSuiteConfiguration:
        """Get the main configuration."""
        if self._config_cache is None:
            self._config_cache = self.config_loader.load_configuration()
        return self._config_cache

    def create_report_config(self, results_dir: Path) -> ReportConfig:
        """Create a ReportConfig instance."""
        config = self.get_config()
        return ReportConfig(config, results_dir)


class FileService:
    """Handles all file I/O operations with proper error handling."""

    @staticmethod
    def read_file(filepath: Path, encoding: str = "utf-8") -> str:
        """Read file content with error handling."""
        try:
            return filepath.read_text(encoding=encoding)
        except FileNotFoundError:
            log.error(f"File not found: {filepath}")
            raise
        except Exception as e:
            log.error(f"Error reading file {filepath}: {e}")
            raise

    @staticmethod
    def write_file(filepath: Path, content: str, encoding: str = "utf-8"):
        """Write file content with error handling."""
        try:
            # Ensure directory exists
            filepath.parent.mkdir(parents=True, exist_ok=True)

            filepath.write_text(content, encoding=encoding)
            log.info(f"File written successfully: {filepath}")
        except Exception as e:
            log.error(f"Error writing file {filepath}: {e}")
            raise

    @staticmethod
    def file_exists(filepath: Path) -> bool:
        """Check if file exists."""
        return filepath.exists() and filepath.is_file()


class TemplateService:
    """Manages HTML template loading and validation."""

    def __init__(self, file_service: FileService):
        self.file_service = file_service

    def load_template(self, template_path: Path) -> str:
        """Load a single template file."""
        if not self.file_service.file_exists(template_path):
            log.warning(f"Template file not found: {template_path}")
            return ""

        try:
            content = self.file_service.read_file(template_path)
            log.debug(f"Loaded template: {template_path}")
            return content
        except Exception as e:
            log.error(f"Failed to load template {template_path}: {e}")
            return ""

    def load_all_templates(self, config: ReportConfig) -> TemplateAssets:
        """Load all required templates including modal components."""
        log.info("Loading HTML templates and modal components...")

        assets = TemplateAssets()

        # Define template files
        template_files = {
            "header": config.templates_dir / "header.html",
            "footer": config.templates_dir / "footer.html",
            "benchmark_info": config.report_dir / "benchmark_info.html",
            "chart_section": config.report_dir / "chart_section.html",
            "detailed_breakdown": config.report_dir / "detailed_breakdown.html",
            "modal_html": config.report_dir / "modal.html",
        }

        # Load each template
        for template_name, template_path in template_files.items():
            content = self.load_template(template_path)
            setattr(assets, template_name, content)

        log.info(f"Loaded {len(template_files)} templates")
        return assets


class AssetService:
    """Handles CSS and static asset management including modal assets."""

    def __init__(self, file_service: FileService):
        self.file_service = file_service

    def load_css_content(self, report_dir: Path) -> str:
        """Load CSS content for inlining."""
        css_path = report_dir / "performance_metrics_styles.css"

        if not self.file_service.file_exists(css_path):
            log.warning(f"CSS file not found: {css_path}")
            return ""

        try:
            content = self.file_service.read_file(css_path)
            log.info(f"Loaded CSS content from: {css_path}")
            return content
        except Exception as e:
            log.error(f"Failed to load CSS content: {e}")
            return ""

    def load_modal_assets(self, report_dir: Path, assets: TemplateAssets):
        """Load modal CSS and JavaScript files."""
        log.info("Loading modal assets...")

        # Load modal CSS
        modal_css_path = report_dir / "modal_styles.css"
        if self.file_service.file_exists(modal_css_path):
            try:
                assets.modal_css = self.file_service.read_file(modal_css_path)
                log.info("Loaded modal CSS")
            except Exception as e:
                log.error(f"Failed to load modal CSS: {e}")

        # Load modal JavaScript files
        modal_script_path = report_dir / "modal_script.js"
        if self.file_service.file_exists(modal_script_path):
            try:
                assets.modal_script_js = self.file_service.read_file(modal_script_path)
                log.info("Loaded modal script JS")
            except Exception as e:
                log.error(f"Failed to load modal script JS: {e}")

        modal_chart_functions_path = report_dir / "modal_chart_functions.js"
        if self.file_service.file_exists(modal_chart_functions_path):
            try:
                assets.modal_chart_functions_js = self.file_service.read_file(
                    modal_chart_functions_path
                )
                log.info("Loaded modal chart functions JS")
            except Exception as e:
                log.error(f"Failed to load modal chart functions JS: {e}")

        log.info("Modal assets loaded successfully")


class TemplateProcessor:
    """Handles template rendering and placeholder replacement."""

    @staticmethod
    def replace_placeholders(template_content: str, data: dict[str, any]) -> str:
        """Replace placeholders in template with actual data."""
        try:
            # Convert all values to strings for replacement
            replacements = {}
            for key, value in data.items():
                if isinstance(value, (list, dict)):
                    replacements[key] = (
                        json.dumps(value) if key.endswith("_data") else str(value)
                    )
                else:
                    replacements[key] = str(value) if value is not None else ""

            # Perform replacements
            processed_content = template_content
            for placeholder, value in replacements.items():
                # Handle different placeholder formats
                placeholder_patterns = [
                    f"{{{{{placeholder.upper()}}}}}",  # {{PLACEHOLDER}} (uppercase)
                    f"{{{{{placeholder}}}}}",  # {{placeholder}} (original case)
                    f"{{{placeholder}}}",  # {placeholder}
                ]

                for pattern in placeholder_patterns:
                    processed_content = processed_content.replace(pattern, value)

            return processed_content

        except Exception as e:
            log.error(f"Error replacing placeholders: {e}")
            return template_content

    def process_template_with_data(
        self, template_content: str, data: dict[str, any]
    ) -> str:
        """Process a template with evaluation data."""
        if not template_content:
            log.warning("Empty template content provided")
            return ""

        return self.replace_placeholders(template_content, data)


class CSSProcessor:
    """Handles CSS processing and inlining including modal styles."""

    @staticmethod
    def inline_css(html_content: str, css_content: str) -> str:
        """Inline CSS content into HTML."""
        if not css_content:
            return html_content

        try:
            # Replace CSS link with inline styles
            css_link_pattern = (
                '<link rel="stylesheet" href="performance_metrics_styles.css">'
            )
            inline_css_block = f"<style>\n{css_content}\n</style>"

            processed_html = html_content.replace(css_link_pattern, inline_css_block)
            log.debug("CSS content inlined successfully")
            return processed_html

        except Exception as e:
            log.error(f"Error inlining CSS: {e}")
            return html_content

    @staticmethod
    def inline_modal_assets(html_content: str, assets: TemplateAssets) -> str:
        """Inline modal CSS and JavaScript into HTML."""
        try:
            # Combine all CSS (main + modal)
            combined_css = assets.css_content
            if assets.modal_css:
                combined_css += f"\n\n/* Modal Styles */\n{assets.modal_css}"

            # Replace CSS link with combined inline styles OR add to existing style block
            css_link_pattern = (
                '<link rel="stylesheet" href="performance_metrics_styles.css">'
            )
            if css_link_pattern in html_content:
                inline_css_block = f"<style>\n{combined_css}\n</style>"
                processed_html = html_content.replace(
                    css_link_pattern, inline_css_block
                )
            else:
                # If no CSS link found, add styles to existing style block or create new one
                if "<style>" in html_content:
                    # Add modal CSS to existing style block
                    if assets.modal_css:
                        style_end = html_content.find("</style>")
                        if style_end != -1:
                            processed_html = (
                                html_content[:style_end]
                                + f"\n\n/* Modal Styles */\n{assets.modal_css}\n"
                                + html_content[style_end:]
                            )
                        else:
                            processed_html = html_content
                    else:
                        processed_html = html_content
                else:
                    # Create new style block in head
                    head_end = html_content.find("</head>")
                    if head_end != -1:
                        inline_css_block = f"<style>\n{combined_css}\n</style>\n"
                        processed_html = (
                            html_content[:head_end]
                            + inline_css_block
                            + html_content[head_end:]
                        )
                    else:
                        processed_html = html_content

            # Add Chart.js CDN and modal HTML before closing body tag
            chart_js_cdn = (
                '<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>'
            )
            chart_js_boxplot_cdn = '<script src="https://cdn.jsdelivr.net/npm/@sgratzl/chartjs-chart-boxplot"></script>'

            # Combine modal JavaScript
            modal_js = ""
            if assets.modal_chart_functions_js:
                modal_js += f"\n<script>\n{assets.modal_chart_functions_js}\n</script>"
            if assets.modal_script_js:
                modal_js += f"\n<script>\n{assets.modal_script_js}\n</script>"

            # Insert modal HTML and scripts before closing body tag
            modal_content = ""
            if assets.modal_html:
                modal_content += f"\n{assets.modal_html}"

            modal_content += f"\n{chart_js_cdn}"
            modal_content += f"\n{chart_js_boxplot_cdn}"
            modal_content += modal_js

            # Insert before closing body tag
            if "</body>" in processed_html:
                processed_html = processed_html.replace(
                    "</body>", f"{modal_content}\n</body>"
                )
            else:
                # Fallback: append to end
                processed_html += modal_content

            log.debug("Modal assets inlined successfully")
            return processed_html

        except Exception as e:
            log.error(f"Error inlining modal assets: {e}")
            return html_content


class HTMLAssembler:
    """Assembles final HTML document from processed templates."""

    def __init__(
        self, template_processor: TemplateProcessor, css_processor: CSSProcessor
    ):
        self.template_processor = template_processor
        self.css_processor = css_processor

    def assemble_report(
        self,
        assets: TemplateAssets,
        evaluation_data: dict[str, any],
        detailed_data: dict[str, any],
    ) -> str:
        """Assemble the complete HTML report with modal functionality."""
        log.info("Assembling HTML report with modal functionality...")

        try:
            # Process each template with appropriate data
            processed_templates = {}

            # Process templates with evaluation data
            eval_templates = ["header", "benchmark_info"]
            for template_name in eval_templates:
                template_content = getattr(assets, template_name)
                processed_templates[template_name] = (
                    self.template_processor.process_template_with_data(
                        template_content, evaluation_data
                    )
                )

            # Process templates with detailed data
            detail_templates = ["chart_section", "detailed_breakdown"]
            for template_name in detail_templates:
                template_content = getattr(assets, template_name)
                processed_templates[template_name] = (
                    self.template_processor.process_template_with_data(
                        template_content, detailed_data
                    )
                )

            # Footer doesn't need data processing
            processed_templates["footer"] = assets.footer

            # Combine all templates in order
            html_sections = [
                processed_templates["header"],
                processed_templates["benchmark_info"],
                processed_templates["chart_section"],
                processed_templates["detailed_breakdown"],
                processed_templates["footer"],
            ]

            final_html = "".join(html_sections)

            # Inline CSS and modal assets into the complete HTML
            final_html = self.css_processor.inline_modal_assets(final_html, assets)

            log.info("HTML report with modal functionality assembled successfully")
            return final_html

        except Exception as e:
            log.error(f"Error assembling HTML report: {e}")
            raise


class ReportSummaryService:
    """Generates report summary information."""

    @staticmethod
    def generate_summary(
        evaluation_data: dict[str, any], output_path: Path
    ) -> dict[str, str]:
        """Generate summary information for logging."""
        models = evaluation_data.get("models", [])
        execution_time = evaluation_data.get(
            "total_execution_time_formatted", "Not available"
        )

        return {
            "output_path": str(output_path),
            "models_evaluated": ", ".join(models) if models else "No models found",
            "total_execution_time": execution_time,
            "models_count": str(len(models)),
            "generation_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }


class ReportGenerator:
    """Main orchestrator that coordinates the entire report generation process."""

    def __init__(self, config_path: str):
        # Initialize services
        self.config_service = ConfigurationService(config_path)
        self.file_service = FileService()
        self.template_service = TemplateService(self.file_service)
        self.asset_service = AssetService(self.file_service)
        self.template_processor = TemplateProcessor()
        self.css_processor = CSSProcessor()
        self.html_assembler = HTMLAssembler(self.template_processor, self.css_processor)
        self.summary_service = ReportSummaryService()

        # Initialize data processor
        self.data_processor = ReportDataProcessor()

    def generate_report(self, results_dir: Path):
        """Main entry point for report generation."""
        log.info("--- Starting HTML report generation ---")

        try:
            # Load configuration
            config = self._load_configuration(results_dir)

            # Load templates and assets
            assets = self._load_assets(config)

            # Get evaluation data
            evaluation_data, detailed_data = self._get_evaluation_data(config)

            # Generate HTML report
            html_content = self._generate_html_content(
                assets, evaluation_data, detailed_data
            )

            # Write report to file
            self._write_report(html_content, config.output_path)

            # Generate and log summary
            self._log_summary(evaluation_data, config.output_path)

            log.info("--- HTML report generation completed successfully ---")

        except Exception as e:
            log.error(f"Report generation failed: {e}")
            raise

    def _load_configuration(self, results_dir: Path) -> ReportConfig:
        """Load and validate configuration."""
        log.info("Loading configuration...")
        config = self.config_service.create_report_config(results_dir)
        log.info(f"Configuration loaded. Results directory: {config.results_dir}")
        return config

    def _load_assets(self, config: ReportConfig) -> TemplateAssets:
        """Load all templates and assets including modal components."""
        log.info("Loading templates and assets...")

        # Load templates
        assets = self.template_service.load_all_templates(config)

        # Load CSS content
        assets.css_content = self.asset_service.load_css_content(config.report_dir)

        # Load modal assets
        self.asset_service.load_modal_assets(config.report_dir, assets)

        log.info("Templates and assets loaded successfully")
        return assets

    def _get_evaluation_data(
        self, config: ReportConfig
    ) -> tuple[dict[str, any], dict[str, any]]:
        """Get evaluation data from the data processor."""
        log.info("Extracting evaluation data...")

        evaluation_data = self.data_processor.get_evaluation_data(config.results_dir)
        detailed_data = self.data_processor.get_detailed_evaluation_data(
            config.results_dir
        )

        log.info("Evaluation data extracted successfully")
        return evaluation_data, detailed_data

    def _generate_html_content(
        self,
        assets: TemplateAssets,
        evaluation_data: dict[str, any],
        detailed_data: dict[str, any],
    ) -> str:
        """Generate the complete HTML content."""
        log.info("Generating HTML content...")

        html_content = self.html_assembler.assemble_report(
            assets, evaluation_data, detailed_data
        )

        log.info("HTML content generated successfully")
        return html_content

    def _write_report(self, html_content: str, output_path: Path):
        """Write the HTML report to file."""
        log.info(f"Writing report to: {output_path}")
        self.file_service.write_file(output_path, html_content)

    def _log_summary(self, evaluation_data: dict[str, any], output_path: Path):
        """Log summary information about the generated report."""
        summary = self.summary_service.generate_summary(evaluation_data, output_path)

        log.info("--- Report Generation Summary ---")
        log.info(f"Report generated at: {summary['output_path']}")
        log.info(f"Models evaluated: {summary['models_evaluated']}")
        log.info(f"Total execution time: {summary['total_execution_time']}")
        log.info(f"Generation completed at: {summary['generation_time']}")


def main(config_path: str = "evaluation/test_suite_config.json"):
    """Main entry point for the report generator."""
    try:
        generator = ReportGenerator(config_path)
        # For standalone execution, calculate results_dir based on config
        config = generator.config_service.get_config()
        results_dir_name = config.results_directory
        script_dir = Path(__file__).parent
        results_dir = script_dir / "results" / results_dir_name
        generator.generate_report(results_dir)
    except Exception as e:
        log.error(f"Report generation failed: {e}")
        raise


if __name__ == "__main__":
    main()
