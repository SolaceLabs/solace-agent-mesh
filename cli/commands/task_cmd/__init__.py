"""
CLI commands for sending tasks to the webui gateway.
"""
import click

from .send import send_task


@click.group("task")
def task():
    """Send tasks to the webui gateway and receive streaming responses."""
    pass


task.add_command(send_task, name="send")
