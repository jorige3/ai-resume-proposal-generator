import pytest
from unittest.mock import Mock, patch
import requests
from app.services.ollama_client import (
    OllamaClient,
    OllamaConnectionError,
    OllamaTimeoutError,
    OllamaResponseError,
)


def test_ollama_client_init():
    with patch.dict(
        "os.environ",
        {
            "OLLAMA_BASE_URL": "http://test-server:11434",
            "OLLAMA_MODEL": "test-model",
            "OLLAMA_TIMEOUT": "15.5",
        },
    ):
        client = OllamaClient()
        assert client.base_url == "http://test-server:11434"
        assert client.model == "test-model"
        assert client.timeout == 15.5


def test_ollama_client_generate_success():
    client = OllamaClient()
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"response": "This is generated text"}

    with patch.object(client.session, "post", return_value=mock_response) as mock_post:
        result = client.generate("Hello world", system="system info", format_json=True)
        assert result == "This is generated text"
        mock_post.assert_called_once_with(
            "http://host.docker.internal:11434/api/generate",
            json={
                "model": "qwen3:1.7b",
                "prompt": "Hello world",
                "stream": False,
                "system": "system info",
                "format": "json",
            },
            timeout=120.0,
        )



def test_ollama_client_generate_connection_error():
    client = OllamaClient()
    with patch.object(
        client.session,
        "post",
        side_effect=requests.exceptions.ConnectionError("Connection refused"),
    ):
        with pytest.raises(OllamaConnectionError):
            client.generate("Hello")


def test_ollama_client_generate_timeout_error():
    client = OllamaClient()
    with patch.object(
        client.session,
        "post",
        side_effect=requests.exceptions.Timeout("Read timeout"),
    ):
        with pytest.raises(OllamaTimeoutError):
            client.generate("Hello")


def test_ollama_client_generate_http_error():
    client = OllamaClient()
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
        "500 Server Error"
    )
    with patch.object(client.session, "post", return_value=mock_response):
        with pytest.raises(OllamaResponseError):
            client.generate("Hello")


def test_ollama_client_generate_malformed_json():
    client = OllamaClient()
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("Invalid JSON")
    with patch.object(client.session, "post", return_value=mock_response):
        with pytest.raises(OllamaResponseError):
            client.generate("Hello")


def test_ollama_client_generate_missing_key():
    client = OllamaClient()
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"some_other_key": "some_value"}
    with patch.object(client.session, "post", return_value=mock_response):
        with pytest.raises(OllamaResponseError):
            client.generate("Hello")


def test_ollama_client_health_check_success():
    client = OllamaClient()
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = "Ollama is running"
    with patch.object(client.session, "get", return_value=mock_response):
        assert client.health_check() is True


def test_ollama_client_health_check_failure():
    client = OllamaClient()
    with patch.object(
        client.session, "get", side_effect=Exception("Network down")
    ):
        assert client.health_check() is False
