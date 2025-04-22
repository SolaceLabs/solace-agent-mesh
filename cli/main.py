import click
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))

from cli.config import Config
from cli.commands.config import config_command
from cli.commands.add import add_command
from cli.commands.build import build_command
from cli.commands.run import run_command
from cli.commands.visualizer import visualizer_command
from cli.commands.init import init_command
from cli.commands.plugin import plugin_command
from cli.commands.chat import chat_command
from cli import __version__

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(__version__)
@click.pass_context
@click.option(
    "-c",
    "--config-file",
    type=click.Path(),
    help="Path to solace-agent-mesh.yaml file. By default, it looks for the file in the current directory.",
)
def cli(ctx=None, config_file=None):
    """Solace Agent Mesh CLI application.

    This cli application can be used to create, build, and run Solace Agent Mesh systems.
    """
    try:
        ctx.obj = Config.get_config(config_file)
    except Exception as e:
        click.echo(f"Failed to load configurations: {e}")
        sys.exit(1)


@cli.group()
def add():
    """
    Creates a template for an agent or gateway.
    """
    pass


@cli.command()
@click.option(
    "-y", default=False, is_flag=True, help="Skip confirmation and build immediately."
)
@click.option(
    "-N",
    "--no-init",
    default=False,
    is_flag=True,
    help="Skip running the init command if not already run.",
)
def build(y, no_init):
    """Build the Solace Agent Mesh application."""
    return build_command(skip_without_asking=y, no_init=no_init)


@cli.command()
@click.option(
    "-u",
    "--use-system-env",
    default=False,
    is_flag=True,
    help="Use only system environment variables (ignore environment variables defined in the config).",
)
@click.option(
    "-s",
    "--skip",
    help="Exclude file from the list of files to run.",
    multiple=True,
)
@click.argument("files", nargs=-1, type=click.Path())
@click.option(
    "-q",
    "--quick-build",
    default=False,
    is_flag=True,
    help="Uses default behavior for init and build command if not have already been run.",
)
@click.option(
    "-i",
    "--ignore-build",
    default=False,
    is_flag=True,
    help="Skips running the build command if build directory does not exist. Mutally exclusive with --force-build.",
)
@click.option(
    "-b",
    "--force-build",
    default=False,
    is_flag=True,
    help="Runs the build command first regardless of the build directory. Mutually exclusive with --ignore-build.",
)
def run(use_system_env, files, skip, quick_build, ignore_build, force_build):
    """Run the Solace Agent Mesh application.

    FILES: Config files to run. Uses all the yaml files in the build directory if not provided.
    """
    return run_command(
        use_system_env, list(files), list(skip), quick_build, ignore_build, force_build
    )


@cli.command()
def config():
    """Update the config file with newly added default settings."""
    return config_command()


@cli.command()
@click.option(
    "-p", "--port", default=8080, help="Port number to run the visualizer on."
)
@click.option(
    "-f",
    "--find-unused-port",
    default=False,
    is_flag=True,
    help="If port is in use, Uses the next available port.",
)
@click.option(
    "-h",
    "--host",
    default=False,
    is_flag=True,
    help="Expose the visualizer to the network.",
)
@click.option(
    "-e",
    "--use-env",
    default=False,
    is_flag=True,
    help="Loads the environment variables file defined in the config.",
)
def visualize(port, find_unused_port, host, use_env):
    """Runs a web GUI visualizer for inspecting stimuli inside the solace agent mesh."""
    return visualizer_command(port, find_unused_port, host, use_env)


@cli.command()
@click.option(
    "--skip",
    is_flag=True,
    default=False,
    help="Non-interactive mode. Skip all the prompts, Uses provided options and default values.",
)
@click.option(
    "--use-web-based-init",
    is_flag=True,
    default=False,
    help="Launch the browser-based initialization interface directly, skipping the prompt.",
)
@click.option(
    "--namespace",
    help="project namespace",
)
@click.option(
    "--config-dir",
    help="base directory for config files",
)
@click.option(
    "--module-dir",
    help="base directory for python modules",
)
@click.option(
    "--build-dir",
    help="base directory for the build output",
)
@click.option(
    "--env-file",
    help="environment file path",
)
@click.option(
    "--broker-type",
    help="broker type to use (container, solace, dev_broker)",
)
@click.option(
    "--broker-url",
    help="Solace broker url endpoint",
)
@click.option(
    "--broker-vpn",
    help="Solace broker vpn name",
)
@click.option(
    "--broker-username",
    help="Solace broker username",
)
@click.option(
    "--broker-password",
    help="Solace broker password",
)
@click.option(
    "--container-engine",
    help="container engine to use (podman, docker)",
)
@click.option(
    "--llm-model-name",
    help="LLM model name to use",
)
@click.option(
    "--llm-endpoint-url",
    help="LLM endpoint URL",
)
@click.option(
    "--llm-api-key",
    help="LLM API Key",
)
@click.option(
    "--embedding-model-name",
    help="Embedding model name to use (only used if embedding service is enabled)",
)
@click.option(
    "--embedding-endpoint-url",
    help="Embedding endpoint URL (only used if embedding service is enabled)",
)
@click.option(
    "--embedding-api-key",
    help="Embedding API Key (only used if embedding service is enabled)",
)
@click.option(
    "--embedding-service-enabled",
    is_flag=True,
    default=None,
    help="Enable/disable Embedding Service for vector embeddings",
)
@click.option(
    "--built-in-agent",
    help="Built-in agents to use, multiple values can be provided (global, image_processing, ...)",
    multiple=True,
)
@click.option(
    "--file-service-provider",
    help="File service provider to use (volume, bucket)",
)
@click.option(
    "--file-service-config",
    help="Key value pairs for file service configuration (eg directory=/path/to/volume)",
    multiple=True,
)
@click.option(
    "--env-var",
    help="Adds Key value pairs to the env file (eg key=value)",
    multiple=True,
)
@click.option(
    "--rest-api-enabled",
    is_flag=True,
    default=None,
    help="Enable/disable REST API Interface",
)
@click.option(
    "--rest-api-server-input-port",
    help="REST API server port",
)
@click.option(
    "--rest-api-server-host",
    help="REST API server host",
)
@click.option(
    "--rest-api-server-input-endpoint",
    help="REST API endpoint",
)
@click.option(
    "--rest-api-gateway-name",
    help="Name for the REST API gateway",
)
@click.option(
    "--webui-enabled",
    is_flag=True,
    default=None,
    help="Enable/disable Web UI",
)
@click.option(
    "--webui-listen-port",
    help="Web UI server listen port",
)
@click.option(
    "--webui-host",
    help="Web UI server host",
)
def init(**kwargs):
    """
    Initialize the Solace Agent Mesh application.
    """
    return init_command(kwargs)


@cli.group()
def plugin():
    """Manage plugins - Create, build, add, and remove plugins."""
    pass


@cli.group()
def chat():
    """Start chatting with the Solace Agent Mesh application."""
    pass


def main():
    add_command(add)
    plugin_command(plugin)
    chat_command(chat)
    cli()


if __name__ == "__main__":
    main()
