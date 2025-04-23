import click
import os

from cli.config import Config
from cli.utils import load_template
from cli.utils import log_error, ask_question


DEFAULT_DESCRIPTION = "A solace-agent-mesh plugin project."
DEFAULT_AUTHOR = "Author Name"
EMPTY_FILE_MSG = ""

def create_command(
    path: str, description: str = None, author: str = None, skip: bool = False
):
    """Initializes and creates a new solace-agent-mesh plugin project.

    Project structure:

    plugin-name/
    ├─ configs/
    │  ├─ overwrite/
    ├─ src/
    │  ├─ __init__.py
    │  ├─ agents/
    │  │  ├─ __init__.py
    │  ├─ gateways/
    │  │  ├─ __init__.py
    ├─ interfaces/
    ├─ solace-agent-mesh-plugin.yaml
    ├─ .gitignore
    ├─ pyproject.toml
    ├─ README.md

    """
    if not skip:
        if not path:
            path = ask_question("Plugin name (A path if it shouldn't be created in the current directory)")
        if not description:
            description = ask_question("Plugin description", "")
        if not author:
            author = ask_question("Plugin author", "")
    if not path:
        log_error("Plugin name is required.")
        return 1
    click.echo(f"Creating solace-agent-mesh plugin '{path}'.")

    # Create the plugin directory
    click.echo("Creating plugin directory...")
    os.makedirs(path, exist_ok=True)

    # Check into the plugin directory
    os.chdir(path)

    # Get the directory base name
    name = str(os.path.basename(path))

    config = Config.get_default_plugin_config()
    config["solace_agent_mesh_plugin"]["name"] = name

    # Write the plugin config file
    Config.write_config(config, Config.user_plugin_config_file)

    # Create the .gitignore file
    ignore_files = ["*.pyc", "__pycache__", "*.egg-info", "dist"]
    with open(".gitignore", "w", encoding="utf-8") as f:
        f.write("\n".join(ignore_files))

    # Create README.md
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(f"# {name.upper()}\n\n{description or DEFAULT_DESCRIPTION}")

    # Create directories and __init__.py files
    py_paths = ["agents", "gateways"]
    py_paths = [os.path.join("src", path) for path in py_paths]
    directories = [
        "interfaces",
        "configs",
        "src",
        os.path.join("configs", "overwrite"),
    ] + py_paths

    for path in directories:
        os.makedirs(path, exist_ok=True)

    for py_path in py_paths:
        with open(os.path.join(py_path, "__init__.py"), "w", encoding="utf-8") as f:
            f.write("")

    with open(os.path.join("configs", ".gitkeep"), "w", encoding="utf-8") as f:
        f.write(EMPTY_FILE_MSG)

    with open(os.path.join("interfaces", ".gitkeep"), "w", encoding="utf-8") as f:
        f.write(EMPTY_FILE_MSG)

    with open(os.path.join("src", "__init__.py"), "w", encoding="utf-8") as f:
        f.write('__version__ = "0.0.1"\n')

    # Create pyproject.toml
    pyproject = load_template("plugin-pyproject.toml")
    pyproject = (pyproject
        .replace("{{name}}", name)
        .replace("{{snake_name}}", name.replace("-", "_"))
        .replace("{{description}}", description or DEFAULT_DESCRIPTION)
        .replace("{{author}}", author or DEFAULT_AUTHOR)
    )

    with open("pyproject.toml", "w", encoding="utf-8") as f:
        f.write(pyproject)

    click.echo(f"Plugin project '{name}' was created successfully.")
    click.echo(
        click.style(f"\tUse `cd {name}` to check into project.", fg="blue")
    )
    click.echo(
        click.style("\tUse `solace-agent-mesh add` to add agents and gateways.", fg="blue")
    )
