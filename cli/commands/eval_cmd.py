import click
from importlib import metadata
from pathlib import Path

from evaluation.run import main as run_evaluation_main
from cli.utils import error_exit, load_template


def _ensure_sam_rest_gateway_installed():
    """Checks if the sam-rest-gateway package is installed."""
    try:
        metadata.distribution("sam-rest-gateway")
    except metadata.PackageNotFoundError:
        error_exit(
            "Error: 'sam-rest-gateway' is not installed. "
            "Please install it using: "
            'pip install "sam-rest-gateway @ git+https://github.com/SolaceLabs/solace-agent-mesh-core-plugins#subdirectory=sam-rest-gateway"'
        )


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
        error_exit(
            "Error: 'configs/shared_config.yaml' not found. Please run 'sam init' first."
        )

    try:
        template_content = load_template("eval_backend_template.yaml")
        with open(eval_backend_config_path, "w", encoding="utf-8") as f:
            f.write(template_content)
        click.echo(
            click.style(
                f"Successfully created '{eval_backend_config_path.relative_to(project_root)}'.",
                fg="green",
            )
        )
    except Exception as e:
        error_exit(f"Failed to create eval_backend.yaml: {e}")


@click.command(name="eval")
@click.argument(
    "test_suite_config_path",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    required=True,
    metavar="<PATH>",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Enable verbose output.",
)
def eval_cmd(test_suite_config_path, verbose):
    """
    Run an evaluation suite using a specified configuration file. Such as path/to/file.yaml.

    <PATH>: The path to the evaluation test suite config file.
    """
    click.echo(
        click.style(
            f"Starting evaluation with test_suite_config: {test_suite_config_path}",
            fg="blue",
        )
    )
    _ensure_sam_rest_gateway_installed()
    _ensure_eval_backend_config_exists()
    try:
        run_evaluation_main(test_suite_config_path, verbose=verbose)
        click.echo(click.style("Evaluation completed successfully.", fg="green"))
    except Exception as e:
        error_exit(f"An error occurred during evaluation: {e}")
