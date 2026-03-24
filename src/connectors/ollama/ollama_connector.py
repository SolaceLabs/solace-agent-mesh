import requests
import json

class OllamaConnector:
    """
    Connector for Ollama local LLM inference.
    Enables privacy-first agent mesh operations.
    """
    def __init__(self, base_url="http://localhost:11434"):
        self.base_url = f"{base_url}/api/generate"

    def generate(self, model, prompt):
        payload = {"model": model, "prompt": prompt, "stream": False}
        response = requests.post(self.base_url, json=payload)
        return response.json().get("response")
