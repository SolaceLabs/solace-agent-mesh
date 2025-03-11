from cli.utils import ask_if_not_provided


def builtin_agent_step(options, default_options, none_interactive, abort):
    """
    Initialize the built-in agent.
    """
    agents = {
        "web_request": (True, "can make queries to web to get real-time data", []),
        "image_processing": (
            True,
            "generate images from text or convert images to text (The model name should be formatted like provider/model-name)",
            ["IMAGE_GEN_ENDPOINT=", "IMAGE_GEN_API_KEY=", "IMAGE_GEN_MODEL=",],
        ),
    }

    env_vars = {}
    if "env_var" in options and options["env_var"]:
        env_var_list = list(options["env_var"])
        for env_var in env_var_list:
            if "=" in env_var:
                key, value = env_var.split("=")
                env_vars[key] = value

    if (
        "built_in_agent" in options
        and (
            isinstance(options["built_in_agent"], tuple)
            or isinstance(options["built_in_agent"], list)
        )
        and len(options["built_in_agent"]) > 0
    ):
        options["built_in_agent"] = list(options["built_in_agent"])
        # Update env vars with default values
        for name, agent in agents.items():
            if name in options["built_in_agent"]:
                for pair in agent[2]:
                    key, value = pair.split("=")
                    if key not in env_vars:
                        env_vars[key] = value
        options["env_var"] = [f"{key}={value}" for key, value in env_vars.items()]
        return

    if none_interactive:
        selected_agents_list = [
            agent for agent, (enabled, _, _), in agents.items() if enabled
        ]
        options["built_in_agent"] = selected_agents_list
        # Update env vars with default values
        for name, agent in agents.items():
            if name in options["built_in_agent"]:
                for pair in agent[2]:
                    key, value = pair.split("=")
                    if key not in env_vars:
                        env_vars[key] = value
        options["env_var"] = [f"{key}={value}" for key, value in env_vars.items()]
        return

    selected_agents = {}
    for agent, (default, description, pairs) in agents.items():
        enabled = ask_if_not_provided(
            selected_agents,
            agent,
            f"Enable {agent} agent: {description}",
            default,
            none_interactive,
        )
        if enabled:
            for pair in pairs:
                key, value = pair.split("=")
                ask_if_not_provided(
                    env_vars,
                    key,
                    f'\tAgent "{agent}" requires env value "{key}":',
                    value,
                    none_interactive,
                    hide_input="KEY" in key.upper(),
                )
    selected_agents_list = [
        agent for agent, enabled in selected_agents.items() if enabled
    ]
    options["built_in_agent"] = selected_agents_list
    options["env_var"] = [f"{key}={value}" for key, value in env_vars.items()]
