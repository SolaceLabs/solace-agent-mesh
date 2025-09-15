import click

from .create_cmd import create_plugin_cmd
from .install_cmd import install_plugin_cmd
from .add_cmd import add_plugin_component_cmd
from .build_cmd import build_plugin_cmd
from .catalog_cmd import catalog


@click.group("plugin")
def plugin():
    """Manage SAM plugins: create, add components, and build."""
    pass


plugin.add_command(create_plugin_cmd, name="create")
plugin.add_command(install_plugin_cmd, name="install")
plugin.add_command(add_plugin_component_cmd, name="add")
plugin.add_command(build_plugin_cmd, name="build")
plugin.add_command(catalog, name="catalog")
