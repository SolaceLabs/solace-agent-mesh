#!/usr/bin/env python3
"""Debug script to test the app preview proxy."""

import requests
import sys

def test_proxy():
    print("=" * 60)
    print("Testing App Preview Proxy")
    print("=" * 60)

    app_id = "test8"

    # Test 1: Direct access to container
    print(f"\n1. Testing direct container access...")
    container_port = 44717  # Update this if different
    direct_url = f"http://127.0.0.1:{container_port}/"
    try:
        response = requests.get(direct_url, timeout=5)
        print(f"   ✅ Direct container: {response.status_code}")
        print(f"   Content-Type: {response.headers.get('content-type')}")
    except Exception as e:
        print(f"   ❌ Direct container failed: {e}")
        return

    # Test 2: Backend proxy (port 8000)
    print(f"\n2. Testing backend proxy (port 8000)...")
    backend_url = f"http://localhost:8000/api/v1/apps/preview/{app_id}/"
    try:
        response = requests.get(backend_url, timeout=10)
        print(f"   Status: {response.status_code}")
        print(f"   Content-Type: {response.headers.get('content-type')}")
        if response.status_code == 500:
            print(f"   Error response: {response.text[:500]}")
        elif response.status_code == 200:
            print(f"   ✅ Backend proxy works!")
            # Check if HTML is rewritten
            if '/api/v1/apps/preview' in response.text:
                print(f"   ✅ URLs rewritten correctly")
            else:
                print(f"   ⚠️  URLs may not be rewritten")
    except Exception as e:
        print(f"   ❌ Backend proxy failed: {e}")
        import traceback
        traceback.print_exc()

    # Test 3: Frontend proxy (port 3000)
    print(f"\n3. Testing frontend Vite proxy (port 3000)...")
    frontend_url = f"http://localhost:3000/api/v1/apps/preview/{app_id}/"
    try:
        response = requests.get(frontend_url, timeout=10)
        print(f"   Status: {response.status_code}")
        print(f"   Content-Type: {response.headers.get('content-type')}")
        if response.status_code == 500:
            print(f"   Error response: {response.text[:500]}")
        elif response.status_code == 200:
            print(f"   ✅ Frontend proxy works!")
    except Exception as e:
        print(f"   ❌ Frontend proxy failed: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)

if __name__ == "__main__":
    test_proxy()
