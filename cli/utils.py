import os
from pathlib import Path
import importlib
import click
import re


def ask_yes_no_question(question: str, default=False) -> bool:
    """Ask a yes/no question and return the answer."""
    return click.confirm(question, default=default)


def ask_question(
    question: str, default=None, hide_input=False, type=None, show_choices=None
) -> str:
    """General purpose question asking function."""
    return click.prompt(
        question,
        default=default,
        hide_input=hide_input,
        type=type,
        show_choices=show_choices,
    )


def ask_if_not_provided(
    options: dict,
    key: str,
    question: str,
    default=None,
    none_interactive: bool = False,
    choices: list | None = None,
    hide_input: bool = False,
    is_bool: bool = False,
    type=None,
):
    """
    Ask a question if the key is not in options or its value is None.
    Updates the options dictionary with the answer and returns the answer.
    """
    if key not in options or options[key] is None:
        if none_interactive:
            options[key] = default
        elif is_bool:
            options[key] = ask_yes_no_question(
                question, default=default if isinstance(default, bool) else False
            )
        elif choices:
            choice_type = click.Choice(choices)
            options[key] = ask_question(
                question, default=default, type=choice_type, show_choices=True
            )
        else:
            options[key] = ask_question(
                question, default=default, hide_input=hide_input, type=type
            )
    return options.get(key)


def get_cli_root_dir():
    """Get the path to the CLI root directory."""
    # Get the directory of the current script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Construct the root directory
    return Path(os.path.normpath(os.path.join(current_dir, "..")))


def load_template(name, parser=None, *args):
    """Load a template file

    Args:
        name (str): The name of the template file to load.
        parser (callable, optional): A function to parse the file content. Defaults to None.
        *args: Additional arguments to pass to the parser function.
    Returns:
        str: The content of the template file, formatted with the provided parser."""
    template_file = os.path.normpath(
        os.path.join(get_cli_root_dir(), "templates", name)
    )

    if not os.path.exists(template_file):
        raise FileNotFoundError(f"Template file '{template_file}' does not exist.")

    with open(template_file, "r", encoding="utf-8") as f:
        if parser:
            file = parser(f.read(), *args)
        else:
            file = f.read()

    return file


def get_formatted_names(name: str):
    # Normalize the name
    parts = [
        segment
        for segment in re.split(
            r"[\s_-]", re.sub(r"(?<!^)(?=[A-Z])", "_", name.strip()).lower()
        )
        if segment
    ]
    return {
        "KEBAB_CASE_NAME": "-".join([word.lower() for word in parts]),
        "PASCAL_CASE_NAME": "".join([word.capitalize() for word in parts]),
        "SNAKE_CASE_NAME": "_".join([word.lower() for word in parts]),
        "SNAKE_UPPER_CASE_NAME": "_".join([word.upper() for word in parts]),
        "SPACED_NAME": " ".join(parts),
        "SPACED_CAPITALIZED_NAME": " ".join([word.capitalize() for word in parts]),
    }


def get_module_path(name):
    """Get the path to a module by name.

    Args:
        name (str): The name of the module to load.

    Returns:
        module_path: The path to the module.
    """
    module = importlib.import_module(name)
    module_path = module.__path__[0]
    return module_path


def error_exit(message: str = None, exit_code: int = 1):
    """Prints an error message and exits with the specified code."""
    if message:
        click.echo(click.style(message, fg="red"), err=True)
    raise click.Abort(exit_code)


def get_sam_cli_home_dir() -> Path:
    """
    Determines the SAM CLI home directory.
    Uses SAM_CLI_HOME env var if set, otherwise defaults to '.sam' in the current working directory.
    Ensures the directory exists.
    """
    env_path_str = os.environ.get("SAM_CLI_HOME")
    sam_home_path: Path

    if env_path_str:
        path_from_env = Path(env_path_str)
        if path_from_env.is_absolute():
            sam_home_path = path_from_env
        else:
            sam_home_path = Path.cwd() / path_from_env
    else:
        sam_home_path = Path.cwd() / ".sam"

    try:
        sam_home_path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        error_exit(
            f"Error: Could not create or access SAM_CLI_HOME directory at '{sam_home_path}'.\nDetails: {e}"
        )

    return sam_home_path.resolve()


def indent_multiline_string(
    text: str, indent: int = 4, initial_indent: bool = False
) -> str:
    """
    Indents a multiline string by a specified number of spaces.

    Args:
        text (str): The multiline string to indent.
        indent (int): The number of spaces to indent each line.

    Returns:
        str: The indented multiline string.
    """
    indentation = " " * indent
    if initial_indent:
        return (
            "\n"
            + indentation
            + "\n".join(indentation + line for line in text.splitlines()).lstrip()
        )
    else:
        return "\n".join(indentation + line for line in text.splitlines()).lstrip()
