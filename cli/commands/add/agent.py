import os
import click

from cli.utils import get_display_path, load_template, log_error, get_formatted_names


def add_agent_command(name):
    """
    Creates a template for an agent
    """
    # Name must be kebab-case, and only character, numbers, and hyphens are allowed
    if not name.islower() or not name.replace("-", "").isalnum():
        log_error(
            "Error: Name must be kebab-case. Only lowercase letters, numbers, and hyphens are allowed.",
        )
        return 1

    formatted_name = get_formatted_names(name)

    try:
        # Load the template file
        template_file = load_template("agent.yaml", formatted_name)
        if template_file is None:
            log_error("Error: Template file for agent not found.")
            return 1
    except IOError as e:
        log_error(f"Error reading template file: {e}")
        return 1

    config = click.get_current_context().obj
    config_directory = config["solace_agent_mesh"]["config_directory"]

    try:
        file_name = f"{formatted_name['SNAKE_CASE_NAME']}.yaml"
        directory = os.path.join(config_directory, "agents")
        path = os.path.join(directory, file_name)

        # Check if the file already exists
        if os.path.exists(path):
            overwrite = click.confirm(
                f"File {path} already exists. Do you want to overwrite it?",
                default=False,
            )
            if not overwrite:
                click.echo("Template not created.")
                return

        # Create the directory if it doesn't exist
        os.makedirs(directory, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(template_file)
    except IOError as e:
        log_error(f"Error creating template: {e}")
        return 1

    click.echo(f"Created agent template at: {get_display_path(path)}")

    try:
        # Creating the agent file
        agent_directory = os.path.join(
            config["solace_agent_mesh"]["modules_directory"],
            "agents",
            formatted_name["SNAKE_CASE_NAME"],
        )
        # Create the agent directory
        os.makedirs(agent_directory, exist_ok=True)
        # Create the __init__.py file
        init_file = os.path.join(agent_directory, "__init__.py")
        if not os.path.exists(init_file):
            with open(init_file, "w", encoding="utf-8") as f:
                f.write("")

        # Create the agent python file
        agent_path = os.path.join(
            agent_directory,
            f"{formatted_name['SNAKE_CASE_NAME']}_agent_component.py",
        )
        agent_template = load_template("agent.py", formatted_name)
        if not os.path.exists(agent_path):
            with open(agent_path, "w", encoding="utf-8") as f:
                f.write(agent_template)

        click.echo(
            f"Created agent at: {get_display_path(agent_path)}"
        )

        # Create the agent action
        action_directory = os.path.join(agent_directory, "actions")
        os.makedirs(action_directory, exist_ok=True)
        # Create the __init__.py file
        init_file = os.path.join(action_directory, "__init__.py")
        if not os.path.exists(init_file):
            with open(init_file, "w", encoding="utf-8") as f:
                f.write("")

        action_path = os.path.join(action_directory, "sample_action.py")
        action_template = load_template("action.py", formatted_name)
        if not os.path.exists(action_path):
            with open(action_path, "w", encoding="utf-8") as f:
                f.write(action_template)

        click.echo(f"Created sample action at: {get_display_path(action_path)}")

        temp_file = os.path.join(config_directory, ".gitkeep")
        if os.path.exists(temp_file):
            os.remove(temp_file)
    except IOError as e:
        log_error(f"Error creating agent, agent config was created: {e}")
        return 1

