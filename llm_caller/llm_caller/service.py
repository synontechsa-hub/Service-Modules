import json
import logging
import requests
from typing import Optional

from .config import LLMCallerConfig

logger = logging.getLogger(__name__)


class LLMCallerError(Exception):
    """Base class for LLM caller exceptions."""
    pass


class LLMCallerAPIError(LLMCallerError):
    """Raised when the LLM API returns an error response."""
    pass


class LLMCallerConfigError(LLMCallerError):
    """Raised when the configuration is invalid."""
    pass


class LLMCallerService:
    """
    Minimal, unified interface for calling LLM APIs.
    
    NOTE: This implementation uses the `requests` library and is synchronous.
    For use in async applications (like FastAPI), call this service in a 
    thread pool using `anyio.to_thread.run_sync` or consider swapping 
    `requests` for `httpx`.
    """
    def __init__(self, config: LLMCallerConfig):
        self.config = config
        self._session = requests.Session()

    def call(self, prompt: str, system: Optional[str] = None) -> str:
        """
        Sends a single prompt to the configured LLM endpoint and returns the
        text of the reply.
        """
        if not self.config.api_key:
            raise LLMCallerConfigError("LLM_API_KEY is not set.")

        try:
            response = self._session.post(
                self.config.api_url,
                headers=self._build_headers(),
                json=self._build_payload(prompt, system),
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error("llm_caller: request failed", error=str(e), url=self.config.api_url)
            raise LLMCallerAPIError(f"LLM request failed: {e}") from e

        data = response.json()

        # Anthropic-style response parsing by default
        try:
            text_blocks = [
                block["text"] for block in data.get("content", [])
                if block.get("type") == "text"
            ]
            reply = "\n".join(text_blocks).strip()
            
            if not reply:
                logger.warning("llm_caller: received empty reply", model=self.config.model)
                
            return reply
        except (KeyError, TypeError) as e:
            logger.error("llm_caller: unexpected response shape", response=json.dumps(data)[:500])
            raise LLMCallerAPIError(f"Unexpected response shape: {json.dumps(data)[:500]}") from e

    def _build_headers(self) -> dict:
        # Default to Anthropic headers
        return {
            "Content-Type": "application/json",
            "x-api-key": self.config.api_key,
            "anthropic-version": self.config.anthropic_version,
        }

    def _build_payload(self, prompt: str, system: Optional[str] = None) -> dict:
        payload = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system
        return payload
