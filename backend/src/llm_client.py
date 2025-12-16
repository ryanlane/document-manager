import requests
import json
import os
import logging
import base64
from pathlib import Path
from typing import Dict, Any, Optional, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment-based defaults (can be overridden by settings)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL = os.getenv("OLLAMA_MODEL", "llama3")
EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "llava")
MOCK_MODE = os.getenv("OLLAMA_MOCK", "false").lower() == "true"

# OpenAI settings
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

# Anthropic settings
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")

# Known vision-capable models
VISION_MODELS = {'llava', 'llava:7b', 'llava:13b', 'llava:34b', 'llama3.2-vision', 'bakllava', 'moondream', 'gpt-4o', 'gpt-4o-mini', 'gpt-4-vision-preview'}


class LLMClient:
    """Multi-provider LLM client with support for Ollama, OpenAI, and Anthropic."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the LLM client.
        
        Args:
            config: Optional configuration dict with provider settings.
                   If None, uses environment variables.
        """
        self.config = config or {}
        self.provider = self.config.get("provider", "ollama")
        
        # Ollama settings
        self.ollama_url = self.config.get("url") or OLLAMA_URL
        self.ollama_model = self.config.get("model") or MODEL
        self.ollama_embedding_model = self.config.get("embedding_model") or EMBEDDING_MODEL
        self.ollama_vision_model = self.config.get("vision_model") or VISION_MODEL
        
        # OpenAI settings
        self.openai_api_key = self.config.get("api_key") or OPENAI_API_KEY
        self.openai_model = self.config.get("model") or OPENAI_MODEL
        self.openai_embedding_model = self.config.get("embedding_model") or OPENAI_EMBEDDING_MODEL
        
        # Anthropic settings  
        self.anthropic_api_key = self.config.get("api_key") or ANTHROPIC_API_KEY
        self.anthropic_model = self.config.get("model") or ANTHROPIC_MODEL

    def generate_json(self, prompt: str, model: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Generate JSON response from LLM."""
        if self.provider == "openai":
            return self._openai_generate_json(prompt, model)
        elif self.provider == "anthropic":
            return self._anthropic_generate_json(prompt, model)
        else:
            return self._ollama_generate_json(prompt, model)

    def generate_text(self, prompt: str, model: Optional[str] = None) -> Optional[str]:
        """Generate text response from LLM."""
        if self.provider == "openai":
            return self._openai_generate_text(prompt, model)
        elif self.provider == "anthropic":
            return self._anthropic_generate_text(prompt, model)
        else:
            return self._ollama_generate_text(prompt, model)

    def embed_text(self, text: str, model: Optional[str] = None) -> Optional[List[float]]:
        """Generate text embeddings."""
        if self.provider == "openai":
            return self._openai_embed(text, model)
        else:
            # Anthropic doesn't have embeddings, fall back to Ollama
            return self._ollama_embed(text, model)

    def describe_image(self, image_path: str, model: Optional[str] = None, prompt: Optional[str] = None) -> Optional[str]:
        """Describe an image using vision model."""
        default_prompt = "Describe this image in detail. Include any visible text, objects, people, settings, colors, and notable features."
        prompt = prompt or default_prompt
        
        if self.provider == "openai":
            return self._openai_describe_image(image_path, model, prompt)
        else:
            return self._ollama_describe_image(image_path, model, prompt)

    # ==================== Ollama Methods ====================
    
    def _ollama_generate_json(self, prompt: str, model: Optional[str] = None) -> Optional[Dict[str, Any]]:
        model = model or self.ollama_model
        url = f"{self.ollama_url}/api/generate"
        
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
            return json.loads(response_text)
        except (requests.RequestException, json.JSONDecodeError) as e:
            logger.error(f"Ollama JSON generation failed: {e}")
            return None

    def _ollama_generate_text(self, prompt: str, model: Optional[str] = None) -> Optional[str]:
        model = model or self.ollama_model
        url = f"{self.ollama_url}/api/generate"
        
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

    def _ollama_embed(self, text: str, model: Optional[str] = None) -> Optional[List[float]]:
        model = model or self.ollama_embedding_model
        url = f"{self.ollama_url}/api/embeddings"
        
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
            logger.error(f"Ollama embedding failed: {e}")
            return None

    def _ollama_describe_image(self, image_path: str, model: Optional[str] = None, prompt: str = "") -> Optional[str]:
        model = model or self.ollama_vision_model
        
        try:
            path = Path(image_path)
            if not path.exists():
                logger.error(f"Image not found: {image_path}")
                return None
            
            with open(path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
            
            url = f"{self.ollama_url}/api/generate"
            payload = {
                "model": model,
                "prompt": prompt,
                "images": [image_data],
                "stream": False
            }
            
            response = requests.post(url, json=payload, timeout=180)
            response.raise_for_status()
            result = response.json()
            
            description = result.get("response", "")
            logger.info(f"Generated description ({len(description)} chars) for {path.name}")
            return description
        except Exception as e:
            logger.error(f"Ollama vision failed: {e}")
            return None

    # ==================== OpenAI Methods ====================
    
    def _openai_generate_json(self, prompt: str, model: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not self.openai_api_key:
            logger.error("OpenAI API key not configured")
            return None
            
        model = model or self.openai_model
        
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"}
                },
                timeout=120
            )
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            return json.loads(content)
        except Exception as e:
            logger.error(f"OpenAI JSON generation failed: {e}")
            return None

    def _openai_generate_text(self, prompt: str, model: Optional[str] = None) -> Optional[str]:
        if not self.openai_api_key:
            logger.error("OpenAI API key not configured")
            return None
            
        model = model or self.openai_model
        
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=120
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"OpenAI text generation failed: {e}")
            return None

    def _openai_embed(self, text: str, model: Optional[str] = None) -> Optional[List[float]]:
        if not self.openai_api_key:
            logger.error("OpenAI API key not configured")
            return None
            
        model = model or self.openai_embedding_model
        
        try:
            response = requests.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "input": text
                },
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            return result["data"][0]["embedding"]
        except Exception as e:
            logger.error(f"OpenAI embedding failed: {e}")
            return None

    def _openai_describe_image(self, image_path: str, model: Optional[str] = None, prompt: str = "") -> Optional[str]:
        if not self.openai_api_key:
            logger.error("OpenAI API key not configured")
            return None
            
        model = model or "gpt-4o"
        
        try:
            path = Path(image_path)
            if not path.exists():
                logger.error(f"Image not found: {image_path}")
                return None
            
            with open(path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
            
            # Determine mime type
            ext = path.suffix.lower()
            mime_types = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.gif': 'image/gif', '.webp': 'image/webp'}
            mime_type = mime_types.get(ext, 'image/jpeg')
            
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_data}"}}
                        ]
                    }],
                    "max_tokens": 1000
                },
                timeout=180
            )
            response.raise_for_status()
            result = response.json()
            description = result["choices"][0]["message"]["content"]
            logger.info(f"Generated description ({len(description)} chars) for {path.name}")
            return description
        except Exception as e:
            logger.error(f"OpenAI vision failed: {e}")
            return None

    # ==================== Anthropic Methods ====================
    
    def _anthropic_generate_json(self, prompt: str, model: Optional[str] = None) -> Optional[Dict[str, Any]]:
        text = self._anthropic_generate_text(prompt + "\n\nRespond with valid JSON only.", model)
        if text:
            try:
                # Try to extract JSON from response
                start = text.find('{')
                end = text.rfind('}') + 1
                if start >= 0 and end > start:
                    return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
        return None

    def _anthropic_generate_text(self, prompt: str, model: Optional[str] = None) -> Optional[str]:
        if not self.anthropic_api_key:
            logger.error("Anthropic API key not configured")
            return None
            
        model = model or self.anthropic_model
        
        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "max_tokens": 4096,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=120
            )
            response.raise_for_status()
            result = response.json()
            return result["content"][0]["text"]
        except Exception as e:
            logger.error(f"Anthropic generation failed: {e}")
            return None


# ==================== Legacy Functions (for backward compatibility) ====================

# Default client instance
_default_client: Optional[LLMClient] = None

def get_client(config: Optional[Dict[str, Any]] = None) -> LLMClient:
    """Get or create an LLM client instance."""
    global _default_client
    if config:
        return LLMClient(config)
    if _default_client is None:
        _default_client = LLMClient()
    return _default_client

def set_default_client(config: Dict[str, Any]):
    """Set the default client configuration."""
    global _default_client
    _default_client = LLMClient(config)

def generate_json(prompt: str, model: str = None) -> Optional[Dict[str, Any]]:
    if MOCK_MODE:
        logger.info("Returning MOCK LLM response")
        return {
            "title": "Mock Title",
            "author": "Mock Author",
            "created_hint": "2023-01-01",
            "tags": ["mock", "test"],
            "summary": "This is a mock summary."
        }
    
    # Use the default client if available (which may have db config)
    client = get_client()
    if model is None:
        model = client.ollama_model
    url = client.ollama_url

    payload = {
        "model": model,
        "prompt": prompt,
        "format": "json",
        "stream": False
    }
    
    try:
        response = requests.post(f"{url}/api/generate", json=payload, timeout=120)
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

def list_models(url: str = None) -> List[str]:
    if MOCK_MODE:
        return ["mock-model-1", "mock-model-2"]
    
    ollama_url = url or OLLAMA_URL
    api_url = f"{ollama_url}/api/tags"
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        # Extract model names
        return [model['name'] for model in data.get('models', [])]
    except requests.RequestException as e:
        logger.error(f"Failed to list Ollama models: {e}")
        return []


def model_exists(model_name: str, url: str = None) -> bool:
    """Check if a model is available in Ollama."""
    if MOCK_MODE:
        return True
    
    available_models = list_models(url)
    # Check exact match or base name match (e.g., "phi4-mini:latest" matches "phi4-mini")
    model_base = model_name.split(':')[0]
    for m in available_models:
        if m == model_name or m.split(':')[0] == model_base:
            return True
    return False


def pull_model(model_name: str, url: str = None) -> bool:
    """
    Pull/download a model from Ollama. Blocks until complete.
    
    Args:
        model_name: Name of the model to pull (e.g., "phi4-mini:latest")
        url: Ollama URL (defaults to OLLAMA_URL)
    
    Returns:
        True if pull succeeded, False otherwise
    """
    if MOCK_MODE:
        return True
    
    ollama_url = url or OLLAMA_URL
    api_url = f"{ollama_url}/api/pull"
    
    logger.info(f"Pulling model '{model_name}' from Ollama...")
    
    try:
        # Use streaming to track progress
        resp = requests.post(
            api_url,
            json={"name": model_name, "stream": True},
            stream=True,
            timeout=7200  # 2 hour timeout for large models
        )
        resp.raise_for_status()
        
        last_progress = -1
        for line in resp.iter_lines():
            if line:
                try:
                    data = json.loads(line)
                    status = data.get("status", "")
                    
                    if "completed" in data and "total" in data and data["total"] > 0:
                        progress = int(data["completed"] / data["total"] * 100)
                        # Log progress at 10% intervals
                        if progress >= last_progress + 10:
                            logger.info(f"Pulling {model_name}: {progress}% - {status}")
                            last_progress = progress
                    elif status == "success":
                        logger.info(f"Successfully pulled model '{model_name}'")
                        return True
                    elif "error" in data:
                        logger.error(f"Error pulling model: {data.get('error')}")
                        return False
                except json.JSONDecodeError:
                    pass
        
        logger.info(f"Successfully pulled model '{model_name}'")
        return True
        
    except requests.RequestException as e:
        logger.error(f"Failed to pull model '{model_name}': {e}")
        return False


def ensure_models_available(config: Dict[str, Any]) -> bool:
    """
    Ensure all configured models are available in Ollama.
    Pulls missing models automatically.
    
    Args:
        config: LLM config dict with model, embedding_model, etc.
    
    Returns:
        True if all models are available, False if any pull failed
    """
    if config.get("provider") != "ollama":
        return True  # Only applies to Ollama
    
    url = config.get("url") or OLLAMA_URL
    models_to_check = []
    
    # Collect models to check
    if config.get("model"):
        models_to_check.append(("chat", config["model"]))
    if config.get("embedding_model"):
        models_to_check.append(("embedding", config["embedding_model"]))
    if config.get("vision_model"):
        models_to_check.append(("vision", config["vision_model"]))
    
    all_available = True
    for model_type, model_name in models_to_check:
        if not model_exists(model_name, url):
            logger.warning(f"{model_type.capitalize()} model '{model_name}' not found. Attempting to pull...")
            if pull_model(model_name, url):
                logger.info(f"{model_type.capitalize()} model '{model_name}' is now available")
            else:
                logger.error(f"Failed to pull {model_type} model '{model_name}'")
                all_available = False
        else:
            logger.debug(f"{model_type.capitalize()} model '{model_name}' is available")
    
    return all_available


def list_vision_models() -> List[str]:
    """Return a list of available vision-capable models."""
    all_models = list_models()
    vision_available = []
    
    for model in all_models:
        # Check if model name matches known vision models
        model_base = model.split(':')[0].lower()
        if model_base in VISION_MODELS or any(vm in model.lower() for vm in VISION_MODELS):
            vision_available.append(model)
    
    return vision_available


def describe_image(
    image_path: str, 
    model: str = VISION_MODEL,
    prompt: str = "Describe this image in detail. Include any visible text, objects, people, settings, colors, and notable features."
) -> Optional[str]:
    """
    Use a vision model to describe an image.
    
    Args:
        image_path: Path to the image file
        model: Vision model to use (e.g., 'llava', 'llama3.2-vision')
        prompt: The prompt to send with the image
        
    Returns:
        Description string or None if failed
    """
    if MOCK_MODE:
        return "This is a mock image description. The image shows a scene with various elements."
    
    try:
        # Read and encode image as base64
        image_path = Path(image_path)
        if not image_path.exists():
            logger.error(f"Image file not found: {image_path}")
            return None
        
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        
        url = f"{OLLAMA_URL}/api/generate"
        
        payload = {
            "model": model,
            "prompt": prompt,
            "images": [image_data],
            "stream": False
        }
        
        response = requests.post(url, json=payload, timeout=180)  # Longer timeout for vision
        response.raise_for_status()
        result = response.json()
        
        description = result.get("response", "")
        logger.info(f"Generated description ({len(description)} chars) for {image_path.name}")
        return description
        
    except requests.RequestException as e:
        logger.error(f"Vision model request failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Error processing image {image_path}: {e}")
        return None


def describe_image_base64(
    image_base64: str,
    model: str = VISION_MODEL,
    prompt: str = "Describe this image in detail. Include any visible text, objects, people, settings, colors, and notable features."
) -> Optional[str]:
    """
    Use a vision model to describe an image from base64 data.
    
    Args:
        image_base64: Base64-encoded image data
        model: Vision model to use
        prompt: The prompt to send with the image
        
    Returns:
        Description string or None if failed
    """
    if MOCK_MODE:
        return "This is a mock image description from base64 data."
    
    try:
        url = f"{OLLAMA_URL}/api/generate"
        
        payload = {
            "model": model,
            "prompt": prompt,
            "images": [image_base64],
            "stream": False
        }
        
        response = requests.post(url, json=payload, timeout=180)
        response.raise_for_status()
        result = response.json()
        
        return result.get("response", "")
        
    except requests.RequestException as e:
        logger.error(f"Vision model request failed: {e}")
        return None
