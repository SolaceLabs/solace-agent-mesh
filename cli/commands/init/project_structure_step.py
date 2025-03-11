from cli.utils import ask_if_not_provided


def project_structure_step(options, default_options, none_interactive, abort):
    """
    Initialize the project structure.
    """
    namespace = ask_if_not_provided(
        options,
        "namespace",
        "Enter a namespace for the project (It will be used as the topic prefix for all events.)",
        default_options["namespace"],
        none_interactive,
    )
    if namespace and not namespace.endswith("/"):
        options["namespace"] = f"{namespace}/"
