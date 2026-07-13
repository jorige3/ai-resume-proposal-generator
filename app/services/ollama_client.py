import os
import requests
from typing import Optional
from dotenv import load_dotenv

# Load configuration from .env file
load_dotenv()


class OllamaConnectionError(Exception):
    """Exception raised when connection to the Ollama server fails."""

    pass


class OllamaTimeoutError(Exception):
    """Exception raised when the Ollama server request times out."""

    pass


class OllamaResponseError(Exception):
    """Exception raised when the Ollama response is invalid, error status, or malformed."""

    pass


class OllamaClient:
    """HTTP Client to interact with local Ollama API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        # Load configs from environment with defaults targeting Docker Host IP and Qwen model
        self.base_url = (
            base_url
            or os.environ.get("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
        ).rstrip("/")
        self.model = model or os.environ.get("OLLAMA_MODEL", "qwen3:1.7b")

        timeout_str = os.environ.get("OLLAMA_TIMEOUT", "120.0")
        try:
            self.timeout = float(timeout if timeout is not None else timeout_str)
        except ValueError:
            self.timeout = 120.0

        # Session for connection pooling and reuse
        self.session = requests.Session()


    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        format_json: bool = False,
    ) -> str:
        """Sends a text generation request to Ollama's /api/generate endpoint.

        Returns the generated text.
        """
        url = f"{self.base_url}/api/generate"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }

        if system:
            payload["system"] = system

        if format_json:
            payload["format"] = "json"

        try:
            response = self.session.post(
                url, json=payload, timeout=self.timeout
            )
            response.raise_for_status()
        except requests.exceptions.Timeout as e:
            raise OllamaTimeoutError(
                f"Ollama request timed out after {self.timeout}s: {e}"
            ) from e
        except requests.exceptions.ConnectionError as e:
            raise OllamaConnectionError(
                f"Failed to connect to Ollama server at {self.base_url}: {e}"
            ) from e
        except requests.exceptions.HTTPError as e:
            raise OllamaResponseError(
                f"Ollama server returned HTTP error: {e}"
            ) from e
        except Exception as e:
            raise OllamaResponseError(
                f"Unexpected error when calling Ollama API: {e}"
            ) from e

        try:
            data = response.json()
        except ValueError as e:
            raise OllamaResponseError(
                f"Ollama returned malformed JSON: {e}"
            ) from e

        if "response" not in data:
            raise OllamaResponseError(
                "Ollama response JSON did not contain the 'response' key"
            )

        return data["response"]

    def health_check(self) -> bool:
        """Verifies if the Ollama server is running and accessible."""
        url = f"{self.base_url}/"
        try:
            # Low timeout for health checks
            response = self.session.get(url, timeout=2.0)
            return (
                response.status_code == 200
                and "Ollama is running" in response.text
            )
        except Exception:
            return False

    def close(self):
        """Closes the underlying requests.Session."""
        self.session.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
