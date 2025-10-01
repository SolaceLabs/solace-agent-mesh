#!/usr/bin/env python3
"""
Debug tool to test token usage reporting from LLM services.

This script tests whether your LLM endpoint returns usage/token data
and helps identify where token tracking might be failing.

Usage:
    python tools/debug_token_usage.py
"""

import os
import sys
import json
from pathlib import Path
from typing import Optional

# Add project root to path to allow imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from dotenv import load_dotenv
    import openai
    import litellm
except ImportError as e:
    print(f"Error: Missing required package: {e}")
    print("\nPlease install required packages:")
    print("  pip install python-dotenv openai litellm")
    sys.exit(1)


def load_credentials():
    """Load credentials from .env file."""
    # Try to load from project root
    env_path = project_root / ".env"
    if not env_path.exists():
        print(f"Error: .env file not found at {env_path}")
        print("Please create a .env file with LLM_SERVICE_ENDPOINT and LLM_SERVICE_API_KEY")
        sys.exit(1)
    
    load_dotenv(env_path)
    
    endpoint = os.getenv("LLM_SERVICE_ENDPOINT")
    api_key = os.getenv("LLM_SERVICE_API_KEY")
    
    if not endpoint or not api_key:
        print("Error: LLM_SERVICE_ENDPOINT and LLM_SERVICE_API_KEY must be set in .env")
        sys.exit(1)
    
    return endpoint, api_key


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_usage_info(usage_data: Optional[dict], source: str):
    """Print formatted usage information."""
    if usage_data:
        print(f"\n✓ Usage data found in {source}:")
        print(f"  {json.dumps(usage_data, indent=2)}")
    else:
        print(f"\n✗ No usage data found in {source}")


