import requests
import json

url = "https://unsanguine-rosette-impressibly.ngrok-free.dev/api/generate"
payload = {
    "model": "llama3.2",
    "prompt": "Hello",
    "stream": False
}

print(f"Testing connection to {url}...")

try:
    # Add header to skip ngrok browser warning and provide Origin
    headers = {
        "ngrok-skip-browser-warning": "true",
        "Origin": "https://unsanguine-rosette-impressibly.ngrok-free.dev"
    }
    response = requests.post(url, json=payload, headers=headers, timeout=10)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        print("Success! Ollama is reachable via ngrok.")
        print(f"Response: {response.text[:200]}...") # Print first 200 chars of response
    else:
        print(f"Failed. Status: {response.status_code}")
        print(f"Response Headers: {response.headers}")
        print(f"Response Body: {response.text}")
except Exception as e:
    print(f"Connection failed: {e}")
