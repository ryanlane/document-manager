import requests
import json
import os
import logging
import base64
import time
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

# Ollama embeddings will return a 500 when the input exceeds the model's context.
# This cap is intentionally conservative because context limits are token-based.
EMBEDDING_MAX_CHARS = int(os.getenv("EMBEDDING_MAX_CHARS", "8000"))
EMBEDDING_RETRY_ATTEMPTS = int(os.getenv("EMBEDDING_RETRY_ATTEMPTS", "2"))
EMBEDDING_RETRY_BASE_DELAY_S = float(os.getenv("EMBEDDING_RETRY_BASE_DELAY_S", "0.25"))


def _sanitize_embedding_prompt(text: str, max_chars: int) -> str:
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)

    # Avoid NULs which can cause odd downstream behavior.
    text = text.replace("\x00", "")
    if max_chars > 0 and len(text) > max_chars:
        return text[:max_chars]
    return text


def _looks_like_context_length_error(response: Optional[requests.Response]) -> bool:
    if response is None:
        return False
    try:
        body = (response.text or "").lower()
    except Exception:
        return False
    return "context length" in body or "input length exceeds" in body

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

        prompt = _sanitize_embedding_prompt(text, EMBEDDING_MAX_CHARS)
        for attempt in range(1, max(1, EMBEDDING_RETRY_ATTEMPTS) + 1):
            payload = {"model": model, "prompt": prompt}
            try:
                response = requests.post(url, json=payload, timeout=60)
                response.raise_for_status()
                result = response.json()
                return result.get("embedding")
            except requests.HTTPError as e:
                resp = getattr(e, "response", None)
                status = getattr(resp, "status_code", None)
                logger.error(
                    f"Ollama embedding failed (status={status}, model={model}, chars={len(prompt)}): {e}"
                )

                # Ollama returns 500 for context length issues; retry with a smaller prompt.
                if status in (500, 400, 413) and _looks_like_context_length_error(resp) and attempt < EMBEDDING_RETRY_ATTEMPTS:
                    prompt = _sanitize_embedding_prompt(prompt, max(1, int(len(prompt) * 0.5)))
                    time.sleep(EMBEDDING_RETRY_BASE_DELAY_S * attempt)
                    continue
                return None
            except requests.RequestException as e:
                logger.error(f"Ollama embedding request error (model={model}, chars={len(prompt)}): {e}")
                if attempt < EMBEDDING_RETRY_ATTEMPTS:
                    time.sleep(EMBEDDING_RETRY_BASE_DELAY_S * attempt)
                    continue
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



    # ==================== Utility Methods ====================

    def list_models(self) -> List[str]:
        """List available models from the configured provider."""
        if MOCK_MODE:
            return ["mock-model-1", "mock-model-2"]

        if self.provider == "openai":
            if self.openai_api_key:
                return ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]
            return []
        elif self.provider == "anthropic":
            if self.anthropic_api_key:
                return ["claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"]
            return []
        else:
            # Ollama
            api_url = f"{self.ollama_url}/api/tags"
            try:
                response = requests.get(api_url, timeout=10)
                response.raise_for_status()
                data = response.json()
                return [model['name'] for model in data.get('models', [])]
            except requests.RequestException as e:
                logger.error(f"Failed to list Ollama models: {e}")
                return []

    def model_exists(self, model_name: str) -> bool:
        """Check if a model is available."""
        if MOCK_MODE:
            return True

        if self.provider in ("openai", "anthropic"):
            return model_name in self.list_models()
        else:
            # Ollama
            available_models = self.list_models()
            model_base = model_name.split(':')[0]
            for m in available_models:
                if m == model_name or m.split(':')[0] == model_base:
                    return True
            return False

    def pull_model(self, model_name: str) -> bool:
        """Pull/download a model. Only applicable for Ollama."""
        if MOCK_MODE:
            return True

        if self.provider in ("openai", "anthropic"):
            logger.info(f"Model pulling not applicable for {self.provider}")
            return True

        # Ollama model pull
        api_url = f"{self.ollama_url}/api/pull"
        logger.info(f"Pulling model '{model_name}' from Ollama...")

        try:
            resp = requests.post(
                api_url,
                json={"name": model_name, "stream": True},
                stream=True,
                timeout=7200
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

    def ensure_models_available(self, models_config: Dict[str, str]) -> bool:
        """Ensure all required models are available."""
        if self.provider in ("openai", "anthropic"):
            return True

        # Ollama - check and pull if needed
        models_to_check = []
        if models_config.get("model"):
            models_to_check.append(("chat", models_config["model"]))
        if models_config.get("embedding_model"):
            models_to_check.append(("embedding", models_config["embedding_model"]))
        if models_config.get("vision_model"):
            models_to_check.append(("vision", models_config["vision_model"]))

        all_available = True
        for model_type, model_name in models_to_check:
            if not self.model_exists(model_name):
                logger.warning(f"{model_type.capitalize()} model '{model_name}' not found. Attempting to pull...")
                if self.pull_model(model_name):
                    logger.info(f"{model_type.capitalize()} model '{model_name}' is now available")
                else:
                    logger.error(f"Failed to pull {model_type} model '{model_name}'")
                    all_available = False
            else:
                logger.debug(f"{model_type.capitalize()} model '{model_name}' is available")

        return all_available

    def list_vision_models(self) -> List[str]:
        """List vision-capable models."""
        if self.provider == "openai":
            return ["gpt-4o", "gpt-4o-mini", "gpt-4-vision-preview"]
        elif self.provider == "anthropic":
            return []
        else:
            # Ollama
            all_models = self.list_models()
            vision_available = []

            for model in all_models:
                model_base = model.split(':')[0].lower()
                if model_base in VISION_MODELS or any(vm in model.lower() for vm in VISION_MODELS):
                    vision_available.append(model)

            return vision_available

    def describe_image_base64(self, image_base64: str, model: Optional[str] = None, prompt: Optional[str] = None) -> Optional[str]:
        """Describe an image from base64 data."""
        if MOCK_MODE:
            return "This is a mock image description from base64 data."

        default_prompt = "Describe this image in detail. Include any visible text, objects, people, settings, colors, and notable features."
        prompt = prompt or default_prompt

        if self.provider == "openai":
            if not self.openai_api_key:
                logger.error("OpenAI API key not configured")
                return None

            model = model or "gpt-4o"

            try:
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
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                            ]
                        }],
                        "max_tokens": 1000
                    },
                    timeout=180
                )
                response.raise_for_status()
                result = response.json()
                return result["choices"][0]["message"]["content"]
            except Exception as e:
                logger.error(f"OpenAI vision from base64 failed: {e}")
                return None
        else:
            # Ollama
            model = model or self.ollama_vision_model

            try:
                url = f"{self.ollama_url}/api/generate"
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
                logger.error(f"Ollama vision from base64 failed: {e}")
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
    """
    Legacy wrapper - delegates to LLMClient.

    .. deprecated::
        Use ``LLMClient().generate_json()`` instead.
    """
    if MOCK_MODE:
        logger.info("Returning MOCK LLM response")
        return {
            "title": "Mock Title",
            "author": "Mock Author",
            "created_hint": "2023-01-01",
            "tags": ["mock", "test"],
            "summary": "This is a mock summary."
        }

    return get_client().generate_json(prompt, model)

