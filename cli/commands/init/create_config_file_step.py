import click

from cli.config import Config


def create_config_file_step(options, default_options, none_interactive, abort):
    """
    Creates the configuration files.
    """
    # Populate options dictionary with default values, for non specified options
    for key, value in default_options.items():
        if key not in options or options[key] is None:
            options[key] = value
    
    sam_config = Config.get_default_config()

    # Set up the built-in agents
    builtin_agents_ref = (
        sam_config.get("solace_agent_mesh", {}).get("built_in", {}).get("agents", [])
    )
    builtin_agents = options.get("built_in_agent", [])
    for agent in builtin_agents_ref:
        agent["enabled"] = agent["name"] in builtin_agents or agent["name"] == "global"

    # Set up the project structure
    sam_config.get("solace_agent_mesh", {})["config_directory"] = options.get("config_dir")
    sam_config.get("solace_agent_mesh", {})["modules_directory"] = options.get("module_dir")
    sam_config.get("solace_agent_mesh", {})["env_file"] = options.get("env_file")
    sam_config.get("solace_agent_mesh", {}).get("build", {})["build_directory"] = (
        options.get("build_dir")
    )

    # Set up the file service
    file_service_ref = (
        sam_config.get("solace_agent_mesh", {})
        .get("runtime", {})
        .get("services", {})
        .get("file_service", {})
    )
    provider = options.get("file_service_provider")
    file_service_ref["type"] = provider
    if "config" not in file_service_ref:
        file_service_ref["config"] = {}
    if provider not in file_service_ref["config"]:
        file_service_ref["config"][provider] = {}
    for pair in options.get("file_service_config", []):
        if "=" not in pair:
            continue
        key, value = pair.split("=")
        file_service_ref["config"][provider][key] = value

    Config.write_config(sam_config)
    click.echo("Project files have been created.")

    #update context (this is needed for add_gateway_command to work properly in the next step)
    ctx = click.get_current_context()
    ctx.obj['solace_agent_mesh'] = sam_config['solace_agent_mesh']
