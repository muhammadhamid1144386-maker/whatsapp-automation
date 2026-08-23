"""Minimal emergentintegrations.llm.chat replacement using the Google Gemini REST API.

This provides the same LlmChat / UserMessage interface the application expects,
backed by direct calls to the Gemini generateContent endpoint. It supports
tool-calling (function declarations) and multi-turn conversations.
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"


@dataclass
class UserMessage:
    text: str


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class ToolResponse:
    content: Optional[str] = None
    tool_calls: list[ToolCall] = field(default_factory=list)


class LlmChat:
    def __init__(self, *, api_key: str, session_id: str, system_message: str):
        self.api_key = api_key
        self.session_id = session_id
        self.system_message = system_message
        self._model_provider = "gemini"
        self._model_name = "gemini-2.0-flash"
        self._tools: Optional[list[dict]] = None
        self._tool_choice: str = "auto"
        self._history: list[dict] = []
        self._call_counter = 0

    def with_model(self, provider: str, model: str) -> "LlmChat":
        self._model_provider = provider
        self._model_name = model
        return self

    def with_tools(self, tools: list[dict], tool_choice: str = "auto") -> "LlmChat":
        self._tools = tools
        self._tool_choice = tool_choice
        return self

    def add_tool_result(self, call_id: str, result_json: str):
        self._history.append({
            "role": "function",
            "name": call_id.split(":")[0] if ":" in call_id else call_id,
            "parts": [{"functionResponse": {"name": call_id, "response": {"content": result_json}}}],
        })

    def _to_gemini_tools(self) -> Optional[dict]:
        if not self._tools:
            return None
        declarations = []
        for tool in self._tools:
            if tool.get("type") == "function" and "function" in tool:
                fn = tool["function"]
                declarations.append({
                    "name": fn["name"],
                    "description": fn.get("description", ""),
                    "parameters": fn.get("parameters", {"type": "object", "properties": {}}),
                })
        if not declarations:
            return None
        return {"functionDeclarations": declarations}

    async def send_message_with_tools(self, message: Optional[UserMessage] = None) -> ToolResponse:
        if message is not None:
            self._history.append({
                "role": "user",
                "parts": [{"text": message.text}],
            })

        url = f"{GEMINI_BASE}/models/{self._model_name}:generateContent?key={self.api_key}"
        body: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": self.system_message}]},
            "contents": self._history,
        }
        tools = self._to_gemini_tools()
        if tools:
            body["tools"] = [tools]
            body["toolConfig"] = {"functionCallingConfig": {"mode": "AUTO"}}

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=body)

        if resp.status_code != 200:
            error_text = resp.text[:500]
            logger.error("Gemini API error %d: %s", resp.status_code, error_text)
            raise RuntimeError(f"Gemini API returned {resp.status_code}: {error_text}")

        data = resp.json()
        candidate = (data.get("candidates") or [{}])[0]
        content = candidate.get("content", {})
        parts = content.get("parts", [])

        text_output = ""
        tool_calls: list[ToolCall] = []

        for part in parts:
            if "text" in part:
                text_output += part["text"]
            if "functionCall" in part:
                fc = part["functionCall"]
                self._call_counter += 1
                call_id = f"{fc.get('name', 'tool')}:{self._call_counter}"
                args = fc.get("args", {})
                if not isinstance(args, dict):
                    args = {"value": args}
                tool_calls.append(ToolCall(id=call_id, name=fc.get("name", ""), arguments=args))

        if text_output or tool_calls:
            self._history.append({
                "role": "model",
                "parts": parts,
            })

        return ToolResponse(content=text_output.strip() if text_output else None, tool_calls=tool_calls)
