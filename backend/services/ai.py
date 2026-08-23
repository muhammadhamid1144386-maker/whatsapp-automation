"""AIProvider abstraction.

AI_PROVIDER=gemini (default, via the Emergent universal key) or AI_PROVIDER=ollama.
The API key never leaves the backend.
"""

import json
import logging
import os
import re
from abc import ABC, abstractmethod
from typing import Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

URDU_SCRIPT = re.compile(r"[\u0600-\u06FF]")
ROMAN_URDU_HINTS = {
    "aap", "ap", "kya", "kia", "hai", "hain", "nahi", "nai", "mein", "mai", "karo", "kar", "krdo",
    "chahiye", "chahye", "acha", "theek", "thik", "shukriya", "bhai", "kitna", "kitne", "kitni",
    "order", "de", "do", "dedo", "haan", "han", "ji", "jee", "mera", "meri", "apna", "sath",
    "khana", "paisa", "rupay", "jaldi", "please", "krna", "krdo", "hogaya", "gaya", "abhi",
    "dikhao", "dikhaen", "dikhayen", "dikhaye", "dikha", "batao", "bataen", "bata", "bhejo",
    "bhej", "bhejen", "chahta", "chahti", "chahiyen", "lena", "lo", "loon", "mangwana", "mangao",
    "karna", "karain", "karen", "karein", "kardo", "kardein", "kar", "hoga", "hogi", "hoga",
    "milega", "milegi", "mil", "sasta", "mehnga", "wala", "wali", "kuch", "thora", "zyada",
    "bilkul", "sahi", "yaar", "mujhe", "hum", "hamara", "tak", "phir", "wapis", "kahan",
    "aur", "ek", "ka", "ke", "ki", "ye", "yeh", "wo", "woh", "bhi", "sirf", "saath", "nahin",
}
# Words that are also ordinary English and must never trigger Roman Urdu on their own.
AMBIGUOUS_HINTS = {"order", "please", "do"}


def detect_language(text: str) -> str:
    if not text:
        return "en"
    if URDU_SCRIPT.search(text):
        return "ur"
    words = {w.strip(".,!?").lower() for w in text.split()}
    if (words & ROMAN_URDU_HINTS) - AMBIGUOUS_HINTS:
        return "roman_ur"
    return "en"


class AIProvider(ABC):
    name = "abstract"

    @abstractmethod
    async def generate_response(
        self,
        *,
        system_message: str,
        session_id: str,
        user_text: str,
        tools: Optional[list[dict]] = None,
        dispatch: Optional[Callable[[str, dict], Awaitable[dict]]] = None,
        max_iterations: int = 6,
    ) -> list[str]: ...

    def detect_language(self, text: str) -> str:
        return detect_language(text)

    async def extract_intent(self, text: str) -> str:
        lowered = (text or "").lower()
        if any(k in lowered for k in ("menu", "kya hai", "list", "rate")):
            return "browse_menu"
        if any(k in lowered for k in ("status", "kahan", "where is my order", "track")):
            return "order_status"
        if any(k in lowered for k in ("agent", "human", "manager", "complain", "shikayat", "baat karo")):
            return "human_handoff"
        if any(k in lowered for k in ("confirm", "yes place", "haan", "kardo", "ok place")):
            return "confirm_order"
        return "general"

    async def generate_upsell(self, cart_items: list[str], addons: list[dict], language: str) -> Optional[str]:
        candidate = next((a for a in addons if a["name"] not in cart_items and a.get("available", True)), None)
        if not candidate:
            return None
        if language == "roman_ur":
            return f"{candidate['name']} PKR {candidate['price']:.0f} mein add kar dein?"
        if language == "ur":
            return f"{candidate['name']} PKR {candidate['price']:.0f} میں شامل کر دوں؟"
        return f"Would you like to add {candidate['name']} for PKR {candidate['price']:.0f}?"


class GeminiProvider(AIProvider):
    name = "gemini"

    def __init__(self) -> None:
        self.api_key = os.environ.get("EMERGENT_LLM_KEY", "")
        self.model = os.environ.get("AI_MODEL", "gemini-3-flash-preview")

    async def generate_response(
        self, *, system_message, session_id, user_text, tools=None, dispatch=None, max_iterations=6
    ) -> list[str]:
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        if not self.api_key:
            raise RuntimeError("EMERGENT_LLM_KEY is not configured")

        chat = LlmChat(api_key=self.api_key, session_id=session_id, system_message=system_message).with_model(
            "gemini", self.model
        )
        if tools:
            chat = chat.with_tools(tools, tool_choice="auto")

        outputs: list[str] = []
        message = UserMessage(text=user_text)
        for _ in range(max_iterations):
            response = await (chat.send_message_with_tools(message) if message else chat.send_message_with_tools())
            message = None
            if getattr(response, "content", None):
                cleaned = response.content.strip()
                if cleaned:
                    outputs.append(cleaned)
            tool_calls = getattr(response, "tool_calls", None) or []
            if not tool_calls:
                break
            for call in tool_calls:
                args = call.arguments if isinstance(call.arguments, dict) else {}
                try:
                    result = await dispatch(call.name, args) if dispatch else {"error": "no dispatcher"}
                except Exception as exc:
                    logger.exception("tool %s failed", call.name)
                    result = {"ok": False, "error": f"Tool failed: {exc}"}
                chat.add_tool_result(call.id, json.dumps(result, default=str))
        return outputs


class OllamaProvider(AIProvider):
    """Optional self-hosted provider. Not required for the MVP."""

    name = "ollama"

    async def generate_response(self, **kwargs) -> list[str]:
        base = os.environ.get("OLLAMA_BASE_URL", "")
        if not base:
            raise RuntimeError("AI_PROVIDER=ollama requires OLLAMA_BASE_URL to be set")
        raise NotImplementedError("Ollama provider is scaffolded but not enabled in the MVP")


_cache: dict[str, AIProvider] = {}


def get_ai_provider() -> AIProvider:
    key = os.environ.get("AI_PROVIDER", "gemini").lower()
    if key not in _cache:
        _cache[key] = OllamaProvider() if key == "ollama" else GeminiProvider()
    return _cache[key]
