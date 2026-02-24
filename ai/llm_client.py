"""
LLM Client — pluggable large-language-model integration.

Supports:
  - Ollama  (local, free — llama3, mistral, phi3, …)
  - OpenAI  (GPT-4o, GPT-4-turbo, …)
  - Anthropic Claude (claude-3-5-sonnet, …)
  - Any OpenAI-compatible endpoint (Together, Groq, LM Studio, …)

Provides:
  - Firmware generation from natural-language requirements
  - Intelligent fault diagnosis from telemetry
  - RF configuration recommendations
  - Research queries with context injection
  - Multi-turn conversation memory
"""

import asyncio
import json
import logging
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class Message:
    """A single conversation message."""

    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}


class ConversationMemory:
    """Rolling conversation history with token-budget trimming."""

    def __init__(self, max_messages: int = 20):
        self._messages: List[Message] = []
        self.max_messages = max_messages

    def add(self, role: str, content: str) -> None:
        self._messages.append(Message(role, content))
        if len(self._messages) > self.max_messages:
            # Always keep the system message at index 0
            self._messages = self._messages[:1] + self._messages[-(self.max_messages - 1):]

    def to_api_list(self) -> List[Dict[str, str]]:
        return [m.to_dict() for m in self._messages]

    def clear(self) -> None:
        self._messages = self._messages[:1]  # keep system prompt


