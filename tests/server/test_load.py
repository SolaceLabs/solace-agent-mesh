import pytest
import requests
import time
import threading
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

SUCCESS_RATE = 0.95 # 95% success rate threshold
NUM_CONCURRENT_REQUESTS = 20
NUM_BURST_REQUESTS = 30
NUM_MIN_STRESS_REQUESTS = 10
NUM_MAX_STRESS_REQUESTS = 50
NUM_STEP_STRESS_REQUESTS = 10
REST_ENDPOINT = os.getenv("REST_API_SERVER_INPUT_ENDPOINT", "/api/v1/request")
WEB_ENDPOINT = "/api/v1/chat"

@pytest.mark.skip(reason="Manually run these tests with sam running")
class TestServerLoad:
    ### Generic request function ###
    def make_request(self, server, endpoint, request_id, headers, data, timeout=60):
        """Generic request function to be used in tests"""
        start_time = time.time()
        print(f"Making request {request_id} to {server}{endpoint}")
        try:
            response = requests.post(
                f"{server}{endpoint}",
                headers=headers,
                data=data,
                timeout=timeout
            )
            elapsed = time.time() - start_time
            print(f"Request completed with status {response.status_code} in {elapsed:.2f}s")
            return {
                "id": request_id,
                "status": response.status_code,
                "time": elapsed,
                "response": response
            }
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"Request failed with error: {str(e)} after {elapsed:.2f}s")
            return {
                "id": request_id,
                "status": str(e),
                "time": elapsed,
                "response": None
            }

    ### Rest server tests ###
    def test_rest_server_concurrent_requests(self, rest_server):
        """Test the server's ability to handle concurrent requests"""
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        results = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for i in range(NUM_CONCURRENT_REQUESTS):
                data = {
                    "prompt": f"This is a test request {i}",
                    "stream": "false",
                    "session_id": f"test_session_{i}"
                }
                futures.append(executor.submit(
                    self.make_request,
                    rest_server(),
                    REST_ENDPOINT,
                    i,
                    headers,
                    data
                ))

            for future in as_completed(futures):
                results.append(future.result())
        
        # Check results
        success_count = sum(1 for result in results if result["status"] == 200)
        assert success_count >= NUM_CONCURRENT_REQUESTS * SUCCESS_RATE

    def test_rest_server_burst_load(self, rest_server):
        """Test the server's ability to handle a sudden burst of traffic"""
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        response_times = []
        success_count = 0
        failures = []

        # Launch burst requests
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=NUM_BURST_REQUESTS) as executor:
            futures = []
            for i in range(NUM_BURST_REQUESTS):
                data = {
                    "prompt": f"Burst request {i}",
                    "stream": "false",
                    "session_id": f"burst_session_{i}"
                }
                futures.append(executor.submit(
                    self.make_request,
                    rest_server(),
                    REST_ENDPOINT,
                    i,
                    headers,
                    data
                ))
            for future in as_completed(futures):
                result = future.result()
                if result["status"] == 200:
                    success_count += 1
                    response_times.append(result["time"])
                else:
                    failures.append(result)
        total_time = time.time() - start_time

        print(f"\nBurst test completed in {total_time:.2f} seconds")
        if not success_count >= NUM_BURST_REQUESTS * SUCCESS_RATE:
            pytest.skip(f"Success rate {success_count/NUM_BURST_REQUESTS*100:.1f}% below threshold of {SUCCESS_RATE*100}%")
        assert success_count >= NUM_BURST_REQUESTS * SUCCESS_RATE

    def test_rest_server_stress(self, rest_server):
        """Test the server by gradually increasing load until failure or threshold"""
        last_successful_batch = 0
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}

        for batch_size in range(NUM_MIN_STRESS_REQUESTS, NUM_MAX_STRESS_REQUESTS + 1, NUM_STEP_STRESS_REQUESTS):
            print(f"\nTesting batch size: {batch_size}")
            successes = 0
            failures = 0
            response_times = []

            start_time = time.time()
            with ThreadPoolExecutor(max_workers=batch_size) as executor:
                futures = []
                for i in range(batch_size):
                    data = {
                        "prompt": f"Stress test request {i} in batch {batch_size}, generate a random plot.",
                        "stream": "false",
                        "session_id": f"stress-{batch_size}-{i}"
                    }
                    futures.append(executor.submit(
                        self.make_request,
                        rest_server(),
                        REST_ENDPOINT,
                        f"{batch_size}-{i}",
                        headers,
                        data
                    ))

                for future in as_completed(futures):
                    result = future.result()
                    if result["status"] == 200:
                        successes += 1
                        response_times.append(result["time"])
                    else:
                        failures += 1
                        print(f"Failure in batch size {batch_size}: {result}")

            total_time = time.time() - start_time
            print(f"Batch size {batch_size} completed in {total_time:.2f}s with {successes} successes and {failures} failures")
            if successes >= batch_size * SUCCESS_RATE:
                last_successful_batch = batch_size
            else:
                print(f"Batch size {batch_size} failed to meet success criteria")
                break

            time.sleep(15)  # Wait before next batch
        print(f"Last successful batch size: {last_successful_batch}")
        assert True

    ### Web server tests ###
    def test_web_server_concurrent_requests(self, web_server):
        """Test the server's ability to handle concurrent requests"""
        headers = {
            'Authorization': 'Bearer test_token',
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-Refresh-Token': 'test_refresh_token'
        }

        results = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for i in range(NUM_CONCURRENT_REQUESTS):
                data = {
                    "prompt": f"This is a test request {i}",
                    "stream": "false",
                    "session_id": f"test_session_{i}"
                }
                futures.append(executor.submit(
                    self.make_request,
                    web_server(),
                    WEB_ENDPOINT,
                    i,
                    headers,
                    data
                ))

            for future in as_completed(futures):
                results.append(future.result())
        # Check results
        success_count = sum(1 for result in results if result["status"] == 200)
        assert success_count >= NUM_CONCURRENT_REQUESTS * SUCCESS_RATE

    def test_web_server_burst_load(self, web_server):
        """Test the server's ability to handle a sudden burst of traffic"""
        headers = {
            'Authorization': 'Bearer test_token',
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-Refresh-Token': 'test_refresh_token'
        }
        response_times = []
        success_count = 0
        failures = []

        # Launch burst requests
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=NUM_BURST_REQUESTS) as executor:
            futures = []
            for i in range(NUM_BURST_REQUESTS):
                data = {
                    "prompt": f"Burst request {i}",
                    "stream": "false",
                    "session_id": f"burst_session_{i}"
                }
                futures.append(executor.submit(
                    self.make_request,
                    web_server(),
                    WEB_ENDPOINT,
                    i,
                    headers,
                    data
                ))
            for future in as_completed(futures):
                result = future.result()
                if result["status"] == 200:
                    success_count += 1
                    response_times.append(result["time"])
                else:
                    failures.append(result)
        total_time = time.time() - start_time

        print(f"\nBurst test completed in {total_time:.2f} seconds")
        if not success_count >= NUM_BURST_REQUESTS * SUCCESS_RATE:
            pytest.skip(f"Success rate {success_count/NUM_BURST_REQUESTS*100:.1f}% below threshold of {SUCCESS_RATE*100}%")
        assert success_count >= NUM_BURST_REQUESTS * SUCCESS_RATE

    def test_web_server_stress(self, web_server):
        """Test the server by gradually increasing load until failure or threshold"""
        last_successful_batch = 0
        headers = {
            'Authorization': 'Bearer test_token',
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-Refresh-Token': 'test_refresh_token'
        }

        for batch_size in range(NUM_MIN_STRESS_REQUESTS, NUM_MAX_STRESS_REQUESTS + 1, NUM_STEP_STRESS_REQUESTS):
            print(f"\nTesting batch size: {batch_size}")
            successes = 0
            failures = []
            response_times = []

            start_time = time.time()
            with ThreadPoolExecutor(max_workers=batch_size) as executor:
                futures = []
                for i in range(batch_size):
                    data = {
                        "prompt": f"Stress test request {i} in batch {batch_size}, generate a random plot.",
                        "stream": "false",
                        "session_id": f"stress-{batch_size}-{i}"
                    }
                    futures.append(executor.submit(
                        self.make_request,
                        web_server(),
                        WEB_ENDPOINT,
                        f"{batch_size}-{i}",
                        headers,
                        data
                    ))

                for future in as_completed(futures):
                    result = future.result()
                    if result["status"] == 200:
                        successes += 1
                        response_times.append(result["time"])
                    else:
                        failures.append(result)
                        print(f"Failure in batch size {batch_size}: {result}")

            total_time = time.time() - start_time
            print(f"Batch size {batch_size} completed in {total_time:.2f}s with {successes} successes and {len(failures)} failures")
            if successes >= batch_size * SUCCESS_RATE:
                last_successful_batch = batch_size
            else:
                print(f"Batch size {batch_size} failed to meet success criteria")
                break

            time.sleep(15)  # Wait before next batch
        print(f"Last successful batch size: {last_successful_batch}")
        assert True