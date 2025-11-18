import os
from pathlib import Path

import click

from cli.utils import error_exit
from evaluation.run import main as run_evaluation_main


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

    # Set logging config path for evaluation
    project_root = Path.cwd()
    logging_config_path = project_root / "configs" / "logging_config.yaml"
    if logging_config_path.exists():
        os.environ["LOGGING_CONFIG_PATH"] = str(logging_config_path.resolve())

    try:
        run_evaluation_main(test_suite_config_path, verbose=verbose)
        click.echo(click.style("Evaluation completed successfully.", fg="green"))
    except Exception as e:
        error_exit(f"An error occurred during evaluation: {e}")
