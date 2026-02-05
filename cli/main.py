import click
import os
import sys
import warnings

_suppress_warnings = "--suppress-warnings" in sys.argv
if _suppress_warnings:
    warnings.simplefilter("ignore")
    sys.argv.remove("--suppress-warnings")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))

from cli import __version__
from cli.commands.init_cmd import init
from cli.commands.run_cmd import run
from cli.commands.add_cmd import add
from cli.commands.plugin_cmd import plugin
from cli.commands.eval_cmd import eval_cmd
from cli.commands.docs_cmd import docs
from cli.commands.tools_cmd import tools


@click.group(context_settings=dict(help_option_names=['-h', '--help']))
@click.version_option(
    __version__, "-v", "--version", help="Show the CLI version and exit."
)
@click.option(
    '--suppress-warnings',
    is_flag=True,
    expose_value=False,
    is_eager=True,
    help="Suppress warnings emitted by Python's warnings module."
)
def cli():
    """Solace CLI Application"""
    pass


cli.add_command(init)
cli.add_command(run)
cli.add_command(add)
cli.add_command(plugin)
cli.add_command(eval_cmd)
cli.add_command(docs)
cli.add_command(tools)


def main():
    cli()


if __name__ == "__main__":
    main()