class LLMClient:
    """
    Unified LLM client supporting multiple backends.

    Usage:
        client = LLMClient.from_config({
            "provider": "ollama",
            "model": "llama3",
            "base_url": "http://localhost:11434",
        })
        response = await client.chat("What is the best LoRa SF for 10 km range?")
    """

    SYSTEM_PROMPT = """You are an expert embedded systems engineer specialising in:
- ESP32 microcontroller programming (Arduino / ESP-IDF)
- RF communications: WiFi, BLE 5, LoRa, 433/868/915 MHz ISM bands
- GNSS/GPS integration
- Real-time multi-agent orchestration systems
- AI-driven adaptive radio control

Always provide practical, concise answers. When asked to generate firmware code,
produce valid C++ for ESP32 with the Arduino framework. When recommending
frequencies or modulation schemes, cite the applicable regulations."""

    def __init__(
        self,
        provider: str = "ollama",
        model: str = "llama3",
        base_url: str = "http://localhost:11434",
        api_key: str = "",
        temperature: float = 0.3,
        max_tokens: int = 2048,
        timeout: int = 60,
    ):
        self.provider = provider.lower()
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self._memory = ConversationMemory()
        self._memory.add("system", self.SYSTEM_PROMPT)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "LLMClient":
        """Create a client from a config dict."""
        provider = config.get("provider", "ollama")
        defaults: Dict[str, Any] = {
            "ollama": {"base_url": "http://localhost:11434", "model": "llama3"},
            "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o"},
            "anthropic": {"base_url": "https://api.anthropic.com/v1", "model": "claude-3-5-sonnet-20241022"},
            "groq": {"base_url": "https://api.groq.com/openai/v1", "model": "llama-3.1-70b-versatile"},
            "lmstudio": {"base_url": "http://localhost:1234/v1", "model": "local-model"},
        }
        d = defaults.get(provider, {})
        return cls(
            provider=provider,
            model=config.get("model", d.get("model", "llama3")),
            base_url=config.get("base_url", d.get("base_url", "http://localhost:11434")),
            api_key=config.get("api_key", ""),
            temperature=config.get("temperature", 0.3),
            max_tokens=config.get("max_tokens", 2048),
            timeout=config.get("timeout", 60),
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def chat(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        remember: bool = True,
    ) -> Dict[str, Any]:
        """
        Send a message and return the LLM response.

        Parameters
        ----------
        message  : User message string
        context  : Optional dict injected into the message as JSON context
        remember : Whether to save this turn to conversation memory
        """
        if context:
            full_msg = f"{message}\n\nContext:\n```json\n{json.dumps(context, indent=2)}\n```"
        else:
            full_msg = message

        if remember:
            self._memory.add("user", full_msg)

        try:
            if self.provider == "ollama":
                reply = await self._ollama_chat()
            elif self.provider == "anthropic":
                reply = await self._anthropic_chat()
            else:
                # OpenAI-compatible: openai, groq, lmstudio, together, etc.
                reply = await self._openai_chat()

            if remember:
                self._memory.add("assistant", reply)

            return {
                "provider": self.provider,
                "model": self.model,
                "response": reply,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("LLM call failed (%s/%s): %s — using fallback", self.provider, self.model, exc)
            return self._fallback_response(message)

    async def generate_firmware(
        self,
        requirements: str,
        features: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Ask the LLM to generate ESP32 firmware code from natural-language requirements.
        """
        features_str = ", ".join(features) if features else "WiFi, BLE"
        prompt = (
            f"Generate complete ESP32 Arduino C++ firmware for the following requirements:\n\n"
            f"Requirements: {requirements}\n"
            f"Features to include: {features_str}\n\n"
            f"Produce the full main.cpp with setup() and loop(). "
            f"Include HTTP API endpoints compatible with the multi-agent orchestration system "
            f"(command: set_frequency, get_rssi, set_modulation, get_status, ota_update). "
            f"Return only valid C++ code in a single code block."
        )
        return await self.chat(prompt, remember=False)

    async def diagnose(self, telemetry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyse device telemetry and diagnose issues.
        """
        prompt = (
            "Analyse the following ESP32 device telemetry and identify any issues, "
            "risks, or optimisation opportunities. Provide actionable recommendations."
        )
        return await self.chat(prompt, context=telemetry, remember=False)

    async def recommend_rf_config(
        self, scenario: str, constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Recommend optimal RF configuration for a given scenario.
        """
        prompt = (
            f"Recommend the optimal RF configuration (frequency, modulation, TX power, "
            f"channel plan) for this scenario: {scenario}. "
            f"Consider range, data rate, power consumption, and regulatory compliance."
        )
        return await self.chat(prompt, context=constraints, remember=False)

    def reset_memory(self) -> None:
        """Clear conversation history (keeps system prompt)."""
        self._memory.clear()

    def get_history(self) -> List[Dict[str, str]]:
        return self._memory.to_api_list()

    # ------------------------------------------------------------------
    # Provider implementations
    # ------------------------------------------------------------------

    async def _ollama_chat(self) -> str:
        """Call Ollama's /api/chat endpoint."""
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": self._memory.to_api_list(),
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
        }
        response = await self._http_post(url, payload)
        return response.get("message", {}).get("content", "")

    async def _openai_chat(self) -> str:
        """Call an OpenAI-compatible /v1/chat/completions endpoint."""
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": self._memory.to_api_list(),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        response = await self._http_post(url, payload, auth_bearer=True)
        return response["choices"][0]["message"]["content"]

    async def _anthropic_chat(self) -> str:
        """Call Anthropic Messages API."""
        url = f"{self.base_url}/messages"
        messages = [m for m in self._memory.to_api_list() if m["role"] != "system"]
        system = next(
            (m["content"] for m in self._memory.to_api_list() if m["role"] == "system"), ""
        )
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": messages,
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        response = await self._http_post(url, payload, extra_headers=headers)
        return response["content"][0]["text"]

    # ------------------------------------------------------------------
    # HTTP helper
    # ------------------------------------------------------------------

    async def _http_post(
        self,
        url: str,
        payload: Dict[str, Any],
        auth_bearer: bool = False,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_post, url, payload, auth_bearer, extra_headers)

    def _sync_post(
        self,
        url: str,
        payload: Dict[str, Any],
        auth_bearer: bool,
        extra_headers: Optional[Dict[str, str]],
    ) -> Dict[str, Any]:
        body = json.dumps(payload).encode()
        headers = {"Content-Type": "application/json"}
        if auth_bearer and self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if extra_headers:
            headers.update(extra_headers)
        req = urllib.request.Request(url, data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read())

    # ------------------------------------------------------------------
    # Fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _fallback_response(message: str) -> Dict[str, Any]:
        return {
            "provider": "fallback",
            "model": "builtin",
            "response": (
                "LLM endpoint unavailable. Built-in heuristic response:\n\n"
                "For ESP32 RF optimisation:\n"
                "• WiFi 2.4GHz: channels 1, 6, 11 are non-overlapping\n"
                "• WiFi 5GHz: channels 36–64 (UNII-1/2) preferred for low interference\n"
                "• LoRa 915MHz: SF7 for speed, SF12 for maximum range\n"
                "• BLE 5: 2M PHY for throughput, Coded PHY (S8) for 400m+ range\n"
                "• GPS: enable WAAS/SBAS for sub-3m accuracy\n\n"
                "Install Ollama (https://ollama.ai) and run: ollama pull llama3"
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
