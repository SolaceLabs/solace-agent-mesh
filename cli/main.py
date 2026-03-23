import click
import os
import sys
import warnings
from importlib.metadata import version, PackageNotFoundError

_suppress_warnings = "--suppress-warnings" in sys.argv
if _suppress_warnings:
    warnings.simplefilter("ignore")
    sys.argv.remove("--suppress-warnings")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))

from cli import __version__
from cli.lazy_group import LazyGroup

# ---------------------------------------------------------------------------
# Lazy command registry
#
# Each entry maps a CLI command name to its import path and short help text.
# ---------------------------------------------------------------------------
_COMMANDS = {
    "init":   ("cli.commands.init_cmd:init",    "Initialize a new Solace application project."),
    "run":    ("cli.commands.run_cmd:run",       "Run the Solace application with specified or discovered YAML configuration files."),
    "add":    ("cli.commands.add_cmd:add",       "Creates templates for agents, gateways, or proxies."),
    "plugin": ("cli.commands.plugin_cmd:plugin", "Manage SAM plugins: create, add components, and build."),
    "eval":   ("cli.commands.eval_cmd:eval_cmd", "Run an evaluation suite using a specified configuration file."),
    "docs":   ("cli.commands.docs_cmd:docs",     "Starts a web server to view the documentation."),
    "tools":  ("cli.commands.tools_cmd:tools",   "Manage and explore SAM built-in tools."),
    "task":   ("cli.commands.task_cmd:task",      "Send tasks to the webui gateway and receive streaming responses."),
}


def _get_version_info():
    """Get version information for solace-agent-mesh and enterprise package if installed."""
    version_lines = [f"solace-agent-mesh: {__version__}"]
    try:
        enterprise_version = version('solace-agent-mesh-enterprise')
        version_lines.append(f"solace-agent-mesh-enterprise: {enterprise_version}")
    except PackageNotFoundError:
        pass
    return "\n".join(version_lines)


def _version_callback(ctx, param, value):
    """Callback for --version flag."""
    if not value or ctx.resilient_parsing:
        return
    click.echo(_get_version_info())
    ctx.exit()


@click.group(cls=LazyGroup, lazy_commands=_COMMANDS, context_settings=dict(help_option_names=['-h', '--help']))
@click.option(
    '-v', '--version',
    is_flag=True,
    callback=_version_callback,
    expose_value=False,
    is_eager=True,
    help="Show the CLI version and exit."
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


def main():
    cli()


if __name__ == "__main__":
    main()
