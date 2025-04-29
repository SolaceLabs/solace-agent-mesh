import re
from playwright.sync_api import Page, expect
import os
import pytest
from time import sleep
import pprint
import json

pytestmark = pytest.mark.skipif(
    not os.path.exists(".env.test"),
    reason="These tests require .env.test with real API keys"
)

def test_initialization_flow(page, config_portal):
    """Test the initialization flow with input tracking for verification"""
    # Dictionary to track all values we input during the test
    test_inputs = {
        "setupPath": "advanced",
        "namespace": "test-project-namespace",
        "broker_type": "solace",
        "broker_url": "ws://localhost:8008",
        "broker_vpn": "test-vpn",
        "broker_username": "test-user",
        "broker_password": "test-password",
        # AI Provider configuration
        "llm_provider": "openai",
        "llm_api_key": "test-openai-api-key",
        "llm_model_name": "gpt-4",
        # Embedding configuration
        "embedding_service_enabled": True,
        "embedding_provider": "openai",
        "embedding_api_key": "test-embedding-api-key",
        "embedding_model_name": "text-embedding-ada-002"
    }
    
    # Wait for the path selection step to load
    page.wait_for_selector("h2:text('Setup Path')", timeout=10000)
    
    # Step 1: Select Advanced Path
    advanced_option = page.locator("h3:has-text('Advanced Setup')").first
    expect(advanced_option).to_be_visible()
    advanced_option.click()
    
    # Click Continue/Next
    continue_button = page.locator("button:has-text('Continue')").or_(
        page.locator("button:has-text('Next')")
    )
    expect(continue_button).to_be_visible()
    continue_button.click()
    
    # Step 2: Project Setup
    # Wait for Project Setup page to load
    page.wait_for_selector("h2:text('Project Structure')", timeout=10000)
    
    # Fill in the namespace with the value from test_inputs
    namespace_input = page.locator("input#namespace")
    expect(namespace_input).to_be_visible()
    namespace_input.fill(test_inputs["namespace"])
    
    # Click Next
    next_button = page.locator("button:text('Next')")
    expect(next_button).to_be_enabled()
    next_button.click()
    
    # Step 3: Broker Setup
    # Wait for Broker Setup page to load
    page.wait_for_selector("h2:text('Broker Setup')", timeout=10000)
    
    # Select broker type
    broker_type_select = page.locator("select#broker_type")
    expect(broker_type_select).to_be_visible()
    broker_type_select.select_option(test_inputs["broker_type"])
    
    # For the "solace" broker type, we need to fill in the connection details
    if test_inputs["broker_type"] == "solace":
        # Fill in broker URL
        broker_url_input = page.locator("input#broker_url")
        expect(broker_url_input).to_be_visible()
        broker_url_input.fill(test_inputs["broker_url"])
        
        # Fill in VPN name
        broker_vpn_input = page.locator("input#broker_vpn")
        expect(broker_vpn_input).to_be_visible()
        broker_vpn_input.fill(test_inputs["broker_vpn"])
        
        # Fill in username
        broker_username_input = page.locator("input#broker_username")
        expect(broker_username_input).to_be_visible()
        broker_username_input.fill(test_inputs["broker_username"])
        
        # Fill in password
        broker_password_input = page.locator("input#broker_password")
        expect(broker_password_input).to_be_visible()
        broker_password_input.fill(test_inputs["broker_password"])
    
    # Click Next to proceed to the AI Provider Setup
    next_button = page.locator("button:text('Next')")
    expect(next_button).to_be_enabled()
    next_button.click()
    
    # Step 4: AI Provider Setup
    # Wait for AI Provider Setup page to load
    page.wait_for_selector("h3:text('Language Model Configuration')", timeout=10000)
    
    # Select LLM provider
    llm_provider_select = page.locator("select#llm_provider")
    expect(llm_provider_select).to_be_visible()
    llm_provider_select.select_option(test_inputs["llm_provider"])
    
    # Fill in LLM API key
    llm_api_key_input = page.locator("input#llm_api_key")
    expect(llm_api_key_input).to_be_visible()
    llm_api_key_input.fill(test_inputs["llm_api_key"])
    
    # Fill in LLM model name using autocomplete input
    llm_model_name_input = page.locator("input#llm_model_name")
    expect(llm_model_name_input).to_be_visible()
    llm_model_name_input.fill(test_inputs["llm_model_name"])
    
    # Handle embedding service toggle if needed
    # First check if it's in the desired state
    embedding_toggle = page.locator("input#embedding_service_enabled")
    current_toggle_state = embedding_toggle.is_checked()
    
    # Toggle if needed to match our desired state
    if current_toggle_state != test_inputs["embedding_service_enabled"]:
        toggle_label = page.locator("label[for='embedding_service_enabled']")
        expect(toggle_label).to_be_visible()
        toggle_label.click()
    
    # Fill in embedding configuration if enabled
    if test_inputs["embedding_service_enabled"]:
        # Select embedding provider
        embedding_provider_select = page.locator("select#embedding_provider")
        expect(embedding_provider_select).to_be_visible()
        embedding_provider_select.select_option(test_inputs["embedding_provider"])
        
        # Fill in embedding API key
        embedding_api_key_input = page.locator("input#embedding_api_key")
        expect(embedding_api_key_input).to_be_visible()
        embedding_api_key_input.fill(test_inputs["embedding_api_key"])
        
        # Fill in embedding model name
        embedding_model_name_input = page.locator("input#embedding_model_name")
        expect(embedding_model_name_input).to_be_visible()
        embedding_model_name_input.fill(test_inputs["embedding_model_name"])
    
    # Mock the API call for testing LLM config
    page.route("/api/test_llm_config", lambda route: route.fulfill(
        status=200,
        body=json.dumps({"status": "success", "message": "Connection successful"})
    ))
    
    # Click Next to proceed
    next_button = page.locator("button:text('Next')")
    expect(next_button).to_be_enabled()
    next_button.click()
    
    # Get the shared configuration
    shared_config = dict(config_portal["shared_config"])
    
    print("\n\n=== TEST INPUTS ===")
    pprint.pprint(test_inputs)
    print("\n=== SHARED CONFIG ===")
    pprint.pprint(shared_config)
    print("====================\n\n")
    
    # Verify all test inputs are correctly reflected in shared_config
    for key, value in test_inputs.items():
        assert key in shared_config, f"Missing key in shared_config: {key}"
        assert shared_config[key] == value, f"Value mismatch for {key}: expected {value}, got {shared_config[key]}"

