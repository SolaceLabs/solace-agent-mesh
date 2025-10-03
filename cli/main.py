import click
import os
import sys
import importlib

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))

from cli import __version__


class LazyCommand(click.Command):
    """A command that imports its callback lazily when invoked"""

    def __init__(self, name, module_path, command_name, **kwargs):
        self.module_path = module_path
        self.command_name = command_name
        self._original_command = None
        super().__init__(name, callback=self._lazy_callback, **kwargs)

    def _lazy_callback(self, *args, **kwargs):
        """Load the actual command on first invocation"""
        if self._original_command is None:
            try:
                module = importlib.import_module(self.module_path)
                self._original_command = getattr(module, self.command_name)
            except (ImportError, AttributeError) as e:
                click.echo(f"Error loading command {self.name}: {e}", err=True)
                sys.exit(1)

        # Get the context and invoke the original command
        ctx = click.get_current_context()
        return ctx.invoke(self._original_command, *args, **kwargs)

    def get_help(self, ctx):
        """Load command to get help text"""
        if self._original_command is None:
            try:
                module = importlib.import_module(self.module_path)
                self._original_command = getattr(module, self.command_name)
            except (ImportError, AttributeError):
                return "Help unavailable - command failed to load"

        return self._original_command.get_help(ctx)


@click.group()
@click.version_option(
    __version__, "-v", "--version", help="Show the CLI version and exit."
)
def cli():
    """Solace CLI Application"""
    pass


# Add lazy-loaded commands
cli.add_command(LazyCommand("init", "cli.commands.init_cmd", "init"))
cli.add_command(LazyCommand("run", "cli.commands.run_cmd", "run"))
cli.add_command(LazyCommand("add", "cli.commands.add_cmd", "add"))
cli.add_command(LazyCommand("plugin", "cli.commands.plugin_cmd", "plugin"))
cli.add_command(LazyCommand("eval", "cli.commands.eval_cmd", "eval_cmd"))
cli.add_command(LazyCommand("docs", "cli.commands.docs_cmd", "docs"))


def main():
    cli()


if __name__ == "__main__":
    main()
