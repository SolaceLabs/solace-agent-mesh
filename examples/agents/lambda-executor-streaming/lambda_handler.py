"""
Lambda handler for the streaming example.

This creates a FastAPI app that wraps the slow_process tool for execution
via AWS Lambda Web Adapter with response streaming.
"""

from sam_lambda_tools import LambdaToolHandler
from tool import slow_process

# Create the handler and FastAPI app
handler = LambdaToolHandler(slow_process)
app = handler.create_fastapi_app()
