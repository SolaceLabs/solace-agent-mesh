"""
Lambda handler for the streaming example.

This creates a FastAPI app that wraps the analyze_document tool for execution
via AWS Lambda Web Adapter with response streaming.
"""

from sam_lambda_tools import LambdaToolHandler
from tool import analyze_document

# Create the handler and FastAPI app
handler = LambdaToolHandler(analyze_document)
app = handler.create_fastapi_app()
