# tests/config_portal_e2e/conftest.py
import pytest
import multiprocessing
import time
import os
import sys
import builtins
import click
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

# Check if .env.test exists
ENV_TEST_EXISTS = os.path.exists(".env.test")

@pytest.fixture(scope="session")
def config_portal():
    """Start the config portal server and provide access to the shared config"""
    with multiprocessing.Manager() as manager:
        shared_config = manager.dict()
        
        # Import the Flask server function
        from solace_agent_mesh.config_portal.backend.server import run_flask
        
        # Start the server process
        server_process = multiprocessing.Process(
            target=run_flask,
            args=("127.0.0.1", 5002, shared_config)
        )
        server_process.start()
        
        # Wait for server to start
        time.sleep(2)
        
        # Yield both the URL and the shared config
        yield {
            "url": "http://127.0.0.1:5002",
            "shared_config": shared_config
        }
        
        # Clean up
        server_process.terminate()
        server_process.join(timeout=5)
        if server_process.is_alive():
            server_process.kill()

@pytest.fixture
def page(config_portal):
    """Provide a Playwright page connected to the config portal"""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        page = context.new_page()
        page.goto(config_portal["url"])
        yield page
        context.close()
        browser.close()

@pytest.fixture
def api_keys():
    """
    Provide API keys from .env.test or mocked values
    """
    keys = {}
    # If .env.test exists, load real keys
    if ENV_TEST_EXISTS:
        load_dotenv(".env.test", override=True)
        
        # Replace with real keys if available
        openai_key = os.environ.get("OPENAI_KEY") or os.environ.get("OPENAI_API_KEY")
        if openai_key:
            keys["openai_key"] = openai_key
            
        anthropic_key = os.environ.get("ANTHROPIC_KEY") or os.environ.get("ANTHROPIC_API_KEY")
        if anthropic_key:
            keys["anthropic_key"] = anthropic_key
    else:
        raise EnvironmentError(
            "No .env.test file found. Please create one with the necessary API keys."
        )
    
    return keys

# @pytest.fixture
# def tmp_test_dir(tmp_path):
#     """Create and use a temporary directory for the test"""
#     original_dir = os.getcwd()
#     os.chdir(tmp_path)
    
#     yield tmp_path
    
#     # Go back to original directory
#     os.chdir(original_dir)

# @pytest.fixture
# def mock_file_operations(monkeypatch, tmp_test_dir):
#     """Mock file operations to use the test directory"""
#     # Store original functions
#     original_open = builtins.open
#     original_exists = os.path.exists
    
#     # Track files for verification
#     created_files = []
    
#     def mock_open(file_path, *args, **kwargs):
#         # For absolute paths or special files, use original open
#         if file_path.startswith('/'):
#             return original_open(file_path, *args, **kwargs)
        
#         # For relative paths, use the test directory
#         test_path = tmp_test_dir / file_path
#         test_path.parent.mkdir(parents=True, exist_ok=True)
#         created_files.append(str(test_path))
#         return original_open(test_path, *args, **kwargs)
    
#     def mock_exists(file_path):
#         # For absolute paths, use original exists
#         if file_path.startswith('/'):
#             return original_exists(file_path)
        
#         # For relative paths, check in test directory
#         test_path = tmp_test_dir / file_path
#         return test_path.exists()
    
#     # Apply mocks
#     monkeypatch.setattr(builtins, "open", mock_open)
#     monkeypatch.setattr(os.path, "exists", mock_exists)
    
#     return {"path": tmp_test_dir, "files": created_files}
