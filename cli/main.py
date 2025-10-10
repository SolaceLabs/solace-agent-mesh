import click
import os
import sys

from cli.lazy_group import LazyGroup

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))

from cli import __version__

@click.group(context_settings=dict(help_option_names=['-h', '--help']),
             cls=LazyGroup,
             lazy_subcommands={
                 "init": "cli.commands.init_cmd.init",
                 "run": "cli.commands.run_cmd.run",
                 "add": "cli.commands.add_cmd.add",
                 "plugin": "cli.commands.plugin_cmd.plugin",
                 "eval": "cli.commands.eval_cmd.eval_cmd",
                 "docs": "cli.commands.docs_cmd.docs"
             })
@click.version_option(
    __version__, "-v", "--version", help="Show the CLI version and exit."
)
def cli():
    """Solace CLI Application"""
    pass



def main():
    cli()


if __name__ == "__main__":
    main()