# def test_get_started_link(page: Page):
#     page.goto("")

#     # Click the get started link.
#     page.get_by_role("link", name="Get started").click()

#     # Expects page to have a heading with the name of Installation.
#     expect(page.get_by_role("heading", name="Installation")).to_be_visible()

    # If we wanted to test the container option instead:
    # elif test_inputs["broker_type"] == "container":
    #     # Select container engine
    #     container_engine_select = page.locator("select#container_engine")
    #     expect(container_engine_select).to_be_visible()
    #     container_engine_select.select_option("podman")  # or "docker"
    #     test_inputs["container_engine"] = "podman"
        
    #     # Click on "Download and Run Container" button
    #     run_container_button = page.locator("button:has-text('Download and Run Container')")
    #     expect(run_container_button).to_be_visible()
    #     run_container_button.click()
        
    #     # Wait for container to start (may need to mock this in a test)
    #     page.wait_for_selector("text=Container Running", timeout=20000)
    #     test_inputs["container_started"] = True
    
    # # If testing dev_mode:
    # elif test_inputs["broker_type"] == "dev_mode":
    #     # dev_mode is simpler, no additional fields to fill
    #     test_inputs["dev_mode"] = True
    
    # # Click Next to proceed to the next step
    # next_button = page.locator("button:text('Next')")
    # expect(next_button).to_be_enabled()
    # next_button.click()
    
    # # Wait for the next page to load (assuming the next page has a different header)
    # # Update this selector to match the header of the next page
    # page.wait_for_selector("h2:not(:text('Broker Setup'))", timeout=10000)
    
    # # Get the shared configuration
    # shared_config = dict(config_portal["shared_config"])
    
    # print("\n\n=== TEST INPUTS ===")
    # pprint.pprint(test_inputs)
    # print("\n=== SHARED CONFIG ===")
    # pprint.pprint(shared_config)
    # print("====================\n\n")