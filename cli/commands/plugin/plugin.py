import click

from cli.utils import log_error
from .add import add_command
from .remove import remove_command
from .create import create_command
from .build import build_command


def plugin_command(plugin):

    @plugin.command()
    @click.option(
        "-n",
        "--name",
        help="Plugin name. (A path if it shouldn't be created in the current directory)",
    )
    @click.option(
        "-d",
        "--description",
        help="Plugin description.",
    )
    @click.option(
        "-a",
        "--author",
        help="Plugin author.",
    )
    @click.option(
        "-s",
        "--skip",
        is_flag=True,
        help="Skip the prompts and use the default values. (Name is required)",
    )
    def create(name, description, author, skip):
        """Initializes and creates a new solace-agent-mesh plugin project."""
        create_command(name, description, author, skip)

    @plugin.command()
    def build():
        """Build the solace-agent-mesh plugin project."""
        build_command()

    @plugin.command()
    @click.argument("name")
    @click.option("--add-all", is_flag=True, help="Added the plugin with default of loading all exported files from the plugin")
    @click.option("--pip", is_flag=True, help="Install with pip.")
    @click.option("--uv", is_flag=True, help="Install with uv pip.")
    @click.option("--poetry", is_flag=True, help="Install with poetry.")
    @click.option("--conda", is_flag=True, help="Install with conda.")
    @click.option(
        "-u",
        "--from-url",
        help="Install the plugin from a the given URL instead of the given name. (URL can be a file path or a git URL)",
    )
    def add(name, add_all, uv, pip, poetry, conda, from_url):
        """
        Add a new plugin to solace-agent-mesh config yaml.
        Optional install the module if not found.

        Only one installation method can be selected at a time.
        """
        # Only one option can be true at a time
        if sum([uv, pip, poetry, conda]) > 1:
            log_error("Only one installation method can be selected.")
            return 1
        installer = (
            "uv" if uv 
            else "pip" if pip 
            else "poetry" if poetry 
            else "conda" if conda 
            else None
        )
        return add_command(name, installer, from_url, add_all)

    @plugin.command()
    @click.argument("name")
    @click.option(
        "--pip-uninstall",
        default=False,
        is_flag=True,
        help="Removes the plugin module using pip",
    )
    @click.option(
        "--uv-uninstall",
        default=False,
        is_flag=True,
        help="Removes the plugin module using uv.",
    )
    @click.option(
        "--poetry-uninstall",
        default=False,
        is_flag=True,
        help="Removes the plugin module using poetry",
    )
    @click.option(
        "--conda-uninstall",
        default=False,
        is_flag=True,
        help="Removes the plugin module using conda",
    )
    def remove(name, pip_uninstall, uv_uninstall, poetry_uninstall, conda_uninstall):
        """
        Remove a plugin by removing it from solace-agent-mesh config yaml
        Optionally uninstall the module.

        Only one uninstallation method can be selected at a time.
        """
        # Only one option can be true at a time
        if sum([pip_uninstall, uv_uninstall, poetry_uninstall, conda_uninstall]) > 1:
            log_error("Only one uninstallation method can be selected.")
            return 1

        installer = (
            "pip"
            if pip_uninstall
            else "uv"
            if uv_uninstall
            else "poetry"
            if poetry_uninstall
            else "conda"
            if conda_uninstall
            else None
        )
        return remove_command(name, installer)
