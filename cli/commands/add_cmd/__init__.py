import click
from .agent_cmd import add_agent
from .gateway_cmd import add_gateway
from .proxy_cmd import add_proxy


@click.group(name="add")
def add():
    """
    Creates templates for agents, gateways, or proxies.
    """
    pass


add.add_command(add_agent, name="agent")
add.add_command(add_gateway, name="gateway")
add.add_command(add_proxy, name="proxy")
