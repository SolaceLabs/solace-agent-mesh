import os
import sys
from pathlib import Path

def write_agent_file(
    agent_name: str, file_type: str, content: str, action_file_name: str = None
) -> Path:
    """
    Write content to an existing agent file based on agent name and file type.
    Will not create new files, only update existing ones.

    Args:
        agent_name: Name of the agent
        file_type: Type of file to write ("agent_config", "agent_main", "agent_action")
        content: The content to write to the file
        action_file_name: Optional name of the action file (without .py extension) when file_type is "agent_action"

    Returns:
        The path of the written file

    Raises:
        FileNotFoundError: If the file or its parent directories don't exist
        ValueError: If the file type is unknown
    """

    current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    project_root = current_dir.parent.parent

    if file_type == "agent_config":
        file_path = project_root / "configs" / "agents" / f"{agent_name}.yaml"
    elif file_type == "agent_main":
        file_path = (
            project_root
            / "modules"
            / "agents"
            / agent_name
            / f"{agent_name}_agent_component.py"
        )
    elif file_type == "agent_action":
        actions_dir = project_root / "modules" / "agents" / agent_name / "actions"

        # If specific action file is provided, use it
        if action_file_name:
            file_path = actions_dir / f"{action_file_name}.py"
        else:
            # Find the first .py file that's not __init__.py
            py_files = [f for f in actions_dir.glob("*.py") if f.name != "__init__.py"]
            if not py_files:
                raise FileNotFoundError(f"No action files found in: {actions_dir}")
            file_path = py_files[0]
    else:
        raise ValueError(f"Unknown file type: {file_type}")

    # Check if file exists
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Check if parent directory exists
    if not file_path.parent.exists():
        raise FileNotFoundError(f"Directory not found: {file_path.parent}")

    # Write content to file
    with open(file_path, "w") as file:
        file.write(content)

    print(f"Written content to: {file_path}")
    return file_path
