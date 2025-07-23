import click
from .agent_cmd import add_agent
from .gateway_cmd import add_gateway


@click.group(name="add")
def add():
    """
    Creates templates for agents or gateways.
    """
    pass


add.add_command(add_agent, name="agent")
add.add_command(add_gateway, name="gateway")
