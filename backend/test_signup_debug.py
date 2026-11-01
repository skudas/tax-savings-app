"""Debug signup error."""

import requests
import json
import sys

BASE_URL = "http://127.0.0.1:8000"

signup_data = {
    "email": "test@example.com",
    "password": "testpass123",
    "first_name": "Test",
    "last_name": "User"
}

print("Attempting signup...")
try:
    response = requests.post(
        f"{BASE_URL}/api/auth/signup",
        json=signup_data,
        timeout=5
    )

    print(f"Status Code: {response.status_code}")
    print(f"Content Type: {response.headers.get('content-type')}")
    print(f"Response Text: {response.text}")

    if response.status_code != 200:
        print(f"\nERROR: Received status {response.status_code}")
        print("Response headers:")
        for key, value in response.headers.items():
            print(f"  {key}: {value}")

except requests.exceptions.RequestException as e:
    print(f"Request error: {e}")
    import traceback
    traceback.print_exc()
except Exception as e:
    print(f"Unexpected error: {e}")
    import traceback
    traceback.print_exc()
