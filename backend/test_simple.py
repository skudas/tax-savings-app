"""Simple test to debug signup issue."""

import requests
import json

BASE_URL = "http://127.0.0.1:8000"

print("Testing health check...")
response = requests.get(f"{BASE_URL}/health")
print(f"Health: {response.status_code} - {response.text}")

print("\nTesting signup...")
signup_data = {
    "email": "test@example.com",
    "password": "testpass123",
    "first_name": "Test",
    "last_name": "User"
}

response = requests.post(f"{BASE_URL}/api/auth/signup", json=signup_data)
print(f"Signup Response Status: {response.status_code}")
print(f"Signup Response Headers: {dict(response.headers)}")
print(f"Signup Response Content: {response.text}")

# Try to parse JSON
try:
    print(f"Parsed JSON: {response.json()}")
except Exception as e:
    print(f"JSON parse error: {e}")