def embed_text(text: str, model: str = EMBEDDING_MODEL) -> Optional[List[float]]:
    """
    Legacy wrapper - delegates to LLMClient.

    .. deprecated::
        Use ``LLMClient().embed_text()`` instead.
    """
    if MOCK_MODE:
        import random
        return [random.random() for _ in range(768)]

    return get_client().embed_text(text, model)

def generate_text(prompt: str, model: str = MODEL) -> Optional[str]:
    """
    Legacy wrapper - delegates to LLMClient.

    .. deprecated::
        Use ``LLMClient().generate_text()`` instead.
    """
    if MOCK_MODE:
        return "This is a mock answer based on the retrieved documents."

    return get_client().generate_text(prompt, model)

def list_models(url: str = None) -> List[str]:
    """
    Legacy wrapper - delegates to LLMClient.

    .. deprecated::
        Use ``LLMClient().list_models()`` instead.
    """
    if MOCK_MODE:
        return ["mock-model-1", "mock-model-2"]

    if url and url != OLLAMA_URL:
        # Create temporary client with custom URL
        client = LLMClient({"provider": "ollama", "url": url})
        return client.list_models()

    return get_client().list_models()

def model_exists(model_name: str, url: str = None) -> bool:
    """
    Legacy wrapper - delegates to LLMClient.

    .. deprecated::
        Use ``LLMClient().model_exists()`` instead.
    """
    if MOCK_MODE:
        return True

    if url and url != OLLAMA_URL:
        client = LLMClient({"provider": "ollama", "url": url})
        return client.model_exists(model_name)

    return get_client().model_exists(model_name)

def pull_model(model_name: str, url: str = None) -> bool:
    """
    Legacy wrapper - delegates to LLMClient.

    .. deprecated::
        Use ``LLMClient().pull_model()`` instead.
    """
    if MOCK_MODE:
        return True

    if url and url != OLLAMA_URL:
        client = LLMClient({"provider": "ollama", "url": url})
        return client.pull_model(model_name)

    return get_client().pull_model(model_name)

def ensure_models_available(config: Dict[str, Any]) -> bool:
    """
    Legacy wrapper - delegates to LLMClient.

    .. deprecated::
        Use ``LLMClient().ensure_models_available()`` instead.
    """
    if config.get("provider") != "ollama":
        return True

    # Create client with this specific config
    client = LLMClient(config)
    return client.ensure_models_available(config)

def list_vision_models() -> List[str]:
    """
    Legacy wrapper - delegates to LLMClient.

    .. deprecated::
        Use ``LLMClient().list_vision_models()`` instead.
    """
    return get_client().list_vision_models()

def describe_image(
    image_path: str,
    model: str = VISION_MODEL,
    prompt: str = "Describe this image in detail. Include any visible text, objects, people, settings, colors, and notable features."
) -> Optional[str]:
    """
    Legacy wrapper - delegates to LLMClient.

    .. deprecated::
        Use ``LLMClient().describe_image()`` instead.
    """
    if MOCK_MODE:
        return "This is a mock image description. The image shows a scene with various elements."

    return get_client().describe_image(image_path, model, prompt)

def describe_image_base64(
    image_base64: str,
    model: str = VISION_MODEL,
    prompt: str = "Describe this image in detail. Include any visible text, objects, people, settings, colors, and notable features."
) -> Optional[str]:
    """
    Legacy wrapper - delegates to LLMClient.

    .. deprecated::
        Use ``LLMClient().describe_image_base64()`` instead.
    """
    if MOCK_MODE:
        return "This is a mock image description from base64 data."

    return get_client().describe_image_base64(image_base64, model, prompt)
