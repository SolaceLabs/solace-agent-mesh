import click
import multiprocessing
from solace_agent_mesh.config_portal.backend.server import run_flask

def web_init_step(options, default_options, none_interactive, abort):
    if not none_interactive:
        with multiprocessing.Manager() as manager:
            # Create a shared configuration dictionary
            shared_config = manager.dict()
            
            # Start the Flask server with the shared config
            init_gui_process = multiprocessing.Process(
                target=run_flask,
                args=("127.0.0.1", 5002, shared_config)
            )
            init_gui_process.start()

            click.echo(click.style("Web configuration portal is running at http://127.0.0.1:5002", fg="green"))
            click.echo("Complete the configuration in your browser to continue...")

            # Wait for the Flask server to finish
            init_gui_process.join()
            
            # Get the configuration from the shared dictionary
            if shared_config:
                # Convert from manager.dict to regular dict
                config_from_portal = dict(shared_config)
                options.update(config_from_portal)
                click.echo(click.style("Configuration received from portal", fg="green"))

            else:
                abort("Web configuration failed, please try again.")