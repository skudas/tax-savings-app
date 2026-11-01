"""Debug search endpoint."""

import requests

BASE_URL = "http://127.0.0.1:8000"

print("Testing search endpoint...")
response = requests.get(f"{BASE_URL}/api/professionals/search", params={"specialty": "S-Corp"})
print(f"Status: {response.status_code}")
print(f"Content: {response.text}")

# Try without params
print("\nTesting search without params...")
response = requests.get(f"{BASE_URL}/api/professionals/")
print(f"Status: {response.status_code}")
print(f"Content: {response.text}")
