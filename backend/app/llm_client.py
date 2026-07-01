from __future__ import annotations

import httpx


class LLMError(Exception):
    pass


class LLMClient:
    def __init__(
        self,
        spec: str,
        ollama_host: str = "http://localhost:11434",
        openrouter_api_key: str = "",
    ):
        if spec.startswith("local:"):
            self.backend = "ollama"
            self.model = spec[len("local:"):]
            self._ollama_host = ollama_host.rstrip("/")
        elif spec.startswith("openrouter:"):
            self.backend = "openrouter"
            self.model = spec[len("openrouter:"):]
            self._api_key = openrouter_api_key
        else:
            raise ValueError(f"Unknown LLM spec: {spec!r}. Use 'local:<model>' or 'openrouter:<model>'.")

    def translate(self, text: str, prompt_template: str = "{text}") -> str:
        prompt = prompt_template.replace("{text}", text)
        try:
            if self.backend == "ollama":
                return self._call_ollama(prompt)
            return self._call_openrouter(prompt)
        except LLMError:
            raise
        except Exception as exc:
            raise LLMError(str(exc)) from exc

    def _call_ollama(self, prompt: str) -> str:
        try:
            resp = httpx.post(
                f"{self._ollama_host}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=120.0,
            )
            resp.raise_for_status()
            return resp.json()["response"]
        except httpx.HTTPError as exc:
            raise LLMError(f"Ollama error: {exc}") from exc

    def _call_openrouter(self, prompt: str) -> str:
        try:
            resp = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=120.0,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except httpx.HTTPError as exc:
            raise LLMError(f"OpenRouter error: {exc}") from exc
