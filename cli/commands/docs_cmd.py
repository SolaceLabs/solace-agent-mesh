import click
import http.server
import socketserver
import webbrowser
import os
from cli.utils import get_cli_root_dir, error_exit

class DocsHttpRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=kwargs.pop('directory'), **kwargs)

    def do_GET(self):
        if self.path.startswith('/solace-agent-mesh'):
            self.path = self.path[len('/solace-agent-mesh'):] or '/'
        super().do_GET()

    def send_error(self, code, message=None):
        if code == 404:
            self.send_response(302)
            self.send_header('Location', '/solace-agent-mesh/docs/documentation/getting-started/introduction/')
            self.end_headers()
        else:
            super().send_error(code, message)

@click.command(name="docs")
@click.option(
    "-p",
    "--port",
    "port",
    default=8585,
    help="Port to run the documentation server on.",
    type=int,
)
def docs(port: int):
    """
    Starts a web server to view the documentation.
    """
    prod_docs_dir = os.path.join(get_cli_root_dir(), 'assets', 'docs')
    dev_docs_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'docs', 'build')

    if os.path.exists(prod_docs_dir):
        docs_dir = prod_docs_dir
    elif os.path.exists(dev_docs_dir):
        docs_dir = dev_docs_dir
        click.echo("Serving development documentation")
    else:
        docs_dir = None
        error_exit("Documentation directory not found. Please build the documentation first.")

    def handler(*args, **kwargs):
        return DocsHttpRequestHandler(*args, directory=docs_dir, **kwargs)

    with socketserver.TCPServer(("", port), handler) as httpd:
        url = f"http://localhost:{port}/solace-agent-mesh/docs/documentation/getting-started/introduction/"
        click.echo(f"Starting documentation server on {url}")
        webbrowser.open_new_tab(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            click.echo("\nShutting down documentation server...")
