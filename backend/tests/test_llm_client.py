"""Unit tests for LLMClient — mocked httpx, no real LLM calls."""
import pytest
from unittest.mock import MagicMock, patch


class TestLLMClientLocal:
    def test_local_prefix_calls_ollama(self):
        from app.llm_client import LLMClient

        client = LLMClient("local:llama3")
        assert client.backend == "ollama"
        assert client.model == "llama3"

    def test_ollama_translate_posts_to_generate_endpoint(self):
        from app.llm_client import LLMClient

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"response": "translated text"}

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            client = LLMClient("local:llama3", ollama_host="http://localhost:11434")
            result = client.translate("Olá mundo", prompt_template="Translate:\n\n{text}")

        assert result == "translated text"
        call_url = mock_post.call_args[0][0]
        assert "generate" in call_url
        assert "localhost:11434" in call_url

    def test_ollama_translate_fills_prompt_template(self):
        from app.llm_client import LLMClient

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"response": "hello"}

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            client = LLMClient("local:llama3", ollama_host="http://localhost:11434")
            client.translate("Olá", prompt_template="Translate to English:\n\n{text}")

        payload = mock_post.call_args[1]["json"]
        assert "Olá" in payload["prompt"]
        assert payload["model"] == "llama3"

    def test_ollama_http_error_raises_llm_error(self):
        from app.llm_client import LLMClient, LLMError
        import httpx

        with patch("httpx.post", side_effect=httpx.HTTPError("timeout")):
            client = LLMClient("local:llama3", ollama_host="http://localhost:11434")
            with pytest.raises(LLMError):
                client.translate("text", prompt_template="{text}")


class TestLLMClientOpenRouter:
    def test_openrouter_prefix_sets_backend(self):
        from app.llm_client import LLMClient

        client = LLMClient("openrouter:mistral/mistral-7b")
        assert client.backend == "openrouter"
        assert client.model == "mistral/mistral-7b"

    def test_openrouter_calls_chat_completions(self):
        from app.llm_client import LLMClient

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "translated"}}]
        }

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            client = LLMClient("openrouter:mistral/mistral-7b", openrouter_api_key="key123")
            result = client.translate("Olá", prompt_template="Translate:\n\n{text}")

        assert result == "translated"
        call_url = mock_post.call_args[0][0]
        assert "openrouter" in call_url
        assert "chat/completions" in call_url

    def test_openrouter_sends_auth_header(self):
        from app.llm_client import LLMClient

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"choices": [{"message": {"content": "ok"}}]}

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            client = LLMClient("openrouter:mistral/mistral-7b", openrouter_api_key="sk-abc")
            client.translate("text", prompt_template="{text}")

        headers = mock_post.call_args[1]["headers"]
        assert "sk-abc" in headers.get("Authorization", "")

    def test_openrouter_http_error_raises_llm_error(self):
        from app.llm_client import LLMClient, LLMError
        import httpx

        with patch("httpx.post", side_effect=httpx.HTTPError("conn refused")):
            client = LLMClient("openrouter:mistral/mistral-7b", openrouter_api_key="key")
            with pytest.raises(LLMError):
                client.translate("text", prompt_template="{text}")

    def test_unknown_prefix_raises_value_error(self):
        from app.llm_client import LLMClient

        with pytest.raises(ValueError, match="Unknown LLM spec"):
            LLMClient("unknown:model")
