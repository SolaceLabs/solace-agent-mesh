import pytest
import psutil
import gc
import os
import requests
import time
import json
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor

MEMORY_THRESHOLD = 5  # MB
NUM_THREADS = 5
NUM_ITERATIONS = 3
REST_API_SERVER_INPUT_ENDPOINT = os.getenv("REST_API_SERVER_INPUT_ENDPOINT", "/api/v1/request")

@pytest.mark.skip(reason="Manually run these tests with sam running")
class TestMemoryCleanup:
    ### Rest server tests ###
    def test_rest_server_memory_cleanup(self, rest_server):
        """Test the server's ability to handle memory cleanup after requests"""
        # Force collect garbage
        gc.collect()

        # Initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / (1024 * 1024)
        print(f"\nInitial memory usage: {initial_memory:.2f} MB")

        headers = {
            'Authorization': 'Bearer test_token',
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-Refresh-Token': 'test_refresh_token'
        }

        def make_request(thread_id):
            """Make a request to the server"""
            data = {
                "prompt": f"Hello from thread {thread_id}, generate a random plot.",
                "stream": "true",
                "session_id": f"test_session_{thread_id}"
            }

            try:
                response = requests.post(
                    f"{rest_server()}{REST_API_SERVER_INPUT_ENDPOINT}",
                    headers=headers,
                    data=data
                )
                print(f"Thread {thread_id} response: {response.status_code}")
                return response.status_code
            except Exception as e:
                print(f"Thread {thread_id} error: {e}")
                return None
            
        # Run multiple threads
        for iteration in range(NUM_ITERATIONS):
            print(f"\nIteration {iteration + 1}/{NUM_ITERATIONS}")
            with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
                futures = [executor.submit(make_request, i) for i in range(NUM_THREADS)]
                results = [future.result() for future in futures]

            successful_requests = sum(1 for status in results if status == 200)
            print(f"Successful requests: {successful_requests}/{NUM_THREADS}")

            # Force collect garbage again
            gc.collect()

            # Check memory usage after requests
            current_memory = process.memory_info().rss / (1024 * 1024)
            print(f"Current memory usage: {current_memory:.2f} MB")
            print(f"Memory increase: {current_memory - initial_memory:.2f} MB")

            time.sleep(1)

        # Final memory cleanup
        gc.collect()
        final_memory = process.memory_info().rss / (1024 * 1024)
        print(f"\nFinal memory usage: {final_memory:.2f} MB")
        print(f"Memory increase after all iterations: {final_memory - initial_memory:.2f} MB")
        assert final_memory - initial_memory < MEMORY_THRESHOLD, "Memory leak detected: increase exceeds threshold"
        time.sleep(15)

    ### Web server tests ###
    def test_web_server_memory_cleanup(self, web_server):
        """Test the server's ability to handle memory cleanup after requests"""
        # Force collect garbage
        gc.collect()

        # Initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / (1024 * 1024)
        print(f"\nInitial memory usage: {initial_memory:.2f} MB")

        headers = {
            'Authorization': 'Bearer test_token',
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-Refresh-Token': 'test_refresh_token'
        }

        def make_request(thread_id):
            """Make a request to the server"""
            data = {
                "prompt": f"Hello from thread {thread_id}, generate a random plot.",
                "stream": "true",
                "session_id": f"test_session_{thread_id}"
            }

            try:
                response = requests.post(
                    f"{web_server()}/api/v1/chat",
                    headers=headers,
                    data=data
                )
                print(f"Thread {thread_id} response: {response.status_code}")
                return response.status_code
            except Exception as e:
                print(f"Thread {thread_id} error: {e}")
                return None
            
        # Run multiple threads
        for iteration in range(NUM_ITERATIONS):
            print(f"\nIteration {iteration + 1}/{NUM_ITERATIONS}")
            with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
                futures = [executor.submit(make_request, i) for i in range(NUM_THREADS)]
                results = [future.result() for future in futures]

            successful_requests = sum(1 for status in results if status == 200)
            print(f"Successful requests: {successful_requests}/{NUM_THREADS}")

            # Force collect garbage again
            gc.collect()

            # Check memory usage after requests
            current_memory = process.memory_info().rss / (1024 * 1024)
            print(f"Current memory usage: {current_memory:.2f} MB")
            print(f"Memory increase: {current_memory - initial_memory:.2f} MB")

            time.sleep(1)

        # Final memory cleanup
        gc.collect()
        final_memory = process.memory_info().rss / (1024 * 1024)
        print(f"\nFinal memory usage: {final_memory:.2f} MB")
        assert final_memory - initial_memory < MEMORY_THRESHOLD, "Memory leak detected: increase exceeds threshold"
        time.sleep(15)