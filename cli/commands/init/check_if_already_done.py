import os

from cli.config import Config


def check_if_already_done(options, default_options, none_interactive, abort):
    """
    Checks if the init command has already been done"""
    config_path = Config.user_config_file
    if os.path.exists(config_path):
        abort(
            "The project has already been initialized. If you want to reinitialize the project, please delete the solace-agent-mesh.yaml file"
        )
