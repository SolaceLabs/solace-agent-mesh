import os
import re
import click
import importlib


def get_cli_root_dir():
    """Get the path to the CLI root directory."""
    # Get the directory of the current script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Construct the root directory
    return os.path.normpath(os.path.join(current_dir, ".."))


def merge_dicts(dict1, dict2):
    """Merge two dictionaries recursively."""
    for key, value in dict2.items():
        if key in dict1 and isinstance(dict1[key], dict) and isinstance(value, dict):
            merge_dicts(dict1[key], value)
        elif key in dict1 and isinstance(dict1[key], list) and isinstance(value, list):
            # set concat arrays
            dict1[key] = list(dict1[key] + value)
        else:
            # dict2 takes precedence
            dict1[key] = value
    return dict1


def remove_duplicate(array, id_fn):
    """Remove duplicates from an array based on a key function. Keeps the last occurrence."""
    seen = set()
    reversed_array = array[::-1]
    deduplicated_array = [
        x for x in reversed_array if not (id_fn(x) in seen or seen.add(id_fn(x)))
    ]
    return deduplicated_array[::-1]


def literal_format_template(template, literals):
    for key, value in literals.items():
        template = template.replace("{{" + key + "}}", value)
    return template


def load_template(name, format_pair={}, parser=None):
    """Load a template file and format it with the given key-value pairs."""
    # Construct the path to the template file using a relative path
    template_file = os.path.normpath(
        os.path.join(get_cli_root_dir(), "templates", name)
    )

    if not os.path.exists(template_file):
        return None

    with open(template_file, "r", encoding="utf-8") as f:
        if parser:
            file = parser(f)
        else:
            file = f.read()

    file = literal_format_template(file, format_pair)

    return file


def extract_yaml_env_variables(yaml_content):
    """Get environment variables from a yaml file.
    Env variables are annotated with the ${VAR}
    """
    return re.findall(r"\${(\w+)}", yaml_content)


def get_display_path(path):
    """Get the display path of a file path."""
    return path if os.path.isabs(path) else f"./{path}"


def log_error(message):
    click.echo(click.style(message, fg="red"), err=True)

def log_warning(message):
    click.echo(click.style(message, fg="yellow"), err=False)

def log_link(message):
    click.echo(click.style(message, fg="blue"), err=False)


def log_success(message):
    click.echo(click.style(message, fg="green"), err=False)


def ask_yes_no_question(question: str, default=False) -> bool:
    """Ask a yes/no question and return the answer."""
    return click.confirm(question, default=default)


def ask_question(question: str, default=None) -> str:
    """Ask a question and return the answer."""
    return click.prompt(question, default=default)


def ask_choice_question(question: str, choices: list, default=None) -> str:
    """Ask a choice question and return the answer."""
    return click.prompt(question, type=click.Choice(choices), default=default)


def ask_password(question: str, default=None) -> str:
    """Ask a password question and return the answer."""
    return click.prompt(question, default=default, hide_input=True)


def ask_if_not_provided(
    options,
    key,
    question,
    default=None,
    none_interactive=False,
    choices=None,
    hide_input=False,
):
    """
    Ask a question if the key is not in the options.
    Updates the options dictionary with the answer.
    Returns the answer.
    """
    if key not in options or options[key] is None:
        if none_interactive:
            options[key] = default
        elif choices:
            options[key] = ask_choice_question(question, choices, default=default)
        elif hide_input:
            options[key] = ask_password(question, default=default)
        elif isinstance(default, bool):
            options[key] = ask_yes_no_question(question, default=default)
        else:
            options[key] = ask_question(question, default=default)
    return options[key]


def apply_document_parsers(file_content, parsers, meta={}):
    for parser in parsers:
        file_content = parser(file_content, meta)
    return file_content


def load_plugin(name, return_path_only=False):
    """Load a plugin by name.

    Args:
        name (str): The name of the plugin to load.
        return_path_only (bool, optional): Whether to return only the path to the module.

    Returns:
        module: The loaded module.
        module_path: The path to the module. (Or only the path if return_path_only is True)
    """
    # Construct the path to the plugin directory using a relative path
    try:
        # Attempt to import the module
        module = importlib.import_module(name)
        module_path = module.__path__[0]
    except ImportError:
        if return_path_only:
            return None
        return None, None

    if return_path_only:
        return module_path

    return module, module_path


def get_formatted_names(name: str):
    name = name.strip()
    parts = re.split(r"[\s_-]", name)
    return {
        "KEBAB_CASE_NAME": "-".join([word.lower() for word in parts]),
        "HYPHENED_NAME": name,
        "CAMEL_CASE_NAME": "".join([word.capitalize() for word in parts]),
        "SNAKE_CASE_NAME": "_".join([word.lower() for word in parts]),
        "SPACED_NAME": " ".join(parts),
        "SNAKE_UPPER_CASE_NAME": "_".join([word.upper() for word in parts]),
    }


def find_last_list_item_indent(yaml_content):
    """
    Finds the indentation of the last list item
    Returns the number of spaces before the dash (-)
    """
    lines = yaml_content.splitlines()
    
    # Look for the last line starting with '-' by iterating in reverse
    for line in reversed(lines):
        stripped_line = line.lstrip()
        if stripped_line.startswith('-'):
            return len(line) - len(stripped_line)
    
    #default to 0
    return 0


def normalize_and_reindent_yaml(reference_yaml, yaml_content):
    """Given YAML content, adjust the indentation to the given target_dash_indent,
    while preserving the relative indentation of the content.
    """
    target_dash_indent = find_last_list_item_indent(reference_yaml)

    lines = yaml_content.splitlines()
    if not lines:
        return ""

    # Find the current dash indentation in the content
    current_dash_indent = None
    for line in lines:
        if line.lstrip().startswith('-'):
            current_dash_indent = len(line) - len(line.lstrip())
            break
    
    if current_dash_indent is None:
        current_dash_indent = 0

    # Calculate the indentation difference
    indent_difference = target_dash_indent - current_dash_indent

    # Apply the indentation difference to all lines
    reindented_lines = []
    for line in lines:
        if not line.strip():
            # Preserve empty lines
            reindented_lines.append(line)
        else:
            current_indent = len(line) - len(line.lstrip())
            #prevent negative indent
            new_indent = max(0, current_indent + indent_difference)
            reindented_lines.append(' ' * new_indent + line.lstrip())

    reindented_lines.append('\n')

    return '\n'.join(reindented_lines)

def get_all_cases(name: str):
    name = name.strip()
    parts = re.split(r"[\s_-]", name)
    return {
        "KEBAB_CASE": "-".join([word.lower() for word in parts]),
        "CAMEL_CASE": "".join([word.capitalize() for word in parts]),
        "SNAKE_CASE": "_".join([word.lower() for word in parts]),
        "SPACED": " ".join(parts),
        "SNAKE_UPPER_CASE": "_".join([word.upper() for word in parts]),
    }
