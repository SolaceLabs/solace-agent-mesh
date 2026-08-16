import click

from ...lazy_group import LazyGroup

_SUBCOMMANDS = {
    "agent":   ("cli.commands.add_cmd.agent_cmd:add_agent",     "Create a new agent from a template."),
    "gateway": ("cli.commands.add_cmd.gateway_cmd:add_gateway", "Create a new gateway from a template."),
    "proxy":   ("cli.commands.add_cmd.proxy_cmd:add_proxy",     "Create a new proxy from a template."),
}


@click.group(name="add", cls=LazyGroup, lazy_commands=_SUBCOMMANDS)
def add():
    """
    Creates templates for agents, gateways, or proxies.
    """
    pass
