import requests
import json
import os
import logging
from typing import Dict, Any, Optional, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL = os.getenv("OLLAMA_MODEL", "llama3")
EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
MOCK_MODE = os.getenv("OLLAMA_MOCK", "false").lower() == "true"

def generate_json(prompt: str, model: str = MODEL) -> Optional[Dict[str, Any]]:
    if MOCK_MODE:
        logger.info("Returning MOCK LLM response")
        return {
            "title": "Mock Title",
            "author": "Mock Author",
            "created_hint": "2023-01-01",
            "tags": ["mock", "test"],
            "summary": "This is a mock summary."
        }

    url = f"{OLLAMA_URL}/api/generate"
    
    payload = {
        "model": model,
        "prompt": prompt,
        "format": "json",
        "stream": False
    }
    
    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        result = response.json()
        response_text = result.get("response", "")
        
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON from LLM response: {response_text}")
            return None
            
    except requests.RequestException as e:
        logger.error(f"Ollama request failed: {e}")
        return None

def embed_text(text: str, model: str = EMBEDDING_MODEL) -> Optional[List[float]]:
    if MOCK_MODE:
        # Return random vector of length 768
        import random
        return [random.random() for _ in range(768)]

    url = f"{OLLAMA_URL}/api/embeddings"
    
    payload = {
        "model": model,
        "prompt": text
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        return result.get("embedding")
    except requests.RequestException as e:
        logger.error(f"Ollama embedding request failed: {e}")
        return None

def generate_text(prompt: str, model: str = MODEL) -> Optional[str]:
    if MOCK_MODE:
        return "This is a mock answer based on the retrieved documents."

    url = f"{OLLAMA_URL}/api/generate"
    
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }
    
    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        result = response.json()
        return result.get("response", "")
    except requests.RequestException as e:
        logger.error(f"Ollama text generation failed: {e}")
        return None