def test_openai_direct_nonstreaming(endpoint: str, api_key: str, model: str = "gpt-4o-mini"):
    """Test 1: Direct OpenAI SDK call (non-streaming)."""
    print_section("Test 1: Direct OpenAI SDK (Non-Streaming)")
    
    try:
        client = openai.OpenAI(
            base_url=endpoint,
            api_key=api_key,
        )
        
        print(f"Calling {endpoint} with model '{model}'...")
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": "Say 'Hello, World!' and nothing else."}
            ],
            max_tokens=50,
        )
        
        print("\n✓ Response received successfully")
        print(f"  Content: {response.choices[0].message.content}")
        
        # Check for usage data
        if hasattr(response, 'usage') and response.usage:
            usage_dict = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
            
            # Check for cached tokens (OpenAI-specific)
            if hasattr(response.usage, 'prompt_tokens_details'):
                details = response.usage.prompt_tokens_details
                if details and hasattr(details, 'cached_tokens'):
                    usage_dict["cached_tokens"] = details.cached_tokens
            
            print_usage_info(usage_dict, "response.usage")
        else:
            print_usage_info(None, "response.usage")
        
        # Print raw response for inspection
        print("\nRaw response object attributes:")
        print(f"  {dir(response)}")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_openai_direct_streaming(endpoint: str, api_key: str, model: str = "gpt-4o-mini"):
    """Test 2: Direct OpenAI SDK call (streaming)."""
    print_section("Test 2: Direct OpenAI SDK (Streaming)")
    
    try:
        client = openai.OpenAI(
            base_url=endpoint,
            api_key=api_key,
        )
        
        print(f"Calling {endpoint} with model '{model}' (streaming)...")
        
        stream = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": "Say 'Hello, World!' and nothing else."}
            ],
            max_tokens=50,
            stream=True,
        )
        
        print("\n✓ Stream started successfully")
        print("  Chunks received:")
        
        chunk_count = 0
        final_chunk = None
        
        for chunk in stream:
            chunk_count += 1
            content = chunk.choices[0].delta.content if chunk.choices[0].delta.content else ""
            if content:
                print(f"    Chunk {chunk_count}: '{content}'")
            
            # Keep track of the last chunk
            final_chunk = chunk
        
        print(f"\n  Total chunks: {chunk_count}")
        
        # Check for usage in final chunk
        if final_chunk and hasattr(final_chunk, 'usage') and final_chunk.usage:
            usage_dict = {
                "prompt_tokens": final_chunk.usage.prompt_tokens,
                "completion_tokens": final_chunk.usage.completion_tokens,
                "total_tokens": final_chunk.usage.total_tokens,
            }
            
            # Check for cached tokens
            if hasattr(final_chunk.usage, 'prompt_tokens_details'):
                details = final_chunk.usage.prompt_tokens_details
                if details and hasattr(details, 'cached_tokens'):
                    usage_dict["cached_tokens"] = details.cached_tokens
            
            print_usage_info(usage_dict, "final chunk.usage")
        else:
            print_usage_info(None, "final chunk.usage")
            if final_chunk:
                print("\nFinal chunk attributes:")
                print(f"  {dir(final_chunk)}")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_litellm_nonstreaming(endpoint: str, api_key: str, model: str = "gpt-4o-mini"):
    """Test 3: LiteLLM call (non-streaming)."""
    print_section("Test 3: LiteLLM (Non-Streaming)")
    
    try:
        # Configure LiteLLM
        litellm.api_base = endpoint
        litellm.api_key = api_key
        
        print(f"Calling via LiteLLM with model '{model}'...")
        
        response = litellm.completion(
            model=model,
            messages=[
                {"role": "user", "content": "Say 'Hello, World!' and nothing else."}
            ],
            max_tokens=50,
            api_base=endpoint,
            api_key=api_key,
        )
        
        print("\n✓ Response received successfully")
        print(f"  Content: {response.choices[0].message.content}")
        
        # Check for usage data
        if hasattr(response, 'usage') and response.usage:
            usage_dict = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
            
            # LiteLLM might normalize cached tokens differently
            if hasattr(response.usage, 'prompt_tokens_details'):
                usage_dict["prompt_tokens_details"] = str(response.usage.prompt_tokens_details)
            
            print_usage_info(usage_dict, "response.usage")
        else:
            print_usage_info(None, "response.usage")
        
        # Print raw response
        print("\nRaw response type:", type(response))
        print("Response attributes:")
        print(f"  {dir(response)}")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_litellm_streaming(endpoint: str, api_key: str, model: str = "gpt-4o-mini"):
    """Test 4: LiteLLM call (streaming)."""
    print_section("Test 4: LiteLLM (Streaming)")
    
    try:
        # Configure LiteLLM
        litellm.api_base = endpoint
        litellm.api_key = api_key
        
        print(f"Calling via LiteLLM with model '{model}' (streaming)...")
        
        response = litellm.completion(
            model=model,
            messages=[
                {"role": "user", "content": "Say 'Hello, World!' and nothing else."}
            ],
            max_tokens=50,
            stream=True,
            api_base=endpoint,
            api_key=api_key,
        )
        
        print("\n✓ Stream started successfully")
        print("  Chunks received:")
        
        chunk_count = 0
        final_chunk = None
        
        for chunk in response:
            chunk_count += 1
            content = chunk.choices[0].delta.content if hasattr(chunk.choices[0].delta, 'content') and chunk.choices[0].delta.content else ""
            if content:
                print(f"    Chunk {chunk_count}: '{content}'")
            
            final_chunk = chunk
        
        print(f"\n  Total chunks: {chunk_count}")
        
        # Check for usage in final chunk
        if final_chunk and hasattr(final_chunk, 'usage') and final_chunk.usage:
            usage_dict = {
                "prompt_tokens": final_chunk.usage.prompt_tokens,
                "completion_tokens": final_chunk.usage.completion_tokens,
                "total_tokens": final_chunk.usage.total_tokens,
            }
            
            if hasattr(final_chunk.usage, 'prompt_tokens_details'):
                usage_dict["prompt_tokens_details"] = str(final_chunk.usage.prompt_tokens_details)
            
            print_usage_info(usage_dict, "final chunk.usage")
        else:
            print_usage_info(None, "final chunk.usage")
            if final_chunk:
                print("\nFinal chunk type:", type(final_chunk))
                print("Final chunk attributes:")
                print(f"  {dir(final_chunk)}")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("  LLM Token Usage Debug Tool")
    print("=" * 80)
    
    # Load credentials
    print("\nLoading credentials from .env...")
    endpoint, api_key = load_credentials()
    print(f"  Endpoint: {endpoint}")
    print(f"  API Key: {'*' * 20}{api_key[-4:] if len(api_key) > 4 else '****'}")
    
    # Ask for model name
    print("\nEnter model name (or press Enter for 'gpt-4o-mini'):")
    model = input("> ").strip() or "gpt-4o-mini"
    print(f"Using model: {model}")
    
    # Run tests
    results = {
        "OpenAI Direct (Non-Streaming)": test_openai_direct_nonstreaming(endpoint, api_key, model),
        "OpenAI Direct (Streaming)": test_openai_direct_streaming(endpoint, api_key, model),
        "LiteLLM (Non-Streaming)": test_litellm_nonstreaming(endpoint, api_key, model),
        "LiteLLM (Streaming)": test_litellm_streaming(endpoint, api_key, model),
    }
    
    # Summary
    print_section("Summary")
    print("\nTest Results:")
    for test_name, success in results.items():
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"  {status}: {test_name}")
    
    # Recommendations
    print("\n" + "-" * 80)
    print("Recommendations:")
    print("-" * 80)
    
    all_passed = all(results.values())
    any_usage_found = False  # You'll need to track this in the tests
    
    if all_passed:
        print("\n✓ All tests passed!")
        print("\nNext steps:")
        print("  1. Check if usage data was found in any of the tests above")
        print("  2. If no usage data was found, your LLM endpoint may not support it")
        print("  3. If usage data was found, check your callback code in callbacks.py")
        print("  4. Verify that llm_response.usage_metadata is being accessed correctly")
    else:
        print("\n✗ Some tests failed. Check the errors above.")
        print("\nCommon issues:")
        print("  - Incorrect endpoint URL (should end with /v1 for OpenAI-compatible APIs)")
        print("  - Invalid API key")
        print("  - Model name not supported by your endpoint")
        print("  - Network connectivity issues")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
